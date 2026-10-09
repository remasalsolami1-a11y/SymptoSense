import source_bundle
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent


def test_project_metadata_was_not_replaced_by_pytest_cache():
    assert not (ROOT / 'CACHEDIR.TAG').exists()
    assert not (ROOT / 'README (1).md').exists()
    assert not (ROOT / 'webapp (8).py').exists()
    assert not (ROOT / 'README.md').read_text(encoding='utf-8').lstrip().startswith('# pytest cache directory #')
    gi = (ROOT / '.gitignore').read_text(encoding='utf-8')
    assert 'Created by pytest automatically' not in gi
    assert gi.strip() != '*'


def test_flat_qa_files_are_excluded_from_railway_image():
    dockerignore = (ROOT / '.dockerignore').read_text(encoding='utf-8')
    for token in ('test_*.py', 'test_*.js', '*_smoke.py', '*_smoke_test.py', '*.spec.js', 'full_interaction_audit.py', 'SymptoSense_Audit.html', 'package.json', 'ci.yml'):
        assert token in dockerignore


def test_release_metadata_matches_current_delivery():
    metrics = json.loads((ROOT / "release_metrics.json").read_text(encoding="utf-8"))
    revision = str(metrics.get("delivery_revision") or "")
    assert revision.startswith("V") and revision[1:].isdigit()
    assert f"SymptoSense Railway build profile: {revision}" in (ROOT / "Dockerfile").read_text(encoding="utf-8")


def test_localized_same_page_post_forms_are_allowed_without_opening_all_post_routes():
    web = source_bundle.webapp_text()
    assert 'localized_post_pages = {"verify-email", "forgot-password", "settings"}' in web
    assert 'subpath not in localized_post_pages' in web
    # Login/register deliberately post to their explicit non-localized actions.
    assert 'action="/login?next=__NEXT__"' in web
    assert 'action="/register?next=__NEXT__"' in web
