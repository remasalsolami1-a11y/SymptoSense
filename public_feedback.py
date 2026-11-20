"""Quality gate for comments shown on the public reviews page.

Only comments that describe an experience are published; one-word cheers,
joke text and keyboard-mash are kept private. Ratings are shown as an average
only once enough of them exist to be meaningful.
"""
import re

MIN_CHARS = 25
MIN_WORDS = 4
MIN_RATINGS_FOR_AVERAGE = 20


def acceptable(comment):
    text = re.sub(r"\s+", " ", str(comment or "")).strip()
    if len(text) < MIN_CHARS:
        return False
    words = re.findall(r"[\w؀-ۿ]+", text)
    if len(words) < MIN_WORDS or len(set(w.lower() for w in words)) < 3:
        return False
    if re.search(r"(.)\1{3,}", text):
        return False
    return True


def avg_visible(ratings):
    try:
        return int(ratings or 0) >= MIN_RATINGS_FOR_AVERAGE
    except (TypeError, ValueError):
        return False
