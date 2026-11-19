from pathlib import Path

import source_bundle
WEB = source_bundle.webapp_text()


def test_legacy_symptoms_route_canonicalizes_to_chat():
    assert '"/symptoms": "/chat"' in WEB
    assert '"symptoms": ("/chat", "")' in WEB


def test_compact_consent_action_is_visible_without_scroll_discovery():
    assert 'const show=compact && !originalVisible;' in WEB
    assert 'window.scrollY > 48 && !originalVisible' not in WEB
    assert 'id="consentStickyBar"' in WEB
    assert 'id="consentStickySubmit"' in WEB


def test_mobile_consent_reserves_space_for_sticky_action():
    assert 'padding-bottom:calc(var(--bnav-h,64px) + var(--safe-bottom,0px) + 104px)' in WEB


def test_blood_upload_remains_pdf_only_and_explicit_consent_is_not_defaulted_for_new_users():
    assert 'accept="application/pdf,.pdf"' in WEB
    assert "blood_consent_checked = \"\"" in WEB
    assert "db.has_blood_collection_consent" in WEB
    assert "const isPdf=String(f.type||'').toLowerCase()==='application/pdf'||/[.]pdf$/i.test(f.name||'');" in WEB


def test_safeid_still_has_contact_fields_and_save_action():
    assert 'id="sidSave"' in WEB
    assert 'Emergency contact name' in WEB
    assert '/api/safeid/save' in WEB
