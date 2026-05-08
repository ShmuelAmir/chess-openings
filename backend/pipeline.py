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
    async def fetch_repertoire(
        self,
        study_ids: list[str],
        study_names: list[str],
    ) -> Repertoire:
        """
        Fetch studies and build repertoire tree.
        
        Args:
            study_ids: Lichess study IDs
            study_names: Corresponding study names (for labeling in repertoire)
        
        Returns:
            Repertoire object with white/black trees and position index
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
    
    Caches repertoires by study ID set (with TTL) to avoid rebuilding on repeated requests.
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
        
        # Cache: key = frozenset(study_ids), value = (repertoire, timestamp)
        self._repertoire_cache: dict[frozenset, tuple[Repertoire, float]] = {}
    
    async def analyze(
        self,
        study_ids: list[str],
        study_names: list[str],
        username: str,
        filters: GameFilters,
    ) -> AnalysisReport:
        """
        Execute the full analysis pipeline.
        
        Args:
            study_ids: Lichess study IDs
            study_names: Corresponding study names
            username: Chess.com username
            filters: Game filtering parameters
        
        Returns:
            AnalysisReport with deviations and statistics
        """
        # Step 1: Fetch or use cached repertoire
        repertoire = await self._get_repertoire(study_ids, study_names)
        
        # Step 2: Fetch games
        games = await self.game_source.fetch_games(username, filters)
        
        # Step 3: Analyze each game
        analyzer = DeviationAnalyzer(repertoire)
        deviations = []
        
        for game in games:
            try:
                result = analyzer.analyze_game(game, username)
                if result:
                    deviations.append(result.to_dict())
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
    
    async def _get_repertoire(
        self,
        study_ids: list[str],
        study_names: list[str],
    ) -> Repertoire:
        """
        Get repertoire from cache or fetch and cache it.
        
        Args:
            study_ids: Lichess study IDs
            study_names: Corresponding study names
        
        Returns:
            Repertoire object
        """
        cache_key = frozenset(study_ids)
        now = time.time()
        
        # Check cache
        if cache_key in self._repertoire_cache:
            cached_repertoire, cached_time = self._repertoire_cache[cache_key]
            if now - cached_time < self.repertoire_ttl_seconds:
                logger.debug(f"Using cached repertoire for studies {study_ids}")
                return cached_repertoire
            else:
                # TTL expired, remove from cache
                del self._repertoire_cache[cache_key]
        
        # Fetch fresh repertoire
        logger.debug(f"Fetching fresh repertoire for studies {study_ids}")
        repertoire = await self.repertoire_source.fetch_repertoire(
            study_ids, study_names
        )
        
        # Cache it
        self._repertoire_cache[cache_key] = (repertoire, now)
        
        return repertoire
