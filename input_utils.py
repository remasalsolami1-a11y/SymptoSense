"""Small, strict parsers for values that arrive in JSON bodies."""


def parse_int(value, low, high):
    """Return an int in [low, high], or None for anything else.

    Accepts an int, an integral float (4.0), or a short string of decimal digits (other scripts' digits such as
    Arabic-Indic are fine: int() understands them). Rejects bool, fractions, lists/dicts, superscripts like '\u00b2'
    (str.isdigit() says yes but int() raises), inf/nan, and absurdly long strings (int() raises past ~4300 digits).
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        value = int(value) if abs(value) < 1e12 and value.is_integer() else None
    elif isinstance(value, str):
        text = value.strip()
        if not text or len(text) > 12:
            return None
        try:
            value = int(text)
        except ValueError:
            return None
    if not isinstance(value, int) or not low <= value <= high:
        return None
    return value


def parse_rating(value, low=1, high=5):
    return parse_int(value, low, high)


def as_dict(value):
    """A JSON body that is not an object (list, string, number, null) is treated as empty."""
    return value if isinstance(value, dict) else {}


def as_text(value):
    """Only real strings count as text; lists, dicts, numbers and None become ''."""
    return value if isinstance(value, str) else ""
