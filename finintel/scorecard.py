"""Turns raw series into driver signals and composite scores (spec section 5)."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd

from .config import CONTESTED_BELOW, MIN_OBS, ZSCORE_LOOKBACK_DAYS

HORIZONS = ("short", "medium", "long")


def to_daily(s: pd.Series) -> pd.Series:
    """Calendar-daily, forward-filled, so windows are in calendar days for every frequency."""
    s = s[~s.index.duplicated(keep="last")].sort_index()
    idx = pd.date_range(s.index.min(), s.index.max(), freq="D")
    return s.reindex(idx).ffill()


def transform(s: pd.Series, how: str, window: int) -> pd.Series:
    d = to_daily(s)
    if how == "level":
        return d
    if how == "diff":
        return d - d.shift(window)
    if how == "pct":
        return 100 * (d / d.shift(window) - 1)
    if how == "sum":
        # sums of flow series must not double-count forward-filled values
        raw = s[~s.index.duplicated(keep="last")].sort_index()
        flows = raw.reindex(pd.date_range(raw.index.min(), raw.index.max(), freq="D")).fillna(0)
        return flows.rolling(window, min_periods=1).sum()
    if how == "vs_sma200":
        raw = s.sort_index()
        sma = raw.rolling(window, min_periods=int(window * 0.9)).mean()
        return to_daily(100 * (raw / sma - 1))
    raise ValueError(f"unknown transform {how}")


def zscore_latest(x: pd.Series, lookback_days: int = ZSCORE_LOOKBACK_DAYS) -> tuple[float, float, int]:
    """z-score and percentile of the latest value against its own trailing history."""
    x = x.dropna()
    if x.empty:
        return np.nan, np.nan, 0
    hist = x[x.index >= x.index.max() - pd.Timedelta(days=lookback_days)]
    n = int(hist.nunique())
    sd = hist.std()
    if n < MIN_OBS or not sd or np.isnan(sd):
        return np.nan, np.nan, n
    z = (hist.iloc[-1] - hist.mean()) / sd
    pct = float((hist <= hist.iloc[-1]).mean() * 100)
    return float(z), pct, n


@dataclass
class DriverReading:
    key: str
    name: str
    layer: int
    weight: float
    horizons: dict
    bullish_when: str
    evidence_class: str
    source_name: str
    source_url: str
    value: float | None = None           # latest transformed value
    raw_value: float | None = None       # latest raw value
    as_of: str | None = None             # date of latest raw observation
    z: float | None = None
    percentile: float | None = None
    signal: float | None = None          # -2 .. +2
    signal_prev: float | None = None     # signal ~7 days earlier (for "what changed")
    status: str = "ok"                   # ok | missing | thin_history
    note: str = ""

    def to_dict(self):
        return asdict(self)


def read_driver(d: dict, raw: pd.Series | None, error: str | None = None) -> DriverReading:
    r = DriverReading(key=d["key"], name=d["name"], layer=d["layer"], weight=d["weight"],
                      horizons=d["horizons"], bullish_when=d["bullish_when"],
                      evidence_class=d["evidence_class"], source_name=d["source"][0], source_url=d["source"][1])
    if raw is None or raw.dropna().empty:
        r.status, r.note = "missing", (error or "no data")
        return r
    raw = raw.dropna()
    x = transform(raw, d["transform"], d["window"]).dropna()
    r.raw_value = float(raw.iloc[-1])
    r.as_of = raw.index.max().strftime("%Y-%m-%d")
    if x.empty:
        r.status, r.note = "thin_history", "not enough history for this transform"
        return r
    r.value = float(x.iloc[-1])
    z, pct, n = zscore_latest(x)
    if np.isnan(z):
        r.status, r.note = "thin_history", f"only {n} distinct observations; need {MIN_OBS}"
        return r
    r.z, r.percentile = z, pct
    r.signal = float(np.clip(d["direction"] * z, -2, 2))
    prev = x[x.index <= x.index.max() - pd.Timedelta(days=7)]
    if len(prev) > MIN_OBS:
        zp, _, _ = zscore_latest(prev)
        if not np.isnan(zp):
            r.signal_prev = float(np.clip(d["direction"] * zp, -2, 2))
    return r


@dataclass
class HorizonScore:
    composite: float | None
    agreement: float | None
    stance: str
    coverage: float          # share of total driver weight that had data


def stance_for(c: float) -> str:
    if c >= 1.0:
        return "Bullish"
    if c >= 0.35:
        return "Leaning bullish"
    if c > -0.35:
        return "Neutral"
    if c > -1.0:
        return "Leaning bearish"
    return "Bearish"


def score(readings: list[DriverReading], horizon: str) -> HorizonScore:
    total_w = sum(r.weight * r.horizons[horizon] for r in readings)
    live = [r for r in readings if r.signal is not None]
    w = np.array([r.weight * r.horizons[horizon] for r in live])
    s = np.array([r.signal for r in live])
    if len(live) == 0 or w.sum() == 0:
        return HorizonScore(None, None, "Insufficient data", 0.0)
    comp = float((w * s).sum() / w.sum())
    side = np.sign(comp) if comp != 0 else 1
    active = np.abs(s) >= 0.25            # signals near zero are neither for nor against
    agree = float(w[active & (np.sign(s) == side)].sum() / w[active].sum()) if active.any() else 1.0
    stance = stance_for(comp)
    if agree < CONTESTED_BELOW:
        stance = "Contested"
    return HorizonScore(round(comp, 2), round(agree, 2), stance, round(float(w.sum() / total_w), 2))


def contradictions(readings: list[DriverReading], composite: float | None) -> list[str]:
    """Drivers pointing against the composite, and conflicts between layers."""
    out = []
    if composite is None:
        return out
    side = 1 if composite >= 0 else -1
    for r in readings:
        if r.signal is not None and abs(r.signal) >= 0.75 and np.sign(r.signal) == -side:
            out.append(f"{r.name} points {'up' if r.signal > 0 else 'down'} ({r.signal:+.1f}) "
                       f"against the {'bullish' if side > 0 else 'bearish'} composite.")
    by_layer = {}
    for r in readings:
        if r.signal is not None:
            by_layer.setdefault(r.layer, []).append(r.signal * r.weight)
    lm = {k: sum(v) for k, v in by_layer.items()}
    if 1 in lm and 4 in lm and np.sign(lm[1]) != np.sign(lm[4]) and min(abs(lm[1]), abs(lm[4])) > 0.05:
        out.append(f"Layer conflict: macro layer is {'bullish' if lm[1] > 0 else 'bearish'}, "
                   f"positioning and flows layer is {'bullish' if lm[4] > 0 else 'bearish'}.")
    if 1 in lm and 3 in lm and np.sign(lm[1]) != np.sign(lm[3]) and min(abs(lm[1]), abs(lm[3])) > 0.05:
        out.append(f"Layer conflict: macro layer is {'bullish' if lm[1] > 0 else 'bearish'}, "
                   f"institutional layer is {'bullish' if lm[3] > 0 else 'bearish'}.")
    return out


def changes(readings: list[DriverReading], threshold: float = 0.5) -> list[str]:
    out = []
    for r in readings:
        if r.signal is not None and r.signal_prev is not None and abs(r.signal - r.signal_prev) >= threshold:
            out.append(f"{r.name}: signal moved {r.signal_prev:+.1f} -> {r.signal:+.1f} over the past week.")
    return out
