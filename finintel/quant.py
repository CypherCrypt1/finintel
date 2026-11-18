"""Quantitative research: performance, correlations, volatility, regimes, benchmark backtests.

Everything here is computed from stored history. Results are historical observations or
statistical relationships, never forecasts.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def daily(s: pd.Series) -> pd.Series:
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D")).ffill()


def performance(close: pd.Series) -> dict:
    c = close.dropna()
    last, t = float(c.iloc[-1]), c.index[-1]

    def ret(days):
        prev = c[c.index <= t - pd.Timedelta(days=days)]
        return None if prev.empty else round((last / float(prev.iloc[-1]) - 1) * 100, 2)

    ytd_base = c[c.index < pd.Timestamp(year=t.year, month=1, day=1)]
    return {"last": last, "date": t.strftime("%Y-%m-%d"), "d1": ret(1), "w1": ret(7), "m1": ret(30), "m3": ret(91),
            "y1": ret(365), "ytd": None if ytd_base.empty else round((last / float(ytd_base.iloc[-1]) - 1) * 100, 2)}


def monthly_returns(close: pd.Series) -> list[dict]:
    m = close.resample("ME").last().pct_change().dropna() * 100
    return [{"month": d.strftime("%Y-%m"), "ret": round(float(v), 2)} for d, v in m.items()]


def changes_frame(series: dict[str, pd.Series], kind: dict[str, str]) -> pd.DataFrame:
    """Daily changes: % returns for prices, point changes for yields/rates."""
    cols = {}
    for k, s in series.items():
        if s is None or s.dropna().empty:
            continue
        d = daily(s.dropna())
        bd = d[d.index.dayofweek < 5]        # weekdays only, so crypto weekends don't dilute
        cols[k] = bd.pct_change() * 100 if kind.get(k) == "price" else bd.diff()
    return pd.DataFrame(cols)


def correlations(chg: pd.DataFrame, window: int) -> dict:
    sub = chg.tail(window).dropna(how="all")
    c = sub.corr(min_periods=int(window * 0.6))
    keys = list(c.columns)
    return {"keys": keys, "window": window,
            "matrix": [[None if pd.isna(c.loc[a, b]) else round(float(c.loc[a, b]), 2) for b in keys] for a in keys]}


def rolling_corr(chg: pd.DataFrame, a: str, b: str, window: int = 90) -> dict:
    if a not in chg or b not in chg:
        return {"dates": [], "values": []}
    r = chg[a].rolling(window, min_periods=int(window * 0.7)).corr(chg[b]).dropna().tail(500)
    return {"dates": [d.strftime("%Y-%m-%d") for d in r.index], "values": [round(float(v), 3) for v in r]}


def volatility(close: pd.Series, ann: int) -> dict:
    r = close.pct_change()
    v30 = (r.rolling(30).std() * np.sqrt(ann) * 100).dropna()
    v90 = (r.rolling(90).std() * np.sqrt(ann) * 100).dropna()
    hist = v30.tail(750)
    return {"vol30": round(float(v30.iloc[-1]), 1), "vol90": round(float(v90.iloc[-1]), 1),
            "vol30_pct_rank": round(float((hist <= v30.iloc[-1]).mean() * 100), 0),
            "dates": [d.strftime("%Y-%m-%d") for d in v30.index[-500:]],
            "values": [round(float(x), 2) for x in v30.tail(500)],
            "max_drawdown_1y": (lambda y: round(float((y / y.cummax() - 1).min() * 100), 1))(close[close.index > close.index[-1] - pd.Timedelta(days=365)])}


def regimes(close: pd.Series) -> dict:
    """Four regimes from trend (vs 200-day average) and volatility (vs its 1-year median).
    For each, the historical forward 20-session return in this sample (an observation, not a forecast)."""
    c = close.dropna()
    sma = c.rolling(200, min_periods=180).mean()
    vol = c.pct_change().rolling(30).std()
    ppy_ = 365 if (vol.index.dayofweek >= 5).any() else 252
    vmed = vol.rolling(ppy_, min_periods=int(ppy_ * 0.55)).median()
    df = pd.DataFrame({"c": c, "up": c > sma, "hv": vol > vmed}).dropna()
    df = df[sma.reindex(df.index).notna() & vmed.reindex(df.index).notna()]
    if df.empty:
        return {"current": "Undetermined", "table": []}
    name = lambda up, hv: ("Uptrend" if up else "Downtrend") + (", high volatility" if hv else ", low volatility")
    df["regime"] = [name(u, h) for u, h in zip(df.up, df.hv)]
    fwd = c.shift(-20) / c - 1
    df["fwd20"] = fwd.reindex(df.index) * 100
    table = []
    for reg, g in df.groupby("regime"):
        f = g.fwd20.dropna()
        table.append({"regime": reg, "days": int(len(g)), "share": round(len(g) / len(df) * 100, 1),
                      "fwd20_median": None if f.empty else round(float(f.median()), 2),
                      "fwd20_hit": None if f.empty else round(float((f > 0).mean() * 100), 0)})
    seq = df.regime
    run = int((seq[::-1] == seq.iloc[-1]).cumprod().sum())
    return {"current": seq.iloc[-1], "days_in_regime": run, "sample_start": df.index[0].strftime("%Y-%m-%d"),
            "table": sorted(table, key=lambda x: x["regime"]),
            "history": [{"date": d.strftime("%Y-%m-%d"), "regime": r} for d, r in seq.tail(500).items()]}


def backtest_trend(close: pd.Series, cost_bp: float = 10) -> dict:
    """Benchmark from spec section 7: 200-day moving average rule vs buy-and-hold."""
    c = close.dropna()
    sma = c.rolling(200, min_periods=200).mean()
    pos = (c > sma).astype(float).shift(1)
    r = c.pct_change()
    valid = sma.notna() & pos.notna()
    r, pos = r[valid], pos[valid]
    if len(r) < 60:
        return {"note": "not enough history"}
    trades = pos.diff().abs().fillna(0)
    strat = pos * r - trades * cost_bp / 1e4
    days = len(r)
    ppy = 365 if (c.index.dayofweek >= 5).any() else 252

    def stats(x):
        eq = (1 + x).cumprod()
        yrs = days / ppy
        return {"total": round(float(eq.iloc[-1] - 1) * 100, 1),
                "cagr": round(float(eq.iloc[-1] ** (1 / yrs) - 1) * 100, 1) if yrs > 0 else None,
                "max_dd": round(float((eq / eq.cummax() - 1).min()) * 100, 1),
                "sharpe": round(float(x.mean() / x.std() * np.sqrt(ppy)), 2) if x.std() else None}

    eq_s, eq_b = (1 + strat).cumprod(), (1 + r).cumprod()
    step = max(1, len(eq_s) // 300)
    return {"start": r.index[0].strftime("%Y-%m-%d"), "end": r.index[-1].strftime("%Y-%m-%d"), "days": days,
            "trades": int(trades.sum()), "cost_bp": cost_bp, "time_in_market": round(float(pos.mean()) * 100, 0),
            "strategy": stats(strat), "buy_hold": stats(r),
            "curve": {"dates": [d.strftime("%Y-%m-%d") for d in eq_s.index[::step]],
                      "strategy": [round(float(v), 4) for v in eq_s[::step]],
                      "buy_hold": [round(float(v), 4) for v in eq_b[::step]]}}
