# SymptoSense — Railway Web Push Worker Setup

Medication reminders use **backend-driven Web Push**. Browser JavaScript timers are not used as the delivery mechanism.

## 1) Generate VAPID keys once

Run locally:

```bash
python generate_vapid_keys.py
```

Add the printed values to Railway Variables for the **web service** (and to a dedicated worker too only if you choose external-worker mode):

- `VAPID_PUBLIC_KEY`
- `VAPID_PRIVATE_KEY`
- `VAPID_CLAIMS_EMAIL` (for example `mailto:your-email@example.com`)

Never put the private key in frontend JavaScript. Only the public key is returned to authenticated browsers when subscribing.

## 2) Keep the existing web service

Start command:

```bash
python webapp.py
```

It serves the website, Service Worker, subscription APIs, medication reminder APIs, and Admin APIs.

## 3) Scheduler mode on Railway

### Default — embedded worker (recommended for the current single-service/SQLite deployment)

No second Railway service is required. `webapp.py` starts a lightweight server-side reminder worker in the same service and therefore uses the same database/volume automatically. This is still **backend-driven** and does not depend on the user's browser being open.

Keep (or omit, because it is the default):

```text
PUSH_WORKER_MODE=embedded
PUSH_WORKER_INTERVAL_SECONDS=20
```

Railway should keep the web service running continuously for scheduled delivery.

### Optional — dedicated worker service

For a larger production deployment using a database that can be shared between services (recommended: PostgreSQL), create another Railway service from the same repository with:

```bash
python push_worker.py
```

Then set on the **web service**:

```text
PUSH_WORKER_MODE=external
```

Give both services the same `DATABASE_URL` and VAPID variables. Do **not** assume a SQLite file/volume attached to one Railway service is automatically shared with another service.

The worker does not need a public domain.

## 4) Recommended production variables

```text
SESSION_COOKIE_SECURE=1
ANALYTICS_PRIVACY_THRESHOLD=5
PUSH_WORKER_MODE=embedded
PUSH_WORKER_INTERVAL_SECONDS=20
```

## 5) Browser/device notes

- Web Push requires HTTPS, a Service Worker, Push API support, and user permission.
- Android/Desktop behavior depends on the installed browser and OS notification settings.
- On supported iPhone/iPad versions, Web Push is available for web apps added to the Home Screen. The user should install SymptoSense to the Home Screen and enable notifications from inside that web app.
- Notification action buttons such as **Taken** and **Snooze** are best-effort: some browsers/OS versions may show the notification without action buttons. Opening the notification still takes the user to My Medications.

## 6) Test

1. Sign in to SymptoSense.
2. Open `/meds` and enable notifications from a direct button click.
3. Add a reminder a few minutes in the future.
4. Confirm the web service is running (embedded mode), or the dedicated worker is running if you selected external mode.
5. Close the site and wait for the reminder.
6. In `/admin` → **Live Activity**, Admin can use **Send Test Notification** for the currently subscribed Admin device.

If `VAPID_*` variables are missing, SymptoSense explicitly shows Push as not configured rather than claiming background reminders are active.
