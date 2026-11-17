"""Explainable technical levels: swing points, 200-day average, 52-week range."""
from __future__ import annotations

import pandas as pd


def swing_points(df: pd.DataFrame, k: int = 5, lookback: int = 250) -> tuple[list, list]:
    """A swing high is a high that is the highest of the k bars either side; lows likewise."""
    d = df.tail(lookback)
    highs, lows = [], []
    for i in range(k, len(d) - k):
        win = d.iloc[i - k:i + k + 1]
        if d.high.iloc[i] == win.high.max():
            highs.append((d.index[i], float(d.high.iloc[i])))
        if d.low.iloc[i] == win.low.min():
            lows.append((d.index[i], float(d.low.iloc[i])))
    return highs, lows


def _cluster(points: list, tol: float) -> list:
    """Merge swing points within tol (fraction) of each other; keep the most recent date."""
    pts = sorted(points, key=lambda p: p[1])
    out = []
    for dt, px in pts:
        if out and abs(px / out[-1][1] - 1) <= tol:
            out[-1] = (max(dt, out[-1][0]), (px + out[-1][1]) / 2, out[-1][2] + 1)
        else:
            out.append((dt, px, 1))
    return out


def key_levels(df: pd.DataFrame, n: int = 2) -> dict:
    last = float(df.close.iloc[-1])
    vol = df.close.pct_change().tail(60).std() or 0.01
    highs, lows = swing_points(df)
    zones = _cluster(highs + lows, tol=max(vol, 0.004))
    sup = sorted([z for z in zones if z[1] < last], key=lambda z: -z[1])[:n]
    res = sorted([z for z in zones if z[1] > last], key=lambda z: z[1])[:n]
    sma200 = float(df.close.tail(200).mean()) if len(df) >= 180 else None
    yr = df.tail(365)

    def fmt(z, kind):
        return {"price": round(z[1], 2), "label": f"{kind}: swing level, {z[2]} touch(es), last {z[0]:%d %b %Y}"}

    return {
        "last": last,
        "support": [fmt(z, "Support") for z in sup],
        "resistance": [fmt(z, "Resistance") for z in res],
        "sma200": round(sma200, 2) if sma200 else None,
        "high_52w": round(float(yr.high.max()), 2),
        "low_52w": round(float(yr.low.min()), 2),
    }
