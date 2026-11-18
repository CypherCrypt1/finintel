"""Long-history series for the Overlay Lab page (site/data/overlay.json).

Markets: up to 10 years of daily closes (Yahoo Finance) for everything the global build already
collects, plus a short list of widely followed stocks and ETFs.
Macro: long monthly/weekly/daily US series from FRED (needs FRED_API_KEY).
Crypto is not stored here: the page loads any Binance pair live in the browser.

Every series keeps its own native frequency; nothing is interpolated or invented.
"""
from __future__ import annotations

import json
import os
import time

import pandas as pd

from . import global_config as G
from . import global_data as D

EXTRA_TICKERS = [  # (key, name, ticker, group)
    ("aapl", "Apple", "AAPL", "Stocks"), ("msft", "Microsoft", "MSFT", "Stocks"), ("nvda", "Nvidia", "NVDA", "Stocks"),
    ("amzn", "Amazon", "AMZN", "Stocks"), ("googl", "Alphabet", "GOOGL", "Stocks"), ("meta", "Meta Platforms", "META", "Stocks"),
    ("tsla", "Tesla", "TSLA", "Stocks"), ("coin", "Coinbase", "COIN", "Stocks"), ("mstr", "Strategy (MicroStrategy)", "MSTR", "Stocks"),
    ("spy", "SPDR S&P 500 ETF", "SPY", "ETFs"), ("qqq", "Invesco Nasdaq-100 ETF", "QQQ", "ETFs"), ("tlt", "iShares 20+ Year Treasury ETF", "TLT", "ETFs"),
    ("hyg", "iShares High Yield Corporate Bond ETF", "HYG", "ETFs"), ("gld", "SPDR Gold Shares", "GLD", "ETFs"), ("ibit", "iShares Bitcoin Trust", "IBIT", "ETFs"),
    ("vix", "CBOE Volatility Index (VIX)", "^VIX", "Volatility"), ("move", "ICE BofA MOVE Index (bond volatility)", "^MOVE", "Volatility"),
]

# (key, name, FRED id, unit, transform, group)   transform: level | yoy | diff
FRED_OVERLAY = [
    ("us_cpi_yoy", "US CPI inflation, y/y", "CPIAUCSL", "%", "yoy", "US inflation"),
    ("us_core_cpi_yoy", "US core CPI inflation, y/y", "CPILFESL", "%", "yoy", "US inflation"),
    ("us_core_pce_yoy", "US core PCE inflation, y/y", "PCEPILFE", "%", "yoy", "US inflation"),
    ("us_ppi_yoy", "US producer prices, y/y", "PPIACO", "%", "yoy", "US inflation"),
    ("us_be5", "US 5-year breakeven inflation", "T5YIE", "%", "level", "US inflation"),
    ("us_unrate", "US unemployment rate", "UNRATE", "%", "level", "US labour"),
    ("us_payrolls_chg", "US nonfarm payrolls, monthly change (thousands)", "PAYEMS", "k", "diff", "US labour"),
    ("us_claims", "US initial jobless claims", "ICSA", "claims", "level", "US labour"),
    ("us_fedfunds", "Fed funds rate (effective)", "FEDFUNDS", "%", "level", "US rates"),
    ("us_2y", "US 2-year Treasury yield", "DGS2", "%", "level", "US rates"),
    ("us_10y", "US 10-year Treasury yield", "DGS10", "%", "level", "US rates"),
    ("us_real10", "US 10-year real yield (TIPS)", "DFII10", "%", "level", "US rates"),
    ("us_curve", "US yield curve, 10y minus 2y", "T10Y2Y", "pp", "level", "US rates"),
    ("us_mortgage", "US 30-year mortgage rate", "MORTGAGE30US", "%", "level", "US rates"),
    ("us_hy_spread", "US high-yield credit spread", "BAMLH0A0HYM2", "pp", "level", "Credit"),
    ("us_ig_spread", "US investment-grade credit spread", "BAMLC0A0CM", "pp", "level", "Credit"),
    ("us_m2", "US M2 money supply ($bn)", "M2SL", "$bn", "level", "Liquidity"),
    ("us_m2_yoy", "US M2 money supply, y/y", "M2SL", "%", "yoy", "Liquidity"),
    ("us_fed_assets", "Fed balance sheet, total assets ($bn)", "WALCL", "$bn", "level", "Liquidity"),
    ("us_rrp", "Fed reverse repo facility ($bn)", "RRPONTSYD", "$bn", "level", "Liquidity"),
    ("us_dollar", "Broad US dollar index (Fed)", "DTWEXBGS", "index", "level", "Dollar"),
    ("us_gdp", "US real GDP growth (annualised q/q)", "A191RL1Q225SBEA", "%", "level", "US growth"),
    ("us_indpro_yoy", "US industrial production, y/y", "INDPRO", "%", "yoy", "US growth"),
    ("us_retail_yoy", "US retail sales, y/y", "RSAFS", "%", "yoy", "US growth"),
    ("us_sentiment", "University of Michigan consumer sentiment", "UMCSENT", "index", "level", "US growth"),
    ("us_debt_gdp", "US federal debt, % of GDP", "GFDEGDQ188S", "%", "level", "US fiscal"),
    ("oil_wti_fred", "WTI crude oil spot (FRED)", "DCOILWTICO", "$/bbl", "level", "Commodities"),
]


def _ser(s: pd.Series, nd=4) -> dict:
    s = s.dropna()
    return {"dates": [d.strftime("%Y-%m-%d") for d in s.index], "values": [round(float(v), nd) for v in s.values]}


def _freq(s: pd.Series) -> str:
    if len(s) < 3:
        return "?"
    gap = pd.Series(s.index).diff().dt.days.median()
    return "Daily" if gap <= 3 else "Weekly" if gap <= 8 else "Monthly" if gap <= 35 else "Quarterly"


def build_overlay(px: dict | None, prev_path: str | None = None, offline: bool = False) -> dict:
    out = {"generated_at": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "series": {}}
    prev = {}
    if prev_path and os.path.exists(prev_path):
        try:
            prev = json.load(open(prev_path)).get("series", {})
        except Exception:  # noqa: BLE001
            prev = {}
    px = dict(px or {})
    if not offline:
        for k, n, t, grp in EXTRA_TICKERS:
            if t not in px:
                try:
                    px[t] = D.yahoo(t, "10y")
                    time.sleep(0.2)
                except Exception as e:  # noqa: BLE001
                    print(f"[overlay] {t}: {e}", flush=True)
    meta = {}
    for i in G.INDICES:
        meta[i[2]] = (i[0], i[1], "Equity indices")
    meta[G.DXY] = ("dxy", "US dollar index (DXY)", "Currencies")
    for c in G.COMMODITIES:
        meta[c[2]] = (c[0], c[1], "Commodities")
    for k, n, t in G.SECTORS:
        meta[t] = (k, n, "US sectors")
    for k, n, t in G.PROXIES + G.US_YIELDS:
        meta[t] = (k, n, "Market proxies")
    for k, n, t, grp in EXTRA_TICKERS:
        meta[t] = (k, n, grp)
    for t, s in px.items():
        if s is None or len(s) < 30 or t not in meta:
            continue
        k, n, grp = meta[t]
        out["series"][f"mkt:{k}"] = {"name": n, "group": grp, "unit": "price", "freq": "Daily", "source": f"Yahoo Finance ({t})", **_ser(s, 4)}
    # currencies: value of one unit in USD terms (higher = currency stronger)
    for fx in G.FX:
        code, t = fx[0], fx[1]
        s = px.get(t)
        if s is None or len(s) < 30:
            continue
        inv = len(fx) > 2 and fx[2]
        v = (1 / s) if inv else s
        out["series"][f"fx:{code}"] = {"name": f"{code} vs US dollar (USD per {code})", "group": "Currencies", "unit": "USD", "freq": "Daily",
                                       "source": f"Yahoo Finance ({t})", **_ser(v, 6)}
    if os.environ.get("FRED_API_KEY") and not offline:
        from .connectors import fred
        for k, n, sid, unit, tr, grp in FRED_OVERLAY:
            try:
                s = fred(sid).dropna()
                s = s[s.index >= "1990-01-01"]
                if tr == "yoy":
                    per = {"Monthly": 12, "Quarterly": 4, "Weekly": 52}.get(_freq(s), 12)
                    s = (s / s.shift(per) - 1) * 100
                elif tr == "diff":
                    s = s.diff()
                out["series"][f"fred:{k}"] = {"name": n, "group": grp, "unit": unit, "freq": _freq(s), "source": f"FRED ({sid})", **_ser(s.dropna(), 3)}
            except Exception as e:  # noqa: BLE001
                print(f"[overlay] FRED {sid}: {e}", flush=True)
    # carry forward anything that failed today
    for k, v in prev.items():
        if k not in out["series"]:
            out["series"][k] = {**v, "carried": True}
    print(f"[overlay] {len(out['series'])} series", flush=True)
    return out
