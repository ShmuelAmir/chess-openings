import asyncio

import chess

from pipeline import GameSource, RepertoireAnalysisPipeline, RepertoireSource
from repertoire import RepertoireBuilder


def repertoire_of(*study_ids):
    builder = RepertoireBuilder()
    for study_id in study_ids:
        builder.add_study("1. e4 e5 *\n", study_id, study_id=study_id)
    return builder.build()


class StudiesSource(RepertoireSource):
    """Builds a Repertoire from whatever studies it currently lists."""

    def __init__(self, *study_ids):
        self.study_ids = list(study_ids)
        self.fetches = 0

    async def fetch_repertoire(self):
        self.fetches += 1
        study_ids = list(self.study_ids)
        await asyncio.sleep(0)
        return repertoire_of(*study_ids)


class NoGames(GameSource):
    async def fetch_games(self, username, filters):
        return []


def test_the_repertoire_is_cached():
    source = StudiesSource("italian")
    pipeline = RepertoireAnalysisPipeline(source, NoGames())

    async def run():
        await pipeline.study_colors()
        await pipeline.study_colors()

    asyncio.run(run())

    assert source.fetches == 1


def test_an_invalidation_takes_effect_on_the_next_request():
    source = StudiesSource("italian", "scratch")
    pipeline = RepertoireAnalysisPipeline(source, NoGames())

    async def run():
        await pipeline.study_colors()
        source.study_ids = ["italian"]
        pipeline.invalidate_repertoire()
        return await pipeline.study_colors()

    assert asyncio.run(run()) == {"italian": chess.WHITE}


def test_an_invalidation_during_a_fetch_is_not_lost():
    source = StudiesSource("italian", "scratch")
    pipeline = RepertoireAnalysisPipeline(source, NoGames())

    async def run():
        in_flight = asyncio.create_task(pipeline.study_colors())
        await asyncio.sleep(0)  # the fetch has listed the old studies
        source.study_ids = ["italian"]
        pipeline.invalidate_repertoire()
        await in_flight
        return await pipeline.study_colors()

    assert asyncio.run(run()) == {"italian": chess.WHITE}
