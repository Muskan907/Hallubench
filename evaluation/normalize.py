import re
import unicodedata


def normalize_text(value):
    if value is None:
        return ""

    text = unicodedata.normalize("NFKC", str(value))
    text = text.lower()
    text = text.replace("’", "'")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_name(value):
    text = normalize_text(value)

    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_number(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return value

    text = str(value).replace(",", "")

    match = re.search(r"-?\d+(?:\.\d+)?", text)

    if not match:
        return None

    number = match.group(0)

    try:
        return float(number) if "." in number else int(number)
    except ValueError:
        return None


def extract_numbers(text):
    if not text:
        return []

    matches = re.findall(
        r"(?<!\w)-?\d+(?:,\d{3})*(?:\.\d+)?",
        str(text),
    )

    return [
        normalize_number(x)
        for x in matches
        if normalize_number(x) is not None
    ]


def contains_value(answer, expected):
    if expected is None:
        return False

    expected_number = normalize_number(expected)

    if expected_number is not None:
        return expected_number in extract_numbers(answer)

    if isinstance(expected, list):
        return any(
            normalize_name(item) in normalize_name(answer)
            for item in expected
        )

    return normalize_name(expected) in normalize_name(answer)