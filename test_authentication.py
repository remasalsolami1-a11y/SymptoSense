"""Integration tests for the SymptoSense account lifecycle.

The mail transport is replaced with an in-memory capture. Token creation,
hashing, expiry, single use, sessions, redirects, RBAC, and rendered UI all run
against the real application and a temporary SQLite database.
"""
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

_TEMP = tempfile.TemporaryDirectory(prefix="symptosense-auth-tests-")
os.environ.pop("DATABASE_URL", None)
os.environ["DB_PATH"] = str(Path(_TEMP.name) / "auth-tests.sqlite3")
os.environ["WEB_SECRET"] = "test-only-stable-secret-with-more-than-32-characters"
os.environ["SITE_URL"] = "http://localhost"
os.environ["SESSION_COOKIE_SECURE"] = "0"
os.environ["RESEND_API_KEY"] = "re_test_not_sent"
os.environ["RESEND_FROM"] = "SymptoSense <noreply@verified.test>"
os.environ["ADMIN_AUTH_DEBUG"] = "0"

import db  # noqa: E402
import platform_v2  # noqa: E402
import medical_knowledge  # noqa: E402
import privacy_features  # noqa: E402
import advanced_features  # noqa: E402
import admin_operational  # noqa: E402
import medication_push  # noqa: E402
import webapp  # noqa: E402


def _csrf(html):
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if not match:
        raise AssertionError("CSRF field missing")
    return match.group(1)


def _first_auth_link(html, path_prefix):
    for href in re.findall(r'href="([^"]+)"', html):
        parsed = urlparse(href)
        if parsed.path.startswith(path_prefix):
            return parsed.path
    raise AssertionError("Auth link missing: %s" % path_prefix)


class AuthenticationIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        webapp.app.config.update(TESTING=True)
        db.init_db()
        for module in (
            platform_v2,
            medical_knowledge,
            privacy_features,
            advanced_features,
            admin_operational,
            medication_push,
        ):
            module.init_schema()

    def setUp(self):
        self.sent = []

        def capture_email(email, subject, html, category="auth"):
            self.sent.append({
                "email": email,
                "subject": subject,
                "html": html,
                "category": category,
            })
            return True, None

        self.original_sender = webapp._send_auth_email
        webapp._send_auth_email = capture_email

    def tearDown(self):
        webapp._send_auth_email = self.original_sender

    def client(self, lang="en"):
        client = webapp.app.test_client()
        client.set_cookie("lang", lang, domain="localhost")
        return client

    def create_verified_user(self, email, password, name="Existing User", role="user"):
        if email == db.OWNER_ADMIN_EMAIL:
            conn = db._conn()
            try:
                cursor = conn.cursor()
                now = datetime.now(timezone.utc).isoformat()
                cursor.execute(
                    "INSERT INTO ss_users (email,name,password_hash,role,email_verified,email_verified_at,created_at,status) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (email, name, db._hash_password(password), role, 1, now, now, "active"),
                )
                conn.commit()
                return int(cursor.lastrowid)
            finally:
                conn.close()
        user_id, error = db.create_ss_user(email, name, password)
        self.assertIsNone(error)
        conn = db._conn()
        try:
            conn.execute(
                "UPDATE ss_users SET email_verified=1,email_verified_at=?,role=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), role, int(user_id)),
            )
            conn.commit()
        finally:
            conn.close()
        return int(user_id)

    def test_auth_email_templates_are_bilingual_responsive_and_safe(self):
        production_origin = "https://symptosense-production-b2e5.up.railway.app"

        with mock.patch.object(webapp, "_site_url", return_value=production_origin), \
                mock.patch.object(
                    platform_v2,
                    "create_email_verification_code",
                    return_value=("opaque-verification-value", "123456", "arabic@example.test", None),
                ):
            ok, error = webapp._issue_verification_email(42, "ar")
        self.assertTrue(ok)
        self.assertIsNone(error)
        verification = self.sent[-1]
        verification_url = production_origin + "/verify-email/opaque-verification-value"
        self.assertEqual(verification["subject"], "تأكيد بريدك الإلكتروني — SymptoSense")
        self.assertIn('<html lang="ar" dir="rtl">', verification["html"])
        self.assertIn("تأكيد البريد الإلكتروني", verification["html"])
        self.assertIn("123456", verification["html"])
        self.assertEqual(verification["html"].count(verification_url), 3)
        self.assertNotIn("localhost", verification["html"])
        self.assertNotIn("<script", verification["html"].lower())

        reset_url = production_origin + "/reset-password/opaque-reset-value"
        ok, error = webapp._send_password_reset_email(
            "english@example.test", reset_url, "en"
        )
        self.assertTrue(ok)
        self.assertIsNone(error)
        reset = self.sent[-1]
        self.assertEqual(reset["subject"], "Reset your password — SymptoSense")
        self.assertIn('<html lang="en" dir="ltr">', reset["html"])
        self.assertIn("Reset Password", reset["html"])
        self.assertEqual(reset["html"].count(reset_url), 3)
        self.assertNotIn("localhost", reset["html"])
        self.assertNotIn("<script", reset["html"].lower())

        combined = (verification["html"] + reset["html"]).lower()
        for forbidden in (
            "password_hash", "api_key", "session_token", "user_id",
            "medical_history", "database id", "authorization:",
        ):
            self.assertNotIn(forbidden, combined)

    def test_six_digit_verification_code_is_hashed_single_use_and_expires(self):
        user_id, error = db.create_ss_user("otp@example.test", "OTP User", "StrongPass123!")
        self.assertIsNone(error)
        token, code, email, reason = platform_v2.create_email_verification_code(user_id)
        self.assertIsNone(reason)
        self.assertEqual(email, "otp@example.test")
        self.assertRegex(code, r"^\d{6}$")
        conn = db._conn()
        try:
            stored = conn.execute(
                "SELECT code_hash FROM ss_email_verifications WHERE user_id=? ORDER BY id DESC LIMIT 1",
                (user_id,),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertNotEqual(stored, code)
        self.assertEqual(platform_v2.consume_email_verification_code(user_id, "00000")[1], "invalid")
        verified_uid, status = platform_v2.consume_email_verification_code(user_id, code)
        self.assertEqual((verified_uid, status), (user_id, "verified"))
        self.assertEqual(platform_v2.consume_email_verification_code(user_id, code)[1], "used")
        self.assertTrue(db.get_ss_user(user_id)["email_verified"])

    def test_complete_user_lifecycle_and_rbac(self):
        client = self.client("en")
        email = "new-auth-user@example.test"
        old_password = "CorrectHorse1!"
        new_password = "CorrectHorse2!"

        # New account: CSRF is required, the account starts unverified, and a
        # real token is created while transport is captured in-memory.
        register = client.get("/register")
        self.assertEqual(register.status_code, 200)
        token = _csrf(register.get_data(as_text=True))
        blocked = client.post("/register", data={
            "name": "New User", "email": "csrf-blocked@example.test",
            "password": old_password, "confirm": old_password,
            "accept_terms": "on", "csrf_token": "invalid",
        })
        self.assertEqual(blocked.status_code, 200)
        self.assertIsNone(db.get_ss_user_by_email("csrf-blocked@example.test"))
        created = client.post("/register?next=/profile", data={
            "name": "New User", "email": email,
            "password": old_password, "confirm": old_password,
            "accept_terms": "on", "csrf_token": token,
        })
        self.assertEqual(created.status_code, 302)
        self.assertEqual(urlparse(created.headers["Location"]).path, "/verify-email")
        user = db.get_ss_user_by_email(email)
        self.assertIsNotNone(user)
        self.assertFalse(user["email_verified"])
        self.assertEqual(len(self.sent), 1)
        verify_path = _first_auth_link(self.sent[-1]["html"], "/verify-email/")

        # A correct password is not enough before verification. The login does
        # not automatically send duplicate email; the user gets a resend UI.
        login_page = client.get("/login")
        login_token = _csrf(login_page.get_data(as_text=True))
        unverified = client.post("/login", data={
            "email": email, "password": old_password, "csrf_token": login_token,
        })
        self.assertEqual(unverified.status_code, 302)
        self.assertEqual(urlparse(unverified.headers["Location"]).path, "/verify-email")
        self.assertEqual(len(self.sent), 1)
        pending = client.get("/verify-email")
        pending_html = pending.get_data(as_text=True)
        self.assertIn("Please verify your email first", pending_html)
        pending_token = _csrf(pending_html)
        resend = client.post("/verify-email", data={
            "action": "resend", "csrf_token": pending_token,
        })
        self.assertIn("Please wait", resend.get_data(as_text=True))

        # Changing the pending email requires the account's current password.
        wrong_change = client.post("/verify-email", data={
            "action": "change_email", "new_email": "moved@example.test",
            "current_password": "wrong-password", "csrf_token": pending_token,
        })
        self.assertIn("current password is incorrect", wrong_change.get_data(as_text=True).lower())
        self.assertEqual(db.get_ss_user_by_email(email)["email"], email)

        # Verify once in the registration browser: verification establishes a
        # session only because the pending account matches this browser's
        # registration session. Replay is rejected.
        verified = client.get(verify_path)
        self.assertEqual(verified.status_code, 302)
        self.assertEqual(urlparse(verified.headers["Location"]).path, "/profile")
        self.assertTrue(db.get_ss_user_by_email(email)["email_verified"])
        self.assertEqual(client.get("/profile").status_code, 200)
        replay = client.get(verify_path)
        self.assertEqual(replay.status_code, 400)
        self.assertIn("already been used", replay.get_data(as_text=True))
        client.get("/logout")

        # Successful user login redirects to profile and injects a single
        # responsive in-site toast. Normal users are rejected by /admin.
        login_page = client.get("/login")
        login_token = _csrf(login_page.get_data(as_text=True))
        signed_in = client.post("/login", data={
            "email": email, "password": old_password, "csrf_token": login_token,
        })
        self.assertEqual(urlparse(signed_in.headers["Location"]).path, "/profile")
        profile = client.get("/profile")
        self.assertIn("Welcome to SymptoSense", profile.get_data(as_text=True))
        profile_again = client.get("/profile")
        self.assertNotIn("Welcome to SymptoSense", profile_again.get_data(as_text=True))
        self.assertEqual(client.get("/admin").status_code, 403)
        self.assertEqual(client.get("/my-results").status_code, 200)
        self.assertEqual(client.get("/health-report").status_code, 200)
        self.assertEqual(client.get("/logout").status_code, 302)
        self.assertEqual(client.get("/profile").status_code, 302)

        # Missing-account and wrong-password messages are translated without
        # leaking tokens or password material.
        missing_page = client.get("/login")
        missing_token = _csrf(missing_page.get_data(as_text=True))
        missing = client.post("/login", data={
            "email": "does-not-exist@example.test", "password": old_password,
            "csrf_token": missing_token,
        })
        missing_html = missing.get_data(as_text=True)
        self.assertIn("Incorrect email or password", missing_html)
        self.assertNotIn("No account found", missing_html)
        self.assertRegex(missing_html, r'href="(/(ar|en))?/register')
        wrong_page = client.get("/login")
        wrong_token = _csrf(wrong_page.get_data(as_text=True))
        wrong = client.post("/login", data={
            "email": email, "password": "wrong-password", "csrf_token": wrong_token,
        })
        self.assertIn("Incorrect email or password", wrong.get_data(as_text=True))

        # Forgot Password uses a generic public response, a random hashed token,
        # CSRF, expiry and single-use semantics.
        forgot_page = client.get("/forgot-password")
        forgot_token = _csrf(forgot_page.get_data(as_text=True))
        count_before = len(self.sent)
        forgot = client.post("/forgot-password", data={"email": email, "csrf_token": forgot_token})
        self.assertIn("If an account exists", forgot.get_data(as_text=True))
        self.assertEqual(len(self.sent), count_before + 1)
        reset_href = next(
            href for href in re.findall(r'href="([^"]+)"', self.sent[-1]["html"])
            if urlparse(href).path.startswith("/reset-password/")
        )
        parsed_reset = urlparse(reset_href)
        self.assertIn("lang=en", parsed_reset.query)
        self.assertIn("set_lang=1", parsed_reset.query)
        reset_path = parsed_reset.path
        # A fresh browser/device with no language cookie must be able to open
        # the emailed token URL directly instead of being sent through the
        # language picker and rewritten into a missing /en/reset-password/... page.
        fresh_browser = webapp.app.test_client()
        fresh_reset = fresh_browser.get(parsed_reset.path + ("?" + parsed_reset.query if parsed_reset.query else ""))
        self.assertEqual(fresh_reset.status_code, 200)
        self.assertIn("Reset Password", fresh_reset.get_data(as_text=True))
        reset_page = client.get(reset_path)
        reset_token = _csrf(reset_page.get_data(as_text=True))
        csrf_rejected = client.post(reset_path, data={
            "password": new_password, "confirm": new_password, "csrf_token": "invalid",
        })
        self.assertIn("form expired", csrf_rejected.get_data(as_text=True).lower())
        reset = client.post(reset_path, data={
            "password": new_password, "confirm": new_password, "csrf_token": reset_token,
        })
        self.assertIn("Password reset successfully", reset.get_data(as_text=True))
        self.assertEqual(client.get(reset_path).status_code, 400)
        self.assertEqual(db.authenticate_ss_user_status(email, old_password)["error"], "incorrect_credentials")
        self.assertTrue(db.authenticate_ss_user_status(email, new_password)["ok"])
        self.assertEqual(client.get("/reset-password/not-a-real-token").status_code, 400)
        conn = db._conn()
        try:
            conn.execute("UPDATE ss_password_resets SET created_at='2000-01-01T00:00:00+00:00'")
            conn.commit()
        finally:
            conn.close()
        expired_token, _, _ = platform_v2.create_password_reset(email, minutes=-1)
        self.assertIsNotNone(expired_token)
        self.assertEqual(client.get("/reset-password/" + expired_token).status_code, 400)

    def test_verification_on_different_browser_does_not_create_session(self):
        registration_browser=self.client("en")
        email="different-browser@example.test"; password="StrongPassword1!"
        page=registration_browser.get("/register")
        created=registration_browser.post("/register",data={"name":"Different Browser","email":email,"password":password,"confirm":password,"accept_terms":"on","csrf_token":_csrf(page.get_data(as_text=True))})
        self.assertEqual(created.status_code,302)
        verify_path=_first_auth_link(self.sent[-1]["html"],"/verify-email/")
        other_browser=self.client("en")
        verified=other_browser.get(verify_path)
        self.assertEqual(verified.status_code,200)
        self.assertIn("You can sign in now",verified.get_data(as_text=True))
        self.assertEqual(other_browser.get("/profile").status_code,302)

    @mock.patch.dict(os.environ, {"ADMIN_2FA_REQUIRED": "1"})
    def test_admin_redirect_toast_and_server_side_protection(self):
        email = db.OWNER_ADMIN_EMAIL
        password = "AdminTestPassword1!"
        if not db.get_ss_user_by_email(email):
            self.create_verified_user(email, password, "Remas", "admin")
        client = self.client("ar")
        login_page = client.get("/login")
        token = _csrf(login_page.get_data(as_text=True))
        signed_in = client.post("/login", data={
            "email": email, "password": password, "csrf_token": token,
        })
        self.assertEqual(urlparse(signed_in.headers["Location"]).path, "/admin/2fa/setup")
        self.assertEqual(client.get("/admin").status_code, 302)
        self.assertEqual(client.get("/api/admin/auth-email-status").status_code, 401)
        setup = client.get("/admin/2fa/setup")
        self.assertEqual(setup.status_code, 200)
        token = _csrf(setup.get_data(as_text=True))
        invalid = client.post("/admin/2fa/setup", data={"code": "invalid", "csrf_token": token})
        self.assertEqual(invalid.status_code, 200)
        self.assertEqual(client.get("/admin").status_code, 302)
        uid = db.get_ss_user_by_email(email)["id"]
        secret = webapp.admin_2fa.current_secret(uid)
        confirmed = client.post("/admin/2fa/setup", data={
            "code": webapp.admin_2fa._totp(secret),
            "csrf_token": _csrf(invalid.get_data(as_text=True)),
        })
        self.assertEqual(confirmed.status_code, 200)
        self.assertTrue(webapp.admin_2fa.status(uid)["enabled"])
        self.assertIn("أهلًا بك، ريماس", confirmed.get_data(as_text=True))
        dashboard = client.get("/admin")
        self.assertEqual(dashboard.status_code, 200)
        html = dashboard.get_data(as_text=True)
        self.assertNotIn("أهلًا بك، ريماس", html)
        scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", html, flags=re.S | re.I)
        checked = subprocess.run(
            ["node", "--check", "-"], input="\n".join(scripts),
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertNotIn("أهلًا بك، ريماس", client.get("/admin").get_data(as_text=True))
        status = client.get("/api/admin/auth-email-status")
        self.assertEqual(status.status_code, 200)
        payload = status.get_json()
        self.assertTrue(payload["configured"])
        self.assertTrue(payload["sender_address_valid"])

        guest = self.client("en")
        self.assertEqual(guest.get("/api/admin/auth-email-status").status_code, 401)

    def test_email_configuration_diagnostics_reject_placeholders(self):
        old_sender = os.environ.get("RESEND_FROM")
        old_key = os.environ.get("RESEND_API_KEY")
        try:
            os.environ["RESEND_FROM"] = "SymptoSense <noreply@YOUR_VERIFIED_DOMAIN>"
            state = webapp._auth_email_provider_state()
            self.assertFalse(state["configured"])
            self.assertIn("RESEND_FROM_PLACEHOLDER", state["invalid"])
            os.environ["RESEND_FROM"] = "SymptoSense <onboarding@resend.dev>"
            state = webapp._auth_email_provider_state()
            self.assertTrue(state["configured"])
            self.assertFalse(state["production_recipient_delivery_ready"])
            os.environ["RESEND_API_KEY"] = "YOUR_RESEND_API_KEY"
            state = webapp._auth_email_provider_state()
            self.assertFalse(state["configured"])
            self.assertIn("RESEND_API_KEY_PLACEHOLDER", state["invalid"])
        finally:
            os.environ["RESEND_FROM"] = old_sender or ""
            os.environ["RESEND_API_KEY"] = old_key or ""

    def test_gmail_smtp_is_preferred_and_uses_starttls(self):
        smtp_env={
            "SMTP_HOST":"smtp.gmail.com","SMTP_PORT":"587",
            "SMTP_USERNAME":"remasalsolami1@gmail.com",
            "SMTP_PASSWORD":"abcd efgh ijkl mnop",
            "SMTP_FROM":"SymptoSense <remasalsolami1@gmail.com>",
            "SMTP_USE_TLS":"1",
        }
        server=mock.MagicMock()
        server.__enter__.return_value=server
        with mock.patch.dict(os.environ,smtp_env,clear=False), mock.patch.object(webapp.smtplib,"SMTP",return_value=server) as smtp:
            state=webapp._auth_email_provider_state()
            self.assertEqual(state["provider"],"smtp")
            self.assertTrue(state["configured"])
            ok,reason=self.original_sender("recipient@example.test","Subject","<b>Hello</b>","verify_email")
        self.assertTrue(ok); self.assertIsNone(reason)
        smtp.assert_called_once_with("smtp.gmail.com",587,timeout=15)
        server.starttls.assert_called_once()
        server.login.assert_called_once_with("remasalsolami1@gmail.com","abcdefghijklmnop")
        server.send_message.assert_called_once()

        failed=mock.MagicMock(); failed.__enter__.return_value=failed
        failed.login.side_effect=webapp.smtplib.SMTPAuthenticationError(535,b"rejected")
        with mock.patch.dict(os.environ,smtp_env,clear=False), mock.patch.object(webapp.smtplib,"SMTP",return_value=failed):
            ok,reason=self.original_sender("recipient@example.test","Subject","<b>Hello</b>","password_reset")
        self.assertFalse(ok); self.assertEqual(reason,"email_smtp_auth_failed")

    def test_brevo_https_api_is_preferred_over_smtp(self):
        brevo_env={
            "BREVO_API_KEY":"test-brevo-secret",
            "BREVO_FROM_EMAIL":"remasalsolami1@gmail.com",
            "BREVO_FROM_NAME":"SymptoSense",
            "SMTP_HOST":"smtp.gmail.com",
        }
        accepted=mock.MagicMock(status_code=201)
        with mock.patch.dict(os.environ,brevo_env,clear=False), mock.patch("requests.post",return_value=accepted) as post:
            state=webapp._auth_email_provider_state()
            self.assertEqual(state["provider"],"brevo")
            self.assertTrue(state["configured"])
            ok,reason=self.original_sender("recipient@example.test","Verify","<b>Verify</b>","verify_email")
        self.assertTrue(ok); self.assertIsNone(reason)
        args,kwargs=post.call_args
        self.assertEqual(args[0],"https://api.brevo.com/v3/smtp/email")
        self.assertEqual(kwargs["json"]["sender"]["email"],"remasalsolami1@gmail.com")
        self.assertEqual(kwargs["json"]["to"][0]["email"],"recipient@example.test")

        rejected=mock.MagicMock(status_code=401)
        rejected.json.return_value={"code":"unauthorized"}
        with mock.patch.dict(os.environ,brevo_env,clear=False), mock.patch("requests.post",return_value=rejected):
            ok,reason=self.original_sender("recipient@example.test","Reset","<b>Reset</b>","password_reset")
        self.assertFalse(ok); self.assertEqual(reason,"email_brevo_auth_failed")

    def test_bilingual_auth_pages_and_private_route_redirects(self):
        for lang, expected in (("ar", "تسجيل الدخول"), ("en", "Welcome back")):
            client = self.client(lang)
            login = client.get("/login")
            self.assertEqual(login.status_code, 200)
            self.assertIn(expected, login.get_data(as_text=True))
            self.assertEqual(client.get("/register").status_code, 200)
            self.assertEqual(client.get("/forgot-password").status_code, 200)
            for private_path in ("/profile", "/my-results", "/health-report"):
                response = client.get(private_path)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(urlparse(response.headers["Location"]).path, "/login")
        self.assertTrue(webapp.app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(webapp.app.config["SESSION_COOKIE_SAMESITE"], "Lax")

    def test_legacy_accounts_are_migrated_as_verified_without_password_changes(self):
        legacy_path = str(Path(_TEMP.name) / "legacy-account.sqlite3")
        password = "LegacyPassword1!"
        stored_hash = db._hash_password(password)
        conn = sqlite3.connect(legacy_path)
        try:
            conn.execute(
                "CREATE TABLE ss_users (id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT UNIQUE NOT NULL,"
                "name TEXT NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'user',"
                "created_at TEXT,last_login TEXT,status TEXT NOT NULL DEFAULT 'active')"
            )
            conn.execute(
                "INSERT INTO ss_users (email,name,password_hash,role,created_at,status) VALUES (?,?,?,?,?,?)",
                ("legacy@example.test", "Legacy User", stored_hash, "user", "2025-01-01T00:00:00+00:00", "active"),
            )
            conn.commit()
        finally:
            conn.close()
        original_path = db.DB_PATH
        try:
            db.DB_PATH = legacy_path
            db.init_db()
            migrated = db.get_ss_user_by_email("legacy@example.test")
            self.assertFalse(migrated["email_verified"])
            self.assertEqual(db.authenticate_ss_user_status("legacy@example.test", password)["error"], "verification_required")
            check = sqlite3.connect(legacy_path)
            try:
                saved = check.execute("SELECT password_hash FROM ss_users WHERE email=?", ("legacy@example.test",)).fetchone()[0]
            finally:
                check.close()
            self.assertEqual(saved, stored_hash)
        finally:
            db.DB_PATH = original_path

    def test_failed_critical_migration_is_not_cached_and_retries(self):
        retry_path = str(Path(_TEMP.name) / "retry-critical-migration.sqlite3")
        original_path = db.DB_PATH
        original_migrate = db._migrate_ss_columns
        calls = {"count": 0}

        def fail_once(conn, cursor):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("simulated critical migration failure")
            return original_migrate(conn, cursor)

        try:
            db.DB_PATH = retry_path
            with mock.patch.object(db, "_migrate_ss_columns", side_effect=fail_once):
                with self.assertRaisesRegex(RuntimeError, "simulated critical migration failure"):
                    db.init_db()
                # Because the failed attempt was not cached as ready, the same
                # process must retry the migration on the next init_db() call.
                db.init_db()

            self.assertEqual(calls["count"], 2)
            check = sqlite3.connect(retry_path)
            try:
                cols = {row[1] for row in check.execute("PRAGMA table_info(ss_users)")}
                marker = check.execute(
                    "SELECT value FROM ss_schema_meta WHERE key='email_otp_all_accounts_v1'"
                ).fetchone()
            finally:
                check.close()
            self.assertTrue({"role", "status", "email_verified", "email_verified_at"}.issubset(cols))
            self.assertIsNotNone(marker)
        finally:
            db.DB_PATH = original_path
            # Restore the readiness key to the primary test database so later
            # callers see the same state as before this isolated retry test.
            db.init_db()


if __name__ == "__main__":
    unittest.main(verbosity=2)
