import chess

from repertoire import ChapterLocation, RepertoireBuilder, study_url

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"
AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -"
AFTER_E4_C5 = "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -"
AFTER_E4_E5 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -"


def chapter(moves, orientation=None, url=None):
    headers = '[Event "Chapter"]\n'
    if url:
        headers += f'[ChapterURL "{url}"]\n'
    if orientation:
        headers += f'[Orientation "{orientation}"]\n'
    return f"{headers}\n{moves} *\n\n"


def url(chapter_id):
    return f"https://lichess.org/study/italian/{chapter_id}"


def build(*studies):
    builder = RepertoireBuilder()
    for study_id, pgn in studies:
        builder.add_study(pgn, study_id, study_id=study_id)
    return builder.build()


def test_a_black_study_is_absent_from_the_white_tree():
    repertoire = build(("sicilian", chapter("1. e4 c5 2. Nf3", "black")))

    assert list(repertoire.get_tree(chess.BLACK).children) == ["e4"]
    assert repertoire.get_tree(chess.WHITE).children == {}


def test_a_study_takes_the_color_of_its_first_chapter():
    pgn = chapter("1. e4 c5", "black") + chapter("1. d4 Nf6", "white")
    repertoire = build(("mixed", pgn))

    assert list(repertoire.get_tree(chess.BLACK).children) == ["e4", "d4"]
    assert repertoire.get_tree(chess.WHITE).children == {}


def test_a_study_without_orientation_is_white():
    repertoire = build(("italian", chapter("1. e4 e5")))

    assert list(repertoire.get_tree(chess.WHITE).children) == ["e4"]
    assert repertoire.get_tree(chess.BLACK).children == {}


def test_a_position_contained_in_several_studies():
    repertoire = build(
        ("italian", chapter("1. e4 e5 2. Nf3 Nc6 3. Bc4")),
        ("vienna", chapter("1. e4 e5 2. Nc3")),
        ("london", chapter("1. d4 d5 2. Bf4")),
    )

    assert repertoire.studies_containing(AFTER_E4_E5, chess.WHITE) == {"italian", "vienna"}
    assert repertoire.studies_containing(START, chess.WHITE) == {"italian", "vienna", "london"}


def test_a_position_in_a_variation_is_contained_in_the_study():
    repertoire = build(("italian", chapter("1. e4 e5 (1... c5 2. c3) 2. Nf3")))

    assert repertoire.studies_containing(AFTER_E4_C5, chess.WHITE) == {"italian"}


def test_studies_of_the_other_color_do_not_contain_the_position():
    repertoire = build(
        ("italian", chapter("1. e4 e5 2. Nf3")),
        ("sicilian", chapter("1. e4 c5 2. Nf3", "black")),
    )

    assert repertoire.studies_containing(AFTER_E4, chess.BLACK) == {"sicilian"}
    assert repertoire.studies_containing(AFTER_E4, chess.WHITE) == {"italian"}
    assert repertoire.studies_containing(AFTER_E4_C5, chess.WHITE) == set()


def test_a_mainline_position_keeps_its_chapter_and_ply():
    repertoire = build(("italian", chapter("1. e4 e5 2. Nf3", url=url("ch1"))))

    assert repertoire.chapter_location(AFTER_E4_E5, chess.WHITE, "italian") == ChapterLocation("ch1", 2)
    assert repertoire.chapter_location(START, chess.WHITE, "italian") == ChapterLocation("ch1", 0)


def test_a_position_off_the_mainline_keeps_only_its_chapter():
    repertoire = build(("italian", chapter("1. e4 e5 (1... c5 2. c3) 2. Nf3", url=url("ch1"))))

    assert repertoire.chapter_location(AFTER_E4_C5, chess.WHITE, "italian") == ChapterLocation("ch1", None)


def test_a_mainline_chapter_is_preferred_over_a_variation():
    pgn = (
        chapter("1. e4 e5 (1... c5 2. c3) 2. Nf3", url=url("ch1"))
        + chapter("1. e4 c5 2. c3", url=url("ch2"))
    )
    repertoire = build(("italian", pgn))

    assert repertoire.chapter_location(AFTER_E4_C5, chess.WHITE, "italian") == ChapterLocation("ch2", 2)
    assert repertoire.chapter_location(AFTER_E4, chess.WHITE, "italian") == ChapterLocation("ch1", 1)


def test_the_chapter_id_is_read_from_the_site_header_too():
    pgn = f'[Event "Chapter"]\n[Site "{url("ch9")}"]\n\n1. e4 *\n'
    repertoire = build(("italian", pgn))

    assert repertoire.chapter_location(AFTER_E4, chess.WHITE, "italian") == ChapterLocation("ch9", 1)


def test_no_chapter_location_outside_the_study():
    repertoire = build(("italian", chapter("1. e4 e5", url=url("ch1"))))

    assert repertoire.chapter_location(AFTER_E4_C5, chess.WHITE, "italian") is None
    assert repertoire.chapter_location(AFTER_E4, chess.WHITE, "vienna") is None


def test_the_repertoire_knows_each_studys_color():
    repertoire = build(
        ("italian", chapter("1. e4 e5")),
        ("sicilian", chapter("1. e4 c5", "black") + chapter("1. d4 d5", "white")),
        ("empty", ""),
    )

    assert repertoire.study_colors == {"italian": chess.WHITE, "sicilian": chess.BLACK}


def named(study_name):
    builder = RepertoireBuilder()
    builder.add_study(chapter("1. e4 e5"), "Italian Game", study_name=study_name, study_id="abc")
    return builder.build()


def test_the_repertoire_knows_each_studys_name():
    assert named("Italian-Game").study_names == {"abc": "Italian-Game"}


def test_renaming_a_study_changes_the_repertoire():
    assert named("Italian-Game") == named("Italian-Game")
    assert named("Italian-Game") != named("Giuoco Piano")


def test_study_link_opens_the_chapter_at_the_ply_of_a_mainline_position():
    assert study_url("abc", "ch1", 7) == "https://lichess.org/study/abc/ch1#7"


def test_study_link_opens_the_chapter_when_the_position_is_off_its_mainline():
    assert study_url("abc", "ch1", None) == "https://lichess.org/study/abc/ch1"


def test_study_link_opens_the_study_when_the_chapter_is_unknown():
    assert study_url("abc", None, None) == "https://lichess.org/study/abc"
