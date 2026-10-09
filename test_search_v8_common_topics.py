"""V249 common-topic search cards: every card answers what / causes / worry / when to see a doctor."""
from urllib.parse import urlparse
from unittest import mock

from trusted_sources_wiring import ALLOWED_HOSTS as ALLOWED_SOURCE_HOSTS
import pytest

import health_search
from health_search_expansion_v8 import EXTRA_SEARCH_KB_V8 as KB
import webapp


@pytest.mark.parametrize("key", sorted(KB))
@pytest.mark.parametrize("lang", ["ar", "en"])
def test_each_topic_is_complete_sourced_and_served_by_both_apis(key, lang, monkeypatch):
    monkeypatch.setenv("ASSISTANT_RATE_LIMIT_MAX", "1000")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    entry = KB[key]
    detail = entry[lang]
    for field in ("title", "what", "self_care", "worry", "doctor", "follow_up"):
        assert detail[field].strip(), (key, lang, field)
    assert len(detail["causes"]) >= 3
    assert entry["sources"] and all(urlparse(s["url"]).hostname in ALLOWED_SOURCE_HOSTS for s in entry["sources"])
    client = webapp.app.test_client()
    client.environ_base["REMOTE_ADDR"] = "198.51.100." + str(1 + sorted(KB).index(key) + (20 if lang == "en" else 0))
    client.set_cookie("lang", lang, domain="localhost")
    assert client.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    with mock.patch.object(webapp, "_assistant_contextual_health_answer", side_effect=AssertionError("unexpected fallback")):
        search = client.get("/api/search", query_string={"q": detail["title"], "lang": lang})
        assistant = client.post("/api/assistant", json={"lang": lang, "messages": [{"role": "user", "content": detail["title"]}]})
    assert search.status_code == assistant.status_code == 200
    result = search.get_json()["result"]
    assert result["key"] == key and result["curated_answer"] is True
    assert detail["worry"] in assistant.get_json()["answer"] and detail["doctor"] in assistant.get_json()["answer"]


@pytest.mark.parametrize("query,key,lang", [
    ("رشح", "common_cold", "ar"), ("زكام", "common_cold", "ar"), ("عطاس", "common_cold", "ar"),
    ("قلق", "anxiety", "ar"), ("طفح جلدي", "rash", "ar"), ("الم المفاصل", "joint_pain", "ar"),
    ("نقص الوزن", "weight_loss", "ar"), ("حكة", "itching", "ar"), ("تورم الرجل", "leg_swelling", "ar"),
    ("runny nose", "common_cold", "en"), ("anxiety", "anxiety", "en"), ("rash", "rash", "en"),
    ("joint pain", "joint_pain", "en"), ("swollen ankles", "leg_swelling", "en"),
    ("what causes joint pain", "joint_pain", "en"), ("when to see a doctor for rash", "rash", "en"),
])
def test_everyday_wording_reaches_the_right_card(query, key, lang):
    result = health_search.search_health(query, lang)
    assert result["key"] == key and result["curated_answer"], result.get("key")
