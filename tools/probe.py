"""Diagnostic: print the structure of DBnomics IMF CDIS / CPIS datasets (run via the probe workflow)."""
import json
import requests

H = {"User-Agent": "Mozilla/5.0 SOVEREIGN probe"}
for ds in ("CDIS", "CPIS"):
    print(f"===== IMF/{ds} =====", flush=True)
    try:
        r = requests.get(f"https://api.db.nomics.world/v22/datasets/IMF/{ds}", headers=H, timeout=60)
        j = r.json()
        d = j.get("datasets", {}).get("docs", [{}])[0]
        print("name:", d.get("name"), "| nb_series:", d.get("nb_series"), "| updated:", d.get("indexed_at"))
        print("dimensions:", d.get("dimensions_codes_order"))
        for dim, vals in (d.get("dimensions_values_labels") or {}).items():
            items = list(vals.items()) if isinstance(vals, dict) else vals
            print(f"  {dim}: {len(items)} values; first 40:", json.dumps(items[:40])[:2500])
    except Exception as e:
        print("dataset error", e)
    try:
        r = requests.get(f"https://api.db.nomics.world/v22/series/IMF/{ds}", headers=H, timeout=60,
                         params={"dimensions": json.dumps({"REF_AREA": ["US"]}), "observations": 1, "limit": 5})
        j = r.json()
        for s in j.get("series", {}).get("docs", [])[:5]:
            print("series:", s.get("series_code"), "|", s.get("series_name"), "| dims:", s.get("dimensions"), "| periods:", s.get("period", [])[-3:], s.get("value", [])[-3:])
        print("num_found:", j.get("series", {}).get("num_found"))
    except Exception as e:
        print("series error", e)
