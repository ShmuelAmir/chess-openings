"""
Chess.com API Client
"""
import httpx
from typing import Optional
import io
import chess.pgn


class ChessComClient:
    """Client for Chess.com Public API."""
    
    BASE_URL = "https://api.chess.com/pub"
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Accept": "application/json",
                "User-Agent": "ChessOpeningAnalyzer/1.0 (github.com/chess-opening-analyzer)",
            },
            timeout=30.0,
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
    
    async def get_archives(self, username: str) -> list[str]:
        """Get list of available monthly game archives."""
        response = await self._client.get(f"/player/{username}/games/archives")
        response.raise_for_status()
        return response.json().get("archives", [])
    
    async def get_games(
        self,
        username: str,
        year: int,
        month: int,
        time_class: Optional[str] = None,
        rated: Optional[bool] = None,
    ) -> list[dict]:
        """
        Fetch games for a specific month with optional filters.
        
        Args:
            username: Chess.com username
            year: Year (e.g., 2026)
            month: Month (1-12)
            time_class: Filter by time control (bullet, blitz, rapid, daily)
            rated: Filter by rated/casual
        
        Returns:
            List of game dictionaries with parsed info
        """
        month_str = str(month).zfill(2)
        response = await self._client.get(f"/player/{username}/games/{year}/{month_str}")
        response.raise_for_status()
        
        raw_games = response.json().get("games", [])
        games = []
        
        for game in raw_games:
            # Apply filters
            if time_class and game.get("time_class") != time_class:
                continue
            if rated is not None and game.get("rated") != rated:
                continue
            
            # Parse PGN to extract moves
            pgn_str = game.get("pgn", "")
            parsed_game = self._parse_pgn(pgn_str)
            
            games.append({
                "url": game.get("url", ""),
                "time_class": game.get("time_class", ""),
                "time_control": game.get("time_control", ""),
                "rated": game.get("rated", False),
                "white": game.get("white", {}).get("username", ""),
                "black": game.get("black", {}).get("username", ""),
                "white_rating": game.get("white", {}).get("rating", 0),
                "black_rating": game.get("black", {}).get("rating", 0),
                "result": game.get("white", {}).get("result", ""),
                "pgn": pgn_str,
                "moves": parsed_game.get("moves", []),
                "headers": parsed_game.get("headers", {}),
            })
        
        return games
    
    def _parse_pgn(self, pgn_str: str) -> dict:
        """Parse PGN string to extract moves and headers."""
        if not pgn_str:
            return {"moves": [], "headers": {}}
        
        try:
            game = chess.pgn.read_game(io.StringIO(pgn_str))
            if not game:
                return {"moves": [], "headers": {}}
            
            # Extract moves in SAN format
            moves = []
            board = game.board()
            for move in game.mainline_moves():
                moves.append(board.san(move))
                board.push(move)
            
            # Extract headers
            headers = dict(game.headers)
            
            return {"moves": moves, "headers": headers}
        except Exception:
            return {"moves": [], "headers": {}}
