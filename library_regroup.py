"""Corrects the library category of entries that were filed under the wrong
section (e.g. ear pain under joint pain, kidney stones under digestive).
Display-only: the stored category (used by the analysis engine) is untouched."""

_MOVES = {
    "ear": "pain-ear-touch ear-canal-pain ear-pain loud-noise-exposure sudden-hearing-loss muffled-hearing ear-discharge tinnitus "
           "ear-infection otitis-externa sudden-hearing-loss-warning-pattern noise-induced-hearing-loss",
    "eye": "eye-burning eye-pain watery-eyes gritty-eyes eye-discharge itchy-eyelids eyelash-crusts eye-redness "
           "conjunctivitis allergic-conjunctivitis dry-eyes blepharitis",
    "mouth": "tooth-pain jaw-clicking jaw-pain-chewing jaw-pain swollen-gums bleeding-gums mouth-ulcers dry-mouth "
             "food-triggered-mouth-itch gum-disease mouth-ulcer-pattern dental-abscess temporomandibular-disorder dry-mouth-pattern",
    "urinary": "reduced-urination dark-urine blood-in-urine cloudy-urine painful-urination frequent-urination flank-pain "
               "urinary-tract-infection kidney-infection kidney-stones",
    "womens_health": "vaginal-dryness missed-period hot-flushes vaginal-odor vaginal-itching vaginal-discharge premenstrual-pattern "
                     "pain-during-sex pelvic-pain breast-tenderness menstrual-cramps irregular-periods heavy-periods excess-hair-growth "
                     "vaginal-dryness-pattern missed-late-period-pattern perimenopause-symptom-pattern "
                     "polycystic-ovary-syndrome-pattern endometriosis-pattern period-pain",
}
OVERRIDE = {slug: cat for cat, slugs in _MOVES.items() for slug in slugs.split()}


def apply(slug, cat, cats):
    """Return the category dict to display for ``slug``."""
    target = OVERRIDE.get(slug)
    if not target:
        return cat
    for c in cats.values():
        if c.get("slug") == target:
            return c
    return cat
