from pathlib import Path


def test_services_dropdown_passes_supported_event_token():
    source = Path(__file__).resolve().parents[1].joinpath("webapp.py").read_text(encoding="utf-8")
    assert 'data-ss-click="toggleDD" data-ss-args="[&quot;$event&quot;]"' in source
    assert 'data-ss-click="toggleDD" data-ss-args="[&quot;event&quot;]"' not in source
