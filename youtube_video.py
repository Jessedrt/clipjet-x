"""Conservative YouTube URL validation and metadata-only MP4 selection.

Telegram fetches media directly. Optional external providers require explicit
operator configuration; ClipJet never saves, proxies or uploads video bytes.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from clipjet import InvalidLink, MediaUnavailable, Video, MAX_REMOTE_BYTES, _estimated_size

VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")
YOUTUBE_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"})
SHORT_HOSTS = frozenset({"youtu.be", "www.youtu.be"})


class YouTubeAccessBlocked(MediaUnavailable):
    """YouTube required human verification or blocked this server's traffic."""


def canonical_youtube_video(raw: str) -> str:
    """Only single-video public URL forms; never follow arbitrary URLs."""
    if not isinstance(raw, str) or not raw or len(raw) > 2048 or any(c.isspace() or c == "\\" for c in raw):
        raise InvalidLink("Please send exactly one YouTube video or Shorts link.")
    try:
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").lower().rstrip(".")
        if (parsed.scheme != "https" or host not in YOUTUBE_HOSTS | SHORT_HOSTS
                or parsed.username or parsed.password or parsed.port not in (None, 443)
                or parsed.fragment):
            raise InvalidLink("Please send a normal HTTPS YouTube video or Shorts link.")
    except ValueError as exc:
        raise InvalidLink("That YouTube link is invalid.") from exc
    if host in SHORT_HOSTS:
        video_id = parsed.path.strip("/") if parsed.path.count("/") <= 2 else ""
        if not VIDEO_ID.fullmatch(video_id):
            raise InvalidLink("Please send a single youtu.be video link.")
    elif parsed.path == "/watch":
        try:
            ids = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=20).get("v", [])
        except ValueError as exc:
            raise InvalidLink("Invalid YouTube video link.") from exc
        if len(ids) != 1 or not VIDEO_ID.fullmatch(ids[0]):
            raise InvalidLink("Please send a YouTube watch link with one valid video ID.")
        video_id = ids[0]
    else:
        parts = parsed.path.strip("/").split("/")
        if len(parts) != 2 or parts[0] not in {"shorts", "live"} or not VIDEO_ID.fullmatch(parts[1]):
            raise InvalidLink("Please send a YouTube watch, Shorts, live or youtu.be video link.")
        video_id = parts[1]
    return f"https://www.youtube.com/watch?v={video_id}"


def verified_youtube_media_url(raw: object) -> bool:
    """Google-owned video delivery host only, no userinfo/ports/redirect input."""
    if not isinstance(raw, str):
        return False
    try:
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").lower().rstrip(".")
        return (parsed.scheme == "https" and host.endswith(".googlevideo.com")
                and not parsed.username and not parsed.password
                and parsed.port in (None, 443) and parsed.path == "/videoplayback"
                and bool(parsed.query) and not parsed.fragment)
    except ValueError:
        return False


def pick_youtube_video(info: dict) -> Video:
    """Use only a single progressive MP4 containing both audio and video."""
    if not isinstance(info, dict) or info.get("_type") in {"playlist", "multi_video"}:
        raise MediaUnavailable("No single public YouTube video found.")
    duration = info.get("duration")
    duration = float(duration) if isinstance(duration, (int, float)) and duration > 0 else None
    suitable = []
    for fmt in info.get("formats") or []:
        if not isinstance(fmt, dict) or fmt.get("ext") != "mp4":
            continue
        if not verified_youtube_media_url(fmt.get("url")):
            continue
        if fmt.get("protocol") not in (None, "https", "http") or fmt.get("fragments"):
            continue
        if fmt.get("vcodec") in (None, "none") or fmt.get("acodec") in (None, "none"):
            continue
        size = _estimated_size(fmt, duration)
        if size is not None and size > MAX_REMOTE_BYTES:
            continue
        height = fmt.get("height") or 0
        if not isinstance(height, (int, float)) or height > 720:
            continue
        if size is None and height > 360:
            continue
        suitable.append((int(height), size is not None, fmt["url"]))
    if not suitable:
        raise MediaUnavailable("No small progressive MP4 with audio was available.")
    suitable.sort(reverse=True)
    title = str(info.get("title") or "YouTube video").strip()[:160]
    return Video(url=suitable[0][-1], caption=title or "YouTube video")


def _optional_provider(url: str, original_error: MediaUnavailable) -> Video:
    """Prefer explicitly enabled SocialKit, retain any approved Cobalt fallback."""
    from socialkit_client import SocialKitUnavailable, is_enabled, resolve_with_socialkit
    from cobalt_client import configured_instance, resolve_with_cobalt

    if is_enabled():
        try:
            return resolve_with_socialkit(url)
        except SocialKitUnavailable:
            if not configured_instance():
                raise
    if configured_instance():
        return resolve_with_cobalt(url)
    raise original_error


def resolve_youtube_video(url: str) -> Video:
    """Extract public metadata, optionally trying configured alternative APIs."""
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError

    opts = {
        "quiet": True, "no_warnings": True, "skip_download": True,
        "noplaylist": True, "socket_timeout": 7, "retries": 1,
        "extractor_retries": 1, "ignoreerrors": False,
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as exc:
        # Do not expose yt-dlp's raw error: it can include URLs and account instructions.
        error = str(exc).lower().replace("’", "'")
        if ("confirm you're not a bot" in error or "sign in to confirm" in error
                or "unusual traffic" in error):
            return _optional_provider(url, YouTubeAccessBlocked("YouTube challenged the hosting server."))
        raise MediaUnavailable("YouTube did not expose accessible public MP4 metadata.") from None
    try:
        return pick_youtube_video(info)
    except MediaUnavailable:
        return _optional_provider(url, MediaUnavailable("No suitable small YouTube MP4 available."))
