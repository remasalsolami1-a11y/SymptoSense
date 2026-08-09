# -*- coding: utf-8 -*-
"""Health calculators — pure calculation logic (no UI text).

Each function returns numeric values and category codes. The web layer
(webapp.py / page JS) maps codes to translated UI strings.

Safety:
  - Results that may need medical attention are flagged via ``alert`` and an
    ``alert_kind`` code ("high" / "low"). The web layer shows a safety banner
    and links to the in-site emergency page.
  - Blood-sugar wording is always range-based (never a personal diagnosis).
"""

ADULT_FLUID_ML_PER_KG = 33.0
FLUID_ACTIVITY = {"low": 1.0, "medium": 1.15, "high": 1.3}
CAL_ACTIVITY = {"low": 1.2, "medium": 1.55, "high": 1.725}
DOSE_INTERVALS = (4, 6, 8, 12, 24)
SUGAR_TYPES = ("fasting", "post", "random", "a1c")
MG_PER_MMOL = 18.016


def calc_bmi(weight_kg, height_cm):
    """BMI (kg/m^2). Returns category code + safety flag."""
    if weight_kg <= 0 or height_cm <= 0:
        raise ValueError("invalid bmi input")
    h = height_cm / 100.0
    bmi = weight_kg / (h * h)
    if bmi < 15:
        cat, color, alert = "under_severe", "red", True
    elif bmi < 18.5:
        cat, color, alert = "under", "blue", False
    elif bmi < 25:
        cat, color, alert = "normal", "green", False
    elif bmi < 30:
        cat, color, alert = "over", "yellow", False
    elif bmi < 40:
        cat, color, alert = "obese", "orange", False
    else:
        cat, color, alert = "obese_severe", "red", True
    return {
        "value": round(bmi, 1),
        "category": cat,
        "color": color,
        "alert": alert,
        "alert_kind": "high" if alert else None,
    }


def calc_fluids(age, weight_kg, activity):
    """Estimated daily fluid need in liters.

    Children (under 16) use the Holliday-Segar weight-based rule; adults use
    ~33 ml/kg/day scaled by activity level.
    """
    if weight_kg <= 0 or age <= 0:
        raise ValueError("invalid fluids input")
    if activity not in FLUID_ACTIVITY:
        raise ValueError("invalid activity level")
    factor = FLUID_ACTIVITY[activity]
    if age < 16:
        if weight_kg <= 10:
            ml = weight_kg * 100
        elif weight_kg <= 20:
            ml = 1000 + (weight_kg - 10) * 50
        else:
            ml = 1500 + (weight_kg - 20) * 20
    else:
        ml = ADULT_FLUID_ML_PER_KG * weight_kg * factor
    return {"value": round(ml / 1000.0, 1), "category": None, "alert": False}


def calc_doses(first_hour, first_minute, interval_hours, count=6):
    """Build a medication schedule (list of {h, m, first}) every interval hours."""
    if interval_hours not in DOSE_INTERVALS:
        raise ValueError("invalid interval")
    if not (0 <= first_hour <= 23 and 0 <= first_minute <= 59):
        raise ValueError("invalid first time")
    times = []
    h, m = int(first_hour), int(first_minute)
    total = h * 60 + m
    for i in range(count):
        times.append({"h": (total // 60) % 24, "m": total % 60, "first": i == 0})
        total += interval_hours * 60
    return {"schedule": times, "interval": interval_hours, "alert": False}


def calc_calories(age, gender, height_cm, weight_kg, activity):
    """Estimated daily calories (kcal) via Mifflin-St Jeor + activity factor."""
    if age <= 0 or weight_kg <= 0 or height_cm <= 0:
        raise ValueError("invalid calories input")
    if gender not in ("male", "female"):
        raise ValueError("invalid gender")
    if activity not in CAL_ACTIVITY:
        raise ValueError("invalid activity level")
    if gender == "female":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    kcal = max(800, bmr * CAL_ACTIVITY[activity])
    return {"value": int(round(kcal / 10.0) * 10), "category": None, "alert": False}


def _classify_glucose(mgdl, mtype):
    """Range-based classification (ADA). Never a personal diagnosis."""
    low = mgdl < 70
    if mtype == "fasting":
        if mgdl >= 300:
            return "very_high", "red", True
        if mgdl >= 126:
            return "high", "orange", False
        if mgdl >= 100:
            return "elevated", "yellow", False
        if mgdl >= 70:
            return "normal", "green", False
        return "low", "blue", False
    if mtype == "post":
        if mgdl >= 300:
            return "very_high", "red", True
        if mgdl >= 200:
            return "high", "orange", False
        if mgdl >= 140:
            return "elevated", "yellow", False
        if mgdl >= 70:
            return "normal", "green", False
        return "low", "blue", False
    if mtype == "random":
        if mgdl >= 300:
            return "very_high", "red", True
        if mgdl >= 200:
            return "high", "orange", False
        if mgdl >= 140:
            return "elevated", "yellow", False
        if mgdl >= 70:
            return "normal", "green", False
        return "low", "blue", False
    # a1c
    if mgdl >= 6.5:
        return "high", "orange", False
    if mgdl >= 5.7:
        return "elevated", "yellow", False
    return "normal", "green", False


def calc_sugar(reading, unit, mtype, age=None):
    """Classify a glucose reading. ``unit`` is 'mg', 'mmol' or 'a1c'."""
    if reading <= 0:
        raise ValueError("invalid reading")
    if mtype not in SUGAR_TYPES:
        raise ValueError("invalid measurement type")
    if mtype == "a1c":
        mgdl = reading
        display = round(reading, 1)
        display_unit = "%"
    elif unit == "mmol":
        mgdl = reading * MG_PER_MMOL
        display = round(reading, 1)
        display_unit = "mmol/L"
    else:
        mgdl = reading
        display = round(reading)
        display_unit = "mg/dL"

    cat, color, alert = _classify_glucose(mgdl, mtype)

    # Severe hypoglycemia overrides to a red safety flag.
    if mtype != "a1c" and mgdl < 54:
        cat, color, alert = "very_low", "red", True
        alert_kind = "low"
    elif alert:
        alert_kind = "high"
    else:
        alert_kind = None

    return {
        "value": display,
        "unit": display_unit,
        "category": cat,
        "color": color,
        "alert": alert,
        "alert_kind": alert_kind,
        "mgdl": round(mgdl),
        "pediatric": bool(age is not None and age < 16 and mtype != "a1c"),
    }
