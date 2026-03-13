"""
Game Cache - SQLite storage for Chess.com games
"""
import sqlite3
import json
import time
from pathlib import Path
from typing import Optional
from datetime import datetime


class GameCache:
    """SQLite-based cache for Chess.com games."""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent / "chess_games.db"
        self.db_path = str(db_path)
        self._init_db()
    
    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    url TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    month INTEGER NOT NULL,
                    date INTEGER,
                    time_class TEXT,
                    time_control TEXT,
                    rated INTEGER,
                    white TEXT,
                    black TEXT,
                    white_rating INTEGER,
                    black_rating INTEGER,
                    result TEXT,
                    eco_url TEXT,
                    opening_name TEXT,
                    pgn TEXT,
                    moves TEXT,
                    headers TEXT,
                    fetched_at INTEGER
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_games_user 
                ON games(username)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_games_user_month 
                ON games(username, year, month)
            """)
            # Track sync status per user
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_status (
                    username TEXT PRIMARY KEY,
                    last_sync_at INTEGER,
                    last_synced_year INTEGER,
                    last_synced_month INTEGER
                )
            """)
            conn.commit()
    
    def get_cached_games(
        self,
        username: str,
        time_classes: Optional[list[str]] = None,
        rated: Optional[bool] = None,
        color: Optional[str] = None,
        from_year: Optional[int] = None,
        from_month: Optional[int] = None,
        to_year: Optional[int] = None,
        to_month: Optional[int] = None,
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
    ) -> list[dict]:
        """
        Get cached games for a user with optional filters.
        
        All filtering is done in Python for flexibility.
        """
        username_lower = username.lower()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM games WHERE username = ? ORDER BY date DESC",
                (username_lower,)
            )
            rows = cursor.fetchall()
        
        games = []
        for row in rows:
            game = dict(row)
            # Parse JSON fields
            game["moves"] = json.loads(game["moves"]) if game["moves"] else []
            game["headers"] = json.loads(game["headers"]) if game["headers"] else {}
            game["rated"] = bool(game["rated"])
            
            # Apply filters
            if time_classes and game["time_class"] not in time_classes:
                continue
            if rated is not None and game["rated"] != rated:
                continue
            
            # Color filter
            if color:
                is_white = game["white"].lower() == username_lower
                if color == "white" and not is_white:
                    continue
                if color == "black" and is_white:
                    continue
            
            # Date range filter
            game_ts = game.get("date")
            if from_ts is not None or to_ts is not None:
                if game_ts is None:
                    continue
                if from_ts is not None and game_ts < from_ts:
                    continue
                if to_ts is not None and game_ts > to_ts:
                    continue

            if from_year and from_month:
                game_date = (game["year"], game["month"])
                if game_date < (from_year, from_month):
                    continue
            if to_year and to_month:
                game_date = (game["year"], game["month"])
                if game_date > (to_year, to_month):
                    continue
            
            games.append(game)
        
        return games
    
    def save_games(self, username: str, games: list[dict], year: int, month: int):
        """Save games to the cache."""
        username_lower = username.lower()
        now = int(time.time())
        
        with sqlite3.connect(self.db_path) as conn:
            for game in games:
                conn.execute("""
                    INSERT OR REPLACE INTO games (
                        url, username, year, month, date, time_class, time_control,
                        rated, white, black, white_rating, black_rating, result,
                        eco_url, opening_name, pgn, moves, headers, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    game["url"],
                    username_lower,
                    year,
                    month,
                    game.get("date"),
                    game.get("time_class"),
                    game.get("time_control"),
                    1 if game.get("rated") else 0,
                    game.get("white"),
                    game.get("black"),
                    game.get("white_rating"),
                    game.get("black_rating"),
                    game.get("result"),
                    game.get("eco_url"),
                    game.get("opening_name"),
                    game.get("pgn"),
                    json.dumps(game.get("moves", [])),
                    json.dumps(game.get("headers", {})),
                    now,
                ))
            conn.commit()
    
    def get_sync_status(self, username: str) -> Optional[dict]:
        """Get the last sync status for a user."""
        username_lower = username.lower()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM sync_status WHERE username = ?",
                (username_lower,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_sync_status(self, username: str, year: int, month: int):
        """Update sync status after successful sync."""
        username_lower = username.lower()
        now = int(time.time())
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sync_status (
                    username, last_sync_at, last_synced_year, last_synced_month
                ) VALUES (?, ?, ?, ?)
            """, (username_lower, now, year, month))
            conn.commit()
    
    def get_cached_months(self, username: str) -> set[tuple[int, int]]:
        """Get set of (year, month) tuples that have cached games."""
        username_lower = username.lower()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT DISTINCT year, month FROM games WHERE username = ?",
                (username_lower,)
            )
            return {(row[0], row[1]) for row in cursor.fetchall()}
    
    def count_games(self, username: str) -> int:
        """Count total cached games for a user."""
        username_lower = username.lower()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM games WHERE username = ?",
                (username_lower,)
            )
            return cursor.fetchone()[0]
    
    def get_first_game_date(self, username: str) -> Optional[tuple[int, int]]:
        """Get the earliest (year, month) with games for a user."""
        username_lower = username.lower()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT MIN(year), month FROM games WHERE username = ? GROUP BY year ORDER BY year LIMIT 1",
                (username_lower,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                # Get actual minimum month for that year
                cursor = conn.execute(
                    "SELECT MIN(month) FROM games WHERE username = ? AND year = ?",
                    (username_lower, row[0])
                )
                month_row = cursor.fetchone()
                return (row[0], month_row[0]) if month_row else None
            return None
    
    def clear_user_cache(self, username: str):
        """Clear all cached games for a user."""
        username_lower = username.lower()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM games WHERE username = ?", (username_lower,))
            conn.execute("DELETE FROM sync_status WHERE username = ?", (username_lower,))
            conn.commit()


# Global cache instance
_cache: Optional[GameCache] = None


def get_game_cache() -> GameCache:
    """Get or create the global game cache instance."""
    global _cache
    if _cache is None:
        _cache = GameCache()
    return _cache
