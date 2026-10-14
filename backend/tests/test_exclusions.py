import sqlite3

from exclusions import ExclusionStore


def test_nothing_is_excluded_at_first(tmp_path):
    store = ExclusionStore("me", tmp_path / "app.db")

    assert store.excluded_studies() == set()


def test_the_exclusion_list_persists_across_restarts(tmp_path):
    ExclusionStore("me", tmp_path / "app.db").set_excluded_studies({"scratch", "puzzles"})

    assert ExclusionStore("me", tmp_path / "app.db").excluded_studies() == {"scratch", "puzzles"}


def test_setting_the_list_replaces_it(tmp_path):
    store = ExclusionStore("me", tmp_path / "app.db")
    store.set_excluded_studies({"scratch", "puzzles"})

    store.set_excluded_studies({"puzzles"})

    assert store.excluded_studies() == {"puzzles"}


def test_each_account_has_its_own_list(tmp_path):
    mine = ExclusionStore("me", tmp_path / "app.db")
    theirs = ExclusionStore("them", tmp_path / "app.db")
    mine.set_excluded_studies({"scratch"})

    theirs.set_excluded_studies({"puzzles"})

    assert mine.excluded_studies() == {"scratch"}
    assert theirs.excluded_studies() == {"puzzles"}


def test_the_list_stored_before_accounts_belongs_to_the_first_account_to_open_it(tmp_path):
    with sqlite3.connect(tmp_path / "app.db") as conn:
        conn.execute("CREATE TABLE not_repertoire_studies (study_id TEXT PRIMARY KEY)")
        conn.executemany("INSERT INTO not_repertoire_studies VALUES (?)", [("scratch",), ("puzzles",)])

    first = ExclusionStore("me", tmp_path / "app.db")
    later = ExclusionStore("them", tmp_path / "app.db")

    assert first.excluded_studies() == {"scratch", "puzzles"}
    assert later.excluded_studies() == set()
    assert ExclusionStore("me", tmp_path / "app.db").excluded_studies() == {"scratch", "puzzles"}
