"""Run locally *after* deployment. Requires BOT_TOKEN, WEBHOOK_SECRET, APP_URL."""
from __future__ import annotations

import os
import sys
from urllib.parse import urlsplit

from dotenv import load_dotenv

from telegram_api import TelegramError, telegram_call


def main() -> None:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    secret = os.getenv("WEBHOOK_SECRET", "").strip()
    app_url = os.getenv("APP_URL", "").strip().rstrip("/")
    if not token or not (16 <= len(secret) <= 256) or any(not (c.isalnum() and c.isascii()) and c not in "_-" for c in secret):
        sys.exit("Configure BOT_TOKEN and WEBHOOK_SECRET (16-256 ASCII letters/digits/_/-).")
    if len(sys.argv) > 1 and sys.argv[1] == "--info":
        info = telegram_call(token, "getWebhookInfo", {})["result"]
        print({k: info.get(k) for k in ("url", "pending_update_count", "last_error_message")})
        return
    if not app_url or (urlsplit(app_url).scheme != "https" or not urlsplit(app_url).hostname or urlsplit(app_url).username):
        sys.exit("APP_URL must be a public HTTPS Vercel deployment, e.g. https://clipjet-x.vercel.app")
    result = telegram_call(token, "setWebhook", {
        "url": app_url + "/api/webhook",
        "secret_token": secret,
        "allowed_updates": ["message"],
        "max_connections": 1,
        "drop_pending_updates": False,
    })
    print("Webhook registered:", bool(result["result"]))
    print("Check it: python setup_webhook.py --info")


if __name__ == "__main__":
    try:
        main()
    except TelegramError as exc:
        sys.exit(str(exc))
