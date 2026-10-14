"""
The app's Users, each identified by their Lichess token: their Lichess
account, their analysis pipeline and their Sync, kept between requests. See
User in CONTEXT.md.
"""
import asyncio
import hashlib
import time
from functools import cached_property

from chess_com import ChessComClient
from drill_attempts import DrillAttemptStore
from exclusions import ExclusionStore
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
    One User: their Lichess account, whose "not repertoire" exclusion list and
    Drill Attempts they keep; the pipeline holding their cached Repertoire and
    last analysis; and their one Sync, of whichever Chess.com account each
    request names.
    """

    def __init__(
        self,
        key: str,
        account: str,
        pipeline: RepertoireAnalysisPipeline,
        games_sync: ChessComSync,
        exclusions: ExclusionStore,
        drill_attempts: DrillAttemptStore,
    ):
        """
        Args:
            key: The User's token key
            account: The User's Lichess account (lowercase), under which their
                exclusions, Drill Attempts and Lichess Sync are kept, so a new
                token for the same account finds them
            pipeline: The User's analysis pipeline, reading `exclusions` and
                `drill_attempts`; its clock is the Sync's too
            games_sync: Syncs a Chess.com account's games into the game cache
            exclusions: The account's "not repertoire" exclusion list
            drill_attempts: The account's Drill Attempts
        """
        self.key = key
        self.account = account
        self.pipeline = pipeline
        self.games_sync = games_sync
        self.exclusions = exclusions
        self.drill_attempts = drill_attempts

    @cached_property
    def sync(self) -> Sync:
        """The User's one Sync, made on first use (its log opens the database)."""
        return Sync(self.pipeline, self.games_sync, RepertoireSyncLog(user=self.account), self.pipeline.clock)


_users: dict[str, User] = {}
# Each token key's Lichess account, asked of Lichess once
_accounts: dict[str, str] = {}


async def account_for(token: str) -> str:
    """
    The Lichess account (lowercase) the token belongs to. Lichess refusing the
    token raises its HTTPStatusError.
    """
    key = token_key(token)
    if key not in _accounts:
        async with LichessClient(token=token) as client:
            account = await client.get_account()
        _accounts[key] = account["username"].lower()
    return _accounts[key]


async def user_for(token: str) -> User:
    """
    The User this Lichess token belongs to, made on their first request, when
    Lichess is asked whose token it is.
    """
    key = token_key(token)
    if key not in _users:
        account = await account_for(token)
        if key not in _users:  # another request may have made them meanwhile
            _users[key] = _new_user(token, account)
    return _users[key]


def _new_user(token: str, account: str) -> User:
    exclusions = ExclusionStore(account)
    drill_attempts = DrillAttemptStore(account)
    return User(
        token_key(token),
        account,
        RepertoireAnalysisPipeline(
            repertoire_source=LichessRepertoireSource(
                lichess_token=token,
                list_studies=lambda: fetch_studies_afresh(token),
                excluded_studies=exclusions.excluded_studies,
            ),
            game_source=CacheGameSource(get_game_cache()),
            drill_attempts=drill_attempts.attempts,
        ),
        ChessComSync(get_game_cache(), client=ChessComClient),
        exclusions,
        drill_attempts,
    )


def invalidate_analyses():
    """
    Drop every User's last analysis, after a Chess.com account's cached games
    changed without a Sync (whose User is unknown).
    """
    for user in _users.values():
        user.pipeline.invalidate_games()
