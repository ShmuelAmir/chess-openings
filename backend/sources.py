"""
Concrete implementations of RepertoireSource and GameSource.
"""

import logging
from typing import Optional

from pipeline import RepertoireSource, GameSource, GameFilters
from repertoire import Repertoire, RepertoireBuilder
from game_cache import GameCache
from lichess import LichessClient
from opening_normalizer import OpeningNormalizer


logger = logging.getLogger(__name__)


class LichessRepertoireSource(RepertoireSource):
    """Fetches and builds repertoires from Lichess studies."""
    
    def __init__(self, lichess_token: str):
        self.lichess_token = lichess_token
    
    async def fetch_repertoire(
        self,
        study_ids: list[str],
        study_names: list[str],
    ) -> Repertoire:
        """
        Fetch studies from Lichess and build repertoire tree.
        
        Args:
            study_ids: Lichess study IDs
            study_names: Corresponding study names
        
        Returns:
            Repertoire object with white/black trees
        """
        builder = RepertoireBuilder()
        
        async with LichessClient(token=self.lichess_token) as client:
            for study_id, study_name in zip(study_ids, study_names):
                try:
                    logger.debug(f"Fetching study {study_id} ({study_name})")
                    pgn = await client.get_study_pgn(study_id)
                    
                    # Extract and normalize opening name from study name
                    # Format: "Sicilian Defense" or "Vienna: Main Line"
                    opening_name = OpeningNormalizer.normalize(study_name)
                    
                    builder.add_study(
                        pgn=pgn,
                        opening_name=opening_name,
                        study_name=study_name,
                        study_id=study_id,
                    )
                except Exception as e:
                    logger.error(f"Failed to fetch study {study_id}: {e}")
                    raise
        
        repertoire = builder.build()
        logger.debug(f"Built repertoire from {len(study_ids)} studies")
        return repertoire


class CacheGameSource(GameSource):
    """Fetches games from the local cache."""
    
    def __init__(self, game_cache: Optional[GameCache] = None):
        self.game_cache = game_cache or GameCache()
    
    async def fetch_games(
        self,
        username: str,
        filters: GameFilters,
    ) -> list[dict]:
        """
        Fetch games from cache with applied filters.
        
        Args:
            username: Chess.com username
            filters: Game filtering parameters
        
        Returns:
            List of game dicts
        """
        logger.debug(f"Fetching games for {username} with filters: {filters}")
        
        games = self.game_cache.get_cached_games(
            username=username,
            time_classes=filters.time_classes,
            rated=filters.rated,
            color=filters.color,
            from_year=filters.from_year,
            from_month=filters.from_month,
            to_year=filters.to_year,
            to_month=filters.to_month,
            from_ts=filters.from_ts,
            to_ts=filters.to_ts,
        )
        
        logger.debug(f"Found {len(games)} cached games for {username}")
        return games
