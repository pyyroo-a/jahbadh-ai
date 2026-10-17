"""Reading numbers the way a human writes them, in English, Arabic and Spanish."""

import re

ARABIC_DIGITS = {ord(c): str(i) for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")} | {ord(c): str(i) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")}
ARABIC_MARKS = {ord("٫"): ".", ord("٪"): "%"}
DECIMAL_COMMA = re.compile(r"(?<=\d),(?=\d{1,3}(?!\d))")
SPACED_PERCENT = re.compile(r"(?<=\d) +%")
NUMBER = re.compile(r"\d+(?:\.\d+)?")


def normalize_digits(text: str) -> str:
    """Arabic-Indic digits to ASCII, Arabic decimal and percent signs to . and %, "0,79" to "0.79", "79 %" to "79%"."""
    text = text.translate(ARABIC_DIGITS).translate(ARABIC_MARKS)
    return SPACED_PERCENT.sub("%", DECIMAL_COMMA.sub(".", text))


def numeric_tokens(text: str) -> list[str]:
    return NUMBER.findall(normalize_digits(text))


def number_matches(written: str, value: float | str) -> bool:
    """Does `written` say `value`, at the precision it is written? "79%" says 0.787; "1.2" does not say 1.13.
    Signs are ignored (direction words are the semantic judge's job)."""
    if isinstance(value, str):
        return written.replace(" ", "").lower() == value.replace(" ", "").lower()
    w = normalize_digits(written)
    found = NUMBER.search(w)
    if found is None:
        return False
    number = float(found.group())
    decimals = len(found.group().partition(".")[2])
    tolerance = 0.5 * 10 ** -decimals + 1e-9
    target = abs(value) * 100 if "%" in w else abs(value)
    return abs(number - target) <= tolerance
