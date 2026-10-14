import sqlite3

import pytest

from drill_attempts import DrillAttempt, DrillAttemptStore

GAP = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -"
EARLIER = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -"


def test_no_drill_attempts_at_first(tmp_path):
    assert DrillAttemptStore("me", tmp_path / "app.db").attempts() == []


def test_a_pass_and_a_fail_are_recorded_oldest_first(tmp_path):
    store = DrillAttemptStore("me", tmp_path / "app.db")

    store.record(GAP, passed=False, first_miss_position_key=EARLIER, at=200)
    store.record(GAP, passed=True, first_miss_position_key=None, at=100)

    assert store.attempts() == [
        DrillAttempt(GAP, at=100, passed=True, first_miss_position_key=None),
        DrillAttempt(GAP, at=200, passed=False, first_miss_position_key=EARLIER),
    ]


def test_drill_attempts_persist_across_restarts(tmp_path):
    DrillAttemptStore("me", tmp_path / "app.db").record(GAP, passed=True, first_miss_position_key=None, at=100)

    assert len(DrillAttemptStore("me", tmp_path / "app.db").attempts()) == 1


def test_a_fail_needs_its_first_miss_and_a_pass_has_none(tmp_path):
    store = DrillAttemptStore("me", tmp_path / "app.db")

    with pytest.raises(ValueError):
        store.record(GAP, passed=False, first_miss_position_key=None, at=100)
    with pytest.raises(ValueError):
        store.record(GAP, passed=True, first_miss_position_key=EARLIER, at=100)
    assert store.attempts() == []


def test_each_account_has_its_own_drill_attempts(tmp_path):
    mine = DrillAttemptStore("me", tmp_path / "app.db")
    theirs = DrillAttemptStore("them", tmp_path / "app.db")

    mine.record(GAP, passed=True, first_miss_position_key=None, at=100)

    assert len(mine.attempts()) == 1
    assert theirs.attempts() == []


def test_drill_attempts_stored_before_accounts_belong_to_the_first_account_to_open_them(tmp_path):
    with sqlite3.connect(tmp_path / "app.db") as conn:
        conn.execute("""
            CREATE TABLE drill_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gap_position_key TEXT NOT NULL,
                at INTEGER NOT NULL,
                passed INTEGER NOT NULL,
                first_miss_position_key TEXT
            )
        """)
        conn.execute("INSERT INTO drill_attempts (gap_position_key, at, passed) VALUES (?, 100, 1)", (GAP,))

    first = DrillAttemptStore("me", tmp_path / "app.db")
    later = DrillAttemptStore("them", tmp_path / "app.db")

    assert first.attempts() == [DrillAttempt(GAP, at=100, passed=True, first_miss_position_key=None)]
    assert later.attempts() == []
    assert len(DrillAttemptStore("me", tmp_path / "app.db").attempts()) == 1
