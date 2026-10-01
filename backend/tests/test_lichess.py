from lichess import study_url


def test_study_link_opens_the_chapter_at_the_ply_of_a_mainline_position():
    assert study_url("abc", "ch1", 7) == "https://lichess.org/study/abc/ch1#7"


def test_study_link_opens_the_chapter_when_the_position_is_off_its_mainline():
    assert study_url("abc", "ch1", None) == "https://lichess.org/study/abc/ch1"


def test_study_link_opens_the_study_when_the_chapter_is_unknown():
    assert study_url("abc", None, None) == "https://lichess.org/study/abc"
