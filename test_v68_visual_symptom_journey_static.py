import source_bundle
import versioning
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CHAT=source_bundle.chat_view_text()
WEB=source_bundle.webapp_text()
RC=(ROOT/"release_candidate.py").read_text(encoding="utf-8")
SW=(ROOT/"service-worker.js").read_text(encoding="utf-8")

def test_visual_symptom_path_present():
    assert "symptom-path-rail" in WEB
    assert "askSymptomPath" in CHAT
    assert "pattern_worse" in CHAT and "pattern_relief" in CHAT
    assert "مسار الأعراض" in CHAT

def test_followup_impact_is_qualitative_and_small():
    assert "كيف غيّرت إجابتك النتيجة؟" in CHAT
    assert "not a diagnostic probability" in CHAT
    assert ".followup-impact-title{font-size:11px" in WEB

def test_next_24_hours_card_and_urgent_guard():
    assert "next24PlanHtml" in CHAT
    assert "خطة الـ24 ساعة القادمة" in CHAT
    assert "لا تنتظر 24 ساعة" in CHAT

def test_unified_clinic_doctor_card_is_local_first():
    assert "openDoctorCard" in CHAT
    assert "ملخص للعيادة والطبيب" in CHAT
    assert "ماذا أقول عند التواصل مع العيادة؟" in CHAT
    assert "الملخص المنظم للطبيب" in CHAT
    assert "openDoctorHandoff" in CHAT

def test_release_v68():
    assert versioning.APP_VERSION == __import__("release_candidate").APP_VERSION
    assert versioning.RC_ID == __import__("release_candidate").RC_ID
    assert versioning.SW_CACHE in SW
