"""
Repertoire Analysis Pipeline - Orchestrates the full analysis workflow.
Abstracts fetching repertoire and games from the orchestration logic.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import logging

import chess

from repertoire import Repertoire
from repertoire_walker import RepertoireWalker
from recall_gaps import RecallFilters, RecallView, WalkedGame, aggregate


logger = logging.getLogger(__name__)


@dataclass
class GameFilters:
    """Game filtering parameters."""
    time_classes: Optional[list[str]] = None
    rated: Optional[bool] = None
    color: Optional[str] = None  # "white", "black", or None for both
    from_year: Optional[int] = None
    from_month: Optional[int] = None
    to_year: Optional[int] = None
    to_month: Optional[int] = None
    from_ts: Optional[int] = None
    to_ts: Optional[int] = None


class RepertoireSource(ABC):
    """Abstract interface for fetching and building repertoires."""
    
    @abstractmethod
    async def fetch_repertoire(self) -> Repertoire:
        """
        Fetch the user's studies and build their Repertoire.
        
        Returns:
            Repertoire object with white/black trees and study membership
        """
        ...


class GameSource(ABC):
    """Abstract interface for fetching games."""
    
    @abstractmethod
    async def fetch_games(
        self,
        username: str,
        filters: GameFilters,
    ) -> list[dict]:
        """
        Fetch games matching filters.
        
        Args:
            username: Chess.com username
            filters: Game filtering parameters
        
        Returns:
            List of game dicts with 'moves', 'white', 'black', 'url', and
            the user's result as 'user_result' ("win", "loss" or "draw")
        """
        ...


class RepertoireAnalysisPipeline:
    """
    Orchestrates the full analysis pipeline: fetch repertoire, fetch games, analyze.
    
    Caches the user's Repertoire (with TTL) to avoid rebuilding on repeated requests.
    A study created on Lichess joins the Repertoire at the next rebuild.
    """
    
    def __init__(
        self,
        repertoire_source: RepertoireSource,
        game_source: GameSource,
        repertoire_ttl_seconds: int = 3600,  # 1 hour TTL
    ):
        self.repertoire_source = repertoire_source
        self.game_source = game_source
        self.repertoire_ttl_seconds = repertoire_ttl_seconds
        
        # The user's Repertoire and when it was built
        self._repertoire_cache: Optional[tuple[Repertoire, float]] = None
        # Bumped by each rebuild, so a fetch begun before it isn't cached
        self._repertoire_generation = 0
        # The last analysis: (username, the Repertoire it walked, walked games),
        # reused until the games or the Repertoire change
        self._walked_cache: Optional[tuple[str, Repertoire, list[WalkedGame]]] = None
        # The Repertoire fetch in flight: (generation, when it began, task)
        self._inflight: Optional[tuple[int, float, asyncio.Future]] = None
    
    async def recall_view(
        self,
        username: str,
        filters: RecallFilters,
    ) -> RecallView:
        """
        Walk every cached game through the user's Repertoire and group the
        player errors into ranked Recall Gaps.

        All games are walked; the filters only decide which ones are shown
        and counted.

        Args:
            username: Chess.com username
            filters: The recall view's Game Filters

        Returns:
            RecallView with the ranked Recall Gaps and the totals
        """
        repertoire = await self._get_repertoire()
        walked = await self._walk_games(username, repertoire)
        return aggregate(walked, filters, repertoire.study_locations)

    async def _walk_games(self, username: str, repertoire: Repertoire) -> list[WalkedGame]:
        """Every cached game walked through the Repertoire, reusing the last analysis."""
        if self._walked_cache is not None:
            cached_username, cached_repertoire, cached_walked = self._walked_cache
            if cached_username == username.lower() and cached_repertoire is repertoire:
                return cached_walked

        games = await self.game_source.fetch_games(username, GameFilters())
        walker = RepertoireWalker(repertoire)

        walked = []
        for game in games:
            try:
                is_white = game.get("white", "").lower() == username.lower()
                color = chess.WHITE if is_white else chess.BLACK
                moves = game.get("moves", [])
                walked.append(WalkedGame(
                    url=game.get("url", ""),
                    date=game.get("date") or 0,
                    time_class=game.get("time_class", ""),
                    rated=bool(game.get("rated")),
                    result=game.get("user_result", ""),
                    moves=moves,
                    color=color,
                    record=walker.walk_game(color, moves),
                ))
            except Exception as e:
                # Log and continue on individual game analysis failures
                logger.warning(
                    f"Failed to analyze game {game.get('url', 'unknown')}: {e}"
                )

        self._walked_cache = (username.lower(), repertoire, walked)
        return walked

    async def study_colors(self) -> dict[str, chess.Color]:
        """The color of each study in the user's Repertoire, by study id."""
        return (await self._get_repertoire()).study_colors
    
    async def refresh_repertoire(self, fresh_within: float = 0) -> bool:
        """
        Rebuild the Repertoire from its source now (a Sync), keeping the
        previous one, and its analysis, if nothing changed. A build already
        in flight is joined rather than repeated.

        Args:
            fresh_within: Skip the rebuild if the cached Repertoire was
                fetched less than this many seconds ago

        Returns:
            Whether the Repertoire changed
        """
        previous = None
        if self._repertoire_cache is not None:
            previous, fetched_at = self._repertoire_cache
            if time.time() - fetched_at < fresh_within:
                return False

        generation = self._repertoire_generation
        repertoire, started = await self._fetch_repertoire()
        if generation != self._repertoire_generation:
            # Invalidated while fetching: the next request rebuilds it
            return True

        changed = repertoire != previous
        self._repertoire_cache = (repertoire if changed else previous, started)
        return changed

    def invalidate_games(self):
        """Drop the last analysis, so the next request walks the games afresh."""
        self._walked_cache = None

    def invalidate_repertoire(self):
        """
        Drop the cached Repertoire, so the next request builds it afresh
        (e.g. after the "not repertoire" exclusion list changed).
        """
        self._repertoire_cache = None
        self._repertoire_generation += 1

    async def _get_repertoire(self) -> Repertoire:
        """
        Get the user's Repertoire from cache or fetch and cache it.
        
        Returns:
            Repertoire object
        """
        now = time.time()
        
        if self._repertoire_cache is not None:
            cached_repertoire, cached_time = self._repertoire_cache
            if now - cached_time < self.repertoire_ttl_seconds:
                logger.debug("Using cached repertoire")
                return cached_repertoire
        
        logger.debug("Fetching fresh repertoire")
        generation = self._repertoire_generation
        repertoire, started = await self._fetch_repertoire()
        if generation == self._repertoire_generation:
            self._repertoire_cache = (repertoire, started)
        
        return repertoire

    async def _fetch_repertoire(self) -> tuple[Repertoire, float]:
        """
        Fetch the Repertoire from its source, joining a fetch already in
        flight unless the Repertoire was invalidated since it began.

        Returns:
            The Repertoire, and when its fetch began
        """
        generation = self._repertoire_generation
        if self._inflight is not None and self._inflight[0] == generation:
            _, started, task = self._inflight
        else:
            started = time.time()
            task = asyncio.ensure_future(self.repertoire_source.fetch_repertoire())
            self._inflight = (generation, started, task)

            def done(finished: asyncio.Future):
                if self._inflight is not None and self._inflight[2] is finished:
                    self._inflight = None

            task.add_done_callback(done)

        # Shielded: one caller giving up doesn't cancel the others' fetch
        return await asyncio.shield(task), started
