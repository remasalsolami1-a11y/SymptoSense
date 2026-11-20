"""Deterministic, signed state machine for symptom-assessment conversations.

The state machine structures the conversation; it does not diagnose. Final
assessment remains delegated to :mod:`analysis_core` so V2 does not create a
second medical decision engine.

Security note: browser clients are never trusted to decide ``step`` or
``complete``. API clients receive a server-signed state token and must return it
on the next request. The token is integrity-protected with HMAC-SHA256 and has a
short lifetime.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any
import base64
import hashlib
import hmac
import json
import time

import analysis_core

FLOW = ("age", "gender", "symptoms", "duration", "severity", "red_flags", "context", "result")
TOKEN_VERSION = 1
DEFAULT_TOKEN_MAX_AGE = 30 * 60


@dataclass
class AssessmentState:
    step: str = "age"
    age: int | None = None
    gender: str | None = None
    symptoms: list[str] = field(default_factory=list)
    duration: str | None = None
    severity: int | None = None
    red_flag_notes: str = ""
    red_flags_checked: bool = False
    red_flag_hits: list[str] = field(default_factory=list)
    conditions: str = ""
    medications: str = ""
    allergies: str = ""
    notes: str = ""
    answers: dict[str, Any] = field(default_factory=dict)
    complete: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _next_step(state: AssessmentState) -> str:
    if state.age is None:
        return "age"
    if not state.gender:
        return "gender"
    if not state.symptoms:
        return "symptoms"
    if not state.duration:
        return "duration"
    if state.severity is None:
        return "severity"
    if not state.red_flags_checked:
        return "red_flags"
    if state.complete:
        return "result"
    return "context"


def progress(state: AssessmentState) -> int:
    checks = [
        state.age is not None,
        bool(state.gender),
        bool(state.symptoms),
        bool(state.duration),
        state.severity is not None,
        state.red_flags_checked,
    ]
    completed = sum(1 for x in checks if x)
    if state.complete:
        completed += 1
    return int(round(100 * completed / 7))


def prompt(step: str, lang: str = "ar") -> dict:
    ar = lang != "en"
    prompts = {
        "age": ("كم عمرك؟", "How old are you?", "number"),
        "gender": ("ما الجنس البيولوجي المرتبط بالتقييم الصحي؟", "What biological sex is relevant to this health assessment?", "choice"),
        "symptoms": ("صف الأعراض بطريقتك.", "Describe your symptoms in your own words.", "text"),
        "duration": ("من متى بدأت الأعراض؟", "When did the symptoms start?", "text"),
        "severity": ("ما شدة الأعراض من 1 إلى 5؟", "How severe are the symptoms from 1 to 5?", "scale"),
        "red_flags": ("سنتحقق الآن من علامات الخطر قبل المتابعة.", "We will check for urgent warning signs before continuing.", "system"),
        "context": ("هل توجد أدوية أو حالات صحية أو تفاصيل إضافية مهمة؟", "Any medicines, health conditions, allergies, or other important details?", "context"),
        "result": ("اكتمل التقييم.", "Assessment complete.", "result"),
    }
    a, e, typ = prompts.get(step, prompts["symptoms"])
    return {"step": step, "text": a if ar else e, "input_type": typ}


def _clean_text(value: Any, limit: int, *, allow_empty: bool = True) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("invalid_state")
    out = value.strip()
    if not allow_empty and not out:
        raise ValueError("invalid_state")
    if len(out) > limit:
        raise ValueError("invalid_state")
    return out


def from_dict(data: dict | None) -> AssessmentState:
    """Strictly validate a serialized assessment state.

    This function intentionally recomputes ``step`` rather than trusting the
    supplied value. ``complete`` is accepted only when all prior steps are
    internally valid; API callers additionally require an HMAC-signed token.
    """
    if data is None:
        return AssessmentState()
    if not isinstance(data, dict):
        raise ValueError("invalid_state")

    st = AssessmentState()

    age = data.get("age")
    if age is not None:
        if isinstance(age, bool):
            raise ValueError("invalid_state")
        try:
            age = int(age)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("invalid_state")
        if not 0 <= age <= 120:
            raise ValueError("invalid_state")
        st.age = age

    gender = data.get("gender")
    if gender not in (None, ""):
        if gender not in {"male", "female"}:
            raise ValueError("invalid_state")
        st.gender = gender

    symptoms = data.get("symptoms", [])
    if symptoms is None:
        symptoms = []
    if not isinstance(symptoms, list) or len(symptoms) > 12:
        raise ValueError("invalid_state")
    clean_symptoms: list[str] = []
    for item in symptoms:
        if not isinstance(item, str):
            raise ValueError("invalid_state")
        item = item.strip()
        if not item or len(item) > 160:
            raise ValueError("invalid_state")
        clean_symptoms.append(item)
    st.symptoms = clean_symptoms

    duration = data.get("duration")
    if duration not in (None, ""):
        st.duration = _clean_text(duration, 120, allow_empty=False)

    severity = data.get("severity")
    if severity is not None:
        if isinstance(severity, bool):
            raise ValueError("invalid_state")
        try:
            severity = int(severity)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("invalid_state")
        if not 1 <= severity <= 5:
            raise ValueError("invalid_state")
        st.severity = severity

    checked = data.get("red_flags_checked", False)
    if not isinstance(checked, bool):
        raise ValueError("invalid_state")
    st.red_flags_checked = checked

    hits = data.get("red_flag_hits", []) or []
    if not isinstance(hits, list) or len(hits) > 20:
        raise ValueError("invalid_state")
    st.red_flag_hits = []
    for item in hits:
        if not isinstance(item, str) or not item.strip() or len(item) > 240:
            raise ValueError("invalid_state")
        st.red_flag_hits.append(item.strip())

    for field_name in ("conditions", "medications", "allergies", "notes"):
        setattr(st, field_name, _clean_text(data.get(field_name, ""), 1200))

    # Preserve the original safety answer independently of later context.
    # Older signed states used notes for this purpose.
    st.red_flag_notes = _clean_text(
        data.get("red_flag_notes", st.notes if st.red_flags_checked else ""), 1200
    )

    answers = data.get("answers", {}) or {}
    if not isinstance(answers, dict) or len(answers) > 40:
        raise ValueError("invalid_state")
    # ``answers`` is informational only. Keep simple bounded primitives so state
    # tokens cannot be abused as an arbitrary JSON storage container.
    safe_answers: dict[str, Any] = {}
    for key, value in answers.items():
        if not isinstance(key, str) or not key or len(key) > 64:
            raise ValueError("invalid_state")
        if isinstance(value, bool) or value is None:
            safe_answers[key] = value
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            safe_answers[key] = value
        elif isinstance(value, str) and len(value) <= 240:
            safe_answers[key] = value
        else:
            raise ValueError("invalid_state")
    st.answers = safe_answers

    complete = data.get("complete", False)
    if not isinstance(complete, bool):
        raise ValueError("invalid_state")
    if complete:
        prerequisites = (
            st.age is not None,
            st.gender in {"male", "female"},
            bool(st.symptoms),
            bool(st.duration),
            st.severity is not None,
            st.red_flags_checked,
        )
        if not all(prerequisites):
            raise ValueError("invalid_state")
        st.complete = True

    # Never trust a serialized step. Derive it from validated fields.
    st.step = _next_step(st)
    return st


def _coerce_state(value: AssessmentState | dict | None) -> AssessmentState:
    if isinstance(value, AssessmentState):
        return from_dict(value.to_dict())
    return from_dict(value)


def apply_answer(state_data: AssessmentState | dict | None, answer: Any, lang: str = "ar") -> dict:
    st = _coerce_state(state_data)
    step = _next_step(st)
    if step == "result":
        raise ValueError("assessment_already_complete")

    if step == "age":
        try:
            age = int(str(answer).strip())
        except (TypeError, ValueError, OverflowError):
            raise ValueError("invalid_age")
        if age < 0 or age > 120:
            raise ValueError("invalid_age")
        st.age = age
    elif step == "gender":
        g = str(answer or "").strip().lower()
        if g not in {"male", "female", "m", "f", "ذكر", "انثى", "أنثى"}:
            raise ValueError("invalid_gender")
        st.gender = "female" if g in {"female", "f", "انثى", "أنثى"} else "male"
    elif step == "symptoms":
        if isinstance(answer, list):
            symptoms = []
            for item in answer:
                if not isinstance(item, str):
                    raise ValueError("invalid_symptoms")
                item = item.strip()
                if item:
                    symptoms.append(item[:160])
        else:
            txt = str(answer or "").strip()
            if len(txt) > 2000:
                raise ValueError("invalid_symptoms")
            symptoms = [x.strip()[:160] for x in txt.replace("،", ",").split(",") if x.strip()]
            if not symptoms and txt:
                symptoms = [txt[:160]]
        if not symptoms:
            raise ValueError("missing_symptoms")
        st.symptoms = symptoms[:12]
    elif step == "duration":
        text = str(answer or "").strip()
        if not text:
            raise ValueError("missing_duration")
        if len(text) > 120:
            raise ValueError("invalid_duration")
        st.duration = text
    elif step == "severity":
        try:
            sev = int(str(answer).strip())
        except (TypeError, ValueError, OverflowError):
            raise ValueError("invalid_severity")
        if sev < 1 or sev > 5:
            raise ValueError("invalid_severity")
        st.severity = sev
    elif step == "red_flags":
        note = str(answer or "")
        if len(note) > 1200:
            raise ValueError("invalid_red_flag_context")
        hits = analysis_core.detect_red_flags(st.symptoms, note, lang)
        st.red_flag_hits = [str(x)[:240] for x in hits] if isinstance(hits, list) else []
        st.red_flags_checked = True
        st.red_flag_notes = note.strip()
        if note:
            st.notes = (st.notes + " " + note).strip()[:1200]
    elif step == "context":
        ctx = answer if isinstance(answer, dict) else {"notes": str(answer or "")}
        if len(ctx) > 8:
            raise ValueError("invalid_context")
        for key in ("conditions", "medications", "allergies", "notes"):
            if key in ctx:
                value = str(ctx.get(key) or "").strip()
                if len(value) > 1200:
                    raise ValueError("invalid_context")
                setattr(st, key, value)
        st.complete = True

    st.step = _next_step(st)
    return {"state": st.to_dict(), "progress": progress(st), "prompt": prompt(st.step, lang)}


def analyze(state_data: AssessmentState | dict, lang: str = "ar") -> dict:
    st = _coerce_state(state_data)
    if not st.complete or _next_step(st) != "result":
        raise ValueError("assessment_incomplete")
    patient = {
        "age": st.age,
        "gender": st.gender,
        "symptoms": st.symptoms,
        "duration": st.duration,
        "severity": st.severity,
        "conditions": st.conditions,
        "medications": st.medications,
        "allergies": st.allergies,
        # A clause separator prevents later negation from changing the safety answer.
        "notes": " ; ".join(dict.fromkeys(x for x in (st.red_flag_notes, st.notes) if x)),
    }
    result = analysis_core.run_analysis(patient, lang)
    return {"state": st.to_dict(), "progress": 100, "result": result}


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64u(text: str) -> bytes:
    raw = str(text or "")
    return base64.urlsafe_b64decode(raw + "=" * ((4 - len(raw) % 4) % 4))


def _signing_key(secret: str | bytes) -> bytes:
    key = secret if isinstance(secret, bytes) else str(secret or "").encode("utf-8")
    if len(key) < 32:
        raise ValueError("state_signing_key_unavailable")
    return key


def sign_state(state: AssessmentState | dict, secret: str | bytes, *, issued_at: int | None = None) -> str:
    st = _coerce_state(state)
    payload = {
        "v": TOKEN_VERSION,
        "iat": int(time.time() if issued_at is None else issued_at),
        "state": st.to_dict(),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(_signing_key(secret), raw, hashlib.sha256).digest()
    return _b64u(raw) + "." + _b64u(sig)


def verify_state_token(token: str, secret: str | bytes, *, max_age_seconds: int = DEFAULT_TOKEN_MAX_AGE, now: int | None = None) -> AssessmentState:
    if not isinstance(token, str) or len(token) > 20_000 or token.count(".") != 1:
        raise ValueError("invalid_state_token")
    payload_part, sig_part = token.split(".", 1)
    try:
        raw = _unb64u(payload_part)
        supplied = _unb64u(sig_part)
    except Exception:
        raise ValueError("invalid_state_token")
    expected = hmac.new(_signing_key(secret), raw, hashlib.sha256).digest()
    if not hmac.compare_digest(supplied, expected):
        raise ValueError("invalid_state_token")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        raise ValueError("invalid_state_token")
    if not isinstance(payload, dict) or payload.get("v") != TOKEN_VERSION:
        raise ValueError("invalid_state_token")
    iat = payload.get("iat")
    if isinstance(iat, bool) or not isinstance(iat, int):
        raise ValueError("invalid_state_token")
    current = int(time.time() if now is None else now)
    if iat > current + 60:
        raise ValueError("invalid_state_token")
    if current - iat > max(60, int(max_age_seconds)):
        raise ValueError("expired_state_token")
    return from_dict(payload.get("state"))
