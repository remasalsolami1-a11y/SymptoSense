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
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
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

        # Verify once; replay is rejected.
        verified = client.get(verify_path)
        self.assertEqual(verified.status_code, 200)
        self.assertTrue(db.get_ss_user_by_email(email)["email_verified"])
        replay = client.get(verify_path)
        self.assertEqual(replay.status_code, 400)
        self.assertIn("already been used", replay.get_data(as_text=True))

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
        self.assertIn("No account found", missing_html)
        self.assertIn("Create Account", missing_html)
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
        reset_path = _first_auth_link(self.sent[-1]["html"], "/reset-password/")
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
        self.assertEqual(urlparse(signed_in.headers["Location"]).path, "/admin")
        dashboard = client.get("/admin")
        self.assertEqual(dashboard.status_code, 200)
        html = dashboard.get_data(as_text=True)
        self.assertIn("أهلًا بك، ريماس", html)
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
            self.assertTrue(migrated["email_verified"])
            self.assertTrue(db.authenticate_ss_user_status("legacy@example.test", password)["ok"])
            check = sqlite3.connect(legacy_path)
            try:
                saved = check.execute("SELECT password_hash FROM ss_users WHERE email=?", ("legacy@example.test",)).fetchone()[0]
            finally:
                check.close()
            self.assertEqual(saved, stored_hash)
        finally:
            db.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main(verbosity=2)
