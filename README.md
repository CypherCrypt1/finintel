# SOVEREIGN — Global Financial Intelligence

*Intelligence Without Influence.*

Live site: https://cyphercrypt1.github.io/finintel/

## Engine (gold and Bitcoin)

Phase 0 of the platform described in the specification. It collects free public data, scores
each driver from -2 (bearish) to +2 (bullish), combines them into composite scores for three
horizons, finds key price levels, logs every outlook for later scoring, and writes a
self-contained dashboard (`output/dashboard.html`).

## Run it

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m finintel.run                                 # writes site/ (serve it: python -m http.server -d site)
python -m finintel.run --offline                       # rebuild from data/finintel.sqlite without network
```

Open `output/dashboard.html` in a browser. Run it once a day (Task Scheduler or cron) to
build history: the point-in-time store and the forecast log grow with every run, and outlooks
are scored automatically when their horizon ends.

Tests run offline with synthetic data: `pip install pytest && python -m pytest -q tests`.

## What is live and what is manual

| Feed | Source | Key needed |
| --- | --- | --- |
| Real yields, broad dollar, 2y yield, Fed balance sheet, RRP, TGA | FRED public CSV | No |
| Gold price (PAXG/USDT proxy), BTC price, BTC funding | Binance public API (falls back to data-api.binance.vision) | No |
| Gold managed money, CME Bitcoin leveraged funds | CFTC Socrata API | No |
| MVRV | Coin Metrics Community API | No |
| Hashrate, hashprice proxy | mempool.space | No |
| Central bank buying, gold ETF tonnes, BTC ETF flows, GPR, exchange reserves, LTH supply, corporate buying, AISC, COMEX stocks, Asian imports | CSV files in `manual_inputs/` (see README there) | n/a |

A driver with no data is left out of the composite and listed under "Not collected"; the
horizon tiles show how much of the total weight had data ("coverage"). A z-score needs at
least 60 distinct observations, so manual series need some history before they count.

If a feed fails (site change, regional block), the run continues and prints which feeds
failed. Binance blocks some regions, including the US; from the UAE it should work.

## How a signal is computed

1. The raw series is transformed (level, change, % change, rolling sum, or % above the 200-day average).
2. Its latest value is compared with its own 3-year history: `z = (x - mean) / sd`.
3. `signal = clip(direction × z, -2, 2)`, where direction is +1 if higher is bullish.
4. `composite = Σ(weight × horizon multiplier × signal) / Σ(weights with data)`.
5. Agreement = share of active weight on the composite's side; below 60% the stance is **Contested**.

Weights and directions live in `finintel/config.py`. They are starting assumptions and should be
re-fitted after 6 to 12 months of logged outlooks (spec section 7).

## Files

- `finintel/config.py`: driver definitions and weights
- `finintel/connectors.py`: data loaders (one function per source)
- `finintel/scorecard.py`: transforms, z-scores, composites, contradictions
- `finintel/levels.py`: swing-point support and resistance, 200-day average, 52-week range
- `finintel/store.py`: SQLite point-in-time store and forecast log with scoring
- `finintel/report.py`: dashboard renderer
- `finintel/run.py`: the daily run
- `snapshot/build_snapshot.py`: the hand-researched 17 Nov 2026 snapshot, scored with the same code

## Not in v0 (next phases)

The AI research layer (Phase 3) replaces the rule-based outlook text. PostgreSQL and TimescaleDB
replace SQLite in Phase 1, and Telegram alerts come in Phase 3. Research tool for personal use;
not investment advice.

## Website (SOVEREIGN interface)

- `web/`: the static site (index.html, styles.css, app.js core, pages.js renderers); 88 pages across 10 sections.
- `reference/`: hand-entered, sourced data (calendar, central banks, WGC demand, ETF flows, geopolitics, briefings). Edit these JSON files to update those panels.
- `finintel/technicals.py`, `quant.py`, `decision.py`: technical indicators, correlations/regimes/backtests, and the −100..+100 scores with confidence and data quality.
- Each daily run writes `site/data/sovereign.json`; GitHub Actions publishes `site/` to GitHub Pages.

## Global modules (v0.3)

`finintel/global_build.py` builds `data/global.json` each day: 20 equity indices, 9 currencies, 19 commodities,
US yields and market proxies (Yahoo Finance); policy rates and effective exchange rates (BIS); 33 World Bank and
11 IMF WEO indicators (IMF via DBnomics when imf.org blocks the runner); goods trade by partner and product
(UN Comtrade); currency futures positioning (CFTC). Slow-changing sources refresh weekly or monthly, and a failed
source keeps its last good copy, labelled "carried forward" on the pages.

Company data: SEC blocks GitHub's servers. Run `python -m finintel.companies` on your own computer, then commit
and push `data/companies.json`.
