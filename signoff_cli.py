#!/usr/bin/env python3
"""List or record clinician sign-off for content areas (see clinical_signoff.py)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import clinical_signoff as cs  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    st = sub.add_parser("check"); st.add_argument("--strict", action="store_true", help="fail while any area is still pending")
    # V292.1: start-review -> in_review, approve -> approved, reject -> rejected, revoke -> pending.
    for name in ("start-review", "approve", "reject", "revoke"):
        p = sub.add_parser(name); p.add_argument("area")
        if name != "revoke":
            p.add_argument("--reviewer", required=True)
            p.add_argument("--credentials", required=(name != "start-review"), default="")
            p.add_argument("--date", required=(name != "start-review"), default=None)
            p.add_argument("--organization", default="", help="the reviewer's hospital, clinic or body, as they state it")
            p.add_argument("--scope", default="", help="what exactly was reviewed, e.g. 'all red-flag questions, Arabic and English'")
            p.add_argument("--notes", default="")
    a = ap.parse_args(argv)
    data = cs.load(cs.PATH)
    areas = data["areas"]
    if a.cmd == "list":
        for aid, x in areas.items():
            print("[" + cs.state(x) + "] " + aid + " — " + x["title_en"] + ((" — " + x["reviewer"] + ", " + x["date"]) if cs.is_reviewed(x) else ""))
        return 0
    if a.cmd == "check":
        problems = cs.validate(data)
        pending = [k for k, x in areas.items() if cs.state(x) != "approved"]
        for pr in problems:
            print("ERROR:", pr)
        if pending:
            print(("PENDING (blocking):" if a.strict else "pending:"), ", ".join(pending))
        return 1 if problems or (a.strict and pending) else 0
    if a.area not in areas:
        print("unknown area; choose from:", ", ".join(areas)); return 2
    if a.cmd != "revoke":
        from datetime import date as _date
        if a.date is not None:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date):
                print("--date must be YYYY-MM-DD"); return 2
            try:
                when = _date.fromisoformat(a.date)
            except ValueError:
                print("--date is not a real date"); return 2
            if when > _date.today():
                print("--date cannot be in the future: record a review only after it happened"); return 2
        status = {"start-review": "in_review", "approve": "approved", "reject": "rejected"}[a.cmd]
        areas[a.area].update(status=status, reviewer=a.reviewer.strip(), credentials=(a.credentials or "").strip() or None,
                             date=a.date, organization=(a.organization or "").strip() or None,
                             scope=(a.scope or "").strip() or None, notes=a.notes)
    else:
        areas[a.area].update(status="pending", reviewer=None, credentials=None, date=None, organization=None)
    # V292: keep who approved or revoked each area and when (the area fields only hold the latest).
    from datetime import datetime, timezone
    areas[a.area].setdefault("history", []).append({
        "action": a.cmd, "reviewer": getattr(a, "reviewer", None), "credentials": getattr(a, "credentials", None) or None,
        "organization": getattr(a, "organization", None) or None, "scope": getattr(a, "scope", None) or None,
        "date": getattr(a, "date", None), "notes": getattr(a, "notes", "") or "",
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    problems = cs.validate(data)
    if problems:
        print("\n".join(problems)); return 1
    cs.PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("updated", a.area)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
