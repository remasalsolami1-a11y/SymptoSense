import source_bundle
from pathlib import Path

TEXT=source_bundle.webapp_text()

def _welcome_block():
    s=TEXT.index('def welcome_page():'); e=TEXT.index('\ndef home_page():',s); return TEXT[s:e]

def test_contact_route_exists_and_landing_points_to_it():
    assert '@app.route("/contact")' in TEXT
    assert 'def contact_page():' in TEXT


def test_landing_about_and_long_disclaimer_stay_removed():
    b=_welcome_block()
    assert 'href="/about"' not in b
    assert 'SymptoSense يقدم معلومات وإرشادًا أوليًا ولا يشخّص الحالات الطبية.' not in b

def test_small_phone_footer_text_remains_readable():
    b=_welcome_block()
    assert 'body.ss-welcome-page .first-lang-legal a{' in b
    assert 'min-height:44px!important' in b
    assert 'font-size:14px!important' in b
