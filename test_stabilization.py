"""Production-stabilization smoke, authorization, search and medication tests."""
import os
import re
import subprocess
import tempfile
import unittest
from unittest import mock
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
import analysis_core
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
        routes=["/","/home","/about-us","/privacy","/terms","/sources","/chat","/blood","/meds","/firstaid","/tips","/relax","/emergency","/checkin","/search","/calculators","/login","/register","/forgot-password","/manifest.webmanifest","/service-worker.js","/icons/icon-192.png","/icons/about-us-phone.webp","/static/images/about-hero.webp","/static/images/about-story.webp","/static/images/symptosense-social-preview.png"]
        for route in routes:
            with self.subTest(route=route):
                response=c.get(route,follow_redirects=False)
                self.assertNotIn(response.status_code,{404,500,502,503})
                response.close()

    def test_all_static_get_routes_avoid_server_errors(self):
        c=self.client("en")
        routes=sorted({rule.rule for rule in webapp.app.url_map.iter_rules() if "GET" in rule.methods and "<" not in rule.rule and rule.rule!="/static/<path:filename>"})
        self.assertGreaterEqual(len(routes),70)
        for route in routes:
            with self.subTest(route=route):
                response=c.get(route,follow_redirects=False)
                self.assertNotIn(response.status_code,{500,502,503})
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

    def test_about_visual_assets_social_metadata_and_readme_links(self):
        project_root=Path(__file__).resolve().parents[1]
        for lang,direction,name in (("ar","rtl","ريماس حميد السلمي"),("en","ltr","Remas Hameed Alsolami")):
            c=self.client(lang); response=c.get("/about-us"); html=response.get_data(as_text=True)
            self.assertEqual(response.status_code,200)
            self.assertIn(f'<html lang="{lang}" dir="{direction}">',html)
            self.assertIn(name,html)
            self.assertIn('/static/images/about-hero.webp',html)
            self.assertIn('/static/images/about-story.webp',html)
            self.assertIn('/icons/about-us-phone.webp',html)
            self.assertNotIn('remas.jpg',html)
            self.assertNotIn('photo placeholder',html.lower())
            self.assertNotIn('Technologies',html)
            self.assertNotIn('PostgreSQL / SQLite',html)
            self.assertIn('prefers-reduced-motion:reduce',html)
        legacy=self.client("en").get("/about",follow_redirects=False)
        self.assertEqual(legacy.status_code,302)
        self.assertTrue(legacy.headers["Location"].endswith("/about-us"))
        home=self.client("en").get("/home").get_data(as_text=True)
        expected="http://localhost/static/images/symptosense-social-preview.png"
        self.assertIn(f'<meta property="og:image" content="{expected}">',home)
        self.assertIn('<meta property="og:url" content="http://localhost/home">',home)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">',home)
        readme=(project_root/"README.md").read_text(encoding="utf-8")
        relative_links=re.findall(r'!?(?:\[[^\]]*\])\((?!https?://|mailto:|#)([^)]+)\)',readme)
        missing=[]
        for link in relative_links:
            clean=link.split("#",1)[0].strip().strip("<>")
            if clean and not (project_root/clean).resolve().exists(): missing.append(clean)
        self.assertEqual(missing,[],f"Broken README asset links: {missing}")

    def test_analysis_validation_does_not_return_server_error(self):
        c=self.client("en")
        response=c.post("/api/analyze",json={"lang":"en","symptoms":[]})
        self.assertIn(response.status_code,{400,403})
        self.assertLess(response.status_code,500)

    def test_red_flags_override_condition_output(self):
        result=analysis_core.run_analysis({"user_id":"red-flag-test","age":30,"gender":"female","symptoms":["severe chest pain","difficulty breathing"],"duration":"now","severity":5,"conditions":"","medications":"","notes":""},lang="en")
        self.assertEqual(result.get("urgency"),"high")
        self.assertTrue(result.get("emergency"))
        self.assertIn("withheld",result.get("possible_conditions","").lower())

    def test_analysis_and_reminder_idor_is_denied(self):
        owner_id=self.verified_user("idor-owner@example.test"); attacker_id=self.verified_user("idor-attacker@example.test")
        owner_key=f"account:{owner_id}"; record_id=db.save_record(owner_key,"en",30,"female",["headache"],"1 day",2,"low")
        db.save_result(owner_key,record_id,{"symptoms":["headache"],"risk_level":"low"})
        attacker=self.client(); self.login_session(attacker,attacker_id)
        self.assertEqual(attacker.get(f"/api/analysis/{record_id}").status_code,404)
        self.assertEqual(attacker.delete(f"/api/analysis/{record_id}").status_code,404)
        owner=self.client(); self.login_session(owner,owner_id)
        owner.post("/api/consent/preferences",json={"service_usage":True,"analytics_research":False})
        created=owner.post("/api/meds/plan",json={"med_name":"Paracetamol","times":["08:00"]}).get_json()["id"]
        attacker.post("/api/consent/preferences",json={"service_usage":True,"analytics_research":False})
        self.assertEqual(attacker.put(f"/api/meds/plan/{created}",json={"med_name":"Changed","times":["09:00"]}).status_code,403)
        self.assertEqual(attacker.delete(f"/api/meds/plan/{created}").status_code,404)

    def test_sensitive_double_actions_are_safe(self):
        uid=self.verified_user("double-action@example.test"); c=self.client(); self.login_session(c,uid)
        c.post("/api/consent/preferences",json={"service_usage":True,"analytics_research":False})
        pid=c.post("/api/meds/plan",json={"med_name":"Paracetamol","times":["08:00"]}).get_json()["id"]
        self.assertEqual(c.delete(f"/api/meds/plan/{pid}").status_code,200)
        self.assertEqual(c.delete(f"/api/meds/plan/{pid}").status_code,200)
        self.assertTrue(db.claim_push_delivery("https://push.invalid/one",pid,"2026-08-30","08:00"))
        self.assertFalse(db.claim_push_delivery("https://push.invalid/one",pid,"2026-08-30","08:00"))

    def test_privacy_consent_withdrawal_and_health_delete(self):
        uid=self.verified_user("privacy-test@example.test"); c=self.client(); self.login_session(c,uid)
        enabled=c.post("/api/consent/preferences",json={"service_usage":True,"analytics_research":True}).get_json()
        self.assertTrue(enabled["consent"]["analytics_research"])
        withdrawn=c.post("/api/privacy/withdraw-analytics").get_json()
        self.assertFalse(withdrawn["consent"]["analytics_research"])
        c.post("/api/meds/plan",json={"med_name":"Paracetamol","times":["08:00"]})
        deleted=c.post("/api/privacy/delete-health-data")
        self.assertEqual(deleted.status_code,200)
        self.assertEqual(c.get("/api/meds/plan").get_json()["plans"],[])
        self.assertIsNotNone(db.get_ss_user(uid))

    def test_error_pages_and_security_request_id(self):
        c=self.client("en"); missing=c.get("/definitely-not-a-route")
        self.assertEqual(missing.status_code,404); self.assertIn("Page not found",missing.get_data(as_text=True))
        self.assertTrue(missing.headers.get("X-Request-ID")); self.assertEqual(missing.headers.get("X-Frame-Options"),"DENY")

    def test_search_failure_is_generic_and_has_request_id(self):
        c=self.client("en")
        with mock.patch.object(webapp.health_search,"search_health",side_effect=RuntimeError("database password must never leak")):
            failed=c.get("/api/search",query_string={"q":"headache","lang":"en"})
        self.assertEqual(failed.status_code,500)
        payload=failed.get_json(); self.assertFalse(payload["ok"])
        self.assertNotIn("database password",payload["error"])
        self.assertEqual(payload["request_id"],failed.headers["X-Request-ID"])


if __name__=="__main__": unittest.main(verbosity=2)
