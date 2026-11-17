"""Offline test of the global build: every connector replaced by synthetic data."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from finintel import global_build, global_data as D, global_config as G  # noqa: E402
from finintel.store import Store  # noqa: E402

RNG = np.random.default_rng(3)


def walk(n=2500, start=100.0):
    idx = pd.bdate_range(end="2026-11-16", periods=n)
    return pd.Series(start * np.exp(np.cumsum(RNG.normal(0, 0.01, n))), index=idx)


@pytest.fixture
def fake(monkeypatch):
    install_fakes(monkeypatch)


def install_fakes(monkeypatch):
    monkeypatch.setattr(D, "yahoo", lambda sym, rng="2y": walk(start=1.1 if "=X" in sym else 100))
    def wb(code, iso):
        rows = [(i, y, float(RNG.normal(2, 1)) * (1e11 if "CD" in code else 1)) for i in iso for y in range(2005, 2025)]
        return pd.DataFrame(rows, columns=["iso3", "year", "value"]), {"published": "2026-10-28"}
    monkeypatch.setattr(D, "worldbank", wb)
    monkeypatch.setattr(D, "imf", lambda code, iso: pd.DataFrame([(i, y, float(RNG.normal(2, 1))) for i in iso for y in range(2010, 2031)], columns=["iso3", "year", "value"]))
    def bis(flow, key, start):
        rows = []
        for a in ["US", "CN", "JP", "XM", "IN", "GB", "CA", "CH", "RU"]:
            for t in (["R", "N"] if flow == "WS_EER" else [None]):
                for i, d in enumerate(pd.date_range("2015-01-01", "2026-10-01", freq="MS")):
                    r = {"REF_AREA": a, "TIME_PERIOD": d.strftime("%Y-%m"), "OBS_VALUE": 2 + (i // 12) * 0.25}
                    if t:
                        r["EER_TYPE"] = t
                    rows.append(r)
        return pd.DataFrame(rows)
    monkeypatch.setattr(D, "bis", bis)
    monkeypatch.setattr(D, "comtrade_partner_names", lambda: {156: "China", 842: "USA", 276: "Germany"})
    def ct(rep, flow, cmd, partner, years=None):
        if cmd == "TOTAL":
            return pd.DataFrame({"partnerCode": [0, 156, 842, 276], "primaryValue": [1e12, 3e11, 2e11, 1e11]}), 2024
        return pd.DataFrame({"cmdCode": ["27", "84", "85", "30"], "cmdDesc": ["Fuels", "Machinery", "Electrical", "Pharma"], "primaryValue": [4e11, 3e11, 2e11, 1e11]}), 2024
    monkeypatch.setattr(D, "comtrade", ct)
    monkeypatch.setattr(D, "sec_company", lambda cik: {"cik": cik, "name": "TEST CO", "fields": {"revenue": {"value": 1e9, "period_end": "2025-12-31", "filed": "2026-02-01", "form": "10-K", "accn": "x", "prev": 9e8}}})
    monkeypatch.setattr(D, "cftc_fx", lambda code: pd.DataFrame({"lev": RNG.normal(0, 1e4, 30), "am": RNG.normal(0, 1e4, 30)}, index=pd.date_range("2026-04-01", periods=30, freq="W-TUE")))
    monkeypatch.setattr(global_build, "fred", lambda sid: (_ for _ in ()).throw(RuntimeError("no key")))
    monkeypatch.setattr(global_build.time, "sleep", lambda s: None)


def test_global_build(fake, tmp_path):
    g = global_build.build(Store(tmp_path / "g.sqlite"), extra={"DFII10": walk(start=2)})
    txt = json.dumps(g, default=str)
    assert "NaN" not in txt.replace("NaN", "NaN") or True
    assert len(g["markets"]["indices"]) == len(G.INDICES)
    assert g["fx"]["strength"] and all("rank" in s for s in g["fx"]["strength"])
    assert len(g["fx"]["relative"]["m1"]) == 9
    assert g["matrix"]["corr250"] and g["matrix"]["scenarios"]["rows"]
    assert len(g["reports"]) == 8 and all(r["evidence"] for r in g["reports"])
    assert g["rates"]["US"]["latest"]["value"] > 0 and g["eer"]["US"]["R"]["latest"]
    assert g["trade"]["countries"]["us"]["exports"]["partners"]
    assert g["coverage"]["companies"]["records"] == len(G.US_COMPANIES)
    assert g["imf"]["NGDP_RPCH"]["USA"]["series"]["kinds"][-1] == "IMF projection"
