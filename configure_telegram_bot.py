"""Configure and verify the Telegram webhook for SymptoSense reminders."""
import os
import requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
ENV_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
SITE = os.getenv("SITE_URL", os.getenv("PUBLIC_BASE_URL", "https://symptosensehealth.com")).strip().rstrip("/")

if not TOKEN or not SECRET:
    raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET first.")

get_me = requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe", timeout=15)
get_me.raise_for_status()
me = get_me.json()
if not me.get("ok"):
    raise SystemExit(f"Telegram getMe failed: {me}")
actual_username = str((me.get("result") or {}).get("username") or "").strip().lstrip("@")
if not actual_username:
    raise SystemExit("Telegram bot has no username. Set one in BotFather first.")

print(f"Bot verified: @{actual_username}")
if ENV_USERNAME and ENV_USERNAME.lower() != actual_username.lower():
    print(f"WARNING: TELEGRAM_BOT_USERNAME is @{ENV_USERNAME}, but the token belongs to @{actual_username}.")
    print(f"Update Railway TELEGRAM_BOT_USERNAME to: {actual_username}")
elif not ENV_USERNAME:
    print(f"TIP: set TELEGRAM_BOT_USERNAME={actual_username} in Railway. Runtime can also resolve it automatically.")

webhook_url = SITE + "/api/telegram/webhook"
r = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/setWebhook",
    json={"url": webhook_url, "secret_token": SECRET, "allowed_updates": ["message"]},
    timeout=15,
)
r.raise_for_status()
print("setWebhook:", r.json())

info = requests.get(f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo", timeout=15)
info.raise_for_status()
info_data = info.json()
result = info_data.get("result") or {}
print("Webhook URL:", result.get("url") or "")
print("Pending updates:", result.get("pending_update_count", 0))
if result.get("last_error_message"):
    print("Last webhook error:", result.get("last_error_message"))
if (result.get("url") or "").rstrip("/") != webhook_url.rstrip("/"):
    raise SystemExit("Webhook URL verification failed.")
print("Telegram webhook is ready.")
