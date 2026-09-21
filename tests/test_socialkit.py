"""Network-free regression tests for the opt-in short-video provider."""
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from socialkit_client import (
    SocialKitUnavailable, _validate_result, approved_download_url,
    is_enabled, resolve_with_socialkit,
)

GOOD_URL = "https://socialkit-downloads.s3.amazonaws.com/file.mp4?X-Amz-Signature=hi"
VIDEO = "https://www.youtube.com/watch?v=ABCDEFGHIJK"
RESPONSE = {"success": True, "data": {
    "format": "mp4", "fileSize": 5_000_000,
    "downloadUrl": GOOD_URL, "title": "Example",
}}


class SocialKitTests(unittest.TestCase):
    def test_disabled_by_default_even_when_key_exists(self):
        with patch.dict(os.environ, {"SOCIALKIT_ENABLED": "", "SOCIALKIT_ACCESS_KEY": ""}):
            self.assertFalse(is_enabled())
            with self.assertRaises(SocialKitUnavailable):
                resolve_with_socialkit(VIDEO)
        with patch.dict(os.environ, {"SOCIALKIT_ENABLED": "false", "SOCIALKIT_ACCESS_KEY": "key"}):
            self.assertFalse(is_enabled())

    def test_restricted_download_hosts(self):
        self.assertTrue(approved_download_url(GOOD_URL))
        bad = (
            "https://evil.com/x.mp4", "http://socialkit-downloads.s3.amazonaws.com/x",
            "https://socialkit-downloads.s3.amazonaws.com.evil.com/x",
            "https://user@socialkit-downloads.s3.amazonaws.com/x",
            "https://socialkit-downloads.s3.amazonaws.com:444/x",
            "https://socialkit-downloads.s3.amazonaws.com/",
            "https://socialkit-downloads.s3.amazonaws.com/file#fragment",
        )
        for url in bad:
            with self.subTest(url=url):
                self.assertFalse(approved_download_url(url))

    def test_rejects_oversize_unknown_and_non_mp4(self):
        self.assertEqual(_validate_result(RESPONSE).url, GOOD_URL)
        for alteration in ({"fileSize": None}, {"fileSize": 10_000_001},
                           {"fileSize": True}, {"format": "webm"},
                           {"downloadUrl": "https://evil.com/f"}):
            with self.subTest(alteration=alteration), self.assertRaises(SocialKitUnavailable):
                _validate_result({"success": True, "data": {**RESPONSE["data"], **alteration}})

    def test_request_method_authentication_and_payload(self):
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, length):
                return json.dumps(RESPONSE).encode()

        def fake_call(request, timeout):
            self.assertEqual(timeout, 12)
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request.full_url, "https://api.socialkit.dev/youtube/download")
            self.assertEqual(request.get_header("X-access-key"), "test-key")
            self.assertEqual(json.loads(request.data), {
                "url": VIDEO, "format": "mp4", "quality": "360p",
            })
            return Response()

        with patch.dict(os.environ, {"SOCIALKIT_ENABLED": "true", "SOCIALKIT_ACCESS_KEY": "test-key"}), \
             patch("socialkit_client.urlopen", side_effect=fake_call):
            self.assertEqual(resolve_with_socialkit(VIDEO).caption, "Example")

    def test_provider_errors_do_not_expose_url_or_key(self):
        with patch.dict(os.environ, {"SOCIALKIT_ENABLED": "true", "SOCIALKIT_ACCESS_KEY": "test-key"}), \
             patch("socialkit_client.urlopen", side_effect=HTTPError("https://sensitive", 403, "bad", None, None)):
            with self.assertRaises(SocialKitUnavailable) as raised:
                resolve_with_socialkit(VIDEO)
            self.assertNotIn("sensitive", str(raised.exception))
            self.assertNotIn("test-key", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
