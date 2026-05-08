"""
Deviation Analyzer - Compares games against repertoire
"""
import chess
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from repertoire import Repertoire
from repertoire_walker import RepertoireWalker


@dataclass
class DeviationResult:
    """Result of analyzing a single game."""
    game_url: str
    opening_name: str
    result_type: str  # "deviation", "opponent_left_book", or "book_completed"
    move_number: int
    user_color: str  # "white" or "black"
    game_date: Optional[str] = None  # Game date (YYYY-MM-DD)
    study_name: Optional[str] = None  # Study/chapter this came from
    study_id: Optional[str] = None  # Lichess study ID
    chapter_id: Optional[str] = None  # Lichess chapter ID
    your_move: Optional[str] = None  # What you played (for deviations)
    correct_move: Optional[str] = None  # What you should have played
    opponent_move: Optional[str] = None  # What opponent played (when they left book)
    fen: Optional[str] = None  # Position FEN for analysis link
    variation_count: Optional[int] = None  # Number of variations available
    
    def to_dict(self) -> dict:
        return {
            "game_url": self.game_url,
            "opening_name": self.opening_name,
            "result_type": self.result_type,
            "move_number": self.move_number,
            "user_color": self.user_color,
            "game_date": self.game_date,
            "study_name": self.study_name,
            "study_id": self.study_id,
            "study_url": f"https://lichess.org/study/{self.study_id}" if self.study_id else None,
            "chapter_id": self.chapter_id,
            "chapter_url": (
                f"https://lichess.org/study/{self.study_id}/{self.chapter_id}"
                if self.study_id and self.chapter_id
                else None
            ),
            "your_move": self.your_move,
            "correct_move": self.correct_move,
            "opponent_move": self.opponent_move,
            "fen": self.fen,
            "variation_count": self.variation_count,
            "analysis_url": f"https://lichess.org/analysis/{self.fen.replace(' ', '_')}" if self.fen else None,
        }


class DeviationAnalyzer:
    """Analyzes games to find deviations from repertoire."""
    
    def __init__(self, repertoire: Repertoire):
        self.repertoire = repertoire
        self.walker = RepertoireWalker(repertoire)
    
    def analyze_game(self, game: dict, username: str) -> Optional[dict]:
        """
        Analyze a single game and find the first deviation or out-of-book position.
        
        Args:
            game: Game dict with 'moves', 'white', 'black', 'url' etc.
            username: The user's Chess.com username to determine their color
        
        Returns:
            DeviationResult dict if deviation found, None if game followed book entirely
            or if the game doesn't start with moves from our repertoire
        """
        moves = game.get("moves", [])
        if not moves:
            return None
        
        # Determine user's color
        white_player = game.get("white", "").lower()
        username_lower = username.lower()
        
        if white_player == username_lower:
            user_color = chess.WHITE
        else:
            user_color = chess.BLACK
        
        # Use walker to find deviations
        deviation = self.walker.find_deviation(user_color, moves)
        
        if deviation is None:
            return None
        
        # Format game date from Unix timestamp
        game_date = None
        if game.get("date"):
            try:
                game_date = datetime.fromtimestamp(game.get("date")).strftime("%Y-%m-%d")
            except (ValueError, TypeError, OSError):
                game_date = None
        
        game_opening_name = game.get("opening_name") or None
        
        # Build result based on deviation type
        if deviation.deviation_type == "deviation":
            # User played a move not in repertoire
            variation_count = deviation.position_info.variation_count
            
            # Format correct move display
            if variation_count == 1:
                correct_move = deviation.expected_moves[0]
            elif variation_count > 1:
                moves_display = ", ".join(deviation.expected_moves[:5])
                if variation_count > 5:
                    moves_display += ", ..."
                correct_move = moves_display
            else:
                correct_move = None
            
            # Skip move 1 deviations - that's "not this opening", not a deviation
            if deviation.move_number == 1:
                return None
            
            return DeviationResult(
                game_url=game.get("url", ""),
                opening_name=deviation.position_info.opening_name or game_opening_name or "Unknown",
                result_type="deviation",
                move_number=deviation.move_number,
                user_color="white" if user_color == chess.WHITE else "black",
                game_date=game_date,
                study_name=deviation.position_info.study_name,
                study_id=deviation.position_info.study_id,
                chapter_id=deviation.position_info.chapter_id,
                your_move=deviation.actual_move,
                correct_move=correct_move,
                fen=deviation.fen,
                variation_count=variation_count,
            ).to_dict()
        
        elif deviation.deviation_type == "opponent_left_book":
            # Opponent played a move not in repertoire
            if deviation.move_number == 1:
                # Different opening family, skip
                return None
            
            variation_count = deviation.position_info.variation_count
            
            # Format correct move display
            if variation_count == 1:
                correct_move = deviation.expected_moves[0]
            elif variation_count > 1:
                moves_display = ", ".join(deviation.expected_moves[:5])
                if variation_count > 5:
                    moves_display += ", ..."
                correct_move = moves_display
            else:
                correct_move = None
            
            return DeviationResult(
                game_url=game.get("url", ""),
                opening_name=(
                    game_opening_name
                    if deviation.move_number == 1 and game_opening_name
                    else (deviation.position_info.opening_name or game_opening_name or "Unknown")
                ),
                result_type="opponent_left_book",
                move_number=deviation.move_number,
                user_color="white" if user_color == chess.WHITE else "black",
                game_date=game_date,
                study_name=deviation.position_info.study_name,
                study_id=deviation.position_info.study_id,
                chapter_id=deviation.position_info.chapter_id,
                opponent_move=deviation.actual_move,
                correct_move=correct_move,
                variation_count=variation_count,
                fen=deviation.fen,
            ).to_dict()
        
        else:  # book_completed
            return DeviationResult(
                game_url=game.get("url", ""),
                opening_name=deviation.position_info.opening_name or game_opening_name or "Unknown",
                result_type="book_completed",
                move_number=max(1, deviation.move_number),
                user_color="white" if user_color == chess.WHITE else "black",
                game_date=game_date,
                study_name=deviation.position_info.study_name,
                study_id=deviation.position_info.study_id,
                chapter_id=deviation.position_info.chapter_id,
                correct_move="All book moves correct",
                fen=deviation.fen,
                variation_count=0,
            ).to_dict()
