"""Deprecated medication Web Push worker.

V175 uses email-only medication reminders. Deploy the once-per-minute cron
command `python medication_email_job.py` instead.
"""
if __name__ == "__main__":
    print("Medication Web Push is disabled. Use: python medication_email_job.py")
