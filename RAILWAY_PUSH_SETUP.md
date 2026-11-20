# SymptoSense — Railway Web Push Worker Setup

Medication reminders use **backend-driven Web Push**. Browser JavaScript timers are not the delivery mechanism.

## Production recommendation

For the public PostgreSQL deployment, run **two Railway services from the same repository**:

1. Web service: `python webapp.py`
2. Worker service: `python push_worker.py`

Both services must share the same `DATABASE_URL` and VAPID variables. On the web service set:

```text
PUSH_WORKER_MODE=external
PUSH_WORKER_INTERVAL_SECONDS=20
```

The Admin dashboard → **Production Readiness** shows the worker mode, last heartbeat, last cycle, sent/failed counts, and last error. A worker is considered offline when its heartbeat is stale.

## VAPID variables

Generate keys once with:

```bash
python generate_vapid_keys.py
```

Set on both web and worker services:

- `VAPID_PUBLIC_KEY`
- `VAPID_PRIVATE_KEY`
- `VAPID_CLAIMS_EMAIL`

Never expose the private key in frontend JavaScript.

## Embedded fallback

For local development or a single-service deployment, the web process can run the embedded scheduler:

```text
PUSH_WORKER_MODE=embedded
PUSH_WORKER_INTERVAL_SECONDS=20
```

Do not run embedded and external schedulers at the same time in production.

## iPhone verification after deploy

Server checks cannot prove that a real iPhone received a notification. Perform this launch test:

1. Sign in on iPhone.
2. Add SymptoSense to the Home Screen.
3. Open the installed web app and enable notifications from a user-initiated button.
4. Use the in-app **Send test notification** action.
5. Add a medication reminder a few minutes ahead.
6. Close the web app and wait for delivery.
7. In `/admin` → **Production Readiness**, confirm the external worker heartbeat is current and `last_failed` is zero or explained.

Notification action buttons are best-effort across browsers/OS versions; opening the notification still routes to My Medications.

## v40 duplicate-delivery protection

- `push_worker.py` refuses to start unless `PUSH_WORKER_MODE=external`.
- The web service refuses to start its embedded scheduler when an active external heartbeat is detected.
- PostgreSQL uses an advisory delivery-cycle lock, so a brief deploy overlap between two workers skips one cycle instead of sending duplicate reminders.
- Admin → Production Readiness reports a configured/heartbeat mode mismatch as an error.
