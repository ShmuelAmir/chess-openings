"""
Recall Gap aggregator - groups player-error Deviations into ranked Recall Gaps.

Pure: takes walk records with their games' metadata and returns the recall
view. No I/O. See Recall Gap in CONTEXT.md.
"""
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

import chess

from repertoire import side_to_move
from repertoire_walker import DeviationType, WalkRecord


@dataclass(frozen=True)
class WalkedGame:
    """One game and the outcome of walking it through the Repertoire."""
    url: str
    date: int  # Unix timestamp
    time_class: str
    rated: bool
    moves: list[str]
    record: WalkRecord


@dataclass(frozen=True)
class RecallFilters:
    """The Game Filters of the recall view."""
    time_classes: Optional[list[str]] = None  # None means every time control
    rated_only: bool = False
    since: Optional[int] = None  # Unix timestamp; None means all time

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


@dataclass
class RecallGap:
    position_key: str
    color: str  # "white" or "black": the user's color, i.e. the side to move
    path: list[str]  # SAN moves leading to the position in the most recent occurrence
    wrong_moves: list[WrongMove]
    book_moves: list[str]
    studies: list[str]  # ids of every study containing the position
    occurrences: int
    last_seen: int
    games: list[GapGame]  # most recent first


@dataclass(frozen=True)
class Totals:
    analysed: int = 0
    opponent_left_book: int = 0
    book_completed: int = 0


@dataclass
class RecallView:
    gaps: list[RecallGap] = field(default_factory=list)
    totals: Totals = field(default_factory=Totals)


def aggregate(
    games: Iterable[WalkedGame],
    filters: RecallFilters,
    studies_of: Callable[[str], Iterable[str]],
) -> RecallView:
    """
    Group the player-error Deviations of the games inside the filters into
    Recall Gaps, ranked by occurrences, ties broken by the most recent one.

    Args:
        games: Every walked game
        filters: Which games count
        studies_of: Ids of the studies containing a position key
    """
    shown = sorted(
        (g for g in games if g.record.analysed and filters.allows(g)),
        key=lambda g: g.date or 0,
        reverse=True,
    )

    by_type = Counter(g.record.deviation.type for g in shown if g.record.deviation)
    totals = Totals(
        analysed=len(shown),
        opponent_left_book=by_type[DeviationType.OPPONENT_LEFT_BOOK],
        book_completed=by_type[DeviationType.BOOK_COMPLETED],
    )

    occurrences: dict[str, list[WalkedGame]] = {}
    for g in shown:
        deviation = g.record.deviation
        if deviation and deviation.type == DeviationType.PLAYER_ERROR:
            occurrences.setdefault(deviation.position_key, []).append(g)

    gaps = [_gap(key, games_at, studies_of) for key, games_at in occurrences.items()]
    gaps.sort(key=lambda gap: (-gap.occurrences, -gap.last_seen, gap.position_key))
    return RecallView(gaps=gaps, totals=totals)


def _gap(
    key: str,
    games_at: list[WalkedGame],
    studies_of: Callable[[str], Iterable[str]],
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
        studies=sorted(studies_of(key)),
        occurrences=len(games_at),
        last_seen=latest.date or 0,
        games=[
            GapGame(g.url, g.date, g.time_class, g.record.deviation.move_played)
            for g in games_at
        ],
    )
