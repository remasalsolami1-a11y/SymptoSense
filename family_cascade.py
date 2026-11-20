"""Deleting a family member must also stop and remove that member's medication reminders."""
import db
import medication_email


def purge_member_medications(account_id, member_id) -> int:
    """Delete every reminder plan (with its schedule, tokens, snoozes and dose history) of one member."""
    try:
        uid = int(account_id)
    except (TypeError, ValueError):
        return 0  # guests have no medication-engine rows
    removed = 0
    for plan in medication_email.list_plans(uid, member_id=int(member_id), active_only=False):
        if medication_email.delete_plan(uid, int(plan["id"])):
            removed += 1
    return removed
