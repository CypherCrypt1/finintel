"""Offline tests: every network loader is replaced by synthetic data.

    python -m pytest -q tests
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from finintel import connectors, run  # noqa: E402
from finintel.scorecard import read_driver, score, transform, zscore_latest  # noqa: E402
from finintel.config import DRIVERS  # noqa: E402

RNG = np.random.default_rng(7)
IDX = pd.date_range("2023-01-01", "2026-11-13", freq="D")


def walk(start, vol, idx=IDX, drift=0.0):
    return pd.Series(start * np.exp(np.cumsum(RNG.normal(drift, vol, len(idx)))), index=idx)


def fake_ohlc(start, vol):
    c = walk(start, vol)
    return pd.DataFrame({"open": c.shift(1).fillna(c), "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1.0}).tail(1000)


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(connectors, "fred", lambda sid: walk(2.0, 0.01).rename(sid))
    monkeypatch.setattr(connectors, "fred_net_liquidity", lambda: walk(6000, 0.003))
    monkeypatch.setattr(connectors, "binance_daily", lambda sym, days=1000: fake_ohlc(4000 if "PAXG" in sym else 70000, 0.012))
    monkeypatch.setattr(connectors, "binance_funding", lambda symbol="BTCUSDT": walk(0.01, 0.05).tail(900))
    weekly = pd.date_range("2023-01-03", "2026-11-10", freq="W-TUE")
    monkeypatch.setattr(connectors, "cftc_gold_mm_pct_oi", lambda: pd.Series(RNG.normal(25, 8, len(weekly)), index=weekly))
    monkeypatch.setattr(connectors, "cftc_btc_lev_net", lambda: pd.Series(RNG.normal(-5000, 2000, len(weekly)), index=weekly))
    monkeypatch.setattr(connectors, "coinmetrics", lambda m, asset="btc": walk(1.6, 0.01))
    monkeypatch.setattr(connectors, "mempool_hashrate", lambda: walk(900, 0.01))


def test_transforms_and_zscore():
    s = pd.Series(np.arange(500, dtype=float), index=pd.date_range("2025-01-01", periods=500))
    assert transform(s, "diff", 10).iloc[-1] == 10
    assert transform(s, "pct", 1).iloc[-1] == pytest.approx(100 * (499 / 498 - 1))
    z, pct, n = zscore_latest(s)
    assert z > 1.5 and pct == 100 and n == 500


def test_flow_sum_does_not_double_count():
    s = pd.Series([10.0, 20.0], index=pd.to_datetime(["2026-01-01", "2026-01-05"]))
    assert transform(s, "sum", 28).iloc[-1] == 30


def test_signal_direction_and_clip():
    d = next(x for x in DRIVERS["XAU"] if x["key"] == "real_yield")
    rising = pd.Series(np.linspace(0, 3, 1200) ** 2, index=pd.date_range("2023-01-01", periods=1200))
    r = read_driver(d, rising)
    assert r.signal is not None and -2 <= r.signal < 0      # rising real yields are bearish for gold


def test_missing_driver_and_contested_score():
    d = DRIVERS["XAU"]
    r_missing = read_driver(d[0], None, "network down")
    assert r_missing.status == "missing" and r_missing.signal is None
    # two equal-weight drivers in opposite directions -> agreement 50% -> contested or neutral
    a = read_driver(d[0], None); a.signal = 1.5
    b = read_driver(d[4], None); b.signal = -1.2
    sc = score([a, b], "long")
    assert sc.agreement < 0.6 and sc.stance in ("Contested", "Neutral")


def test_end_to_end(offline, tmp_path):
    out = tmp_path / "dash.html"
    run.main(["--out", str(out), "--manual", str(Path(__file__).resolve().parent.parent / "manual_inputs"),
              "--db", str(tmp_path / "t.sqlite")])
    res = json.loads(out.with_suffix(".json").read_text())
    assert {a["symbol"] for a in res["assets"]} == {"XAU", "BTC"}
    for a in res["assets"]:
        assert set(a["scores"]) == {"short", "medium", "long"}
        assert a["levels"]["sma200"] is not None
        assert any(d["signal"] is not None for d in a["drivers"])
        assert len(a["outlooks"]) == 3
    html = out.read_text()
    assert "const DATA =" in html and "</script>" in html
