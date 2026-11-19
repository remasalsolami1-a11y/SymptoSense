import source_bundle
import best_effort


def test_returns_value_and_swallows_errors_without_leaking_details(caplog):
    assert best_effort.call(lambda a, b=1: a + b, 2, b=3) == 5
    caplog.set_level("WARNING", logger="symptosense.best_effort")

    def boom():
        raise RuntimeError("secret-user-data")
    assert best_effort.call(boom) is None
    assert "RuntimeError" in caplog.text and "secret-user-data" not in caplog.text


def test_webapp_no_longer_has_hand_rolled_audit_swallowing():
    import re
    from pathlib import Path
    src = source_bundle.webapp_text()
    assert not re.search(r"try:\s*platform_v2\.audit\([^\n]*\n\s*except Exception", src)


def test_failures_are_counted_for_system_health():
    import ops_metrics
    ops_metrics.reset()

    def audit():
        raise OSError("disk")

    def other():
        raise ValueError("x")
    assert best_effort.call(audit) is None and best_effort.call(other) is None
    counters = ops_metrics.snapshot()["counters"]
    assert counters.get("audit_log_failures_total") == 1 and counters.get("best_effort_failures_total") == 1
