import httpx
from fastapi.testclient import TestClient

import main
from pipeline import GameSource, RepertoireAnalysisPipeline, RepertoireSource
from repertoire import RepertoireBuilder


class ItalianSource(RepertoireSource):
    async def fetch_repertoire(self):
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


def get_recall_view(token, source):
    main._pipelines[main._token_key(token)] = RepertoireAnalysisPipeline(source, OneMiss())
    return TestClient(main.app).get(
        "/api/recall-view",
        params={"chess_com_username": "me", "date_range": "all", "studies": ["abc"]},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_the_recall_view_is_served_as_the_pipeline_returns_it(monkeypatch):
    monkeypatch.setattr(main, "_pipelines", {})

    response = get_recall_view("good-token", ItalianSource())

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

    refused = get_recall_view("bad-token", RefusedSource())

    assert refused.status_code == 401
    assert refused.json() == {"detail": "Invalid Lichess token"}
