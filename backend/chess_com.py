"""
Chess.com API Client
"""
import httpx
from typing import Optional
import io
import re
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
    
    async def get_all_games_for_month(
        self,
        username: str,
        year: int,
        month: int,
    ) -> list[dict]:
        """
        Fetch ALL games for a specific month without any filters.
        Used for caching - returns raw game data.
        
        Args:
            username: Chess.com username
            year: Year (e.g., 2026)
            month: Month (1-12)
        
        Returns:
            List of game dicts with all fields
        """
        month_str = str(month).zfill(2)
        response = await self._client.get(f"/player/{username}/games/{year}/{month_str}")
        response.raise_for_status()
        
        raw_games = response.json().get("games", [])
        games = []
        
        for game in raw_games:
            # Extract opening name from eco URL
            eco_url = game.get("eco", "")
            opening_name = self._extract_opening_from_eco(eco_url)
            
            # Parse PGN to extract moves
            pgn_str = game.get("pgn", "")
            parsed_game = self._parse_pgn(pgn_str)
            
            games.append({
                "url": game.get("url", ""),
                "date": game.get("end_time"),  # Unix timestamp
                "time_class": game.get("time_class", ""),
                "time_control": game.get("time_control", ""),
                "rated": game.get("rated", False),
                "white": game.get("white", {}).get("username", ""),
                "black": game.get("black", {}).get("username", ""),
                "white_rating": game.get("white", {}).get("rating", 0),
                "black_rating": game.get("black", {}).get("rating", 0),
                "result": game.get("white", {}).get("result", ""),
                "eco_url": eco_url,
                "opening_name": opening_name,
                "pgn": pgn_str,
                "moves": parsed_game.get("moves", []),
                "headers": parsed_game.get("headers", {}),
            })
        
        return games

    def _extract_opening_from_eco(self, eco_url: str) -> str:
        """
        Extract opening name from Chess.com ECO URL.
        
        Example: "https://www.chess.com/openings/Italian-Game-Two-Knights-Defense"
        Returns: "Italian Game Two Knights Defense"
        """
        if not eco_url:
            return ""
        
        # Extract the last part of the URL path
        match = re.search(r'/openings/([^/]+)$', eco_url)
        if not match:
            return ""
        
        # Convert hyphens to spaces and clean up
        opening_slug = match.group(1)
        # Remove move numbers like "-4.exd5" at the end
        opening_slug = re.sub(r'-\d+\..*$', '', opening_slug)
        # Convert to readable name
        opening_name = opening_slug.replace('-', ' ')
        
        return opening_name
    
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
