"""data-ss-* actions: delegated, allow-listed, JSON arguments, no eval (real Chromium)."""
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
playwright = pytest.importorskip("playwright.sync_api")


def _chromium_ok():
    try:
        with playwright.sync_playwright() as p:
            p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None).close()
        return True
    except Exception:
        return False


PAGE = """<!doctype html><meta charset=utf-8><body>
<button id=a type=button data-ss-click="doSearch">a</button>
<button id=b type=button data-ss-click="dqAsk" data-ss-args='["x", 2, null, {"k":[1]}]'><span id=inner>b</span></button>
<select id=c data-ss-change="doSearch dqAsk" data-ss-args='["$value"]'><option value=v1>1</option><option value=v2>2</option></select>
<input id=d data-ss-keydown="doSearch" data-ss-key="Enter">
<div id=e style="padding:20px" data-ss-click="doSearch" data-ss-self><button id=e2 type=button>child</button></div>
<button id=f type=button data-ss-click="notAllowedFunction">f</button>
<button id=g type=button data-ss-click="doSearch" data-ss-args="not json">g</button>
<button id=h type=button onclick="doSearch('legacy')">h</button>
<script>window.calls=[];
window.doSearch=function(){calls.push(['doSearch'].concat([].slice.call(arguments)))};
window.dqAsk=function(){calls.push(['dqAsk'].concat([].slice.call(arguments)))};
window.notAllowedFunction=function(){calls.push(['BAD'])};</script>"""


@pytest.mark.skipif(not _chromium_ok(), reason="Chromium not available")
def test_data_actions_behave():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        pg = b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.set_content(PAGE)
        pg.add_script_tag(path=str(ROOT / "static" / "js" / "interaction-bridge.js"))
        pg.wait_for_timeout(200)
        calls = lambda: pg.evaluate("window.calls")
        pg.click("#a");                       assert calls()[-1] == ["doSearch"]
        pg.click("#inner");                   assert calls()[-1] == ["dqAsk", "x", 2, None, {"k": [1]}]      # child click reaches the button
        pg.select_option("#c", "v2");         assert calls()[-2:] == [["doSearch", "v2"], ["dqAsk", "v2"]]   # two functions, $value, in order
        n = len(calls())
        pg.press("#d", "a");                  assert len(calls()) == n                                      # wrong key: nothing
        pg.press("#d", "Enter");              assert calls()[-1] == ["doSearch"]
        n = len(calls())
        pg.click("#e2");                      assert len(calls()) == n                                      # data-ss-self ignores bubbled clicks
        pg.click("#e", position={"x": 2, "y": 2}); assert len(calls()) == n + 1
        n = len(calls())
        pg.click("#f");                       assert len(calls()) == n                                      # not allow-listed: refused
        pg.click("#g");                       assert len(calls()) == n                                      # bad JSON: refused, no page error
        pg.click("#h");                       assert calls()[-1] == ["doSearch", "legacy"]                  # legacy attributes still work
        pg.evaluate("""() => { const b = document.createElement('button'); b.id = 'z'; b.type = 'button';
            b.setAttribute('data-ss-click', 'doSearch'); b.setAttribute('data-ss-args', '["late"]'); document.body.appendChild(b); }""")
        pg.click("#z");                       assert calls()[-1] == ["doSearch", "late"]                    # added later: delegation, no rebinding
        assert not errors, errors
        b.close()
