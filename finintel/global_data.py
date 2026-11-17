"""Global connectors: Yahoo Finance charts, World Bank WDI, IMF WEO, BIS, UN Comtrade, SEC EDGAR, CFTC.

Every dataset is returned with metadata (provider, source URL, observation date, publication date,
reporting period, frequency, status, actual/estimated) so pages can show where each number came from.
A failed source is recorded in `errors` and its panels show as pending; nothing is filled in.
"""
from __future__ import annotations

import io
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

from . import global_config as G
from .connectors import ConnectorError, _cftc, _col, fred, CFTC_TFF

BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept": "application/json,text/plain,*/*"}
SEC_UA = {"User-Agent": "SOVEREIGN research cyphercrypt1@users.noreply.github.com"}
TODAY = pd.Timestamp(datetime.now(timezone.utc).date())


def get(url, params=None, headers=None, timeout=25, retries=1, pause=1.5):
    last = None
    for i in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=headers or BROWSER, timeout=timeout)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
            if r.status_code in (400, 401, 403, 404):
                break
        except requests.RequestException as e:
            last = type(e).__name__
        time.sleep(pause * (i + 1))
    raise ConnectorError(f"{url.split('?')[0]} -> {last}")


def meta(provider, source, url, obs=None, published=None, period=None, freq=None, status="ok", kind="Actual", confidence=None, note=""):
    return {"provider": provider, "source": source, "url": url, "observation": obs, "published": published,
            "period": period, "frequency": freq, "status": status, "kind": kind, "confidence": confidence, "note": note}


# ------------------------------------------------------------------ Yahoo
def yahoo(symbol: str, rng: str = "2y") -> pd.Series:
    last = None
    for host in ("query1", "query2"):
        try:
            j = get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(symbol)}",
                    {"range": rng, "interval": "1d", "includePrePost": "false"}).json()
            res = j["chart"]["result"][0]
            ts, close = res.get("timestamp"), res["indicators"]["quote"][0]["close"]
            if not ts:
                raise ConnectorError("no rows")
            s = pd.Series(close, index=pd.to_datetime(ts, unit="s").normalize(), dtype=float).dropna()
            return s[~s.index.duplicated(keep="last")]
        except Exception as e:
            last = e
    raise ConnectorError(f"Yahoo {symbol}: {last}")


def perf(s: pd.Series) -> dict:
    s = s.dropna()
    last, t = float(s.iloc[-1]), s.index[-1]

    def r(days):
        p = s[s.index <= t - pd.Timedelta(days=days)]
        return None if p.empty else round((last / float(p.iloc[-1]) - 1) * 100, 2)

    yb = s[s.index < pd.Timestamp(year=t.year, month=1, day=1)]
    rets = s.pct_change().dropna()
    return {"last": round(last, 4), "date": t.strftime("%Y-%m-%d"), "d1": r(1) if len(s) > 1 else None,
            "w1": r(7), "m1": r(30), "m3": r(91), "y1": r(365),
            "ytd": None if yb.empty else round((last / float(yb.iloc[-1]) - 1) * 100, 2),
            "vol30": round(float(rets.tail(30).std() * np.sqrt(252) * 100), 1) if len(rets) > 20 else None,
            "dd1y": round(float((s.tail(260) / s.tail(260).cummax() - 1).min() * 100), 1),
            "hi52": round(float(s.tail(260).max()), 4), "lo52": round(float(s.tail(260).min()), 4)}


def ser(s: pd.Series, n: int = 520, nd: int = 4) -> dict:
    s = s.dropna().tail(n)
    return {"dates": [d.strftime("%Y-%m-%d") for d in s.index], "values": [round(float(v), nd) for v in s]}


# --------------------------------------------------------------- World Bank
def worldbank(code: str, iso3: list[str]) -> tuple[pd.DataFrame, dict]:
    url = f"https://api.worldbank.org/v2/country/{';'.join(iso3)}/indicator/{code}"
    j = get(url, {"format": "json", "per_page": 2000, "date": "2000:2026"}, timeout=40, retries=1).json()
    if not isinstance(j, list) or len(j) < 2 or not j[1]:
        raise ConnectorError(f"World Bank {code}: empty")
    rows = [(x["countryiso3code"] or x["country"]["id"], int(x["date"]), x["value"]) for x in j[1] if x["value"] is not None]
    df = pd.DataFrame(rows, columns=["iso3", "year", "value"])
    return df, {"published": j[0].get("lastupdated")}


# --------------------------------------------------------------------- IMF
def imf(code: str, iso3: list[str]) -> pd.DataFrame:
    j = get(f"https://www.imf.org/external/datamapper/api/v1/{code}/{'/'.join(iso3)}", timeout=40, retries=1).json()
    vals = j.get("values", {}).get(code, {})
    rows = [(c, int(y), v) for c, ys in vals.items() for y, v in ys.items() if v is not None]
    if not rows:
        raise ConnectorError(f"IMF {code}: empty")
    return pd.DataFrame(rows, columns=["iso3", "year", "value"])


# --------------------------------------------------------------------- BIS
def bis(flow: str, key: str, start: str) -> pd.DataFrame:
    urls = [(f"https://stats.bis.org/api/v1/data/{flow}/{key}/all", {"startPeriod": start, "format": "csv", "detail": "dataonly"}),
            (f"https://stats.bis.org/api/v2/data/dataflow/BIS/{flow}/1.0/{key}", {"startPeriod": start, "format": "csv"})]
    last = None
    for u, p in urls:
        try:
            r = get(u, p, headers={"User-Agent": BROWSER["User-Agent"], "Accept": "text/csv"}, timeout=40)
            df = pd.read_csv(io.StringIO(r.text))
            cols = {c.upper(): c for c in df.columns}
            need = ["REF_AREA", "TIME_PERIOD", "OBS_VALUE"]
            if not all(n in cols for n in need):
                raise ConnectorError(f"columns {list(df.columns)[:8]}")
            out = df.rename(columns={cols[n]: n for n in need} | ({cols["EER_TYPE"]: "EER_TYPE"} if "EER_TYPE" in cols else {}))
            out["OBS_VALUE"] = pd.to_numeric(out["OBS_VALUE"], errors="coerce")
            return out.dropna(subset=["OBS_VALUE"])
        except Exception as e:
            last = e
    raise ConnectorError(f"BIS {flow}: {last}")


# ----------------------------------------------------------------- Comtrade
def comtrade_partner_names() -> dict:
    j = get("https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json", timeout=40).json()
    return {int(x["id"]): x["text"] for x in j.get("results", []) if str(x.get("id", "")).lstrip("-").isdigit()}


def comtrade(reporter: int, flow: str, cmd: str, partner: str | None, years=(2025, 2024, 2023, 2022, 2021)) -> tuple[pd.DataFrame, int]:
    for y in years:
        p = {"reporterCode": reporter, "period": y, "flowCode": flow, "cmdCode": cmd, "includeDesc": "true"}
        if partner is not None:
            p["partnerCode"] = partner
        try:
            j = get("https://comtradeapi.un.org/public/v1/preview/C/A/HS", p, timeout=40, retries=1, pause=3).json()
        except ConnectorError:
            time.sleep(2)
            continue
        data = j.get("data") or []
        time.sleep(1.2)
        if data:
            return pd.DataFrame(data), y
    raise ConnectorError(f"Comtrade reporter {reporter} {flow} {cmd}: no data 2021-2025")


# --------------------------------------------------------------------- SEC
SEC_TAGS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    "ebit": ["OperatingIncomeLoss"], "net_income": ["NetIncomeLoss"], "da": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization"],
    "assets": ["Assets"], "liabilities": ["Liabilities"], "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "debt": ["LongTermDebt", "LongTermDebtNoncurrent"], "ocf": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"], "acquisitions": ["PaymentsToAcquireBusinessesNetOfCashAcquired"],
    "investments": ["PaymentsToAcquireInvestments", "PaymentsToAcquireAvailableForSaleSecuritiesDebt"],
    "divestments": ["ProceedsFromDivestitureOfBusinesses", "ProceedsFromSaleOfBusinesses"],
}
INSTANT = {"assets", "liabilities", "equity", "cash", "debt"}


def sec_company(cik: int) -> dict:
    j = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json", headers=SEC_UA, timeout=40).json()
    facts = j.get("facts", {}).get("us-gaap", {})
    out = {"cik": cik, "name": j.get("entityName"), "fields": {}}
    for field, tags in SEC_TAGS.items():
        best = None
        for tag in tags:
            units = facts.get(tag, {}).get("units", {}).get("USD", [])
            rows = []
            for u in units:
                if u.get("form") not in ("10-K", "10-K/A", "20-F", "40-F") or u.get("fp") != "FY":
                    continue
                if field not in INSTANT:
                    if not u.get("start"):
                        continue
                    if (pd.Timestamp(u["end"]) - pd.Timestamp(u["start"])).days < 330:
                        continue
                rows.append(u)
            if rows:
                rows.sort(key=lambda u: (u["end"], u.get("filed", "")))
                by_end = {}
                for u in rows:
                    by_end[u["end"]] = u
                ends = sorted(by_end)
                cur = by_end[ends[-1]]
                prev = by_end[ends[-2]] if len(ends) > 1 else None
                cand = {"value": cur["val"], "period_end": cur["end"], "filed": cur.get("filed"), "form": cur.get("form"),
                        "accn": cur.get("accn"), "tag": tag, "prev": prev["val"] if prev else None,
                        "prev_end": prev["end"] if prev else None}
                if best is None or cand["period_end"] > best["period_end"]:
                    best = cand
        if best:
            out["fields"][field] = best
    f = out["fields"]
    if "ebit" in f and "da" in f and f["ebit"]["period_end"] == f["da"]["period_end"]:
        f["ebitda"] = {"value": f["ebit"]["value"] + f["da"]["value"], "period_end": f["ebit"]["period_end"], "derived": "EBIT + D&A",
                       "filed": f["ebit"]["filed"], "form": f["ebit"]["form"], "accn": f["ebit"]["accn"]}
    if "ocf" in f and "capex" in f and f["ocf"]["period_end"] == f["capex"]["period_end"]:
        f["fcf"] = {"value": f["ocf"]["value"] - f["capex"]["value"], "period_end": f["ocf"]["period_end"], "derived": "OCF − capex",
                    "filed": f["ocf"]["filed"], "form": f["ocf"]["form"], "accn": f["ocf"]["accn"]}
    if "liabilities" not in f and "assets" in f and "equity" in f and f["assets"]["period_end"] == f["equity"]["period_end"]:
        f["liabilities"] = {"value": f["assets"]["value"] - f["equity"]["value"], "period_end": f["assets"]["period_end"],
                            "derived": "assets − equity", "filed": f["assets"]["filed"], "form": f["assets"]["form"], "accn": f["assets"]["accn"]}
    pf = j.get("facts", {}).get("dei", {}).get("EntityPublicFloat", {}).get("units", {}).get("USD", [])
    if pf:
        p = sorted(pf, key=lambda u: u["end"])[-1]
        f["public_float"] = {"value": p["val"], "period_end": p["end"], "filed": p.get("filed"), "form": p.get("form"), "accn": p.get("accn")}
    return out


def cftc_fx(code: str) -> pd.Series:
    df = _cftc(CFTC_TFF, code)
    lev = _col(df, "lev_money_positions_long") - _col(df, "lev_money_positions_short")
    am = _col(df, "asset_mgr_positions_long") - _col(df, "asset_mgr_positions_short")
    return pd.DataFrame({"lev": lev, "am": am}).dropna()
