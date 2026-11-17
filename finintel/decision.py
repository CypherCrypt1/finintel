"""Decision intelligence: -100..+100 scores, confidence, data quality, what changed, alerts."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .scorecard import HORIZONS, score as horizon_score

# share of each component in the combined score, per horizon
BLEND = {"short": {"macro": 0.25, "fundamental": 0.25, "technical": 0.50},
         "medium": {"macro": 0.35, "fundamental": 0.35, "technical": 0.30},
         "long": {"macro": 0.40, "fundamental": 0.45, "technical": 0.15}}
MACRO_LAYERS, FUND_LAYERS = {1}, {2, 3, 4}

# expected maximum age (days) before a reading counts as stale
MAX_AGE = {"price": 4, "binance": 4, "cm": 4, "mempool": 4, "calc": 4, "fred": 7, "cftc": 12, "manual": 10}
MANUAL_AGE = {"manual:cb_purchases": 130, "manual:gold_etf_tonnes": 40, "manual:aisc": 130, "manual:asia_demand": 60,
              "manual:gpr": 40}


def label(v: float | None) -> str:
    if v is None:
        return "No data"
    if v >= 60:
        return "Strong bullish"
    if v >= 20:
        return "Moderately bullish"
    if v > -20:
        return "Neutral"
    if v > -60:
        return "Moderately bearish"
    return "Strong bearish"


def component(readings, layers, hz):
    sub = [r for r in readings if r.layer in layers]
    sc = horizon_score(sub, hz)
    return (None if sc.composite is None else round(sc.composite * 50)), sc


def scores(readings, tech: dict) -> dict:
    out = {}
    for hz in HORIZONS:
        macro, msc = component(readings, MACRO_LAYERS, hz)
        fund, fsc = component(readings, FUND_LAYERS, hz)
        td, tw = tech["daily"]["score"], tech["weekly"]["score"]
        techv = {"short": td, "medium": round((td + tw) / 2), "long": tw}[hz]
        parts = {"macro": macro, "fundamental": fund, "technical": techv}
        w = {k: BLEND[hz][k] for k, v in parts.items() if v is not None}
        comb = round(sum(parts[k] * w[k] for k in w) / sum(w.values())) if w else None
        allsc = horizon_score(readings, hz)
        vals = [v for v in parts.values() if v is not None]
        disagreement = (max(vals) > 20 and min(vals) < -20) if len(vals) > 1 else False
        conf = confidence(allsc.coverage, allsc.agreement, disagreement)
        out[hz] = {"macro": macro, "fundamental": fund, "technical": techv, "combined": comb,
                   "label": label(comb), "contested": bool((allsc.agreement or 1) < 0.6 or disagreement),
                   "agreement": allsc.agreement, "coverage": allsc.coverage,
                   "components_disagree": disagreement, "confidence": conf}
    return out


def confidence(coverage, agreement, disagreement) -> dict:
    cov = coverage or 0
    agr = agreement if agreement is not None else 0.5
    v = 100 * (0.6 * cov + 0.4 * agr) - (15 if disagreement else 0)
    v = int(max(0, min(100, round(v))))
    lab = "High" if v >= 70 else "Medium" if v >= 45 else "Low"
    if cov < 0.6 and lab == "High":
        lab = "Medium"  # never High while less than 60% of the evidence has data
    why = [f"{cov:.0%} of driver weight has data", f"{agr:.0%} of active weight agrees with the composite"]
    if disagreement:
        why.append("macro, fundamental and technical scores point in different directions")
    return {"value": v, "label": lab, "why": why}


def data_quality(drivers: list[dict], series_ids: dict[str, str], today: pd.Timestamp) -> dict:
    rows, fresh, total_w = [], 0.0, 0.0
    for d in drivers:
        sid = series_ids[d["key"]]
        kind = sid.split(":")[0]
        limit = MANUAL_AGE.get(sid, MAX_AGE.get(kind, 7))
        total_w += d["weight"]
        if d["as_of"] is None or d["signal"] is None:
            status, age = ("Missing" if d["as_of"] is None else "Insufficient history"), None
        else:
            age = int((today - pd.Timestamp(d["as_of"])).days)
            status = "Fresh" if age <= limit else "Stale"
            if status == "Fresh":
                fresh += d["weight"]
        rows.append({"driver": d["name"], "series": sid, "status": status, "age_days": age, "max_age": limit,
                     "as_of": d["as_of"], "evidence_class": d["evidence_class"], "source": d["source_name"]})
    q = round(100 * fresh / total_w) if total_w else 0
    return {"score": q, "label": "Good" if q >= 75 else "Fair" if q >= 50 else "Poor", "rows": rows}


def what_changed(asset: dict, prev: dict | None, calendar: list[dict], today: str) -> dict:
    drivers = asset["drivers"]
    improving, deteriorating, new_data = [], [], []
    prev_drv = {d["key"]: d for d in (prev or {}).get("drivers", [])}
    basis = "previous run" if prev else "7 days earlier"
    for d in drivers:
        if d["signal"] is None:
            continue
        before = prev_drv.get(d["key"], {}).get("signal") if prev else d.get("signal_prev")
        if before is not None and abs(d["signal"] - before) >= 0.3:
            item = {"driver": d["name"], "from": round(before, 2), "to": round(d["signal"], 2)}
            (improving if d["signal"] > before else deteriorating).append(item)
        if prev and d["as_of"] and d["as_of"] != prev_drv.get(d["key"], {}).get("as_of"):
            new_data.append(f"{d['name']}: new reading dated {d['as_of']}")
    model = []
    if prev:
        for hz in HORIZONS:
            a, b = prev["decision"][hz], asset["decision"][hz]
            if a["label"] != b["label"]:
                model.append(f"{hz.title()} term outlook changed from {a['label']} to {b['label']} ({a['combined']:+} to {b['combined']:+}).")
            elif a["combined"] is not None and b["combined"] is not None and abs(b["combined"] - a["combined"]) >= 10:
                model.append(f"{hz.title()} term combined score moved {a['combined']:+} to {b['combined']:+}.")
    # level breaks since the previous run
    developments = []
    p_now = asset["performance"]["last"]
    if prev:
        p_prev = prev["performance"]["last"]
        for s in prev["levels"].get("support", []):
            if p_prev >= s["price"] > p_now:
                developments.append(f"Price broke below support {s['price']:,.0f}.")
        for s in prev["levels"].get("resistance", []):
            if p_prev <= s["price"] < p_now:
                developments.append(f"Price broke above resistance {s['price']:,.0f}.")
    perf = asset["performance"]
    if perf.get("d1") is not None and abs(perf["d1"]) >= 2:
        developments.append(f"Price moved {perf['d1']:+.1f}% on the day.")
    developments += new_data[:4]
    # sentiment: technical vs previous
    sentiment = []
    t_now = asset["technicals"]["daily"]["score"]
    if prev:
        t_prev = prev["technicals"]["daily"]["score"]
        if abs(t_now - t_prev) >= 10:
            sentiment.append(f"Technical score {t_prev:+.0f} to {t_now:+.0f}.")
    # three things to monitor
    monitor = []
    lv = asset["levels"]
    atr = asset["technicals"]["daily"].get("atr") or 0
    near = sorted([(abs(p_now - x["price"]), x, k) for k in ("support", "resistance") for x in lv.get(k, [])],
                  key=lambda t: t[0])
    if near:
        dist, x, k = near[0]
        monitor.append(f"{'Support' if k == 'support' else 'Resistance'} at {x['price']:,.0f}, "
                       f"{dist / p_now * 100:.1f}% away" + (f" ({dist / atr:.1f} average daily ranges)" if atr else "") + ".")
    comb = asset["decision"]["medium"]["combined"] or 0
    against = sorted([d for d in drivers if d["signal"] is not None and np.sign(d["signal"]) == -np.sign(comb or 1)],
                     key=lambda d: -abs(d["signal"] * d["weight"]))
    if against:
        d = against[0]
        monitor.append(f"{d['name']} ({d['signal']:+.1f}) is the strongest driver against the medium-term view.")
    upcoming = [e for e in calendar if e.get("date", "") >= today]
    if upcoming:
        e = sorted(upcoming, key=lambda e: e["date"])[0]
        monitor.append(f"{e['event']} on {e['date']}: {e.get('why', '')}".strip())
    imp7, det7 = [], []
    for d in drivers:
        if d["signal"] is not None and d.get("signal_prev") is not None and abs(d["signal"] - d["signal_prev"]) >= 0.3:
            item = {"driver": d["name"], "from": round(d["signal_prev"], 2), "to": round(d["signal"], 2)}
            (imp7 if d["signal"] > d["signal_prev"] else det7).append(item)
    return {"basis": basis, "developments": developments, "improving": improving, "deteriorating": deteriorating,
            "improving_7d": imp7, "deteriorating_7d": det7,
            "sentiment": sentiment, "model": model, "monitor": monitor[:3]}


def alerts(asset: dict, prev: dict | None, feed_errors: dict) -> list[dict]:
    out = []
    sym = asset["symbol"]
    for d in asset["drivers"]:
        if d["signal"] is not None and abs(d["signal"]) >= 1.5:
            out.append({"severity": "High", "asset": sym, "text": f"{d['name']} at an extreme reading ({d['signal']:+.1f})."})
    for hz in HORIZONS:
        dc = asset["decision"][hz]
        if dc["confidence"]["label"] == "Low":
            out.append({"severity": "Info", "asset": sym, "text": f"{hz.title()} term confidence is low ({dc['confidence']['value']})."})
        if prev and prev["decision"][hz]["label"] != dc["label"]:
            out.append({"severity": "High", "asset": sym,
                        "text": f"{hz.title()} term outlook changed: {prev['decision'][hz]['label']} to {dc['label']}."})
    p = asset["performance"]["last"]
    for k in ("support", "resistance"):
        for x in asset["levels"].get(k, [])[:1]:
            if abs(p / x["price"] - 1) < 0.01:
                out.append({"severity": "Medium", "asset": sym, "text": f"Price within 1% of {k} {x['price']:,.0f}."})
    return out
