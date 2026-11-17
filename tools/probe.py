"""Diagnostic: list IMF CDIS/CPIS indicator codes and test the position collector (run via the probe workflow)."""
import json
from finintel import global_data as D
from finintel.global_build import Collector, collect_positions

for ds in ("CDIS", "CPIS"):
    lab = D.dbn_labels(ds, "INDICATOR")
    print(f"===== {ds} indicators ({len(lab)}) =====", flush=True)
    for k, v in lab.items():
        print(" ", k, "|", v)
c = Collector(None, offline=False)
out = collect_positions(c)
print("errors:", c.errors)
for k, rec in out.items():
    print(k, {s: (v["year"], v["n_partners"], round(v["total_allocated"] / 1e9), [p["iso2"] for p in v["partners"][:5]]) if v else None for s, v in rec.items()}, flush=True)
