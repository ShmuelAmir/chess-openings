"""
Opening Distribution - how often the user plays each opening and how they score in it.

Pure: takes cached games and returns the Opening Distribution. No I/O. See
Opening Distribution in CONTEXT.md.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone

from game_result import player_result

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


def categorize_opening(opening_name: str) -> str:
    """Categorize an opening by its first move family."""
    name_lower = opening_name.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(keyword in name_lower for keyword in keywords):
            return category
    return "Other"


def opening_distribution(games: list[dict], username: str) -> dict:
    """
    The Opening Distribution of the user's games.

    Args:
        games: Cached games, each with Chess.com's opening label as
            'opening_name' and White's result code as 'result'
        username: The user's Chess.com username

    Returns:
        The response of /api/opening-stats: every opening most played first
        with the user's wins, draws and losses, the first-move categories,
        and the monthly (UTC) counts of the most played openings. A game with no
        result is a game played, but not a win, draw or loss.
    """
    username_lower = username.lower()

    opening_counts = Counter()
    results = defaultdict(Counter)  # {opening: {"win" | "draw" | "loss": count}}
    category_counts = Counter()
    monthly_counts = defaultdict(Counter)  # {month: {opening: count}}

    for game in games:
        opening_name = game.get("opening_name") or "Unknown"
        opening_counts[opening_name] += 1
        category_counts[categorize_opening(opening_name)] += 1

        user_is_white = (game.get("white") or "").lower() == username_lower
        result = player_result(game.get("result") or "", user_is_white)
        if result:
            results[opening_name][result] += 1

        date_ts = game.get("date")
        if date_ts:
            month = datetime.fromtimestamp(date_ts, timezone.utc).strftime("%Y-%m")
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
