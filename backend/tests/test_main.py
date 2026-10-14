import asyncio

import chess
import httpx
import pytest
from fastapi.testclient import TestClient

import main
import users
from chess_com import ChessComAccountNotFoundError
from drill_attempts import DrillAttempt, DrillAttemptStore
from exclusions import ExclusionStore
from game_cache import GameCache
from games import Game
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
    async def games(self, username):
        return [Game(url="g1", date=100, month=(2026, 3), time_class="blitz", rated=True,
                     opening_name="Italian Game", moves=("e4", "e5", "Bc4"),
                     color=chess.WHITE, result="loss")]


def sign_in(token, source, tmp_path, account="me"):
    """Make the token's User one of the Lichess account whose Repertoire comes from `source`."""
    exclusions = ExclusionStore(account, tmp_path / "app.db")
    drill_attempts = DrillAttemptStore(account, tmp_path / "app.db")
    users._users[users.token_key(token)] = users.User(
        users.token_key(token),
        account,
        RepertoireAnalysisPipeline(source, OneMiss(), drill_attempts=drill_attempts.attempts),
        ChessComSync(GameCache(tmp_path / "games.db"), client=None),
        exclusions,
        drill_attempts,
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

    async def owned_studies(token):
        return [{"id": "abc", "name": "Italian-Game"}]

    monkeypatch.setattr(main, "fetch_studies_cached", owned_studies)
    mine, theirs = ItalianSource(), ItalianSource()
    sign_in("my-token", mine, tmp_path, account="me")
    sign_in("their-token", theirs, tmp_path, account="them")
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
    their_list = TestClient(main.app).get("/api/not-repertoire", headers={"Authorization": "Bearer their-token"})
    assert their_list.json()["studies"][0]["excluded"] is False


def test_the_opening_distribution_is_of_the_cached_games_under_the_filters(monkeypatch, tmp_path):
    cache = GameCache(tmp_path / "games.db")
    cache.save_games("me", [
        {"url": "g1", "white": "me", "black": "x", "result": "win", "opening_name": "Italian Game", "date": 100},
        {"url": "g2", "white": "x", "black": "me", "result": "win", "opening_name": "Sicilian Defense", "date": 100},
    ], 2026, 2)
    cache.save_games("me", [
        {"url": "g3", "white": "me", "black": "x", "result": "win", "opening_name": "London System", "date": 100},
    ], 2026, 4)
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
    sync = asyncio.run(users.user_for("my-token")).sync

    asyncio.run(sync.run("me"))
    mine, other = get_sync("my-token", "Me"), get_sync("my-token", "you")

    assert asyncio.run(users.user_for("my-token")).sync is sync
    assert (mine["runs"], mine["result"] is not None) == (1, True)
    assert (other["runs"], other["result"]) == (0, None)
    assert mine["sources"]["lichess"] == other["sources"]["lichess"]
    assert other["sources"]["lichess"]["status"] == "ok"


class LichessAccounts:
    """Lichess, knowing each token's account; it refuses any other token."""

    def __init__(self, accounts):
        self.accounts = accounts

    def __call__(self, token=None):
        self.token = token
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        pass

    async def get_account(self):
        if self.token not in self.accounts:
            request = httpx.Request("GET", "https://lichess.org/api/account")
            raise httpx.HTTPStatusError(
                "401 Unauthorized", request=request, response=httpx.Response(401, request=request)
            )
        return {"username": self.accounts[self.token]}


@pytest.fixture
def lichess_accounts(monkeypatch, tmp_path):
    """Users made by users.user_for over these Lichess accounts and a temporary database."""
    monkeypatch.setattr(users, "_users", {})
    monkeypatch.setattr(users, "_accounts", {})
    monkeypatch.setattr(users, "ExclusionStore", lambda account: ExclusionStore(account, tmp_path / "app.db"))
    monkeypatch.setattr(users, "DrillAttemptStore", lambda account: DrillAttemptStore(account, tmp_path / "app.db"))
    monkeypatch.setattr(users, "get_game_cache", lambda: GameCache(tmp_path / "games.db"))
    lichess = LichessAccounts({"my-token": "Me", "my-new-token": "me", "their-token": "Them"})
    monkeypatch.setattr(users, "LichessClient", lichess)
    return lichess


def test_a_users_exclusions_and_drill_attempts_are_their_lichess_accounts(lichess_accounts):
    async def run():
        mine, mine_again, theirs = [
            await users.user_for(token) for token in ("my-token", "my-new-token", "their-token")
        ]
        mine.exclusions.set_excluded_studies({"scratch"})
        mine.drill_attempts.record("gap", passed=True, first_miss_position_key=None, at=100)
        return mine, mine_again, theirs

    mine, mine_again, theirs = asyncio.run(run())

    assert (mine.account, mine_again.account, theirs.account) == ("me", "me", "them")
    assert mine_again.exclusions.excluded_studies() == {"scratch"}
    assert len(mine_again.drill_attempts.attempts()) == 1
    assert theirs.exclusions.excluded_studies() == set()
    assert theirs.drill_attempts.attempts() == []
    assert mine.pipeline.drill_attempts() == mine.drill_attempts.attempts()
    assert theirs.pipeline.drill_attempts() == []


def test_lichess_is_asked_for_a_tokens_account_once(lichess_accounts):
    async def run():
        return await users.user_for("my-token"), await users.user_for("my-token")

    first, second = asyncio.run(run())
    lichess_accounts.accounts.clear()  # Lichess would now refuse it

    assert first is second
    assert asyncio.run(users.user_for("my-token")) is first


def post_drill_attempt(token):
    return TestClient(main.app).post(
        "/api/drill-attempts",
        json={"gap_position_key": "gap", "passed": True},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_a_drill_attempt_is_recorded_for_the_tokens_account(lichess_accounts, tmp_path):
    response = post_drill_attempt("my-token")

    assert response.status_code == 201
    assert [a.gap_position_key for a in DrillAttemptStore("me", tmp_path / "app.db").attempts()] == ["gap"]
    assert DrillAttemptStore("them", tmp_path / "app.db").attempts() == []


def test_recording_a_drill_attempt_with_a_refused_token_is_a_401(lichess_accounts):
    response = post_drill_attempt("revoked-token")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid Lichess token"}
