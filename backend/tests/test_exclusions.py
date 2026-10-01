from exclusions import ExclusionStore


def test_nothing_is_excluded_at_first(tmp_path):
    store = ExclusionStore(tmp_path / "app.db")

    assert store.excluded_studies() == set()


def test_the_exclusion_list_persists_across_restarts(tmp_path):
    ExclusionStore(tmp_path / "app.db").set_excluded_studies({"scratch", "puzzles"})

    assert ExclusionStore(tmp_path / "app.db").excluded_studies() == {"scratch", "puzzles"}


def test_setting_the_list_replaces_it(tmp_path):
    store = ExclusionStore(tmp_path / "app.db")
    store.set_excluded_studies({"scratch", "puzzles"})

    store.set_excluded_studies({"puzzles"})

    assert store.excluded_studies() == {"puzzles"}
