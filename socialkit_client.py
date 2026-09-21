"""Opt-in SocialKit v1 resolver for small, authorized public YouTube videos.

The operator must explicitly opt in and supply their own access key. The
provider returns a signed S3 URL; Telegram fetches the file directly. This
module never downloads video bytes, follows media links, or logs credentials.
"""
from __future__ import annotations

import json
import math
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from clipjet import MAX_REMOTE_BYTES, MediaUnavailable, Video

API_ENDPOINT = "https://api.socialkit.dev/youtube/download"
# The provider documents a 10 MB maximum for its synchronous v1 endpoint.
SYNC_LIMIT_BYTES = min(MAX_REMOTE_BYTES, 10_000_000)
_BUCKET_HOST = re.compile(r"socialkit-downloads\.s3(?:[.-][a-z0-9-]+)?\.amazonaws\.com\Z")


class SocialKitUnavailable(MediaUnavailable):
    """The configured provider did not supply a safe, deliverable MP4 URL."""


def is_enabled() -> bool:
    """No credits can be spent merely by deploying code or setting a key."""
    return (os.getenv("SOCIALKIT_ENABLED", "").strip().lower() == "true"
            and bool(os.getenv("SOCIALKIT_ACCESS_KEY", "").strip()))


def approved_download_url(value: object) -> bool:
    """Accept only the provider's documented S3 download bucket."""
    if not isinstance(value, str) or not 0 < len(value) <= 8192:
        return False
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        return (parsed.scheme == "https" and bool(_BUCKET_HOST.fullmatch(host))
                and not parsed.username and not parsed.password
                and parsed.port in (None, 443) and bool(parsed.path.strip("/"))
                and not parsed.fragment)
    except ValueError:
        return False


def _validate_result(result: object) -> Video:
    if not isinstance(result, dict) or result.get("success") is not True:
        raise SocialKitUnavailable("Provider did not return a successful result.")
    data = result.get("data")
    if not isinstance(data, dict) or data.get("format") != "mp4":
        raise SocialKitUnavailable("Provider did not return an MP4.")
    size = data.get("fileSize")
    # An unknown or invalid size cannot be assumed Telegram-compatible.
    if (isinstance(size, bool) or not isinstance(size, (int, float))
            or not math.isfinite(size) or not 0 < size <= SYNC_LIMIT_BYTES):
        raise SocialKitUnavailable("Provider file size is missing or over 10 MB.")
    url = data.get("downloadUrl")
    if not approved_download_url(url):
        raise SocialKitUnavailable("Provider returned an unapproved download URL.")
    title = str(data.get("title") or "YouTube video").replace("\n", " ").replace("\r", " ").strip()[:160]
    return Video(url=url, caption=title or "YouTube video")


def resolve_with_socialkit(video_url: str) -> Video:
    """Submit one billed-at-most-on-success v1 request; no automatic retries."""
    if not is_enabled():
        raise SocialKitUnavailable("SocialKit is not explicitly enabled.")
    from youtube_video import canonical_youtube_video
    if canonical_youtube_video(video_url) != video_url:
        raise SocialKitUnavailable("Expected a canonical YouTube URL.")
    key = os.environ["SOCIALKIT_ACCESS_KEY"].strip()
    if "\r" in key or "\n" in key:
        raise SocialKitUnavailable("Invalid provider configuration.")
    request = Request(
        API_ENDPOINT,
        data=json.dumps({"url": video_url, "format": "mp4", "quality": "360p"}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json", "x-access-key": key},
        method="POST",
    )
    try:
        with urlopen(request, timeout=12) as response:
            raw = response.read(65_537)
        if len(raw) > 65_536:
            raise ValueError("Provider response too large")
        result = json.loads(raw)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError):
        # urllib errors may contain request URLs or credentials: never surface them.
        raise SocialKitUnavailable("Provider request failed or API key/quota is unavailable.") from None
    return _validate_result(result)
