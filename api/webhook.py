"""Vercel Python function: Telegram webhook for ClipJet X-only MVP."""
from __future__ import annotations

from collections import deque
from http.server import BaseHTTPRequestHandler
import hmac
import json
import logging
import os
from threading import Lock
from time import monotonic

from clipjet import InvalidLink, MediaUnavailable, canonical_x_post, resolve_x_video
from telegram_api import TelegramError, telegram_call

log = logging.getLogger("clipjet")
_seen = deque(maxlen=512)
_seen_set: set[int] = set()
_last_request: dict[int, float] = {}
_lock = Lock()


def duplicate_or_throttled(update_id: int, user_id: int) -> str | None:
    """Best-effort per-instance protection, NOT durable or globally shared."""
    with _lock:
        if update_id in _seen_set:
            return "duplicate"
        if len(_seen) == _seen.maxlen:
            old = _seen.popleft()
            _seen_set.discard(old)
        _seen.append(update_id)
        _seen_set.add(update_id)
        now = monotonic()
        if now - _last_request.get(user_id, -99999) < 20:
            return "cooldown"
        _last_request[user_id] = now
        return None


def process_update(update: dict, token: str) -> None:
    message = update.get("message")
    if not isinstance(message, dict):
        return
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    if chat.get("type") != "private":
        return
    chat_id, user_id = chat.get("id"), sender.get("id")
    if not isinstance(chat_id, int) or not isinstance(user_id, int):
        return
    owner = os.getenv("BOT_OWNER_ID", "").strip()
    if owner and str(user_id) != owner:
        telegram_call(token, "sendMessage", {"chat_id": chat_id, "text": "ClipJet is currently in private testing."})
        return
    text = message.get("text")
    if not isinstance(text, str):
        return
    command = text.split(maxsplit=1)[0].split("@", 1)[0].lower() if text.strip() else ""
    if command in {"/start", "/help"}:
        telegram_call(token, "sendMessage", {"chat_id": chat_id, "text": "🎬 ClipJet X — send ONE public X/Twitter post URL containing a video. I can try a small direct MP4. Only download media you're authorized to use. Private/restricted posts aren't supported."})
        return
    try:
        url = canonical_x_post(text.strip())
    except InvalidLink as exc:
        telegram_call(token, "sendMessage", {"chat_id": chat_id, "text": str(exc)})
        return
    state = duplicate_or_throttled(update.get("update_id", -1), user_id)
    if state == "duplicate":
        return
    if state == "cooldown":
        telegram_call(token, "sendMessage", {"chat_id": chat_id, "text": "Please wait 20 seconds between requests."})
        return
    telegram_call(token, "sendMessage", {"chat_id": chat_id, "text": "🔎 Checking the public X video…"})
    try:
        video = resolve_x_video(url)
    except MediaUnavailable:
        telegram_call(token, "sendMessage", {"chat_id": chat_id, "text": "I couldn't find a suitable public MP4. The post might be restricted, X may block extraction, or the video may exceed the small-file limit."})
        return
    except Exception:
        log.exception("Metadata extraction failed (URL and token not logged)")
        telegram_call(token, "sendMessage", {"chat_id": chat_id, "text": "X video lookup failed temporarily. Please try again later."})
        return
    try:
        telegram_call(token, "sendVideo", {
            "chat_id": chat_id,
            "video": video.url,
            "caption": video.caption,
            "supports_streaming": True,
        }, timeout=18)
    except TelegramError:
        log.warning("Telegram could not fetch selected remote MP4")
        telegram_call(token, "sendMessage", {"chat_id": chat_id, "text": "Telegram couldn't fetch that video directly. It may be too large, expired, or blocked. Try a different public post."})


class handler(BaseHTTPRequestHandler):
    def _json(self, code: int, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        self._json(200, {"service": "clipjet-x", "status": "ready"})

    def do_POST(self) -> None:
        secret = os.getenv("WEBHOOK_SECRET", "")
        token = os.getenv("BOT_TOKEN", "")
        if not secret or len(secret) < 16 or not token:
            self._json(503, {"ok": False, "error": "bot_not_configured"})
            return
        provided = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(provided, secret):
            self._json(403, {"ok": False})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 0 < length <= 16384:
            self._json(413, {"ok": False, "error": "invalid_payload_size"})
            return
        try:
            update = json.loads(self.rfile.read(length))
            if not isinstance(update, dict):
                raise ValueError("object required")
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"ok": False, "error": "invalid_json"})
            return
        try:
            process_update(update, token)
        except TelegramError:
            # Telegram retries non-2xx; best-effort in-memory de-dup is not durable.
            log.error("Telegram API action failed")
            self._json(502, {"ok": False})
            return
        self._json(200, {"ok": True})
