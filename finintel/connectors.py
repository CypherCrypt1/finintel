"""Connectors to free public data sources.

Every loader returns a pandas Series indexed by date (UTC, daily or lower
frequency) or raises ConnectorError. Nothing here needs an API key.

Sources that have no free API (ETF flows, central bank purchases, exchange
reserves...) are read from CSV files you keep in the `manual_inputs/` folder:
two columns, `date,value`. A missing file simply leaves that driver out of the
scorecard and lists it under "Not collected".
"""
from __future__ import annotations

import io
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

UA = {"User-Agent": "finintel-research/0.1 (personal research tool)"}
TIMEOUT = 30


class ConnectorError(RuntimeError):
    pass


def _get(url: str, params: dict | None = None, retries: int = 2, timeout: int = TIMEOUT) -> requests.Response:
    last = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=timeout)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}: {r.text[:200]}"
        except requests.RequestException as e:  # network error
            last = str(e)
        time.sleep(1.5 * (attempt + 1))
    raise ConnectorError(f"{url} -> {last}")


# --------------------------------------------------------------------- FRED
FRED_START = (pd.Timestamp.today() - pd.Timedelta(days=6 * 365)).strftime("%Y-%m-%d")


def fred(series_id: str) -> pd.Series:
    """FRED series. Uses the official API if FRED_API_KEY is set (free key, most reliable),
    otherwise the public CSV endpoint. Treasury yields fall back to treasury.gov."""
    errors = []
    key = os.environ.get("FRED_API_KEY", "").strip()
    if key:
        try:
            j = _get("https://api.stlouisfed.org/fred/series/observations",
                     {"series_id": series_id, "api_key": key, "file_type": "json",
                      "observation_start": FRED_START}, retries=1, timeout=60).json()
            obs = j["observations"]
            s = pd.Series(pd.to_numeric([o["value"] for o in obs], errors="coerce"),
                          index=pd.to_datetime([o["date"] for o in obs]))
            return s.dropna().rename(series_id)
        except Exception as e:
            errors.append(f"API: {e}")
    try:
        r = _get("https://fred.stlouisfed.org/graph/fredgraph.csv", {"id": series_id, "cosd": FRED_START},
                 retries=1, timeout=60)
        df = pd.read_csv(io.StringIO(r.text))
        date_col = "observation_date" if "observation_date" in df.columns else df.columns[0]
        s = pd.to_numeric(df[series_id], errors="coerce")
        s.index = pd.to_datetime(df[date_col])
        return s.dropna().rename(series_id)
    except Exception as e:
        errors.append(f"CSV: {e}")
    if series_id in TREASURY_FALLBACK:
        try:
            return treasury_yield(*TREASURY_FALLBACK[series_id]).rename(series_id)
        except Exception as e:
            errors.append(f"Treasury: {e}")
    raise ConnectorError(f"FRED {series_id} unavailable ({'; '.join(errors)[:300]})")


# FRED series that US Treasury also publishes: (curve type, column)
TREASURY_FALLBACK = {"DFII10": ("daily_treasury_real_yield_curve", "10 yr"),
                     "DGS2": ("daily_treasury_yield_curve", "2 yr"),
                     "DGS10": ("daily_treasury_yield_curve", "10 yr")}


def treasury_yield(curve: str, column: str, years: int = 4) -> pd.Series:
    """Daily Treasury par / real yield curve from home.treasury.gov, one CSV per year."""
    parts = []
    this_year = pd.Timestamp.today().year
    for y in range(this_year - years + 1, this_year + 1):
        url = (f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
               f"daily-treasury-rates.csv/{y}/all")
        r = _get(url, {"type": curve, "field_tdr_date_value": y, "page": "", "_format": "csv"}, retries=1, timeout=60)
        df = pd.read_csv(io.StringIO(r.text))
        cols = {c.lower().strip(): c for c in df.columns}
        if column not in cols:
            raise ConnectorError(f"Treasury {curve} {y}: no column '{column}' in {list(df.columns)}")
        parts.append(pd.Series(pd.to_numeric(df[cols[column]], errors="coerce").values,
                               index=pd.to_datetime(df[cols["date"]])))
    return pd.concat(parts).dropna().sort_index()


def fred_net_liquidity() -> pd.Series:
    """Fed total assets - reverse repo - Treasury General Account, in $bn."""
    walcl = fred("WALCL") / 1000.0          # millions -> billions (weekly)
    rrp = fred("RRPONTSYD")                 # billions (daily)
    tga = fred("WTREGEN") / 1000.0          # millions -> billions (weekly)
    idx = pd.date_range(min(walcl.index.min(), rrp.index.min()), max(walcl.index.max(), rrp.index.max()), freq="D")
    df = pd.DataFrame({"w": walcl.reindex(idx).ffill(), "r": rrp.reindex(idx).ffill(), "t": tga.reindex(idx).ffill()})
    return (df.w - df.r - df.t).dropna().rename("NETLIQ")


# ------------------------------------------------------------------ Binance
BINANCE_HOSTS = ["https://api.binance.com", "https://data-api.binance.vision"]


def binance_daily(symbol: str, days: int = 1000) -> pd.DataFrame:
    """Daily OHLCV. PAXGUSDT is used as a gold proxy (1 PAXG = 1 troy oz, LBMA gold)."""
    last_err = None
    for host in BINANCE_HOSTS:
        try:
            r = _get(f"{host}/api/v3/klines", {"symbol": symbol, "interval": "1d", "limit": min(days, 1000)})
            rows = r.json()
            df = pd.DataFrame(rows).iloc[:, :6]
            df.columns = ["t", "open", "high", "low", "close", "volume"]
            df.index = pd.to_datetime(df.t, unit="ms").dt.normalize()
            return df[["open", "high", "low", "close", "volume"]].astype(float)
        except (ConnectorError, ValueError) as e:
            last_err = e
    raise ConnectorError(f"Binance klines {symbol}: {last_err}")


def binance_funding(symbol: str = "BTCUSDT") -> pd.Series:
    """Perpetual funding rate (3 prints a day), returned as a 7-day average in %.

    Binance futures blocks US servers (including GitHub's), so OKX is tried as a fallback.
    """
    try:
        r = _get("https://fapi.binance.com/fapi/v1/fundingRate", {"symbol": symbol, "limit": 1000}, retries=0)
        df = pd.DataFrame(r.json())
        s = pd.Series(df.fundingRate.astype(float).values * 100, index=pd.to_datetime(df.fundingTime, unit="ms"))
    except ConnectorError:
        rows, after = [], None
        for _ in range(3):  # OKX pages 100 prints at a time; 300 prints = 100 days
            params = {"instId": "BTC-USDT-SWAP", "limit": 100}
            if after:
                params["after"] = after
            page = _get("https://www.okx.com/api/v5/public/funding-rate-history", params).json().get("data", [])
            if not page:
                break
            rows += page
            after = page[-1]["fundingTime"]
        if not rows:
            raise ConnectorError("no funding data from Binance or OKX")
        s = pd.Series([float(x["realizedRate"] or x["fundingRate"]) * 100 for x in rows],
                      index=pd.to_datetime([int(x["fundingTime"]) for x in rows], unit="ms")).sort_index()
    return s.resample("D").mean().rolling(7, min_periods=3).mean().dropna().rename("funding")


# --------------------------------------------------------------------- CFTC
# Socrata datasets on publicreporting.cftc.gov
CFTC_DISAGG = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"   # disaggregated, futures only
CFTC_TFF = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"      # traders in financial futures
GOLD_CODE = "088691"   # Gold, COMEX
BTC_CODE = "133741"    # Bitcoin, CME


def _cftc(url: str, code: str) -> pd.DataFrame:
    r = _get(url, {"cftc_contract_market_code": code, "$order": "report_date_as_yyyy_mm_dd DESC", "$limit": 600})
    df = pd.DataFrame(r.json())
    if df.empty:
        raise ConnectorError(f"CFTC returned no rows for {code}")
    df.index = pd.to_datetime(df["report_date_as_yyyy_mm_dd"])
    return df.sort_index()


def _col(df: pd.DataFrame, *needles: str) -> pd.Series:
    for c in df.columns:
        if all(n in c for n in needles):
            return pd.to_numeric(df[c], errors="coerce")
    raise ConnectorError(f"CFTC column with {needles} not found; columns: {list(df.columns)[:15]}...")


def cftc_gold_mm_pct_oi() -> pd.Series:
    df = _cftc(CFTC_DISAGG, GOLD_CODE)
    net = _col(df, "m_money_positions_long") - _col(df, "m_money_positions_short")
    oi = _col(df, "open_interest_all")
    return (100 * net / oi).dropna().rename("gold_mm_pct_oi")


def cftc_btc_lev_net() -> pd.Series:
    df = _cftc(CFTC_TFF, BTC_CODE)
    net = _col(df, "lev_money_positions_long") - _col(df, "lev_money_positions_short")
    return net.dropna().rename("btc_lev_net")


# -------------------------------------------------------------- Coin Metrics
def coinmetrics(metric: str, asset: str = "btc") -> pd.Series:
    url = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    params = {"assets": asset, "metrics": metric, "frequency": "1d", "page_size": 10000,
              "start_time": (pd.Timestamp.utcnow() - pd.Timedelta(days=4 * 365)).strftime("%Y-%m-%d")}
    data = _get(url, params).json().get("data", [])
    if not data:
        raise ConnectorError(f"Coin Metrics returned no data for {metric}")
    s = pd.Series([float(d[metric]) for d in data],
                  index=pd.to_datetime([d["time"] for d in data]).tz_localize(None).normalize())
    return s.rename(metric)


# ------------------------------------------------------------------ mempool
def mempool_hashrate() -> pd.Series:
    """Daily average network hashrate in EH/s."""
    j = _get("https://mempool.space/api/v1/mining/hashrate/3y").json()
    s = pd.Series([h["avgHashrate"] / 1e18 for h in j["hashrates"]],
                  index=pd.to_datetime([h["timestamp"] for h in j["hashrates"]], unit="s").normalize())
    return s.rename("hashrate")


def block_subsidy(ts: pd.Timestamp) -> float:
    # halvings: 2024-04-20 -> 3.125; next expected around April 2028 -> 1.5625
    return 3.125 if ts < pd.Timestamp("2028-04-15") else 1.5625


def hashprice_proxy(btc_close: pd.Series, hashrate_eh: pd.Series) -> pd.Series:
    """USD subsidy revenue per EH/s per day (fees excluded): price * subsidy * 144 / hashrate."""
    df = pd.DataFrame({"p": btc_close, "h": hashrate_eh}).dropna()
    sub = np.array([block_subsidy(t) for t in df.index])
    return (df.p * sub * 144 / df.h).rename("hashprice")


# ------------------------------------------------------------- manual files
def manual(name: str, folder: Path) -> pd.Series:
    path = folder / f"{name}.csv"
    if not path.exists():
        raise ConnectorError(f"no manual file {path.name}")
    df = pd.read_csv(path, comment="#")
    if df.empty:
        raise ConnectorError(f"manual file {path.name} is empty")
    s = pd.Series(pd.to_numeric(df["value"], errors="coerce").values, index=pd.to_datetime(df["date"]))
    return s.dropna().sort_index().rename(name)


# ---------------------------------------------------------------- dispatcher
class SeriesLoader:
    """Loads and caches every series a driver may need, and records failures."""

    def __init__(self, manual_folder: Path):
        self.manual_folder = manual_folder
        self.cache: dict[str, pd.Series] = {}
        self.errors: dict[str, str] = {}
        self.prices: dict[str, pd.DataFrame] = {}

    def price(self, asset: str) -> pd.DataFrame:
        if asset not in self.prices:
            self.prices[asset] = binance_daily({"XAU": "PAXGUSDT", "BTC": "BTCUSDT"}[asset])
        return self.prices[asset]

    def load(self, sid: str) -> pd.Series | None:
        if sid in self.cache:
            return self.cache[sid]
        if sid in self.errors:
            return None
        kind, _, name = sid.partition(":")
        try:
            if kind == "fred":
                s = fred_net_liquidity() if name == "NETLIQ" else fred(name)
            elif kind == "price":
                s = self.price(name)["close"]
            elif kind == "cftc":
                s = {"gold_mm_pct_oi": cftc_gold_mm_pct_oi, "btc_lev_net": cftc_btc_lev_net}[name]()
            elif kind == "cm":
                s = coinmetrics(name)
            elif kind == "binance" and name == "funding":
                s = binance_funding()
            elif kind == "mempool" and name == "hashrate":
                s = mempool_hashrate()
            elif kind == "calc" and name == "hashprice":
                s = hashprice_proxy(self.price("BTC")["close"], self.load("mempool:hashrate"))
            elif kind == "manual":
                s = manual(name, self.manual_folder)
            else:
                raise ConnectorError(f"unknown series id {sid}")
        except Exception as e:  # keep going: one failed feed must not stop the run
            self.errors[sid] = f"{type(e).__name__}: {e}"
            return None
        self.cache[sid] = s
        return s
