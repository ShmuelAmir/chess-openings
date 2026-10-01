"""The analyse endpoint's per-game results, pinned so the walker can change underneath."""
from analyzer import DeviationAnalyzer
from repertoire import RepertoireBuilder

WHITE_PGN = '[Event "Italian"]\n\n1. e4 e5 2. Nf3 (2. Bc4 Nf6) Nc6 3. Bc4 *\n'


def analyze(moves, white="me", black="opp"):
    builder = RepertoireBuilder()
    builder.add_study(WHITE_PGN, "Italian", study_id="s1")
    analyzer = DeviationAnalyzer(builder.build())
    game = {"moves": moves, "white": white, "black": black, "url": "u", "date": 0}
    return analyzer.analyze_game(game, "me")


def test_player_error_row():
    result = analyze(["e4", "e5", "Nf3", "Nc6", "Bb5"])
    assert result["result_type"] == "deviation"
    assert result["move_number"] == 3
    assert result["your_move"] == "Bb5"
    assert result["correct_move"] == "Bc4"
    assert result["variation_count"] == 1
    assert result["fen"] == "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
    assert result["study_id"] == "s1"
    assert result["user_color"] == "white"


def test_several_book_moves_are_listed():
    result = analyze(["e4", "e5", "d4"])
    assert result["correct_move"] == "Nf3, Bc4"
    assert result["variation_count"] == 2


def test_opponent_left_book_row():
    result = analyze(["e4", "e5", "Nf3", "d6"])
    assert result["result_type"] == "opponent_left_book"
    assert result["move_number"] == 2
    assert result["opponent_move"] == "d6"
    assert result["correct_move"] == "Nc6"


def test_book_completed_row():
    result = analyze(["e4", "e5", "Nf3", "Nc6", "Bc4"])
    assert result["result_type"] == "book_completed"
    assert result["move_number"] == 2
    assert result["correct_move"] == "All book moves correct"


def test_games_outside_the_opening_are_skipped():
    assert analyze(["d4", "d5"]) is None
    assert analyze(["e4", "c5"]) is None  # opponent leaves on move 1
    assert analyze(["e4", "c5"], white="opp", black="me") is None  # player error on move 1
    assert analyze([]) is None
