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
    
    async def get_games_for_month(
        self,
        username: str,
        year: int,
        month: int,
        time_classes: Optional[list[str]] = None,
        rated: Optional[bool] = None,
        opening_filters: Optional[list[str]] = None,
    ) -> tuple[list[dict], int]:
        """
        Fetch games for a specific month with optional filters.
        
        Args:
            username: Chess.com username
            year: Year (e.g., 2026)
            month: Month (1-12)
            time_classes: Filter by time controls (list of: bullet, blitz, rapid, daily)
            rated: Filter by rated/casual
            opening_filters: List of opening name keywords to filter by
        
        Returns:
            Tuple of (list of game dicts, total games before opening filter)
        """
        month_str = str(month).zfill(2)
        response = await self._client.get(f"/player/{username}/games/{year}/{month_str}")
        response.raise_for_status()
        
        raw_games = response.json().get("games", [])
        games = []
        total_after_basic_filters = 0
        
        for game in raw_games:
            # Apply time class filter (multiple selection)
            if time_classes and game.get("time_class") not in time_classes:
                continue
            if rated is not None and game.get("rated") != rated:
                continue
            
            total_after_basic_filters += 1
            
            # Extract opening name from eco URL
            eco_url = game.get("eco", "")
            opening_name = self._extract_opening_from_eco(eco_url)
            
            # Apply opening filter if provided
            if opening_filters:
                if not self._matches_opening_filter(opening_name, opening_filters):
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
                "eco_url": eco_url,
                "opening_name": opening_name,
                "pgn": pgn_str,
                "moves": parsed_game.get("moves", []),
                "headers": parsed_game.get("headers", {}),
            })
        
        return games, total_after_basic_filters

    async def get_games_for_range(
        self,
        username: str,
        from_year: int,
        from_month: int,
        to_year: int,
        to_month: int,
        time_classes: Optional[list[str]] = None,
        rated: Optional[bool] = None,
        opening_filters: Optional[list[str]] = None,
    ) -> tuple[list[dict], int]:
        """
        Fetch games for a date range spanning multiple months.
        
        Args:
            username: Chess.com username
            from_year, from_month: Start of range (inclusive)
            to_year, to_month: End of range (inclusive)
            time_classes: Filter by time controls
            rated: Filter by rated/casual
            opening_filters: List of opening name keywords to filter by
        
        Returns:
            Tuple of (list of game dicts, total games before opening filter)
        """
        all_games = []
        total_games = 0
        
        # Generate list of (year, month) tuples in the range
        current_year, current_month = from_year, from_month
        
        while (current_year, current_month) <= (to_year, to_month):
            try:
                games, month_total = await self.get_games_for_month(
                    username=username,
                    year=current_year,
                    month=current_month,
                    time_classes=time_classes,
                    rated=rated,
                    opening_filters=opening_filters,
                )
                all_games.extend(games)
                total_games += month_total
            except httpx.HTTPStatusError as e:
                # 404 means no games for that month, just skip
                if e.response.status_code != 404:
                    raise
            
            # Move to next month
            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1
        
        return all_games, total_games
    
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
    
    def _matches_opening_filter(self, opening_name: str, filters: list[str]) -> bool:
        """
        Check if an opening name matches any of the filter keywords.
        
        Uses fuzzy matching - checks if key words from filter appear in opening name.
        """
        if not opening_name:
            return False
        
        opening_lower = opening_name.lower()
        
        for filter_name in filters:
            filter_lower = filter_name.lower()
            
            # Extract key words from filter (ignore common words)
            ignore_words = {'opening', 'defense', 'defence', 'attack', 'game', 'variation', 'system', 'the', 'a', 'an'}
            filter_words = [w for w in filter_lower.split() if w not in ignore_words and len(w) > 2]
            
            # Check if main keyword matches
            if filter_words:
                # Match if the main opening name word appears
                main_word = filter_words[0]
                if main_word in opening_lower:
                    return True
            
            # Also check for exact containment
            if filter_lower in opening_lower or opening_lower in filter_lower:
                return True
        
        return False
    
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
