"""V273: one brand palette (blue #1F6FAE, navy #123B70, muted #566A7D) and two font stacks (Arabic: Tajawal, Latin: Poppins)."""
import glob
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RETIRED = {'#1565c0', '#0d66b5', '#155d8b', '#225c86', '#1f6fd0', '#087fc4', '#0f5fb0', '#2b7ca8',
           '#163b5c', '#0b3775', '#0f2f63', '#173c63', '#163f66', '#173d63', '#0b477e', '#244c6c', '#24445f',
           '#5f7285', '#526d84', '#637a92', '#4a6580', '#0c3b70', '#1d5f99', '#147ec7', '#2e85c5', '#39708f'}
AR = "'Tajawal','Segoe UI',Tahoma,sans-serif"
LAT = "'Poppins','Tajawal','Segoe UI',sans-serif"


def _sources():
    files = glob.glob(str(ROOT / 'inline_assets' / '*.css')) + glob.glob(str(ROOT / 'static' / 'css' / '*.css')) + [str(ROOT / 'polish_css_v249.py'), str(ROOT / 'webapp.py')] + glob.glob(str(ROOT / 'pagelib' / '*.py'))
    return files


def _strip_dark_blocks(t):
    out, i = [], 0
    for m in re.finditer(r'@media\s*\(\s*prefers-color-scheme\s*:\s*dark\s*\)\s*\{', t):
        if m.start() < i:
            continue
        d, j = 1, m.end()
        while j < len(t) and d:
            d += (t[j] == '{') - (t[j] == '}')
            j += 1
        out.append(t[i:m.start()])
        i = j
    out.append(t[i:])
    return ''.join(out)


def test_retired_near_duplicate_colours_are_gone_from_light_theme_css():
    left = {}
    for f in _sources():
        t = _strip_dark_blocks(Path(f).read_text(encoding='utf-8', errors='ignore'))
        for h in re.findall(r'#[0-9A-Fa-f]{6}\b', t):
            if h.lower() in RETIRED:
                left.setdefault(Path(f).name, set()).add(h.lower())
    assert not left, left


def test_brand_tokens_are_defined_once_in_the_shared_variables():
    base = (ROOT / 'inline_assets' / 'BASE_CSS.css').read_text(encoding='utf-8')
    v2 = (ROOT / 'inline_assets' / 'V2_CSS.css').read_text(encoding='utf-8')
    assert '--primary: #1565c0' not in base.lower() and '--primary-dark: #123b70' in base.lower()
    assert '--v2-blue:#1f6fae' in v2.lower() and '--v2-blue-dark:#123b70' in v2.lower()


def test_only_two_font_stacks_are_used_in_site_css():
    allowed = {re.sub(r'[\s"\']', '', s) for s in (AR, LAT)}
    bad = {}
    for f in _sources():
        t = Path(f).read_text(encoding='utf-8', errors='ignore')
        for m in re.finditer(r"font-family\s*:\s*([^;}{<]+)", t):
            s = m.group(1).replace('!important', '').strip()
            first = s.split(',')[0].strip().strip('"\'').lower()
            if first in ('poppins', 'tajawal', 'segoe ui') and re.sub(r'[\s"\']', '', s) not in allowed:
                bad.setdefault(Path(f).name, set()).add(s[:60])
    assert not bad, bad
