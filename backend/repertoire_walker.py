"""
RepertoireWalker - Traverses repertoire trees to find positions and deviations.

This module encapsulates the logic for walking through a repertoire tree
(matching moves, tracking position state, detecting when moves leave the book).
"""
import chess
from enum import Enum
from typing import Optional, NamedTuple
from repertoire import Repertoire, RepertoireNode, position_key


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


class DeviationType(str, Enum):
    """Why a game left the book. See Deviation in CONTEXT.md."""
    PLAYER_ERROR = "player_error"
    OPPONENT_LEFT_BOOK = "opponent_left_book"
    BOOK_COMPLETED = "book_completed"


class Deviation(NamedTuple):
    """The first move of a game that was not in the repertoire (or the end of book)."""
    type: DeviationType
    position_key: str
    move_played: Optional[str]  # None when the book was completed
    book_moves: list[str]
    move_number: int
    fen: str
    position_info: PositionInfo


class InBookMove(NamedTuple):
    """A position reached on the user's move while still in book, and the move played."""
    position_key: str
    move: str


class WalkRecord(NamedTuple):
    """The outcome of walking one game through the repertoire."""
    analysed: bool
    deviation: Optional[Deviation]
    reached_in_book: list[InBookMove]


def not_analysed() -> WalkRecord:
    return WalkRecord(analysed=False, deviation=None, reached_in_book=[])


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
    
    def walk_game(
        self,
        user_color: chess.Color,
        moves: list[str],
    ) -> WalkRecord:
        """
        Walk a game's moves down the repertoire tree for the user's color.

        A game is analysed when its first move is in the tree and the user
        did not leave the book on move 1 ("not this opening"). Walking is
        path-based: a transposition into a book position by another move
        order is not recognised.
        """
        tree = self.get_tree_for_color(user_color)
        if not moves or moves[0] not in tree.children:
            return not_analysed()

        board = chess.Board()
        current_node = tree
        reached_in_book: list[InBookMove] = []

        for move_san in moves:
            is_your_move = board.turn == user_color

            if move_san not in current_node.children:
                if is_your_move and board.fullmove_number == 1:
                    return not_analysed()
                return WalkRecord(
                    analysed=True,
                    deviation=self._deviation(
                        DeviationType.PLAYER_ERROR if is_your_move else DeviationType.OPPONENT_LEFT_BOOK,
                        current_node,
                        board,
                        move_san,
                        board.fullmove_number,
                    ),
                    reached_in_book=reached_in_book,
                )

            if is_your_move:
                reached_in_book.append(InBookMove(position_key(board), move_san))

            current_node = current_node.children[move_san]
            try:
                board.push_san(move_san)
            except ValueError:
                # Invalid move, stop analysis
                return not_analysed()

        return WalkRecord(
            analysed=True,
            deviation=self._deviation(
                DeviationType.BOOK_COMPLETED,
                current_node,
                board,
                None,
                len(moves) // 2,
            ),
            reached_in_book=reached_in_book,
        )

    def _deviation(
        self,
        deviation_type: DeviationType,
        node: RepertoireNode,
        board: chess.Board,
        move_played: Optional[str],
        move_number: int,
    ) -> Deviation:
        position_info = self.get_position_info(node)
        return Deviation(
            type=deviation_type,
            position_key=position_key(board),
            move_played=move_played,
            book_moves=position_info.available_moves,
            move_number=move_number,
            fen=board.fen(),
            position_info=position_info,
        )
