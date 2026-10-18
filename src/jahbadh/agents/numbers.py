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
    numbers = NUMBER.findall(w)
    if len(numbers) != 1:            # "3 of 99" would let the 99 go unchecked
        return False
    number = float(numbers[0])
    decimals = len(numbers[0].partition(".")[2])
    tolerance = 0.5 * 10 ** -decimals + 1e-9
    target = abs(value) * 100 if "%" in w else abs(value)
    return abs(number - target) <= tolerance


NUMBER_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen twenty".split())} | {"twice": 2}
NUMBER_WORD = re.compile(r"(?<![\w-])(" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")\b(-?)(\s*)(\w*)",
                         re.IGNORECASE)
# "one" is often not a count: "laying one to Pereira", "one of the best", "one worth 0.69", "no one"
ONE_IS_NOT_A_COUNT = {"", "of", "to", "worth", "that", "who", "which", "another", "more", "or", "and", "the", "a",
                      "an", "in", "for", "on", "at", "from", "with"}
NOT_A_COUNT_AFTER_HYPHEN = set(NUMBER_WORDS) | {"on", "touch", "sided", "off", "time"}


def words_to_digits(text: str) -> str:
    """Number words as digits, so "five goals" is checked like "5 goals". A count only: "one" before a noun, and
    never in "no one", "one-two" or "one-on-one"."""
    def swap(m: re.Match) -> str:
        word, hyphen, space, nxt = m.group(1), m.group(2), m.group(3), m.group(4)
        lower, after = word.lower(), nxt.lower()
        if hyphen and after in NOT_A_COUNT_AFTER_HYPHEN:
            return m.group(0)
        if lower == "one" and not hyphen and after in ONE_IS_NOT_A_COUNT:
            return m.group(0)
        if lower == "one" and re.search(r"\bno\s+$", text[:m.start()], re.IGNORECASE):
            return m.group(0)
        return str(NUMBER_WORDS[lower]) + hyphen + space + nxt
    return NUMBER_WORD.sub(swap, text)
