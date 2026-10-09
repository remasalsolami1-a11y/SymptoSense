"""chat_view.py builds the page; the chat behaviour lives in static/js/chat/*.js (loaded in a fixed order)."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import chat_view
import source_bundle

ROOT = Path(__file__).resolve().parent
JS = ROOT / "static" / "js" / "chat"
ORDER = list(source_bundle.CHAT_JS_ORDER)


def _page(lang):
    return chat_view.render_chat_page(lang=lang, page=lambda title, body: body, t=lambda k: k, json_for_script=lambda o, **kw: "null")


def test_chat_view_is_a_page_builder_not_a_script_container():
    src = (ROOT / "chat_view.py").read_text(encoding="utf-8")
    assert len(src.splitlines()) < 1200 and len(src.encode()) < 120_000
    inline = re.findall(r"<script>(.*?)</script>", src, re.S)
    assert len(inline) == 1 and inline[0].count("\n") < 20, "only the page-data bootstrap may stay inline"
    assert "function startChat" not in src


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_scripts_are_loaded_in_the_fixed_order_after_the_data_bootstrap(lang):
    html = _page(lang)
    tags = re.findall(r'<script src="/static/js/chat/([a-z-]+)\.js\?v=__ASSET_VERSION__"></script>', html)
    assert tags == ORDER
    assert html.index("const DEMO_RESULT") < html.index("/static/js/chat/chat-core.js")
    assert ORDER[-1] == "chat-boot", "event wiring + startChat() must load last"


def test_every_script_exists_and_is_valid_javascript_on_its_own():
    node = shutil.which("node")
    for name in ORDER:
        p = JS / (name + ".js")
        assert p.is_file() and p.stat().st_size > 200, name
        if node:
            r = subprocess.run([node, "--check", str(p)], capture_output=True, text=True)
            assert r.returncode == 0, name + ": " + r.stderr[:300]


def test_no_top_level_name_is_declared_twice_and_boot_holds_all_load_time_wiring():
    seen = {}
    for name in ORDER:
        text = (JS / (name + ".js")).read_text(encoding="utf-8")
        for m in re.finditer(r"^    (?:async )?function ([A-Za-z0-9_$]+)\(|^    (?:const|let|var) ([A-Za-z0-9_$]+)\b", text, re.M):
            ident = m.group(1) or m.group(2)
            assert ident not in seen, "%s declared in both %s and %s" % (ident, seen[ident], name)
            seen[ident] = name
    boot = (JS / "chat-boot.js").read_text(encoding="utf-8")
    assert boot.rstrip().endswith("startChat();")
    for must in ("addEventListener('click', submitText)", "syncSpeakerButton();"):
        assert must in boot
    for name in ORDER[:-1]:
        text = (JS / (name + ".js")).read_text(encoding="utf-8")
        assert not re.search(r"^    startChat\(\);", text, re.M), name + " must not start the chat at load time"


def test_data_placeholders_are_defined_by_the_bootstrap_not_the_scripts():
    for name in ORDER:
        text = (JS / (name + ".js")).read_text(encoding="utf-8")
        assert not re.search(r"\b__(?:T|LANG|SYMS|DURS|SEVS|CONDS|REL|DEMO_RESULT|ME)__\b", text), name
        assert not re.search(r"^    const (?:T|LANG|SYMS|DURS|SEVS|CONDS|REL|DEMO_RESULT) =", text, re.M), name


def test_scripts_are_served_with_the_page(tmp_path):
    import webapp
    c = webapp.app.test_client()
    for name in ORDER:
        r = c.get("/static/js/chat/%s.js" % name)
        assert r.status_code == 200 and b"SymptoSense chat" in r.data[:200], name
