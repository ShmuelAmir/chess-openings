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
    # The study name this came from
    study_name: Optional[str] = None
    # Is this a position where it's your turn to move?
    is_your_turn: bool = False


@dataclass
class Repertoire:
    """Complete repertoire with separate trees for White and Black."""
    white_tree: RepertoireNode = field(default_factory=RepertoireNode)
    black_tree: RepertoireNode = field(default_factory=RepertoireNode)
    # FEN position index: maps FEN string -> (opening_name, study_name, variation_count)
    position_index: dict[str, tuple[str, str, int]] = field(default_factory=dict)
    
    def get_tree(self, color: chess.Color) -> RepertoireNode:
        """Get the repertoire tree for a specific color."""
        return self.white_tree if color == chess.WHITE else self.black_tree


class RepertoireBuilder:
    """Builds a repertoire from Lichess study PGNs."""
    
    def __init__(self):
        self.repertoire = Repertoire()
        self._studies: list[tuple[str, str, str]] = []  # (pgn, opening_name, study_name)
    
    def add_study(self, pgn: str, opening_name: str, study_name: Optional[str] = None):
        """Add a study PGN to be processed."""
        self._studies.append((pgn, opening_name, study_name or opening_name))
    
    def build(self) -> Repertoire:
        """Process all studies and build the repertoire trees."""
        for pgn, opening_name, study_name in self._studies:
            self._process_study(pgn, opening_name, study_name)
        # Build FEN position index for transposition handling
        self._build_fen_index()
        return self.repertoire
    
    def _process_study(self, pgn: str, opening_name: str, study_name: str):
        """Process a single study PGN (may contain multiple chapters/games)."""
        pgn_io = io.StringIO(pgn)
        
        while True:
            game = chess.pgn.read_game(pgn_io)
            if game is None:
                break
            
            # Extract chapter name from PGN headers
            # Lichess uses the game name or title as chapter name
            chapter_name = game.headers.get("Event") or game.headers.get("Site") or study_name
            
            # Remove redundant study name prefix if present
            # E.g., "Vienna: Accepted" -> just "Accepted"
            if ":" in chapter_name:
                chapter_name = chapter_name.split(":", 1)[1].strip()
            
            full_chapter_name = f"{study_name} - {chapter_name}"
            self._process_game(game, opening_name, full_chapter_name)
    
    def _build_fen_index(self):
        """Build FEN position index by traversing the white repertoire tree."""
        def traverse_tree(node: RepertoireNode, board: chess.Board):
            """Recursively traverse tree and index FEN positions."""
            fen = board.fen()
            if fen and node.opening_name:
                # Count variations available at this position
                variation_count = len(node.children)
                # Store the opening and study info for this FEN
                self.repertoire.position_index[fen] = (
                    node.opening_name,
                    node.study_name,
                    variation_count,
                )
            
            # Traverse all child positions
            for move_san, child_node in node.children.items():
                try:
                    move = board.parse_san(move_san)
                    board.push(move)
                    traverse_tree(child_node, board)
                    board.pop()
                except ValueError:
                    # Invalid move, skip
                    pass
        
        # Start from white's perspective
        board = chess.Board()
        traverse_tree(self.repertoire.white_tree, board)
    
    def _process_game(self, game: chess.pgn.Game, opening_name: str, study_name: str):
        """Process a single game/chapter from a study."""
        # Process the main line and all variations
        self._process_node(
            game,
            self.repertoire.white_tree,
            self.repertoire.black_tree,
            chess.WHITE,  # White moves first
            opening_name,
            study_name,
        )
    
    def _process_node(
        self,
        node: chess.pgn.GameNode,
        white_tree: RepertoireNode,
        black_tree: RepertoireNode,
        turn: chess.Color,
        opening_name: str,
        study_name: str,
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
                    study_name=study_name,
                    is_your_turn=(turn == chess.WHITE),
                )
            white_child = white_tree.children[move_san]
            white_child.opening_name = opening_name
            white_child.study_name = study_name
            
            # Black tree: positions from Black's perspective
            if move_san not in black_tree.children:
                black_tree.children[move_san] = RepertoireNode(
                    opening_name=opening_name,
                    study_name=study_name,
                    is_your_turn=(turn == chess.BLACK),
                )
            black_child = black_tree.children[move_san]
            black_child.opening_name = opening_name
            black_child.study_name = study_name
            
            # Recursively process this variation
            self._process_node(
                variation,
                white_child,
                black_child,
                not turn,  # Alternate turns
                opening_name,
                study_name,
            )
