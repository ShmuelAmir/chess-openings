import asyncio

from drill_attempts import DrillAttempt
from pipeline import GameSource, RepertoireAnalysisPipeline, RepertoireSource
from recall_gaps import RecallFilters
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


async def studies(pipeline):
    """The ids of the studies in the pipeline's recall view."""
    view = await pipeline.recall_view("me", RecallFilters())
    return [study.id for study in view.studies]


def test_the_repertoire_is_cached():
    source = StudiesSource("italian")
    pipeline = RepertoireAnalysisPipeline(source, NoGames())

    async def run():
        await studies(pipeline)
        await studies(pipeline)

    asyncio.run(run())

    assert source.fetches == 1


def test_an_invalidation_takes_effect_on_the_next_request():
    source = StudiesSource("italian", "scratch")
    pipeline = RepertoireAnalysisPipeline(source, NoGames())

    async def run():
        await studies(pipeline)
        source.study_ids = ["italian"]
        pipeline.invalidate_repertoire()
        return await studies(pipeline)

    assert asyncio.run(run()) == ["italian"]


def test_an_invalidation_during_a_fetch_is_not_lost():
    source = StudiesSource("italian", "scratch")
    pipeline = RepertoireAnalysisPipeline(source, NoGames())

    async def run():
        in_flight = asyncio.create_task(studies(pipeline))
        await asyncio.sleep(0)  # the fetch has listed the old studies
        source.study_ids = ["italian"]
        pipeline.invalidate_repertoire()
        await in_flight
        return await studies(pipeline)

    assert asyncio.run(run()) == ["italian"]


class CountingGames(GameSource):
    """One game; counts how often the games are fetched for analysis."""

    def __init__(self):
        self.fetches = 0

    async def fetch_games(self, username, filters):
        self.fetches += 1
        return [{"url": "g1", "white": "me", "black": "them", "moves": ["e4", "c5"], "date": 1}]


def test_a_refresh_reports_whether_the_repertoire_changed():
    source = StudiesSource("italian")
    pipeline = RepertoireAnalysisPipeline(source, NoGames())

    async def run():
        await studies(pipeline)
        unchanged = await pipeline.refresh_repertoire()
        source.study_ids = ["italian", "spanish"]
        changed = await pipeline.refresh_repertoire()
        return unchanged, changed, await studies(pipeline)

    unchanged, changed, study_ids = asyncio.run(run())

    assert (unchanged, changed) == (False, True)
    assert set(study_ids) == {"italian", "spanish"}
    assert source.fetches == 3


def test_the_analysis_is_reused_until_something_changes():
    games = CountingGames()
    source = StudiesSource("italian")
    pipeline = RepertoireAnalysisPipeline(source, games)

    async def run():
        await pipeline.recall_view("me", RecallFilters())
        await pipeline.recall_view("me", RecallFilters(rated_only=True))
        await pipeline.refresh_repertoire()  # unchanged
        await pipeline.recall_view("me", RecallFilters())
        reused = games.fetches
        pipeline.invalidate_games()
        await pipeline.recall_view("me", RecallFilters())
        after_new_games = games.fetches
        source.study_ids = ["italian", "spanish"]
        await pipeline.refresh_repertoire()
        await pipeline.recall_view("me", RecallFilters())
        return reused, after_new_games, games.fetches

    assert asyncio.run(run()) == (1, 2, 3)


def test_a_refresh_joins_a_build_already_in_flight():
    source = StudiesSource("italian")
    pipeline = RepertoireAnalysisPipeline(source, NoGames())

    async def run():
        building = asyncio.create_task(studies(pipeline))
        await asyncio.sleep(0)
        await pipeline.refresh_repertoire()
        await building

    asyncio.run(run())

    assert source.fetches == 1


def test_a_refresh_skips_a_repertoire_fetched_moments_ago():
    source = StudiesSource("italian")
    pipeline = RepertoireAnalysisPipeline(source, NoGames())

    async def run():
        await studies(pipeline)
        return await pipeline.refresh_repertoire(fresh_within=30)

    assert asyncio.run(run()) is False
    assert source.fetches == 1


class FixedGames(GameSource):
    def __init__(self, games):
        self.games = games

    async def fetch_games(self, username, filters):
        return self.games


class ItalianSource(RepertoireSource):
    async def fetch_repertoire(self):
        builder = RepertoireBuilder()
        builder.add_study("1. e4 e5 2. Nf3 *\n", "italian", study_id="italian")
        return builder.build()


def test_gap_statuses_cover_every_game():
    games = FixedGames([
        {"white": "me", "black": "x", "moves": ["e4", "e5", "Bc4"], "url": "g1",
         "date": 100, "time_class": "bullet", "rated": False},
    ])
    pipeline = RepertoireAnalysisPipeline(ItalianSource(), games)

    async def run():
        before = pipeline.last_gap_statuses("me")
        statuses = await pipeline.gap_statuses("me")
        return before, statuses, pipeline.last_gap_statuses("me"), pipeline.last_gap_statuses("other")

    before, statuses, last, other = asyncio.run(run())

    assert before is None  # no analysis yet, and none is run for it
    assert list(statuses.values()) == ["open"]
    assert last == statuses
    assert other is None


def test_the_practice_queue_reads_the_drill_attempts():
    games = FixedGames([
        {"white": "me", "black": "x", "moves": ["e4", "e5", "Bc4"], "url": "g1",
         "date": 100, "time_class": "blitz", "rated": True},
    ])
    attempts = []
    pipeline = RepertoireAnalysisPipeline(ItalianSource(), games, drill_attempts=lambda: attempts)

    async def queue():
        return await pipeline.practice_queue("me", RecallFilters(), now=200)

    view = asyncio.run(pipeline.recall_view("me", RecallFilters(), now=200))
    assert asyncio.run(queue()) == view.gaps  # never drilled: due, as the view shows it
    gap_key = view.gaps[0].position_key
    attempts.append(DrillAttempt(gap_key, at=150, passed=True, first_miss_position_key=None))
    assert asyncio.run(queue()) == []  # passed: held back a day


class NamedSource(RepertoireSource):
    """An Italian study and a Sicilian one, under the names they have on Lichess."""

    async def fetch_repertoire(self):
        builder = RepertoireBuilder()
        builder.add_study(
            '[ChapterURL "https://lichess.org/study/abc/ch1"]\n\n1. e4 e5 2. Nf3 *\n',
            "Italian Game", study_name="White: Italian-Game", study_id="abc",
        )
        builder.add_study(
            '[Orientation "black"]\n\n1. e4 c5 *\n', "Sicilian", study_name="alapin", study_id="xyz",
        )
        return builder.build()


BC4_MISS = {"white": "me", "black": "x", "moves": ["e4", "e5", "Bc4"], "url": "g1",
            "date": 100, "time_class": "blitz", "rated": True}


def test_the_recall_view_lists_the_studies_by_opening_name():
    pipeline = RepertoireAnalysisPipeline(NamedSource(), FixedGames([BC4_MISS]))

    view = asyncio.run(pipeline.recall_view("me", RecallFilters()))

    assert [(s.id, s.name, s.opening_name, s.color, s.gaps) for s in view.studies] == [
        ("xyz", "alapin", "alapin", "black", 0),
        ("abc", "White: Italian-Game", "Italian Game", "white", 1),
    ]


def test_the_recall_views_gaps_name_and_link_their_studies():
    pipeline = RepertoireAnalysisPipeline(NamedSource(), FixedGames([BC4_MISS]))

    async def run():
        view = await pipeline.recall_view("me", RecallFilters())
        return view.gaps, await pipeline.practice_queue("me", RecallFilters())

    gaps, queue = asyncio.run(run())

    assert [(s.id, s.name, s.url) for s in gaps[0].studies] == [
        ("abc", "White: Italian-Game", "https://lichess.org/study/abc/ch1#2"),
    ]
    assert queue == gaps


def test_a_renamed_study_shows_once_the_repertoire_is_rebuilt():
    class Renamed(RepertoireSource):
        name = "Italian"

        async def fetch_repertoire(self):
            builder = RepertoireBuilder()
            builder.add_study("1. e4 e5 *\n", "Italian", study_name=self.name, study_id="abc")
            return builder.build()

    source = Renamed()
    pipeline = RepertoireAnalysisPipeline(source, NoGames())

    async def run():
        before = (await pipeline.recall_view("me", RecallFilters())).studies[0].name
        source.name = "Giuoco Piano"
        cached = (await pipeline.recall_view("me", RecallFilters())).studies[0].name
        changed = await pipeline.refresh_repertoire()
        return before, cached, changed, (await pipeline.recall_view("me", RecallFilters())).studies[0].name

    assert asyncio.run(run()) == ("Italian", "Italian", True, "Giuoco Piano")
