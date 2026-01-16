"""
Repertoire Parser - Builds a move tree from Lichess study PGNs
"""
import io
import chess
import chess.pgn
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RepertoireNode:
    """A node in the repertoire tree."""
    # For opponent moves: multiple possible moves they can play
    # For your moves: exactly one correct response
    children: dict[str, "RepertoireNode"] = field(default_factory=dict)
    # The opening/study this line belongs to
    opening_name: Optional[str] = None
    # Is this a position where it's your turn to move?
    is_your_turn: bool = False


@dataclass
class Repertoire:
    """Complete repertoire with separate trees for White and Black."""
    white_tree: RepertoireNode = field(default_factory=RepertoireNode)
    black_tree: RepertoireNode = field(default_factory=RepertoireNode)
    
    def get_tree(self, color: chess.Color) -> RepertoireNode:
        """Get the repertoire tree for a specific color."""
        return self.white_tree if color == chess.WHITE else self.black_tree


class RepertoireBuilder:
    """Builds a repertoire from Lichess study PGNs."""
    
    def __init__(self):
        self.repertoire = Repertoire()
        self._studies: list[tuple[str, str]] = []  # (pgn, opening_name)
    
    def add_study(self, pgn: str, opening_name: str):
        """Add a study PGN to be processed."""
        self._studies.append((pgn, opening_name))
    
    def build(self) -> Repertoire:
        """Process all studies and build the repertoire trees."""
        for pgn, opening_name in self._studies:
            self._process_study(pgn, opening_name)
        return self.repertoire
    
    def _process_study(self, pgn: str, opening_name: str):
        """Process a single study PGN (may contain multiple chapters/games)."""
        pgn_io = io.StringIO(pgn)
        
        while True:
            game = chess.pgn.read_game(pgn_io)
            if game is None:
                break
            
            # Determine which color this study is for based on first move
            # If study starts with 1.e4, it's a White repertoire
            # We'll need to infer from the perspective of moves
            self._process_game(game, opening_name)
    
    def _process_game(self, game: chess.pgn.Game, opening_name: str):
        """Process a single game/chapter from a study."""
        # Process the main line and all variations
        self._process_node(
            game,
            self.repertoire.white_tree,
            self.repertoire.black_tree,
            chess.WHITE,  # White moves first
            opening_name,
        )
    
    def _process_node(
        self,
        node: chess.pgn.GameNode,
        white_tree: RepertoireNode,
        black_tree: RepertoireNode,
        turn: chess.Color,
        opening_name: str,
    ):
        """Recursively process a game node and its variations."""
        # Get the current position's tree node based on perspective
        # For White repertoire: your moves when it's White's turn
        # For Black repertoire: your moves when it's Black's turn
        
        for variation in node.variations:
            move_san = node.board().san(variation.move)
            
            # Add to both trees (the tree structure is the same,
            # but interpretation differs based on which color you play)
            
            # White tree: positions from White's perspective
            if move_san not in white_tree.children:
                white_tree.children[move_san] = RepertoireNode(
                    opening_name=opening_name,
                    is_your_turn=(turn == chess.WHITE),
                )
            white_child = white_tree.children[move_san]
            white_child.opening_name = opening_name
            
            # Black tree: positions from Black's perspective
            if move_san not in black_tree.children:
                black_tree.children[move_san] = RepertoireNode(
                    opening_name=opening_name,
                    is_your_turn=(turn == chess.BLACK),
                )
            black_child = black_tree.children[move_san]
            black_child.opening_name = opening_name
            
            # Recursively process this variation
            self._process_node(
                variation,
                white_child,
                black_child,
                not turn,  # Alternate turns
                opening_name,
            )
