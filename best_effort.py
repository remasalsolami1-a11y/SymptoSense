"""Best-effort wrapper for NON-CRITICAL side effects (audit trail, usage counters, login logs).

One reviewed place that deliberately fails open: if writing an audit line or a usage counter fails, the user's
request must not fail with it. But the failure is never silent: it is logged at WARNING (exception type only, no
personal data) and counted in ops_metrics (``audit_log_failures_total`` for audit/login/security writes,
``best_effort_failures_total`` for the rest) so System Health shows it. Never use this for safety decisions, medical
logic or consent; those paths stay fail-closed (see ``SafetyCheckError``).
"""
import logging

_LOG = logging.getLogger("symptosense.best_effort")
_AUDIT_NAMES = {"audit", "log_login", "record_login_attempt", "record"}


def call(fn, *args, **kwargs):
    """Run ``fn(*args, **kwargs)``; on any error warn + count, and return None."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # the single sanctioned broad catch for non-critical side effects
        name = getattr(fn, "__name__", "operation")
        counter = "audit_log_failures_total" if name in _AUDIT_NAMES else "best_effort_failures_total"
        _LOG.warning("Non-critical operation failed: %s (%s)", name, type(exc).__name__)
        try:
            import ops_metrics
            ops_metrics.incr(counter)
        except (ImportError, AttributeError, TypeError):
            pass
        return None
