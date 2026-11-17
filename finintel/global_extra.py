"""Additional free official sources for the global platform.

banking   BIS Locational Banking Statistics (cross-border bank claims/liabilities), quarterly
iip       IMF Balance of Payments: International Investment Position (via DBnomics), quarterly
cb_gold   IMF International Financial Statistics: official gold reserves (via DBnomics), monthly
tic       US Treasury TIC: major foreign holders of US Treasury securities, monthly
oecd      OECD composite leading indicators + key short-term indicators, monthly
calendar  FRED release calendar (US data releases) + mempool.space difficulty adjustment estimate
valuation multpl.com (Shiller CAPE, S&P 500 P/E, dividend yield) + Damodaran country risk premiums

Every collector returns plain JSON-able dicts and raises on failure so the caller can carry forward
the previous good copy. Nothing here invents a value: a missing number stays missing.
"""
from __future__ import annotations

import html as _html
import io
import os
import re
from datetime import datetime, timedelta, timezone

import pandas as pd

from . import global_data as D

ISO2 = {"us": "US", "cn": "CN", "jp": "JP", "de": "DE", "fr": "FR", "in": "IN", "gb": "GB", "ca": "CA", "ch": "CH", "ru": "RU"}
ISO3 = {"us": "USA", "cn": "CHN", "jp": "JPN", "de": "DEU", "fr": "FRA", "in": "IND", "gb": "GBR", "ca": "CAN", "ch": "CHE", "ru": "RUS"}
NOW = datetime.now(timezone.utc)


def _series(dates, values, n=None, nd=2):
    d = list(dates)[-n:] if n else list(dates)
    v = list(values)[-n:] if n else list(values)
    return {"dates": [str(x) for x in d], "values": [None if pd.isna(x) else round(float(x), nd) for x in v]}


# ------------------------------------------------------------------ BIS LBS
def _bis_csv(key: str, start: str) -> pd.DataFrame:
    last = None
    for u, p in [(f"https://stats.bis.org/api/v1/data/WS_LBS_D_PUB/{key}", {"startPeriod": start, "format": "csv"}),
                 (f"https://stats.bis.org/api/v2/data/dataflow/BIS/WS_LBS_D_PUB/1.0/{key}", {"startPeriod": start, "format": "csv"})]:
        try:
            r = D.get(u, p, headers={"User-Agent": D.BROWSER["User-Agent"], "Accept": "text/csv"}, timeout=60)
            df = pd.read_csv(io.StringIO(r.text), dtype=str)
            df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
            return df.dropna(subset=["OBS_VALUE"])
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"BIS LBS: {last}")


def collect_banking(c) -> dict:
    ks = list(ISO2)
    cps = "+".join(ISO2.values())
    out = {"countries": {}, "matrix": {}, "unit": "US$ (converted from US$ millions)"}
    # 1) cross-border claims/liabilities of ALL reporting banks vis-a-vis each country
    df = c.try_("banking:on", lambda: _bis_csv(f"Q.S.C+L.A.TO1.A.5J.A.5A.A.{cps}.N", "2010-Q1"))
    # 2) cross-border claims/liabilities of banks LOCATED in each country vis-a-vis the world
    df2 = c.try_("banking:by", lambda: _bis_csv(f"Q.S.C+L.A.TO1.A.5J.A.{cps}.A.5J.N", "2010-Q1"))
    # 3) bilateral: banks located in row country -> claims on column country
    df3 = c.try_("banking:matrix", lambda: _bis_csv(f"Q.S.C.A.TO1.A.5J.A.{cps}.A.{cps}.N", "2023-Q1"))
    for k, iso in ISO2.items():
        rec = {}
        for tag, d, col in (("on", df, "L_CP_COUNTRY"), ("by", df2, "L_REP_CTY")):
            if d is None:
                continue
            for pos, nm in (("C", "claims"), ("L", "liabilities")):
                s = d[(d[col] == iso) & (d["L_POSITION"] == pos)].sort_values("TIME_PERIOD")
                if s.empty:
                    continue
                v = s["OBS_VALUE"].astype(float) * 1e6
                rec[f"{tag}_{nm}"] = {"latest": float(v.iloc[-1]), "period": s["TIME_PERIOD"].iloc[-1],
                                      "yoy": round((v.iloc[-1] / v.iloc[-5] - 1) * 100, 1) if len(v) > 4 and v.iloc[-5] else None,
                                      "series": _series(s["TIME_PERIOD"], v / 1e9, 64, 1)}
        if rec:
            out["countries"][k] = rec
    if df3 is not None and not df3.empty:
        per = df3["TIME_PERIOD"].max()
        last = df3[df3["TIME_PERIOD"] == per]
        out["matrix_period"] = per
        for _, r in last.iterrows():
            a = next((k for k, v in ISO2.items() if v == r["L_REP_CTY"]), None)
            b = next((k for k, v in ISO2.items() if v == r["L_CP_COUNTRY"]), None)
            if a and b and a != b:
                out["matrix"].setdefault(a, {})[b] = float(r["OBS_VALUE"]) * 1e6
    if not out["countries"]:
        raise RuntimeError("no BIS banking data")
    return out


# ------------------------------------------------------------------ IMF IIP
IIP_IND = {"IA_BP6_USD": "Total assets", "IL_BP6_USD": "Total liabilities", "IAD_BP6_USD": "Direct investment assets",
           "ILD_BP6_USD": "Direct investment liabilities", "IAP_BP6_USD": "Portfolio investment assets",
           "ILP_BP6_USD": "Portfolio investment liabilities", "IAO_BP6_USD": "Other investment assets",
           "ILO_BP6_USD": "Other investment liabilities", "IAR_BP6_USD": "Reserve assets"}


def collect_iip(c) -> dict:
    out = {}
    for k, iso in ISO2.items():
        docs = c.try_(f"iip:{k}", lambda: D.dbn_series("BOP", {"FREQ": ["Q"], "REF_AREA": [iso], "INDICATOR": list(IIP_IND)}))
        freq = "Quarterly"
        if not docs:
            docs = c.try_(f"iip:{k}:A", lambda: D.dbn_series("BOP", {"FREQ": ["A"], "REF_AREA": [iso], "INDICATOR": list(IIP_IND)}))
            freq = "Annual"
        rec = {}
        for d in docs or []:
            ind = (d.get("dimensions") or {}).get("INDICATOR")
            pts = [(p, float(v)) for p, v in zip(d.get("period", []), d.get("value", [])) if v not in (None, "NA")]
            if ind in IIP_IND and pts:
                pts = pts[-48:]
                rec[ind] = {"label": IIP_IND[ind], "latest": pts[-1][1] * 1e6, "period": pts[-1][0],
                            "series": {"dates": [p for p, _ in pts], "values": [round(v / 1e3, 1) for _, v in pts]}}  # US$ bn
        if rec:
            a, l = rec.get("IA_BP6_USD"), rec.get("IL_BP6_USD")
            if a and l and a["period"] == l["period"]:
                la = dict(zip(a["series"]["dates"], a["series"]["values"]))
                pairs = [(p, round(la[p] - v, 1)) for p, v in zip(l["series"]["dates"], l["series"]["values"]) if p in la]
                rec["NET"] = {"label": "Net international investment position", "latest": a["latest"] - l["latest"], "period": a["period"],
                              "series": {"dates": [p for p, _ in pairs], "values": [v for _, v in pairs]}}
            out[k] = {"freq": freq, "items": rec}
    if not out:
        raise RuntimeError("no IIP data")
    return out


# ------------------------------------------------------------------ official gold
GOLD_HOLDERS = ["US", "DE", "IT", "FR", "RU", "CN", "CH", "JP", "IN", "NL", "TR", "PL", "GB", "KZ", "UZ", "SA", "CZ", "QA", "SG", "TH", "HU", "IQ"]
TROY_OZ_PER_TONNE = 32150.7466


def collect_cb_gold(c) -> dict:
    docs = c.try_("cbgold:ifs", lambda: D.dbn_series("IFS", {"FREQ": ["M"], "REF_AREA": GOLD_HOLDERS, "INDICATOR": ["RAFAGOLDV_OZT"]}))
    if not docs:
        raise RuntimeError("no IFS gold data")
    lab = {}
    try:
        lab = D.dbn_labels("IFS", "REF_AREA")
    except Exception:  # noqa: BLE001
        pass
    rows = []
    for d in docs:
        iso = (d.get("dimensions") or {}).get("REF_AREA")
        pts = [(p, float(v)) for p, v in zip(d.get("period", []), d.get("value", [])) if v not in (None, "NA")]
        if not pts:
            continue
        t = [(p, v * 1e6 / TROY_OZ_PER_TONNE) for p, v in pts]  # million troy oz -> tonnes
        last = t[-1]
        back = lambda n: t[-1 - n][1] if len(t) > n else None  # noqa: E731
        rows.append({"iso2": iso, "name": lab.get(iso, iso), "tonnes": round(last[1], 1), "period": last[0],
                     "chg_1m": round(last[1] - back(1), 1) if back(1) is not None else None,
                     "chg_12m": round(last[1] - back(12), 1) if back(12) is not None else None,
                     "series": {"dates": [p for p, _ in t[-120:]], "values": [round(v, 1) for _, v in t[-120:]]}})
    rows.sort(key=lambda r: -r["tonnes"])
    return {"holders": rows, "latest_period": max(r["period"] for r in rows) if rows else None}


# ------------------------------------------------------------------ TIC
def collect_tic(c) -> dict:
    url = "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.txt"
    txt = c.try_("tic:slt5", lambda: D.get(url, timeout=40).text)
    if not txt:
        raise RuntimeError("TIC unavailable")
    lines = [ln.rstrip("\r") for ln in txt.split("\n")]
    hdr = next(i for i, ln in enumerate(lines) if ln.startswith("Country\t"))
    months = [m.strip() for m in lines[hdr].split("\t")[1:] if m.strip()]
    rows = []
    for ln in lines[hdr + 1:]:
        parts = [p.strip() for p in ln.split("\t")]
        if len(parts) < 2 or not parts[0] or not re.match(r"^-?[\d.]+$", parts[1] or ""):
            continue
        vals = [float(p) if re.match(r"^-?[\d.]+$", p) else None for p in parts[1:len(months) + 1]]
        rows.append({"name": parts[0], "values": vals})
    if not rows:
        raise RuntimeError("TIC parse failed")
    for r in rows:
        v = r["values"]
        r["latest"] = v[0]
        r["chg_1m"] = round(v[0] - v[1], 1) if len(v) > 1 and v[0] is not None and v[1] is not None else None
        r["chg_12m"] = round(v[0] - v[12], 1) if len(v) > 12 and v[0] is not None and v[12] is not None else None
    return {"months": months, "rows": rows, "unit": "US$ billions", "source_url": url}


# ------------------------------------------------------------------ OECD
OECD_AREAS = ["USA", "CHN", "JPN", "DEU", "FRA", "IND", "GBR", "CAN", "CHE"]
OECD_BASE = "https://sdmx.oecd.org/public/rest/data"


def _oecd(flow: str, key: str, start: str) -> pd.DataFrame:
    r = D.get(f"{OECD_BASE}/{flow}/{key}", {"startPeriod": start, "format": "csvfilewithlabels"}, timeout=90, retries=1)
    return pd.read_csv(io.StringIO(r.text), dtype=str)


def _pick(df: pd.DataFrame, prefs: dict) -> pd.DataFrame:
    """From several variants of one indicator keep the preferred one (e.g. seasonally adjusted, y/y growth)."""
    for col, order in prefs.items():
        if col in df.columns and df[col].nunique() > 1:
            for o in order:
                if (df[col] == o).any():
                    df = df[df[col] == o]
                    break
            else:
                df = df[df[col] == df[col].iloc[0]]
    return df


def collect_oecd(c) -> dict:
    inv3 = {v: k for k, v in ISO3.items()}
    out = {"countries": {}, "labels": {}}
    cli = c.try_("oecd:cli", lambda: _oecd("OECD.SDD.STES,DSD_STES@DF_CLI,", f"{'+'.join(OECD_AREAS)}.M.LI+BCICP+CCICP......", "2016-01"))
    kei = c.try_("oecd:kei", lambda: _oecd("OECD.SDD.STES,DSD_KEI@DF_KEI,", f"{'+'.join(OECD_AREAS)}.M........", "2019-01"))
    for src, df in (("cli", cli), ("kei", kei)):
        if df is None or df.empty:
            continue
        df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
        df = df.dropna(subset=["OBS_VALUE"])
        for (area, meas), g in df.groupby(["REF_AREA", "MEASURE"]):
            k = inv3.get(area)
            if not k:
                continue
            if src == "kei" and meas in ("BCICP", "CCICP", "LI"):
                continue  # take these from the CLI dataset
            rate_like = "UNIT_MEASURE" in g.columns and g["UNIT_MEASURE"].isin(["PA", "PT_LF", "PB", "PT_B1GQ"]).any()
            if rate_like:   # rates and balances: show the level
                g = _pick(g, {"UNIT_MEASURE": ["PA", "PT_LF", "PB", "PT_B1GQ"], "TRANSFORMATION": ["_Z", "GY"]})
            g = _pick(g, {"ADJUSTMENT": ["AA", "Y", "S", "N", "_Z"], "TRANSFORMATION": ["GY", "IX", "_Z", "G1"],
                          "ACTIVITY": ["_T", "C", "_Z"], "UNIT_MEASURE": ["IX", "PA", "PT_LF", "PB"]})
            # if still several series (e.g. different units) keep the longest
            key_cols = [x for x in ("UNIT_MEASURE", "ACTIVITY", "ADJUSTMENT", "TRANSFORMATION") if x in g.columns]
            if key_cols and g.groupby(key_cols).ngroups > 1:
                best = g.groupby(key_cols).size().idxmax()
                best = best if isinstance(best, tuple) else (best,)
                for col, val in zip(key_cols, best):
                    g = g[g[col] == val]
            g = g.sort_values("TIME_PERIOD")
            if g.empty:
                continue
            row = g.iloc[-1]
            tr = row.get("Transformation", "") if "Transformation" in g.columns else ""
            unit = row.get("Unit of measure", "") if "Unit of measure" in g.columns else ""
            lab = row.get("Measure", meas) if "Measure" in g.columns else meas
            out["labels"][meas] = lab
            out["countries"].setdefault(k, {})[meas] = {
                "label": lab, "unit": unit, "transform": tr if tr != "Not applicable" else "",
                "adjustment": row.get("Adjustment", "") if "Adjustment" in g.columns else "",
                "latest": float(row["OBS_VALUE"]), "period": row["TIME_PERIOD"],
                "prev": float(g["OBS_VALUE"].iloc[-2]) if len(g) > 1 else None,
                "series": _series(g["TIME_PERIOD"], g["OBS_VALUE"], 84, 2)}
    if not out["countries"]:
        raise RuntimeError("no OECD data")
    return out


# ------------------------------------------------------------------ calendar
CAL_IMPORTANCE = [
    ("Consumer Price Index", "High", "Inflation; drives Fed expectations, real yields, gold and Bitcoin"),
    ("Employment Situation", "High", "Payrolls and unemployment; the main labour-market release"),
    ("Gross Domestic Product", "High", "Output growth and the GDP price index"),
    ("Personal Income and Outlays", "High", "PCE inflation, the Fed's preferred measure"),
    ("FOMC Press Release", "High", "Federal Reserve policy decision"),
    ("Producer Price Index", "Medium", "Pipeline inflation"),
    ("Advance Monthly Sales for Retail", "Medium", "Consumer spending"),
    ("Job Openings and Labor Turnover", "Medium", "Labour demand (JOLTS)"),
    ("Industrial Production and Capacity", "Medium", "Factory output"),
    ("Unemployment Insurance Weekly Claims", "Medium", "Weekly jobless claims"),
    ("Surveys of Consumers", "Medium", "University of Michigan sentiment and inflation expectations"),
    ("Employment Cost Index", "Medium", "Wage growth"),
    ("U.S. International Trade in Goods and Services", "Medium", "Trade balance"),
    ("New Residential Construction", "Low", "Housing starts and permits"),
    ("Advance Durable Goods", "Low", "Capital goods orders"),
    ("Productivity and Costs", "Low", "Unit labour costs"),
    ("Treasury International Capital", "Low", "Foreign flows into US securities"),
    ("H.4.1 Factors Affecting Reserve Balances", "Low", "Fed balance sheet (weekly)"),
    ("Euro Short Term Rate", None, None),
]


def collect_calendar(c) -> dict:
    events = []
    key = os.environ.get("FRED_API_KEY")
    if key:
        start, end = NOW.strftime("%Y-%m-%d"), (NOW + timedelta(days=75)).strftime("%Y-%m-%d")
        j = c.try_("calendar:fred", lambda: D.get("https://api.stlouisfed.org/fred/releases/dates",
                                                  {"api_key": key, "file_type": "json", "realtime_start": start, "realtime_end": end,
                                                   "include_release_dates_with_no_data": "true", "limit": 1000, "sort_order": "asc"}, timeout=40).json())
        for r in (j or {}).get("release_dates", []):
            nm = r.get("release_name", "")
            hit = next((x for x in CAL_IMPORTANCE if nm.startswith(x[0]) or x[0] in nm), None)
            if not hit or not hit[1]:
                continue
            events.append({"date": r["date"], "event": nm, "region": "US", "importance": hit[1], "why": hit[2],
                           "source": "FRED release calendar (St. Louis Fed)", "url": f"https://fred.stlouisfed.org/release?rid={r.get('release_id')}",
                           "status": "Scheduled"})
    da = c.try_("calendar:difficulty", lambda: D.get("https://mempool.space/api/v1/difficulty-adjustment", timeout=30).json())
    if da and da.get("estimatedRetargetDate"):
        dt = datetime.fromtimestamp(da["estimatedRetargetDate"] / 1000, tz=timezone.utc)
        events.append({"date": dt.strftime("%Y-%m-%d"), "event": f"Bitcoin difficulty adjustment (estimated {da.get('difficultyChange', 0):+.1f}%)",
                       "region": "Bitcoin", "importance": "Low", "why": "Changes mining economics; the date and size are estimates until the block arrives",
                       "source": "mempool.space", "url": "https://mempool.space/mining", "status": "Estimated"})
    # de-duplicate weekly series etc.
    seen, out = set(), []
    for e in sorted(events, key=lambda e: (e["date"], e["event"])):
        k = (e["date"], e["event"])
        if k not in seen:
            seen.add(k)
            out.append(e)
    if not out:
        raise RuntimeError("no calendar events")
    return {"events": out, "window_days": 75}


# ------------------------------------------------------------------ valuation
def _multpl(path: str) -> pd.Series:
    t = D.get(f"https://www.multpl.com/{path}/table/by-month", timeout=40).text
    rows = re.findall(r"<td>\s*([A-Z][a-z]{2} \d{1,2}, \d{4})\s*</td>\s*<td[^>]*>(.*?)</td>", t, re.S)
    vals = {}
    for d, v in rows:
        m = re.search(r"(-?\d+(?:\.\d+)?)", re.sub(r"<[^>]+>|&#x?\w+;", " ", v))
        if m:
            vals[pd.Timestamp(datetime.strptime(d, "%b %d, %Y"))] = float(m.group(1))
    if len(vals) < 24:
        raise RuntimeError(f"multpl {path}: parsed {len(vals)} rows")
    return pd.Series(vals).sort_index()


def _damodaran() -> dict:
    t = D.get("https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.html", timeout=60).text
    title = re.search(r"Updated[^<]{0,60}", t)
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S | re.I):
        cells = [_html.unescape(re.sub(r"<[^>]+>", " ", x)).replace("\xa0", " ").strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        cells = [re.sub(r"\s+", " ", x) for x in cells]
        if cells:
            rows.append(cells)
    hi = next(i for i, r in enumerate(rows) if any("Country" == x or x.startswith("Country") for x in r) and any("Equity Risk" in x or "ERP" in x for x in r))
    header = rows[hi]
    want = {"United States": "us", "China": "cn", "Japan": "jp", "Germany": "de", "France": "fr", "India": "in",
            "United Kingdom": "gb", "Canada": "ca", "Switzerland": "ch", "Russia": "ru"}
    out = {}
    for r in rows[hi + 1:]:
        if r and r[0] in want and len(r) >= 3:
            out[want[r[0]]] = dict(zip(header, r))
    if len(out) < 6:
        raise RuntimeError("Damodaran parse failed")
    return {"header": header, "countries": out, "updated": title.group(0).strip() if title else None}


def collect_valuation(c) -> dict:
    out = {}
    for k, path, nm in (("cape", "shiller-pe", "Shiller CAPE (cyclically adjusted P/E)"), ("pe", "s-p-500-pe-ratio", "S&P 500 P/E (trailing 12m earnings)"),
                        ("dy", "s-p-500-dividend-yield", "S&P 500 dividend yield, %"), ("ey", "s-p-500-earnings-yield", "S&P 500 earnings yield, %")):
        s = c.try_(f"valuation:{k}", lambda: _multpl(path))
        if s is not None and len(s):
            s10 = s[s.index >= s.index[-1] - pd.DateOffset(years=30)]
            pct = float((s10 < s.iloc[-1]).mean() * 100)
            out[k] = {"name": nm, "latest": float(s.iloc[-1]), "date": s.index[-1].strftime("%Y-%m-%d"),
                      "avg_30y": round(float(s10.mean()), 2), "pctile_30y": round(pct), "long_avg": round(float(s.mean()), 2),
                      "first": s.index[0].strftime("%Y"),
                      "series": _series([d.strftime("%Y-%m") for d in s.index[-480:]], s.values[-480:], None, 2)}
    dam = c.try_("valuation:damodaran", _damodaran)
    if dam:
        out["damodaran"] = dam
    if not out:
        raise RuntimeError("no valuation data")
    return out
