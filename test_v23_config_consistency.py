import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_medication_email_env_matches_runtime_code():
    env = _read(".env.example")
    runtime = _read("medication_email.py")
    assert "BREVO_API_KEY=" in env
    assert "RESEND_API_KEY=" in env
    assert "VAPID_PUBLIC_KEY=" not in env
    assert 'BREVO_API_KEY' in runtime
    assert 'RESEND_API_KEY' in runtime


def test_sentry_is_documented_and_opt_in():
    env = _read(".env.example")
    app = source_bundle.webapp_text()
    deploy = _read("DEPLOY_GUIDE_AR.md")
    assert "SENTRY_DSN=" in env
    assert 'os.environ.get("SENTRY_DSN"' in app
    assert "send_default_pii=False" in app
    assert "`SENTRY_DSN`" in deploy


def test_primary_auth_deployment_docs_use_brevo():
    deploy = _read("DEPLOY_GUIDE_AR.md")
    auth = _read("AUTHENTICATION_SETUP.md")
    assert "`BREVO_API_KEY`" in deploy
    assert "`BREVO_FROM_EMAIL`" in deploy
    assert "BREVO_API_KEY=<BREVO_API_KEY>" in auth
    assert "هو الإعداد الموصى به لهذه النسخة على Railway" in auth


def test_competition_readiness_is_current_release():
    doc = _read("COMPETITION_READINESS.md")
    assert "Updated: 15 September 2026" in doc
    assert "100 recognized symptom concepts" in doc
    assert "41 documented conditions" in doc
