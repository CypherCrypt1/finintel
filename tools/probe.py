"""Probe: Eurostat, ONS, IMF portal CDIS/CPIS, coal tickers, FRED PPI."""
import io, os, requests, pandas as pd
H = {"User-Agent": "Mozilla/5.0 SOVEREIGN-research"}
def show(label, url, params=None, n=700, headers=None):
    try:
        r = requests.get(url, params=params, headers=headers or H, timeout=120)
        print(f"\n### {label}: HTTP {r.status_code} len={len(r.content)}", flush=True); print(r.text[:n], flush=True); return r
    except Exception as e:
        print(f"\n### {label}: ERROR {e}", flush=True)
ES = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
r = show("Eurostat HICP", f"{ES}/prc_hicp_manr", {"geo": ["FR", "DE", "CH"], "coicop": "CP00", "sinceTimePeriod": "2026-01"}, 300)
try:
    j = r.json(); print("time:", list(j["dimension"]["time"]["category"]["index"])[-3:], "geo:", j["dimension"]["geo"]["category"]["index"], "values:", list(j["value"].items())[-6:])
except Exception as e: print(e)
r = show("Eurostat unemployment", f"{ES}/une_rt_m", {"geo": ["FR", "DE", "CH"], "s_adj": "SA", "age": "TOTAL", "sex": "T", "unit": "PC_ACT", "sinceTimePeriod": "2026-01"}, 300)
try:
    j = r.json(); print("time:", list(j["dimension"]["time"]["category"]["index"])[-3:], "values:", list(j["value"].items())[-6:])
except Exception as e: print(e)
r = show("Eurostat PPI", f"{ES}/sts_inppd_m", {"geo": ["FR", "DE"], "nace_r2": "B-E36", "unit": "PCH_SM", "indic_bt": "PRC_PRR_DOM", "s_adj": "NSA", "sinceTimePeriod": "2026-01"}, 300)
try:
    j = r.json(); print("time:", list(j["dimension"]["time"]["category"]["index"])[-3:], "values:", list(j["value"].items())[-6:])
except Exception as e: print(e)
show("ONS CPIH/CPI D7G7", "https://api.beta.ons.gov.uk/v1/timeseries/d7g7/dataset/mm23/data", n=300)
show("ONS CPI csv", "https://www.ons.gov.uk/generator", {"format": "csv", "uri": "/economy/inflationandpriceindices/timeseries/d7g7/mm23"}, 600)
show("ONS unemp csv", "https://www.ons.gov.uk/generator", {"format": "csv", "uri": "/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms"}, 300)
show("Swiss SNB data CPI", "https://data.snb.ch/api/cube/plkopr/data/csv/en", n=600)
H2 = {"User-Agent": "Mozilla/5.0 SOVEREIGN-research", "Accept": "application/vnd.sdmx.data+csv;version=2.0.0;labels=both"}
for flow in ("CDIS", "CPIS"):
    r = show(f"IMF portal {flow}", f"https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/{flow}/+/*", {"c[COUNTRY]": "USA", "c[TIME_PERIOD]": "ge:2024"}, 300, H2)
    try:
        df = pd.read_csv(io.StringIO(r.text), dtype=str)
        for c in df.columns:
            if df[c].nunique() < 60: print("  ", c, "|", " | ".join(map(str, df[c].dropna().unique()[:30]))[:1200])
        print("  periods:", sorted(df.filter(like="TIME_PERIOD").iloc[:, 0].unique())[-5:])
    except Exception as e: print(e)
for t in ("MTF=F", "NCF=F", "QZ=F", "ATW=F"):
    show(f"yahoo {t}", f"https://query1.finance.yahoo.com/v8/finance/chart/{t}", {"range": "1mo", "interval": "1d"}, 250)
k = os.environ.get("FRED_API_KEY")
for sid in ("PPIACO", "PCUOMFGOMFG", "CPALTT01FRM659N", "FRACPIALLMINMEI", "CP0000FRM086NEST", "CP0000CHM086NEST", "LRHUTTTTFRM156S", "PRMNTO01DEM661N"):
    if k:
        r = show(f"FRED {sid}", "https://api.stlouisfed.org/fred/series", {"series_id": sid, "api_key": k, "file_type": "json"}, 0)
        try: s = r.json()["seriess"][0]; print("  ", s["title"][:80], "|", s["observation_end"], s["frequency"])
        except Exception as e: print("  ", e)
