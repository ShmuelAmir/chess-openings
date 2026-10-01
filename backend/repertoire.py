"""
Repertoire Parser - Builds a move tree from Lichess study PGNs
"""
import io
import re
import chess
import chess.pgn
from dataclasses import dataclass, field
from typing import NamedTuple, Optional
from opening_normalizer import OpeningNormalizer


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
    # Lichess study ID this line came from
    study_id: Optional[str] = None
    # Lichess chapter ID this line came from
    chapter_id: Optional[str] = None
    # Is this a position where it's your turn to move?
    is_your_turn: bool = False


class ChapterLocation(NamedTuple):
    """Where a position sits in a study, for an "open in study" deep link."""
    chapter_id: Optional[str]
    # Half-moves from the chapter start; None when the position is off the mainline
    mainline_ply: Optional[int]


def position_key(board: chess.Board) -> str:
    """The FEN without the halfmove and fullmove counters."""
    return " ".join(board.fen().split(" ")[:4])


@dataclass
class Repertoire:
    """Complete repertoire with separate trees for White and Black."""
    white_tree: RepertoireNode = field(default_factory=RepertoireNode)
    black_tree: RepertoireNode = field(default_factory=RepertoireNode)
    # (study color, position key) -> {study id: where the position sits in that study}
    _study_membership: dict[tuple[chess.Color, str], dict[str, ChapterLocation]] = field(default_factory=dict)

    def get_tree(self, color: chess.Color) -> RepertoireNode:
        """Get the repertoire tree for a specific color."""
        return self.white_tree if color == chess.WHITE else self.black_tree

    def studies_containing(self, key: str, color: chess.Color) -> set[str]:
        """Ids of the studies of this color whose lines contain the position."""
        return set(self._locations(key, color))

    def chapter_location(
        self, key: str, color: chess.Color, study_id: str
    ) -> Optional[ChapterLocation]:
        """The chapter (and mainline ply, if any) to deep-link this position in a study."""
        return self._locations(key, color).get(study_id)

    def _locations(self, key: str, color: chess.Color) -> dict[str, ChapterLocation]:
        return self._study_membership.get((color, key), {})

    def add_study_position(
        self, color: chess.Color, key: str, study_id: str, location: ChapterLocation
    ):
        """Record that a study contains the position (used by RepertoireBuilder).

        A chapter that has the position on its mainline beats one that doesn't.
        """
        locations = self._study_membership.setdefault((color, key), {})
        known = locations.get(study_id)
        if known is None or (known.mainline_ply is None and location.mainline_ply is not None):
            locations[study_id] = location


class RepertoireBuilder:
    """Builds a repertoire from Lichess study PGNs."""

    # Match Lichess study URLs and capture optional chapter id.
    # Be permissive about id length/characters to tolerate format changes
    _LICHESS_STUDY_SITE_RE = re.compile(
        r"https?://(?:www\.)?lichess\.org/study/([^/\s]+)(?:/([^/?#\s]+))?"
    )
    
    def __init__(self):
        self.repertoire = Repertoire()
        self._studies: list[tuple[str, str, str, Optional[str]]] = []  # (pgn, opening_name, study_name, study_id)
    
    def add_study(
        self,
        pgn: str,
        opening_name: str,
        study_name: Optional[str] = None,
        study_id: Optional[str] = None,
    ):
        """Add a study PGN to be processed."""
        self._studies.append((pgn, opening_name, study_name or opening_name, study_id))
    
    def build(self) -> Repertoire:
        """Process all studies and build the repertoire trees."""
        for pgn, opening_name, study_name, study_id in self._studies:
            self._process_study(pgn, opening_name, study_name, study_id)
        return self.repertoire
    
    def _process_study(
        self,
        pgn: str,
        opening_name: str,
        study_name: str,
        study_id: Optional[str],
    ):
        """Process a single study PGN (one game per chapter).

        The study belongs to the color of its first chapter's orientation
        and feeds only that color's tree.
        """
        chapters = self._read_chapters(pgn)
        if not chapters:
            return
        color = self._orientation(chapters[0])

        for game in chapters:
            # Extract chapter name from PGN headers
            # Lichess uses the game name or title as chapter name
            chapter_name = game.headers.get("Event") or game.headers.get("Site") or study_name
            chapter_id = self._chapter_id(game.headers)

            # Normalize study & chapter pair, avoiding redundancy.
            # This prevents cases where a chapter that only repeats the study
            # becomes an empty string (e.g., "Vienna: " -> "").
            norm_study, norm_chapter = OpeningNormalizer.from_study_chapter_pair(
                study_name, chapter_name
            )

            # Use normalized study name for consistency
            opening_name = norm_study

            # If chapter is empty after normalization, fall back to None so
            # callers/UI can decide how to render (avoids producing "Study - ").
            chapter_name = norm_chapter if norm_chapter else None

            full_chapter_name = f"{study_name} - {chapter_name}" if chapter_name else study_name
            self._process_game(
                game,
                color,
                opening_name,
                full_chapter_name,
                study_id,
                chapter_id,
            )

    @staticmethod
    def _read_chapters(pgn: str) -> list[chess.pgn.Game]:
        pgn_io = io.StringIO(pgn)
        chapters = []
        while (game := chess.pgn.read_game(pgn_io)) is not None:
            chapters.append(game)
        return chapters

    @staticmethod
    def _orientation(game: chess.pgn.Game) -> chess.Color:
        """A chapter's orientation, from the PGN fetched with ?orientation=true.

        A missing header is read as White, Lichess's default orientation.
        """
        return chess.BLACK if game.headers.get("Orientation", "").lower() == "black" else chess.WHITE

    def _chapter_id(self, headers: chess.pgn.Headers) -> Optional[str]:
        """The chapter id from the first Lichess chapter URL in the headers."""
        for header in ("ChapterURL", "Site", "Event"):
            chapter_id = self._extract_chapter_id(headers.get(header))
            if chapter_id:
                return chapter_id
        return None

    def _extract_chapter_id(self, site_header: Optional[str]) -> Optional[str]:
        """Extract the chapter ID from Lichess PGN Site header URL."""
        if not site_header:
            return None

        match = self._LICHESS_STUDY_SITE_RE.search(site_header)
        if not match:
            return None

        # group(2) is the optional chapter id (may be None)
        chapter = match.group(2)
        if chapter:
            # Normalize common delimiters and strip whitespace
            return chapter.strip().strip("/")
        return None
    
    def _process_game(
        self,
        game: chess.pgn.Game,
        color: chess.Color,
        opening_name: str,
        study_name: str,
        study_id: Optional[str],
        chapter_id: Optional[str],
    ):
        """Process a single game/chapter into its study's color tree."""
        # Process the main line and all variations
        self._process_node(
            game,
            self.repertoire.get_tree(color),
            color,
            opening_name,
            study_name,
            study_id,
            chapter_id,
        )

    def _process_node(
        self,
        node: chess.pgn.GameNode,
        tree: RepertoireNode,
        color: chess.Color,
        opening_name: str,
        study_name: str,
        study_id: Optional[str],
        chapter_id: Optional[str],
    ):
        """Recursively process a game node and its variations."""
        board = node.board()
        if study_id:
            self.repertoire.add_study_position(
                color,
                position_key(board),
                study_id,
                ChapterLocation(chapter_id, node.ply() if node.is_mainline() else None),
            )
        for variation in node.variations:
            move_san = board.san(variation.move)

            if move_san not in tree.children:
                tree.children[move_san] = RepertoireNode(
                    opening_name=opening_name,
                    study_name=study_name,
                    study_id=study_id,
                    chapter_id=chapter_id,
                    is_your_turn=(board.turn == color),
                )
            child = tree.children[move_san]
            if child.opening_name is None:
                child.opening_name = opening_name
            if child.study_name is None:
                child.study_name = study_name
            if child.study_id is None:
                child.study_id = study_id
            if child.chapter_id is None:
                child.chapter_id = chapter_id

            # Recursively process this variation
            self._process_node(
                variation,
                child,
                color,
                opening_name,
                study_name,
                study_id,
                chapter_id,
            )
