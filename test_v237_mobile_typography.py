import source_bundle
import versioning
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
SW = (ROOT / "service-worker.js").read_text(encoding="utf-8")
CSS = (ROOT / "app-shell-v111.css").read_text(encoding="utf-8")

def test_v237_cache_bust_is_consistent():
    assert "/assets/app-shell-v112.css?v=273" in WEB
    assert "symptosense-app-shell-v112-v273" in WEB
    assert versioning.SW_CACHE in SW
    assert "'/assets/app-shell-v112.css?v=273'" in SW

def test_symptom_method_labels_are_bounded_on_iphone():
    for src in (WEB, CSS):
        assert "V237 iPhone typography + no-overlap hardening" in src
        assert '.symptom-method-copy>b' in src
        assert 'font-size:12px!important' in src
        assert 'word-break:keep-all!important' in src

def test_home_trust_row_cannot_overlap_preview():
    for src in (WEB, CSS):
        assert '.ss-trust-row' in src
        assert 'grid-template-columns:repeat(3,minmax(0,1fr))!important' in src
        assert '.ss-trust-item>*:not(.ss-trust-ic)' in src
        assert 'overflow-wrap:break-word!important' in src
