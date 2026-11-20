"""Deprecated compatibility entrypoint.

Medication reminders moved from Web Push to account-email delivery in V175.
No VAPID keys are required.
"""

if __name__ == "__main__":
    print("Web Push medication reminders are disabled. Configure BREVO_* or RESEND_* for email reminders.")
