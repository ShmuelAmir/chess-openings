"""
Concrete implementations of RepertoireSource and GameSource.
"""

import logging
from typing import Awaitable, Callable, Optional

import chess

from games import Game
from pipeline import RepertoireSource, GameSource
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
            list_studies: Lists the user's owned studies (id, name) from
                Lichess afresh; called on every rebuild, so new studies join
                the Repertoire
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
    """Reads the user's games from the local cache."""
    
    def __init__(self, game_cache: Optional[GameCache] = None):
        self.game_cache = game_cache or GameCache()
    
    async def games(self, username: str) -> list[Game]:
        """
        Every cached game of the user's, newest first.
        
        Args:
            username: Chess.com username
        """
        games = [_game(row, username) for row in self.game_cache.get_cached_games(username)]
        logger.debug(f"Found {len(games)} cached games for {username}")
        return games


def _game(row: dict, username: str) -> Game:
    """
    A cached game as the user's Game: the one place their color and result
    are worked out from the players' names and White's result code.
    """
    user_is_white = (row.get("white") or "").lower() == username.lower()
    return Game(
        url=row["url"],
        date=row.get("date"),
        month=(row["year"], row["month"]),
        time_class=row.get("time_class") or "",
        rated=bool(row.get("rated")),
        opening_name=row.get("opening_name") or "",
        moves=tuple(row.get("moves") or ()),
        color=chess.WHITE if user_is_white else chess.BLACK,
        result=player_result(row.get("result") or "", user_is_white),
    )
