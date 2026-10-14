"""
Opening Distribution - how often the user plays each opening and how they score in it.

Pure: takes the user's games and its Game Filters, and returns the Opening
Distribution. No I/O. See Opening Distribution in CONTEXT.md.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import chess

from games import Game

# Openings whose monthly counts make up the trend
TREND_OPENINGS = 5

# Opening name keywords of each first-move family, checked in this order
_CATEGORY_KEYWORDS = {
    "e4 Openings": ["sicilian", "italian", "spanish", "ruy lopez", "french", "caro-kann",
                    "scandinavian", "alekhine", "pirc", "modern", "king's pawn", "scotch",
                    "petroff", "petrov", "vienna", "bishop's opening", "center game",
                    "king's gambit", "philidor", "two knights"],
    "d4 Openings": ["queen's gambit", "king's indian", "slav", "gruenfeld", "grunfeld",
                    "nimzo", "queen's indian", "dutch", "london", "trompowsky", "torre",
                    "colle", "catalan", "bogo", "benoni", "semi-slav"],
    "c4 Openings": ["english"],
    "Nf3 Openings": ["reti", "réti"],
}


@dataclass(frozen=True)
class DistributionFilters:
    """The Game Filters of the Opening Distribution. None means no bound."""
    time_classes: Optional[list[str]] = None  # None or empty means every time control
    rated: Optional[bool] = None  # True: rated games only; False: casual games only
    color: Optional[chess.Color] = None  # the user's color
    from_month: Optional[tuple[int, int]] = None  # (year, month) of the Chess.com archive
    to_month: Optional[tuple[int, int]] = None
    from_ts: Optional[int] = None  # Unix timestamps the game ended between
    to_ts: Optional[int] = None

    def shows(self, game: Game) -> bool:
        """Whether the filters show the game. A game with no date is outside any timestamp bound."""
        if self.time_classes and game.time_class not in self.time_classes:
            return False
        if self.rated is not None and game.rated != self.rated:
            return False
        if self.color is not None and game.color != self.color:
            return False
        if self.from_month is not None and game.month < self.from_month:
            return False
        if self.to_month is not None and game.month > self.to_month:
            return False
        if self.from_ts is not None or self.to_ts is not None:
            if game.date is None:
                return False
            if self.from_ts is not None and game.date < self.from_ts:
                return False
            if self.to_ts is not None and game.date > self.to_ts:
                return False
        return True


def categorize_opening(opening_name: str) -> str:
    """Categorize an opening by its first move family."""
    name_lower = opening_name.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(keyword in name_lower for keyword in keywords):
            return category
    return "Other"


def opening_distribution(games: list[Game], filters: DistributionFilters = DistributionFilters()) -> dict:
    """
    The Opening Distribution of the user's games that the filters show.

    Args:
        games: The user's games
        filters: The Opening Distribution's Game Filters

    Returns:
        The response of /api/opening-stats: every opening most played first
        with the user's wins, draws and losses, the first-move categories,
        and the monthly (UTC) counts of the most played openings. A game with no
        result is a game played, but not a win, draw or loss.
    """
    games = [game for game in games if filters.shows(game)]

    opening_counts = Counter()
    results = defaultdict(Counter)  # {opening: {"win" | "draw" | "loss": count}}
    category_counts = Counter()
    monthly_counts = defaultdict(Counter)  # {month: {opening: count}}

    for game in games:
        opening_name = game.opening_name or "Unknown"
        opening_counts[opening_name] += 1
        category_counts[categorize_opening(opening_name)] += 1

        if game.result:
            results[opening_name][game.result] += 1

        if game.date:
            month = datetime.fromtimestamp(game.date, timezone.utc).strftime("%Y-%m")
            monthly_counts[month][opening_name] += 1

    top_openings = []
    for name, count in opening_counts.most_common():
        wins, draws, losses = (results[name][result] for result in ("win", "draw", "loss"))
        total = wins + draws + losses
        top_openings.append({
            "opening": name,
            "games": count,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "win_rate": round(wins / total * 100, 1) if total else 0,
        })

    top_names = [name for name, _ in opening_counts.most_common(TREND_OPENINGS)]

    return {
        "total_games": len(games),
        "unique_openings": len(opening_counts),
        "top_openings": top_openings,
        "categories": [
            {"category": category, "count": count}
            for category, count in category_counts.most_common()
        ],
        "trends": [
            {"month": month, **{name: monthly_counts[month][name] for name in top_names}}
            for month in sorted(monthly_counts)
        ],
        "top_opening_names": top_names,
    }
