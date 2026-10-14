import asyncio

import chess
import pytest

import sources
import users
from game_cache import GameCache
from games import Game
from sources import CacheGameSource, LichessRepertoireSource


class FakeLichess:
    """A Lichess account whose owned studies can change between listings."""

    def __init__(self, *study_ids):
        self.study_ids = list(study_ids)
        self.listings = 0

    def __call__(self, token=None):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        pass

    async def get_account(self):
        return {"username": "me"}

    async def get_user_studies(self, username):
        self.listings += 1
        return [{"id": study_id, "name": study_id} for study_id in self.study_ids]

    async def get_study_pgn_with_normalized_name(self, study_id, study_name):
        pgn = f'[ChapterURL "https://lichess.org/study/{study_id}/ch1"]\n\n1. e4 e5 *\n'
        return pgn, study_name


def repertoire_source(token):
    return LichessRepertoireSource(
        lichess_token=token,
        list_studies=lambda: users.fetch_studies_afresh(token),
        excluded_studies=set,
    )


def test_a_build_lists_the_studies_afresh_and_the_listing_cache_returns_them(monkeypatch):
    lichess = FakeLichess("italian")
    monkeypatch.setattr(users, "LichessClient", lichess)
    monkeypatch.setattr(sources, "LichessClient", lichess)
    token = "a build lists afresh"

    async def run():
        cached_before = await users.fetch_studies_cached(token)
        lichess.study_ids.append("sicilian")
        repertoire = await repertoire_source(token).fetch_repertoire()
        return cached_before, repertoire, await users.fetch_studies_cached(token)

    cached_before, repertoire, cached_after = asyncio.run(run())

    assert [study["id"] for study in cached_before] == ["italian"]
    assert set(repertoire.study_names) == {"italian", "sicilian"}
    assert [study["id"] for study in cached_after] == ["italian", "sicilian"]
    assert lichess.listings == 2


def cached_games(tmp_path, *games, username="me", month=(2026, 3)):
    """The user's games as CacheGameSource reads them back from a game cache holding `games`."""
    cache = GameCache(tmp_path / "games.db")
    cache.save_games(username, list(games), *month)
    return asyncio.run(CacheGameSource(cache).games(username))


def cached(url="g1", white="me", black="opponent", result="win", **fields):
    """A game as the Chess.com sync caches it; `result` is White's result code."""
    return {"url": url, "white": white, "black": black, "result": result, **fields}


def test_a_cached_game_becomes_the_users_game(tmp_path):
    games = cached_games(tmp_path, cached(
        url="g1", date=100, time_class="blitz", rated=True,
        opening_name="Italian Game", moves=["e4", "e5"],
    ))

    assert games == [Game(
        url="g1", date=100, month=(2026, 3), time_class="blitz", rated=True,
        opening_name="Italian Game", moves=("e4", "e5"), color=chess.WHITE, result="win",
    )]


@pytest.mark.parametrize("white, result, expected", [
    ("me", "win", (chess.WHITE, "win")),
    ("me", "resigned", (chess.WHITE, "loss")),
    ("me", "agreed", (chess.WHITE, "draw")),
    ("opponent", "win", (chess.BLACK, "loss")),
    ("opponent", "checkmated", (chess.BLACK, "win")),
    ("opponent", "stalemate", (chess.BLACK, "draw")),
    ("opponent", "kingofthehill", (chess.BLACK, "win")),
    ("me", "", (chess.WHITE, "")),
])
def test_the_users_color_and_result_are_decided_from_whites_result_code(tmp_path, white, result, expected):
    black = "me" if white == "opponent" else "opponent"

    [game] = cached_games(tmp_path, cached(white=white, black=black, result=result))

    assert (game.color, game.result) == expected


def test_the_username_matches_whatever_its_case(tmp_path):
    cache = GameCache(tmp_path / "games.db")
    cache.save_games("Me", [cached(white="ME", black="opponent", result="win")], 2026, 3)

    [game] = asyncio.run(CacheGameSource(cache).games("mE"))

    assert (game.color, game.result) == (chess.WHITE, "win")


def test_a_cached_game_missing_its_details_has_their_empty_values(tmp_path):
    [game] = cached_games(tmp_path, {"url": "g1", "white": "opponent", "black": "me"})

    assert (game.date, game.time_class, game.rated, game.opening_name, game.moves, game.result) == (
        None, "", False, "", (), "",
    )
    assert game.color == chess.BLACK
