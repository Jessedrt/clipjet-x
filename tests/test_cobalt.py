"""Cobalt is opt-in; no external service is contacted by these tests."""
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from clipjet import MediaUnavailable
from cobalt_client import CobaltUnavailable, configured_instance, resolve_with_cobalt
from youtube_video import YouTubeAccessBlocked, resolve_youtube_video

YOUTUBE_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
INSTANCE = "https://media.example.org"


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, count):
        return self.payload


class CobaltTests(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {"COBALT_API_URL": ""}), patch("cobalt_client.urlopen") as request:
            self.assertIsNone(configured_instance())
            with self.assertRaises(CobaltUnavailable):
                resolve_with_cobalt(YOUTUBE_URL)
            request.assert_not_called()

    def test_reject_unapproved_hosts_and_insecure_configuration(self):
        bad = ["http://media.example.org", "https://api.cobalt.tools",
               "https://127.0.0.1", "https://media.local", "https://user:password@media.example.org",
               "https://media.example.org:444", "https://media.example.org/path",
               "https://media.example.org/?query=1"]
        for url in bad:
            with self.subTest(url=url), patch.dict(os.environ, {"COBALT_API_URL": url}):
                self.assertIsNone(configured_instance())

    def test_uses_authorized_api_and_returns_only_same_host_mp4_tunnel(self):
        payload = {"status": "tunnel", "url": INSTANCE + "/tunnel?sig=abc", "filename": "clip.mp4"}
        with patch.dict(os.environ, {"COBALT_API_URL": INSTANCE, "COBALT_API_KEY": "test-only-key"}), \
             patch("cobalt_client.urlopen", return_value=FakeResponse(payload)) as send:
            video = resolve_with_cobalt(YOUTUBE_URL)
        self.assertEqual(video.url, payload["url"])
        request = send.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data)["videoQuality"], "360")
        self.assertIn("Api-Key test-only-key", str(request.headers))

    def test_rejects_unexpected_returned_urls_and_formats(self):
        for target, filename in [("https://attacker.invalid/tunnel", "clip.mp4"),
                                 ("https://media.example.org.attacker.invalid/tunnel", "clip.mp4"),
                                 ("http://media.example.org/tunnel", "clip.mp4"),
                                 (INSTANCE + "/tunnel", "clip.mp3")]:
            payload = {"status": "tunnel", "url": target, "filename": filename}
            with self.subTest(target=target), patch.dict(os.environ, {"COBALT_API_URL": INSTANCE}), \
                 patch("cobalt_client.urlopen", return_value=FakeResponse(payload)):
                with self.assertRaises(CobaltUnavailable):
                    resolve_with_cobalt(YOUTUBE_URL)

    def test_rejects_local_processing_and_oversized_files(self):
        cases = [{"status": "local-processing", "tunnel": [INSTANCE + "/tunnel"]},
                 {"status": "tunnel", "url": INSTANCE + "/tunnel", "filename": "clip.mp4",
                  "filesize": 20_000_000}]
        for result in cases:
            with patch.dict(os.environ, {"COBALT_API_URL": INSTANCE}), \
                 patch("cobalt_client.urlopen", return_value=FakeResponse(result)):
                with self.assertRaises(CobaltUnavailable):
                    resolve_with_cobalt(YOUTUBE_URL)

    def test_never_echoes_token_in_network_error(self):
        with patch.dict(os.environ, {"COBALT_API_URL": INSTANCE, "COBALT_API_KEY": "private-key"}), \
             patch("cobalt_client.urlopen", side_effect=HTTPError(INSTANCE, 401, "Unauthorized", None, None)):
            with self.assertRaises(CobaltUnavailable) as captured:
                resolve_with_cobalt(YOUTUBE_URL)
            self.assertNotIn("private-key", str(captured.exception))

    def test_youtube_challenge_uses_fallback_only_when_configured(self):
        from yt_dlp.utils import DownloadError
        with patch("yt_dlp.YoutubeDL") as extractor, \
             patch("youtube_video.pick_youtube_video") as direct, \
             patch("cobalt_client.resolve_with_cobalt") as fallback:
            extractor.return_value.__enter__.return_value.extract_info.side_effect = DownloadError(
                "Sign in to confirm you're not a bot")
            with patch.dict(os.environ, {"COBALT_API_URL": ""}):
                with self.assertRaises(YouTubeAccessBlocked):
                    resolve_youtube_video(YOUTUBE_URL)
            fallback.assert_not_called()
            with patch.dict(os.environ, {"COBALT_API_URL": INSTANCE}):
                fallback.return_value = object()
                self.assertIs(resolve_youtube_video(YOUTUBE_URL), fallback.return_value)
                fallback.assert_called_once_with(YOUTUBE_URL)
            direct.assert_not_called()

    def test_no_progressive_mp4_uses_configured_fallback(self):
        with patch("yt_dlp.YoutubeDL") as extractor, \
             patch("youtube_video.pick_youtube_video", side_effect=MediaUnavailable("missing")), \
             patch("cobalt_client.resolve_with_cobalt") as fallback, \
             patch.dict(os.environ, {"COBALT_API_URL": INSTANCE}):
            extractor.return_value.__enter__.return_value.extract_info.return_value = {"formats": []}
            fallback.return_value = object()
            self.assertIs(resolve_youtube_video(YOUTUBE_URL), fallback.return_value)
            fallback.assert_called_once_with(YOUTUBE_URL)


if __name__ == "__main__":
    unittest.main()
