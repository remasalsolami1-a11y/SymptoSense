import source_bundle
import versioning
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import blood_test


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


def test_guest_cbc_is_not_persisted():
    web = source_bundle.webapp_text()
    block = source_bundle.between('@app.route("/api/blood"', 'def run_webapp')
    assert 'if _ss_user_id():' in block
    assert 'db.save_blood_test' in block
    assert block.index('if _ss_user_id():') < block.index('db.save_blood_test')


def test_guest_profile_requires_login():
    web = source_bundle.webapp_text()
    marker='@app.route("/api/profile", methods=["POST"])\n@login_required\ndef api_profile():'
    assert marker in web


def test_shared_rate_limiter_does_not_fail_open():
    text = _read('platform_v2.py')
    block = text[text.index('def request_allowed('):text.index('def prune_rate_limit_events')]
    assert 'return True' not in block.split('except Exception:',1)[1]
    assert 'raise' in block.split('except Exception:',1)[1]


def test_disabled_account_checks_password_before_status():
    text = _read('db.py')
    block = text[text.index('def authenticate_ss_user_status'):text.index('def authenticate_ss_user(')]
    assert block.index('valid, needs_upgrade = _verify_password') < block.index('account_unavailable')


def test_public_login_genericizes_account_unavailable():
    text = source_bundle.webapp_text()
    block = source_bundle.between('def api_login():', '@app.route("/api/auth/resend-verification"')
    assert 'if code in {"account_not_found", "account_unavailable"}' in block
    assert 'return jsonify({"ok":False,"error":code}),401' in block


def test_registration_does_not_return_email_exists_publicly():
    text = source_bundle.webapp_text()
    block = source_bundle.between('def api_register():', '@app.route("/api/auth/login"')
    assert 'if err == "email_exists":' in block
    assert '"registration_unavailable"' in block


def test_cbc_multi_page_pdf_reads_the_whole_valid_pdf_with_size_bound():
    text = source_bundle.webapp_text()
    block = source_bundle.between('@app.route("/api/blood"', 'def run_webapp')
    # V207+ intentionally accepts valid PDFs regardless of page count; the upload
    # remains bounded by bytes and every page is considered.
    assert 'BLOOD_UPLOAD_MAX_BYTES' in block
    assert 'if len(raw) > blood_upload_limit:' in block
    assert 'for page_index in range(len(pdf)):' in block
    assert 'pages_total": len(pdf)' in block
    assert 'pdf[0]' not in block


def test_neutrophil_absolute_count_wording_follows_unit():
    results, *_ = blood_test.analyze_blood([
        {'key':'neut','value':5.0,'unit':'10^9/L','reference_low':2.0,'reference_high':7.5}
    ], gender='f', age=30)
    desc = blood_test.describe_results(results, 'en')[0]
    assert 'Absolute neutrophil count' in desc['what']
    assert 'percentage' not in desc['what'].lower()


def test_teething_not_presented_as_true_fever_cause():
    text = _read('health_search.py')
    assert 'التسنين قد يسبب ارتفاعًا بسيطًا في الحرارة لكنه لا يفسر عادة حمى حقيقية 38°م أو أكثر' in text
    assert 'Teething may cause a small temperature rise but does not usually explain a true fever of 38°C or higher' in text


def test_groq_uses_max_completion_tokens():
    for name in ('webapp.py','bot.py'):
        text = _read(name)
        assert 'max_tokens=' not in text.replace('def _groq_chat_completion_with_retry(messages, *, max_tokens=240', '')
        assert 'max_completion_tokens=' in text


def test_release_metadata_v42():
    assert versioning.SW_CACHE in _read('service-worker.js')
    assert "RELEASE_CANDIDATE_ID=" + versioning.RC_ID in _read('.env.example')


def test_differential_does_not_double_count_overlapping_concepts():
    import medical_knowledge
    cases = [('انسداد الانف','ar'), ('رعشه','ar'), ('one sided numbness','en')]
    for text, lang in cases:
        result = medical_knowledge.differential_question([text], lang=lang)
        assert all(int(c.get('matched_count', 0)) <= 1 for c in result.get('candidates', []))
