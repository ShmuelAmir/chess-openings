from dataclasses import replace
from datetime import datetime, timezone

import chess

from recall_gaps import RecallFilters, Totals, WalkedGame, aggregate
from repertoire import RepertoireBuilder
from repertoire_walker import RepertoireWalker

AFTER_E4_E5 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -"
AFTER_E4_E5_NF3_NC6 = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -"
AFTER_E4_C5_NF3 = "rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq -"

ITALIAN = '[Event "Italian"]\n\n1. e4 e5 2. Nf3 (2. Bc4 Nf6) Nc6 3. Bc4 *\n'
SPANISH = '[Event "Spanish"]\n\n1. e4 e5 2. Nf3 Nc6 3. Bb5 *\n'
SICILIAN = '[Event "Sicilian"]\n[Orientation "black"]\n\n1. e4 c5 2. Nf3 d6 *\n'

DAY = 24 * 60 * 60


def repertoire(*studies):
    builder = RepertoireBuilder()
    for study_id, pgn in studies:
        builder.add_study(pgn, study_id, study_id=study_id)
    return builder.build()


REPERTOIRE = repertoire(("italian", ITALIAN), ("sicilian", SICILIAN))


def game(moves, day, color=chess.WHITE, rep=REPERTOIRE, time_class="blitz", rated=True, result="win"):
    return WalkedGame(
        url=f"https://chess.com/game/{day}-{'-'.join(moves)}",
        date=day * DAY,
        time_class=time_class,
        rated=rated,
        result=result,
        moves=moves,
        color=color,
        record=RepertoireWalker(rep).walk_game(color, moves),
    )


def recall(games, filters=RecallFilters(), rep=REPERTOIRE):
    return aggregate(games, filters, rep.study_locations)


def test_player_errors_at_the_same_position_are_one_gap():
    view = recall([
        game(["e4", "e5", "Nf3", "Nc6", "Bb5"], day=1),
        game(["e4", "e5", "Nf3", "Nc6", "Bb5"], day=2),
    ])

    assert len(view.gaps) == 1
    gap = view.gaps[0]
    assert gap.position_key == AFTER_E4_E5_NF3_NC6
    assert gap.occurrences == 2
    assert gap.book_moves == ["Bc4"]
    assert gap.color == "white"


def test_each_wrong_move_is_counted_most_frequent_first():
    view = recall([
        game(["e4", "e5", "Nf3", "Nc6", "d4"], day=1),
        game(["e4", "e5", "Nf3", "Nc6", "Bb5"], day=2),
        game(["e4", "e5", "Nf3", "Nc6", "Bb5"], day=3),
    ])

    assert [(m.san, m.count) for m in view.gaps[0].wrong_moves] == [("Bb5", 2), ("d4", 1)]


def test_opponent_leaving_book_and_book_completed_never_create_gaps():
    view = recall([
        game(["e4", "e5", "Nf3", "d6", "d4"], day=1),
        game(["e4", "e5", "Nf3", "Nc6", "Bc4"], day=2),
    ])

    assert view.gaps == []
    assert view.totals == Totals(analysed=2, opponent_left_book=1, book_completed=1)


def test_games_outside_the_repertoire_are_not_counted():
    view = recall([game(["d4", "d5"], day=1), game(["e4", "e5", "d4"], day=2)])

    assert view.totals == Totals(analysed=1, opponent_left_book=0, book_completed=0)


def test_gaps_rank_by_occurrences_then_most_recent_occurrence():
    italian_bb5 = ["e4", "e5", "Nf3", "Nc6", "Bb5"]
    italian_d4 = ["e4", "e5", "d4"]
    sicilian_nc6 = ["e4", "c5", "Nf3", "Nc6"]
    view = recall([
        game(italian_d4, day=9),
        game(italian_bb5, day=1),
        game(italian_bb5, day=2),
        game(sicilian_nc6, day=5, color=chess.BLACK),
    ])

    assert [g.position_key for g in view.gaps] == [
        AFTER_E4_E5_NF3_NC6,  # 2 occurrences
        AFTER_E4_E5,  # 1 occurrence, day 9
        AFTER_E4_C5_NF3,  # 1 occurrence, day 5
    ]


def test_gap_records_the_line_and_date_of_its_most_recent_occurrence():
    view = recall([
        game(["e4", "c5", "Nf3", "Nc6", "d4"], day=3, color=chess.BLACK),
        game(["e4", "c5", "Nf3", "e6"], day=7, color=chess.BLACK),
    ])

    gap = view.gaps[0]
    assert gap.path == ["e4", "c5", "Nf3"]
    assert gap.last_seen == 7 * DAY
    assert gap.color == "black"
    assert [g.move_played for g in gap.games] == ["e6", "Nc6"]


def test_gap_drill_turns_are_the_users_turns_of_its_most_recent_line():
    after_e4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -"
    view = recall([
        game(["e4", "c5", "Nf3", "e6"], day=7, color=chess.BLACK),
    ])

    assert [(t.ply, t.position_key, t.book_moves) for t in view.gaps[0].drill_turns] == [
        (1, after_e4, ["c5"]),
        (3, AFTER_E4_C5_NF3, ["d6"]),  # the gap itself
    ]


def test_gap_drill_turn_at_the_gap_accepts_every_book_move_there():
    rep = repertoire(("italian", ITALIAN), ("spanish", SPANISH))
    view = recall([game(["e4", "e5", "Nf3", "Nc6", "d4"], day=1, rep=rep)], rep=rep)

    turns = view.gaps[0].drill_turns
    assert [t.ply for t in turns] == [0, 2, 4]
    assert turns[-1].position_key == AFTER_E4_E5_NF3_NC6
    assert turns[-1].book_moves == ["Bc4", "Bb5"]


def test_gap_belongs_to_every_study_containing_its_position():
    rep = repertoire(("italian", ITALIAN), ("spanish", SPANISH))
    view = recall([game(["e4", "e5", "Nf3", "Nc6", "d4"], day=1, rep=rep)], rep=rep)

    gap = view.gaps[0]
    assert [s.id for s in gap.studies] == ["italian", "spanish"]
    assert gap.book_moves == ["Bc4", "Bb5"]


def test_book_moves_are_merged_across_paths_to_the_same_position():
    rep = repertoire(
        ("a", '[Event "A"]\n\n1. e4 e5 2. Nf3 Nc6 3. Bc4 *\n'),
        ("b", '[Event "B"]\n\n1. Nf3 Nc6 2. e4 e5 3. Bb5 *\n'),
    )
    view = recall([
        game(["e4", "e5", "Nf3", "Nc6", "d4"], day=1, rep=rep),
        game(["Nf3", "Nc6", "e4", "e5", "d4"], day=2, rep=rep),
    ], rep=rep)

    assert len(view.gaps) == 1
    assert sorted(view.gaps[0].book_moves) == ["Bb5", "Bc4"]


def test_filters_decide_which_games_count():
    bb5 = ["e4", "e5", "Nf3", "Nc6", "Bb5"]
    view = recall(
        [
            game(bb5, day=10),
            game(bb5, day=11, time_class="bullet"),
            game(bb5, day=12, rated=False),
            game(bb5, day=1),
            game(["e4", "e5", "d4"], day=2),
        ],
        RecallFilters(time_classes=["blitz", "rapid"], rated_only=True, since=5 * DAY),
    )

    assert len(view.gaps) == 1
    assert view.gaps[0].occurrences == 1
    assert view.gaps[0].last_seen == 10 * DAY
    assert view.totals.analysed == 1


def test_one_off_gaps_are_kept():
    view = recall([game(["e4", "e5", "d4"], day=1)])

    assert len(view.gaps) == 1
    assert view.gaps[0].occurrences == 1


def test_gap_games_show_what_was_played_and_the_users_result():
    bb5 = ["e4", "e5", "Nf3", "Nc6", "Bb5"]
    view = recall([
        game(bb5, day=1, time_class="rapid", result="loss"),
        game(["e4", "e5", "Nf3", "Nc6", "d4"], day=2, result="draw"),
    ])

    assert [
        (g.date, g.time_class, g.move_played, g.result) for g in view.gaps[0].games
    ] == [(2 * DAY, "blitz", "d4", "draw"), (1 * DAY, "rapid", "Bb5", "loss")]


def test_gap_studies_locate_the_position_in_their_chapters():
    rep = repertoire((
        "italian",
        '[Event "Italian"]\n[ChapterURL "https://lichess.org/study/italian/ch1"]\n\n'
        "1. e4 e5 2. Nf3 (2. Bc4 Nf6 3. d3) Nc6 3. Bc4 *\n",
    ))
    view = recall([
        game(["e4", "e5", "Nf3", "Nc6", "d4"], day=2, rep=rep),
        game(["e4", "e5", "Bc4", "Nf6", "Nc3"], day=1, rep=rep),
    ], rep=rep)

    on_mainline, off_mainline = view.gaps
    assert [(s.id, s.chapter_id, s.mainline_ply) for s in on_mainline.studies] == [("italian", "ch1", 4)]
    assert [(s.id, s.chapter_id, s.mainline_ply) for s in off_mainline.studies] == [("italian", "ch1", None)]


TWO_KNIGHTS = '[Event "Two Knights"]\n\n1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. Ng5 *\n'
STUDY_REPERTOIRE = repertoire(
    ("italian", ITALIAN), ("spanish", SPANISH), ("two-knights", TWO_KNIGHTS), ("sicilian", SICILIAN)
)


def study_game(moves, day, color=chess.WHITE):
    return game(moves, day, color=color, rep=STUDY_REPERTOIRE)


SHARED_GAP = ["e4", "e5", "Nf3", "Nc6", "d4"]  # Italian, Spanish and Two Knights
ITALIAN_ONLY_GAP = ["e4", "e5", "Bc4", "Nf6", "Nc3"]
TWO_KNIGHTS_GAP = ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "d3"]
SICILIAN_GAP = ["e4", "c5", "Nf3", "Nc6"]


def study_recall(games, studies=None):
    return recall(games, RecallFilters(studies=studies), rep=STUDY_REPERTOIRE)


def test_no_study_selected_shows_every_gap():
    games = [study_game(SHARED_GAP, 1), study_game(SICILIAN_GAP, 2, color=chess.BLACK)]

    assert len(study_recall(games).gaps) == 2
    assert len(study_recall(games, studies=frozenset()).gaps) == 2


def test_a_gap_shows_when_any_selected_study_contains_its_position():
    games = [
        study_game(SHARED_GAP, 1),
        study_game(ITALIAN_ONLY_GAP, 2),
        study_game(TWO_KNIGHTS_GAP, 3),
        study_game(SICILIAN_GAP, 4, color=chess.BLACK),
    ]

    def shown(*studies):
        return {tuple(g.path) for g in study_recall(games, frozenset(studies)).gaps}

    assert shown("spanish") == {tuple(SHARED_GAP[:-1])}
    assert shown("italian") == {tuple(SHARED_GAP[:-1]), tuple(ITALIAN_ONLY_GAP[:-1])}
    assert shown("two-knights", "sicilian") == {
        tuple(SHARED_GAP[:-1]), tuple(TWO_KNIGHTS_GAP[:-1]), tuple(SICILIAN_GAP[:-1])
    }


def test_the_study_filter_never_changes_a_gaps_occurrences():
    games = [study_game(SHARED_GAP, 1), study_game(SHARED_GAP, 2)]

    unfiltered = study_recall(games).gaps
    filtered = study_recall(games, frozenset({"spanish"})).gaps

    assert [(g.occurrences, g.last_seen, [s.id for s in g.studies]) for g in filtered] == [
        (g.occurrences, g.last_seen, [s.id for s in g.studies]) for g in unfiltered
    ]
    assert [s.id for s in filtered[0].studies] == ["italian", "spanish", "two-knights"]


def test_totals_under_a_study_filter_count_games_that_left_book_in_a_selected_study():
    games = [
        study_game(SHARED_GAP, 1),  # player error, shared position
        study_game(ITALIAN_ONLY_GAP, 2),  # player error, Italian only
        study_game(["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5"], 3),  # Two Knights completed
        study_game(["e4", "e5", "Nf3", "Nc6", "Bb5"], 4),  # Spanish completed
        study_game(["e4", "e5", "Nf3", "d6"], 5),  # opponent left book, shared position
        study_game(SICILIAN_GAP, 6, color=chess.BLACK),
    ]

    assert study_recall(games, frozenset({"spanish"})).totals == Totals(
        analysed=3, opponent_left_book=1, book_completed=1
    )
    # Passing through the Italian on the way into the Two Knights doesn't count
    assert study_recall(games, frozenset({"italian"})).totals == Totals(
        analysed=3, opponent_left_book=1, book_completed=0
    )
    assert study_recall(games, frozenset({"sicilian"})).totals == Totals(
        analysed=1, opponent_left_book=0, book_completed=0
    )


def test_each_study_counts_the_gaps_it_contains_whatever_studies_are_selected():
    games = [
        study_game(SHARED_GAP, 1),
        study_game(SHARED_GAP, 2),
        study_game(ITALIAN_ONLY_GAP, 3),
        study_game(SICILIAN_GAP, 4, color=chess.BLACK),
    ]

    expected = {"italian": 2, "spanish": 1, "two-knights": 1, "sicilian": 1}
    assert study_recall(games).gaps_by_study == expected
    assert study_recall(games, frozenset({"sicilian"})).gaps_by_study == expected


def test_study_gap_counts_follow_the_other_filters():
    games = [study_game(SHARED_GAP, 1), study_game(ITALIAN_ONLY_GAP, 10)]

    view = recall(games, RecallFilters(since=5 * DAY), rep=STUDY_REPERTOIRE)

    assert view.gaps_by_study == {"italian": 1}


BB5_MISS = ["e4", "e5", "Nf3", "Nc6", "Bb5"]
IN_BOOK = ["e4", "e5", "Nf3", "Nc6", "Bc4"]  # the user plays the book move at the gap


def test_a_gap_is_open_with_no_progress_after_its_occurrence():
    gap = recall([game(BB5_MISS, day=1)]).gaps[0]

    assert (gap.status, gap.progress, gap.closed_at) == ("open", 0, None)


def test_a_gap_shows_its_progress_toward_closing():
    gap = recall([game(BB5_MISS, day=1), game(IN_BOOK, day=2)]).gaps[0]

    assert (gap.status, gap.progress, gap.closed_at) == ("open", 1, None)


def test_a_gap_closes_after_two_in_book_games_since_its_last_occurrence():
    gap = recall([
        game(BB5_MISS, day=1),
        game(IN_BOOK, day=2),
        game(IN_BOOK, day=5),
        game(IN_BOOK, day=9),
    ]).gaps[0]

    assert (gap.status, gap.progress, gap.closed_at) == ("closed", 2, 5 * DAY)


def test_in_book_games_before_the_last_occurrence_do_not_count():
    gap = recall([
        game(IN_BOOK, day=1),
        game(IN_BOOK, day=2),
        game(BB5_MISS, day=3),
    ]).gaps[0]

    assert (gap.status, gap.progress) == ("open", 0)


def test_games_that_leave_book_before_the_position_do_not_count():
    gaps = {
        g.position_key: g
        for g in recall([
            game(BB5_MISS, day=1),
            game(["e4", "e5", "Nf3", "d6"], day=2),  # opponent left book first
            game(["e4", "e5", "d4"], day=3),  # another gap, earlier in the line
        ]).gaps
    }
    assert gaps[AFTER_E4_E5_NF3_NC6].progress == 0


def test_a_new_occurrence_reopens_a_closed_gap_and_restarts_the_count():
    gap = recall([
        game(BB5_MISS, day=1),
        game(IN_BOOK, day=2),
        game(IN_BOOK, day=3),
        game(["e4", "e5", "Nf3", "Nc6", "d4"], day=4),
        game(IN_BOOK, day=5),
    ]).gaps[0]

    assert (gap.status, gap.progress, gap.closed_at) == ("open", 1, None)


def test_status_ignores_the_game_filters():
    games = [
        game(BB5_MISS, day=1),
        game(IN_BOOK, day=2, time_class="bullet"),
        game(IN_BOOK, day=3, rated=False),
    ]

    unfiltered = recall(games).gaps[0]
    filtered = recall(games, RecallFilters(time_classes=["blitz"], rated_only=True)).gaps[0]

    assert (filtered.status, filtered.closed_at) == (unfiltered.status, unfiltered.closed_at) == (
        "closed", 3 * DAY
    )


def test_a_new_occurrence_outside_the_filters_still_reopens_a_gap():
    games = [
        game(BB5_MISS, day=1),
        game(IN_BOOK, day=2),
        game(IN_BOOK, day=3),
        game(BB5_MISS, day=4, time_class="bullet"),
    ]

    gap = recall(games, RecallFilters(time_classes=["blitz"])).gaps[0]

    assert (gap.status, gap.progress) == ("open", 0)



def utc(year, month, day=1):
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp())


def game_at(moves, date, **kwargs):
    return replace(game(moves, day=0, **kwargs), date=date)


NOW = utc(2026, 10, 15)
OPP_LEFT_BOOK = ["e4", "e5", "Nf3", "d6"]


def test_miss_rate_is_the_share_of_analysed_games_with_a_player_error():
    view = recall([
        game(BB5_MISS, day=1),
        game(["e4", "e5", "d4"], day=2),  # a second player error
        game(IN_BOOK, day=3),
        game(OPP_LEFT_BOOK, day=4),
        game(["d4", "d5"], day=5),  # not analysed
    ])

    assert view.miss_rate == 0.5


def test_miss_rate_is_none_without_analysed_games():
    assert recall([]).miss_rate is None


def test_miss_rate_follows_every_game_filter():
    games = [
        study_game(SHARED_GAP, 1),
        study_game(ITALIAN_ONLY_GAP, 10),
        study_game(["e4", "e5", "Nf3", "Nc6", "Bb5"], 11),  # Spanish completed
        study_game(SICILIAN_GAP, 12, color=chess.BLACK),
    ]

    assert recall(games, RecallFilters(since=5 * DAY), rep=STUDY_REPERTOIRE).miss_rate == 2 / 3
    assert study_recall(games, frozenset({"spanish"})).miss_rate == 0.5
    assert recall(
        games, RecallFilters(since=5 * DAY, studies=frozenset({"italian"})), rep=STUDY_REPERTOIRE
    ).miss_rate == 1.0


def test_trend_has_the_last_twelve_months_oldest_first():
    view = aggregate([], RecallFilters(), REPERTOIRE.study_locations, now=NOW)

    assert [m.month for m in view.trend] == [
        "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04",
        "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10",
    ]


def test_trend_buckets_the_miss_rate_by_month():
    games = [game_at(BB5_MISS, utc(2026, 9, 3))] + [
        game_at(IN_BOOK, utc(2026, 9, d)) for d in (4, 5, 6, 30)
    ] + [game_at(BB5_MISS, utc(2026, 10, d)) for d in range(1, 6)]

    trend = {m.month: m for m in aggregate(games, RecallFilters(), REPERTOIRE.study_locations, now=NOW).trend}

    assert (trend["2026-09"].games, trend["2026-09"].miss_rate) == (5, 0.2)
    assert (trend["2026-10"].games, trend["2026-10"].miss_rate) == (5, 1.0)


def test_trend_months_with_fewer_than_five_games_are_empty():
    games = [game_at(BB5_MISS, utc(2026, 8, d)) for d in range(1, 5)]

    trend = {m.month: m for m in aggregate(games, RecallFilters(), REPERTOIRE.study_locations, now=NOW).trend}

    assert (trend["2026-08"].games, trend["2026-08"].miss_rate) == (4, None)
    assert (trend["2026-07"].games, trend["2026-07"].miss_rate) == (0, None)


def test_trend_ignores_the_date_range_but_follows_the_other_filters():
    games = [game_at(BB5_MISS, utc(2026, 3, d)) for d in range(1, 6)] + [
        game_at(IN_BOOK, utc(2026, 3, d), time_class="bullet") for d in range(1, 6)
    ] + [game_at(BB5_MISS, utc(2025, 10, 31))]  # before the 12 months

    filters = RecallFilters(time_classes=["blitz"], since=utc(2026, 10, 1))
    view = aggregate(games, filters, REPERTOIRE.study_locations, now=NOW)

    assert {m.month: (m.games, m.miss_rate) for m in view.trend if m.games} == {"2026-03": (5, 1.0)}
    assert view.miss_rate is None


def test_trend_follows_the_study_filter():
    games = [game_at(SICILIAN_GAP, utc(2026, 5, d), color=chess.BLACK, rep=STUDY_REPERTOIRE) for d in range(1, 6)]
    games += [game_at(ITALIAN_ONLY_GAP, utc(2026, 5, d), rep=STUDY_REPERTOIRE) for d in range(1, 6)]

    view = aggregate(games, RecallFilters(studies=frozenset({"sicilian"})), STUDY_REPERTOIRE.study_locations, now=NOW)

    assert [(m.games, m.miss_rate) for m in view.trend if m.games] == [(5, 1.0)]


def test_trend_is_empty_without_now():
    assert recall([game(BB5_MISS, day=1)]).trend == []


def test_open_gaps_count_the_open_gaps_shown():
    view = recall([
        game(BB5_MISS, day=1),
        game(IN_BOOK, day=2),
        game(IN_BOOK, day=3),  # closes the Bb5 gap
        game(["e4", "e5", "d4"], day=4),
        game(SICILIAN_GAP, day=5, color=chess.BLACK),
    ])

    assert view.open_gaps == 2


def test_closed_in_range_counts_gaps_by_their_closing_date():
    games = [
        game(BB5_MISS, day=1),  # occurs before the range, closes inside it
        game(IN_BOOK, day=6),
        game(IN_BOOK, day=7),
        game(["e4", "e5", "d4"], day=1),  # closed before the range
        game(["e4", "e5", "Nf3"], day=2),
        game(["e4", "e5", "Nf3"], day=3),
    ]

    assert recall(games, RecallFilters(since=5 * DAY)).closed_in_range == 1
    assert recall(games).closed_in_range == 2


def test_closed_in_range_follows_the_other_filters():
    games = [
        game(BB5_MISS, day=1, time_class="bullet"),
        game(IN_BOOK, day=6),
        game(IN_BOOK, day=7),
    ]

    assert recall(games, RecallFilters(since=5 * DAY)).closed_in_range == 1
    assert recall(games, RecallFilters(since=5 * DAY, time_classes=["blitz"])).closed_in_range == 0
