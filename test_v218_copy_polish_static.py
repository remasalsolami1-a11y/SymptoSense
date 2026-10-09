import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_core_disclaimer_is_clear_and_consistent():
    web = source_bundle.webapp_text()
    chat = source_bundle.chat_view_text()
    expected = "يقدم SymptoSense معلومات وإرشادًا أوليًا، ولا يُعد تشخيصًا طبيًا أو بديلًا عن التقييم الطبي عند الحاجة."
    assert expected in web
    assert expected in chat
    assert "راجع الطبيب عند أي شك" not in web
    assert "راجع الطبيب عند أي شك" not in chat


def test_symptom_analysis_label_is_consistent():
    web = source_bundle.webapp_text()
    manifest = read("manifest.webmanifest")
    assert "تحليل الأعراض" in web
    assert "تحليل الأعراض" in manifest
    assert '"فحص الأعراض"' not in manifest


def test_severity_scale_has_distinct_levels():
    chat = source_bundle.chat_view_text()
    bot = read("bot.py")
    for source in (chat, bot):
        assert "1️⃣ خفيف جدًا" in source
        assert "2️⃣ خفيف" in source
        assert "3️⃣ متوسط" in source
        assert "4️⃣ شديد" in source
        assert "5️⃣ شديد جدًا" in source
        assert "5️⃣ حرج جدًا" not in source


def test_model_percentage_copy_is_not_diagnostic_probability():
    chat = source_bundle.chat_view_text()
    assert "النسب تعبّر عن درجة توافق المعلومات المدخلة مع كل احتمال" in chat
    assert "هذه النسب تمثل مخرجات النموذج" not in chat


def test_medication_warning_is_gender_neutral():
    chat = source_bundle.chat_view_text()
    assert "لا توقف أو تغيّر أي دواء موصوف دون استشارة الطبيب أو الصيدلي." in chat
    assert "لا توقفي دواءك" not in chat


def test_source_copy_does_not_overclaim_verification():
    source = read("health_library.py")
    assert "تتضمن الصفحة مصادر سعودية وعالمية داعمة للمحتوى." in source
    assert "تم التحقق من وجود مصدر سعودي موثوق" not in source


def test_transcription_medication_question_is_formal_arabic():
    web = source_bundle.webapp_text()
    assert "ما الأدوية التي تتناولها حاليًا؟" in web
    assert "وش الأدوية اللي تتناولها" not in web


def test_checkin_copy_tracks_change_without_emergency_wording():
    web = source_bundle.webapp_text()
    assert "سجّل شعورك اليومي من 1 إلى 5 وتابع التغيّر مع الوقت." in web
    assert "سجّل حالتك كل يوم" not in web
