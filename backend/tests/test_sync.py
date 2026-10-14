import asyncio
from datetime import datetime

from chess_com import ChessComAccountNotFoundError
from game_cache import GameCache
from pipeline import RepertoireAnalysisPipeline, RepertoireSource
from recall_gaps import RecallFilters
from repertoire import RepertoireBuilder
from sources import CacheGameSource
from sync import ChessComSync, GamesSyncResult, GapChanges, RepertoireSyncLog, Sync, gap_changes

ARCHIVES = "https://api.chess.com/pub/player/magnus/games/{}/{:02d}"


def game(url, moves=("e4",), date=1):
    return {"url": url, "date": date, "white": "magnus", "black": "hikaru", "moves": list(moves)}


class FakeChessCom:
    """A Chess.com account whose months can be made to fail."""

    def __init__(self, months):
        self.months = {month: list(games) for month, games in months.items()}
        self.failing = set()
        self.fetched = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        pass

    async def get_archives(self, username):
        return [ARCHIVES.format(*month) for month in sorted(self.months)]

    async def get_all_games_for_month(self, username, year, month):
        self.fetched.append((year, month))
        if (year, month) in self.failing:
            raise RuntimeError("Chess.com is down")
        return [g if isinstance(g, dict) else game(g) for g in self.months[(year, month)]]


def chess_com_sync(tmp_path, account, now=datetime(2024, 3, 15)):
    cache = GameCache(tmp_path / "games.db")
    return cache, ChessComSync(cache, client=lambda: account, now=lambda: now)


def sync_games(games_sync, on_month=lambda year, month: None):
    return asyncio.run(games_sync.sync("magnus", on_month))


def test_the_first_sync_fetches_every_month(tmp_path):
    account = FakeChessCom({(2024, 1): ["a"], (2024, 2): ["b", "c"], (2024, 3): ["d"]})
    cache, games_sync = chess_com_sync(tmp_path, account)

    result = sync_games(games_sync)

    assert result == GamesSyncResult(new_games=4, failed_months=[])
    assert cache.count_games("magnus") == 4


def test_progress_names_each_month_being_fetched(tmp_path):
    account = FakeChessCom({(2023, 4): ["a"], (2023, 5): ["b"]})
    _, games_sync = chess_com_sync(tmp_path, account)
    seen = []

    sync_games(games_sync, lambda year, month: seen.append((year, month)))

    assert seen == [(2023, 4), (2023, 5)]


def test_a_later_sync_refetches_only_from_the_month_of_the_last_sync(tmp_path):
    account = FakeChessCom({(2024, 1): ["a"], (2024, 2): ["b"]})
    _, games_sync = chess_com_sync(tmp_path, account, now=datetime(2024, 2, 20))
    sync_games(games_sync)
    account.fetched.clear()
    account.months[(2024, 2)].append("late february game")
    account.months[(2024, 3)] = ["march game"]
    _, games_sync = chess_com_sync(tmp_path, account, now=datetime(2024, 3, 2))

    result = sync_games(games_sync)

    assert account.fetched == [(2024, 2), (2024, 3)]
    assert result.new_games == 2


def test_a_sync_with_nothing_new_reports_no_new_games(tmp_path):
    account = FakeChessCom({(2024, 3): ["a"]})
    _, games_sync = chess_com_sync(tmp_path, account)
    sync_games(games_sync)

    assert sync_games(games_sync).new_games == 0


def test_a_failed_month_is_fetched_again_on_the_next_sync(tmp_path):
    account = FakeChessCom({(2023, 1): ["a"], (2023, 2): ["b"], (2024, 3): ["c"]})
    account.failing = {(2023, 1)}
    cache, games_sync = chess_com_sync(tmp_path, account)

    first = sync_games(games_sync)
    account.failing = set()
    account.fetched.clear()
    second = sync_games(games_sync)

    assert first.failed_months == [(2023, 1)]
    assert account.fetched == [(2023, 1), (2024, 3)]
    assert second == GamesSyncResult(new_games=1, failed_months=[])
    assert cache.count_games("magnus") == 3


def test_the_last_sync_time_does_not_advance_when_a_month_fails(tmp_path):
    account = FakeChessCom({(2024, 2): ["a"], (2024, 3): ["b"]})
    cache, games_sync = chess_com_sync(tmp_path, account)
    sync_games(games_sync)
    synced_at = cache.get_sync_status("magnus")["last_sync_at"]
    account.failing = {(2024, 3)}

    sync_games(games_sync)

    assert cache.get_sync_status("magnus")["last_sync_at"] == synced_at


def test_a_first_sync_with_a_failed_month_has_no_last_sync_time(tmp_path):
    account = FakeChessCom({(2024, 2): ["a"], (2024, 3): ["b"]})
    account.failing = {(2024, 2)}
    cache, games_sync = chess_com_sync(tmp_path, account)

    sync_games(games_sync)

    assert cache.get_sync_status("magnus")["last_sync_at"] is None
    assert cache.get_failed_months("magnus") == {(2024, 2)}


# ---- Sync: both sources ----


class InMemoryLog:
    """A RepertoireSyncLog that forgets everything on restart."""

    def __init__(self):
        self.last_success_at = None

    def last_success(self):
        return self.last_success_at

    def record_success(self, at):
        self.last_success_at = at


class Clock:
    """The one clock the pipeline and the Sync share; moved by hand."""

    def __init__(self, at=1000):
        self.at = at

    def __call__(self):
        return self.at


class ItalianStudy(RepertoireSource):
    """The user's Lichess Repertoire: 1. e4 e5 2. Nf3 as White, then whatever lines are added."""

    def __init__(self):
        self.lines = ["1. e4 e5 2. Nf3 *"]
        self.error = None
        self.fetches = 0
        self.on_fetch = lambda: None

    async def fetch_repertoire(self):
        self.fetches += 1
        self.on_fetch()
        if self.error:
            raise self.error
        builder = RepertoireBuilder()
        builder.add_study("\n\n".join(self.lines) + "\n", "Italian Game", study_id="italian")
        return builder.build()


class CountedGames(CacheGameSource):
    """The game cache, counting how often the analysis reads it."""

    def __init__(self, cache):
        super().__init__(cache)
        self.reads = 0
        self.error = None

    async def fetch_games(self, username, filters):
        self.reads += 1
        if self.error:
            raise self.error
        return await super().fetch_games(username, filters)


# White plays Bc4 where the Repertoire has Nf3: one occurrence of a Recall Gap
MISS = ["e4", "e5", "Bc4"]
BOOK = ["e4", "e5", "Nf3"]


class World:
    """One user's Sync over the real pipeline, game cache and Chess.com sync."""

    def __init__(self, tmp_path, months=None, account=None, now=datetime(2024, 3, 15)):
        self.account = account or FakeChessCom(months or {})
        self.cache = GameCache(tmp_path / "games.db")
        self.clock = Clock()
        self.studies = ItalianStudy()
        self.games = CountedGames(self.cache)
        self.pipeline = RepertoireAnalysisPipeline(self.studies, self.games, clock=self.clock)
        self.games_sync = ChessComSync(self.cache, client=lambda: self.account, now=lambda: now)
        self.repertoire_log = InMemoryLog()

    def sync(self, username="magnus"):
        return Sync(self.pipeline, self.games_sync, username, self.repertoire_log, clock=self.clock)

    def analyse(self):
        """Open the recall view, as the page does: the last analysis."""
        return asyncio.run(self.pipeline.recall_view("magnus", RecallFilters()))


def run(sync):
    return asyncio.run(sync.run())


def test_a_sync_reports_new_games_and_reanalyses(tmp_path):
    world = World(tmp_path, {(2024, 3): [game("a", MISS), game("b", BOOK), game("c", BOOK)]})
    world.analyse()

    result = run(world.sync())

    assert (result.games_changed, result.repertoire_changed, result.new_games) == (True, False, 3)
    assert world.games.reads == 2


def test_a_sync_that_changed_nothing_does_not_reanalyse(tmp_path):
    world = World(tmp_path, {(2024, 3): [game("a", MISS)]})
    run(world.sync())
    world.analyse()

    result = run(world.sync())

    assert (result.games_changed, result.repertoire_changed) == (False, False)
    assert world.games.reads == 1


def test_a_repertoire_change_is_reported(tmp_path):
    world = World(tmp_path)
    world.analyse()
    world.studies.lines.append("1. e4 c5 2. Nf3 *")
    world.clock.at += 60

    assert run(world.sync()).repertoire_changed


def test_a_repertoire_fetched_moments_ago_is_not_fetched_again(tmp_path):
    world = World(tmp_path)
    world.analyse()
    sync = world.sync()

    world.clock.at += 29
    run(sync)
    fetched_within_30_seconds = world.studies.fetches
    lichess = sync.status()["sources"]["lichess"]
    world.clock.at += 2
    run(sync)

    assert fetched_within_30_seconds == 1
    assert lichess == {"status": "ok", "last_success_at": 1029, "error": None}
    assert world.studies.fetches == 2


def test_each_source_records_its_own_last_success(tmp_path):
    world = World(tmp_path, {(2024, 3): [game("a")]})
    sync = world.sync()

    run(sync)

    status = sync.status()
    assert status["sources"]["chess_com"]["status"] == "ok"
    assert status["sources"]["chess_com"]["last_success_at"] is not None
    assert status["sources"]["lichess"] == {"status": "ok", "last_success_at": 1000, "error": None}


def test_last_synced_is_the_older_of_the_two_sources(tmp_path):
    world = World(tmp_path, {(2024, 3): [game("a")]})
    sync = world.sync()

    world.clock.at = 4_000_000_000  # Lichess syncs after the game cache's real time
    assert sync.status()["last_synced_at"] is None
    run(sync)
    chess_com_synced_at = sync.status()["sources"]["chess_com"]["last_success_at"]
    assert sync.status()["last_synced_at"] == chess_com_synced_at < 4_000_000_000


def test_a_failed_lichess_refresh_keeps_the_new_games(tmp_path):
    world = World(tmp_path, {(2024, 3): [game("a"), game("b")]})
    world.studies.error = RuntimeError("Lichess is down")
    sync = world.sync()

    result = run(sync)

    assert result.games_changed
    assert sync.status()["sources"]["lichess"] == {
        "status": "failed", "last_success_at": None, "error": "Lichess is down",
    }
    assert sync.status()["sources"]["chess_com"]["status"] == "ok"
    assert sync.status()["cached_games"] == 2


class ChessComDown(FakeChessCom):
    def __init__(self):
        super().__init__({})

    async def get_archives(self, username):
        raise RuntimeError("Chess.com is down")


def test_a_failed_chess_com_sync_keeps_the_repertoire_refresh(tmp_path):
    world = World(tmp_path, account=ChessComDown())
    world.analyse()
    world.studies.lines.append("1. e4 c5 2. Nf3 *")
    world.clock.at += 60
    sync = world.sync()

    result = run(sync)

    assert result.repertoire_changed and not result.games_changed
    assert sync.status()["sources"]["chess_com"]["status"] == "failed"
    assert sync.status()["sources"]["lichess"]["status"] == "ok"


class UnknownAccount(FakeChessCom):
    """Chess.com has no such account."""

    def __init__(self):
        super().__init__({})

    async def get_archives(self, username):
        raise ChessComAccountNotFoundError(username)


def test_a_sync_against_an_unknown_account_names_it(tmp_path):
    world = World(tmp_path, account=UnknownAccount())
    sync = world.sync("nobody")

    run(sync)

    assert sync.status()["sources"]["chess_com"] == {
        "status": "failed",
        "last_success_at": None,
        "error": "No Chess.com account named 'nobody'",
    }
    assert sync.status()["sources"]["lichess"]["status"] == "ok"


def test_failed_months_mark_chess_com_failed_and_name_them(tmp_path):
    world = World(tmp_path, {(2023, 4): [game("a")], (2024, 3): [game("b")]})
    world.account.failing = {(2023, 4)}
    sync = world.sync()

    result = run(sync)

    chess_com = sync.status()["sources"]["chess_com"]
    assert result.games_changed
    assert chess_com["status"] == "failed"
    assert "2023-04" in chess_com["error"]


class Watched(FakeChessCom):
    """Notes the Sync's progress as each month is fetched."""

    def __init__(self, months):
        super().__init__(months)
        self.sync = None
        self.progress = []

    async def get_all_games_for_month(self, username, year, month):
        self.progress.append(self.sync.status()["progress"])
        return await super().get_all_games_for_month(username, year, month)


def test_progress_names_the_month_being_fetched(tmp_path):
    account = Watched({(2023, 4): [game("a")]})
    world = World(tmp_path, account=account)
    sync = account.sync = world.sync()

    run(sync)

    assert account.progress == ["Fetching games… 2023-04"]
    assert sync.status()["progress"] is None
    assert sync.status()["running"] is False


def test_new_games_drop_the_last_analysis_before_the_lichess_refresh(tmp_path):
    world = World(tmp_path, {(2024, 3): [game("a", MISS)]})
    world.analyse()
    world.account.months[(2024, 3)].append(game("b", MISS))
    world.clock.at += 60
    last_analysis_when_fetched = []
    world.studies.on_fetch = lambda: last_analysis_when_fetched.append(
        world.pipeline.last_gap_statuses("magnus")
    )

    run(world.sync())

    assert last_analysis_when_fetched == [None]


def test_the_lichess_last_success_survives_a_restart(tmp_path):
    world = World(tmp_path)
    world.repertoire_log = RepertoireSyncLog(tmp_path / "app.db")
    run(world.sync())

    world.repertoire_log = RepertoireSyncLog(tmp_path / "app.db")
    restarted = world.sync()

    assert restarted.status()["sources"]["lichess"]["last_success_at"] == 1000


def test_a_sync_reports_what_changed_in_the_analysis(tmp_path):
    # Two Recall Gaps as White: Bc4 for 2. Nf3 (X) and Bb5 for 3. Bc4 (Y)
    world = World(tmp_path, {(2024, 2): [
        game("g1", MISS, date=10),                                 # X
        game("g2", ["e4", "e5", "Nf3", "Nc6", "Bb5"], date=20),   # Y; X book once
        game("g3", BOOK, date=30),                                 # X book twice: Closed
    ]})
    world.studies.lines = ["1. e4 e5 2. Nf3 Nc6 3. Bc4 *", "1. e4 c5 2. Nf3 *"]
    run(world.sync())
    world.analyse()
    world.account.months[(2024, 3)] = [
        game("g4", ["e4", "e5", "Nf3", "Nc6", "Bc4"], date=40),
        game("g5", ["e4", "e5", "Nf3", "Nc6", "Bc4"], date=50),  # Y Closed
        game("g6", MISS, date=60),                                 # X reopened
        game("g7", ["e4", "c5", "Nc3"], date=70),                  # a new gap
    ]
    sync = world.sync()

    result = run(sync)

    assert result.gaps == GapChanges(new=1, closed=1, reopened=1)
    assert sync.status()["result"] == {
        "games_changed": True,
        "repertoire_changed": False,
        "new_games": 4,
        "new_gaps": 1,
        "closed_gaps": 1,
        "reopened_gaps": 1,
    }


def test_without_a_last_analysis_only_the_new_games_are_reported(tmp_path):
    world = World(tmp_path, {(2024, 3): [game("a", MISS), game("b", MISS)]})

    result = run(world.sync())

    assert (result.new_games, result.gaps) == (2, GapChanges())
    assert world.games.reads == 0


def test_a_failed_analysis_leaves_the_gaps_out_of_the_diff(tmp_path):
    world = World(tmp_path, {(2024, 3): [game("a", MISS)]})
    run(world.sync())
    world.analyse()
    world.account.months[(2024, 3)].append(game("b", MISS))
    world.games.error = RuntimeError("Game cache unavailable")
    sync = world.sync()

    result = run(sync)

    assert result.new_games == 1 and result.gaps == GapChanges()
    assert sync.status()["sources"]["chess_com"]["status"] == "ok"


def test_gap_changes_count_new_newly_closed_and_reopened_gaps():
    before = {"a": "open", "b": "open", "c": "closed", "d": "closed"}
    after = {"a": "open", "b": "closed", "c": "open", "d": "closed", "e": "open", "f": "open"}

    assert gap_changes(before, after) == GapChanges(new=2, closed=1, reopened=1)


def test_a_gap_that_disappears_is_not_counted():
    assert gap_changes({"a": "open"}, {}) == GapChanges()
