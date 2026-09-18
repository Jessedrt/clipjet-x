"""Restricted X post validation and direct-progressive MP4 selection.

No authenticated/private media, video downloading, or redirection of user URLs.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlsplit

MAX_REMOTE_BYTES = 18_000_000  # Buffer below Telegram's 20 MB URL-fetch ceiling.
POST_PATH = re.compile(r"^/(?:([A-Za-z0-9_]{1,15})/status|i/(?:web/)?status)/(\d{5,25})/?$", re.I)
SUPPORTED_HOSTS = frozenset({"x.com", "www.x.com", "mobile.x.com", "m.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com", "m.twitter.com"})
MEDIA_HOSTS = frozenset({"video.twimg.com"})


class InvalidLink(ValueError):
    """A user provided something other than an ordinary X post URL."""


class MediaUnavailable(Exception):
    """The extractor found no suitable direct public video."""


@dataclass(frozen=True)
class Video:
    url: str
    caption: str


def canonical_x_post(raw: str) -> str:
    if not isinstance(raw, str) or not raw or len(raw) > 2048 or any(c.isspace() for c in raw):
        raise InvalidLink("Please send exactly one X post link.")
    try:
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").lower().rstrip(".")
        if (parsed.scheme != "https" or host not in SUPPORTED_HOSTS or parsed.username
                or parsed.password or parsed.port not in (None, 443) or parsed.fragment):
            raise InvalidLink("Please send a normal https://x.com/.../status/... link.")
    except ValueError as exc:
        raise InvalidLink("That X link is invalid.") from exc
    match = POST_PATH.fullmatch(parsed.path)
    if not match:
        raise InvalidLink("Please send the link to an X post containing a video.")
    user, tweet_id = match.groups()
    if user:
        return f"https://x.com/{user}/status/{tweet_id}"
    return f"https://x.com/i/status/{tweet_id}"


def verified_media_url(raw: object) -> bool:
    if not isinstance(raw, str):
        return False
    try:
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").lower().rstrip(".")
        return (parsed.scheme == "https" and host in MEDIA_HOSTS and
                not parsed.username and not parsed.password and
                parsed.port in (None, 443) and parsed.path.lower().endswith(".mp4") and
                not parsed.fragment)
    except ValueError:
        return False


def _estimated_size(fmt: dict, duration: float | None) -> int | None:
    size = fmt.get("filesize") or fmt.get("filesize_approx")
    if isinstance(size, (int, float)) and size > 0:
        return int(size)
    tbr = fmt.get("tbr")
    if isinstance(tbr, (int, float)) and tbr > 0 and duration and duration > 0:
        return int(float(tbr) * 1000 * float(duration) / 8 * 1.2)
    return None


def pick_video(info: dict) -> Video:
    """Select an X-hosted direct MP4 (not HLS, DASH, or video-only)."""
    if not isinstance(info, dict):
        raise MediaUnavailable("No public media found.")
    if info.get("_type") in {"playlist", "multi_video"}:
        entries = info.get("entries") or []
        info = next((entry for entry in entries if isinstance(entry, dict) and entry.get("formats")), {})
    formats = info.get("formats") or []
    duration = info.get("duration")
    duration = float(duration) if isinstance(duration, (int, float)) and duration > 0 else None
    suitable = []
    for fmt in formats:
        if not isinstance(fmt, dict) or not verified_media_url(fmt.get("url")):
            continue
        if fmt.get("vcodec") == "none" or fmt.get("acodec") == "none":
            continue
        if fmt.get("protocol") not in (None, "http", "https"):
            continue
        size = _estimated_size(fmt, duration)
        if size is not None and size > MAX_REMOTE_BYTES:
            continue
        height = fmt.get("height") or 0
        if not isinstance(height, (int, float)):
            height = 0
        if size is None and height > 360:
            # Missing size/duration: use smaller variants, but URL fetch might still fail.
            continue
        suitable.append((int(height <= 720), height, size is not None, fmt["url"]))
    if not suitable:
        raise MediaUnavailable("No suitable MP4 under the URL-fetch size limit was found.")
    # Prefer higher quality <= 720, then a known size and a deterministic URL.
    suitable.sort(reverse=True)
    chosen_url = suitable[0][-1]
    title = str(info.get("title") or "Video from X").strip()[:160]
    return Video(url=chosen_url, caption=title or "Video from X")


def resolve_x_video(url: str) -> Video:
    """Extract metadata only. The server NEVER downloads or serves video bytes."""
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 7,
        "retries": 1,
        "extractor_retries": 1,
        "ignoreerrors": False,
        "extractor_args": {"twitter": {"api": ["syndication"]}},
    }
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as exc:
        raise MediaUnavailable("X did not provide publicly downloadable video metadata.") from exc
    return pick_video(info)
