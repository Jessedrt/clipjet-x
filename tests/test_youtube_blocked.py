"""YouTube bot-check failures must never be misreported as format or file-size errors."""
import unittest
from unittest.mock import patch

from youtube_video import YouTubeAccessBlocked, resolve_youtube_video
from api.webhook import process_update


class YouTubeBlockedTests(unittest.TestCase):
    def test_extractor_bot_challenge_is_classified(self):
        from yt_dlp.utils import DownloadError
        for message in (
            "Sign in to confirm you're not a bot.",
            "Sign in to confirm you’re not a bot.",
            "Unusual traffic from your computer network",
        ):
            with self.subTest(message=message), patch("yt_dlp.YoutubeDL") as youtube_dl:
                youtube_dl.return_value.__enter__.return_value.extract_info.side_effect = DownloadError(message)
                with self.assertRaises(YouTubeAccessBlocked):
                    resolve_youtube_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_bot_explains_block_without_requesting_credentials(self):
        update = {
            "update_id": 99887766,
            "message": {"chat": {"type": "private", "id": 123},
                        "from": {"id": 123},
                        "text": "https://youtu.be/dQw4w9WgXcQ"},
        }
        calls = []
        def fake_call(token, method, payload, timeout=12):
            calls.append((method, payload))
            return {"ok": True}
        with patch.dict("os.environ", {"BOT_OWNER_ID": "123"}), \
             patch("api.webhook.telegram_call", side_effect=fake_call), \
             patch("api.webhook.resolve_youtube_video", side_effect=YouTubeAccessBlocked("blocked")):
            process_update(update, "not-a-real-token")
        self.assertEqual([method for method, _ in calls], ["sendMessage", "sendMessage"])
        text = calls[-1][1]["text"].lower()
        self.assertIn("hosting server", text)
        self.assertIn("not a bot", text)
        self.assertIn("don't send", text)
        self.assertNotIn("too large", text)


if __name__ == "__main__":
    unittest.main()
