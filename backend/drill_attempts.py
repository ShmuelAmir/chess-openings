"""
Drill Attempt store - every practice run of a Recall Gap, stored in SQLite
next to the game cache. See Drill Attempt in CONTEXT.md.
"""
import sqlite3
from pathlib import Path
from typing import NamedTuple, Optional


class DrillAttempt(NamedTuple):
    gap_position_key: str
    at: int  # Unix timestamp
    passed: bool
    first_miss_position_key: Optional[str]  # where a failed attempt's first wrong move was played


class DrillAttemptStore:
    """The persisted Drill Attempts."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent / "chess_games.db"
        self.db_path = str(db_path)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS drill_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gap_position_key TEXT NOT NULL,
                    at INTEGER NOT NULL,
                    passed INTEGER NOT NULL,
                    first_miss_position_key TEXT
                )
            """)
            conn.commit()

    def record(
        self,
        gap_position_key: str,
        passed: bool,
        first_miss_position_key: Optional[str],
        at: int,
    ):
        """Record one Drill Attempt: a pass, or a fail with its first miss."""
        if passed != (first_miss_position_key is None):
            raise ValueError("A failed Drill Attempt needs its first miss, and a pass has none")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO drill_attempts (gap_position_key, at, passed, first_miss_position_key)"
                " VALUES (?, ?, ?, ?)",
                (gap_position_key, at, int(passed), first_miss_position_key),
            )
            conn.commit()

    def attempts(self) -> list[DrillAttempt]:
        """Every Drill Attempt, oldest first."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT gap_position_key, at, passed, first_miss_position_key"
                " FROM drill_attempts ORDER BY at, id"
            ).fetchall()
        return [DrillAttempt(key, at, bool(passed), miss) for key, at, passed, miss in rows]


# Global store instance
_store: Optional[DrillAttemptStore] = None


def get_drill_attempt_store() -> DrillAttemptStore:
    """Get or create the global Drill Attempt store."""
    global _store
    if _store is None:
        _store = DrillAttemptStore()
    return _store
