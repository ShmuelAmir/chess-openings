"""
Drill Attempt store - every practice run of a Recall Gap by a Lichess
account, stored in SQLite next to the game cache. See Drill Attempt in CONTEXT.md.
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
    """One Lichess account's persisted Drill Attempts."""

    def __init__(self, account: str, db_path: Optional[str] = None):
        """
        Args:
            account: The Lichess account the Drill Attempts belong to. The
                first account to open the store adopts those stored before
                Drill Attempts had accounts.
        """
        if db_path is None:
            db_path = Path(__file__).parent / "chess_games.db"
        self.db_path = str(db_path)
        self.account = account
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS drill_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gap_position_key TEXT NOT NULL,
                    at INTEGER NOT NULL,
                    passed INTEGER NOT NULL,
                    first_miss_position_key TEXT,
                    account TEXT
                )
            """)
            columns = [row[1] for row in conn.execute("PRAGMA table_info(drill_attempts)")]
            if "account" not in columns:
                conn.execute("ALTER TABLE drill_attempts ADD COLUMN account TEXT")
            conn.execute("UPDATE drill_attempts SET account = ? WHERE account IS NULL", (account,))
            conn.commit()

    def record(
        self,
        gap_position_key: str,
        passed: bool,
        first_miss_position_key: Optional[str],
        at: int,
    ):
        """Record one of the account's Drill Attempts: a pass, or a fail with its first miss."""
        if passed != (first_miss_position_key is None):
            raise ValueError("A failed Drill Attempt needs its first miss, and a pass has none")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO drill_attempts (account, gap_position_key, at, passed, first_miss_position_key)"
                " VALUES (?, ?, ?, ?, ?)",
                (self.account, gap_position_key, at, int(passed), first_miss_position_key),
            )
            conn.commit()

    def attempts(self) -> list[DrillAttempt]:
        """Every one of the account's Drill Attempts, oldest first."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT gap_position_key, at, passed, first_miss_position_key"
                " FROM drill_attempts WHERE account = ? ORDER BY at, id",
                (self.account,),
            ).fetchall()
        return [DrillAttempt(key, at, bool(passed), miss) for key, at, passed, miss in rows]

