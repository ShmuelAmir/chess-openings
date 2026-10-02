from drill_attempts import DrillAttempt
from drill_scheduler import practice_queue, schedule
from recall_gaps import RecallGap

GAP = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -"
EARLIER = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -"

DAY = 24 * 60 * 60
HOUR = 60 * 60
OCCURRED = 10 * DAY  # the gap's latest real-game occurrence


def passed(at):
    return DrillAttempt(GAP, at=at, passed=True, first_miss_position_key=None)


def failed(at):
    return DrillAttempt(GAP, at=at, passed=False, first_miss_position_key=EARLIER)


def test_a_gap_with_no_attempts_is_due():
    result = schedule({GAP: OCCURRED}, [], now=OCCURRED + DAY)

    assert result.due == [GAP]
    assert result.next_due[GAP] <= OCCURRED + DAY


def test_a_pass_holds_the_gap_back_one_day():
    drilled = OCCURRED + HOUR

    result = schedule({GAP: OCCURRED}, [passed(drilled)], now=drilled + HOUR)

    assert result.due == []
    assert result.next_due[GAP] == drilled + DAY
    assert schedule({GAP: OCCURRED}, [passed(drilled)], now=drilled + DAY).due == [GAP]


def test_successive_passes_hold_the_gap_back_1_then_3_then_7_days_and_stay_at_7():
    attempts = []
    at = OCCURRED + HOUR
    holds = []
    for _ in range(5):
        attempts.append(passed(at))
        due_at = schedule({GAP: OCCURRED}, attempts, now=at).next_due[GAP]
        holds.append((due_at - at) // DAY)
        at = due_at

    assert holds == [1, 3, 7, 7, 7]


def test_a_fail_resets_the_interval():
    at = OCCURRED + HOUR
    attempts = [passed(at), passed(at + DAY), passed(at + 4 * DAY), failed(at + 11 * DAY)]

    after_fail = schedule({GAP: OCCURRED}, attempts, now=at + 11 * DAY)
    assert after_fail.due == [GAP]

    attempts.append(passed(at + 12 * DAY))
    assert schedule({GAP: OCCURRED}, attempts, now=at + 12 * DAY).next_due[GAP] == at + 13 * DAY


def test_an_occurrence_newer_than_the_last_attempt_makes_the_gap_due():
    at = OCCURRED + HOUR
    attempts = [passed(at), passed(at + DAY), passed(at + 4 * DAY)]  # held back to at + 11 days
    occurred_again = at + 5 * DAY

    result = schedule({GAP: occurred_again}, attempts, now=occurred_again + HOUR)

    assert result.due == [GAP]
    assert result.next_due[GAP] == occurred_again


def test_passes_before_a_new_occurrence_do_not_count():
    at = OCCURRED + HOUR
    occurred_again = at + 5 * DAY
    attempts = [passed(at), passed(at + DAY), passed(at + 4 * DAY), passed(occurred_again + HOUR)]

    result = schedule({GAP: occurred_again}, attempts, now=occurred_again + HOUR)

    assert result.next_due[GAP] == occurred_again + HOUR + DAY


OTHER = "rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq -"
THIRD = "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq -"


def gap(key, status="open", last_occurrence=OCCURRED):
    return RecallGap(
        position_key=key, color="white", path=[], wrong_moves=[], book_moves=[],
        studies=[], occurrences=1, last_seen=last_occurrence, games=[],
        status=status, last_occurrence=last_occurrence,
    )


def test_a_session_keeps_the_ranking_order_of_the_due_gaps():
    ranked = [gap(OTHER), gap(GAP), gap(THIRD)]
    drilled = DrillAttempt(GAP, at=OCCURRED + HOUR, passed=True, first_miss_position_key=None)

    queue = practice_queue(ranked, [drilled], now=OCCURRED + 2 * HOUR)

    assert [(q.gap.position_key, q.due_at) for q in queue] == [(OTHER, OCCURRED), (THIRD, OCCURRED)]


def test_closed_gaps_are_left_out_of_sessions():
    queue = practice_queue([gap(GAP, status="closed"), gap(OTHER)], [], now=OCCURRED + DAY)

    assert [q.gap.position_key for q in queue] == [OTHER]
