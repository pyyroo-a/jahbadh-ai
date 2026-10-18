import pytest

from jahbadh.agents.numbers import normalize_digits, number_matches, numeric_tokens, words_to_digits


@pytest.mark.parametrize("written,value,ok", [
    ("79%", 0.787, True), ("78%", 0.787, False), ("78.7%", 0.787, True),
    ("1.1", 1.13, True), ("1.2", 1.13, False), ("1.13", 1.134, True),
    ("12.5", -12.5, True), ("7", 7.4, True), ("7", 7.6, False),
    ("4v2", "4v2", True), ("4v3", "4v2", False), ("4 v 2", "4v2", True),
])
def test_number_matches(written, value, ok):
    assert number_matches(written, value) is ok


def test_unparseable_written_number_never_matches():
    assert number_matches("lots", 3.0) is False


def test_normalize_digits():
    assert normalize_digits("٧٩٪ و ٠٫٧٩") == "79% و 0.79"
    assert normalize_digits("۷۹") == "79"
    assert normalize_digits("un 0,79 y 1.500 pases") == "un 0.79 y 1.500 pases"
    assert numeric_tokens("79 % de 3-4-3") == ["79", "3", "4", "3"]


@pytest.mark.parametrize("text,expected", [
    ("five goals from ten shots", "5 goals from 10 shots"),
    ("Three shots and twice on target", "3 shots and 2 on target"),
    ("leaving one booking on the pitch", "leaving 1 booking on the pitch"),
    ("a tidy four-pass sequence", "a tidy 4-pass sequence"),
    ("in the ten minutes before the change", "in the 10 minutes before the change"),
    ("laying one to Yusuf Pereira", "laying one to Yusuf Pereira"),          # a pronoun, not a count
    ("one of the best chances", "one of the best chances"),
    ("a very good chance, one worth 0.69 xG", "a very good chance, one worth 0.69 xG"),
    ("a quick one-two and a one-on-one", "a quick one-two and a one-on-one"),
    ("no one closed him down", "no one closed him down"),
    ("someone and everyone", "someone and everyone"),
])
def test_number_words_read_as_digits(text, expected):
    # showcase run: "leaving one booking on the pitch" was false (3 bookings by 61') and number words were never checked
    assert words_to_digits(text) == expected
