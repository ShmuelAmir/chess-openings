"""
"Not repertoire" exclusion list - the studies the user has marked as not part
of their Repertoire, stored in SQLite next to the game cache.
"""
import sqlite3
from pathlib import Path
from typing import Iterable, Optional


class ExclusionStore:
    """The persisted "not repertoire" exclusion list, by study id."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent / "chess_games.db"
        self.db_path = str(db_path)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS not_repertoire_studies (
                    study_id TEXT PRIMARY KEY
                )
            """)
            conn.commit()

    def excluded_studies(self) -> set[str]:
        """The ids of the studies marked "not repertoire"."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT study_id FROM not_repertoire_studies").fetchall()
        return {row[0] for row in rows}

    def set_excluded_studies(self, study_ids: Iterable[str]):
        """Replace the exclusion list."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM not_repertoire_studies")
            conn.executemany(
                "INSERT INTO not_repertoire_studies (study_id) VALUES (?)",
                [(study_id,) for study_id in set(study_ids)],
            )
            conn.commit()


# Global store instance
_store: Optional[ExclusionStore] = None


def get_exclusion_store() -> ExclusionStore:
    """Get or create the global exclusion store."""
    global _store
    if _store is None:
        _store = ExclusionStore()
    return _store
