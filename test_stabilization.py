"""Production-stabilization smoke, authorization, search and medication tests."""
import os
import re
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

_TEMP=tempfile.TemporaryDirectory(prefix="symptosense-stabilization-")
os.environ.pop("DATABASE_URL",None)
os.environ["DB_PATH"]=str(Path(_TEMP.name)/"stabilization.sqlite3")
os.environ["WEB_SECRET"]="stabilization-test-secret-more-than-32-characters"
os.environ["SITE_URL"]="http://localhost"
os.environ["SESSION_COOKIE_SECURE"]="0"

import db
import medical_knowledge
import medication_push
import medication_warnings
import platform_v2
import webapp


class StabilizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        webapp.app.config.update(TESTING=True)
        db.init_db(); medical_knowledge.init_schema(); medication_push.init_schema(); medication_warnings.init_schema(); platform_v2.init_schema()

    def client(self,lang="en"):
        c=webapp.app.test_client(); c.set_cookie("lang",lang,domain="localhost"); return c

    def verified_user(self,email="stability-user@example.test"):
        existing=db.get_ss_user_by_email(email)
        if existing:return int(existing["id"])
        uid,error=db.create_ss_user(email,"Stability User","StrongPassword1!")
        self.assertIsNone(error)
        conn=db._conn(); conn.execute("UPDATE ss_users SET email_verified=1,email_verified_at=? WHERE id=?",(datetime.now(timezone.utc).isoformat(),uid)); conn.commit(); conn.close()
        return int(uid)

    def login_session(self,c,uid):
        with c.session_transaction() as session: session["ss_user_id"]=int(uid)

    def test_public_route_smoke_has_no_404_or_500(self):
        c=self.client("en")
        routes=["/","/home","/about-us","/privacy","/terms","/sources","/chat","/blood","/meds","/firstaid","/tips","/relax","/emergency","/checkin","/search","/calculators","/login","/register","/forgot-password","/manifest.webmanifest","/service-worker.js","/icons/icon-192.png","/icons/about-us-phone.webp"]
        for route in routes:
            with self.subTest(route=route):
                response=c.get(route,follow_redirects=False)
                self.assertNotIn(response.status_code,{404,500,502,503})
                response.close()

    def test_private_routes_and_admin_authorization(self):
        guest=self.client()
        for route in ["/profile","/history","/my-results","/health-report","/admin"]:
            response=guest.get(route)
            self.assertIn(response.status_code,{302,401})
        uid=self.verified_user(); user=self.client(); self.login_session(user,uid)
        self.assertEqual(user.get("/admin").status_code,403)
        admin_rules=[r.rule for r in webapp.app.url_map.iter_rules() if r.rule.startswith("/api/admin/") and "GET" in r.methods and "<" not in r.rule]
        for route in admin_rules:
            with self.subTest(route=route):
                response=user.get(route)
                self.assertEqual(response.status_code,403)

    def test_search_arabic_english_empty_and_no_result(self):
        c=self.client()
        for term,lang in [("صداع","ar"),("headache","en")]:
            payload=c.get("/api/search",query_string={"q":term,"lang":lang}).get_json()
            self.assertTrue(payload["ok"]); self.assertTrue(payload["result"]); self.assertTrue(payload["result"].get("sources"))
        self.assertIsNone(c.get("/api/search",query_string={"q":"not-in-medical-kb","lang":"en"}).get_json()["result"])
        self.assertTrue(c.get("/api/search",query_string={"q":"","lang":"en"}).get_json()["suggestions"])

    def test_medication_database_search_and_reminder_crud(self):
        c=self.client()
        for term in ("Paracetamol","باراسيتامول"):
            payload=c.get("/api/drug",query_string={"name":term}).get_json()
            self.assertTrue(payload["ok"]); self.assertTrue(payload["result"]); self.assertTrue(payload["name"])
        self.assertIsNone(c.get("/api/drug",query_string={"name":"not-a-real-medicine"}).get_json()["result"])
        self.assertEqual(c.post("/api/meds/plan",json={"med_name":"Paracetamol","times":["08:00"]}).status_code,401)
        uid=self.verified_user("reminder-user@example.test"); self.login_session(c,uid)
        consent=c.post("/api/consent/preferences",json={"service_usage":True,"analytics_research":False})
        self.assertEqual(consent.status_code,200)
        created=c.post("/api/meds/plan",json={"med_name":"Paracetamol","dose":"500 mg","times":["08:00"],"frequency":"daily","start_date":"2026-08-30","timezone":"Asia/Riyadh"})
        self.assertEqual(created.status_code,200); pid=created.get_json()["id"]
        plans=c.get("/api/meds/plan").get_json()["plans"]; self.assertEqual(plans[0]["med_name"],"Paracetamol")
        updated=c.put(f"/api/meds/plan/{pid}",json={"med_name":"Paracetamol","dose":"500 mg","times":["09:00"],"frequency":"daily","start_date":"2026-08-30","timezone":"Asia/Riyadh"})
        self.assertEqual(updated.status_code,200)
        self.assertEqual(c.delete(f"/api/meds/plan/{pid}").status_code,200)

    def test_login_throttle_uses_only_pseudonymous_keys(self):
        email="rate-limit-user@example.test"; origin="192.0.2.10"
        self.assertTrue(platform_v2.login_attempt_allowed(email,origin))
        for _ in range(10): platform_v2.record_login_attempt(email,origin,False)
        self.assertFalse(platform_v2.login_attempt_allowed(email,origin))
        conn=db._conn(); row=conn.execute("SELECT key_hash FROM ss_auth_rate_limits LIMIT 1").fetchone(); conn.close()
        self.assertIsNotNone(row); self.assertNotIn("rate-limit-user",row[0]); self.assertNotIn(origin,row[0])
        platform_v2.record_login_attempt(email,origin,True)
        self.assertTrue(platform_v2.login_attempt_allowed(email,origin))

    def test_database_integrity_and_required_tables(self):
        conn=db._conn()
        tables={row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required={"ss_users","ss_email_verifications","ss_password_resets","ss_login_activity","ss_auth_rate_limits","med_plans"}
        self.assertFalse(required-tables)
        self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(),[])
        conn.close()

    def test_core_inline_javascript_parses_and_no_translation_keys_leak(self):
        c=self.client("en")
        for route in ["/","/search","/meds","/about-us","/login","/register","/chat"]:
            html=c.get(route).get_data(as_text=True)
            self.assertNotRegex(html,r">\s*(?:prereview_title|prereview_sub|auth_error|verification_required)\s*<")
            for index,script in enumerate(re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>",html,re.S|re.I)):
                if not script.strip(): continue
                checked=subprocess.run(["node","--check"],input=script,text=True,capture_output=True)
                self.assertEqual(checked.returncode,0,f"{route} script {index}: {checked.stderr}")

    def test_analysis_validation_does_not_return_server_error(self):
        c=self.client("en")
        response=c.post("/api/analyze",json={"lang":"en","symptoms":[]})
        self.assertIn(response.status_code,{400,403})
        self.assertLess(response.status_code,500)


if __name__=="__main__": unittest.main(verbosity=2)
