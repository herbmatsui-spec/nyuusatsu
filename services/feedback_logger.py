from __future__ import annotations

import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = str(_PROJECT_ROOT / "data" / "prediction_feedback.sqlite3")
FEEDBACK_TYPES = ("difficulty", "win_prediction", "similarity")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS prediction_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feedback_type TEXT NOT NULL CHECK(feedback_type IN ('difficulty', 'win_prediction', 'similarity')),
    bid_id INTEGER NOT NULL CHECK(bid_id > 0),
    rating INTEGER NOT NULL CHECK(rating IN (-1, 1)),
    similar_bid_id INTEGER CHECK(similar_bid_id > 0),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_type_created
    ON prediction_feedback (feedback_type, created_at);
CREATE TRIGGER IF NOT EXISTS feedback_no_update BEFORE UPDATE ON prediction_feedback
BEGIN SELECT RAISE(ABORT, 'feedback is append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_no_delete BEFORE DELETE ON prediction_feedback
BEGIN SELECT RAISE(ABORT, 'feedback is append-only'); END;
"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _bid_id(value):
    if type(value) is not int or not 1 <= value <= 9223372036854775807:
        raise ValueError("bid_id must be a positive SQLite integer")


class FeedbackLogger:
    def __init__(self, path: str | None = None):
        self.path = path or DEFAULT_DB_PATH
        self._lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.executescript(_SCHEMA)
        except Exception:
            connection.close()
            raise
        return connection

    def log_feedback(self, feedback_type: str, bid_id: int, rating: int, *, similar_bid_id: int | None = None) -> int:
        if feedback_type not in FEEDBACK_TYPES:
            raise ValueError(f"feedback_type must be one of {FEEDBACK_TYPES}")
        _bid_id(bid_id)
        if type(rating) is not int or rating not in (-1, 1):
            raise ValueError("rating must be -1 or 1")
        if similar_bid_id is not None:
            _bid_id(similar_bid_id)
            if feedback_type != "similarity" or similar_bid_id == bid_id:
                raise ValueError("similar_bid_id requires a distinct similarity target")
        if feedback_type == "similarity" and similar_bid_id is None:
            raise ValueError("similarity feedback requires similar_bid_id")
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "INSERT INTO prediction_feedback (feedback_type, bid_id, rating, similar_bid_id, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (feedback_type, bid_id, rating, similar_bid_id, _utcnow().isoformat()),
            )
            return int(cursor.lastrowid)

    def aggregate_weekly(self, feedback_type: str | None = None, weeks: int = 12) -> list[dict]:
        if feedback_type is not None and feedback_type not in FEEDBACK_TYPES:
            raise ValueError("Invalid feedback_type")
        if type(weeks) is not int or not 1 <= weeks <= 520:
            raise ValueError("weeks must be an integer between 1 and 520")
        if not Path(self.path).exists():
            return []
        now = _utcnow()
        monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        start = monday - timedelta(weeks=weeks - 1)
        sql = (
            "SELECT feedback_type, substr(created_at, 1, 10) AS day, COUNT(*) AS total, "
            "SUM(rating = 1) AS positive, SUM(rating = -1) AS negative "
            "FROM prediction_feedback WHERE created_at >= ? AND created_at <= ?"
        )
        parameters = [start.isoformat(), now.isoformat()]
        if feedback_type is not None:
            sql += " AND feedback_type = ?"
            parameters.append(feedback_type)
        sql += " GROUP BY feedback_type, day"
        with self._lock, closing(self._connect()) as connection:
            rows = connection.execute(sql, parameters).fetchall()
        buckets = {}
        for row in rows:
            day = datetime.fromisoformat(row["day"]).date()
            week = (day - timedelta(days=day.weekday())).isoformat()
            key = week, row["feedback_type"]
            bucket = buckets.setdefault(key, {"week_start": week, "feedback_type": row["feedback_type"], "total": 0, "positive": 0, "negative": 0})
            for field in ("total", "positive", "negative"):
                bucket[field] += int(row[field])
        return [dict(bucket, positive_rate=bucket["positive"] / bucket["total"]) for _, bucket in sorted(buckets.items())]
