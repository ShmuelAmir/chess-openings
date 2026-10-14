"""
Game - one of the user's games, as it crosses the game seam.

The user's side of it (their color and their result) is already decided, so
no reader works it out again from the players' names.
"""
from dataclasses import dataclass
from typing import Optional

import chess


@dataclass(frozen=True)
class Game:
    """One of the user's games."""
    url: str
    date: Optional[int]  # Unix timestamp the game ended; None when unknown
    month: tuple[int, int]  # (year, month) of the Chess.com archive it came from
    time_class: str
    rated: bool
    opening_name: str  # Chess.com's opening label; "" when it has none
    moves: tuple[str, ...]
    color: chess.Color  # the user's color
    result: str  # the user's result: "win", "loss", "draw", or "" when unknown
