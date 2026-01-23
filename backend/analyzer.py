"""
Deviation Analyzer - Compares games against repertoire
"""
import chess
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from repertoire import Repertoire, RepertoireNode


@dataclass
class DeviationResult:
    """Result of analyzing a single game."""
    game_url: str
    opening_name: str
    result_type: str  # "deviation" or "opponent_left_book"
    move_number: int
    user_color: str  # "white" or "black"
    game_date: Optional[str] = None  # Game date (YYYY-MM-DD)
    study_name: Optional[str] = None  # Study/chapter this came from
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
        
        # Get the appropriate repertoire tree
        tree = self.repertoire.get_tree(user_color)
        current_node = tree
        
        # Check if the first move(s) match our repertoire
        # Skip games that don't start with openings we're studying
        first_move = moves[0] if moves else None
        if first_move and first_move not in current_node.children:
            # Game doesn't start with an opening from our repertoire
            return None
        
        board = chess.Board()
        move_number = 1
        
        for i, move_san in enumerate(moves):
            is_white_move = (i % 2 == 0)
            is_your_move = (is_white_move and user_color == chess.WHITE) or \
                          (not is_white_move and user_color == chess.BLACK)
            
            current_move_number = (i // 2) + 1
            
            # Check if this move exists in repertoire
            if move_san not in current_node.children:
                if is_your_move:
                    # You deviated from your repertoire
                    # Find what the correct move(s) should be
                    correct_moves = list(current_node.children.keys())
                    variation_count = len(correct_moves)
                    
                    if correct_moves:
                        # Format correct move display
                        if variation_count == 1:
                            correct_move = correct_moves[0]
                        else:
                            # Multiple variations available
                            variation_nums = ", ".join([str(i+1) for i in range(min(variation_count, 5))])
                            if variation_count > 5:
                                variation_nums += "..."
                            correct_move = f"Multiple variations ({variation_nums})"
                        
                        # Format game date from Unix timestamp
                        game_date = None
                        if game.get("date"):
                            try:
                                game_date = datetime.fromtimestamp(game.get("date")).strftime("%Y-%m-%d")
                            except (ValueError, TypeError, OSError):
                                game_date = None
                        
                        return DeviationResult(
                            game_url=game.get("url", ""),
                            opening_name=current_node.opening_name or "Unknown",
                            result_type="deviation",
                            move_number=current_move_number,
                            user_color="white" if user_color == chess.WHITE else "black",
                            game_date=game_date,
                            study_name=current_node.study_name,
                            your_move=move_san,
                            correct_move=correct_move,
                            fen=board.fen(),
                            variation_count=variation_count,
                        ).to_dict()
                else:
                    # Opponent played a move not in your repertoire
                    # Format game date from Unix timestamp
                    game_date = None
                    if game.get("date"):
                        try:
                            game_date = datetime.fromtimestamp(game.get("date")).strftime("%Y-%m-%d")
                        except (ValueError, TypeError, OSError):
                            game_date = None
                    
                    return DeviationResult(
                        game_url=game.get("url", ""),
                        opening_name=current_node.opening_name or "Unknown",
                        result_type="opponent_left_book",
                        move_number=current_move_number,
                        user_color="white" if user_color == chess.WHITE else "black",
                        game_date=game_date,
                        study_name=current_node.study_name,
                        opponent_move=move_san,
                        fen=board.fen(),
                    ).to_dict()
            
            # Move to next node in tree
            current_node = current_node.children[move_san]
            
            # Apply move to board for FEN tracking
            try:
                board.push_san(move_san)
            except ValueError:
                # Invalid move, stop analysis
                break
        
        # Game followed book entirely (or book ran out without deviation)
        return None
