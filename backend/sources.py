"""
Concrete implementations of RepertoireSource and GameSource.
"""

import logging
from typing import Awaitable, Callable, Optional

from pipeline import RepertoireSource, GameSource, GameFilters
from repertoire import Repertoire, RepertoireBuilder
from game_cache import GameCache
from lichess import LichessClient
from game_result import player_result


logger = logging.getLogger(__name__)


class LichessRepertoireSource(RepertoireSource):
    """
    Builds the user's Repertoire from every study they own on Lichess, except
    those marked "not repertoire".
    """
    
    def __init__(
        self,
        lichess_token: str,
        list_studies: Callable[[], Awaitable[list[dict]]],
        excluded_studies: Callable[[], set[str]],
    ):
        """
        Args:
            lichess_token: The user's Lichess token
            list_studies: Lists the user's owned studies (id, name); called on
                every rebuild, so new studies join the Repertoire
            excluded_studies: The ids of the studies marked "not repertoire";
                read on every rebuild
        """
        self.lichess_token = lichess_token
        self.list_studies = list_studies
        self.excluded_studies = excluded_studies
    
    async def fetch_repertoire(self) -> Repertoire:
        """
        Fetch every owned study not marked "not repertoire" from Lichess and
        build the repertoire trees.
        
        Returns:
            Repertoire object with white/black trees
        """
        builder = RepertoireBuilder()
        excluded = self.excluded_studies()
        studies = [s for s in await self.list_studies() if s["id"] not in excluded]
        
        async with LichessClient(token=self.lichess_token) as client:
            for study in studies:
                study_id, study_name = study["id"], study["name"]
                try:
                    logger.debug(f"Fetching study {study_id} ({study_name})")
                    # Deepen: LichessClient handles opening name normalization
                    pgn, opening_name = await client.get_study_pgn_with_normalized_name(
                        study_id=study_id,
                        study_name=study_name,
                    )
                    
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
        logger.debug(f"Built repertoire from {len(studies)} studies")
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
            List of game dicts, each with the user's result as "user_result"
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
        
        for game in games:
            user_is_white = game.get("white", "").lower() == username.lower()
            game["user_result"] = player_result(game.get("result") or "", user_is_white)

        logger.debug(f"Found {len(games)} cached games for {username}")
        return games
