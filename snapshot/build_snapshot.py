"""Builds the hand-researched snapshot dashboard (17 Nov 2026) with the engine's own scoring and renderer.

Readings were looked up on the web on 17 Nov 2026; each carries its source. Because a snapshot has
no multi-year history, the -2..+2 signals here were ASSIGNED BY CLAUDE from the readings (evidence
class: AI interpretation of the reading). The live engine computes them from 3-year z-scores instead.
Composite scores, agreement and stances are computed by finintel.scorecard exactly as in a live run.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from finintel.config import ASSET_NAMES, DRIVERS  # noqa: E402
from finintel.report import render  # noqa: E402
from finintel.scorecard import HORIZONS, DriverReading, contradictions, score  # noqa: E402

S = {  # sources
    "tips": ("247 Wall St, 10 Nov 2026 (FRED DFII10)", "https://247wallst.com/investing/2026/11/10/treasuries-now-offer-2-66-above-inflation-are-dividend-stocks-in-trouble/"),
    "dxy": ("FXStreet, 11 Nov 2026", "https://www.fxstreet.com/analysis/why-the-us-dollars-rally-isnt-as-strong-as-it-looks-202611111707"),
    "fed": ("BabyPips, 13 Nov 2026 (CME FedWatch)", "https://www.babypips.com/analysis/headline-gold-takes-hit-yields-rise-2026-11-13"),
    "geo": ("Khaleej Times / Reuters, 12 Nov 2026", "https://www.khaleejtimes.com/business/gold-drops-3-to-over-one-year-low-as-fading-middle-east-peace-hopes-fan-inflation-fears"),
    "gdt": ("World Gold Council, Gold Demand Trends Q3 2026", "https://www.gold.org/download/file/21338/Executive-summary.pdf"),
    "gdt_inv": ("World Gold Council, GDT Q3 2026: Investment", "https://www.gold.org/goldhub/research/gold-demand-trends/gold-demand-trends-q3-2026/investment"),
    "etf": ("FXStreet / Money Metals, 8 Nov 2026 (WGC data)", "https://www.fxstreet.com/analysis/etf-gold-flows-slow-in-october-but-remain-positive-202611082140"),
    "cot": ("Bullion Trading LLC, COT analysis (CFTC, 3 Nov 2026)", "https://bulliontradingllc.com/blog/gold-cot-report-hedge-fund-positioning/"),
    "gold_px": ("ISA Bullion daily report, 13 Nov 2026", "https://www.isabullion.com/?p=9193"),
    "gold_low": ("The Nation (Reuters/LSEG), 13 Nov 2026", "https://www.nationthailand.com/business/trading-investment/40073439"),
    "gold_range": ("USAGOLD, live gold price page", "https://www.usagold.com/federal-reserve-gold-prices"),
    "btc_etf": ("The Block (SoSoValue data), 7 Nov 2026", "https://theblock.co/news/markets/2026-11-07-bitcoin-etfs-flip-negative-for-2026-after-1-28-billion-outflow-week-worst-since-june-435984"),
    "btc_etf2": ("investingLive, 13 Nov 2026", "https://investinglive.com/cryptocurrency/bitcoin-dipped-under-70k-first-time-since-august/"),
    "reserves": ("CryptoQuant QuickTake (early Nov 2026)", "https://cryptoquant.com/insights/quicktake/6af0bfa898fe666a74dfc673"),
    "deriv": ("Glassnode, BTC Market Pulse week 45", "https://research.glassnode.com/btc-market-pulse-week-45/"),
    "hash": ("Hashrate Index roundup, 9 Nov 2026", "https://hashrateindex.com/blog/hashrate-index-roundup-november-9-2026/"),
    "corp": ("CryptoSlate via Coinalyze news feed, 10 Nov 2026", "https://coinalyze.net/bitcoin/usdc/deribit/btc_usdc-14nov26/price-chart-live/"),
    "etf_vs_supply": ("CoinStats weekly ETF report, 2–6 Nov 2026", "https://coinstats.app/news/59499a339fec6491ef38a0580daa5efe5d41056cf080b85ce327ea18bed0c4af_Spot-Bitcoin-ETFs-Weekly-Report-128B-in-Outflows-November-26-2026/"),
    "btc_px": ("Fortune daily Bitcoin price, 12 Nov 2026", "https://fortune.com/article/price-of-bitcoin-11-12-2026/"),
    "btc_70k": ("The Motley Fool, 13 Nov 2026", "https://www.fool.com/investing/2026/11/13/why-bitcoin-is-falling-today/"),
    "btc_200": ("NewsBTC via Coinalyze news feed, 12 Nov 2026", "https://coinalyze.net/bitcoin/usdc/deribit/btc_usdc-16nov26/price-chart-live/"),
}

# key -> (signal, reading, as_of, source key, evidence class shown, note)
GOLD = {
    "real_yield": (-1.5, "2.66% on 9 Nov, up from 1.84% a year earlier; near an 18-year high (2.92% on 2 Oct)", "2026-11-09", "tips", "Fact", ""),
    "usd": (-1.5, "DXY near 103, an 18-month high; up 3.4 points from the August low", "2026-11-06", "dxy", "Fact", ""),
    "policy": (-2.0, "Fed funds 3.75–4.00% after a September hike; a December hike fully priced, ~13% odds of 50 bp", "2026-11-13", "fed", "Fact", ""),
    "gpr": (0.5, "US–Iran talks stalled; Middle East risk is lifting oil but feeding inflation fears more than safe-haven buying", "2026-11-12", "geo", "AI interpretation", ""),
    "cb": (2.0, "321 t bought in Q3 2026, +42% y/y and the most since Q4 2024; 675 t year to date", "2026-11-03", "gdt", "Estimate", ""),
    "etf": (1.0, "+19 t in October ($2.7bn); holdings at a record 4,275 t; North American funds saw outflows", "2026-10-31", "etf", "Fact", ""),
    "cot": (0.5, "Managed money net long 103,614 contracts, 26% of open interest; not extreme, and falling", "2026-11-03", "cot", "Fact", ""),
    "asia": (0.0, "India bar and coin 55 t in Q3, −40% y/y; PBoC bought for an 8th straight quarter", "2026-11-03", "gdt_inv", "Estimate", ""),
    "trend": (-2.0, "$3,876 close on 12 Nov, the lowest since Oct 2025; about 31% below the 2026 high of $5,599", "2026-11-12", "gold_px", "Fact", ""),
}
BTC = {
    "liquidity": (-1.5, "No direct liquidity reading collected; proxy: Fed hiking and the 10y Treasury yield back above 5%", "2026-11-13", "fed", "AI interpretation", "Proxy until the live FRED net-liquidity feed runs"),
    "usd": (-1.5, "DXY near 103, an 18-month high", "2026-11-06", "dxy", "Fact", ""),
    "etf": (-2.0, "−$1.28bn in the week of 2–6 Nov; November outflows near $2bn by 13 Nov; 2026 net flows now negative", "2026-11-13", "btc_etf", "Fact", ""),
    "reserves": (-1.5, "2.83M BTC on exchanges, 98th percentile of the past year", "2026-11-05", "reserves", "Estimate", ""),
    "mvrv": (0.5, "MVRV 1.40 and NUPL 0.29: holders still in modest profit, far from overvalued", "2026-11-05", "reserves", "Estimate", ""),
    "funding": (-0.5, "Funding softened; futures CVD −$790m, showing renewed sell pressure", "2026-11-09", "deriv", "Estimate", ""),
    "miner_rev": (-1.0, "Hashprice $31.89/PH/day on 9 Nov, 11% below its 30-day average; hashrate −7.8% in the week", "2026-11-09", "hash", "Estimate", ""),
    "corporate": (0.5, "Strategy funded further BTC purchases with stock sales, 2–8 Nov (filing 9 Nov)", "2026-11-09", "corp", "Fact", ""),
    "trend": (-2.0, "Lost the 200-day average on 12 Nov; below $70,000 on 13 Nov for the first time since August", "2026-11-13", "btc_70k", "Fact", ""),
}


NAMES = {  # snapshot readings are levels/events, not the engine's exact transforms
    "real_yield": "US 10y real yield (TIPS)", "usd": "US dollar (DXY)", "policy": "Fed policy path",
    "gpr": "Geopolitical risk", "cb": "Central bank net purchases", "etf": "ETF flows and holdings",
    "cot": "CFTC managed money positioning", "asia": "Asian physical demand", "trend": "Price trend and structure",
    "liquidity": "Global liquidity / Fed policy", "reserves": "Exchange reserves", "mvrv": "MVRV ratio",
    "funding": "Derivatives: funding and futures flow", "miner_rev": "Miner revenue (hashprice) and hashrate",
    "corporate": "Corporate / treasury buying",
}


def readings(sym, table):
    out = []
    for d in DRIVERS[sym]:
        r = DriverReading(key=d["key"], name=d["name"], layer=d["layer"], weight=d["weight"], horizons=d["horizons"],
                          bullish_when=d["bullish_when"], evidence_class=d["evidence_class"],
                          source_name=d["source"][0], source_url=d["source"][1])
        if d["key"] in table:
            sig, reading, as_of, src, ev, note = table[d["key"]]
            r.signal, r.as_of, r.evidence_class, r.note = sig, as_of, ev, note
            r.source_name, r.source_url = S[src]
            r.reading = reading
            r.name = NAMES.get(d["key"], r.name)
        else:
            r.status, r.note, r.reading = "missing", "no reading looked up for this snapshot", ""
        out.append(r)
    return out


def asset(sym, table, extra):
    rs = readings(sym, table)
    scores = {hz: vars(score(rs, hz)) for hz in HORIZONS}
    drivers = []
    for r in rs:
        dd = r.to_dict(); dd["reading"] = getattr(r, "reading", ""); drivers.append(dd)
    return dict(symbol=sym, name=ASSET_NAMES[sym], scores=scores, drivers=drivers,
                missing=[f"{r.name}" for r in rs if r.signal is None],
                contradictions=extra.pop("contradictions_extra") + contradictions(rs, scores["medium"]["composite"]),
                **extra), scores


gold_extra = dict(
    price=3876.0, price_date="12 Nov 2026 close (OTC)", price_source="ISA Bullion daily report",
    price_change="−2.8% on 12 Nov; third straight weekly loss; 2026 range $3,853 to $5,599",
    history=[["2026-10-29", 4021], ["2026-10-30", 3875], ["2026-11-02", 3948], ["2026-11-03", 3928], ["2026-11-04", 4060],
             ["2026-11-05", 4087], ["2026-11-06", 4066], ["2026-11-09", 4139], ["2026-11-10", 4031], ["2026-11-11", 3987],
             ["2026-11-12", 3876]],
    history_label="last 2 weeks, daily OTC close",
    price_note="Closes from ISA Bullion's daily reports (each report gives the previous session's close).",
    levels=dict(resistance=[{"price": 4000, "label": "Round number; 12 Nov session high"},
                            {"price": 4148, "label": "9–10 Nov session highs"}],
                support=[{"price": 3852, "label": "12 Nov low, lowest since 3 Oct 2025 (Reuters/LSEG)"},
                         {"price": 3800, "label": "ISA Bullion support level (3 Nov report)"}],
                sma200=None, high_52w=5598.58, low_52w=3852.53,
                note="Snapshot levels come from the cited reports; the live engine computes swing levels and the 200-day average from price history."),
    contradictions_extra=["Gold is falling while central banks buy at the fastest pace since 2024 and ETF holdings sit at a record: "
                          "official and investor demand is being outweighed by rate-hike expectations and the strong dollar."],
    changes=["WGC Q3 data (3 Nov): central bank buying 321 t, +42% y/y.",
             "October CPI hotter than expected (10 Nov): a December Fed hike is now fully priced.",
             "Price broke below $3,900 on 12 Nov to the lowest level since October 2025."],
    outlooks=[
        dict(horizon="Long term (1–12 months)", stance="", evidence_class="AI interpretation",
             thesis="Structural demand is strong: central banks bought 321 t in Q3 and ETF holdings are at a record. "
                    "Against it, real yields near 18-year highs and a hiking Fed raise the cost of holding gold. "
                    "The long-term case rests on central bank buying continuing while the hiking cycle ends.",
             supports=["Central bank buying 321 t in Q3, +42% y/y", "Record ETF holdings, 4,275 t", "Positioning not crowded (26% of open interest)"],
             contradicts=["10y real yield 2.66%", "Fed hiking; December hike priced", "Dollar at an 18-month high"],
             invalidation=["Q4 central bank buying falls below 150 t", "Global ETF holdings fall for 2 straight months"],
             confirmation=["Fed signals the end of hikes in 2027 guidance", "Real yields fall back below 2.3%"]),
        dict(horizon="Medium term (1–4 weeks)", stance="", evidence_class="AI interpretation",
             thesis="Rates and the dollar dominate into the 8–9 December FOMC. With a hike already priced, the risk is a "
                    "hawkish message on 2027. Price structure is weak: a third weekly loss and a one-year low.",
             supports=["ETF inflows still positive in October"],
             contradicts=["December hike fully priced", "Price at a one-year low", "Dollar strength"],
             invalidation=["Weekly close back above $4,150", "US data soft enough to price out the December hike"],
             confirmation=["Weekly close below $3,850", "FOMC guides to further hikes in 2027"]),
        dict(horizon="Short term (1–5 days)", stance="", evidence_class="AI interpretation",
             thesis="Momentum is down after a 2.8% drop to $3,876. The $3,852 low is the first test; $4,000 is the "
                    "first resistance. US data that moves December hike odds will drive daily moves.",
             supports=["Close to the $3,852 one-year low, where buyers stepped in on 12 Nov"],
             contradicts=["Three straight down sessions; rejection near $4,000"],
             invalidation=["Daily close above $4,000"], confirmation=["Daily close below $3,852"]),
    ],
)

btc_extra = dict(
    price=73208.24, price_date="12 Nov 2026, 6:30 am ET", price_source="Fortune daily price",
    price_change="Fell below $70,000 on 13 Nov; −28% vs a year earlier; sixth weekly decline",
    history=[["2026-11-02", 77750.64], ["2026-11-03", 76995.40], ["2026-11-04", 78520.27], ["2026-11-05", 80221.40],
             ["2026-11-06", 76023.87], ["2026-11-08", 75818.94], ["2026-11-09", 74549.48], ["2026-11-10", 74260.59],
             ["2026-11-11", 73937.78], ["2026-11-12", 73208.24]],
    history_label="last 2 weeks, morning ET price",
    price_note="Fortune's daily morning price; the intraday break below $70,000 on 13 Nov is not in this series.",
    levels=dict(resistance=[{"price": 76000, "label": "6 Nov breakdown level (ETF outflow day)"},
                            {"price": 81000, "label": "Post-midterm rally high that failed to hold"}],
                support=[{"price": 70000, "label": "Round number; broken intraday on 13 Nov"}],
                sma200=None, high_52w=None, low_52w=None,
                note="Snapshot levels come from the cited reports; the live engine computes swing levels and the 200-day average from price history."),
    contradictions_extra=["On-chain valuation is not stretched (MVRV 1.40) and corporate buyers are still adding, "
                          "but ETF selling of about 5x weekly new supply is overwhelming that demand."],
    changes=["Spot ETFs: worst outflow week since June (−$1.28bn, 2–6 Nov); 2026 net flows turned negative.",
             "Price lost the 200-day average (12 Nov) and $70,000 (13 Nov).",
             "December Fed hike fully priced after the October CPI report."],
    outlooks=[
        dict(horizon="Long term (1–12 months)", stance="", evidence_class="AI interpretation",
             thesis="Tightening liquidity is the main headwind: the Fed is hiking and the dollar is strong. Valuation is "
                    "moderate rather than stretched, which limits downside from forced revaluation, but no driver yet "
                    "points to a turn in flows.",
             supports=["MVRV 1.40, not overvalued", "Corporate treasuries still buying"],
             contradicts=["Fed hiking, 10y yield above 5%", "ETF flows negative for 2026", "Exchange reserves at a 1-year high"],
             invalidation=["Two straight weeks of ETF inflows above $1bn", "Fed signals a pause"],
             confirmation=["MVRV falls below 1.2 while ETF outflows continue"]),
        dict(horizon="Medium term (1–4 weeks)", stance="", evidence_class="AI interpretation",
             thesis="Flows decide this horizon, and they are negative: about $2bn left spot ETFs in the first half of "
                    "November. Miner revenue is falling, which raises the risk of miner selling.",
             supports=[], contradicts=["ETF outflows", "Rising exchange reserves", "Hashprice down 11% vs its 30-day average"],
             invalidation=["Weekly close back above $76,000", "ETF flows positive for a full week"],
             confirmation=["Weekly close below $70,000"]),
        dict(horizon="Short term (1–5 days)", stance="", evidence_class="AI interpretation",
             thesis="Price is testing $70,000 after losing the 200-day average. Leveraged long liquidations on 13 Nov "
                    "may have cleared some selling, but funding and futures flow still lean negative.",
             supports=["Liquidations may have reset leverage"], contradicts=["Futures CVD −$790m", "Below the 200-day average"],
             invalidation=["Daily close above $76,000"], confirmation=["Daily close below $70,000"]),
    ],
)

ga, gs = asset("XAU", GOLD, gold_extra)
ba, bs = asset("BTC", BTC, btc_extra)
for a, sc in ((ga, gs), (ba, bs)):
    for o, hz in zip(a["outlooks"], ("long", "medium", "short")):
        o["stance"] = sc[hz]["stance"]

srcs = {v for v in S.values()}
results = dict(
    title="Financial Intelligence Terminal: snapshot 17 Nov 2026", mode="snapshot",
    as_of="readings to 13 Nov 2026 (looked up 17 Nov 2026)", generated_at="17 Nov 2026",
    assets=[ga, ba], sources=[{"title": t, "url": u} for t, u in sorted(srcs)],
    disclaimer="Snapshot signals were assigned by Claude from the cited readings; composites, agreement and stances "
               "are computed by the engine's scorecard. Research tool for personal use; not investment advice.",
)
out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("snapshot_dashboard.html")
render(results, out)
for a in results["assets"]:
    print(a["symbol"], {h: (a["scores"][h]["stance"], a["scores"][h]["composite"], a["scores"][h]["agreement"], a["scores"][h]["coverage"]) for h in HORIZONS})
print("written", out)
