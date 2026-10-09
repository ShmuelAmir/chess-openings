from datetime import datetime

import pytest

from opening_distribution import categorize_opening, opening_distribution


def game(opening="Italian Game", white="me", result="win", year=2026, month=3):
    return {
        "white": white,
        "black": "opponent" if white == "me" else "me",
        "result": result,  # White's Chess.com result code
        "opening_name": opening,
        "date": int(datetime(year, month, 15, 12).timestamp()),
    }


def opening(distribution, name):
    return next(o for o in distribution["top_openings"] if o["opening"] == name)


def test_no_games_is_an_empty_distribution():
    assert opening_distribution([], "me") == {
        "total_games": 0,
        "unique_openings": 0,
        "top_openings": [],
        "categories": [],
        "trends": [],
        "top_opening_names": [],
    }


def test_openings_are_counted_and_listed_most_played_first():
    games = [game("Sicilian Defense"), game("Italian Game"), game("Sicilian Defense")]

    distribution = opening_distribution(games, "me")

    assert distribution["total_games"] == 3
    assert distribution["unique_openings"] == 2
    assert [(o["opening"], o["games"]) for o in distribution["top_openings"]] == [
        ("Sicilian Defense", 2),
        ("Italian Game", 1),
    ]


def test_results_are_the_users_when_playing_white():
    games = [game(result="win"), game(result="win"), game(result="resigned"), game(result="agreed")]

    italian = opening(opening_distribution(games, "me"), "Italian Game")

    assert (italian["wins"], italian["draws"], italian["losses"]) == (2, 1, 1)
    assert italian["win_rate"] == 50.0


def test_results_are_the_users_when_playing_black():
    games = [
        game(white="opponent", result="win"),
        game(white="opponent", result="checkmated"),
        game(white="opponent", result="timeout"),
        game(white="opponent", result="stalemate"),
    ]

    italian = opening(opening_distribution(games, "me"), "Italian Game")

    assert (italian["wins"], italian["draws"], italian["losses"]) == (2, 1, 1)


def test_the_username_matches_whatever_its_case():
    italian = opening(opening_distribution([game(white="Me", result="win")], "ME"), "Italian Game")

    assert italian["wins"] == 1


@pytest.mark.parametrize("white, expected", [("me", (0, 0, 1)), ("opponent", (1, 0, 0))])
def test_an_unlisted_result_code_is_a_loss_for_that_side(white, expected):
    games = [game(white=white, result="kingofthehill")]

    italian = opening(opening_distribution(games, "me"), "Italian Game")

    assert (italian["wins"], italian["draws"], italian["losses"]) == expected


@pytest.mark.parametrize("result", ["", None])
def test_a_game_with_no_result_is_played_but_has_no_win_draw_or_loss(result):
    games = [game(result="win"), game(result=result)]

    distribution = opening_distribution(games, "me")
    italian = opening(distribution, "Italian Game")

    assert distribution["total_games"] == 2
    assert italian["games"] == 2
    assert (italian["wins"], italian["draws"], italian["losses"]) == (1, 0, 0)
    assert italian["win_rate"] == 100.0


def test_an_opening_with_no_known_results_has_a_zero_win_rate():
    italian = opening(opening_distribution([game(result="")], "me"), "Italian Game")

    assert italian["win_rate"] == 0


@pytest.mark.parametrize("name", ["", None])
def test_a_game_without_an_opening_label_is_the_unknown_opening(name):
    distribution = opening_distribution([game(opening=name)], "me")

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

    assert opening_distribution(games, "me")["categories"] == [
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

    distribution = opening_distribution(games, "me")

    assert distribution["top_opening_names"] == ["A", "B", "C", "D", "E"]
    assert distribution["trends"] == [
        {"month": "2026-03", "A": 6, "B": 5, "C": 4, "D": 3, "E": 2},
        {"month": "2026-04", "A": 1, "B": 0, "C": 0, "D": 0, "E": 0},
    ]


def test_a_game_without_a_date_is_left_out_of_the_trend():
    undated = {**game(), "date": None}

    distribution = opening_distribution([undated], "me")

    assert distribution["total_games"] == 1
    assert distribution["trends"] == []
