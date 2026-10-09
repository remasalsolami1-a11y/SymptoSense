import source_bundle
from pathlib import Path
import os, subprocess, sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_v177_static_quality_contracts_present():
    mk = read("medical_knowledge.py")
    tax = read("medical_taxonomy.py")
    guide = read("symptom_guidance.py")
    prio = read("content_priority.py")
    meds = read("medication_warnings.py")
    web = source_bundle.webapp_text()
    assert "saudi-moh-937" in mk
    assert "مرجع محلي للاستشارة ومسار الرعاية" in mk
    assert "CATEGORY_ICD_SYSTEM" in tax and '"womens_health": {"chapter": "17"' in tax
    assert "three_to_five_followup_questions_required" in guide
    assert "GSC_ACCESS_TOKEN" in prio and "import_google_trends_csv" in prio
    assert "GROUP_CONCAT" not in prio
    assert "local_registry" in meds and "clinical_provider_count" in meds
    assert "/api/admin/icd11/candidates" in web
    assert "/api/admin/content-priority/search-console-sync" in web
    assert "/api/admin/content-priority/trends-import" in web


def test_v177_runtime_quality_in_temp_sqlite(tmp_path):
    code = r'''
import os, json
import medical_knowledge as mk
import health_library, symptom_guidance, medical_taxonomy, medication_warnings, content_priority
mk.init_schema()
assert health_library.source_quality_audit() == [], health_library.source_quality_audit()[:5]
syms = mk.list_entities("symptoms", False, "")
dis = mk.list_entities("diseases", False, "")
assert len(syms) >= 280
assert len(dis) >= 150
result = symptom_guidance.backfill_all()
assert result["total"] == len(syms)
for item in syms:
    g = symptom_guidance.get(int(item["id"]))
    assert g is not None
    assert 3 <= len(g["followup_questions_ar"]) <= 5
    assert 3 <= len(g["followup_questions_en"]) <= 5
    assert g["when_to_seek_care_ar"].strip()
    assert g["when_to_seek_care_en"].strip()
assert medical_taxonomy.category_system("womens_health", "en")["chapter"] == "17"
for q in ["aspirin", "amoxicillin", "cetirizine", "pseudoephedrine"]:
    r = medication_warnings.lookup_drug(q)
    assert r and r["source_policy"]["ok"]
    assert r["source_policy"]["has_local"]
    assert r["source_policy"]["clinical_provider_count"] >= 2
assert medication_warnings.lookup_drug("antibiotic") is None
csv_text = "Query,Interest\nصداع جديد نادر,91\nrare new symptom phrase,85\n"
content_priority.import_google_trends_csv(csv_text)
gaps = content_priority.content_gap_report(days=90, limit=50)
assert any("rare new symptom phrase" == str(x.get("query", "")).lower() for x in gaps)
print(json.dumps({"diseases":len(dis),"symptoms":len(syms),"source_gaps":0,"guidance":result["total"]}))
'''
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env["DB_PATH"] = str(tmp_path / "v177.db")
    cp = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=120)
    assert cp.returncode == 0, cp.stdout + "\n" + cp.stderr
