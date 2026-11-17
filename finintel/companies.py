"""Refresh the corporate database from SEC EDGAR on your own computer.

SEC blocks requests from GitHub's servers, so run this locally (any home or office connection works):

    python -m finintel.companies          # writes data/companies.json
    git add data/companies.json && git commit -m "Company refresh" && git push

The daily GitHub build picks the file up and publishes it, labelled with its refresh date.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from . import global_config as G
from . import global_data as D


def main():
    out, errors = [], {}
    for cik, name in G.US_COMPANIES:
        try:
            rec = D.sec_company(cik)
            rec["country"], rec["listed_name"] = "us", name
            out.append(rec)
            print(f"ok  {name}")
        except Exception as e:
            errors[str(cik)] = str(e)[:200]
            print(f"ERR {name}: {e}")
        time.sleep(0.2)
    path = Path(__file__).resolve().parent.parent / "data" / "companies.json"
    path.write_text(json.dumps({"fetched": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "companies": out, "errors": errors}, default=str))
    print(f"{len(out)} companies written to {path}")


if __name__ == "__main__":
    main()
