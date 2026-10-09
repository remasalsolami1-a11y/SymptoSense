"""V270: statistics + reference organisations live in ONE box; 'how it works' follows it."""
import re

import source_bundle

WEB = source_bundle.webapp_text()


def _home():
    s = WEB.index('def home_page():')
    return WEB[s:WEB.index('\n    </main>', s)]


def _box(h):
    a = h.index('<section class="ss-strength ss-knowledge"')
    return h[a:h.index('</section>', a)]


def test_one_box_with_mandatory_order():
    box = _box(_home())
    order = ['id="strengthTitle"', '__STRENGTH_SUB__', 'ss-strength-grid', 'class="ss-knowledge-sep"',
             'id="sourcesTitle"', 'ss-sources-logos', 'class="ss-source-more" href="/sources"']
    pos = [box.index(t) for t in order]
    assert pos == sorted(pos), pos
    assert box.count('class="ss-strength-stat') == 6
    assert box.count('<section') == 1


def test_old_standalone_sources_container_is_gone_and_how_comes_after():
    h = _home()
    assert 'ss-sources-strip' not in h and 'ss-sources-copy' not in h
    assert h.index('class="ss-strength ss-knowledge"') < h.index('<section class="ss-how"')
    assert h.count('id="sourcesTitle"') == 1 and h.count('class="ss-how"') == 1
    # the how-it-works block must not sit between the statistics and the sources
    box = _box(h)
    assert 'ss-how' not in box


def test_all_reference_badges_and_all_sources_link_kept():
    box = _box(_home())
    for t in ('__MOH__', 'WHO', 'NHS', 'CDC', 'NICE', 'NIDCR', 'NIAMS', 'AHA'):
        assert t in box, t
    assert '__ALL_SOURCES__' in box


def test_stats_are_still_bound_to_the_knowledge_snapshot_not_hardcoded():
    for k in ('verified_sources', 'conditions', 'symptoms', 'searchable_symptoms', 'red_flags'):
        assert 'strength.get("%s"' % k in WEB, k
    box = _box(_home())
    assert not re.search(r'<strong>\d', box)


def test_unified_title_and_reference_heading():
    assert 'معرفة صحية تستند إلى مصادر موثوقة' in WEB and 'من الجهات المرجعية' in WEB


def test_css_has_vertical_single_column_layout_for_the_box():
    css = WEB[WEB.index('.ss-knowledge-sep{'):][:700]
    assert 'height:1px' in css and 'justify-content:center' in css and 'min-height:44px' in css
    assert '.ss-sources-strip{display:grid' not in WEB
