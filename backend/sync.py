"""
Sync service - brings both data sources up to date: Chess.com games into the
local cache, and the user's Lichess Repertoire. See Sync in CONTEXT.md.

Each source succeeds or fails on its own; the analysis is re-run only if
something changed.
"""
import asyncio
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from game_cache import GameCache
from pipeline import RepertoireAnalysisPipeline


logger = logging.getLogger(__name__)

Month = tuple[int, int]  # (year, month)


@dataclass(frozen=True)
class GamesSyncResult:
    """The outcome of syncing a Chess.com account's games into the cache."""
    new_games: int
    failed_months: list[Month]


def _archive_month(archive_url: str) -> Optional[Month]:
    """(year, month) of a Chess.com archive URL (.../games/2024/01)."""
    parts = archive_url.rstrip("/").split("/")
    try:
        return int(parts[-2]), int(parts[-1])
    except (IndexError, ValueError):
        return None


class ChessComSync:
    """
    Syncs a Chess.com account's games into the game cache.

    Fetches every month not yet cached, every month whose fetch failed last
    time, and every month from the one of the last Sync on (its later games
    weren't played yet).
    """

    def __init__(
        self,
        cache: GameCache,
        client: Callable,
        now: Callable[[], datetime] = datetime.now,
    ):
        """
        Args:
            cache: The game cache to sync into
            client: Makes a Chess.com client (an async context manager)
            now: The current local time, for the current month
        """
        self.cache = cache
        self.client = client
        self.now = now

    async def sync(
        self,
        username: str,
        on_month: Callable[[int, int], None],
    ) -> GamesSyncResult:
        """
        Fetch the months that may hold games the cache lacks.

        Args:
            username: Chess.com username
            on_month: Called with (year, month) as each month is fetched

        Returns:
            How many games are new, and which months failed to fetch

        Raises:
            Whatever the archive listing raises (ChessComAccountNotFoundError for
            an unknown account)
        """
        today = self.now()
        current: Month = (today.year, today.month)
        status = self.cache.get_sync_status(username)
        last_synced: Optional[Month] = (
            (status["last_synced_year"], status["last_synced_month"])
            if status and status["last_synced_year"]
            else None
        )
        cached = self.cache.get_cached_months(username)
        failed_before = self.cache.get_failed_months(username)

        async with self.client() as client:
            archives = await client.get_archives(username)
            available = sorted(
                {m for m in map(_archive_month, archives) if m is not None}
            )
            to_fetch = [
                m for m in available
                if m not in cached
                or m in failed_before
                or (last_synced is not None and m >= last_synced)
                or m == current
            ]

            games_before = self.cache.count_games(username)
            failed: list[Month] = []
            for year, month in to_fetch:
                on_month(year, month)
                try:
                    games = await client.get_all_games_for_month(username, year, month)
                except Exception as e:
                    logger.warning(f"Failed to fetch {year}-{month:02d} for {username}: {e}")
                    failed.append((year, month))
                    continue
                if games:
                    self.cache.save_games(username, games, year, month)

        self.cache.record_sync(username, *current, failed_months=failed)
        return GamesSyncResult(
            new_games=self.cache.count_games(username) - games_before,
            failed_months=failed,
        )

    def last_success(self, username: str) -> Optional[int]:
        """When the account's games last synced without a failed month."""
        status = self.cache.get_sync_status(username)
        return status["last_sync_at"] if status else None

    def cached_games(self, username: str) -> int:
        """How many of the account's games are cached."""
        return self.cache.count_games(username)


class RepertoireSyncLog:
    """
    When one user's Repertoire last synced from Lichess, stored in SQLite next
    to the game cache (which records the Chess.com side).
    """

    def __init__(self, db_path: Optional[str] = None, user: str = ""):
        if db_path is None:
            db_path = Path(__file__).parent / "chess_games.db"
        self.db_path = str(db_path)
        self.user = user
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS repertoire_syncs (
                    user TEXT PRIMARY KEY,
                    last_success_at INTEGER
                )
            """)
            conn.commit()

    def last_success(self) -> Optional[int]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT last_success_at FROM repertoire_syncs WHERE user = ?",
                (self.user,),
            ).fetchone()
        return row[0] if row else None

    def record_success(self, at: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO repertoire_syncs (user, last_success_at) VALUES (?, ?)",
                (self.user, at),
            )
            conn.commit()


GapStatuses = dict[str, str]  # each Recall Gap's status, by position key


@dataclass(frozen=True)
class GapChanges:
    """How the Recall Gaps differ from the previous analysis."""
    new: int = 0
    closed: int = 0  # newly Closed
    reopened: int = 0


def gap_changes(before: GapStatuses, after: GapStatuses) -> GapChanges:
    """Count the gaps that are new, newly Closed and reopened since `before`."""
    new = closed = reopened = 0
    for key, status in after.items():
        previous = before.get(key)
        if previous is None:
            new += 1
        elif previous == "open" and status == "closed":
            closed += 1
        elif previous == "closed" and status == "open":
            reopened += 1
    return GapChanges(new, closed, reopened)


@dataclass(frozen=True)
class SyncResult:
    """What a Sync changed."""
    games_changed: bool
    repertoire_changed: bool
    new_games: int
    gaps: GapChanges


@dataclass
class SourceStatus:
    """One source's state after the last Sync in this process."""
    status: str = "never"  # "never", "ok" or "failed"
    error: Optional[str] = None

    def as_dict(self) -> dict:
        return {"status": self.status, "error": self.error}


def _error_message(error: Exception) -> str:
    return str(error) or type(error).__name__


# A Repertoire built this recently (e.g. by the page that just opened) is
# fresh enough for a Sync, and spares the Lichess rate limit
REPERTOIRE_FRESH_SECONDS = 30


@dataclass
class _AccountSyncs:
    """One Chess.com account's finished Syncs in this process."""
    chess_com: SourceStatus
    result: SyncResult
    runs: int = 0  # so a client can tell a new result


class Sync:
    """
    One user's Sync: syncs their Lichess Repertoire and the games of the
    Chess.com account it is asked for, tracks each source's status and
    last-success time, and reports progress while running.

    The account arrives with each call. A Sync running for one account
    finishes for it; a start for another remembers that account as next.
    Each account's result, Chess.com status and run count are its own.
    """

    def __init__(
        self,
        pipeline: RepertoireAnalysisPipeline,
        games: ChessComSync,
        repertoire_log: RepertoireSyncLog,
        clock: Callable[[], float],
    ):
        """
        Args:
            pipeline: The user's analysis pipeline: refreshes their
                Repertoire, and its analysis gives "what changed"
            games: Syncs a Chess.com account's games into the game cache
            repertoire_log: When the Repertoire last synced from Lichess
            clock: The current Unix time; the pipeline's own
        """
        self.pipeline = pipeline
        self.games = games
        self.repertoire_log = repertoire_log
        self.clock = clock

        self.lichess = SourceStatus()
        self.progress: Optional[str] = None
        self._running_account: Optional[str] = None  # the account syncing now
        self._next_account: Optional[str] = None  # the account waiting its turn
        self._accounts: dict[str, _AccountSyncs] = {}  # by lowercased account
        self._task: Optional[asyncio.Task] = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self, chess_com_username: str):
        """
        Start a Sync of the account in the background. While one is running
        for another account, the account runs next, replacing any other next.
        """
        if not self.running:
            self._running_account = chess_com_username
            self._task = asyncio.create_task(self._run_in_turn())
        elif chess_com_username.lower() not in {
            self._running_account.lower(),
            (self._next_account or "").lower(),
        }:
            self._next_account = chess_com_username

    async def _run_in_turn(self):
        """
        Run the account's Sync, then the account next in turn, if any; one
        that breaks doesn't stop the next.
        """
        try:
            while self._running_account is not None:
                try:
                    await self.run(self._running_account)
                except Exception as e:
                    logger.exception(f"Sync of {self._running_account} failed: {e}")
                    self.progress = None
                self._running_account, self._next_account = self._next_account, None
        finally:
            self._running_account = self._next_account = None

    async def run(self, chess_com_username: str) -> SyncResult:
        """Sync both sources; a failing source doesn't stop the other."""
        new_games = 0
        games_changed = repertoire_changed = False
        chess_com = SourceStatus()
        # Never runs an analysis, so the Repertoire refresh isn't pre-empted
        before = self.pipeline.last_gap_statuses(chess_com_username)

        try:
            games = await self.games.sync(
                chess_com_username,
                lambda year, month: self._set_progress(f"Fetching games… {year}-{month:02d}"),
            )
            new_games = games.new_games
            games_changed = new_games > 0
            if games.failed_months:
                months = ", ".join(f"{y}-{m:02d}" for y, m in games.failed_months)
                chess_com.status = "failed"
                chess_com.error = f"Could not fetch {months}"
            else:
                chess_com.status = "ok"
        except Exception as e:
            logger.warning(f"Chess.com sync failed: {e}")
            chess_com.status = "failed"
            chess_com.error = _error_message(e)

        # Before the Lichess step, so no request walks the old games meanwhile
        if games_changed:
            self.pipeline.invalidate_games()

        self._set_progress("Syncing studies…")
        try:
            repertoire_changed = await self.pipeline.refresh_repertoire(
                fresh_within=REPERTOIRE_FRESH_SECONDS
            )
            self.repertoire_log.record_success(int(self.clock()))
            self.lichess.status = "ok"
            self.lichess.error = None
        except Exception as e:
            logger.warning(f"Lichess refresh failed: {e}")
            self.lichess.status = "failed"
            self.lichess.error = _error_message(e)

        gaps = GapChanges()
        if before is not None and (games_changed or repertoire_changed):
            after = await self._gap_statuses_after(chess_com_username)
            if after is not None:
                gaps = gap_changes(before, after)

        result = SyncResult(games_changed, repertoire_changed, new_games, gaps)
        account = chess_com_username.lower()
        previous = self._accounts.get(account)
        self._accounts[account] = _AccountSyncs(chess_com, result, (previous.runs if previous else 0) + 1)
        self.progress = None
        return result

    async def _gap_statuses_after(self, chess_com_username: str) -> Optional[GapStatuses]:
        """Each Recall Gap's status after the Sync, or None if the analysis failed."""
        try:
            return await self.pipeline.gap_statuses(chess_com_username)
        except Exception as e:
            logger.warning(f"Analysis for the Sync's changes failed: {e}")
            return None

    def _set_progress(self, message: str):
        self.progress = message

    def status(self, chess_com_username: str) -> dict:
        """The Sync's state for the account, as the API reports it."""
        account = chess_com_username.lower()
        last = self._accounts.get(account)
        if self.running and self._running_account and self._running_account.lower() == account:
            running, progress = True, self.progress
        elif self.running and self._next_account and self._next_account.lower() == account:
            running, progress = True, "Waiting for another Sync…"
        else:
            running, progress = False, None

        chess_com = {
            **(last.chess_com if last else SourceStatus()).as_dict(),
            "last_success_at": self.games.last_success(chess_com_username),
        }
        lichess = {**self.lichess.as_dict(), "last_success_at": self.repertoire_log.last_success()}
        last_successes = [chess_com["last_success_at"], lichess["last_success_at"]]
        return {
            "running": running,
            "progress": progress,
            "sources": {
                "chess_com": chess_com,
                "lichess": lichess,
            },
            # The older of the two; never synced if either never was
            "last_synced_at": None if None in last_successes else min(last_successes),
            "runs": last.runs if last else 0,
            "cached_games": self.games.cached_games(chess_com_username),
            "result": (
                {
                    "games_changed": last.result.games_changed,
                    "repertoire_changed": last.result.repertoire_changed,
                    "new_games": last.result.new_games,
                    "new_gaps": last.result.gaps.new,
                    "closed_gaps": last.result.gaps.closed,
                    "reopened_gaps": last.result.gaps.reopened,
                }
                if last
                else None
            ),
        }
