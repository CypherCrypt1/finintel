Manual input files: one CSV per series, two columns "date,value", one row per observation.
Lines starting with # are ignored. Delete the example rows and keep your own history;
a z-score needs at least 60 distinct observations, so add history going back 1-3 years.

File name                 What to put in "value"                          Where to get it
cb_purchases.csv          central bank net purchases for the quarter, t  WGC Gold Demand Trends (quarterly)
gold_etf_tonnes.csv       total global gold ETF holdings, tonnes          WGC Goldhub ETF data (monthly/daily)
btc_etf_flows.csv         US spot BTC ETF net flow for the day, $m       issuer sites / Farside / SoSoValue
gpr.csv                   Geopolitical Risk Index level                  matteoiacoviello.com/gpr.htm
exchange_reserves.csv     BTC held on exchanges                          CryptoQuant / Glassnode
lth_supply.csv            long-term holder supply, BTC                   Glassnode
corporate_btc.csv         net BTC bought by public companies that day    company 8-K filings
aisc.csv                  spot minus average AISC of major miners, $/oz  company quarterly reports
asia_demand.csv           China + India gold imports, tonnes             customs data / WGC
comex_stocks.csv          COMEX gold registered + eligible, oz           CME daily warehouse report
