import asyncio
from datetime import datetime

from game_cache import GameCache
from sync import ChessComSync, GamesSyncResult, Sync

ARCHIVES = "https://api.chess.com/pub/player/magnus/games/{}/{:02d}"


def chess_com_game(url):
    return {"url": url, "date": 1, "white": "magnus", "black": "hikaru", "moves": ["e4"]}


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
        return [chess_com_game(url) for url in self.months[(year, month)]]


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


class Sources:
    """Stand-ins for the two sources and the re-analysis hook of a Sync."""

    def __init__(self, new_games=0, failed_months=(), repertoire_changed=False):
        self.games = GamesSyncResult(new_games=new_games, failed_months=list(failed_months))
        self.repertoire_changed = repertoire_changed
        self.games_error = None
        self.repertoire_error = None
        self.games_last_success = None
        self.games_invalidated = 0

    def sync(self):
        return Sync(
            sync_games=self.sync_games,
            refresh_repertoire=self.refresh_repertoire,
            games_last_success=lambda: self.games_last_success,
            on_games_changed=self.invalidate_games,
            clock=lambda: 1000,
        )

    async def sync_games(self, on_month):
        on_month(2023, 4)
        if self.games_error:
            raise self.games_error
        if not self.games.failed_months:
            self.games_last_success = 900
        return self.games

    async def refresh_repertoire(self):
        if self.repertoire_error:
            raise self.repertoire_error
        return self.repertoire_changed

    def invalidate_games(self):
        self.games_invalidated += 1


def run(sync):
    return asyncio.run(sync.run())


def test_a_sync_reports_new_games_and_reanalyses():
    sources = Sources(new_games=3)
    sync = sources.sync()

    result = run(sync)

    assert (result.games_changed, result.repertoire_changed, result.new_games) == (True, False, 3)
    assert sources.games_invalidated == 1


def test_a_sync_that_changed_nothing_does_not_reanalyse():
    sources = Sources()
    sync = sources.sync()

    result = run(sync)

    assert (result.games_changed, result.repertoire_changed) == (False, False)
    assert sources.games_invalidated == 0


def test_a_repertoire_change_is_reported():
    sources = Sources(repertoire_changed=True)

    assert run(sources.sync()).repertoire_changed


def test_each_source_records_its_own_last_success():
    sources = Sources()
    sync = sources.sync()

    run(sync)

    status = sync.status()
    assert status["sources"]["chess_com"] == {"status": "ok", "last_success_at": 900, "error": None}
    assert status["sources"]["lichess"] == {"status": "ok", "last_success_at": 1000, "error": None}


def test_last_synced_is_the_older_of_the_two_sources():
    sources = Sources()
    sync = sources.sync()

    assert sync.status()["last_synced_at"] is None
    run(sync)
    assert sync.status()["last_synced_at"] == 900


def test_a_failed_lichess_refresh_keeps_the_new_games():
    sources = Sources(new_games=2)
    sources.repertoire_error = RuntimeError("Lichess is down")
    sync = sources.sync()

    result = run(sync)

    assert result.games_changed and sources.games_invalidated == 1
    assert sync.status()["sources"]["lichess"]["status"] == "failed"
    assert sync.status()["sources"]["chess_com"]["status"] == "ok"


def test_a_failed_chess_com_sync_keeps_the_repertoire_refresh():
    sources = Sources(repertoire_changed=True)
    sources.games_error = RuntimeError("Chess.com is down")
    sync = sources.sync()

    result = run(sync)

    assert result.repertoire_changed and not result.games_changed
    assert sync.status()["sources"]["chess_com"]["status"] == "failed"
    assert sync.status()["sources"]["lichess"]["status"] == "ok"


def test_failed_months_mark_chess_com_failed_and_name_them():
    sources = Sources(new_games=1, failed_months=[(2023, 4)])
    sync = sources.sync()

    result = run(sync)

    chess_com = sync.status()["sources"]["chess_com"]
    assert result.games_changed
    assert chess_com["status"] == "failed"
    assert "2023-04" in chess_com["error"]


def test_progress_names_the_month_being_fetched():
    sources = Sources()
    sync = sources.sync()
    seen = []

    async def watch(on_month):
        await Sources.sync_games(sources, on_month)
        seen.append(sync.status()["progress"])
        return sources.games

    sync.sync_games = watch
    run(sync)

    assert seen == ["Fetching games… 2023-04"]
    assert sync.status()["progress"] is None
    assert sync.status()["running"] is False
