import source_bundle
from pathlib import Path
ROOT=Path(__file__).resolve().parent
WEB=source_bundle.webapp_text()
CSS=(ROOT/'static/css/app-shell-v111.css').read_text(encoding='utf-8')

def test_mobile_hero_never_stacks():
    for source in (WEB,CSS):
        assert 'V126 — Mobile landing hero' in source
        block=source[source.rfind('/* V126 — Mobile landing hero'): ]
        assert 'body.ss-home-page .ss-home-hero' in block
        assert 'grid-template-columns:minmax(0,1.08fr) minmax(0,.92fr)!important' in block
        assert 'grid-template-columns:minmax(0,1.12fr) minmax(0,.88fr)!important' in block
        assert 'body.ss-home-page .ss-hero-demo{grid-column:2!important;grid-row:1!important' in block
        assert 'body.ss-home-page .ss-hero-copy{grid-column:1!important;grid-row:1!important' in block

def test_narrow_phone_simplifies_instead_of_stacking():
    block=CSS[CSS.rfind('/* V126 — Mobile landing hero'): ]
    assert '@media (max-width:389px)' in block
    assert 'body.ss-home-page .ss-hero-desc{display:none!important}' in block
    narrow=block[block.index('@media (max-width:389px)'):]
    hero=narrow[narrow.index('body.ss-home-page .ss-home-hero'):narrow.index('body.ss-home-page .ss-hero-copy')]
    assert 'grid-template-columns:1fr!important' not in hero
