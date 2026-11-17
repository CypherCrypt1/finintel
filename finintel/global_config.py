"""Coverage of the global modules: countries, indices, currencies, commodities, indicators, companies.

A ticker or code of None means no free source is wired yet: the page shows it as pending,
never as an invented number.
"""

COUNTRIES = [
    # key, name, iso3, iso2 (BIS), currency, comtrade M49 code, monetary authority
    dict(key="us", name="United States", iso3="USA", bis="US", ccy="USD", m49=842, cb="Federal Reserve"),
    dict(key="cn", name="China", iso3="CHN", bis="CN", ccy="CNY", m49=156, cb="People's Bank of China"),
    dict(key="jp", name="Japan", iso3="JPN", bis="JP", ccy="JPY", m49=392, cb="Bank of Japan"),
    dict(key="de", name="Germany", iso3="DEU", bis="XM", ccy="EUR", m49=276, cb="European Central Bank (euro area)"),
    dict(key="fr", name="France", iso3="FRA", bis="XM", ccy="EUR", m49=251, cb="European Central Bank (euro area)"),
    dict(key="in", name="India", iso3="IND", bis="IN", ccy="INR", m49=699, cb="Reserve Bank of India"),
    dict(key="gb", name="United Kingdom", iso3="GBR", bis="GB", ccy="GBP", m49=826, cb="Bank of England"),
    dict(key="ca", name="Canada", iso3="CAN", bis="CA", ccy="CAD", m49=124, cb="Bank of Canada"),
    dict(key="ch", name="Switzerland", iso3="CHE", bis="CH", ccy="CHF", m49=757, cb="Swiss National Bank"),
    dict(key="ru", name="Russia", iso3="RUS", bis="RU", ccy="RUB", m49=643, cb="Bank of Russia"),
]

# key, name, Yahoo ticker, region, country key, currency
INDICES = [
    ("spx", "S&P 500", "^GSPC", "Americas", "us", "USD"), ("ndx", "Nasdaq 100", "^NDX", "Americas", "us", "USD"),
    ("dji", "Dow Jones Industrial Average", "^DJI", "Americas", "us", "USD"), ("rut", "Russell 2000", "^RUT", "Americas", "us", "USD"),
    ("tsx", "S&P/TSX Composite", "^GSPTSE", "Americas", "ca", "CAD"), ("bvsp", "Bovespa", "^BVSP", "Americas", None, "BRL"),
    ("sxxp", "STOXX Europe 600", "^STOXX", "Europe", None, "EUR"), ("dax", "DAX 40", "^GDAXI", "Europe", "de", "EUR"),
    ("cac", "CAC 40", "^FCHI", "Europe", "fr", "EUR"), ("ftse", "FTSE 100", "^FTSE", "Europe", "gb", "GBP"),
    ("smi", "SMI", "^SSMI", "Europe", "ch", "CHF"), ("moex", "MOEX Russia", "IMOEX.ME", "Europe", "ru", "RUB"),
    ("n225", "Nikkei 225", "^N225", "Asia-Pacific", "jp", "JPY"), ("topix", "TOPIX (via TOPIX ETF 1306.T, proxy)", "1306.T", "Asia-Pacific", "jp", "JPY"),
    ("shcomp", "Shanghai Composite", "000001.SS", "Asia-Pacific", "cn", "CNY"), ("csi300", "CSI 300", "000300.SS", "Asia-Pacific", "cn", "CNY"),
    ("hsi", "Hang Seng", "^HSI", "Asia-Pacific", None, "HKD"), ("nifty", "Nifty 50", "^NSEI", "Asia-Pacific", "in", "INR"),
    ("sensex", "BSE Sensex", "^BSESN", "Asia-Pacific", "in", "INR"), ("kospi", "KOSPI", "^KS11", "Asia-Pacific", None, "KRW"),
]

# currency, Yahoo ticker, invert (True when the ticker quotes units of currency per USD)
FX = [("EUR", "EURUSD=X", False), ("GBP", "GBPUSD=X", False), ("JPY", "JPY=X", True), ("CNY", "CNY=X", True),
      ("INR", "INR=X", True), ("CAD", "CAD=X", True), ("CHF", "CHF=X", True), ("RUB", "RUB=X", True)]
DXY = "DX-Y.NYB"
CURRENCY_NAMES = {"USD": "US dollar", "EUR": "Euro", "CNY": "Chinese yuan", "JPY": "Japanese yen", "GBP": "British pound",
                  "INR": "Indian rupee", "CAD": "Canadian dollar", "CHF": "Swiss franc", "RUB": "Russian rouble"}
CCY_COUNTRY = {"USD": "us", "EUR": "de", "CNY": "cn", "JPY": "jp", "GBP": "gb", "INR": "in", "CAD": "ca", "CHF": "ch", "RUB": "ru"}
CFTC_FX = {"EUR": "099741", "JPY": "097741", "GBP": "096742", "CAD": "090741", "CHF": "092741"}

# key, name, Yahoo ticker (None = no free daily price), unit, group, top producers / consumers note key
COMMODITIES = [
    ("gold", "Gold", "GC=F", "$/oz", "Precious metals"), ("silver", "Silver", "SI=F", "$/oz", "Precious metals"),
    ("wti", "Crude oil (WTI)", "CL=F", "$/bbl", "Energy"), ("brent", "Crude oil (Brent)", "BZ=F", "$/bbl", "Energy"),
    ("natgas", "Natural gas (Henry Hub)", "NG=F", "$/MMBtu", "Energy"), ("coal", "Coal (Rotterdam)", "MTF=F", "$/t", "Energy"),
    ("uranium", "Uranium", None, "$/lb", "Energy"),
    ("copper", "Copper", "HG=F", "$/lb", "Industrial metals"), ("aluminium", "Aluminium", "ALI=F", "$/t", "Industrial metals"),
    ("ironore", "Iron ore", "TIO=F", "$/t", "Industrial metals"), ("steel", "Steel (US HRC)", "HRC=F", "$/short ton", "Industrial metals"),
    ("lithium", "Lithium", None, "$/t", "Battery metals"), ("nickel", "Nickel", None, "$/t", "Battery metals"), ("cobalt", "Cobalt", None, "$/t", "Battery metals"),
    ("wheat", "Wheat", "ZW=F", "¢/bu", "Agriculture"), ("corn", "Corn", "ZC=F", "¢/bu", "Agriculture"),
    ("soybeans", "Soybeans", "ZS=F", "¢/bu", "Agriculture"), ("coffee", "Coffee (Arabica)", "KC=F", "¢/lb", "Agriculture"),
    ("sugar", "Sugar No. 11", "SB=F", "¢/lb", "Agriculture"), ("cotton", "Cotton", "CT=F", "¢/lb", "Agriculture"),
]

# market proxies used by the relationship engine
PROXIES = [("acwi", "Global equities (ACWI ETF)", "ACWI"), ("eem", "Emerging markets (EEM ETF)", "EEM"),
           ("tlt", "Long US Treasuries (TLT ETF)", "TLT"), ("hyg", "US high yield bonds (HYG ETF)", "HYG"),
           ("lqd", "US investment grade bonds (LQD ETF)", "LQD"), ("dba", "Agriculture basket (DBA ETF)", "DBA"),
           ("dbb", "Base metals basket (DBB ETF)", "DBB"), ("btc", "Bitcoin", "BTC-USD")]
US_YIELDS = [("us3m", "US 13-week bill", "^IRX"), ("us5y", "US 5y Treasury", "^FVX"), ("us10y", "US 10y Treasury", "^TNX"), ("us30y", "US 30y Treasury", "^TYX")]
# FRED monthly long-term government bond yields (OECD MEI); need FRED_API_KEY
FRED_YIELDS = {"de": "IRLTLT01DEM156N", "fr": "IRLTLT01FRM156N", "gb": "IRLTLT01GBM156N", "jp": "IRLTLT01JPM156N",
               "ca": "IRLTLT01CAM156N", "ch": "IRLTLT01CHM156N", "in": "INDIRLTLT01STM", "us": "IRLTLT01USM156N"}
FRED_CREDIT = {"hy_oas": ("US high yield option-adjusted spread", "BAMLH0A0HYM2"),
               "ig_oas": ("US investment grade option-adjusted spread", "BAMLC0A0CM")}

# World Bank WDI indicators: code -> (label, unit, module)
WB = {
    "NY.GDP.MKTP.CD": ("GDP", "US$", "economy"), "NY.GDP.MKTP.KD.ZG": ("GDP growth", "%", "economy"),
    "NY.GDP.PCAP.CD": ("GDP per capita", "US$", "economy"), "NV.IND.TOTL.KD.ZG": ("Industry value added growth (industrial production proxy)", "%", "economy"),
    "FP.CPI.TOTL.ZG": ("CPI inflation", "%", "economy"), "SL.UEM.TOTL.ZS": ("Unemployment (ILO)", "%", "economy"),
    "NE.EXP.GNFS.CD": ("Exports of goods and services", "US$", "trade"), "NE.IMP.GNFS.CD": ("Imports of goods and services", "US$", "trade"),
    "NE.RSB.GNFS.CD": ("Trade balance (goods and services)", "US$", "trade"), "BN.CAB.XOKA.CD": ("Current account balance", "US$", "trade"),
    "TM.VAL.FUEL.ZS.UN": ("Fuel imports, % of merchandise imports", "%", "trade"), "TX.VAL.FUEL.ZS.UN": ("Fuel exports, % of merchandise exports", "%", "trade"),
    "TM.TAX.MRCH.WM.AR.ZS": ("Applied tariff rate, weighted mean", "%", "trade"),
    "FI.RES.TOTL.CD": ("Total reserves including gold", "US$", "reserves"), "FI.RES.XGLD.CD": ("Reserves excluding gold", "US$", "reserves"),
    "FM.LBL.BMNY.GD.ZS": ("Broad money, % of GDP", "%", "money"), "FM.LBL.BMNY.ZG": ("Broad money growth", "%", "money"),
    "BX.KLT.DINV.CD.WD": ("FDI, net inflows", "US$", "flows"), "BM.KLT.DINV.CD.WD": ("FDI, net outflows", "US$", "flows"),
    "BX.PEF.TOTL.CD.WD": ("Portfolio equity, net inflows", "US$", "flows"),
    "GC.REV.XGRT.GD.ZS": ("Revenue excluding grants, % of GDP", "%", "fiscal"), "GC.XPN.TOTL.GD.ZS": ("Expense, % of GDP", "%", "fiscal"),
    "GC.TAX.TOTL.GD.ZS": ("Tax revenue, % of GDP", "%", "fiscal"), "GC.XPN.INTP.RV.ZS": ("Interest payments, % of revenue", "%", "fiscal"),
    "GC.XPN.TRFT.ZS": ("Subsidies and transfers, % of expense", "%", "fiscal"), "MS.MIL.XPND.GD.ZS": ("Military expenditure, % of GDP", "%", "fiscal"),
    "FS.AST.PRVT.GD.ZS": ("Domestic credit to private sector, % of GDP", "%", "credit"), "FB.AST.NPER.ZS": ("Non-performing loans, % of gross loans", "%", "credit"),
    "FB.BNK.CAPA.ZS": ("Bank capital to assets", "%", "credit"), "FD.RES.LIQU.AS.ZS": ("Bank liquid reserves to assets", "%", "credit"),
    "FR.INR.LEND": ("Lending interest rate", "%", "credit"), "PA.NUS.PPPC.RF": ("Price level ratio (PPP ÷ market FX)", "ratio", "fx"),
    "PA.NUS.FCRF": ("Official exchange rate, LCU per US$ (annual average)", "LCU", "fx"),
}
WB_EXTRA_AREAS = ["EMU"]   # euro area, for EUR valuation

# IMF World Economic Outlook (DataMapper): code -> (label, unit, module)
IMF = {
    "NGDP_RPCH": ("Real GDP growth", "%", "economy"), "NGDPD": ("GDP, current prices", "US$ bn", "economy"),
    "NGDPDPC": ("GDP per capita", "US$", "economy"), "PCPIPCH": ("Inflation, average consumer prices", "%", "economy"),
    "LUR": ("Unemployment rate", "%", "economy"), "BCA_NGDPD": ("Current account balance, % of GDP", "%", "trade"),
    "GGR_NGDP": ("General government revenue, % of GDP", "%", "fiscal"), "GGX_NGDP": ("General government expenditure, % of GDP", "%", "fiscal"),
    "GGXCNL_NGDP": ("Fiscal balance (net lending/borrowing), % of GDP", "%", "fiscal"),
    "GGXONLB_NGDP": ("Primary balance, % of GDP", "%", "fiscal"), "GGXWDG_NGDP": ("General government gross debt, % of GDP", "%", "fiscal"),
}

# Starter US large-cap set for the corporate database (SEC EDGAR CIKs). Target is up to 500 per country.
US_COMPANIES = [
    (320193, "Apple"), (789019, "Microsoft"), (1045810, "NVIDIA"), (1018724, "Amazon"), (1652044, "Alphabet"),
    (1326801, "Meta Platforms"), (1067983, "Berkshire Hathaway"), (1730168, "Broadcom"), (1318605, "Tesla"),
    (59478, "Eli Lilly"), (19617, "JPMorgan Chase"), (104169, "Walmart"), (1403161, "Visa"), (34088, "Exxon Mobil"),
    (731766, "UnitedHealth"), (1141391, "Mastercard"), (909832, "Costco"), (80424, "Procter & Gamble"),
    (200406, "Johnson & Johnson"), (354950, "Home Depot"), (1341439, "Oracle"), (70858, "Bank of America"),
    (1551152, "AbbVie"), (21344, "Coca-Cola"), (93410, "Chevron"), (310158, "Merck"), (77476, "PepsiCo"),
    (858877, "Cisco"), (78003, "Pfizer"), (50863, "Intel"),
]
CORPORATE_SOURCES = {
    "us": "SEC EDGAR XBRL (connected for a starter set)", "jp": "EDINET (FSA) XBRL API", "cn": "CNINFO / SSE / SZSE disclosures",
    "de": "Unternehmensregister / company annual reports (ESEF)", "fr": "AMF / ESEF filings", "in": "BSE / NSE XBRL filings",
    "gb": "Companies House API / FCA NSM", "ca": "SEDAR+", "ch": "SIX disclosures / company reports", "ru": "e-disclosure.ru (coverage limited)",
}


# if an index fails on Yahoo, try a fund that tracks it (labelled as a proxy on the site)
TICKER_FALLBACK = {"000300.SS": ("510300.SS", "Huatai-PineBridge CSI 300 ETF"), "^N225": ("1321.T", "Nomura Nikkei 225 ETF"),
                   "000001.SS": ("510210.SS", "SSE Composite ETF")}

# US sector ETFs (SPDR Select Sector) for sector intelligence; prices from Yahoo Finance
SECTORS = [("xlk", "Information technology", "XLK"), ("xlf", "Financials", "XLF"), ("xlv", "Health care", "XLV"),
           ("xly", "Consumer discretionary", "XLY"), ("xlp", "Consumer staples", "XLP"), ("xle", "Energy", "XLE"),
           ("xli", "Industrials", "XLI"), ("xlb", "Materials", "XLB"), ("xlu", "Utilities", "XLU"),
           ("xlre", "Real estate", "XLRE"), ("xlc", "Communication services", "XLC"),
           ("smh", "Semiconductors (VanEck SMH)", "SMH"), ("kre", "Regional banks (SPDR KRE)", "KRE"), ("gdx", "Gold miners (VanEck GDX)", "GDX")]
