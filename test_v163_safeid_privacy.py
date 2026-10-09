import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json


def test_safeid_public_payload_minimizes_data(tmp_path, monkeypatch):
    import db
    import privacy_features

    db.DB_PATH = str(tmp_path / "safeid.db")
    db.DATABASE_URL = ""
    db.USE_POSTGRES = False
    db.PH = "?"
    db._DB_READY_KEY = None
    privacy_features._SCHEMA_READY = None
    monkeypatch.setenv("WEB_SECRET", "test-safeid-secret-1234567890")
    monkeypatch.setenv("HASH_SALT", "safeid-test")

    db.init_db()
    db.save_health_profile(1, {
        "display_name": "Private Name",
        "allergies": "Private Name - Penicillin user@example.com",
        "medications": "Epinephrine 0.3 mg",
        "health_conditions": "Asthma",
        "lang": "ar",
    })
    owner = "account-1"
    card = privacy_features.save_safeid(owner, 1, config={
        "share_allergies": True,
        "share_medications": True,
        "share_conditions": False,
        "emergency_note": "Call 0501234567 only if needed",
        "preferred_language": "Arabic",
        "support_needs": "Use written instructions",
        "contact_alert": True,
    })
    payload = privacy_features.safeid_public_payload(card["token"], "emergency")
    raw = json.dumps(payload, ensure_ascii=False)
    assert "Private Name" not in raw
    assert "[hidden name]" in raw
    assert "user@example.com" not in raw
    assert "0501234567" not in raw
    assert "[hidden email]" in raw
    assert "[hidden number]" in raw
    assert "Asthma" not in raw


def test_safeid_rotation_pause_and_contact_cooldown(tmp_path, monkeypatch):
    import db
    import privacy_features

    db.DB_PATH = str(tmp_path / "safeid2.db")
    db.DATABASE_URL = ""
    db.USE_POSTGRES = False
    db.PH = "?"
    db._DB_READY_KEY = None
    privacy_features._SCHEMA_READY = None
    monkeypatch.setenv("WEB_SECRET", "test-safeid-secret-1234567890")
    monkeypatch.setenv("HASH_SALT", "safeid-test")

    db.init_db()
    owner = "account-2"
    card = privacy_features.save_safeid(owner, 2, config={"contact_alert": True})
    old_token = card["token"]
    assert privacy_features.safeid_contact_alert(old_token)["ok"] is True
    assert privacy_features.safeid_contact_alert(old_token)["reason"] == "cooldown"
    new_token = privacy_features.rotate_safeid(owner, 2)["token"]
    assert new_token != old_token
    assert privacy_features.get_safeid_public(old_token) is None
    assert privacy_features.get_safeid_public(new_token) is not None
    privacy_features.set_safeid_enabled(owner, 2, enabled=False)
    assert privacy_features.get_safeid_public(new_token) is None


def test_safeid_contact_alert_is_atomic(tmp_path, monkeypatch):
    import db
    import privacy_features
    from concurrent.futures import ThreadPoolExecutor

    db.DB_PATH = str(tmp_path / "safeid3.db")
    db.DATABASE_URL = ""
    db.USE_POSTGRES = False
    db.PH = "?"
    db._DB_READY_KEY = None
    privacy_features.PH = "?"
    privacy_features._SCHEMA_READY = None
    monkeypatch.setenv("WEB_SECRET", "test-safeid-secret-1234567890")
    monkeypatch.setenv("HASH_SALT", "safeid-test")

    db.init_db()
    card = privacy_features.save_safeid("account-3", 3, config={"contact_alert": True})
    token = card["token"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: privacy_features.safeid_contact_alert(token), range(8)))
    assert sum(1 for r in results if r.get("ok")) == 1
    assert sum(1 for r in results if r.get("reason") == "cooldown") == 7


def test_safeid_first_create_race_reuses_one_card(tmp_path, monkeypatch):
    import db
    import privacy_features
    from concurrent.futures import ThreadPoolExecutor

    db.DB_PATH = str(tmp_path / "safeid4.db")
    db.DATABASE_URL = ""
    db.USE_POSTGRES = False
    db.PH = "?"
    db._DB_READY_KEY = None
    privacy_features.PH = "?"
    privacy_features._SCHEMA_READY = None
    monkeypatch.setenv("WEB_SECRET", "test-safeid-secret-1234567890")
    monkeypatch.setenv("HASH_SALT", "safeid-test")
    db.init_db()

    with ThreadPoolExecutor(max_workers=6) as pool:
        cards = list(pool.map(lambda _: privacy_features.get_or_create_safeid("account-4", 4), range(6)))
    assert len({c["id"] for c in cards}) == 1
    assert len({c["token"] for c in cards}) == 1
