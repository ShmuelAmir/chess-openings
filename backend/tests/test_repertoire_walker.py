import chess

from repertoire import RepertoireBuilder
from repertoire_walker import DeviationType, RepertoireWalker

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"
AFTER_E4_E5 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -"
AFTER_E4_E5_NF3_NC6 = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -"


def walk(pgn, color, moves):
    builder = RepertoireBuilder()
    builder.add_study(pgn, "Test")
    return RepertoireWalker(builder.build()).walk_game(color, moves)


ITALIAN = '[Event "Italian"]\n\n1. e4 e5 2. Nf3 (2. Bc4 Nf6) Nc6 3. Bc4 *\n'


def test_player_error():
    record = walk(ITALIAN, chess.WHITE, ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6"])

    assert record.analysed
    assert record.deviation.type == DeviationType.PLAYER_ERROR
    assert record.deviation.position_key == AFTER_E4_E5_NF3_NC6
    assert record.deviation.move_played == "Bb5"
    assert record.deviation.book_moves == ["Bc4"]


def test_several_book_moves_are_all_listed():
    record = walk(ITALIAN, chess.WHITE, ["e4", "e5", "d4"])

    assert record.deviation.type == DeviationType.PLAYER_ERROR
    assert record.deviation.position_key == AFTER_E4_E5
    assert record.deviation.book_moves == ["Nf3", "Bc4"]


def test_opponent_left_book():
    record = walk(ITALIAN, chess.WHITE, ["e4", "e5", "Nf3", "d6", "d4"])

    assert record.analysed
    assert record.deviation.type == DeviationType.OPPONENT_LEFT_BOOK
    assert record.deviation.move_played == "d6"
    assert record.deviation.book_moves == ["Nc6"]


def test_book_completed():
    record = walk(ITALIAN, chess.WHITE, ["e4", "e5", "Nf3", "Nc6", "Bc4"])

    assert record.analysed
    assert record.deviation.type == DeviationType.BOOK_COMPLETED
    assert record.deviation.move_played is None
    assert record.deviation.book_moves == []


def test_game_not_in_the_repertoire():
    record = walk(ITALIAN, chess.WHITE, ["d4", "d5"])

    assert not record.analysed
    assert record.deviation is None
    assert record.reached_in_book == []


def test_empty_game_is_not_analysed():
    assert not walk(ITALIAN, chess.WHITE, []).analysed


SICILIAN = '[Event "Sicilian"]\n\n1. e4 c5 2. Nf3 d6 *\n'


def test_player_error_on_move_one_is_not_this_opening():
    record = walk(SICILIAN, chess.BLACK, ["e4", "e5", "Nf3"])

    assert not record.analysed
    assert record.deviation is None


def test_opponent_leaving_on_move_one_is_still_analysed():
    record = walk(ITALIAN, chess.WHITE, ["e4", "c5"])

    assert record.analysed
    assert record.deviation.type == DeviationType.OPPONENT_LEFT_BOOK


def test_player_error_as_black():
    record = walk(SICILIAN, chess.BLACK, ["e4", "c5", "Nf3", "Nc6"])

    assert record.analysed
    assert record.deviation.type == DeviationType.PLAYER_ERROR
    assert record.deviation.move_played == "Nc6"
    assert record.deviation.book_moves == ["d6"]
    assert record.deviation.position_key == (
        "rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq -"
    )


def test_reached_in_book_lists_the_users_moves_in_order():
    record = walk(ITALIAN, chess.WHITE, ["e4", "e5", "Nf3", "Nc6", "Bb5"])

    assert record.reached_in_book == [(START, "e4"), (AFTER_E4_E5, "Nf3")]


def test_reached_in_book_as_black():
    record = walk(SICILIAN, chess.BLACK, ["e4", "c5", "Nf3", "d6", "d4"])

    assert [move for _, move in record.reached_in_book] == ["c5", "d6"]
    assert record.reached_in_book[0].position_key == (
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -"
    )


def test_position_key_drops_move_counters_but_keeps_en_passant():
    pgn = '[Event "French"]\n\n1. e4 e6 2. e5 d5 3. d4 *\n'
    record = walk(pgn, chess.WHITE, ["e4", "e6", "e5", "d5", "exd6"])

    assert record.deviation.position_key == (
        "rnbqkbnr/ppp2ppp/4p3/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6"
    )


def test_transpositions_are_not_recognised():
    record = walk(ITALIAN, chess.WHITE, ["Nf3", "Nc6", "e4", "e5"])

    assert not record.analysed
