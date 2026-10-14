from datetime import datetime, timezone

import chess
import pytest

from games import Game
from opening_distribution import DistributionFilters, categorize_opening, opening_distribution


def timestamp(year, month, day=15, hour=12, minute=0):
    return int(datetime(year, month, day, hour, minute, tzinfo=timezone.utc).timestamp())


def game(opening="Italian Game", result="win", year=2026, month=3, **fields):
    """One of the user's games; `result` is the user's."""
    return Game(**{
        "url": "g", "date": timestamp(year, month), "month": (year, month),
        "time_class": "rapid", "rated": True, "opening_name": opening, "moves": (),
        "color": chess.WHITE, "result": result, **fields,
    })


def opening(distribution, name):
    return next(o for o in distribution["top_openings"] if o["opening"] == name)


def test_no_games_is_an_empty_distribution():
    assert opening_distribution([]) == {
        "total_games": 0,
        "unique_openings": 0,
        "top_openings": [],
        "categories": [],
        "trends": [],
        "top_opening_names": [],
    }


def test_openings_are_counted_and_listed_most_played_first():
    games = [game("Sicilian Defense"), game("Italian Game"), game("Sicilian Defense")]

    distribution = opening_distribution(games)

    assert distribution["total_games"] == 3
    assert distribution["unique_openings"] == 2
    assert [(o["opening"], o["games"]) for o in distribution["top_openings"]] == [
        ("Sicilian Defense", 2),
        ("Italian Game", 1),
    ]


def test_results_are_the_users():
    games = [game(result="win"), game(result="win"), game(result="loss"), game(result="draw")]

    italian = opening(opening_distribution(games), "Italian Game")

    assert (italian["wins"], italian["draws"], italian["losses"]) == (2, 1, 1)
    assert italian["win_rate"] == 50.0


def test_a_game_with_no_result_is_played_but_has_no_win_draw_or_loss():
    games = [game(result="win"), game(result="")]

    distribution = opening_distribution(games)
    italian = opening(distribution, "Italian Game")

    assert distribution["total_games"] == 2
    assert italian["games"] == 2
    assert (italian["wins"], italian["draws"], italian["losses"]) == (1, 0, 0)
    assert italian["win_rate"] == 100.0


def test_an_opening_with_no_known_results_has_a_zero_win_rate():
    italian = opening(opening_distribution([game(result="")]), "Italian Game")

    assert italian["win_rate"] == 0


def test_a_game_without_an_opening_label_is_the_unknown_opening():
    distribution = opening_distribution([game(opening="")])

    assert [o["opening"] for o in distribution["top_openings"]] == ["Unknown"]
    assert distribution["categories"] == [{"category": "Other", "count": 1}]


@pytest.mark.parametrize("name, category", [
    ("Sicilian Defense", "e4 Openings"),
    ("Ruy Lopez", "e4 Openings"),
    ("Queen's Gambit Declined", "d4 Openings"),
    ("London System", "d4 Openings"),
    ("English Opening", "c4 Openings"),
    ("Réti Opening", "Nf3 Openings"),
    ("Bird's Opening", "Other"),
    ("Unknown", "Other"),
])
def test_an_opening_is_categorized_by_its_first_move_family(name, category):
    assert categorize_opening(name) == category


def test_categories_count_games_and_are_listed_largest_first():
    games = [
        game("Queen's Gambit"),
        game("Sicilian Defense"),
        game("Italian Game"),
        game("French Defense"),
        game("London System"),
        game("Bird's Opening"),
    ]

    assert opening_distribution(games)["categories"] == [
        {"category": "e4 Openings", "count": 3},
        {"category": "d4 Openings", "count": 2},
        {"category": "Other", "count": 1},
    ]


def test_the_trend_counts_the_top_five_openings_month_by_month():
    names = ["A", "B", "C", "D", "E", "F"]
    # A is played 6 times in March, B 5 times, ... F once; A and F once more in April
    games = [
        game(name, month=3)
        for plays, name in zip(range(6, 0, -1), names)
        for _ in range(plays)
    ] + [game("A", month=4), game("F", month=4)]

    distribution = opening_distribution(games)

    assert distribution["top_opening_names"] == ["A", "B", "C", "D", "E"]
    assert distribution["trends"] == [
        {"month": "2026-03", "A": 6, "B": 5, "C": 4, "D": 3, "E": 2},
        {"month": "2026-04", "A": 1, "B": 0, "C": 0, "D": 0, "E": 0},
    ]


@pytest.mark.parametrize("date, month", [
    (timestamp(2026, 3, 31, 23, 30), "2026-03"),
    (timestamp(2026, 4, 1, 0, 30), "2026-04"),
])
def test_a_game_is_counted_in_the_utc_month_it_ended(date, month):
    distribution = opening_distribution([game(date=date)])

    assert distribution["trends"] == [{"month": month, "Italian Game": 1}]


def test_a_game_without_a_date_is_left_out_of_the_trend():
    undated = game(date=None)

    distribution = opening_distribution([undated])

    assert distribution["total_games"] == 1
    assert distribution["trends"] == []


def test_no_filters_show_every_game():
    games = [game(time_class="bullet", rated=False, color=chess.BLACK, date=None), game()]

    assert opening_distribution(games, DistributionFilters())["total_games"] == 2


def counted(games, **filters):
    """The openings of the games the filters show."""
    distribution = opening_distribution(games, DistributionFilters(**filters))
    return sorted(o["opening"] for o in distribution["top_openings"])


def test_the_time_control_filter_shows_the_games_of_the_selected_time_controls():
    games = [game("Bullet", time_class="bullet"), game("Blitz", time_class="blitz"),
             game("Rapid", time_class="rapid")]

    assert counted(games, time_classes=["blitz", "rapid"]) == ["Blitz", "Rapid"]


@pytest.mark.parametrize("rated, expected", [(True, ["Rated"]), (False, ["Casual"])])
def test_the_rated_filter_shows_rated_or_casual_games(rated, expected):
    games = [game("Rated", rated=True), game("Casual", rated=False)]

    assert counted(games, rated=rated) == expected


@pytest.mark.parametrize("color, expected", [(chess.WHITE, ["As White"]), (chess.BLACK, ["As Black"])])
def test_the_color_filter_shows_the_games_the_user_played_as_that_color(color, expected):
    games = [game("As White", color=chess.WHITE), game("As Black", color=chess.BLACK)]

    assert counted(games, color=color) == expected


def test_the_month_bounds_show_the_games_of_the_archive_months_between_them():
    games = [game(f"{month}", month=month) for month in (1, 2, 3, 4)] + [game("2025-12", year=2025, month=12)]

    assert counted(games, from_month=(2026, 2), to_month=(2026, 3)) == ["2", "3"]


def test_the_timestamp_bounds_show_the_games_that_ended_between_them():
    games = [game("Before", date=99), game("From", date=100), game("To", date=200), game("After", date=201)]

    assert counted(games, from_ts=100, to_ts=200) == ["From", "To"]


def test_a_game_without_a_date_is_outside_any_timestamp_bound():
    games = [game("Undated", date=None), game("Dated", date=150)]

    assert counted(games, to_ts=200) == ["Dated"]
    assert counted(games) == ["Dated", "Undated"]


def test_the_counts_are_of_the_games_the_filters_show():
    games = [game("Italian Game", result="win"), game("Italian Game", result="loss", rated=False)]

    distribution = opening_distribution(games, DistributionFilters(rated=True))

    assert distribution["total_games"] == 1
    assert opening(distribution, "Italian Game")["losses"] == 0
