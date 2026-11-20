"""Public test-count figures that never show a misleading zero.

Test files are excluded from the production image, so counting them at runtime
yields 0 there. Fall back to the release_metrics.json number shipped with the
release, and return None when no real figure exists (callers then hide it).
"""
import json
import os


def figure(snapshot_quality):
    q = snapshot_quality or {}
    checks = int(q.get("automated_checks") or 0)
    if checks > 0:
        return {"n": checks, "kind": "checks", "files": int(q.get("test_files") or 0)}
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "release_metrics.json")
        with open(path, "r", encoding="utf-8") as fh:
            files = int(json.load(fh).get("test_files") or 0)
    except (OSError, ValueError, TypeError):
        files = 0
    if files > 0:
        return {"n": files, "kind": "files", "files": files}
    return None


def kpi(snapshot_quality, ar):
    f = figure(snapshot_quality)
    if not f:
        return "—", "فحوص آلية تُشغَّل قبل كل إصدار" if ar else "automated checks run before each release"
    if f["kind"] == "checks":
        return str(f["n"]), "اختبار/فحص آلي" if ar else "automated checks"
    return str(f["n"]), "ملف اختبار آلي" if ar else "automated test files"


def sentence(snapshot_quality, ar):
    f = figure(snapshot_quality)
    if not f:
        return ("تُشغَّل فحوص واختبارات آلية قبل كل إصدار لتقليل الانحدارات." if ar
                else "Automated checks run before each release to catch regressions early.")
    if f["kind"] == "checks":
        return (("توجد %d فحصًا/اختبارًا آليًا عبر %d ملفًا، لتقليل الانحدارات واكتشاف المشاكل مبكرًا." % (f["n"], f["files"])) if ar
                else "There are %d automated checks across %d test file(s), helping catch regressions early." % (f["n"], f["files"]))
    return (("تُشغَّل %d ملف اختبار آلي قبل كل إصدار لتقليل الانحدارات." % f["n"]) if ar
            else "%d automated test files run before each release to catch regressions." % f["n"])
