import source_bundle
import versioning
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_cbc_age_units_are_not_misread_as_years():
    import blood_test
    _entries, age = blood_test.parse_blood_text("Age 18 months\nHGB | 11.5 | g/dL | 10.5 | 13.5")
    assert age == 1.5
    _entries, age = blood_test.parse_blood_text("العمر: 6 أشهر\nHGB | 11.2 | g/dL | 10 | 13")
    assert age == 0.5


def test_cbc_common_count_unit_variants_normalize_safely():
    import blood_test
    cases = {
        "×10^9/L": "10^9/L",
        "x10⁹/L": "10^9/L",
        "10^3/µL": "10^3/uL",
        "10³/μL": "10^3/uL",
        "K/µL": "10^3/uL",
        "M/µL": "10^6/uL",
        "10^3/mm3": "10^3/uL",
    }
    for raw, expected in cases.items():
        assert blood_test._normalize_unit(raw) == expected, raw


def test_cbc_free_text_extracts_common_count_units():
    import blood_test
    rows, _age = blood_test.parse_blood_text("Age 30 years\nWBC 6.2 K/µL ref 4.0-11.0\nPLT 250 ×10⁹/L ref 150-400")
    by = {row["key"]: row for row in rows}
    assert by["wbc"]["unit"] == "10^3/uL"
    assert by["plt"]["unit"] == "10^9/L"
    assert by["wbc"]["reference_low"] == 4.0 and by["wbc"]["reference_high"] == 11.0


def test_cbc_unknown_sex_does_not_use_female_hgb_range():
    import blood_test
    rows, _notes, _dangers, level, is_child = blood_test.analyze_blood([
        {"key": "hgb", "value": 12.5, "unit": "g/dL", "reference_low": None, "reference_high": None}
    ], gender="", age=30)
    assert not is_child
    assert rows[0]["status"] == "unclassified"
    assert rows[0]["low"] is None and rows[0]["high"] is None
    assert level == "unclassified"


def test_cbc_unknown_age_never_assumes_adult_reference():
    import blood_test
    rows, *_ = blood_test.analyze_blood([
        {"key": "wbc", "value": 6.0, "unit": "10^9/L", "reference_low": None, "reference_high": None}
    ], gender="f", age=None)
    assert rows[0]["status"] == "unclassified"
    assert rows[0]["reference_source"] == "unclassified"


def test_cbc_child_without_lab_range_never_uses_adult_fallback():
    import blood_test
    rows, *_ = blood_test.analyze_blood([
        {"key": "hgb", "value": 11.0, "unit": "g/dL", "reference_low": None, "reference_high": None}
    ], gender="child", age=None)
    assert rows[0]["status"] == "unclassified"
    assert rows[0]["reference_source"] == "unclassified"


def test_cbc_ui_has_neutral_unclassified_state_and_unknown_sex():
    src = source_bundle.webapp_text()
    assert 'bl_status_u' in src
    assert 'bl_ref_unknown' in src
    assert '<option value="" selected>__BU__</option>' in src
    assert "s==='unclassified'" in src or 's === \'unclassified\'' in src


def test_health_handoff_is_no_store_no_index_and_escaped():
    src = source_bundle.webapp_text()
    assert '"/share/health/"' in src
    assert 'X-Robots-Tag' in src and 'noindex, nofollow, noarchive' in src
    assert 'Referrer-Policy"] = "no-referrer"' in src
    assert 'html_lib.escape' in src
    # Regression: the old raw previous-assessment interpolation must be gone.
    assert "lis=''.join('<li>%s — %s — %s</li>'%((\"، \".join(x.get(\"symptoms\")" not in src


def test_stored_health_data_apis_require_login():
    src = source_bundle.webapp_text()
    routes = [
        r'@app\.route\("/api/blood/history"[^\n]*\)\s*\n@api_login_required',
        r'@app\.route\("/api/handoff/candidates"[^\n]*\)\s*\n@api_login_required',
        r'@app\.route\("/api/handoff/create"[^\n]*\)\s*\n@api_login_required',
        r'@app\.route\("/api/handoff/revoke"[^\n]*\)\s*\n@api_login_required',
        r'@app\.route\("/api/analyze/export/<int:record_id>"[^\n]*\)\s*\n@api_login_required',
    ]
    for pattern in routes:
        assert re.search(pattern, src), pattern


def test_signed_in_health_mutations_are_in_csrf_gate():
    src = source_bundle.webapp_text()
    block = source_bundle.between('def protect_sensitive_user_api_csrf', 'def _admin_auth_debug')
    for prefix in ('/api/analyze', '/api/blood', '/api/assistant/feedback', '/api/feedback'):
        assert f'"{prefix}"' in block
    assert 'or not _ss_user_id()' in block  # guest flows remain available


def test_analysis_throttle_uses_fail_safe_fallback():
    web = source_bundle.webapp_text()
    platform = _read("platform_v2.py")
    analyze_block = web[web.index('def api_analyze():'):web.index('def api_analyze_differential_question') if 'def api_analyze_differential_question' in web[web.index('def api_analyze():'):] else len(web)]
    assert '_request_allowed("analyze", analyze_max, analyze_window_seconds)' in analyze_block
    limiter_start = platform.index('def analyze_request_allowed')
    limiter_end = platform.index('\ndef _request_rate_key', limiter_start)
    limiter = platform[limiter_start:limiter_end]
    assert 'return True' in limiter  # success path
    except_part = limiter.split('except Exception:', 1)[1]
    assert 'return True' not in except_part
    assert 'raise' in except_part


def test_413_is_json_safe_for_api_uploads():
    src = source_bundle.webapp_text()
    assert '@app.errorhandler(413)' in src
    block = source_bundle.between('@app.errorhandler(413)', '@app.errorhandler(404)')
    assert 'request.path.startswith("/api/")' in block
    assert '"error_code": "file_too_large"' in block


def test_v43_release_metadata_is_consistent():
    assert "APP_VERSION=" + versioning.APP_VERSION in _read('.env.example')
    assert "RELEASE_CANDIDATE_ID=" + versioning.RC_ID in _read('.env.example')
    assert versioning.RC_ID == __import__("release_candidate").RC_ID
    assert versioning.APP_VERSION == __import__("release_candidate").APP_VERSION
    assert versioning.APP_VERSION == __import__("research_study").APP_VERSION
    assert versioning.SW_CACHE in _read('service-worker.js')


def test_shared_natural_language_aliases_reach_symptom_engine():
    import medical_knowledge as mk
    expected = {
        'حرقان البول': 'painful-urination',
        'دورتي توجعني': 'menstrual-cramps',
        'دقات قلبي سريعة': 'palpitations',
        'my back hurts': 'back-pain',
        'constipated': 'constipation',
        'hard stools': 'constipation',
        'شعري يطيح': 'hair-loss',
        'اذني توجعني': 'ear-pain',
        'always thirsty': 'increased-thirst',
    }
    for phrase, slug in expected.items():
        result = mk.normalize_symptoms([phrase])
        assert slug in {item['slug'] for item in result['canonical']}, (phrase, result)
        assert not result['unmatched'], (phrase, result)


def test_cbc_chart_is_reference_normalized_not_raw_mixed_units():
    src = _read("blood_test.py")
    block = src[src.index('def generate_blood_chart'):]
    assert "Relative to each test's reference range" in block
    assert '(value - lo) / (hi - lo)' in block
    assert 'r.get("status") == "unclassified"' in block


def test_v43_retired_aliases_do_not_double_map():
    import medical_knowledge as mk
    cases = {
        "انسداد الانف": ["nasal-congestion"],
        "blocked nose": ["nasal-congestion"],
        "سيلان الانف": ["runny-nose"],
        "runny nose": ["runny-nose"],
        "one sided numbness": ["one-sided-numbness"],
        "weakness on one side": ["one-sided-weakness"],
        "رعشه": ["tremor"],
        "قشعريرة": ["chills"],
    }
    for text, expected in cases.items():
        got = [x["slug"] for x in mk.normalize_symptoms([text])["canonical"]]
        assert got == expected, (text, got)


def test_v43_effective_alias_registry_has_no_exact_cross_symptom_collisions():
    import collections
    import medical_knowledge as mk
    rows = mk._fetch_symptoms(True)
    aliases = collections.defaultdict(set)
    for item in rows:
        for value in mk._aliases_for_symptom(item):
            norm = mk._normalize_text(value)
            if norm:
                aliases[norm].add(item["slug"])
    collisions = {a: sorted(slugs) for a, slugs in aliases.items() if len(slugs) > 1}
    assert collisions == {}


def test_v43_voice_and_blood_external_ai_endpoints_are_rate_limited():
    from pathlib import Path
    source = source_bundle.webapp_text()
    voice = source_bundle.between('def api_voice():', '@app.route("/api/blood/history"')
    blood = source_bundle.between('def api_blood():', '@app.route("/api/blood/report"')
    assert '_request_allowed("voice_stt"' in voice
    assert 'VOICE_RATE_LIMIT_MAX' in voice
    assert '_request_allowed("blood_vision"' in blood
    assert 'BLOOD_RATE_LIMIT_MAX' in blood


def test_v43_guest_never_reads_persistent_legacy_profile():
    from pathlib import Path
    source = Path(__file__).resolve().parent.joinpath("webapp.py").read_text(encoding="utf-8")
    analyze = source_bundle.between('def api_analyze():', '@app.route("/api/analyze/export/<int:record_id>"')
    assert 'elif _ss_user_id() and use_saved and analysis_privacy and analysis_privacy.get("use_in_analysis", False):\n                    # Persistent legacy profile data is account-only.' in analyze
    assert 'else:\n                    p = db.load_profile(_data_user_id())' not in analyze


def test_v43_auth_rate_limit_survives_bad_shared_limiter_or_env_config():
    from pathlib import Path
    source = Path(__file__).resolve().parent.joinpath("webapp.py").read_text(encoding="utf-8")
    assert 'def _bounded_env_int(' in source
    assert 'def _login_pair_allowed(' in source
    assert '_local_request_allowed(scope + "_pair"' in source
    login = source_bundle.between('def login():', '@app.route("/register"')
    api_login = source_bundle.between('def api_login():', '@app.route("/api/auth/resend-verification"')
    assert '_login_pair_allowed(email, network_origin, "login")' in login
    assert '_login_pair_allowed(email, network_origin, "api_login")' in api_login
    assert 'int(os.environ.get("AUTH_RATE_LIMIT_MAX"' not in login
    assert 'int(os.environ.get("AUTH_RATE_LIMIT_MAX"' not in api_login
