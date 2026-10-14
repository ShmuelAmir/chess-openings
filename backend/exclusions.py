"""
"Not repertoire" exclusion list - the studies a Lichess account has marked as
not part of their Repertoire, stored in SQLite next to the game cache.
"""
import sqlite3
from pathlib import Path
from typing import Iterable, Optional


class ExclusionStore:
    """One Lichess account's persisted "not repertoire" exclusion list, by study id."""

    def __init__(self, account: str, db_path: Optional[str] = None):
        """
        Args:
            account: The Lichess account the list belongs to. The first
                account to open the store adopts a list stored before lists
                had accounts.
        """
        if db_path is None:
            db_path = Path(__file__).parent / "chess_games.db"
        self.db_path = str(db_path)
        self.account = account
        with sqlite3.connect(self.db_path) as conn:
            columns = [row[1] for row in conn.execute("PRAGMA table_info(not_repertoire_studies)")]
            if columns and "account" not in columns:
                conn.execute("ALTER TABLE not_repertoire_studies RENAME TO not_repertoire_studies_unowned")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS not_repertoire_studies (
                    account TEXT NOT NULL,
                    study_id TEXT NOT NULL,
                    PRIMARY KEY (account, study_id)
                )
            """)
            if columns and "account" not in columns:
                conn.execute(
                    "INSERT INTO not_repertoire_studies (account, study_id)"
                    " SELECT ?, study_id FROM not_repertoire_studies_unowned",
                    (account,),
                )
                conn.execute("DROP TABLE not_repertoire_studies_unowned")
            conn.commit()

    def excluded_studies(self) -> set[str]:
        """The ids of the studies the account marked "not repertoire"."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT study_id FROM not_repertoire_studies WHERE account = ?", (self.account,)
            ).fetchall()
        return {row[0] for row in rows}

    def set_excluded_studies(self, study_ids: Iterable[str]):
        """Replace the account's exclusion list."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM not_repertoire_studies WHERE account = ?", (self.account,))
            conn.executemany(
                "INSERT INTO not_repertoire_studies (account, study_id) VALUES (?, ?)",
                [(self.account, study_id) for study_id in set(study_ids)],
            )
            conn.commit()
