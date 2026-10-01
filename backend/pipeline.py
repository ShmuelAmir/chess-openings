"""
Repertoire Analysis Pipeline - Orchestrates the full analysis workflow.
Abstracts fetching repertoire and games from the orchestration logic.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import logging

from repertoire import Repertoire
from analyzer import DeviationAnalyzer, DeviationResult


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


@dataclass
class AnalysisReport:
    """Result of analyzing all games against repertoire."""
    deviations: list[dict] = field(default_factory=list)
    total_games_analyzed: int = 0
    games_with_deviations: int = 0
    

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
    
    async def analyze(
        self,
        username: str,
        filters: GameFilters,
    ) -> AnalysisReport:
        """
        Execute the full analysis pipeline.
        
        Args:
            username: Chess.com username
            filters: Game filtering parameters
        
        Returns:
            AnalysisReport with deviations and statistics
        """
        # Step 1: Fetch or use cached repertoire
        repertoire = await self._get_repertoire()
        
        # Step 2: Fetch games
        games = await self.game_source.fetch_games(username, filters)
        
        # Step 3: Analyze each game
        analyzer = DeviationAnalyzer(repertoire)
        deviations = []
        
        for game in games:
            try:
                result = analyzer.analyze_game(game, username)
                if not result:
                    continue

                # Analyzer may return either a DeviationResult object
                # (with a to_dict() method) or a plain dict. Handle both.
                if hasattr(result, "to_dict") and callable(getattr(result, "to_dict")):
                    deviations.append(result.to_dict())
                elif isinstance(result, dict):
                    deviations.append(result)
                else:
                    # Unknown result type; log and skip
                    logger.warning(
                        f"Analyzer returned unexpected result type for game {game.get('url', 'unknown')}: {type(result)}"
                    )
            except Exception as e:
                # Log and continue on individual game analysis failures
                logger.warning(
                    f"Failed to analyze game {game.get('url', 'unknown')}: {e}"
                )
                continue
        
        # Step 4: Compile report
        report = AnalysisReport(
            deviations=deviations,
            total_games_analyzed=len(games),
            games_with_deviations=len(deviations),
        )
        
        return report
    
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
