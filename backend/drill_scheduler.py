"""
Drill scheduler - pure, no I/O. Decides which Recall Gaps are due for a
Drill Attempt, from their Drill Attempts and latest real-game occurrence.
See Drill Attempt in CONTEXT.md.
"""
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from drill_attempts import DrillAttempt
from recall_gaps import RecallGap

DAY = 24 * 60 * 60
# How long successive passes hold a gap back; it stays at the last
INTERVAL_DAYS = (1, 3, 7)


@dataclass(frozen=True)
class Schedule:
    due: list[str] = field(default_factory=list)  # position keys due now, in the given order
    next_due: dict[str, int] = field(default_factory=dict)  # each gap's next due time


@dataclass(frozen=True)
class QueuedGap:
    gap: RecallGap
    due_at: int


def practice_queue(
    gaps: Sequence[RecallGap],
    attempts: Iterable[DrillAttempt],
    now: int,
) -> list[QueuedGap]:
    """
    A practice session's queue: the due Open gaps among `gaps`, in their
    (ranking) order. Closed gaps are left out; they are drilled on demand.
    """
    open_gaps = [gap for gap in gaps if gap.status == "open"]
    result = schedule({gap.position_key: gap.last_occurrence for gap in open_gaps}, attempts, now)
    due = set(result.due)
    return [
        QueuedGap(gap, result.next_due[gap.position_key])
        for gap in open_gaps
        if gap.position_key in due
    ]


def schedule(
    last_occurrences: Mapping[str, int],
    attempts: Iterable[DrillAttempt],
    now: int,
) -> Schedule:
    """
    When each gap is next due, and which are due at `now`.

    Args:
        last_occurrences: Each gap's latest occurrence time by position key;
            its order is the order of `due`
        attempts: Every Drill Attempt (of any gap)
        now: Unix timestamp
    """
    by_gap: dict[str, list[DrillAttempt]] = {}
    for attempt in sorted(attempts, key=lambda a: a.at):
        by_gap.setdefault(attempt.gap_position_key, []).append(attempt)

    next_due = {
        key: _next_due(by_gap.get(key, []), occurred)
        for key, occurred in last_occurrences.items()
    }
    return Schedule(
        due=[key for key, at in next_due.items() if at <= now],
        next_due=next_due,
    )


def _next_due(attempts: list[DrillAttempt], last_occurrence: int) -> int:
    """
    When a gap is next due, from its Drill Attempts (oldest first). Only the
    attempts since its latest occurrence count: a newer occurrence makes it
    due at once and starts the interval again, as a fail does.
    """
    attempts = [a for a in attempts if a.at >= last_occurrence]
    if not attempts:
        return last_occurrence
    passes = 0
    for attempt in reversed(attempts):
        if not attempt.passed:
            break
        passes += 1
    if passes == 0:
        # A fail resets the interval: due again at once
        return attempts[-1].at
    interval = INTERVAL_DAYS[min(passes, len(INTERVAL_DAYS)) - 1]
    return attempts[-1].at + interval * DAY
