"""Driver definitions for the gold and Bitcoin scorecards.

Each driver turns one raw series into a signal from -2 (strongly bearish) to +2
(strongly bullish). Weights are the starting weights from the specification,
section 5; re-fit them once the forecast log has 6-12 months of history.

Fields
------
key            unique id
name           label shown on the dashboard
layer          intelligence layer 1-5 (spec section 3)
series         series id understood by connectors.load_series()
transform      "level" | "diff" | "pct" | "sum"   (applied over `window` days)
window         days for diff / pct / rolling sum (calendar days, daily-resampled)
direction      +1 if a HIGHER transformed value is bullish, -1 if bearish
weight         starting weight (fraction of 1)
horizons       multiplier per horizon: short (1-5 days), medium (1-4 weeks), long (1-12 months)
bullish_when   plain-language rule shown to the reader
evidence_class Fact | Estimate | Statistical relationship ...
source         (name, url) for the reader
"""

H_ALL = {"short": 1.0, "medium": 1.0, "long": 1.0}
H_SLOW = {"short": 0.3, "medium": 0.8, "long": 1.0}
H_FAST = {"short": 1.0, "medium": 0.8, "long": 0.3}
H_MID = {"short": 0.5, "medium": 1.0, "long": 0.7}

FRED = ("FRED, Federal Reserve Bank of St. Louis", "https://fred.stlouisfed.org/")
CFTC = ("CFTC Commitments of Traders", "https://publicreporting.cftc.gov/")
BINANCE = ("Binance public market data", "https://developers.binance.com/docs/binance-spot-api-docs")
COINMETRICS = ("Coin Metrics Community API", "https://docs.coinmetrics.io/api/v4/")
MEMPOOL = ("mempool.space API", "https://mempool.space/docs/api")
WGC = ("World Gold Council, Goldhub", "https://www.gold.org/goldhub/data")
MANUAL = ("Your manual input file", "")

DRIVERS = {
    "XAU": [
        dict(key="real_yield", name="US 10y real yield (TIPS), 3-month change", layer=1,
             series="fred:DFII10", transform="diff", window=91, direction=-1, weight=0.15,
             horizons=H_SLOW, bullish_when="Falling", evidence_class="Fact", source=FRED),
        dict(key="usd", name="Broad US dollar, 3-month % change", layer=1,
             series="fred:DTWEXBGS", transform="pct", window=91, direction=-1, weight=0.10,
             horizons=H_MID, bullish_when="Falling", evidence_class="Fact", source=FRED),
        dict(key="policy", name="Fed policy path (2y Treasury yield, 3-month change)", layer=1,
             series="fred:DGS2", transform="diff", window=91, direction=-1, weight=0.08,
             horizons=H_MID, bullish_when="More cuts priced (2y yield falling)", evidence_class="Fact", source=FRED),
        dict(key="gpr", name="Geopolitical Risk Index", layer=1,
             series="manual:gpr", transform="level", window=0, direction=+1, weight=0.05,
             horizons=H_FAST, bullish_when="Rising", evidence_class="Estimate",
             source=("Caldara & Iacoviello GPR index", "https://www.matteoiacoviello.com/gpr.htm")),
        dict(key="cb", name="Central bank net purchases, trailing 4 quarters (t)", layer=3,
             series="manual:cb_purchases", transform="sum", window=365, direction=+1, weight=0.15,
             horizons=H_SLOW, bullish_when="Rising", evidence_class="Estimate", source=WGC),
        dict(key="etf", name="Gold ETF holdings, 1-month change (t)", layer=4,
             series="manual:gold_etf_tonnes", transform="diff", window=30, direction=+1, weight=0.10,
             horizons=H_MID, bullish_when="Inflows", evidence_class="Fact", source=WGC),
        dict(key="cot", name="CFTC managed money net long, % of open interest", layer=4,
             series="cftc:gold_mm_pct_oi", transform="level", window=0, direction=-1, weight=0.08,
             horizons=H_MID, bullish_when="Low (room to buy); very high = crowded", evidence_class="Fact", source=CFTC),
        dict(key="miner_margin", name="Miner AISC margin vs spot", layer=3,
             series="manual:aisc", transform="level", window=0, direction=+1, weight=0.04,
             horizons=H_SLOW, bullish_when="Rising AISC lifts the long-run floor", evidence_class="Fact",
             source=("Company quarterly reports (SEC EDGAR)", "https://www.sec.gov/edgar/search/")),
        dict(key="asia", name="Asian physical demand (China/India imports)", layer=2,
             series="manual:asia_demand", transform="level", window=0, direction=+1, weight=0.07,
             horizons=H_MID, bullish_when="Rising", evidence_class="Fact", source=WGC),
        dict(key="comex", name="COMEX registered + eligible stocks, 1-month % change", layer=2,
             series="manual:comex_stocks", transform="pct", window=30, direction=-1, weight=0.05,
             horizons=H_FAST, bullish_when="Falling (physical tightness)", evidence_class="Fact",
             source=("CME Group warehouse stocks", "https://www.cmegroup.com/clearing/operations-and-deliveries/nymex-delivery-notices.html")),
        dict(key="trend", name="Price vs 200-day average (%)", layer=5,
             series="price:XAU", transform="vs_sma200", window=200, direction=+1, weight=0.10,
             horizons=H_FAST, bullish_when="Above the average", evidence_class="Fact",
             source=("COMEX gold futures, front month (Yahoo Finance GC=F)", "https://www.cmegroup.com/markets/metals/precious/gold.html")),
    ],
    "BTC": [
        dict(key="liquidity", name="US net liquidity (Fed assets - RRP - TGA), 3-month % change", layer=1,
             series="fred:NETLIQ", transform="pct", window=91, direction=+1, weight=0.15,
             horizons=H_SLOW, bullish_when="Expanding", evidence_class="Fact", source=FRED),
        dict(key="usd", name="Broad US dollar, 3-month % change", layer=1,
             series="fred:DTWEXBGS", transform="pct", window=91, direction=-1, weight=0.07,
             horizons=H_MID, bullish_when="Falling", evidence_class="Fact", source=FRED),
        dict(key="etf", name="Spot ETF net flows, 20-day sum ($m)", layer=4,
             series="manual:btc_etf_flows", transform="sum", window=28, direction=+1, weight=0.15,
             horizons=H_MID, bullish_when="Inflows", evidence_class="Fact",
             source=("Issuer websites / your flow file", "")),
        dict(key="reserves", name="Exchange reserves, 30-day % change", layer=4,
             series="manual:exchange_reserves", transform="pct", window=30, direction=-1, weight=0.08,
             horizons=H_MID, bullish_when="Falling", evidence_class="Estimate",
             source=("CryptoQuant / Glassnode (paid)", "https://cryptoquant.com/")),
        dict(key="lth", name="Long-term holder supply, 30-day % change", layer=4,
             series="manual:lth_supply", transform="pct", window=30, direction=+1, weight=0.07,
             horizons=H_SLOW, bullish_when="Rising", evidence_class="Estimate",
             source=("Glassnode (paid)", "https://glassnode.com/")),
        dict(key="mvrv", name="MVRV ratio", layer=4,
             series="cm:CapMVRVCur", transform="level", window=0, direction=-1, weight=0.08,
             horizons=H_SLOW, bullish_when="Low; very high = overvalued", evidence_class="Estimate", source=COINMETRICS),
        dict(key="funding", name="Perpetual funding rate, 7-day average (%)", layer=4,
             series="binance:funding", transform="level", window=0, direction=-1, weight=0.07,
             horizons=H_FAST, bullish_when="Neutral; high positive = crowded longs", evidence_class="Fact", source=BINANCE),
        dict(key="cme", name="CME leveraged funds net position, 4-week change", layer=4,
             series="cftc:btc_lev_net", transform="diff", window=28, direction=+1, weight=0.03,
             horizons=H_MID, bullish_when="Short covering", evidence_class="Fact", source=CFTC),
        dict(key="hashrate", name="Network hashrate, 3-month % change", layer=2,
             series="mempool:hashrate", transform="pct", window=91, direction=+1, weight=0.03,
             horizons=H_SLOW, bullish_when="Rising", evidence_class="Estimate", source=MEMPOOL),
        dict(key="corporate", name="Corporate / treasury net buying (BTC, 30 days)", layer=3,
             series="manual:corporate_btc", transform="sum", window=30, direction=+1, weight=0.07,
             horizons=H_SLOW, bullish_when="Net buying", evidence_class="Fact",
             source=("Company filings (SEC EDGAR 8-K)", "https://www.sec.gov/edgar/search/")),
        dict(key="trend", name="Price vs 200-day average (%)", layer=5,
             series="price:BTC", transform="vs_sma200", window=200, direction=+1, weight=0.10,
             horizons=H_FAST, bullish_when="Above the average", evidence_class="Fact", source=BINANCE),
    ],
}

ASSET_NAMES = {"XAU": "Gold (XAU/USD)", "BTC": "Bitcoin (BTC/USD)"}

# z-score look-back for normalisation (calendar days)
ZSCORE_LOOKBACK_DAYS = 3 * 365
# minimum history (observations of the transformed series) before a z-score is trusted
MIN_OBS = 60
# stance thresholds on the composite score
STANCE_BANDS = [(1.0, "Bullish"), (0.35, "Leaning bullish"), (-0.35, "Neutral"),
                (-1.0, "Leaning bearish"), (-99, "Bearish")]
CONTESTED_BELOW = 0.60  # agreement share below which the stance is "Contested"
