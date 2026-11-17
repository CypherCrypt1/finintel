"""Probe: OECD quarterly GDP growth and the IMF's new SDMX API."""
import requests
H = {"User-Agent": "Mozilla/5.0 SOVEREIGN-research", "Accept": "*/*"}
def show(label, url, params=None, n=1200):
    try:
        r = requests.get(url, params=params, headers=H, timeout=90)
        print(f"\n### {label}: HTTP {r.status_code} len={len(r.content)}", flush=True); print(r.text[:n], flush=True)
    except Exception as e:
        print(f"\n### {label}: ERROR {e}", flush=True)
A = "USA+CHN+JPN+DEU+FRA+IND+GBR+CAN+CHE+RUS"
base = "https://sdmx.oecd.org/public/rest/data"
show("QNA growth A", f"{base}/OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA_EXPENDITURE_GROWTH_OECD,/Q..{A}.S1..B1GQ......GY.", {"startPeriod": "2025-Q1", "format": "csvfilewithlabels"}, 2500)
show("QNA growth B", f"{base}/OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA_EXPENDITURE_GROWTH_OECD,/Q..{A}..........", {"startPeriod": "2026-Q1", "format": "csvfilewithlabels"}, 2500)
show("QNA growth all", f"{base}/OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA_EXPENDITURE_GROWTH_OECD,/all", {"startPeriod": "2026-Q2", "format": "csvfilewithlabels"}, 3000)
show("IMF 2.1 dataflows", "https://api.imf.org/external/sdmx/2.1/dataflow", n=400)
show("IMF 3.0 dataflows", "https://api.imf.org/external/sdmx/3.0/structure/dataflow/IMF.STA/*/+", n=400)
for flow, key in (("IRFCL", "CHN+USA+IND+RUS..M"), ("IRFCL", "*"), ("IFS", "*"), ("IIP", "*"), ("BOP", "*")):
    show(f"IMF 3.0 data {flow} {key}", f"https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/{flow}/+/{key}", {"c[TIME_PERIOD]": "ge:2026-01", "dimensionAtObservation": "AllDimensions"}, 800)
show("IMF 2.1 IRFCL", "https://api.imf.org/external/sdmx/2.1/data/IMF.STA,IRFCL/all", {"startPeriod": "2026-06"}, 800)
show("IMF 3.0 IRFCL structure", "https://api.imf.org/external/sdmx/3.0/structure/dataflow/IMF.STA/IRFCL/+", {"references": "descendants", "detail": "referencepartial"}, 3000)
