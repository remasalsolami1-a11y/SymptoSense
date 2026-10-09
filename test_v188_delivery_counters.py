from pathlib import Path

ROOT = Path(__file__).resolve().parent
mail = (ROOT / "medication_email.py").read_text(encoding="utf-8")


def test_primary_already_sent_is_counted_as_skipped_not_sent():
    block = mail[mail.index('if channel == "telegram":'):mail.index('user = db.get_ss_user', mail.index('if channel == "telegram":'))]
    assert 'if tg.get("sent"):' in block
    assert 'if tg.get("reason") == "already_sent":' in block
    already = block[block.index('if tg.get("reason") == "already_sent":'):]
    assert 'skipped += 1' in already
    assert 'sent += 1' not in already


def test_snooze_already_sent_does_not_increment_sent_counter():
    snooze_start = mail.index('delivered = False', mail.index('# Deliver due snoozes'))
    snooze_end = mail.index('except Exception:', snooze_start)
    block = mail[snooze_start:snooze_end]
    assert 'newly_sent = False' in block
    assert 'already_delivered = False' in block
    assert 'elif already_delivered:' in block
    already_branch = block[block.index('elif already_delivered:'):block.index('else:', block.index('elif already_delivered:'))]
    assert 'skipped += 1' in already_branch
    assert 'sent += 1' not in already_branch
