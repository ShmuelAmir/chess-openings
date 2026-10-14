"""
The app's Users, each identified by their Lichess token: their analysis
pipeline and their Syncs, kept between requests. See User in CONTEXT.md.
"""
import asyncio
import hashlib
import time

from chess_com import ChessComClient
from drill_attempts import get_drill_attempt_store
from exclusions import get_exclusion_store
from game_cache import get_game_cache
from lichess import LichessClient
from pipeline import RepertoireAnalysisPipeline
from sources import CacheGameSource, LichessRepertoireSource
from sync import ChessComSync, RepertoireSyncLog, Sync


def token_key(token: str) -> str:
    """The key a Lichess token is known by, so the token itself is never kept as one."""
    return hashlib.sha256(token.encode()).hexdigest()


# Short-lived cache of a token's studies, so repeated page loads / duplicate
# frontend requests don't each hit the Lichess API (which rate-limits hard).
STUDIES_CACHE_TTL = 60  # seconds
_studies_cache: dict[str, tuple[float, list[dict]]] = {}
_studies_locks: dict[str, asyncio.Lock] = {}


async def _list_studies_into_cache(token: str) -> list[dict]:
    """List the token owner's studies from Lichess, into the cache."""
    async with LichessClient(token=token) as client:
        account = await client.get_account()
        studies = await client.get_user_studies(account["username"])

    _studies_cache[token_key(token)] = (time.monotonic(), studies)
    return studies


async def fetch_studies_cached(token: str) -> list[dict]:
    """
    Return the token owner's studies, using a short-lived cache.

    Concurrent callers for the same token share a single upstream request.
    """
    key = token_key(token)

    async with _studies_locks.setdefault(key, asyncio.Lock()):
        cached = _studies_cache.get(key)
        if cached and time.monotonic() - cached[0] < STUDIES_CACHE_TTL:
            return cached[1]

        return await _list_studies_into_cache(token)


async def fetch_studies_afresh(token: str) -> list[dict]:
    """
    Return the token owner's studies as Lichess lists them now, so new ones
    join the Repertoire being built; the cache then holds this listing.
    """
    async with _studies_locks.setdefault(token_key(token), asyncio.Lock()):
        return await _list_studies_into_cache(token)


class User:
    """
    One User: the pipeline holding their cached Repertoire and last analysis,
    and their Sync of each Chess.com account.
    """

    def __init__(self, key: str, pipeline: RepertoireAnalysisPipeline, games_sync: ChessComSync):
        """
        Args:
            key: The User's token key, under which their Lichess Sync is logged
            pipeline: The User's analysis pipeline; its clock is the Syncs' too
            games_sync: Syncs a Chess.com account's games into the game cache
        """
        self.key = key
        self.pipeline = pipeline
        self.games_sync = games_sync
        self._syncs: dict[str, Sync] = {}

    def sync(self, chess_com_username: str) -> Sync:
        """The Sync of this User's Lichess Repertoire and the account's games."""
        account = chess_com_username.lower()
        if account not in self._syncs:
            self._syncs[account] = Sync(
                self.pipeline,
                self.games_sync,
                chess_com_username,
                RepertoireSyncLog(user=self.key),
                self.pipeline.clock,
            )
        return self._syncs[account]


_users: dict[str, User] = {}


def user_for(token: str) -> User:
    """The User this Lichess token belongs to, made on their first request."""
    key = token_key(token)
    if key not in _users:
        _users[key] = User(
            key,
            RepertoireAnalysisPipeline(
                repertoire_source=LichessRepertoireSource(
                    lichess_token=token,
                    list_studies=lambda: fetch_studies_afresh(token),
                    excluded_studies=get_exclusion_store().excluded_studies,
                ),
                game_source=CacheGameSource(get_game_cache()),
                drill_attempts=get_drill_attempt_store().attempts,
            ),
            ChessComSync(get_game_cache(), client=ChessComClient),
        )
    return _users[key]


def invalidate_analyses():
    """
    Drop every User's last analysis, after a Chess.com account's cached games
    changed without a Sync (whose User is unknown).
    """
    for user in _users.values():
        user.pipeline.invalidate_games()
