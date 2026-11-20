"""One-shot medication reminder delivery job.

Email is always the baseline channel. If a user linked Telegram, the same run
also sends the optional Telegram copy. Run once per minute from Railway Cron:
    python medication_email_job.py
"""
import json
import medication_email


def main():
    medication_email.init_schema()
    print(json.dumps(medication_email.send_due_emails(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
