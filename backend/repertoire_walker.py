"""
RepertoireWalker - Traverses repertoire trees to find positions and deviations.

This module encapsulates the logic for walking through a repertoire tree
(matching moves, tracking position state, detecting when moves leave the book).
"""
import chess
from typing import Optional, NamedTuple
from repertoire import Repertoire, RepertoireNode


class WalkerPosition(NamedTuple):
    """Current position state while walking the repertoire tree."""
    node: RepertoireNode
    board: chess.Board
    move_number: int
    is_your_move: bool


class PositionInfo(NamedTuple):
    """Information about a repertoire position."""
    opening_name: Optional[str]
    study_name: Optional[str]
    study_id: Optional[str]
    chapter_id: Optional[str]
    available_moves: list[str]
    variation_count: int


class DeviationInfo(NamedTuple):
    """Information about a move deviation or end of book."""
    deviation_type: str  # "deviation", "opponent_left_book", or "book_completed"
    move_number: int
    is_your_move: bool
    actual_move: Optional[str]
    expected_moves: list[str]
    fen: str
    position_info: PositionInfo


class RepertoireWalker:
    """Walks through repertoire trees to analyze game moves against the book."""
    
    def __init__(self, repertoire: Repertoire):
        self.repertoire = repertoire
    
    def get_tree_for_color(self, color: chess.Color) -> RepertoireNode:
        """Get the repertoire tree for a specific color."""
        return self.repertoire.get_tree(color)
    
    def walk_to_move(
        self,
        node: RepertoireNode,
        move_san: str,
        board: chess.Board,
    ) -> Optional[WalkerPosition]:
        """
        Walk from current node to the next position via a move.
        
        Args:
            node: Current repertoire node
            move_san: Move in algebraic notation
            board: Current chess board position
        
        Returns:
            WalkerPosition if move is in repertoire, None if move leaves the book
        """
        if move_san not in node.children:
            return None
        
        next_node = node.children[move_san]
        next_board = board.copy()
        
        try:
            next_board.push_san(move_san)
        except ValueError:
            # Invalid move
            return None
        
        # Calculate if next move is user's turn (alternates each move)
        next_is_your_turn = not node.is_your_turn
        
        return WalkerPosition(
            node=next_node,
            board=next_board,
            move_number=(board.fullmove_number if board.turn == chess.BLACK else board.fullmove_number + 1),
            is_your_move=next_is_your_turn,
        )
    
    def get_position_info(self, node: RepertoireNode) -> PositionInfo:
        """
        Get metadata about a repertoire position.
        
        Args:
            node: Repertoire node to analyze
        
        Returns:
            PositionInfo with opening, study, and available moves
        """
        available_moves = list(node.children.keys())
        variation_count = len(available_moves)
        
        return PositionInfo(
            opening_name=node.opening_name,
            study_name=node.study_name,
            study_id=node.study_id,
            chapter_id=node.chapter_id,
            available_moves=available_moves,
            variation_count=variation_count,
        )
    
    def find_deviation(
        self,
        user_color: chess.Color,
        moves: list[str],
    ) -> Optional[DeviationInfo]:
        """
        Walk through game moves and find the first deviation from repertoire.
        
        Args:
            user_color: User's playing color (WHITE or BLACK)
            moves: List of moves in the game (algebraic notation)
        
        Returns:
            DeviationInfo if deviation found, None if game stayed in book
        """
        if not moves:
            return None
        
        tree = self.get_tree_for_color(user_color)
        board = chess.Board()
        current_node = tree
        
        # Check if game starts with a repertoire opening
        first_move = moves[0]
        if first_move not in current_node.children:
            # Game doesn't start with an opening from repertoire
            return None
        
        # Walk through moves one by one
        for i, move_san in enumerate(moves):
            is_white_move = (i % 2 == 0)
            is_your_move = (is_white_move and user_color == chess.WHITE) or \
                          (not is_white_move and user_color == chess.BLACK)
            
            move_number = (i // 2) + 1
            
            # Check if this move is in the book
            if move_san not in current_node.children:
                # Move leaves the book
                position_info = self.get_position_info(current_node)
                
                return DeviationInfo(
                    deviation_type="deviation" if is_your_move else "opponent_left_book",
                    move_number=move_number,
                    is_your_move=is_your_move,
                    actual_move=move_san,
                    expected_moves=position_info.available_moves,
                    fen=board.fen(),
                    position_info=position_info,
                )
            
            # Move is in the book, advance to next position
            current_node = current_node.children[move_san]
            
            try:
                board.push_san(move_san)
            except ValueError:
                # Invalid move, stop analysis
                return None
        
        # Game followed the book for all moves
        position_info = self.get_position_info(current_node)
        
        return DeviationInfo(
            deviation_type="book_completed",
            move_number=len(moves) // 2,
            is_your_move=False,
            actual_move=None,
            expected_moves=position_info.available_moves,
            fen=board.fen(),
            position_info=position_info,
        )
