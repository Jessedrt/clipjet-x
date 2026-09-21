"""WSGI entry point for Vercel's Python application preset.

Keep webhook processing in api.webhook so existing logic and tests stay shared.
"""
from __future__ import annotations

import hmac
import json
import logging
import os

from api.webhook import process_update
from telegram_api import TelegramError, telegram_call

log = logging.getLogger("clipjet")


def app(environ, start_response):
    """Serve the Telegram webhook as a standards-compliant WSGI application."""
    status, result = _dispatch(environ)
    payload = json.dumps(result).encode("utf-8")
    start_response(f"{status} {_STATUS[status]}", [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(payload))),
    ])
    return [payload]


_STATUS = {200: "OK", 400: "Bad Request", 403: "Forbidden", 404: "Not Found",
           405: "Method Not Allowed", 413: "Content Too Large",
           502: "Bad Gateway", 503: "Service Unavailable"}


def _bootstrap_webhook():
    """One-time deployment bootstrap; remove immediately after invoking.

    The destination is fixed in code and credentials are read exclusively from
    server-side Vercel environment variables, never echoed to the caller.
    """
    token = os.getenv("BOT_TOKEN", "").strip()
    secret = os.getenv("WEBHOOK_SECRET", "").strip()
    if not token or not (16 <= len(secret) <= 256) or any(
        (not c.isascii()) or (not c.isalnum() and c not in "_-") for c in secret
    ):
        return 503, {"service": "clipjet-x", "registration": "missing_configuration"}
    destination = "https://clipjet-x.vercel.app/api/webhook"
    try:
        telegram_call(token, "setWebhook", {
            "url": destination,
            "secret_token": secret,
            "allowed_updates": ["message"],
            "max_connections": 1,
            "drop_pending_updates": False,
        })
        info = telegram_call(token, "getWebhookInfo", {})["result"]
    except TelegramError as exc:
        # TelegramError never includes the token or other request credentials.
        return 502, {"service": "clipjet-x", "registration": "failed", "reason": str(exc)}
    if info.get("url") != destination:
        return 502, {"service": "clipjet-x", "registration": "url_mismatch"}
    return 200, {"service": "clipjet-x", "registration": "registered", "webhook_url": destination}


def _dispatch(environ):
    method = environ.get("REQUEST_METHOD", "GET")
    if method == "GET" and environ.get("PATH_INFO") == "/api/activate":
        return _bootstrap_webhook()
    if environ.get("PATH_INFO") not in ("/api/webhook", "/"):
        return 404, {"ok": False, "error": "not_found"}
    if method == "GET":
        return 200, {"service": "clipjet-x", "status": "ready"}
    if method != "POST" or environ.get("PATH_INFO") != "/api/webhook":
        return 405, {"ok": False, "error": "method_not_allowed"}

    secret = os.getenv("WEBHOOK_SECRET", "")
    token = os.getenv("BOT_TOKEN", "")
    if not secret or len(secret) < 16 or not token:
        return 503, {"ok": False, "error": "bot_not_configured"}
    provided = environ.get("HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN", "")
    if not hmac.compare_digest(provided, secret):
        return 403, {"ok": False}

    try:
        length = int(environ.get("CONTENT_LENGTH") or "0")
    except (ValueError, TypeError):
        length = 0
    if not 0 < length <= 16384:
        return 413, {"ok": False, "error": "invalid_payload_size"}
    try:
        raw = environ["wsgi.input"].read(length)
        update = json.loads(raw)
        if not isinstance(update, dict):
            raise ValueError("object required")
    except (ValueError, UnicodeDecodeError, TypeError, KeyError):
        return 400, {"ok": False, "error": "invalid_json"}
    try:
        process_update(update, token)
    except TelegramError:
        log.error("Telegram API action failed")
        return 502, {"ok": False}
    return 200, {"ok": True}
