"""Fixed medical regression cases (V253). Run on every release.

Each case is (id, patient input). ``snapshot()`` records the decision level and whether the
emergency path fired. ``medical_regression_snapshot.json`` is the reviewed expectation;
a change in any case fails the test until a human regenerates and reviews the diff
(``python tools/regression_update.py``).
"""
from __future__ import annotations

import analysis_core

_BASE = {"age": "30", "gender": "female", "duration": "2", "severity": "2", "conditions": "", "medications": "", "notes": ""}

CASES = [
    # (id, symptoms, overrides, must_be_emergency)
    ("knee_click_no_pain", ["طقطقة الركبة"], {"notes": "بدون ألم"}, False),
    ("mild_headache", ["صداع"], {}, False),
    ("mild_cough", ["كحة"], {}, False),
    ("period_nausea", ["غثيان"], {"notes": "مع بداية الدورة الشهرية"}, False),
    ("sore_throat", ["ألم الحلق"], {}, False),
    ("fainting", ["إغماء"], {"severity": "4"}, None),
    ("chest_pain_severe", ["ألم في الصدر"], {"severity": "5", "notes": "ألم شديد ينتشر للذراع مع تعرق"}, True),
    ("breathing_difficulty", ["صعوبة في التنفس"], {"severity": "5"}, True),
    ("breathing_difficulty_4of5", ["صعوبة في التنفس"], {"severity": "4"}, None),
    ("sudden_weakness_speech", ["ضعف مفاجئ في جانب واحد"], {"notes": "صعوبة في الكلام"}, True),
    ("suicidal_note", ["حزن"], {"notes": "أفكر أنهي حياتي"}, True),
    ("child_high_fever", ["حمى"], {"age": "1", "severity": "4"}, None),
    ("english_chest_pain", ["chest pain"], {"severity": "5", "notes": "crushing pain, sweating"}, True),
]


def run_case(symptoms, overrides, lang="ar"):
    p = dict(_BASE)
    p.update(overrides)
    p["symptoms"] = list(symptoms)
    r = analysis_core.run_analysis(p, lang)
    return {"level": r["decision"]["level"], "emergency": bool(r.get("emergency"))}


def snapshot():
    out = {}
    for cid, syms, ov, _ in CASES:
        lang = "en" if cid.startswith("english_") else "ar"
        out[cid] = run_case(syms, ov, lang)
    return out
