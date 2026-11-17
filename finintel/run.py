"""Run the engine: collect -> store -> score -> levels -> outlook -> dashboard.

    python -m finintel.run                 # writes output/dashboard.html and output/results.json
    python -m finintel.run --out my.html
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .config import ASSET_NAMES, DRIVERS
from .connectors import SeriesLoader
from .levels import key_levels
from .report import render
from .scorecard import HORIZONS, changes, contradictions, read_driver, score
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
HORIZON_LABEL = {"long": "Long term (1–12 months)", "medium": "Medium term (1–4 weeks)", "short": "Short term (1–5 days)"}


def reading_text(r) -> str:
    if r.value is None:
        return "n/a" if r.raw_value is None else f"{r.raw_value:,.2f} latest"
    pct = f" (percentile {r.percentile:.0f})" if r.percentile is not None else ""
    return f"{r.raw_value:,.2f} latest; {r.value:+,.2f} after transform{pct}"


def rule_based_outlook(asset: str, hz: str, sc, readings, levels) -> dict:
    """Deterministic summary. Phase 3 replaces this with the AI layer (spec section 6)."""
    live = [r for r in readings if r.signal is not None]
    w = {r.key: r.weight * r.horizons[hz] for r in live}
    ranked = sorted(live, key=lambda r: -abs(r.signal * w[r.key]))
    side = 1 if (sc.composite or 0) >= 0 else -1
    sup = [f"{r.name} ({r.signal:+.1f})" for r in ranked if r.signal * side > 0.25][:4]
    con = [f"{r.name} ({r.signal:+.1f})" for r in ranked if r.signal * side < -0.25][:4]
    top = ", ".join(r.name.split(",")[0] for r in ranked[:3]) or "no drivers"
    s1 = levels["support"][0]["price"] if levels["support"] else None
    r1 = levels["resistance"][0]["price"] if levels["resistance"] else None
    inval, conf = [], []
    if side > 0:
        if s1: inval.append(f"Daily close below support {s1:,.0f}")
        if r1: conf.append(f"Close above resistance {r1:,.0f}")
    else:
        if r1: inval.append(f"Daily close above resistance {r1:,.0f}")
        if s1: conf.append(f"Close below support {s1:,.0f}")
    inval.append("Composite crosses zero or agreement falls below 60%")
    return dict(horizon=HORIZON_LABEL[hz], stance=sc.stance, evidence_class="Model output (rule-based)",
                thesis=f"Composite {sc.composite:+.2f} with {sc.agreement:.0%} of active weight agreeing. "
                       f"Largest contributors: {top}." if sc.composite is not None else "Not enough data.",
                supports=sup, contradicts=con, invalidation=inval, confirmation=conf)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "output" / "dashboard.html"))
    ap.add_argument("--manual", default=str(ROOT / "manual_inputs"))
    ap.add_argument("--db", default=str(ROOT / "output" / "finintel.sqlite"))
    args = ap.parse_args(argv)
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)

    loader = SeriesLoader(Path(args.manual))
    store = Store(Path(args.db))
    now = datetime.now(timezone.utc)
    assets, as_of = [], []

    for sym, drivers in DRIVERS.items():
        readings = []
        for d in drivers:
            raw = loader.load(d["series"])
            if raw is not None:
                store.save_series(d["series"], raw)
            readings.append(read_driver(d, raw, loader.errors.get(d["series"])))
        try:
            px = loader.price(sym)
        except Exception as e:
            print(f"[{sym}] price feed failed: {e}")
            continue
        store.save_series(f"price:{sym}", px.close)
        levels = key_levels(px)
        scores = {hz: score(readings, hz) for hz in HORIZONS}
        price_date = px.index.max().strftime("%Y-%m-%d"); as_of.append(price_date)
        for hz in HORIZONS:
            if scores[hz].composite is not None:
                store.log_outlook(sym, hz, price_date, scores[hz].stance, scores[hz].composite,
                                  scores[hz].agreement, float(px.close.iloc[-1]))
        drivers_out = []
        for r in readings:
            dd = r.to_dict(); dd["reading"] = reading_text(r); drivers_out.append(dd)
        hist = px.close.tail(365)
        assets.append(dict(
            symbol=sym, name=ASSET_NAMES[sym], price=float(px.close.iloc[-1]), price_date=price_date,
            price_source="Binance PAXG/USDT (gold proxy)" if sym == "XAU" else "Binance BTC/USDT",
            price_note="Gold is tracked through PAXG, a token backed 1:1 by a London Good Delivery ounce; it can differ from spot by a small premium." if sym == "XAU" else "",
            history=[[d.strftime("%Y-%m-%d"), round(float(v), 2)] for d, v in hist.items()],
            history_label="last 12 months, daily close",
            scores={hz: vars(scores[hz]) for hz in HORIZONS},
            drivers=drivers_out,
            missing=[f"{r.name}: {r.note}" for r in readings if r.signal is None],
            contradictions=contradictions(readings, scores["medium"].composite),
            changes=changes(readings),
            levels=levels,
            outlooks=[rule_based_outlook(sym, hz, scores[hz], readings, levels) for hz in ("long", "medium", "short")],
        ))
        print(f"[{sym}] " + " | ".join(f"{hz}: {scores[hz].stance} ({scores[hz].composite})" for hz in HORIZONS))

    scored = store.score_due({a["symbol"]: loader.prices[a["symbol"]].close for a in assets if a["symbol"] in loader.prices})
    results = dict(
        title="Global Financial Intelligence Terminal", mode="live",
        as_of=max(as_of) if as_of else now.strftime("%Y-%m-%d"),
        generated_at=now.strftime("%Y-%m-%d %H:%M UTC"),
        assets=assets, feed_errors=loader.errors, outlooks_scored_this_run=scored,
        report_card=store.report_card().to_dict("records"),
        disclaimer="Research tool for personal use; not investment advice.",
        sources=[],
    )
    out.with_suffix(".json").write_text(json.dumps(results, indent=1, default=str))
    render(results, out)
    if loader.errors:
        print("Feeds that failed (drivers left out):")
        for k, v in loader.errors.items():
            print(f"  {k}: {v[:160]}")
    print(f"Dashboard written to {out}")


if __name__ == "__main__":
    main()
