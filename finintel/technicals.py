"""Technical indicators, trend, market structure and the technical score (-100..+100)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .levels import swing_points


def weekly(df: pd.DataFrame) -> pd.DataFrame:
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df.resample("W-FRI").agg(agg).dropna(subset=["close"])


def indicators(df: pd.DataFrame, fast: int = 50, slow: int = 200) -> pd.DataFrame:
    """Columns sma50/sma200 hold the fast/slow averages (10/40 weeks on the weekly frame)."""
    c = df.close
    out = pd.DataFrame(index=df.index)
    out["close"] = c
    for name, n in (("sma20", 20), ("sma50", fast), ("sma200", slow)):
        out[name] = c.rolling(n, min_periods=int(n * 0.9)).mean()
    ema12, ema26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out.macd.ewm(span=9, adjust=False).mean()
    out["macd_hist"] = out.macd - out.macd_signal
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    out["rsi"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    tr = pd.concat([df.high - df.low, (df.high - c.shift()).abs(), (df.low - c.shift()).abs()], axis=1).max(axis=1)
    out["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    out["bb_up"], out["bb_lo"] = mid + 2 * sd, mid - 2 * sd
    out["vol30"] = c.pct_change().rolling(30).std() * np.sqrt(365) * 100
    if "volume" in df and df.volume.sum() > 0:
        out["volume"] = df.volume
        out["vol_ratio"] = df.volume / df.volume.rolling(20).mean()
    return out


def structure(df: pd.DataFrame, k: int = 5) -> dict:
    highs, lows = swing_points(df, k=k, lookback=250)
    h, l = highs[-2:], lows[-2:]
    if len(h) < 2 or len(l) < 2:
        return {"label": "Undetermined", "score": 0.0, "detail": "not enough swing points"}
    hh, hl = h[1][1] > h[0][1], l[1][1] > l[0][1]
    if hh and hl:
        lab, sc = "Higher highs and higher lows (uptrend structure)", 1.0
    elif not hh and not hl:
        lab, sc = "Lower highs and lower lows (downtrend structure)", -1.0
    else:
        lab, sc = "Mixed swings (range or transition)", 0.0
    return {"label": lab, "score": sc,
            "detail": f"last swing highs {h[0][1]:,.0f} -> {h[1][1]:,.0f}; last swing lows {l[0][1]:,.0f} -> {l[1][1]:,.0f}"}


def trend(ind: pd.DataFrame) -> dict:
    r = ind.iloc[-1]
    if pd.isna(r.sma50) or pd.isna(r.sma200):
        return {"label": "Undetermined", "score": 0.0}
    slope = (ind.sma50.iloc[-1] / ind.sma50.iloc[-11] - 1) * 100 if len(ind) > 11 else 0
    above200, above50, golden = r.close > r.sma200, r.close > r.sma50, r.sma50 > r.sma200
    s = (0.4 if above200 else -0.4) + (0.3 if above50 else -0.3) + (0.3 if golden else -0.3)
    if s >= 0.6:
        lab = "Uptrend"
    elif s <= -0.6:
        lab = "Downtrend"
    else:
        lab = "Range / transition"
    return {"label": lab, "score": round(s, 2), "sma50_slope_10": round(float(slope), 2),
            "above_sma200": bool(above200), "above_sma50": bool(above50), "sma50_above_sma200": bool(golden)}


def signals(ind: pd.DataFrame, levels: dict) -> list[dict]:
    r, p = ind.iloc[-1], ind.iloc[-2]
    out = []

    def add(name, state, bias, detail):
        out.append({"name": name, "state": state, "bias": bias, "detail": detail})

    if not pd.isna(r.sma200):
        add("Price vs 200-day average", "Above" if r.close > r.sma200 else "Below",
            1 if r.close > r.sma200 else -1, f"{(r.close / r.sma200 - 1) * 100:+.1f}% from {r.sma200:,.0f}")
    if not pd.isna(r.sma50) and not pd.isna(r.sma200):
        cross = ""
        recent = ind[["sma50", "sma200"]].dropna().tail(20)
        sgn = np.sign(recent.sma50 - recent.sma200)
        if len(sgn) > 1 and (sgn.diff().fillna(0) != 0).any():
            cross = " (crossed in the last 20 sessions)"
        add("50-day vs 200-day average", "Golden cross" if r.sma50 > r.sma200 else "Death cross",
            1 if r.sma50 > r.sma200 else -1, f"50d {r.sma50:,.0f} vs 200d {r.sma200:,.0f}{cross}")
    if not pd.isna(r.rsi):
        st = "Overbought" if r.rsi >= 70 else "Oversold" if r.rsi <= 30 else "Neutral"
        add("RSI (14)", st, 0 if st == "Neutral" else (-1 if st == "Overbought" else 1),
            f"{r.rsi:.0f}; overbought above 70, oversold below 30 (contrarian)")
    add("MACD vs signal line", "Above" if r.macd_hist > 0 else "Below", 1 if r.macd_hist > 0 else -1,
        f"histogram {r.macd_hist:+,.2f}" + (" (just crossed)" if np.sign(r.macd_hist) != np.sign(p.macd_hist) else ""))
    if not pd.isna(r.bb_up):
        st = "Above upper band" if r.close > r.bb_up else "Below lower band" if r.close < r.bb_lo else "Inside bands"
        add("Bollinger bands (20, 2)", st, 0, f"band {r.bb_lo:,.0f} to {r.bb_up:,.0f}")
    for s in levels.get("support", [])[:1]:
        add("Nearest support", f"{s['price']:,.0f}", 0, f"{(r.close / s['price'] - 1) * 100:+.1f}% above it")
    for s in levels.get("resistance", [])[:1]:
        add("Nearest resistance", f"{s['price']:,.0f}", 0, f"{(s['price'] / r.close - 1) * 100:.1f}% overhead")
    return out


def score(ind: pd.DataFrame, struct: dict) -> float:
    """Technical score -100..+100: trend 40%, structure 20%, momentum (MACD, RSI, 1-month return) 40%."""
    r = ind.iloc[-1]
    t = trend(ind)["score"]
    macd = float(np.clip(r.macd_hist / (ind.macd_hist.tail(250).std() or 1), -1, 1))
    rsi = float(np.clip((r.rsi - 50) / 25, -1, 1)) if not pd.isna(r.rsi) else 0
    m1 = ind.close.pct_change(21)
    mom = float(np.clip((m1.iloc[-1] - m1.tail(500).mean()) / (m1.tail(500).std() or 1), -2, 2) / 2)
    s = 0.4 * t + 0.2 * struct["score"] + 0.4 * (macd + rsi + mom) / 3
    return round(float(s) * 100, 0)


def analyse(df: pd.DataFrame, levels: dict) -> dict:
    out = {}
    for tf, frame in (("daily", df), ("weekly", weekly(df))):
        ind = indicators(frame) if tf == "daily" else indicators(frame, fast=10, slow=40)
        st = structure(frame, k=5 if tf == "daily" else 3)
        r = ind.iloc[-1]
        out[tf] = {
            "trend": trend(ind), "structure": st, "score": score(ind, st),
            "rsi": None if pd.isna(r.rsi) else round(float(r.rsi), 1),
            "macd_hist": round(float(r.macd_hist), 3),
            "atr": None if pd.isna(r.atr) else round(float(r.atr), 2),
            "vol30": None if pd.isna(r.vol30) else round(float(r.vol30), 1),
            "signals": signals(ind, levels) if tf == "daily" else [],
        }
        if tf == "daily":
            out["daily_series"] = {k: [None if pd.isna(v) else round(float(v), 4) for v in ind[k].tail(400)]
                                   for k in ("sma50", "sma200", "rsi", "macd", "macd_signal", "macd_hist", "vol30")
                                   if k in ind}
            out["daily_series"]["dates"] = [d.strftime("%Y-%m-%d") for d in ind.index[-400:]]
            if "vol_ratio" in ind:
                out["daily"]["vol_ratio"] = None if pd.isna(r.vol_ratio) else round(float(r.vol_ratio), 2)
    return out
