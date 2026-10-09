import pytest

from game_result import player_result


@pytest.mark.parametrize(
    "white_result, user_is_white, expected",
    [
        ("win", True, "win"),
        ("win", False, "loss"),
        ("checkmated", True, "loss"),
        ("resigned", False, "win"),
        ("timeout", False, "win"),
        ("agreed", True, "draw"),
        ("repetition", False, "draw"),
        ("stalemate", True, "draw"),
        ("timevsinsufficient", False, "draw"),
        ("", True, ""),
    ],
)
def test_the_users_result_from_whites_chess_com_result(white_result, user_is_white, expected):
    assert player_result(white_result, user_is_white) == expected
