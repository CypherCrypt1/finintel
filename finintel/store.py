"""Point-in-time storage (SQLite for v0; PostgreSQL + TimescaleDB in Phase 1).

Every observation keeps value_date (the date the value applies to) and
known_at (when this platform first saw it). Revisions are new rows, never
overwrites, so a backtest can ask "what did we know on that date?".
Outlooks are frozen in a log and scored when their horizon ends.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS observation (
  series_id TEXT, value_date TEXT, known_at TEXT, value REAL,
  PRIMARY KEY (series_id, value_date, known_at));
CREATE TABLE IF NOT EXISTS outlook (
  id INTEGER PRIMARY KEY AUTOINCREMENT, asset TEXT, horizon TEXT, as_of TEXT,
  stance TEXT, composite REAL, agreement REAL, price REAL, resolve_on TEXT,
  realised_return REAL, hit INTEGER, scored_at TEXT);
"""
HORIZON_DAYS = {"short": 5, "medium": 28, "long": 91}


class Store:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def save_series(self, sid: str, s: pd.Series) -> int:
        """Insert values that are new or revised since the last time we saw them."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cur = self.db.execute(
            "SELECT value_date, value FROM observation o WHERE series_id=? AND known_at="
            "(SELECT MAX(known_at) FROM observation WHERE series_id=o.series_id AND value_date=o.value_date)", (sid,))
        known = dict(cur.fetchall())
        rows = [(sid, d.strftime("%Y-%m-%d"), now, float(v)) for d, v in s.dropna().items()
                if known.get(d.strftime("%Y-%m-%d")) is None or abs(known[d.strftime("%Y-%m-%d")] - float(v)) > 1e-12]
        self.db.executemany("INSERT OR IGNORE INTO observation VALUES (?,?,?,?)", rows)
        self.db.commit()
        return len(rows)

    def as_known_on(self, sid: str, when: str) -> pd.Series:
        """The series exactly as the platform knew it on `when` (YYYY-MM-DD)."""
        q = ("SELECT value_date, value FROM observation o WHERE series_id=? AND known_at<=? AND known_at="
             "(SELECT MAX(known_at) FROM observation WHERE series_id=o.series_id AND value_date=o.value_date AND known_at<=?)")
        df = pd.read_sql(q, self.db, params=(sid, when + "T23:59:59", when + "T23:59:59"))
        return pd.Series(df.value.values, index=pd.to_datetime(df.value_date)).sort_index()

    def log_outlook(self, asset, horizon, as_of, stance, composite, agreement, price):
        resolve = (pd.Timestamp(as_of) + pd.Timedelta(days=HORIZON_DAYS[horizon])).strftime("%Y-%m-%d")
        self.db.execute("INSERT INTO outlook (asset,horizon,as_of,stance,composite,agreement,price,resolve_on)"
                        " VALUES (?,?,?,?,?,?,?,?)", (asset, horizon, as_of, stance, composite, agreement, price, resolve))
        self.db.commit()

    def score_due(self, prices: dict[str, pd.Series]) -> int:
        """Score every outlook whose horizon has ended. Neutral/Contested are scored by a small move (<1 sd)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        due = self.db.execute("SELECT id, asset, horizon, stance, price, resolve_on FROM outlook "
                              "WHERE scored_at IS NULL AND resolve_on<=?", (today,)).fetchall()
        n = 0
        for oid, asset, hz, stance, p0, resolve in due:
            px = prices.get(asset)
            if px is None or p0 is None:
                continue
            after = px[px.index >= pd.Timestamp(resolve)]
            if after.empty:
                continue
            ret = float(after.iloc[0] / p0 - 1)
            band = float(px.pct_change().tail(250).std() * (HORIZON_DAYS[hz] ** 0.5))
            if "bullish" in stance.lower():
                hit = ret > 0
            elif "bearish" in stance.lower():
                hit = ret < 0
            else:
                hit = abs(ret) < band
            self.db.execute("UPDATE outlook SET realised_return=?, hit=?, scored_at=? WHERE id=?",
                            (ret, int(hit), today, oid))
            n += 1
        self.db.commit()
        return n

    def report_card(self) -> pd.DataFrame:
        return pd.read_sql("SELECT asset, horizon, COUNT(*) n, AVG(hit) hit_rate FROM outlook "
                           "WHERE scored_at IS NOT NULL GROUP BY asset, horizon", self.db)
