"""Optional authorized Cobalt instance for small YouTube MP4s.

Never downloads video bytes or accepts a Cobalt URL from a Telegram message.
Requires the operator to explicitly configure their own/authorized instance.
"""
from __future__ import annotations

import ipaddress
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from clipjet import MAX_REMOTE_BYTES, MediaUnavailable, Video


class CobaltUnavailable(MediaUnavailable):
    """An authorized instance did not yield a Telegram-compatible video."""


def configured_instance() -> str | None:
    """Allow only an explicitly configured remote HTTPS API at its origin."""
    value = os.getenv("COBALT_API_URL", "").strip().rstrip("/")
    if not value:
        return None
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if (parsed.scheme != "https" or not host or "." not in host
                or host in {"api.cobalt.tools", "www.api.cobalt.tools"}
                or host.endswith((".local", ".localhost", ".internal"))
                or parsed.username or parsed.password or parsed.port not in (None, 443)
                or parsed.path or parsed.query or parsed.fragment):
            return None
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            return None
    except ValueError:
        return None
    return f"https://{host}"


def _approved_tunnel(media_url: object, instance: str) -> bool:
    if not isinstance(media_url, str) or len(media_url) > 8192:
        return False
    try:
        parsed = urlsplit(media_url)
        return (parsed.scheme == "https" and parsed.hostname == urlsplit(instance).hostname
                and not parsed.username and not parsed.password
                and parsed.port in (None, 443) and parsed.path.startswith("/")
                and parsed.path != "/" and not parsed.fragment)
    except ValueError:
        return False


def resolve_with_cobalt(video_url: str) -> Video:
    """Ask configured Cobalt for a 360p MP4 tunnel, then pass its URL to Telegram."""
    instance = configured_instance()
    if not instance:
        raise CobaltUnavailable("No authorized Cobalt API instance configured.")
    # video_url is already canonicalized by the strict YouTube validator.
    key = os.getenv("COBALT_API_KEY", "").strip()
    if any(c in key for c in "\r\n"):
        raise CobaltUnavailable("Invalid Cobalt configuration.")
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Api-Key {key}"
    payload = {"url": video_url, "videoQuality": "360", "youtubeVideoCodec": "h264",
               "youtubeVideoContainer": "mp4", "downloadMode": "auto", "alwaysProxy": True,
               "localProcessing": "disabled"}
    request = Request(instance + "/", data=json.dumps(payload).encode("utf-8"),
                      headers=headers, method="POST")
    try:
        with urlopen(request, timeout=12) as response:
            raw = response.read(65_537)
        if len(raw) > 65_536:
            raise ValueError("Oversized response")
        result = json.loads(raw)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        # HTTPError can include Authorization-bearing request details; never surface it.
        raise CobaltUnavailable("Authorized media service is unavailable.") from None
    if not isinstance(result, dict) or result.get("status") != "tunnel":
        raise CobaltUnavailable("Authorized media service returned no compatible MP4.")
    name = result.get("filename")
    target = result.get("url")
    if not isinstance(name, str) or not name.lower().endswith(".mp4"):
        raise CobaltUnavailable("Media service did not return an MP4 file.")
    if not _approved_tunnel(target, instance):
        raise CobaltUnavailable("Media service returned an unapproved URL.")
    size = result.get("filesize")
    if isinstance(size, (int, float)) and not isinstance(size, bool) and size > MAX_REMOTE_BYTES:
        raise CobaltUnavailable("Media service returned a file too large for URL delivery.")
    # Cobalt usually does not disclose file size; Telegram's 20MB URL limit still applies.
    return Video(url=target, caption="YouTube video")
