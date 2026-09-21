import os
import unittest
from unittest.mock import patch

from api.webhook import process_update
from clipjet import Video


class YoutubeWebhookTests(unittest.TestCase):
    def test_youtube_routes_to_resolver(self):
        update={"update_id":923000001,"message":{"chat":{"type":"private","id":987643},"from":{"id":987643},"text":"https://youtu.be/dQw4w9WgXcQ"}}
        methods=[]
        def fake_call(token, method, payload, timeout=12):
            methods.append((method,payload))
            return {"ok":True}
        with patch.dict(os.environ, {"BOT_OWNER_ID":"987643"}), \
             patch("api.webhook.telegram_call", side_effect=fake_call), \
             patch("api.webhook.resolve_youtube_video", return_value=Video("https://rr.googlevideo.com/videoplayback?x=1","YT")) as resolver:
            process_update(update,"test-token")
        resolver.assert_called_once_with("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual([method for method,_ in methods], ["sendMessage","sendVideo"])
        self.assertEqual(methods[-1][1]["caption"], "YT")

    def test_start_advertises_both(self):
        update={"message":{"chat":{"type":"private","id":987645},"from":{"id":987645},"text":"/start"}}
        with patch.dict(os.environ, {"BOT_OWNER_ID":"987645"}), patch("api.webhook.telegram_call") as api:
            process_update(update,"test-token")
        text=api.call_args.args[2]["text"]
        self.assertIn("YouTube",text)
        self.assertIn("X/Twitter",text)


if __name__ == "__main__":
    unittest.main()
