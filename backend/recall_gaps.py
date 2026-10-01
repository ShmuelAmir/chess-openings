"""
Recall Gap aggregator - groups player-error Deviations into ranked Recall Gaps.

Pure: takes walk records with their games' metadata and returns the recall
view. No I/O. See Recall Gap in CONTEXT.md.
"""
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Optional

import chess

from repertoire import ChapterLocation, side_to_move
from repertoire_walker import DeviationType, WalkRecord

# In-book games since the last occurrence that close a Recall Gap
GAMES_TO_CLOSE = 2


@dataclass(frozen=True)
class WalkedGame:
    """One game and the outcome of walking it through the Repertoire."""
    url: str
    date: int  # Unix timestamp
    time_class: str
    rated: bool
    result: str  # the user's result: "win", "loss", "draw", or "" when unknown
    moves: list[str]
    color: chess.Color  # the user's color
    record: WalkRecord


@dataclass(frozen=True)
class RecallFilters:
    """The Game Filters of the recall view."""
    time_classes: Optional[list[str]] = None  # None means every time control
    rated_only: bool = False
    since: Optional[int] = None  # Unix timestamp; None means all time
    studies: Optional[frozenset[str]] = None  # Study filter: study ids; None or empty means all

    def allows(self, game: WalkedGame) -> bool:
        if self.time_classes and game.time_class not in self.time_classes:
            return False
        if self.rated_only and not game.rated:
            return False
        if self.since is not None and (game.date or 0) < self.since:
            return False
        return True


@dataclass(frozen=True)
class WrongMove:
    san: str
    count: int


@dataclass(frozen=True)
class GapGame:
    """A game in which a Recall Gap occurred."""
    url: str
    date: int
    time_class: str
    move_played: str
    result: str


@dataclass(frozen=True)
class GapStudy:
    """A study containing a Recall Gap's position, and where it sits in that study."""
    id: str
    chapter_id: Optional[str]
    mainline_ply: Optional[int]  # None when the position is off the chapter's mainline


@dataclass
class RecallGap:
    position_key: str
    color: str  # "white" or "black": the user's color, i.e. the side to move
    path: list[str]  # SAN moves leading to the position in the most recent occurrence
    wrong_moves: list[WrongMove]
    book_moves: list[str]
    studies: list[GapStudy]  # every study containing the position, sorted by id
    occurrences: int
    last_seen: int
    games: list[GapGame]  # most recent first
    status: str = "open"  # "open" or "closed"
    progress: int = 0  # in-book games since the last occurrence, up to GAMES_TO_CLOSE
    closed_at: Optional[int] = None  # date of the game that closed the gap


@dataclass(frozen=True)
class Closing:
    progress: int = 0
    closed_at: Optional[int] = None


@dataclass(frozen=True)
class Totals:
    analysed: int = 0
    opponent_left_book: int = 0
    book_completed: int = 0


@dataclass
class RecallView:
    gaps: list[RecallGap] = field(default_factory=list)
    totals: Totals = field(default_factory=Totals)
    # Recall Gaps per study id under every Game Filter but the Study filter
    gaps_by_study: dict[str, int] = field(default_factory=dict)


StudiesOf = Callable[[str, chess.Color], Mapping[str, ChapterLocation]]


def aggregate(
    games: Iterable[WalkedGame],
    filters: RecallFilters,
    studies_of: StudiesOf,
) -> RecallView:
    """
    Group the player-error Deviations of the games inside the filters into
    Recall Gaps, ranked by occurrences, ties broken by the most recent one.

    Each gap's status comes from every analysed game, whatever the filters:
    it is Closed once GAMES_TO_CLOSE games after its last occurrence reached
    its position and the user played a book move there.

    The Study filter keeps the games whose Deviation position (where they
    left book) is in a selected study. Every occurrence of a gap shares its
    position, so the filter decides only whether a gap is shown.

    Args:
        games: Every walked game
        filters: Which games count
        studies_of: Where a position key sits in each study of a color
            containing it, by study id
    """
    def left_book_in_selected_study(g: WalkedGame) -> bool:
        if not filters.studies:
            return True
        return not filters.studies.isdisjoint(studies_of(g.record.deviation.position_key, g.color))

    analysed = sorted(
        (g for g in games if g.record.analysed),
        key=lambda g: g.date or 0,
        reverse=True,
    )
    closings = _closings(analysed)
    in_window = [g for g in analysed if filters.allows(g)]
    shown = [g for g in in_window if left_book_in_selected_study(g)]

    by_type = Counter(g.record.deviation.type for g in shown if g.record.deviation)
    totals = Totals(
        analysed=len(shown),
        opponent_left_book=by_type[DeviationType.OPPONENT_LEFT_BOOK],
        book_completed=by_type[DeviationType.BOOK_COMPLETED],
    )

    gaps_by_study = Counter(
        study_id
        for key, games_at in _occurrences(in_window).items()
        for study_id in studies_of(key, games_at[0].color)
    )

    gaps = [
        _gap(key, games_at, closings[key], studies_of)
        for key, games_at in _occurrences(shown).items()
    ]
    gaps.sort(key=lambda gap: (-gap.occurrences, -gap.last_seen, gap.position_key))
    return RecallView(gaps=gaps, totals=totals, gaps_by_study=dict(gaps_by_study))


def _occurrences(games: list[WalkedGame]) -> dict[str, list[WalkedGame]]:
    """The games of each player-error position key, in the given order."""
    occurrences: dict[str, list[WalkedGame]] = {}
    for g in games:
        deviation = g.record.deviation
        if deviation and deviation.type == DeviationType.PLAYER_ERROR:
            occurrences.setdefault(deviation.position_key, []).append(g)
    return occurrences


def _closings(games: list[WalkedGame]) -> dict[str, Closing]:
    """
    Each player-error position key's progress toward closing: the games
    after its last occurrence that played a book move there.

    Walks the games most recent first, so the first occurrence met is the
    last one, and every in-book game met before it came after it.
    """
    closings: dict[str, Closing] = {}
    in_book_since: dict[str, list[int]] = {}  # the in-book games' dates, most recent first
    for g in games:
        deviation = g.record.deviation
        if deviation and deviation.type == DeviationType.PLAYER_ERROR:
            key = deviation.position_key
            if key not in closings:
                dates = in_book_since.get(key, [])
                closings[key] = Closing(
                    progress=min(len(dates), GAMES_TO_CLOSE),
                    # The gap closed with the GAMES_TO_CLOSE-th in-book game after it
                    closed_at=dates[-GAMES_TO_CLOSE] if len(dates) >= GAMES_TO_CLOSE else None,
                )
        # A game counts once however often it reached the position
        for key in dict.fromkeys(m.position_key for m in g.record.reached_in_book):
            if key not in closings:
                in_book_since.setdefault(key, []).append(g.date or 0)
    return closings


def _gap(
    key: str,
    games_at: list[WalkedGame],
    closing: Closing,
    studies_of: StudiesOf,
) -> RecallGap:
    """Build one Recall Gap from its occurrences (most recent first)."""
    latest = games_at[0]
    played = Counter(g.record.deviation.move_played for g in games_at)
    # A position reached by different book paths can allow different moves on each
    book_moves = list(dict.fromkeys(m for g in games_at for m in g.record.deviation.book_moves))

    return RecallGap(
        position_key=key,
        color="white" if side_to_move(key) == chess.WHITE else "black",
        path=latest.moves[: latest.record.deviation.ply],
        wrong_moves=[WrongMove(san, n) for san, n in sorted(played.items(), key=lambda m: (-m[1], m[0]))],
        book_moves=book_moves,
        studies=[
            GapStudy(study_id, location.chapter_id, location.mainline_ply)
            for study_id, location in sorted(studies_of(key, latest.color).items())
        ],
        occurrences=len(games_at),
        last_seen=latest.date or 0,
        games=[
            GapGame(g.url, g.date, g.time_class, g.record.deviation.move_played, g.result)
            for g in games_at
        ],
        status="open" if closing.closed_at is None else "closed",
        progress=closing.progress,
        closed_at=closing.closed_at,
    )
