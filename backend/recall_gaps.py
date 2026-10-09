"""
Recall Gap aggregator - groups player-error Deviations into ranked Recall Gaps.

Pure: takes walk records with their games' metadata and returns the recall
view. No I/O. See Recall Gap in CONTEXT.md.
"""
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Iterable, Optional

import chess

from opening_normalizer import OpeningNormalizer
from repertoire import Repertoire, side_to_move, study_url
from repertoire_walker import DeviationType, WalkRecord

# In-book games since the last occurrence that close a Recall Gap
GAMES_TO_CLOSE = 2
# Months in the Miss Rate trend, and the fewest games a month needs to get a Miss Rate
TREND_MONTHS = 12
MIN_TREND_GAMES = 5
# Date range presets of the recall view, in days back from now (None = all time)
DATE_RANGE_DAYS = {"month": 30, "3months": 91, "year": 365, "all": None}
DAY = 24 * 60 * 60


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

    @classmethod
    def for_date_range(
        cls,
        date_range: str,
        now: int,
        time_classes: Optional[list[str]] = None,
        rated_only: bool = False,
        studies: Optional[Iterable[str]] = None,
    ) -> "RecallFilters":
        """
        The Game Filters with a date range preset, reaching back from `now`.

        Raises:
            ValueError: `date_range` is not one of the presets
        """
        if date_range not in DATE_RANGE_DAYS:
            raise ValueError(f"date_range must be one of {', '.join(DATE_RANGE_DAYS)}")
        days = DATE_RANGE_DAYS[date_range]
        return cls(
            time_classes=time_classes,
            rated_only=rated_only,
            since=now - days * DAY if days else None,
            studies=frozenset(studies) if studies else None,
        )

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
    """A study containing a Recall Gap's position, and the link to it in that study."""
    id: str
    name: str
    url: str  # opens the study at the position, or at its chapter when off the mainline


@dataclass(frozen=True)
class DrillTurn:
    """One of the user's turns in a Recall Gap's drill, and the moves it accepts."""
    ply: int  # half-moves played before it
    position_key: str
    book_moves: list[str]


@dataclass
class RecallGap:
    """One Recall Gap as the recall view and practice sessions return it."""
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
    games_to_close: int = GAMES_TO_CLOSE
    closed_at: Optional[int] = None  # date of the game that closed the gap
    # The user's turns along `path` and at the gap itself, which a Drill Attempt plays
    drill_turns: list[DrillTurn] = field(default_factory=list)


@dataclass(frozen=True)
class Closing:
    progress: int = 0
    closed_at: Optional[int] = None


@dataclass(frozen=True)
class TrendMonth:
    month: str  # "YYYY-MM", in UTC
    games: int  # analysed games
    miss_rate: Optional[float]  # None with fewer than MIN_TREND_GAMES games


@dataclass(frozen=True)
class Totals:
    analysed: int = 0
    opponent_left_book: int = 0
    book_completed: int = 0
    miss_rate: Optional[float] = None  # None without analysed games
    # The last TREND_MONTHS months, oldest first, under every Game Filter but the date range
    trend: list[TrendMonth] = field(default_factory=list)
    open_gaps: int = 0  # the Open gaps shown
    # Gaps whose closing date is inside the date range, under every other Game Filter
    closed_in_range: int = 0


@dataclass(frozen=True)
class StudyView:
    """A study of the Repertoire, as the Study filter lists it."""
    id: str
    name: str
    opening_name: str
    color: str  # "white" or "black"
    gaps: int  # its Recall Gaps under every Game Filter but the Study filter


@dataclass
class RecallView:
    """
    The recall view. These dataclasses are the wire contract: the HTTP layer
    serialises them as they are.
    """
    studies: list[StudyView] = field(default_factory=list)  # sorted by opening name
    gaps: list[RecallGap] = field(default_factory=list)
    totals: Totals = field(default_factory=Totals)


def aggregate(
    games: Iterable[WalkedGame],
    filters: RecallFilters,
    repertoire: Repertoire,
    now: Optional[int] = None,
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

    The Miss Rate is per game: the share of the shown games with a player
    error. Its trend buckets the games by month under every filter but the
    date range, so it always covers the last TREND_MONTHS months.

    The view also lists every study of the Repertoire, sorted by opening
    name, each with its Recall Gaps under every filter but the Study filter.

    Args:
        games: Every walked game
        filters: Which games count
        repertoire: The Repertoire the games were walked through, for its
            studies and where each position sits in them
        now: Unix timestamp the trend ends at; None leaves the trend empty
    """
    studies_of = repertoire.study_locations

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
    any_date = replace(filters, since=None)
    shown_any_date = [g for g in analysed if any_date.allows(g) and left_book_in_selected_study(g)]

    by_type = Counter(g.record.deviation.type for g in shown if g.record.deviation)
    gaps_by_study = Counter(
        study_id
        for key, games_at in _occurrences(in_window).items()
        for study_id in studies_of(key, games_at[0].color)
    )

    gaps = [
        _gap(key, games_at, closings[key], repertoire)
        for key, games_at in _occurrences(shown).items()
    ]
    gaps.sort(key=lambda gap: (-gap.occurrences, -gap.last_seen, gap.position_key))

    closed_in_range = sum(
        1
        for key in _occurrences(shown_any_date)
        if closings[key].closed_at is not None
        and (filters.since is None or closings[key].closed_at >= filters.since)
    )
    return RecallView(
        studies=_studies(repertoire, gaps_by_study),
        gaps=gaps,
        totals=Totals(
            analysed=len(shown),
            opponent_left_book=by_type[DeviationType.OPPONENT_LEFT_BOOK],
            book_completed=by_type[DeviationType.BOOK_COMPLETED],
            miss_rate=_miss_rate(shown),
            trend=_trend(shown_any_date, now) if now is not None else [],
            open_gaps=sum(1 for gap in gaps if gap.status == "open"),
            closed_in_range=closed_in_range,
        ),
    )


def last_occurrences(games: Iterable[WalkedGame]) -> dict[str, int]:
    """
    The date of each Recall Gap's most recent occurrence, by position key,
    over every game whatever the Game Filters.
    """
    latest: dict[str, int] = {}
    for g in games:
        if g.record.analysed and _is_miss(g):
            key = g.record.deviation.position_key
            latest[key] = max(latest.get(key, 0), g.date or 0)
    return latest


def _color_name(color: chess.Color) -> str:
    return "white" if color == chess.WHITE else "black"


def _studies(repertoire: Repertoire, gaps_by_study: Counter) -> list[StudyView]:
    """The Repertoire's studies, sorted by opening name whatever its case."""
    studies = []
    for study_id, color in repertoire.study_colors.items():
        name = repertoire.study_names.get(study_id, study_id)
        studies.append(StudyView(
            id=study_id,
            name=name,
            opening_name=OpeningNormalizer.normalize(name),
            color=_color_name(color),
            gaps=gaps_by_study[study_id],
        ))
    return sorted(studies, key=lambda study: study.opening_name.lower())


def _is_miss(g: WalkedGame) -> bool:
    return g.record.deviation is not None and g.record.deviation.type == DeviationType.PLAYER_ERROR


def _miss_rate(games: list[WalkedGame]) -> Optional[float]:
    """The share of the games with a player error, or None for no games."""
    if not games:
        return None
    return sum(1 for g in games if _is_miss(g)) / len(games)


def _month(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m")


def _trend(games: list[WalkedGame], now: int) -> list[TrendMonth]:
    """The Miss Rate of each of the TREND_MONTHS months up to `now`'s, oldest first."""
    end = datetime.fromtimestamp(now, timezone.utc)
    months = []
    for back in range(TREND_MONTHS - 1, -1, -1):
        year, month = divmod(end.year * 12 + end.month - 1 - back, 12)
        months.append(f"{year:04d}-{month + 1:02d}")

    by_month: dict[str, list[WalkedGame]] = {}
    for g in games:
        by_month.setdefault(_month(g.date or 0), []).append(g)

    trend = []
    for month in months:
        games_in = by_month.get(month, [])
        trend.append(TrendMonth(
            month=month,
            games=len(games_in),
            miss_rate=_miss_rate(games_in) if len(games_in) >= MIN_TREND_GAMES else None,
        ))
    return trend


def _occurrences(games: list[WalkedGame]) -> dict[str, list[WalkedGame]]:
    """The games of each player-error position key, in the given order."""
    occurrences: dict[str, list[WalkedGame]] = {}
    for g in games:
        if _is_miss(g):
            occurrences.setdefault(g.record.deviation.position_key, []).append(g)
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
    repertoire: Repertoire,
) -> RecallGap:
    """Build one Recall Gap from its occurrences (most recent first)."""
    latest = games_at[0]
    played = Counter(g.record.deviation.move_played for g in games_at)
    # A position reached by different book paths can allow different moves on each
    book_moves = list(dict.fromkeys(m for g in games_at for m in g.record.deviation.book_moves))

    return RecallGap(
        position_key=key,
        color=_color_name(side_to_move(key)),
        path=latest.moves[: latest.record.deviation.ply],
        wrong_moves=[WrongMove(san, n) for san, n in sorted(played.items(), key=lambda m: (-m[1], m[0]))],
        book_moves=book_moves,
        studies=[
            GapStudy(
                id=study_id,
                name=repertoire.study_names.get(study_id, study_id),
                url=study_url(study_id, location.chapter_id, location.mainline_ply),
            )
            for study_id, location in sorted(repertoire.study_locations(key, latest.color).items())
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
        drill_turns=_drill_turns(latest, book_moves),
    )


def _drill_turns(latest: WalkedGame, book_moves: list[str]) -> list[DrillTurn]:
    """The user's turns of the gap's most recent occurrence, up to and including the gap."""
    turns = [
        DrillTurn(m.ply, m.position_key, m.book_moves)
        for m in latest.record.reached_in_book
    ]
    deviation = latest.record.deviation
    return turns + [DrillTurn(deviation.ply, deviation.position_key, book_moves)]
