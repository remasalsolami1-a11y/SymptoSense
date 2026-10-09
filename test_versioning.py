"""One version everywhere: the VERSION file is the source; static copies must agree with it."""
from pathlib import Path

import release_candidate
import research_study
import versioning

ROOT = Path(__file__).resolve().parent


def _t(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_runtime_modules_use_the_version_file():
    assert release_candidate.APP_VERSION == versioning.APP_VERSION == (ROOT / "VERSION").read_text().strip()
    assert research_study.APP_VERSION == versioning.APP_VERSION
    assert release_candidate.RC_ID == versioning.RC_ID


def test_static_copies_agree_with_the_version_file():
    assert "const CACHE_NAME = '%s'" % versioning.SW_CACHE in _t("service-worker.js")
    env = _t(".env.example")
    assert "APP_VERSION=" + versioning.APP_VERSION in env and "RELEASE_CANDIDATE_ID=" + versioning.RC_ID in env
    docker = _t("Dockerfile")
    assert "build profile: " + versioning.REVISION in docker and "SymptoSense " + versioning.REVISION + " production" in docker
    assert '"delivery_revision": "%s"' % versioning.REVISION in _t("release_metrics.json")


def test_old_hardcoded_version_is_gone_from_runtime_sources():
    for name in ("release_candidate.py", "research_study.py"):
        assert "247.0.0" not in _t(name)


def test_production_gate_blocks_pending_signoff_unless_explicitly_overridden(monkeypatch, capsys):
    import release_check
    monkeypatch.setattr(release_check, "FAILURES", [])
    monkeypatch.delenv("RELEASE_TARGET", raising=False)
    release_check.check_clinical_signoff_gate()
    assert release_check.FAILURES == []                                   # development stays green
    monkeypatch.setenv("RELEASE_TARGET", "production")
    release_check.check_clinical_signoff_gate()
    assert release_check.FAILURES and "sign-off pending" in release_check.FAILURES[0]
    monkeypatch.setattr(release_check, "FAILURES", [])
    monkeypatch.setenv("ALLOW_UNSIGNED_CLINICAL", "1")
    release_check.check_clinical_signoff_gate()
    assert release_check.FAILURES == [] and "OVERRIDDEN" in capsys.readouterr().out


def test_dockerfile_enforces_the_signoff_gate():
    docker = _t("Dockerfile")
    assert "tools/signoff.py check --strict" in docker and "ARG ALLOW_UNSIGNED_CLINICAL=0" in docker
