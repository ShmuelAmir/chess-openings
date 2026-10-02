import pytest

from drill_attempts import DrillAttempt, DrillAttemptStore

GAP = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -"
EARLIER = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -"


def test_no_drill_attempts_at_first(tmp_path):
    assert DrillAttemptStore(tmp_path / "app.db").attempts() == []


def test_a_pass_and_a_fail_are_recorded_oldest_first(tmp_path):
    store = DrillAttemptStore(tmp_path / "app.db")

    store.record(GAP, passed=False, first_miss_position_key=EARLIER, at=200)
    store.record(GAP, passed=True, first_miss_position_key=None, at=100)

    assert store.attempts() == [
        DrillAttempt(GAP, at=100, passed=True, first_miss_position_key=None),
        DrillAttempt(GAP, at=200, passed=False, first_miss_position_key=EARLIER),
    ]


def test_drill_attempts_persist_across_restarts(tmp_path):
    DrillAttemptStore(tmp_path / "app.db").record(GAP, passed=True, first_miss_position_key=None, at=100)

    assert len(DrillAttemptStore(tmp_path / "app.db").attempts()) == 1


def test_a_fail_needs_its_first_miss_and_a_pass_has_none(tmp_path):
    store = DrillAttemptStore(tmp_path / "app.db")

    with pytest.raises(ValueError):
        store.record(GAP, passed=False, first_miss_position_key=None, at=100)
    with pytest.raises(ValueError):
        store.record(GAP, passed=True, first_miss_position_key=EARLIER, at=100)
    assert store.attempts() == []
