"""
Repertoire Analysis Pipeline - Orchestrates the full analysis workflow.
Abstracts fetching repertoire and games from the orchestration logic.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import logging

import chess

from repertoire import Repertoire, side_to_move
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
            List of game dicts with 'moves', 'white', 'black', 'url', etc.
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
                    moves=moves,
                    record=walker.walk_game(color, moves),
                ))
            except Exception as e:
                # Log and continue on individual game analysis failures
                logger.warning(
                    f"Failed to analyze game {game.get('url', 'unknown')}: {e}"
                )

        def studies_of(key: str) -> set[str]:
            # A Recall Gap is a position on the user's move, so its side to
            # move is the user's color and picks the tree.
            return repertoire.studies_containing(key, side_to_move(key))

        return aggregate(walked, filters, studies_of)
    
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
        repertoire = await self.repertoire_source.fetch_repertoire()
        self._repertoire_cache = (repertoire, now)
        
        return repertoire
