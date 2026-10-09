import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEBAPP = source_bundle.webapp_text()


def test_localized_contact_is_registered():
    assert '"contact": "contact"' in WEBAPP
    assert '@app.route("/contact")' in WEBAPP
    assert 'def contact():' in WEBAPP


def test_contact_page_renderer_still_exists():
    assert 'def contact_page():' in WEBAPP
