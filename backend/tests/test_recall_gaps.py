import chess

from recall_gaps import RecallFilters, Totals, WalkedGame, aggregate
from repertoire import RepertoireBuilder, side_to_move
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
        record=RepertoireWalker(rep).walk_game(color, moves),
    )


def recall(games, filters=RecallFilters(), rep=REPERTOIRE):
    def studies_of(key):
        return rep.study_locations(key, side_to_move(key))

    return aggregate(games, filters, studies_of)


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
