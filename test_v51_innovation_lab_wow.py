import source_bundle
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parent

if "groq" not in sys.modules:
    fake = types.ModuleType("groq")
    class _Groq:
        def __init__(self, *args, **kwargs):
            pass
    fake.Groq = _Groq
    sys.modules["groq"] = fake


def test_live_probe_understands_combo_and_stays_nonpersistent():
    import v51_innovation
    result = v51_innovation.probe_phrase('ركبتي تطقطق وتوجعني', 'ar')
    assert result['ok'] is True
    slugs = {x['slug'] for x in result['recognized_symptoms']}
    assert {'knee-pain', 'joint-clicking'} <= slugs
    assert any(x['slug'] == 'oa-knee-pattern' for x in result['pattern_insights'])
    assert result['safety_alert'] is False
    assert 'results' not in result  # lab exposes interpretation, not disease ranking
    assert 'answer' not in result


def test_live_probe_surfaces_safety_alert_without_ranking():
    import v51_innovation
    result = v51_innovation.probe_phrase('ألم صدر شديد مع ضيق تنفس شديد', 'ar')
    assert result['ok'] is True
    assert result['safety_alert'] is True
    assert result['red_flags']
    assert 'results' not in result


def test_coverage_matrix_is_computed_from_real_kb():
    import v51_innovation
    c = v51_innovation._coverage_matrix()
    assert c['symptoms_total'] >= 100
    assert 0 <= c['symptoms_linked'] <= c['symptoms_total']
    assert 0 <= c['diseases_sourced'] <= c['diseases_total']
    assert 0 <= c['red_flags_sourced'] <= c['red_flags_total']


def test_combo_catalog_integrity_gate_is_clean():
    import v51_innovation
    status = v51_innovation._combo_catalog_status()
    assert status['ok'] is True, status['issues']


def test_innovation_page_contains_wow_sections_and_safe_dom_rendering():
    import v51_innovation
    def page(title, body, desc=None, bare=False, extra_css=''):
        return title + '\n' + body + '\n' + extra_css
    html = v51_innovation.render_innovation_lab(page=page, lang='ar')
    assert 'مختبر اللغة الحي' in html
    assert 'Coverage Matrix' in html
    assert 'Combo Explorer' in html
    assert 'Why trust the process?' in html
    assert '/api/admin/innovation-lab/probe' in html
    assert "document.querySelectorAll('[data-iv-example]')" in html
    assert 'innerHTML=' not in html.split('<script>',1)[1].split('</script>',1)[0]


def test_probe_endpoint_is_rate_limited_and_bounded_statically():
    src = source_bundle.webapp_text()
    assert '@app.route("/api/admin/innovation-lab/probe", methods=["POST"])' in src
    assert '@admin_api_required("analytics")' in src
    assert '_request_allowed("innovation_probe", 40, 60)' in src
    assert 'len(text) > 180' in src


def test_evidence_passport_is_nonclinical_and_computed():
    import v51_innovation
    e = v51_innovation.evidence_snapshot()
    assert e["project"] == "SymptoSense"
    assert e["clinical_validation"] is False
    assert e["diagnostic_accuracy_claim"] is False
    assert e["knowledge"]["symptoms"] >= 100
    assert e["combo_catalog"]["valid"] is True
    assert e["synthetic_safety"]["total"] >= 1


def test_evidence_endpoint_and_trace_are_exposed():
    web = source_bundle.webapp_text()
    lab = (ROOT / "v51_innovation.py").read_text(encoding="utf-8")
    assert '@app.route("/api/admin/innovation-lab/evidence", methods=["GET"])' in web
    assert 'EVIDENCE TRACE' in lab
    assert 'Evidence Passport' in lab
