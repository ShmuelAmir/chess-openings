"""
The result rule - the user's result in a game, from White's Chess.com result code.

Pure. Shared by the recall view and the Opening Distribution.
"""

# Chess.com result codes that end a game in a draw
_DRAW_RESULTS = {"agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"}


def player_result(white_result: str, user_is_white: bool) -> str:
    """
    The user's result ("win", "loss" or "draw") from White's Chess.com result code.

    Returns "" when the result is unknown.
    """
    if not white_result:
        return ""
    if white_result in _DRAW_RESULTS:
        return "draw"
    white_won = white_result == "win"
    return "win" if white_won == user_is_white else "loss"
