#!/usr/bin/env python3
"""List or record clinician sign-off for content areas (see clinical_signoff.py)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import clinical_signoff as cs  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    st = sub.add_parser("check"); st.add_argument("--strict", action="store_true", help="fail while any area is still pending")
    for name in ("approve", "revoke"):
        p = sub.add_parser(name); p.add_argument("area")
        if name == "approve":
            p.add_argument("--reviewer", required=True); p.add_argument("--credentials", required=True)
            p.add_argument("--date", required=True); p.add_argument("--notes", default="")
    a = ap.parse_args(argv)
    data = cs.load(cs.PATH)
    areas = data["areas"]
    if a.cmd == "list":
        for aid, x in areas.items():
            print(("✔ " if cs.is_reviewed(x) else "… ") + aid + " — " + x["title_en"] + ((" — " + x["reviewer"] + ", " + x["date"]) if cs.is_reviewed(x) else ""))
        return 0
    if a.cmd == "check":
        problems = cs.validate(data)
        pending = [k for k, x in areas.items() if not cs.is_reviewed(x)]
        for pr in problems:
            print("ERROR:", pr)
        if pending:
            print(("PENDING (blocking):" if a.strict else "pending:"), ", ".join(pending))
        return 1 if problems or (a.strict and pending) else 0
    if a.area not in areas:
        print("unknown area; choose from:", ", ".join(areas)); return 2
    if a.cmd == "approve":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date):
            print("--date must be YYYY-MM-DD"); return 2
        areas[a.area].update(status="reviewed", reviewer=a.reviewer.strip(), credentials=a.credentials.strip(), date=a.date, notes=a.notes)
    else:
        areas[a.area].update(status="pending", reviewer=None, credentials=None, date=None)
    problems = cs.validate(data)
    if problems:
        print("\n".join(problems)); return 1
    cs.PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("updated", a.area)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
