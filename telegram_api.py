"""Small Telegram JSON API client; never log a URL containing the bot token."""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class TelegramError(RuntimeError):
    pass


def telegram_call(token: str, method: str, payload: dict, timeout: int = 12) -> dict:
    if method not in {"sendMessage", "sendVideo", "setWebhook", "getWebhookInfo", "deleteWebhook"}:
        raise ValueError("Unsupported Telegram method")
    request = Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(16384)
        result = json.loads(body)
    except HTTPError as exc:
        # Avoid leaking token via HTTPError's URL representation.
        raise TelegramError(f"Telegram returned HTTP {exc.code}") from None
    except (URLError, TimeoutError, ValueError) as exc:
        raise TelegramError("Telegram request failed") from None
    if not result.get("ok"):
        raise TelegramError(f"Telegram rejected {method} (code {result.get('error_code', 'unknown')})")
    return result
