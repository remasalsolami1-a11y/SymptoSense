import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEBAPP = source_bundle.webapp_text()


def test_consent_checkboxes_override_global_input_sizing_and_background():
    assert 'appearance:auto!important' in WEBAPP
    assert '-webkit-appearance:checkbox!important' in WEBAPP
    assert 'width:22px!important' in WEBAPP
    assert 'height:22px!important' in WEBAPP
    assert 'min-height:22px!important' in WEBAPP
    assert 'padding:0!important' in WEBAPP
    assert 'background:transparent!important' in WEBAPP
    assert 'accent-color:var(--v2-blue)' in WEBAPP


def test_consent_labels_are_explicitly_bound_to_inputs():
    for cid in ('serviceConsent', 'analyticsConsent', 'researchConsent'):
        assert f'label for="{cid}"' in WEBAPP
        assert f'id="{cid}"' in WEBAPP


def test_consent_fields_have_stable_names():
    assert 'name="service_usage"' in WEBAPP
    assert 'name="analytics_research"' in WEBAPP
    assert 'name="research_participation"' in WEBAPP
