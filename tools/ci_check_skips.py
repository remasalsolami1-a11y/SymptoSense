#!/usr/bin/env python3
"""Fail CI when tests were skipped without a reason we accept, and print the real passed / failed / skipped numbers.

Reads pytest JUnit XML files (--junitxml). Rules:
  * any failure or error                        -> fail
  * a skipped test in a --critical file         -> fail   (e.g. PostgreSQL / Chromium tests must RUN in their CI job)
  * more skipped tests than --budget            -> fail   (each allowed skip is a documented one, see conftest.SKIP_REASONS)
  * fewer than --min-tests passed               -> fail   (guards against "nothing ran, so nothing failed")
xfail is counted separately (known, documented gaps) and never hides a failure.
"""
import argparse
import fnmatch
import os
import sys
import xml.etree.ElementTree as ET  # our own CI output, not network data
from pathlib import Path


def collect(paths):
    files = []
    for p in paths:
        p = Path(p)
        files += sorted(p.glob("*.xml")) if p.is_dir() else [p]
    return files


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--budget", type=int, default=0, help="skipped tests allowed in total")
    ap.add_argument("--critical", nargs="*", default=[], help="file globs whose tests must never be skipped")
    ap.add_argument("--min-tests", type=int, default=1, help="minimum number of passed tests")
    a = ap.parse_args(argv)
    passed = failed = skipped = xfailed = 0
    skips, crit_skips, bad = [], [], []
    for xml in collect(a.paths):
        for case in ET.parse(xml).getroot().iter("testcase"):
            name = "%s::%s" % ((case.get("file") or case.get("classname", "").replace(".", "/") + ".py"), case.get("name"))
            module = (case.get("classname") or "").split(".")[0] + ".py"
            sk = case.find("skipped")
            if case.find("failure") is not None or case.find("error") is not None:
                failed += 1; bad.append(name)
            elif sk is not None:
                if "xfail" in (sk.get("type") or ""):
                    xfailed += 1
                else:
                    skipped += 1; skips.append((name, sk.get("message") or ""))
                    if any(fnmatch.fnmatch(module, g) for g in a.critical):
                        crit_skips.append((name, sk.get("message") or ""))
            else:
                passed += 1
    lines = ["| passed | failed | skipped | xfail |", "|---|---|---|---|", "| %d | %d | %d | %d |" % (passed, failed, skipped, xfailed)]
    for n, r in skips:
        lines.append("- skipped: `%s` - %s" % (n, r))
    for n in bad:
        lines.append("- FAILED: `%s`" % n)
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    problems = []
    if failed:
        problems.append("%d failed/errored test(s)" % failed)
    if crit_skips:
        problems.append("critical tests were skipped: %s" % ", ".join(n for n, _ in crit_skips))
    if skipped > a.budget:
        problems.append("%d skipped test(s), budget is %d" % (skipped, a.budget))
    if passed < a.min_tests:
        problems.append("only %d test(s) passed, expected at least %d" % (passed, a.min_tests))
    for p in problems:
        print("::error::" + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
