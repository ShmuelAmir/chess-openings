import asyncio

import main
import sources
from sources import LichessRepertoireSource


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
        list_studies=lambda: main.fetch_studies_afresh(token),
        excluded_studies=set,
    )


def test_a_build_lists_the_studies_afresh_and_the_listing_cache_returns_them(monkeypatch):
    lichess = FakeLichess("italian")
    monkeypatch.setattr(main, "LichessClient", lichess)
    monkeypatch.setattr(sources, "LichessClient", lichess)
    token = "a build lists afresh"

    async def run():
        cached_before = await main.fetch_studies_cached(token)
        lichess.study_ids.append("sicilian")
        repertoire = await repertoire_source(token).fetch_repertoire()
        return cached_before, repertoire, await main.fetch_studies_cached(token)

    cached_before, repertoire, cached_after = asyncio.run(run())

    assert [study["id"] for study in cached_before] == ["italian"]
    assert set(repertoire.study_names) == {"italian", "sicilian"}
    assert [study["id"] for study in cached_after] == ["italian", "sicilian"]
    assert lichess.listings == 2
