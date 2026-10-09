"""Guards: chat scripts must not become a new monolith; no legacy inline on* attributes."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Ceilings sit slightly above today's sizes. If a file nears its ceiling,
# split it by feature (e.g. symptom-flow -> questions / rendering / state)
# instead of raising the number.
CEILINGS = {
    "symptom-flow.js": 950, "body-map.js": 450, "clarifications.js": 180, "analysis-result.js": 850, "data-quality.js": 140, "result-tracking.js": 40, "result-actions.js": 130, "chat-core.js": 500,
    "assistant.js": 480, "followup.js": 340, "red-flags.js": 280,
    "doctor-summary.js": 160, "chat-boot.js": 80,
}
LEGACY = re.compile(r"""\son(?:click|change|input|submit|keydown|keyup|load|focus|blur)\s*=\s*["']""", re.I)


def test_chat_scripts_stay_below_size_ceiling():
    d = ROOT / "static/js/chat"
    for f in d.glob("*.js"):
        n = len(f.read_text(encoding="utf-8").splitlines())
        assert f.name in CEILINGS, f"new chat script {f.name}: add a ceiling"
        assert n <= CEILINGS[f.name], f"{f.name} has {n} lines (> {CEILINGS[f.name]}); split it"


def test_no_legacy_inline_event_attributes_in_sources():
    bad = []
    for p in list(ROOT.glob("*.py")) + list((ROOT / "routes").glob("*.py")) + list((ROOT / "pagelib").glob("*.py")) + list((ROOT / "inline_assets").glob("*")):
        if p.name.startswith("test_") or p.is_dir() or p.name in {"full_interaction_audit.py"}:
            continue
        try:
            t = p.read_text(encoding="utf-8")
        except Exception:
            continue
        if LEGACY.search(t):
            bad.append(p.name)
    assert not bad, bad
