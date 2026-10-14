import asyncio

import httpx
from fastapi.testclient import TestClient

import main
import users
from chess_com import ChessComAccountNotFoundError
from exclusions import ExclusionStore
from game_cache import GameCache
from pipeline import GameSource, RepertoireAnalysisPipeline, RepertoireSource
from repertoire import RepertoireBuilder
from sync import ChessComSync, RepertoireSyncLog


class ItalianSource(RepertoireSource):
    def __init__(self):
        self.fetches = 0

    async def fetch_repertoire(self):
        self.fetches += 1
        builder = RepertoireBuilder()
        builder.add_study(
            '[ChapterURL "https://lichess.org/study/abc/ch1"]\n\n1. e4 e5 2. Nf3 *\n',
            "Italian Game", study_name="Italian-Game", study_id="abc",
        )
        return builder.build()


class RefusedSource(RepertoireSource):
    """Lichess refuses the token."""

    async def fetch_repertoire(self):
        request = httpx.Request("GET", "https://lichess.org/api/account")
        raise httpx.HTTPStatusError(
            "401 Unauthorized", request=request, response=httpx.Response(401, request=request)
        )


class OneMiss(GameSource):
    async def fetch_games(self, username, filters):
        return [{"white": "me", "black": "x", "moves": ["e4", "e5", "Bc4"], "url": "g1",
                 "date": 100, "time_class": "blitz", "rated": True, "user_result": "loss"}]


def sign_in(token, source, tmp_path):
    """Make the token's User one whose Repertoire comes from `source`."""
    users._users[users.token_key(token)] = users.User(
        users.token_key(token),
        RepertoireAnalysisPipeline(source, OneMiss()),
        ChessComSync(GameCache(tmp_path / "games.db"), client=None),
    )


def get_recall_view(token):
    return TestClient(main.app).get(
        "/api/recall-view",
        params={"chess_com_username": "me", "date_range": "all", "studies": ["abc"]},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_the_recall_view_is_served_as_the_pipeline_returns_it(monkeypatch, tmp_path):
    monkeypatch.setattr(users, "_users", {})
    sign_in("good-token", ItalianSource(), tmp_path)
    sign_in("bad-token", RefusedSource(), tmp_path)

    response = get_recall_view("good-token")

    assert response.status_code == 200
    view = response.json()
    assert set(view) == {"studies", "gaps", "totals"}
    assert view["studies"] == [
        {"id": "abc", "name": "Italian-Game", "opening_name": "Italian Game", "color": "white", "gaps": 1}
    ]
    assert view["totals"] == {
        "analysed": 1, "opponent_left_book": 0, "book_completed": 0, "miss_rate": 1.0,
        "trend": view["totals"]["trend"], "open_gaps": 1, "closed_in_range": 0,
    }
    assert set(view["totals"]["trend"][0]) == {"month", "games", "miss_rate"}
    (gap,) = view["gaps"]
    assert gap == {
        "position_key": gap["position_key"],
        "color": "white",
        "path": ["e4", "e5"],
        "wrong_moves": [{"san": "Bc4", "count": 1}],
        "book_moves": ["Nf3"],
        "studies": [{"id": "abc", "name": "Italian-Game", "url": "https://lichess.org/study/abc/ch1#2"}],
        "occurrences": 1,
        "last_seen": 100,
        "status": "open",
        "progress": 0,
        "games_to_close": 2,
        "closed_at": None,
        "drill_turns": gap["drill_turns"],
        "games": [{"url": "g1", "date": 100, "time_class": "blitz", "move_played": "Bc4", "result": "loss"}],
    }
    assert set(gap["drill_turns"][0]) == {"ply", "position_key", "book_moves"}

    refused = get_recall_view("bad-token")

    assert refused.status_code == 401
    assert refused.json() == {"detail": "Invalid Lichess token"}


def test_changing_the_not_repertoire_list_rebuilds_only_that_users_repertoire(monkeypatch, tmp_path):
    monkeypatch.setattr(users, "_users", {})
    monkeypatch.setattr(main, "get_exclusion_store", lambda: ExclusionStore(tmp_path / "app.db"))

    async def owned_studies(token):
        return [{"id": "abc", "name": "Italian-Game"}]

    monkeypatch.setattr(main, "fetch_studies_cached", owned_studies)
    mine, theirs = ItalianSource(), ItalianSource()
    sign_in("my-token", mine, tmp_path)
    sign_in("their-token", theirs, tmp_path)
    get_recall_view("my-token")
    get_recall_view("their-token")

    response = TestClient(main.app).put(
        "/api/not-repertoire", json={"excluded": ["abc"]},
        headers={"Authorization": "Bearer my-token"},
    )
    get_recall_view("my-token")
    get_recall_view("their-token")

    assert response.json()["studies"][0]["excluded"] is True
    assert (mine.fetches, theirs.fetches) == (2, 1)


class CachedGames:
    """A game cache holding one win as White in the Italian."""

    def get_cached_games(self, **filters):
        self.filters = filters
        return [{"white": "me", "black": "x", "result": "win",
                 "opening_name": "Italian Game", "date": 100}]


def test_the_opening_distribution_is_of_the_cached_games_under_the_filters(monkeypatch):
    cache = CachedGames()
    monkeypatch.setattr(main, "get_game_cache", lambda: cache)

    response = TestClient(main.app).post(
        "/api/opening-stats",
        params={"chess_com_username": "me", "from_year": 2026, "from_month": 1,
                "to_year": 2026, "to_month": 3, "color": "white"},
    )

    assert response.status_code == 200
    assert response.json()["top_openings"] == [
        {"opening": "Italian Game", "games": 1, "wins": 1, "draws": 0, "losses": 0, "win_rate": 100.0}
    ]
    assert cache.filters["username"] == "me"
    assert cache.filters["color"] == "white"
    assert (cache.filters["from_year"], cache.filters["to_month"]) == (2026, 3)


class NoSuchAccount:
    """Chess.com has no such account."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        pass

    async def get_archives(self, username):
        raise ChessComAccountNotFoundError(username)


def test_validating_an_unknown_chess_com_account_is_a_404(monkeypatch):
    monkeypatch.setattr(main, "ChessComClient", NoSuchAccount)

    response = TestClient(main.app).get("/api/chess-com/validate/nobody")

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "No Chess.com account named 'nobody'. Use your Chess.com username, not your email."
    )


def get_sync(token, chess_com_username):
    return TestClient(main.app).get(
        "/api/sync",
        params={"chess_com_username": chess_com_username},
        headers={"Authorization": f"Bearer {token}"},
    ).json()


def test_each_linked_account_is_reported_by_the_users_one_sync(monkeypatch, tmp_path):
    monkeypatch.setattr(users, "_users", {})
    monkeypatch.setattr(users, "RepertoireSyncLog", lambda user: RepertoireSyncLog(tmp_path / "app.db", user))
    sign_in("my-token", ItalianSource(), tmp_path)
    sync = users.user_for("my-token").sync

    asyncio.run(sync.run("me"))
    mine, other = get_sync("my-token", "Me"), get_sync("my-token", "you")

    assert users.user_for("my-token").sync is sync
    assert (mine["runs"], mine["result"] is not None) == (1, True)
    assert (other["runs"], other["result"]) == (0, None)
    assert mine["sources"]["lichess"] == other["sources"]["lichess"]
    assert other["sources"]["lichess"]["status"] == "ok"
