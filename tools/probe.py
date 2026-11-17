"""Diagnostic probe of candidate free data sources (run via the probe workflow)."""
import json, os, requests
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) SOVEREIGN-research"}
DBN = "https://api.db.nomics.world/v22"

def show(label, url, params=None, n=600, headers=None):
    try:
        r = requests.get(url, params=params, headers=headers or H, timeout=60)
        print(f"\n### {label}: HTTP {r.status_code} len={len(r.content)} ct={r.headers.get('content-type')}", flush=True)
        print(r.text[:n].replace("\r", ""), flush=True)
        return r
    except Exception as e:
        print(f"\n### {label}: ERROR {e}", flush=True)

def dbn_ds(prov, q):
    r = show(f"DBN search {prov} {q}", f"{DBN}/search", {"q": q, "limit": 20}, n=0)
    try:
        for d in r.json()["results"]["docs"]:
            if d.get("provider_code") == prov:
                print("  ", d.get("code"), "|", d.get("name"), "|", d.get("nb_series"))
    except Exception as e:
        print("  parse", e)

def dbn_dims(prov, ds, maxv=60):
    try:
        j = requests.get(f"{DBN}/datasets/{prov}/{ds}", headers=H, timeout=60).json()
        d = j["datasets"]["docs"][0]
        print(f"\n=== {prov}/{ds}: {d.get('name')} nb={d.get('nb_series')} dims={d.get('dimensions_codes_order')}")
        for dim, vals in (d.get("dimensions_values_labels") or {}).items():
            items = list(vals.items()) if isinstance(vals, dict) else vals
            print(f"  {dim} ({len(items)}):", json.dumps(items[:maxv])[:1500])
    except Exception as e:
        print(f"\n=== {prov}/{ds}: ERROR {e}")

def dbn_ser(prov, ds, dims, n=4):
    try:
        j = requests.get(f"{DBN}/series/{prov}/{ds}", params={"dimensions": json.dumps(dims), "observations": 1, "limit": n}, headers=H, timeout=60).json()
        s = j.get("series", {})
        print(f"\n--- series {prov}/{ds} {dims}: found={s.get('num_found')}")
        for d in s.get("docs", [])[:n]:
            print("  ", d.get("series_code"), "|", d.get("series_name", "")[:140], "|", d.get("period", [])[-2:], d.get("value", [])[-2:])
    except Exception as e:
        print("  ERROR", e)

# --- BIS locational banking
dbn_ds("BIS", "locational banking")
dbn_dims("BIS", "WS_LBS_D_PUB", 40)
show("BIS direct LBS", "https://stats.bis.org/api/v1/data/WS_LBS_D_PUB/Q.S.C.A.TO1.A.5J.A.US.A.5J.N", {"startPeriod": "2023-Q1", "format": "csv"}, 800)
show("BIS direct LBS v2", "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_LBS_D_PUB/1.0/Q.S.C.A.TO1.A.5J.A.US.A.5J.N", {"startPeriod": "2023-Q1", "format": "csv"}, 800)
# --- IMF IIP
dbn_ds("IMF", "international investment position")
for ds in ("BOP", "IIP"):
    dbn_ser("IMF", ds, {"FREQ": ["A"], "REF_AREA": ["US"]}, 6)
dbn_ser("IMF", "BOP", {"FREQ": ["Q"], "REF_AREA": ["US"], "INDICATOR": ["IAD_BP6_USD", "IL_BP6_USD", "IA_BP6_USD", "IN_BP6_USD"]}, 6)
# --- IMF gold reserves
dbn_ser("IMF", "IFS", {"FREQ": ["M"], "REF_AREA": ["CN"], "INDICATOR": ["RAFAGOLDV_OZT", "RAFAGOLD_USD"]}, 4)
dbn_ds("IMF", "international reserves")
# --- TIC
show("TIC mfh", "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/mfh.txt", n=1500)
show("TIC mfh home", "https://home.treasury.gov/system/files/206/mfh.txt", n=1500)
show("TIC slt5", "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.txt", n=1200)
# --- OECD
show("OECD CLI", "https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI,/USA+CHN+JPN+DEU+FRA+IND+GBR+CAN+CHE.M.LI+BCICP+CCICP......", {"startPeriod": "2025-06", "format": "csvfilewithlabels"}, 1500)
show("OECD KEI", "https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_KEI@DF_KEI,/USA+DEU.M........", {"startPeriod": "2025-06", "format": "csvfilewithlabels"}, 1500)
dbn_ds("OECD", "composite leading indicators")
# --- FRED release calendar
k = os.environ.get("FRED_API_KEY")
if k:
    r = show("FRED release dates", "https://api.stlouisfed.org/fred/releases/dates", {"api_key": k, "file_type": "json", "realtime_start": "2026-11-17", "realtime_end": "2027-01-31", "include_release_dates_with_no_data": "true", "limit": 1000, "sort_order": "asc"}, 0)
    try:
        j = r.json(); print("count", j.get("count")); print(json.dumps(j.get("release_dates", [])[:30])[:2500])
    except Exception as e: print(e)
# --- NBIM
show("NBIM api", "https://www.nbim.no/api/investments/v2/report/?assetType=eq&date=20241231", n=800)
show("NBIM page", "https://www.nbim.no/en/investments/all-investments/", n=300)
# --- yahoo CSI300 alternatives
for sym in ("000300.SS", "510300.SS", "ASHR", "IMOEX.ME", "^SPX"):
    show(f"yahoo {sym}", f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}", {"range": "5d", "interval": "1d"}, 200)
# --- valuation: shiller / multpl
show("multpl", "https://www.multpl.com/shiller-pe/table/by-month", n=300)
show("Damodaran", "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.html", n=300)
