#!/usr/bin/env python3
"""Backend-only smoke checks for v36 using an isolated SQLite database."""
from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Running ``python tools/v36_backend_smoke.py`` sets sys.path[0] to ``tools``.
# Add the project root explicitly so the smoke test can import the application
# modules exactly as documented, without requiring callers to set PYTHONPATH.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.pop('DATABASE_URL', None)
_tmp = tempfile.TemporaryDirectory(prefix='symptosense-v36-')
os.environ['DB_PATH'] = str(Path(_tmp.name) / 'smoke.db')

import db  # noqa: E402
import medication_push as push  # noqa: E402
import research_validation as validation  # noqa: E402
import medical_knowledge as knowledge  # noqa: E402


def main():
    # Browser-delivery receipt lifecycle (no external push provider required).
    user_id = 'v36-smoke-user'
    rid = push._new_delivery_receipt(db._hash_user(user_id), 'https://push.invalid/device', 'test', 'v36-smoke')
    before = push.receipt_status(user_id, rid)
    marked = push.record_push_receipt(rid, 'displayed')
    after = push.receipt_status(user_id, rid)
    delivery = push.delivery_verification_summary()
    assert before['found'] and not before['displayed']
    assert marked['ok'] and after['displayed'] and delivery['displayed'] == 1

    # Validation workspace starts with templates but no false evidence.
    summary = validation.summary()
    assert summary['total_cases'] >= 180
    assert summary['verified_cases'] == 0
    assert summary['study_ready'] is False
    assert validation.study_protocol()['minimum_verified_cases'] == 100
    assert 'system_risk' not in validation.export_rows(blinded=True)[0]
    assert 'system_risk' in validation.export_rows(blinded=False)[0]

    # Knowledge review queue is computable and status counts reconcile.
    review = knowledge.periodic_review_status()
    assert review['total'] == sum(review['counts'].values())
    assert all(x['review_status'] != 'verified' for x in review['queue'])

    result = {
        'ok': True,
        'push_receipt': {'before_displayed': before['displayed'], 'after_displayed': after['displayed']},
        'validation': {'total_templates': summary['total_cases'], 'verified': summary['verified_cases'], 'study_ready': summary['study_ready']},
        'knowledge_review': {'total': review['total'], 'counts': review['counts'], 'queue': len(review['queue'])},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
