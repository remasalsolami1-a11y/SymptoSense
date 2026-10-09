import source_bundle
from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parent
WEB=source_bundle.python_text()
CHAT=source_bundle.chat_view_text()
CHAT2=source_bundle.chat_view_text()
SEARCH=(ROOT/'health_search.py').read_text(encoding='utf-8')
CSS=(ROOT/'static/css/app-shell-v111.css').read_text(encoding='utf-8')


def _isolated_function(name, extra_names=()):
    tree=ast.parse(WEB)
    wanted={name,*extra_names}
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
    ns={}
    return nodes,ns


def test_consent_checkbox_has_explicit_stable_visual_control():
    # V205+ uses the browser-native checkbox, but pins its geometry so global
    # text-input styling cannot stretch or hide the control.
    assert '.consent-option input[type="checkbox"]{appearance:auto!important' in WEB
    assert '-webkit-appearance:checkbox!important' in WEB
    assert 'min-height:22px!important' in WEB
    assert 'border-radius:4px!important' in WEB
    assert 'accent-color:var(--v2-blue)' in WEB


def test_followup_actions_are_deduplicated_and_simple_action_removed():
    for text in (CHAT, CHAT2):
        assert 'data-result-action="simple"' not in text
        assert 'data-result-action="care-script"' not in text
        assert 'data-simple-condition=' not in text
        assert "'ملخص للعيادة والطبيب'" in text
        assert "'ماذا أقول عند التواصل مع العيادة؟'" in text
        assert "'الملخص المنظم للطبيب'" in text
    assert CHAT == CHAT2
    assert '.doctor-card-section' in CSS


def test_blood_selected_file_hides_redundant_large_drop_zone():
    assert 'drop.hidden=selFiles.length>0;' in WEB
    # There must be only one visible click-to-upload control in the drop zone.
    start=WEB.index('<div class="lab-upload-choice lab-upload-choice-pdf"')
    end=WEB.index('const drop = document.getElementById', start)
    blood_fragment=WEB[start:end]
    assert 'id="bloodUploadBtn"' in blood_fragment
    assert 'class="d-btn"' not in blood_fragment


def test_scanned_pdf_pages_share_bounded_vision_pool():
    assert 'LAB_PDF_VISION_MAX_WORKERS' in WEB
    assert 'ThreadPoolExecutor(max_workers=pdf_workers, thread_name_prefix="lab-pdf-vision")' in WEB
    assert 'pending_vision = []' in WEB
    assert '_safe_pdf_page_png(page)' in WEB
    assert 'pdf_page_limit' not in WEB


def test_heat_nausea_shorthand_is_directly_recognized():
    tree=ast.parse(WEB)
    names={'_normalize_health_query_text','_search_contextual_structured_result'}
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    ns={
        '_health_search_relation_result':lambda q,l:None,
        '_health_search_context_relation_result':lambda q,l:None,
    }
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'v202-iso','exec'),ns)
    for query in ('غثيان الحر','الغثيان مع الحر','حر وغثيان'):
        result=ns['_search_contextual_structured_result'](query,'ar')
        assert result and result['key']=='heat_nausea'
        assert result['query_only'] is False
        assert result['curated_answer'] is True


def test_known_search_answer_is_stable_and_does_not_need_external_ai():
    tree=ast.parse(WEB)
    func=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_health_search_question_answer')
    class Bomb:
        def __getattr__(self,name):
            raise AssertionError('external AI must not be called for a covered structured topic')
    ns={
        '_strip_search_answer_heading':lambda x,l:x,
        '_assistant_compact_response':lambda x,l,c:x,
        '_assistant_contextual_health_answer':lambda q,l:None,
        '_service_consent_ok':lambda:True,
        '_assistant_general_local_fallback':lambda q,l:'',
        'analysis_core':Bomb(),
        'json':__import__('json'),'os':__import__('os'),'logging':__import__('logging'),
    }
    exec(compile(ast.Module(body=[func],type_ignores=[]),'v202-answer','exec'),ns)
    result={'query_only':False,'what':'نص ثابت من قاعدة المحتوى','causes':['سبب أ','سبب ب']}
    a=ns['_health_search_question_answer']('غثيان','ar',result)
    b=ns['_health_search_question_answer']('غثيان','ar',result)
    assert a==b=='نص ثابت من قاعدة المحتوى'


def test_heat_nausea_is_in_search_suggestions_and_home_sources_badge_is_removed():
    assert 'غثيان مع الحر' in SEARCH
    assert 'Nausea in hot weather' in SEARCH
    assert '__STAT_SOURCES_NEW__' not in WEB
    assert '+5 مصادر جديدة' not in WEB


def test_contextual_search_runs_before_generic_curated_glossary():
    marker='result = _search_contextual_structured_result(q, lang)'
    generic='result = health_search.curated_result(q, lang)'
    route=WEB[WEB.index('def api_search('):]
    assert route.index(marker) < route.index(generic)
