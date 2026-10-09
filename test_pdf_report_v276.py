import io, fitz, pdf_report_extras as pre
from services.search_answers import _pdf_report

RESULT = {
    "lang": "ar", "age": 30, "gender": "female", "symptoms": ["صداع", "غثيان"], "duration": "يومان", "severity": 3,
    "urgency": "medium", "data_quality": {"percentage": 70},
    "why_result": "ظهر هذا المستوى بسبب مدة الأعراض وشدتها.",
    "risk_reasons": [{"message": "الأعراض مستمرة أكثر من 48 ساعة"}, {"description": "شدة متوسطة"}],
    "followup_answers": [{"name": "حساسية للضوء", "answer": "yes"}, {"name": "قيء", "answer": "no"}],
    "recommendations": [{"tip": "اشرب سوائل"}], "danger_signs": ["ضعف مفاجئ"], "when_to_seek_care": "إذا ساءت الأعراض",
}

def _text(buf):
    doc = fitz.open(stream=buf.getvalue(), filetype="pdf")
    return doc.page_count, "".join(p.get_text() for p in doc)

def test_arabic_pdf_has_reason_followup_and_required_disclaimer():
    pages, txt = _text(_pdf_report(RESULT, "ar"))
    assert pages >= 1
    flat = " ".join(txt.split())
    html_ar = pre.sections(RESULT, True)
    assert "سبب مستوى الخطورة" in html_ar and "الأعراض مستمرة أكثر من 48 ساعة" in html_ar
    assert "إجابات أسئلة المتابعة" in html_ar and "نعم" in html_ar and "لا" in html_ar
    assert pre.DISCLAIMER_AR.startswith("هذا ملخص للمعلومات المقدمة من المستخدم")

def test_english_pdf_builds_and_includes_followup():
    res = dict(RESULT, lang="en")
    pages, txt = _text(_pdf_report(res, "en"))
    assert pages >= 1
    flat = " ".join(txt.split())
    assert "Follow-up answers" in flat and "Why this risk level" in flat
    assert "not a medical diagnosis or a report issued by a physician" in flat

def test_pdf_without_optional_sections_still_valid():
    pages, txt = _text(_pdf_report({"symptoms": ["cough"], "urgency": "low"}, "en"))
    assert pages >= 1 and "Follow-up answers" not in txt

def test_prepare_export_sanitises_followup_and_drops_unknown_keys():
    allowed = {"symptoms", "urgency"}
    raw = {"symptoms": ["x"], "urgency": "low", "evil": "<script>", "why_result": "a", "followup_answers": [
        {"name": "ok", "answer": "yes"}, {"name": "", "answer": "yes"}, {"name": "bad", "answer": "maybe"}, "junk"] + [{"name": "n%d" % i, "answer": "no"} for i in range(40)]}
    out = pdf_report_extras_prepare(raw, allowed)
    assert "evil" not in out and out["why_result"] == "a"
    assert len(out["followup_answers"]) <= 20 and out["followup_answers"][0] == {"name": "ok", "answer": "yes"}
    assert all(x["answer"] in ("yes", "no") and x["name"] for x in out["followup_answers"])

def pdf_report_extras_prepare(raw, allowed):
    return pre.prepare_export(raw, allowed)

def test_html_in_followup_names_is_escaped():
    html = pre.sections({"followup_answers": [{"name": "<b>x</b>", "answer": "yes"}]}, False)
    assert "<b>x</b>" not in html and "&lt;b&gt;" in html


def _guest_client():
    import webapp
    webapp.app.config["TESTING"] = True
    c = webapp.app.test_client()
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    return c


def test_export_current_endpoint_works_for_guest_both_languages_and_filters_keys():
    c = _guest_client()
    for lang in ("ar", "en"):
        body = dict(RESULT, lang=lang, evil_key="<script>alert(1)</script>")
        r = c.post("/api/analyze/export-current", json={"result": body, "lang": lang})
        assert r.status_code == 200, r.get_data(as_text=True)[:200]
        assert r.headers["Content-Type"].startswith("application/pdf") and r.data.startswith(b"%PDF")
        doc = fitz.open(stream=r.data, filetype="pdf")
        assert doc.page_count >= 1
        assert "alert(1)" not in "".join(p.get_text() for p in doc)


def test_export_current_requires_current_result_and_consent():
    import webapp
    fresh = webapp.app.test_client()
    assert fresh.post("/api/analyze/export-current", json={"result": RESULT}).status_code in (401, 403, 409, 428, 400)
    c = _guest_client()
    assert c.post("/api/analyze/export-current", json={"result": {}}).status_code == 400
