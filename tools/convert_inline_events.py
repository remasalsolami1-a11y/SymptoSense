#!/usr/bin/env python3
"""Rewrite static inline on* handlers into data-ss-* actions (see static/js/interaction-bridge.js).

    python tools/convert_inline_events.py FILE... [--apply]

Only literal, fully static handlers are converted (string/number/null/true/false/this/this.value/event arguments).
Anything built from variables ('+x+', ${x}, {{ }}) is reported and left for a manual rewrite."""
import html
import json
import re
import sys
from pathlib import Path

EVENTS = {"onclick": "click", "onchange": "change", "oninput": "input", "onkeydown": "keydown", "onsubmit": "submit"}
TAG = re.compile(r"<[A-Za-z][^<>]*>")
ATTR = re.compile(r"""\s(on(?:click|change|input|keydown|submit))=(["'])(.*?)\2""", re.S)


def split_top(text, sep):
    parts, depth, quote, esc, start = [], 0, "", False, 0
    for i, ch in enumerate(text):
        if quote:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == quote: quote = ""
            continue
        if ch in "\"'": quote = ch
        elif ch in "([{": depth += 1
        elif ch in ")]}": depth -= 1
        elif ch == sep and depth == 0:
            parts.append(text[start:i].strip()); start = i + 1
    parts.append(text[start:].strip())
    return [p for p in parts if p]


def arg(token):
    t = token.strip()
    if t == "this": return "$this"
    if t == "this.value": return "$value"
    if t == "event": return "$event"
    if t in ("true", "false", "null"): return {"true": True, "false": False, "null": None}[t]
    if re.fullmatch(r"-?(?:\d+\.?\d*|\.\d+)", t): return float(t) if "." in t else int(t)
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        inner = t[1:-1]
        if "\\" in inner: raise ValueError("escape")
        return inner
    raise ValueError("arg " + t)


def convert_body(body):
    """-> (names, args, multi, key, selfonly) or raises ValueError."""
    code = html.unescape(body).strip()
    if re.search(r"\$\{|\{\{|\{%|'\s*\+|\"\s*\+|\+\s*['\"]", code): raise ValueError("dynamic")
    key = selfonly = False
    m = re.match(r"^if\s*\(\s*event\.key\s*===?\s*(['\"])Enter\1\s*\)\s*(.+)$", code, re.S)
    if m: key, code = "Enter", m.group(2).strip()
    m = re.match(r"^if\s*\(\s*event\.target\s*===\s*this\s*\)\s*(.+)$", code, re.S)
    if m: selfonly, code = True, m.group(1).strip()
    names, arglists = [], []
    for st in split_top(code, ";"):
        c = re.fullmatch(r"([A-Za-z_$][\w$]*)\s*\((.*)\)", st, re.S)
        if not c: raise ValueError("stmt " + st[:30])
        names.append(c.group(1))
        raw = c.group(2).strip()
        arglists.append([arg(x) for x in split_top(raw, ",")] if raw else [])
    if len(names) == 1:
        return names, arglists[0], False, key, selfonly
    if not any(arglists):
        return names, [], False, key, selfonly
    return names, arglists, True, key, selfonly          # several calls with arguments: one list per call (never share)


def esc_attr(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("&", "&amp;").replace('"', "&quot;")


def convert_tag(tag, report, where):
    found = list(ATTR.finditer(tag))
    if not found: return tag
    if len({EVENTS[m.group(1)] for m in found}) != len(found):
        report.append((where, "two handlers of one type", tag[:90])); return tag
    out, extra, args_used = tag, [], False
    for m in found:
        try:
            names, args, multi, key, selfonly = convert_body(m.group(3))
        except ValueError as exc:
            report.append((where, str(exc), m.group(0).strip()[:100])); continue
        if args and args_used:
            report.append((where, "two argument lists on one element", tag[:90])); continue
        etype = "keydown" if key else EVENTS[m.group(1)]
        if key and m.group(1) != "onkeydown":
            report.append((where, "Enter guard on non-keydown", m.group(0)[:80])); continue
        new = ' data-ss-%s="%s"' % (etype, " ".join(names))
        if key: new += ' data-ss-key="%s"' % key
        if selfonly: new += " data-ss-self"
        if multi: new += " data-ss-multi"
        if args:
            new += ' data-ss-args="%s"' % esc_attr(args); args_used = True
        out = out.replace(m.group(0), new, 1)
    return out


def main(argv):
    apply = "--apply" in argv
    files = [Path(a) for a in argv if not a.startswith("--")]
    report, total = [], 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        before = len(ATTR.findall(text))
        new = TAG.sub(lambda m: convert_tag(m.group(0), report, f.name), text)
        after = len(ATTR.findall(new))
        total += before - after
        print("%-28s %3d -> %3d" % (f, before, after))
        if apply and new != text: f.write_text(new, encoding="utf-8")
    for r in report: print("  LEFT", r)
    print("converted", total, "(applied)" if apply else "(dry run)")


if __name__ == "__main__":
    main(sys.argv[1:])
