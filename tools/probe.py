"""Probe: IMF new SDMX 3.0 API in CSV form (IRFCL reserves, IIP)."""
import io, requests, pandas as pd
H = {"User-Agent": "Mozilla/5.0 SOVEREIGN-research", "Accept": "application/vnd.sdmx.data+csv;version=2.0.0;labels=both"}
for flow in ("IRFCL", "IIP"):
    u = f"https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/{flow}/+/*"
    p = {"c[COUNTRY]": "USA,CHN", "c[TIME_PERIOD]": "ge:2026-01"}
    try:
        r = requests.get(u, params=p, headers=H, timeout=120)
        print(f"\n### {flow}: HTTP {r.status_code} len={len(r.content)} ct={r.headers.get('content-type')}", flush=True)
        print(r.text[:600])
        df = pd.read_csv(io.StringIO(r.text), dtype=str)
        print("columns:", list(df.columns))
        for col in df.columns:
            if col in ("OBS_VALUE",) or df[col].nunique() > 400:
                continue
            vals = df[col].dropna().unique()
            print(f"  {col} ({len(vals)}):", " | ".join(map(str, vals[:120]))[:4000])
        print("periods:", sorted(df.get("TIME_PERIOD", pd.Series(dtype=str)).dropna().unique())[-8:])
    except Exception as e:
        print(flow, "ERROR", e)
