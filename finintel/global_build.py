"""Builds data/global.json: collection + analytics for the global modules (1-12)."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import global_config as G
from . import global_data as D
from .connectors import ConnectorError, fred

NOW = datetime.now(timezone.utc)
YEAR = NOW.year


class Collector:
    def __init__(self, store, offline=False):
        self.store, self.offline, self.errors, self.saved = store, offline, {}, []
        self.fails, self.t0 = {}, time.time()

    def keep(self, sid, s: pd.Series):
        if s is not None and not s.dropna().empty and not self.offline:
            try:
                self.store.save_series(sid, s)
                self.saved.append(sid)
            except Exception as e:  # storage must never stop the build
                self.errors[f"store:{sid}"] = str(e)[:120]

    def offline_series(self, sid):
        s = self.store.as_known_on(sid, NOW.strftime("%Y-%m-%d"))
        if s.empty:
            raise ConnectorError(f"{sid} not in database")
        return s

    def try_(self, sid, fn):
        src = sid.split(":")[0]
        if self.fails.get(src, 0) >= (8 if src == "wb" else 4):
            self.errors[sid] = "skipped: source failed repeatedly earlier in this run"
            return None
        try:
            out = fn()
            self.fails[src] = 0
            return out
        except Exception as e:
            self.fails[src] = self.fails.get(src, 0) + 1
            self.errors[sid] = f"{type(e).__name__}: {str(e)[:200]}"
            return None

    def stage(self, name):
        print(f"[global] {name} ({time.time() - self.t0:.0f}s, {len(self.errors)} errors so far)", flush=True)


# ------------------------------------------------------------------ markets
def collect_markets(c: Collector) -> dict:
    tickers = {}
    for k, n, t, *_ in G.INDICES:
        tickers[t] = ("index", k, n)
    for ccy, t, inv in G.FX:
        tickers[t] = ("fx", ccy, ccy)
    tickers[G.DXY] = ("fx", "USD", "US dollar index (DXY)")
    for k, n, t, *_ in G.COMMODITIES:
        if t:
            tickers[t] = ("commodity", k, n)
    for k, n, t in G.PROXIES + G.US_YIELDS:
        tickers[t] = ("proxy", k, n)
    out = {}
    for t, (kind, k, n) in tickers.items():
        sid = f"yahoo:{t}"
        if c.offline:
            s = c.try_(sid, lambda: c.offline_series(sid))
        else:
            s = c.try_(sid, lambda: D.yahoo(t, "10y"))
            c.keep(sid, s)
            time.sleep(0.25)
        if s is not None and len(s) > 5:
            out[t] = s
    return out


def usd_value(fx: dict[str, pd.Series]) -> dict[str, pd.Series]:
    """US dollars per one unit of each currency (USD = 1)."""
    out = {}
    for ccy, t, inv in G.FX:
        s = fx.get(t)
        if s is not None:
            out[ccy] = (1 / s) if inv else s
    return out


def weekday(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_index()
    df = df.reindex(pd.date_range(df.index.min(), df.index.max(), freq="D")).ffill(limit=3)
    return df[df.index.dayofweek < 5]


def currency_block(px: dict, bis_rates: dict, imf_df: pd.DataFrame | None, wb: dict, eer: dict, cftc: dict) -> dict:
    uv = usd_value(px)
    dxy = px.get(G.DXY)
    ccys = ["USD"] + [c for c, *_ in G.FX if c in uv]
    windows = {"w1": 7, "m1": 30, "m3": 91, "y1": 365}
    frame = weekday(pd.DataFrame({c: uv[c] for c in ccys if c != "USD"}))
    frame["USD"] = 1.0
    last = frame.index.max()

    def chg(c, days):
        p = frame[c][frame.index <= last - pd.Timedelta(days=days)].dropna()
        cur = frame[c].dropna()
        return None if p.empty or cur.empty else float(cur.iloc[-1] / p.iloc[-1])

    rel = {}
    for w, days in windows.items():
        m = []
        for a in ccys:
            row = []
            for b in ccys:
                ra, rb = chg(a, days), chg(b, days)
                row.append(None if ra is None or rb is None or a == b else round((ra / rb - 1) * 100, 2))
            m.append(row)
        rel[w] = m
    strength = []
    for i, a in enumerate(ccys):
        sc = {}
        for w in windows:
            vals = [v for v in rel[w][i] if v is not None]
            sc[w] = round(float(np.mean(vals)), 2) if vals else None
        comp = [sc[w] * wt for w, wt in (("w1", .2), ("m1", .3), ("m3", .3), ("y1", .2)) if sc[w] is not None]
        absolute = D.perf(dxy) if a == "USD" and dxy is not None else (D.perf(uv[a]) if a in uv else None)
        vol = None if a == "USD" else (round(float(uv[a].pct_change().tail(30).std() * np.sqrt(252) * 100), 1) if a in uv else None)
        if a == "USD" and dxy is not None:
            vol = round(float(dxy.pct_change().tail(30).std() * np.sqrt(252) * 100), 1)
        ck = G.CCY_COUNTRY[a]
        bk = next(x["bis"] for x in G.COUNTRIES if x["key"] == ck)
        rate = bis_rates.get(bk, {}).get("latest")
        us_rate = bis_rates.get("US", {}).get("latest")
        infl = infl_us = None
        if imf_df is not None:
            iso = "EURO" if a == "EUR" else next(x["iso3"] for x in G.COUNTRIES if x["key"] == ck)
            d = imf_df[(imf_df.code == "PCPIPCH") & (imf_df.year == YEAR - 1)]
            vi = d[d.iso3 == iso].value
            if a == "EUR" and vi.empty:
                vi = d[d.iso3.isin(["DEU", "FRA"])].value
                vi = pd.Series([vi.mean()]) if not vi.empty else vi
            vu = d[d.iso3 == "USA"].value
            infl = None if vi.empty else round(float(vi.iloc[0]), 2)
            infl_us = None if vu.empty else round(float(vu.iloc[0]), 2)
        if infl is None:  # World Bank CPI fallback (latest year, may lag)
            iso_wb = "EMU" if a == "EUR" else next(x["iso3"] for x in G.COUNTRIES if x["key"] == ck)
            w, wu = wb.get("FP.CPI.TOTL.ZG", {}).get(iso_wb, {}).get("latest"), wb.get("FP.CPI.TOTL.ZG", {}).get("USA", {}).get("latest")
            if w and wu:
                infl, infl_us = round(w["value"], 2), round(wu["value"], 2)
        ppp_iso = "EMU" if a == "EUR" else next(x["iso3"] for x in G.COUNTRIES if x["key"] == ck)
        ppp = wb.get("PA.NUS.PPPC.RF", {}).get(ppp_iso, {}).get("latest")
        strength.append({"ccy": a, "name": G.CURRENCY_NAMES[a], "scores": sc,
                         "composite": round(sum(comp) / sum(wt for w, wt in (("w1", .2), ("m1", .3), ("m3", .3), ("y1", .2)) if sc[w] is not None), 2) if comp else None,
                         "absolute": absolute, "vol30": vol, "policy_rate": rate,
                         "rate_diff_vs_usd": None if rate is None or us_rate is None else round(rate["value"] - us_rate["value"], 2),
                         "inflation": infl, "infl_diff_vs_us": None if infl is None or infl_us is None else round(infl - infl_us, 2),
                         "ppp_ratio": ppp, "reer": eer.get(bk, {}).get("R"), "neer": eer.get(bk, {}).get("N"),
                         "cftc": cftc.get(a)})
    ranked = sorted([s for s in strength if s["composite"] is not None], key=lambda s: -s["composite"])
    for i, s in enumerate(ranked):
        s["rank"] = i + 1
    series = {c: D.ser(uv[c], 520, 6) for c in uv}
    if dxy is not None:
        series["USD"] = D.ser(dxy, 520, 3)
    return {"currencies": ccys, "relative": rel, "strength": strength, "series": series,
            "note": "Relative change = % change of the row currency against the column currency over the window. "
                    "Strength score = average of a currency's change against all others; composite weights 1W 20%, 1M 30%, 3M 30%, 1Y 20%."}


def asset_matrix(px: dict) -> dict:
    uv = usd_value(px)
    drivers = {"USD (DXY)": px.get(G.DXY)} | {f"{c}": uv[c] for c in ("EUR", "JPY", "CNY", "GBP", "CHF", "CAD", "INR") if c in uv}
    assets = {"Gold": px.get("GC=F"), "Silver": px.get("SI=F"), "Oil (WTI)": px.get("CL=F"), "Copper": px.get("HG=F"),
              "Agriculture (DBA)": px.get("DBA"), "Base metals (DBB)": px.get("DBB"), "Global equities (ACWI)": px.get("ACWI"),
              "Emerging markets (EEM)": px.get("EEM"), "Long Treasuries (TLT)": px.get("TLT"), "High yield (HYG)": px.get("HYG"),
              "Bitcoin": px.get("BTC-USD")}
    drivers = {k: v for k, v in drivers.items() if v is not None}
    assets = {k: v for k, v in assets.items() if v is not None}
    df = weekday(pd.DataFrame({**{f"d:{k}": v for k, v in drivers.items()}, **{f"a:{k}": v for k, v in assets.items()}}))
    r = df.pct_change()
    out = {"drivers": list(drivers), "assets": list(assets), "corr90": [], "corr250": [], "beta250": []}
    for d in drivers:
        c90, c250, b250 = [], [], []
        for a in assets:
            x, y = r[f"d:{d}"].tail(250), r[f"a:{a}"].tail(250)
            ok = x.notna() & y.notna()
            x9, y9 = r[f"d:{d}"].tail(90), r[f"a:{a}"].tail(90)
            ok9 = x9.notna() & y9.notna()
            c90.append(round(float(x9[ok9].corr(y9[ok9])), 2) if ok9.sum() > 40 else None)
            c250.append(round(float(x[ok].corr(y[ok])), 2) if ok.sum() > 120 else None)
            b250.append(round(float(np.polyfit(x[ok], y[ok], 1)[0]), 2) if ok.sum() > 120 else None)
        out["corr90"].append(c90); out["corr250"].append(c250); out["beta250"].append(b250)
    # historical scenario: concurrent 3-month moves when the dollar index rose or fell more than 3%
    if "USD (DXY)" in drivers:
        m = df.resample("ME").last()
        q = m.pct_change(3) * 100
        q = q.iloc[::3].dropna(subset=["d:USD (DXY)"])
        buckets = {"Dollar up > 3% in 3 months": q["d:USD (DXY)"] > 3, "Dollar within ±3%": q["d:USD (DXY)"].abs() <= 3,
                   "Dollar down > 3% in 3 months": q["d:USD (DXY)"] < -3}
        sc = []
        for name, mask in buckets.items():
            row = {"bucket": name, "n": int(mask.sum()), "assets": {}}
            for a in assets:
                v = q.loc[mask, f"a:{a}"].dropna()
                row["assets"][a] = None if len(v) < 2 else {"median": round(float(v.median()), 1), "n": int(len(v))}
            sc.append(row)
        out["scenarios"] = {"sample": f"{q.index.min():%Y-%m} to {q.index.max():%Y-%m}", "rows": sc,
                            "note": "Non-overlapping 3-month windows. Historical association only; supply shocks and other drivers also moved these assets."}
    roll = {}
    for a in ("Gold", "Oil (WTI)", "Copper", "Emerging markets (EEM)"):
        if "USD (DXY)" in drivers and a in assets:
            rc = r["d:USD (DXY)"].rolling(250, min_periods=180).corr(r[f"a:{a}"]).dropna()
            roll[a] = D.ser(rc.iloc[::5], 600, 3)
    out["rolling_usd"] = roll
    return out


# ------------------------------------------------------------- statistics
def collect_bis(c: Collector) -> tuple[dict, dict]:
    areas = sorted({x["bis"] for x in G.COUNTRIES})
    rates = {}
    df = c.try_("bis:WS_CBPOL", lambda: D.bis("WS_CBPOL", "M." + "+".join(areas), "2005-01"))
    if df is not None:
        for a, g in df.groupby("REF_AREA"):
            s = pd.Series(g.OBS_VALUE.values, index=pd.to_datetime(g.TIME_PERIOD.astype(str))).sort_index()
            c.keep(f"bis:cbpol:{a}", s)
            chg = s.diff()
            moves = chg[chg.abs() > 1e-9]
            rates[a] = {"latest": {"value": float(s.iloc[-1]), "date": s.index[-1].strftime("%Y-%m")},
                        "last_move": None if moves.empty else {"size": round(float(moves.iloc[-1]), 2), "date": moves.index[-1].strftime("%Y-%m")},
                        "y1_change": round(float(s.iloc[-1] - s[s.index <= s.index[-1] - pd.DateOffset(months=12)].iloc[-1]), 2) if len(s) > 12 else None,
                        "series": D.ser(s, 300, 3)}
    eer = {}
    df = c.try_("bis:WS_EER", lambda: D.bis("WS_EER", "M.R+N.B." + "+".join(areas), "2010-01"))
    if df is not None and "EER_TYPE" in df:
        for (a, t), g in df.groupby(["REF_AREA", "EER_TYPE"]):
            s = pd.Series(g.OBS_VALUE.values, index=pd.to_datetime(g.TIME_PERIOD.astype(str))).sort_index()
            c.keep(f"bis:eer:{t}:{a}", s)
            p12 = s[s.index <= s.index[-1] - pd.DateOffset(months=12)]
            eer.setdefault(a, {})[t] = {"latest": round(float(s.iloc[-1]), 2), "date": s.index[-1].strftime("%Y-%m"),
                                        "y1": None if p12.empty else round(float(s.iloc[-1] / p12.iloc[-1] - 1) * 100, 2),
                                        "vs_10y_avg": round(float(s.iloc[-1] / s.tail(120).mean() - 1) * 100, 1), "series": D.ser(s, 200, 2)}
    return rates, eer


def collect_wb(c: Collector) -> tuple[dict, dict]:
    iso = [x["iso3"] for x in G.COUNTRIES] + G.WB_EXTRA_AREAS
    out, pub = {}, {}
    for code in G.WB:
        res = c.try_(f"wb:{code}", lambda: D.worldbank(code, iso))
        if res is None:
            continue
        df, m = res
        pub[code] = m.get("published")
        out[code] = {}
        for i, g in df.groupby("iso3"):
            g = g.sort_values("year")
            s = pd.Series(g.value.values, index=pd.to_datetime(g.year.astype(str) + "-12-31"))
            c.keep(f"wb:{code}:{i}", s)
            out[code][i] = {"latest": {"value": float(g.value.iloc[-1]), "year": int(g.year.iloc[-1])},
                            "series": {"years": g.year.astype(int).tolist(), "values": [round(float(v), 4) for v in g.value]}}
        time.sleep(2.0)
    return out, pub


def collect_imf(c: Collector) -> pd.DataFrame | None:
    iso = [x["iso3"] for x in G.COUNTRIES] + ["EURO"]
    frames = []
    for code in G.IMF:
        df = c.try_(f"imf:{code}", lambda: D.imf(code, iso))
        if df is not None:
            df["code"] = code
            frames.append(df)
            for i, g in df.groupby("iso3"):
                c.keep(f"imf:{code}:{i}", pd.Series(g.value.values, index=pd.to_datetime(g.year.astype(str) + "-12-31")))
        time.sleep(0.3)
    return pd.concat(frames) if frames else None


def imf_kind(year: int) -> str:
    return "IMF projection" if year >= YEAR else ("IMF estimate" if year == YEAR - 1 else "Actual (IMF)")


def imf_block(df: pd.DataFrame | None) -> dict:
    if df is None:
        return {}
    out = {}
    for code, g0 in df.groupby("code"):
        out[code] = {}
        for i, g in g0.groupby("iso3"):
            g = g[(g.year >= 2000) & (g.year <= YEAR + 5)].sort_values("year")
            hist = g[g.year < YEAR]
            latest = hist.iloc[-1] if not hist.empty else g.iloc[-1]
            out[code][i] = {"latest": {"value": round(float(latest.value), 3), "year": int(latest.year), "kind": imf_kind(int(latest.year))},
                            "series": {"years": g.year.astype(int).tolist(), "values": [round(float(v), 3) for v in g.value],
                                       "kinds": [imf_kind(int(y)) for y in g.year]}}
    return out


# ---------------------------------------------------------------- trade
HS_GROUPS = {"Energy (HS 27)": ["27"], "Metals and ores (HS 26, 72–81)": ["26"] + [str(x) for x in range(72, 82)],
             "Food and agriculture (HS 01–24)": [f"{x:02d}" for x in range(1, 25)], "Machinery (HS 84)": ["84"],
             "Electrical and electronics, incl. semiconductors (HS 85)": ["85"], "Pharmaceuticals (HS 30)": ["30"],
             "Vehicles (HS 87)": ["87"], "Precious metals and stones (HS 71)": ["71"]}


def collect_trade(c: Collector) -> dict:
    if c.offline:
        return {}
    names = c.try_("comtrade:partners", D.comtrade_partner_names) or {}
    out = {}
    for x in G.COUNTRIES:
        rec = {"reporter": x["name"]}
        for flow, lab in (("X", "exports"), ("M", "imports")):
            r = c.try_(f"comtrade:{x['key']}:{flow}:partners", lambda: D.comtrade(x["m49"], flow, "TOTAL", None))
            if r is not None:
                df, yr = r
                df = df[df.partnerCode.astype(int) != 0] if "partnerCode" in df else df
                vcol = "primaryValue" if "primaryValue" in df else ("TradeValue" if "TradeValue" in df else None)
                if vcol:
                    df = df.groupby("partnerCode", as_index=False)[vcol].sum().sort_values(vcol, ascending=False)
                    tot = float(df[vcol].sum())
                    rec[lab] = {"year": yr, "total": tot, "partners": [{"code": int(p), "name": names.get(int(p), str(p)), "value": float(v),
                                                                        "share": round(float(v) / tot * 100, 2) if tot else None}
                                                                       for p, v in zip(df.partnerCode, df[vcol])][:25]}
            r = c.try_(f"comtrade:{x['key']}:{flow}:hs2", lambda: D.comtrade(x["m49"], flow, "AG2", "0"))
            if r is not None:
                df, yr = r
                vcol = "primaryValue" if "primaryValue" in df else None
                if vcol and "cmdCode" in df:
                    df = df.groupby(["cmdCode"] + (["cmdDesc"] if "cmdDesc" in df else []), as_index=False)[vcol].sum().sort_values(vcol, ascending=False)
                    tot = float(df[vcol].sum())
                    shares = (df[vcol] / tot) if tot else df[vcol] * 0
                    groups = {g: round(float(df[df.cmdCode.astype(str).str.zfill(2).isin(codes)][vcol].sum() / tot * 100), 2) if tot else None
                              for g, codes in HS_GROUPS.items()}
                    rec[f"{lab}_products"] = {"year": yr, "total": tot, "hhi": round(float((shares ** 2).sum() * 10000), 0),
                                              "top": [{"hs": str(cd).zfill(2), "desc": (ds if "cmdDesc" in df else ""), "value": float(v), "share": round(float(v) / tot * 100, 2)}
                                                      for cd, ds, v in zip(df.cmdCode, df.cmdDesc if "cmdDesc" in df else [""] * len(df), df[vcol])][:15],
                                              "groups": groups}
        out[x["key"]] = rec
    # bilateral matrix among covered economies (exports of row to column, from the row's own report)
    m49 = {x["m49"]: x["key"] for x in G.COUNTRIES}
    alias = {251: 250, 699: 356, 757: 756}  # Comtrade reporter codes vs partner codes for France, India, Switzerland
    keys = [x["key"] for x in G.COUNTRIES]
    mat = []
    for a in keys:
        row = []
        ex = (out.get(a) or {}).get("exports")
        lookup = {p["code"]: p["value"] for p in ex["partners"]} if ex else {}
        if ex:  # partners list was truncated to 25; refetch not needed for large economies
            pass
        for b in keys:
            code = next(x["m49"] for x in G.COUNTRIES if x["key"] == b)
            v = lookup.get(code, lookup.get(alias.get(code, -1)))
            row.append(None if a == b or not ex else (round(v / 1e9, 1) if v is not None else None))
        mat.append(row)
    return {"countries": out, "matrix": {"keys": keys, "values_bn": mat,
            "note": "US$ bn of exports from the row economy to the column economy, as reported by the exporter. Blank = not in its top-25 partner list or not reported."}}


# ---------------------------------------------------------------- companies
def collect_companies(c: Collector) -> list:
    if c.offline:
        return []
    out = []
    for cik, name in G.US_COMPANIES:
        rec = c.try_(f"sec:{cik}", lambda: D.sec_company(cik))
        if rec:
            rec["country"] = "us"
            rec["listed_name"] = name
            out.append(rec)
        time.sleep(0.15)
    return out


# ------------------------------------------------------------- relationship engine
def annual_change(s: pd.Series) -> pd.Series:
    a = s.resample("YE").mean()
    return (a.pct_change() * 100).dropna()


def rel_reports(px, wb, imf, rates, trade, extra) -> list:
    def p(t):
        s = px.get(t)
        return D.perf(s) if s is not None else None

    def corr_annual(x: pd.Series, y: pd.Series):
        df = pd.concat([x, y], axis=1).dropna()
        return (round(float(df.iloc[:, 0].corr(df.iloc[:, 1])), 2), len(df)) if len(df) >= 5 else (None, len(df))

    def wbv(code, iso):
        return wb.get(code, {}).get(iso, {}).get("latest")

    def imfv(code, iso):
        return imf.get(code, {}).get(iso, {}).get("latest")

    def wbs(code, iso):
        d = wb.get(code, {}).get(iso)
        return None if not d else pd.Series(d["series"]["values"], index=pd.to_datetime([f"{y}-12-31" for y in d["series"]["years"]]))

    def fmt(v, d=1, suf=""):
        return "n/a" if v is None else f"{v:+.{d}f}{suf}" if isinstance(v, (int, float)) else str(v)

    reports = []
    dxy, gold, oil, cu, wheat = (px.get(t) for t in (G.DXY, "GC=F", "CL=F", "HG=F", "ZW=F"))

    # 1 USD -> commodities
    ev, con = [], []
    if dxy is not None:
        pd_ = p(G.DXY)
        ev.append(f"Dollar index {pd_['last']:.2f}; 3-month change {fmt(pd_['m3'], 1, '%')}, 1-year {fmt(pd_['y1'], 1, '%')} (Yahoo Finance, {pd_['date']}).")
        r = weekday(pd.DataFrame({"d": dxy, "g": gold, "o": oil, "c": cu})).pct_change().tail(250)
        for k, n in (("g", "gold"), ("o", "WTI oil"), ("c", "copper")):
            if k in r and r[k].notna().sum() > 120:
                cc = round(float(r.d.corr(r[k])), 2)
                (ev if cc < 0 else con).append(f"250-day correlation of daily dollar-index and {n} returns: {cc:+.2f}" + (" (the expected inverse link holds)" if cc < 0 else " (the usual inverse link is not holding)") + ".")
    reports.append(dict(key="usd-commodities", title="How does USD appreciation affect commodity prices?",
        development="A stronger US dollar against major currencies.",
        mechanism=["Most commodities are priced in dollars, so a stronger dollar raises their cost in other currencies and can reduce non-US demand.",
                   "Producers outside the US earn dollars but pay local costs, so a strong dollar can lift their margins and supply at a given dollar price.",
                   "A strong dollar often coincides with tighter global financial conditions, which weighs on industrial demand and speculative positioning."],
        countries=["Commodity importers with weak currencies (India, Japan, euro area)", "Dollar-funded emerging markets", "Commodity exporters (Canada, Russia)"],
        industries=["Mining", "Energy", "Agriculture", "Commodity-intensive manufacturing"],
        assets=["Gold", "Oil", "Copper and base metals", "Agricultural futures", "Commodity currencies"],
        precedents=[{"period": "2014–2015", "text": "The dollar index rose sharply while oil and industrial metals fell; oversupply in oil was also a major cause."},
                    {"period": "2020–2021", "text": "A weaker dollar after March 2020 coincided with a broad commodity rally, alongside stimulus and supply disruptions."}],
        evidence=ev, contradicting=con,
        scenarios=[{"name": "Dollar strengthens further", "text": "Historically associated with weaker dollar-priced commodities, unless supply shocks dominate."},
                   {"name": "Dollar weakens", "text": "Historically associated with firmer commodity prices and stronger emerging-market demand."}],
        link="currencies/asset-matrix"))

    # 2 real yields -> gold
    ev, con = [], []
    ry = extra.get("DFII10")
    if ry is not None and gold is not None:
        ev.append(f"US 10y real yield {ry.dropna().iloc[-1]:.2f}% ({ry.dropna().index[-1]:%Y-%m-%d}); gold {p('GC=F')['last']:,.0f} with 1-year change {fmt(p('GC=F')['y1'], 1, '%')}.")
        df = weekday(pd.DataFrame({"ry": ry, "g": gold})).dropna()
        dd = pd.DataFrame({"ry": df.ry.diff(), "g": df.g.pct_change()}).dropna()
        for win in (250, 750):
            sub = dd.tail(win)
            if len(sub) > win * 0.7:
                cc = round(float(sub.ry.corr(sub.g)), 2)
                (ev if cc < 0 else con).append(f"{win}-session correlation of daily real-yield changes and gold returns: {cc:+.2f}.")
    con.append("Central bank gold buying (321 t in Q3 2026, WGC) has offset part of the real-yield headwind since 2022.")
    reports.append(dict(key="real-yields-gold", title="How do rising US real yields affect gold?",
        development="A rise in US inflation-adjusted (TIPS) yields.",
        mechanism=["Gold pays no income; higher real yields raise the return given up by holding it.",
                   "Higher real yields usually come with a firmer dollar, a second headwind for dollar-priced gold.",
                   "Price-insensitive buyers (central banks) can absorb selling by yield-sensitive investors."],
        countries=["United States (policy source)", "Major gold buyers: China, India, Türkiye, Poland"],
        industries=["Gold mining", "Jewellery", "Asset management (ETFs)"], assets=["Gold", "Silver", "Gold miners", "TIPS"],
        precedents=[{"period": "2013", "text": "Real yields rose in the 'taper tantrum' and gold fell by roughly 28% over the year."},
                    {"period": "2022–2024", "text": "Real yields rose steeply, yet gold reached record highs in 2024, supported by record central bank purchases."}],
        evidence=ev, contradicting=con,
        scenarios=[{"name": "Real yields keep rising", "text": "Headwind for gold unless official-sector buying accelerates."},
                   {"name": "Real yields fall as hikes end", "text": "Removes the main macro headwind identified in the scorecard."}],
        link="gold/fundamentals"))

    # 3 China industry -> copper
    ev, con = [], []
    cn_ind = wbs("NV.IND.TOTL.KD.ZG", "CHN")
    if cn_ind is not None and cu is not None:
        cc, n = corr_annual(cn_ind, annual_change(cu))
        if cc is not None:
            (ev if cc > 0 else con).append(f"Correlation of China's annual industry value-added growth with copper's annual average price change: {cc:+.2f} over {n} years (World Bank, Yahoo Finance).")
        lv = wbv("NV.IND.TOTL.KD.ZG", "CHN")
        if lv:
            ev.append(f"China industry value added grew {lv['value']:.1f}% in {lv['year']} (World Bank).")
    if cu is not None:
        ev.append(f"Copper 1-year change {fmt(p('HG=F')['y1'], 1, '%')} ({p('HG=F')['date']}).")
    con.append("Monthly industrial production and PMIs are not yet connected; annual data hides turning points.")
    reports.append(dict(key="china-copper", title="How does China's industrial production affect copper?",
        development="A change in China's industrial output.", mechanism=["China consumes roughly half of the world's refined copper, mostly for power grids, construction, appliances and vehicles.",
            "Stronger industrial activity raises copper demand and drawdowns from exchange inventories.", "Expectations move prices ahead of the data: policy stimulus announcements often lead copper."],
        countries=["China", "Chile and Peru (largest miners)", "DR Congo", "Australia"], industries=["Copper mining", "Power grid equipment", "Construction", "Electric vehicles"],
        assets=["Copper", "Mining equities", "Chilean peso, Australian dollar", "Base metals ETFs"],
        precedents=[{"period": "2009", "text": "China's stimulus-led industrial rebound coincided with copper more than doubling over the year."},
                    {"period": "2015", "text": "China's industrial slowdown coincided with copper falling to multi-year lows."}],
        evidence=ev, contradicting=con, scenarios=[{"name": "Chinese stimulus lifts industry", "text": "Historically supportive for copper and copper-exporter currencies."},
                                                   {"name": "Property and industry stay weak", "text": "Copper relies on energy-transition demand outside China."}], link="commodities/detail/copper"))

    # 4 Japan tightening -> capital flows
    ev, con = [], []
    jp = rates.get("JP")
    if jp:
        ev.append(f"Bank of Japan policy rate {jp['latest']['value']:.2f}% ({jp['latest']['date']}); 12-month change {fmt(jp.get('y1_change'), 2, ' pp')} (BIS).")
    jpy = usd_value(px).get("JPY")
    if jpy is not None:
        ev.append(f"Yen against the dollar: 3-month {fmt(D.perf(jpy)['m3'], 1, '%')}, 1-year {fmt(D.perf(jpy)['y1'], 1, '%')} (Yahoo Finance).")
    fo = wbv("BM.KLT.DINV.CD.WD", "JPN")
    if fo:
        ev.append(f"Japan FDI net outflows US${fo['value'] / 1e9:,.0f}bn in {fo['year']} (World Bank).")
    con.append("Bilateral portfolio holdings (IMF CPIS) and Japanese investors' monthly flows (MoF) are not yet connected.")
    reports.append(dict(key="japan-tightening", title="How does Japanese monetary tightening affect global capital flows?",
        development="The Bank of Japan raises rates or lets long-term yields rise.",
        mechanism=["Japan is the world's largest creditor nation; higher domestic yields make it more attractive for Japanese investors to keep savings at home.",
                   "Yen-funded carry trades lose appeal when the funding cost rises and the yen strengthens, forcing position cuts.",
                   "Repatriation can lift yields in markets where Japanese investors are large holders (US Treasuries, European bonds)."],
        countries=["Japan", "United States", "Euro area", "Australia"], industries=["Banks and life insurers", "Exporters", "Asset managers"],
        assets=["Yen", "JGBs", "US Treasuries", "Global equities", "Carry-trade currencies"],
        precedents=[{"period": "July–August 2024", "text": "A BoJ rate rise and a sharp yen rally coincided with a carry-trade unwind; the Nikkei 225 fell 12.4% on 5 August 2024."},
                    {"period": "Structural", "text": "Japanese investors are among the largest foreign holders of US Treasuries."}],
        evidence=ev, contradicting=con, scenarios=[{"name": "Faster BoJ tightening", "text": "Risk of yen strength and pressure on carry trades and foreign bonds."},
                                                   {"name": "Gradual normalisation", "text": "Flows adjust slowly with limited market stress."}], link="economies/jp"))

    # 5 Europe industry -> German equities
    ev, con = [], []
    de_ind = wbv("NV.IND.TOTL.KD.ZG", "DEU")
    if de_ind:
        (con if de_ind["value"] < 0 else ev).append(f"German industry value added {de_ind['value']:+.1f}% in {de_ind['year']} (World Bank).")
    dax = px.get("^GDAXI")
    if dax is not None:
        pdx = D.perf(dax)
        ev.append(f"DAX {pdx['last']:,.0f}; 1-year change {fmt(pdx['y1'], 1, '%')} (Yahoo Finance, {pdx['date']}).")
        if de_ind and de_ind["value"] < 0 and (pdx["y1"] or 0) > 0:
            con.append("The DAX has risen while German industry contracted: index earnings are global, not domestic.")
    reports.append(dict(key="europe-germany", title="How does European industrial weakness affect German equities?",
        development="Falling industrial output in Germany and the euro area.",
        mechanism=["Weak industry hurts domestic cyclicals (chemicals, autos, machinery) through lower volumes and margins.",
                   "DAX companies earn most of their revenue outside Germany, which dilutes the domestic effect.",
                   "Weakness can bring ECB easing and a weaker euro, both of which can support exporters' share prices."],
        countries=["Germany", "Euro area", "China (export market)", "United States"], industries=["Chemicals", "Autos", "Machinery", "Utilities"],
        assets=["DAX", "STOXX Europe 600", "Euro", "Bunds"],
        precedents=[{"period": "2022–2024", "text": "German industrial output fell after the energy-price shock while the DAX reached record highs, led by globally exposed companies."}],
        evidence=ev, contradicting=con, scenarios=[{"name": "Industrial recovery", "text": "Supports domestic cyclicals and mid-caps more than the DAX."},
                                                   {"name": "Prolonged weakness", "text": "Pressure on domestic sectors; ECB easing may cushion the index."}], link="economies/de"))

    # 6 Oil -> India
    ev, con = [], []
    if oil is not None:
        ev.append(f"WTI 1-year change {fmt(p('CL=F')['y1'], 1, '%')} ({p('CL=F')['date']}).")
    fi = wbv("TM.VAL.FUEL.ZS.UN", "IND")
    if fi:
        ev.append(f"Fuel was {fi['value']:.0f}% of India's merchandise imports in {fi['year']} (World Bank).")
    tb = wbv("NE.RSB.GNFS.CD", "IND")
    if tb:
        ev.append(f"India's trade balance in goods and services: US${tb['value'] / 1e9:,.0f}bn in {tb['year']} (World Bank).")
    tr = (trade or {}).get("countries", {}).get("in", {}).get("imports_products")
    if tr:
        ev.append(f"Energy (HS 27) was {tr['groups'].get('Energy (HS 27)')}% of India's goods imports in {tr['year']} (UN Comtrade).")
    tbs, infl = wbs("NE.RSB.GNFS.CD", "IND"), imf.get("PCPIPCH", {}).get("IND")
    if oil is not None and tbs is not None:
        oa = annual_change(oil)
        dd = pd.concat([oa, tbs.diff() / 1e9], axis=1).dropna()
        if len(dd) >= 5:
            cc = round(float(dd.iloc[:, 0].corr(dd.iloc[:, 1])), 2)
            (ev if cc < 0 else con).append(f"Correlation of oil's annual average price change with the annual change in India's trade balance: {cc:+.2f} over {len(dd)} years.")
    if infl:
        ev.append(f"India CPI inflation {infl['latest']['value']:.1f}% in {infl['latest']['year']} ({infl['latest']['kind']}).")
    reports.append(dict(key="oil-india", title="How do higher oil prices affect India's trade deficit and inflation?",
        development="A sustained rise in crude oil prices.", mechanism=["India imports most of the crude oil it consumes, so higher prices raise the import bill directly.",
            "A wider trade deficit puts pressure on the rupee, which raises the rupee cost of all imports.", "Fuel and transport costs pass through to consumer prices; the government may absorb part through taxes and subsidies."],
        countries=["India", "Oil exporters (Gulf states, Russia)"], industries=["Refining", "Airlines", "Logistics", "Fertilisers", "Paints and chemicals"],
        assets=["Indian rupee", "Nifty 50", "Indian government bonds", "Oil"],
        precedents=[{"period": "2022", "text": "Higher oil prices widened India's trade deficit and pushed CPI inflation above the RBI's 6% upper tolerance band for most of the year."},
                    {"period": "2014–2016", "text": "Falling oil prices narrowed the deficit and helped bring inflation down."}],
        evidence=ev, contradicting=con, scenarios=[{"name": "Oil rises 20%", "text": "Wider deficit, rupee pressure and higher inflation risk."},
                                                   {"name": "Oil falls", "text": "Improves the external balance and gives the RBI room to ease."}], link="economies/in"))

    # 7 US deficit -> issuance and yields
    ev, con = [], []
    fb, debt = imf.get("GGXCNL_NGDP", {}).get("USA"), imf.get("GGXWDG_NGDP", {}).get("USA")
    if fb:
        ev.append(f"US general government balance {fb['latest']['value']:+.1f}% of GDP in {fb['latest']['year']} ({fb['latest']['kind']}).")
        proj = [(y, v) for y, v, k in zip(fb["series"]["years"], fb["series"]["values"], fb["series"]["kinds"]) if k == "IMF projection"][:3]
        if proj:
            ev.append("IMF projections: " + ", ".join(f"{y} {v:+.1f}%" for y, v in proj) + ".")
    if debt:
        ev.append(f"US gross government debt {debt['latest']['value']:.0f}% of GDP in {debt['latest']['year']} ({debt['latest']['kind']}).")
    t10 = px.get("^TNX")
    if t10 is not None:
        pt = D.perf(t10)
        ev.append(f"US 10y Treasury yield {pt['last']:.2f}% ({pt['date']}).")
    con.append("Treasury issuance and auction data (TreasuryDirect, Fiscal Data API) are not yet connected; yields also depend on Fed policy and inflation.")
    reports.append(dict(key="us-deficit", title="How does a growing US fiscal deficit affect Treasury issuance and bond yields?",
        development="A wider US federal deficit.", mechanism=["The Treasury finances the deficit by issuing more bills, notes and bonds.",
            "More supply needs buyers; if demand does not keep pace, investors demand a higher term premium.", "Higher yields raise interest costs, which widens the deficit further."],
        countries=["United States", "Large foreign holders: Japan, China, United Kingdom"], industries=["Banks", "Housing", "Highly indebted companies"],
        assets=["US Treasuries", "US dollar", "Gold", "Equity valuations"],
        precedents=[{"period": "2023", "text": "Heavier issuance after the debt-ceiling deal and Fitch's downgrade of the US (August) coincided with the 10-year yield touching about 5% in October."}],
        evidence=ev, contradicting=con, scenarios=[{"name": "Deficits widen with strong growth", "text": "Term premium and yields rise."},
                                                   {"name": "Recession", "text": "Deficits widen but yields fall as the Fed cuts and investors seek safety."}], link="fiscal/comparison"))

    # 8 FDI -> currency and equities
    ev, con = [], []
    rows = []
    for x in G.COUNTRIES:
        fdi = wbv("BX.KLT.DINV.CD.WD", x["iso3"])
        gdp = wbv("NY.GDP.MKTP.CD", x["iso3"])
        if fdi and gdp and fdi["year"] == gdp["year"]:
            rows.append(f"{x['name']} {fdi['value'] / gdp['value'] * 100:+.1f}% of GDP ({fdi['year']})")
    if rows:
        ev.append("FDI net inflows: " + "; ".join(rows) + " (World Bank).")
    con.append("Bilateral investment positions (IMF CDIS/CPIS) and monthly portfolio flows are not yet connected, so flow-to-price links cannot be tested here.")
    reports.append(dict(key="fdi-currency", title="How does foreign investment affect a country's currency and stock market?",
        development="Large inflows (or outflows) of foreign direct or portfolio investment.",
        mechanism=["Foreign investors must buy the local currency, which supports it while inflows last.", "Portfolio inflows raise demand for local equities and bonds directly.",
                   "Direct investment is slower and stickier; portfolio flows reverse quickly in risk-off periods."],
        countries=["Emerging markets with current account deficits (India)", "Financial centres (United Kingdom, Switzerland)"], industries=["Banks", "Real estate", "Export manufacturing"],
        assets=["Local currencies", "Local equity indices", "Local government bonds"],
        precedents=[{"period": "1997–1998", "text": "A sudden reversal of foreign capital caused currency collapses and equity sell-offs in Thailand, Indonesia and South Korea."},
                    {"period": "2013", "text": "In the taper tantrum, portfolio outflows hit India and Indonesia; their currencies fell sharply."}],
        evidence=ev, contradicting=con, scenarios=[{"name": "Risk-on inflows", "text": "Currency and equity support for recipients."},
                                                   {"name": "Sudden stop", "text": "Currency weakness and equity sell-off, most severe where deficits are funded by portfolio flows."}], link="flows/overview"))
    for r in reports:
        r["class"] = "AI interpretation (mechanism, precedents, scenarios) with computed evidence (numbers)"
    return reports


# ----------------------------------------------------------------- build
REFRESH_DAYS = {"wb": 7, "imf": 7, "trade": 30, "companies": 7, "eer": 7}


def _age_days(prev, sec):
    d = (prev or {}).get("fetched", {}).get(sec)
    return None if not d else (pd.Timestamp(NOW.date()) - pd.Timestamp(d)).days


def build(store, offline=False, extra=None, calendar=None, prev_path=None) -> dict:
    c = Collector(store, offline)
    t0 = time.time()
    prev = {}
    if prev_path and os.path.exists(prev_path):
        try:
            prev = json.load(open(prev_path))
        except Exception:
            prev = {}
    fetched, carried = dict(prev.get("fetched", {})), {}

    def section(name, fetch, empty, prev_val):
        """Fetch a section if due; otherwise, or on failure, carry forward the previous good copy."""
        age = _age_days(prev, name)
        due = offline is False and (age is None or age >= REFRESH_DAYS.get(name, 0) or not prev_val)
        if not due and prev_val:
            return prev_val
        val = fetch() if not offline else empty
        ok = bool(val) and (not isinstance(val, tuple) or bool(val[0]))
        if ok:
            fetched[name] = NOW.strftime("%Y-%m-%d")
            if isinstance(val, dict) and isinstance(prev_val, dict):  # fill keys that failed today
                miss = [k for k in prev_val if k not in val]
                if miss:
                    carried[name] = {"keys": miss, "from": prev.get("fetched", {}).get(name)}
                    val = {**{k: prev_val[k] for k in miss}, **val}
            return val
        if prev_val:
            carried[name] = {"keys": "all", "from": prev.get("fetched", {}).get(name)}
            return prev_val
        return val

    c.stage("start markets")
    px = collect_markets(c)
    c.stage("start bis")
    rates, eer = collect_bis(c) if not offline else ({}, {})
    if not rates and prev.get("rates"):
        rates, carried["rates"] = prev["rates"], {"keys": "all", "from": prev.get("fetched", {}).get("rates")}
    elif rates:
        fetched["rates"] = NOW.strftime("%Y-%m-%d")
    if not eer and prev.get("eer"):
        eer, carried["eer"] = prev["eer"], {"keys": "all", "from": prev.get("fetched", {}).get("eer")}
    elif eer:
        fetched["eer"] = NOW.strftime("%Y-%m-%d")
    c.stage("start worldbank")
    wb_pair = section("wb", lambda: collect_wb(c), ({}, {}), (prev.get("wb"), prev.get("meta", {}).get("worldbank", {}).get("published")) if prev.get("wb") else None)
    if isinstance(wb_pair, tuple):
        wb, wb_pub = wb_pair
        wb_pub = wb_pub if isinstance(wb_pub, dict) else {"_": wb_pub}
    else:
        wb, wb_pub = wb_pair or {}, {}
    if isinstance(wb, dict) and prev.get("wb") and "wb" not in carried:
        miss = [k for k in prev["wb"] if k not in wb]
        if miss:  # some indicators failed today: keep yesterday's copy of those
            carried["wb"] = {"keys": miss, "from": prev.get("fetched", {}).get("wb")}
            wb = {**{k: prev["wb"][k] for k in miss}, **wb}
    c.stage("start imf")
    imf = section("imf", lambda: imf_block(collect_imf(c)), {}, prev.get("imf"))
    imf_df = None
    if imf:
        rows = [(i, y, v, code) for code, d in imf.items() for i, x in d.items() for y, v in zip(x["series"]["years"], x["series"]["values"])]
        imf_df = pd.DataFrame(rows, columns=["iso3", "year", "value", "code"]) if rows else None
    c.stage("start comtrade")
    trade = section("trade", lambda: collect_trade(c), {}, prev.get("trade"))
    c.stage("start sec")
    companies = section("companies", lambda: collect_companies(c), [], prev.get("companies"))
    local = os.path.join(os.path.dirname(prev_path or "."), "companies.json")
    if not companies and os.path.exists(local):
        try:
            loc = json.load(open(local))
            companies = loc.get("companies", [])
            carried["companies"] = {"keys": "all", "from": loc.get("fetched"), "via": "local refresh (python -m finintel.companies)"}
        except Exception:
            pass
    cftc = {}
    for ccy, code in G.CFTC_FX.items():
        df = c.try_(f"cftc:{ccy}", lambda: D.cftc_fx(code)) if not offline else None
        if df is not None and not df.empty:
            cftc[ccy] = {"date": df.index[-1].strftime("%Y-%m-%d"), "lev_net": int(df.lev.iloc[-1]), "am_net": int(df.am.iloc[-1]),
                         "lev_4w": int(df.lev.iloc[-1] - df.lev.iloc[-5]) if len(df) > 4 else None,
                         "series": D.ser(df.lev, 160, 0)}
    if not cftc and prev.get("cftc_fx"):
        cftc, carried["cftc_fx"] = prev["cftc_fx"], {"keys": "all", "from": prev.get("fetched", {}).get("cftc_fx")}
    elif cftc:
        fetched["cftc_fx"] = NOW.strftime("%Y-%m-%d")
    fredd = {}
    if not offline:
        for k, sid in list(G.FRED_YIELDS.items()) + [(k, v[1]) for k, v in G.FRED_CREDIT.items()]:
            s = c.try_(f"fred:{sid}", lambda: fred(sid))
            if s is not None:
                c.keep(f"fred:{sid}", s)
                fredd[k] = {"series": D.ser(s, 400, 3), "latest": {"value": float(s.iloc[-1]), "date": s.index[-1].strftime("%Y-%m-%d")}}

    markets = {"indices": [], "commodities": [], "proxies": [], "yields": []}
    for k, n, t, region, ck, ccy in G.INDICES:
        s = px.get(t)
        markets["indices"].append({"key": k, "name": n, "ticker": t, "region": region, "country": ck, "ccy": ccy,
                                   "perf": D.perf(s) if s is not None else None, "series": D.ser(s, 520, 2) if s is not None else None,
                                   "annual": [{"year": int(y.year), "ret": round(float(v), 2)} for y, v in (s.resample("YE").last().pct_change().dropna() * 100).items()] if s is not None else []})
    for k, n, t, unit, grp in G.COMMODITIES:
        s = px.get(t) if t else None
        markets["commodities"].append({"key": k, "name": n, "ticker": t, "unit": unit, "group": grp,
                                       "perf": D.perf(s) if s is not None else None, "series": D.ser(s, 520, 3) if s is not None else None})
    for k, n, t in G.PROXIES:
        s = px.get(t)
        markets["proxies"].append({"key": k, "name": n, "ticker": t, "perf": D.perf(s) if s is not None else None})
    for k, n, t in G.US_YIELDS:
        s = px.get(t)
        markets["yields"].append({"key": k, "name": n, "ticker": t, "perf": D.perf(s) if s is not None else None, "series": D.ser(s, 520, 3) if s is not None else None})

    fx = currency_block(px, rates, imf_df, wb, eer, cftc) if px else {}
    matrix = asset_matrix(px) if px else {}
    reports = rel_reports(px, wb, imf, rates, trade, extra or {})

    # global what changed
    movers = sorted([(i["name"], i["perf"]["d1"]) for i in markets["indices"] if i["perf"] and i["perf"]["d1"] is not None], key=lambda x: -abs(x[1]))[:5]
    cm = sorted([(i["name"], i["perf"]["d1"]) for i in markets["commodities"] if i["perf"] and i["perf"]["d1"] is not None], key=lambda x: -abs(x[1]))[:5]
    rate_moves = [f"{next((x['cb'] for x in G.COUNTRIES if x['bis'] == a), a)}: {v['last_move']['size']:+.2f} pp in {v['last_move']['date']}"
                  for a, v in rates.items() if v.get("last_move") and v["last_move"]["date"] >= (NOW - pd.Timedelta(days=62)).strftime("%Y-%m")]
    ranking = sorted([s for s in fx.get("strength", []) if s.get("rank")], key=lambda s: s["rank"])
    changed = {"index_movers": movers, "commodity_movers": cm, "rate_moves": rate_moves,
               "strongest_ccy": ranking[0]["ccy"] if ranking else None, "weakest_ccy": ranking[-1]["ccy"] if ranking else None,
               "new_data": [s for s in c.saved if s.startswith(("wb:", "imf:", "bis:"))][:0]}

    revisions = store_revisions(store)
    coverage = coverage_summary(markets, fx, wb, imf, rates, trade, companies, c.errors)
    meta = {
        "yahoo": D.meta("Yahoo Finance", "Exchange and futures prices (delayed)", "https://finance.yahoo.com/", freq="Daily", kind="Actual", confidence="Medium",
                        note="Free delayed data; futures are front-month continuous contracts. Index levels in local currency."),
        "worldbank": D.meta("World Bank", "World Development Indicators", "https://data.worldbank.org/", published=max([v for v in wb_pub.values() if isinstance(v, str)] or [None]) if wb_pub else None,
                            freq="Annual", kind="Actual", confidence="High", note="Annual; latest year is often 1–2 years old."),
        "imf": D.meta("IMF", "World Economic Outlook (DataMapper)", "https://www.imf.org/external/datamapper/", freq="Annual (semi-annual editions)",
                      kind="Actual, estimate and projection", confidence="High", note="Years from the current year onward are IMF projections and are labelled as such."),
        "bis": D.meta("Bank for International Settlements", "Central bank policy rates (WS_CBPOL); effective exchange rates (WS_EER)", "https://data.bis.org/",
                      freq="Monthly", kind="Actual", confidence="High"),
        "comtrade": D.meta("United Nations", "UN Comtrade (public preview API)", "https://comtradeplus.un.org/", freq="Annual", kind="Actual (as reported)", confidence="High",
                           note="Reported by each country; Russia has not reported since 2021. Mirror data is not yet used."),
        "sec": D.meta("US SEC", "EDGAR XBRL company facts", "https://www.sec.gov/edgar/sec-api-documentation", freq="Annual (10-K)", kind="Actual (as filed)", confidence="High"),
        "cftc": D.meta("CFTC", "Traders in Financial Futures", "https://publicreporting.cftc.gov/", freq="Weekly", kind="Actual", confidence="High"),
        "fred": D.meta("Federal Reserve Bank of St. Louis", "FRED (OECD long-term rates, ICE BofA spreads)", "https://fred.stlouisfed.org/", freq="Daily / monthly", kind="Actual", confidence="High",
                       note="Requires FRED_API_KEY."),
    }
    print(f"[global] built in {time.time() - t0:.0f}s; {len(c.errors)} source errors")
    return {"generated_at": NOW.strftime("%Y-%m-%d %H:%M UTC"), "year": YEAR, "countries": G.COUNTRIES, "markets": markets, "fx": fx, "matrix": matrix,
            "rates": rates, "eer": eer, "wb": wb, "wb_labels": {k: v[0] for k, v in G.WB.items()}, "wb_units": {k: v[1] for k, v in G.WB.items()},
            "imf": imf, "imf_labels": {k: v[0] for k, v in G.IMF.items()}, "trade": trade, "companies": companies,
            "company_sources": G.CORPORATE_SOURCES, "fred": fredd, "cftc_fx": cftc, "reports": reports, "changed": changed,
            "meta": meta, "coverage": coverage, "revisions": revisions, "errors": c.errors,
            "fetched": fetched, "carried": carried, "refresh_days": REFRESH_DAYS}


def store_revisions(store) -> dict:
    try:
        rows = store.db.execute("SELECT substr(series_id,1,instr(series_id,':')-1) AS src, COUNT(*) FROM (SELECT series_id, value_date, COUNT(*) n "
                                "FROM observation GROUP BY series_id, value_date HAVING n > 1) GROUP BY src").fetchall()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


def coverage_summary(markets, fx, wb, imf, rates, trade, companies, errors) -> dict:
    idx = markets["indices"]
    com = markets["commodities"]
    wb_cells = sum(len(v) for v in wb.values())
    return {
        "indices": {"covered": sum(1 for i in idx if i["perf"]), "target": len(idx)},
        "commodities": {"priced": sum(1 for i in com if i["perf"]), "target": len(com)},
        "currencies": {"covered": len([s for s in fx.get("strength", []) if s.get("absolute")]), "target": 9},
        "policy_rates": {"covered": len(rates), "target": len({x["bis"] for x in G.COUNTRIES})},
        "worldbank": {"indicators": len(wb), "target": len(G.WB), "country_cells": wb_cells},
        "imf": {"indicators": len(imf), "target": len(G.IMF)},
        "trade": {"reporters": sum(1 for v in (trade.get("countries") or {}).values() if v.get("exports")), "target": len(G.COUNTRIES)},
        "companies": {"records": len(companies), "target_per_country": 500, "countries_with_data": 1 if companies else 0, "countries": len(G.COUNTRIES)},
        "errors": len(errors),
    }
