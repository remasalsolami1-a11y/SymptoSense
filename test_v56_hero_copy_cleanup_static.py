from pathlib import Path

import source_bundle
WEB = source_bundle.webapp_text()


def test_new_single_hero_lead_is_present():
    assert 'مساعد صحي ذكي يساعدك على فهم أعراضك وسياقها، ويقدّم لك إرشادًا أوليًا واضحًا لتحديد الخطوة المناسبة دون تشخيص طبي.' in WEB
    assert 'معلومات صحية موثوقة تساعدك على اتخاذ قرار أوضح، دون تشخيص طبي.' not in WEB


def test_new_safety_link_copy_and_class():
    assert 'كيف يحافظ SymptoSense على سلامتك؟' in WEB
    assert 'class="ss-trust-safety-link"' in WEB


def test_trust_copy_matches_requested_wording():
    assert '"__TRUST_NODIAG__": bi("دون تشخيص طبي"' in WEB
    assert '<i class="ss-trust-ic">✓</i>__TRUST_INFO__' in WEB


def test_desktop_cta_hierarchy():
    assert 'body.ss-home-page .ss-hero-primary{grid-column:1/-1!important;width:100%!important}' in WEB
    assert 'grid-template-columns:minmax(0,1fr) minmax(0,.82fr)!important' in WEB


def test_mobile_stays_responsive():
    assert '@media (max-width:767px)' in WEB
    assert 'body.ss-home-page .ss-home-hero{\n    grid-template-columns:1fr!important;' in WEB
    assert 'body.ss-home-page .ss-hero-actions{grid-template-columns:1fr!important}' in WEB
