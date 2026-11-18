"""SOVEREIGN daily run: collect -> store -> score -> technicals -> quant -> decision -> site.

    python -m finintel.run                       # live run, writes site/ (open site/index.html via a local server)
    python -m finintel.run --offline             # rebuild from the stored database, no network
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import decision, quant, technicals
from .config import ASSET_NAMES, DRIVERS
from .connectors import ConnectorError, SeriesLoader
from .levels import key_levels
from .scorecard import HORIZONS, changes, contradictions, read_driver, score
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
HZ_LABEL = {"long": "Long term (1–12 months)", "medium": "Medium term (1–4 weeks)", "short": "Short term (1–5 days)"}
MACRO_SERIES = {  # id -> (label, unit)
    "fred:DFII10": ("US 10y real yield (TIPS)", "%"), "fred:DGS2": ("US 2y Treasury yield", "%"),
    "fred:DGS10": ("US 10y Treasury yield", "%"), "fred:DTWEXBGS": ("Broad US dollar index", "index"),
    "fred:NETLIQ": ("US net liquidity (Fed assets − RRP − TGA)", "$bn"),
    "fred:CPIAUCSL": ("US CPI, all items (index)", "index"), "fred:PCEPILFE": ("US core PCE price index", "index"),
    "fred:UNRATE": ("US unemployment rate", "%"), "fred:PAYEMS": ("US nonfarm payrolls", "thousands"),
    "fred:ICSA": ("US initial jobless claims", "claims"), "fred:A191RL1Q225SBEA": ("US real GDP growth (annualised q/q)", "%"),
    "fred:GFDEGDQ188S": ("US federal debt to GDP", "%"), "fred:T10Y2Y": ("US 10y minus 2y yield spread", "pp"),
}


class OfflineLoader(SeriesLoader):
    """Serves every series from the point-in-time database (used for development and rebuilds)."""

    def __init__(self, manual_folder: Path, store: Store):
        super().__init__(manual_folder)
        self.store = store
        self.when = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _db(self, sid):
        s = self.store.as_known_on(sid, self.when)
        if s.empty:
            raise ConnectorError(f"{sid} not in database")
        return s

    def price(self, asset):
        if asset not in self.prices:
            c = self._db(f"price:{asset}")
            df = pd.DataFrame({"close": c})
            for col in ("open", "high", "low", "volume"):
                try:
                    df[col] = self._db(f"price:{asset}:{col}")
                except ConnectorError:
                    df[col] = c if col != "volume" else 0.0
            self.prices[asset] = df.dropna(subset=["close"])
        return self.prices[asset]

    def load(self, sid):
        if sid in self.cache:
            return self.cache[sid]
        if sid in self.errors:
            return None
        try:
            if sid.startswith("manual:"):
                return super().load(sid)
            s = self.price(sid.split(":")[1])["close"] if sid.startswith("price:") else self._db(sid)
        except Exception as e:
            self.errors[sid] = f"{type(e).__name__}: {e}"
            return None
        self.cache[sid] = s
        return s


def ser(s: pd.Series | None, n: int = 800, step: int = 1, nd: int = 4) -> dict:
    if s is None or s.dropna().empty:
        return {"dates": [], "values": []}
    s = s.dropna().sort_index().tail(n)[::step]
    return {"dates": [d.strftime("%Y-%m-%d") for d in s.index], "values": [round(float(v), nd) for v in s]}


def ohlc(px: pd.DataFrame, n: int = 1100) -> list:
    d = px.tail(n)
    return [[i.strftime("%Y-%m-%d"), round(float(r.open), 2), round(float(r.high), 2), round(float(r.low), 2),
             round(float(r.close), 2), round(float(r.volume), 2)] for i, r in d.iterrows()]


def latest_change(s: pd.Series | None) -> dict | None:
    if s is None or s.dropna().empty:
        return None
    s = s.dropna().sort_index()
    last, t = float(s.iloc[-1]), s.index[-1]

    def back(days):
        p = s[s.index <= t - pd.Timedelta(days=days)]
        return None if p.empty else round(last - float(p.iloc[-1]), 3)

    return {"last": round(last, 3), "date": t.strftime("%Y-%m-%d"), "chg_1w": back(7), "chg_1m": back(30), "chg_3m": back(91)}


def outlook_text(asset_sym, hz, dec, readings, levels):
    live = [r for r in readings if r.signal is not None]
    side = 1 if (dec["combined"] or 0) >= 0 else -1
    ranked = sorted(live, key=lambda r: -abs(r.signal * r.weight * r.horizons[hz]))
    sup = [f"{r.name} ({r.signal:+.1f})" for r in ranked if r.signal * side > 0.25][:4]
    con = [f"{r.name} ({r.signal:+.1f})" for r in ranked if r.signal * side < -0.25][:4]
    s1 = levels["support"][0]["price"] if levels["support"] else None
    r1 = levels["resistance"][0]["price"] if levels["resistance"] else None
    horizon_word = {"short": "daily", "medium": "weekly", "long": "weekly"}[hz]
    inval, conf = [], []
    if side > 0:
        if s1: inval.append(f"A {horizon_word} close below support {s1:,.0f}")
        if r1: conf.append(f"A {horizon_word} close above resistance {r1:,.0f}")
    else:
        if r1: inval.append(f"A {horizon_word} close above resistance {r1:,.0f}")
        if s1: conf.append(f"A {horizon_word} close below support {s1:,.0f}")
    inval.append("Combined score crosses zero, or driver agreement falls below 60%")
    top = ", ".join(r.name.split(",")[0].split("(")[0].strip() for r in ranked[:3]) or "no drivers"
    parts = f"macro {dec['macro']:+}" if dec["macro"] is not None else "macro n/a"
    parts += f", fundamental {dec['fundamental']:+}" if dec["fundamental"] is not None else ", fundamental n/a"
    parts += f", technical {dec['technical']:+}"
    thesis = (f"Combined score {dec['combined']:+} ({dec['label'].lower()}); {parts}. Largest contributors: {top}."
              if dec["combined"] is not None else "Not enough data for this horizon.")
    if dec["contested"]:
        thesis += " The evidence is contested: drivers or components disagree, so treat the label with caution."
    return dict(horizon=HZ_LABEL[hz], key=hz, label=dec["label"], combined=dec["combined"], thesis=thesis,
                supports=sup, contradicts=con, invalidation=inval, confirmation=conf,
                evidence_class="Model output (rule-based)")


def scenarios(sym, dec, readings, levels, tech):
    """Bullish / base / bearish scenarios: conditions, not price targets or probabilities."""
    live = [r for r in readings if r.signal is not None]
    bear = sorted([r for r in live if r.signal < 0], key=lambda r: r.signal * r.weight)[:3]
    bull = sorted([r for r in live if r.signal > 0], key=lambda r: -r.signal * r.weight)[:3]
    weak = sorted([r for r in live if r.signal < 0], key=lambda r: r.signal * r.weight)[:3]
    s = [x["price"] for x in levels["support"]]
    r = [x["price"] for x in levels["resistance"]]
    ref = lambda lst, i: f"{lst[i]:,.0f}" if len(lst) > i else "n/a"
    return [
        {"name": "Bullish", "assumptions": [f"{x.name} turns supportive or strengthens" for x in weak[:2]] +
                                          [f"{x.name} stays supportive" for x in bull[:2]],
         "technical_path": f"Reclaims resistance {ref(r, 0)}, then {ref(r, 1)}; daily trend turns up",
         "watch": "Weekly close above the first resistance with improving macro score"},
        {"name": "Base", "assumptions": ["Current driver readings persist with no regime change",
                                         f"Combined medium-term score stays near {dec['medium']['combined']:+}"],
         "technical_path": f"Trades between support {ref(s, 0)} and resistance {ref(r, 0)}",
         "watch": "Agreement and confidence trend; next scheduled data releases"},
        {"name": "Bearish", "assumptions": [f"{x.name} deteriorates further" for x in bear[:2]] +
                                           [f"{x.name} loses support" for x in bull[:1]],
         "technical_path": f"Loses support {ref(s, 0)}, then {ref(s, 1)}",
         "watch": "Weekly close below the first support with worsening macro score"},
    ]


def append_history(path: Path, rows: list[dict]):
    new = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if new:
            w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=str(ROOT / "site"))
    ap.add_argument("--manual", default=str(ROOT / "manual_inputs"))
    ap.add_argument("--db", default=str(ROOT / "data" / "finintel.sqlite"))
    ap.add_argument("--offline", action="store_true", help="rebuild from the database without network access")
    ap.add_argument("--no-log", action="store_true", help="do not log outlooks or append score history")
    ap.add_argument("--no-global", action="store_true", help="skip the global modules (countries, FX, equities, trade, companies)")
    args = ap.parse_args(argv)
    site = Path(args.site)
    data_dir = Path(args.db).parent
    data_dir.mkdir(parents=True, exist_ok=True)
    store = Store(Path(args.db))
    loader = OfflineLoader(Path(args.manual), store) if args.offline else SeriesLoader(Path(args.manual))
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    ref_dir = ROOT / "reference"
    calendar = json.loads((ref_dir / "calendar.json").read_text()).get("events", []) if (ref_dir / "calendar.json").exists() else []
    prev_path = data_dir / "last_results.json"
    prev_all = json.loads(prev_path.read_text()) if prev_path.exists() else {}

    # macro series (shared by both assets and the macro pages)
    macro = {}
    for sid, (lab, unit) in MACRO_SERIES.items():
        s = loader.load(sid)
        if s is not None and not args.offline:
            store.save_series(sid, s)
        macro[sid.split(":")[1]] = {"label": lab, "unit": unit, "latest": latest_change(s),
                                    "series": ser(s, n=1100, step=1 if sid != "fred:NETLIQ" else 7, nd=3),
                                    "status": "ok" if s is not None else loader.errors.get(sid, "missing")}

    assets, hist_rows, all_feed = [], [], {}
    closes = {}
    for sym, drivers in DRIVERS.items():
        readings = []
        for d in drivers:
            raw = loader.load(d["series"])
            if raw is not None and not args.offline:
                store.save_series(d["series"], raw)
            readings.append(read_driver(d, raw, loader.errors.get(d["series"])))
        try:
            px = loader.price(sym)
        except Exception as e:
            print(f"[{sym}] price feed failed: {e}")
            continue
        if not args.offline:
            for col in ("close", "open", "high", "low", "volume"):
                store.save_series(f"price:{sym}" + ("" if col == "close" else f":{col}"), px[col])
        closes[sym] = px.close
        levels = key_levels(px)
        tech = technicals.analyse(px, levels)
        perf = quant.performance(px.close)
        drivers_out = []
        for r in readings:
            dd = r.to_dict()
            dd["reading"] = ("n/a" if r.raw_value is None else f"{r.raw_value:,.2f}") + \
                            ("" if r.value is None else f" (transformed {r.value:+,.2f}" +
                             ("" if r.percentile is None else f", percentile {r.percentile:.0f}") + ")")
            drivers_out.append(dd)
        dec = decision.scores(readings, tech)
        sid_map = {d["key"]: d["series"] for d in drivers}
        asset = dict(
            symbol=sym, name=ASSET_NAMES[sym], performance=perf, levels=levels, technicals=tech,
            price_source="Binance PAXG/USDT (1 token = 1 troy oz of London Good Delivery gold)" if sym == "XAU" else "Binance BTC/USDT",
            ohlc=ohlc(px), drivers=drivers_out, decision=dec,
            composite={hz: vars(score(readings, hz)) for hz in HORIZONS},
            contradictions=contradictions(readings, dec["medium"]["combined"] / 50 if dec["medium"]["combined"] is not None else None),
            weekly_changes=changes(readings),
            missing=[{"name": r.name, "note": r.note} for r in readings if r.signal is None],
            outlooks=[outlook_text(sym, hz, dec[hz], readings, levels) for hz in ("short", "medium", "long")],
            scenarios=scenarios(sym, dec, readings, levels, tech),
            data_quality=decision.data_quality(drivers_out, sid_map, pd.Timestamp(today)),
            volatility=quant.volatility(px.close, 365 if sym == "BTC" else 365),
            regime=quant.regimes(px.close), backtest=quant.backtest_trend(px.close),
            monthly_returns=quant.monthly_returns(px.close),
        )
        prev = prev_all.get(sym)
        asset["what_changed"] = decision.what_changed(asset, prev, calendar, today)
        asset["alerts"] = decision.alerts(asset, prev, loader.errors)
        # asset-specific chart series
        extra = {}
        for d in drivers:
            s = loader.cache.get(d["series"])
            if s is not None:
                extra[d["key"]] = ser(s, n=1100, step=1, nd=4)
        asset["series"] = extra
        assets.append(asset)
        for hz in HORIZONS:
            dc = dec[hz]
            if dc["combined"] is not None and not args.no_log:
                store.log_outlook(sym, hz, perf["date"], dc["label"], dc["combined"], dc["agreement"], perf["last"])
            hist_rows.append({"date": perf["date"], "asset": sym, "horizon": hz, "macro": dc["macro"],
                              "fundamental": dc["fundamental"], "technical": dc["technical"],
                              "combined": dc["combined"], "label": dc["label"], "price": round(perf["last"], 2)})
        print(f"[{sym}] " + " | ".join(f"{hz}: {dec[hz]['label']} ({dec[hz]['combined']})" for hz in HORIZONS))

    # quantitative research across assets and macro
    corr_input = {"Gold": closes.get("XAU"), "Bitcoin": closes.get("BTC"),
                  "Real yield": loader.cache.get("fred:DFII10"), "2y yield": loader.cache.get("fred:DGS2"),
                  "10y yield": loader.cache.get("fred:DGS10"), "Dollar": loader.cache.get("fred:DTWEXBGS"),
                  "Net liquidity": loader.cache.get("fred:NETLIQ")}
    kinds = {"Gold": "price", "Bitcoin": "price", "Dollar": "price", "Net liquidity": "price"}
    chg = quant.changes_frame(corr_input, kinds)
    quant_out = {
        "corr_90": quant.correlations(chg, 90), "corr_365": quant.correlations(chg, 250),
        "rolling": {"Gold vs Bitcoin": quant.rolling_corr(chg, "Gold", "Bitcoin"),
                    "Gold vs real yield": quant.rolling_corr(chg, "Gold", "Real yield"),
                    "Bitcoin vs real yield": quant.rolling_corr(chg, "Bitcoin", "Real yield")},
        "note": "Daily changes on weekdays: % returns for prices, point changes for yields.",
    }

    if not args.no_log:
        append_history(data_dir / "score_history.csv", hist_rows)
    scored = store.score_due({a["symbol"]: loader.prices[a["symbol"]].close for a in assets if a["symbol"] in loader.prices})
    hist = pd.read_csv(data_dir / "score_history.csv") if (data_dir / "score_history.csv").exists() else pd.DataFrame(hist_rows)
    hist = hist.drop_duplicates(subset=["date", "asset", "horizon"], keep="last").tail(3000)
    outlog = pd.read_sql("SELECT asset, horizon, as_of, stance, composite, price, resolve_on, realised_return, hit "
                         "FROM outlook ORDER BY id DESC LIMIT 400", store.db)

    results = dict(
        brand="SOVEREIGN", mode="offline rebuild" if args.offline else "live",
        as_of=max(a["performance"]["date"] for a in assets) if assets else today,
        generated_at=now.strftime("%Y-%m-%d %H:%M UTC"), assets=assets, macro=macro, quant=quant_out,
        score_history=hist.replace({np.nan: None}).to_dict("records"),
        forecast_log=outlog.replace({np.nan: None}).to_dict("records"),
        report_card=store.report_card().replace({np.nan: None}).to_dict("records"),
        outlooks_scored_this_run=scored,
        feed_errors={k: v[:220] for k, v in loader.errors.items()},
        drivers_config={k: [{kk: vv for kk, vv in d.items() if kk != "horizons"} | {"horizons": d["horizons"]} for d in v]
                        for k, v in DRIVERS.items()},
        blend=decision.BLEND,
    )
    # keep a slim copy for tomorrow's "what changed"
    slim = {a["symbol"]: {"drivers": [{"key": d["key"], "signal": d["signal"], "as_of": d["as_of"]} for d in a["drivers"]],
                          "decision": a["decision"], "performance": a["performance"], "levels": a["levels"],
                          "technicals": {"daily": {"score": a["technicals"]["daily"]["score"]}}} for a in assets}
    if not args.no_log:
        prev_path.write_text(json.dumps(slim, default=str))

    # assemble the static site
    site.mkdir(parents=True, exist_ok=True)
    web = ROOT / "web"
    if web.exists():
        shutil.copytree(web, site, dirs_exist_ok=True)
    if ref_dir.exists():
        shutil.copytree(ref_dir, site / "reference", dirs_exist_ok=True)
    (site / "data").mkdir(exist_ok=True)
    (site / "data" / "sovereign.json").write_text(json.dumps(results, default=str, separators=(",", ":")))
    # global modules (countries, equities, currencies, commodities, fiscal, trade, flows, companies, credit, relationships)
    gpath = data_dir / "global.json"
    if not args.no_global:
        if args.offline and gpath.exists():
            shutil.copy(gpath, site / "data" / "global.json")
            ovp = data_dir / "overlay.json"   # local development only
            if ovp.exists():
                shutil.copy(ovp, site / "data" / "overlay.json")
        else:
            from . import global_build
            g = global_build.build(store, offline=args.offline, extra={"DFII10": loader.cache.get("fred:DFII10")}, calendar=calendar,
                                   prev_path=str(gpath))
            txt = json.dumps(g, default=str, separators=(",", ":")).replace("NaN", "null")
            (site / "data" / "global.json").write_text(txt)
            if not args.offline:
                gpath.write_text(txt)
            # Overlay Lab: long histories. Yesterday's file is taken from the live site for carry-forward (not stored in git).
            try:
                from .overlay import build_overlay
                prev_ov = data_dir / "_overlay_prev.json"
                if not args.offline:
                    try:
                        import requests
                        r = requests.get("https://cyphercrypt1.github.io/finintel/data/overlay.json", timeout=60)
                        if r.ok:
                            prev_ov.write_text(r.text)
                    except Exception:
                        pass
                ov = build_overlay(global_build.LAST_PX, prev_path=str(prev_ov), offline=args.offline)
                (site / "data" / "overlay.json").write_text(json.dumps(ov, separators=(",", ":")).replace("NaN", "null"))
                prev_ov.unlink(missing_ok=True)
            except Exception as e:  # never let the overlay break the daily build
                print(f"[overlay] failed: {e}")
            if g["errors"]:
                print(f"Global source errors ({len(g['errors'])}):")
                for k, v in list(g["errors"].items())[:80]:
                    print(f"  {k}: {v[:160]}")
    if loader.errors:
        print("Feeds that failed (drivers left out):")
        for k, v in loader.errors.items():
            print(f"  {k}: {v[:160]}")
    print(f"Site written to {site}")


if __name__ == "__main__":
    main()
