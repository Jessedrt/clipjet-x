"""Test the actual entrypoint deployed by Vercel's Python preset."""
from io import BytesIO
import json
import os
import unittest
from unittest.mock import patch

from app import app


class WSGITests(unittest.TestCase):
    def request(self, method="GET", path="/api/webhook", data=b"{}", secret="test_secret_123456789"):
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "CONTENT_LENGTH": str(len(data)),
            "HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN": secret,
            "wsgi.input": BytesIO(data),
        }
        response = []
        body = b"".join(app(environ, lambda status, headers: response.append((status, headers))))
        return int(response[0][0][:3]), json.loads(body)

    def test_health(self):
        self.assertEqual(self.request()[1]["status"], "ready")
        self.assertEqual(self.request(path="/unknown")[0], 404)

    def test_requires_config_and_secret(self):
        with patch.dict(os.environ, {"BOT_TOKEN": "", "WEBHOOK_SECRET": ""}):
            self.assertEqual(self.request(method="POST")[0], 503)
        with patch.dict(os.environ, {"BOT_TOKEN": "fake", "WEBHOOK_SECRET": "test_secret_123456789"}):
            self.assertEqual(self.request(method="POST", secret="wrong")[0], 403)
            self.assertEqual(self.request(method="POST", data=b"broken")[0], 400)

    def test_dispatches_authorized_update(self):
        with patch.dict(os.environ, {"BOT_TOKEN": "fake", "WEBHOOK_SECRET": "test_secret_123456789"}), \
             patch("app.process_update") as worker:
            code, payload = self.request(method="POST", data=b'{"update_id":789}')
            self.assertEqual((code, payload), (200, {"ok": True}))
            worker.assert_called_once_with({"update_id": 789}, "fake")


if __name__ == "__main__":
    unittest.main()
