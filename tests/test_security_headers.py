import unittest

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from fastapi.testclient import TestClient

from app.core.security import CustomSecurityMiddleware


def _app():
    app = FastAPI()
    app.add_middleware(CustomSecurityMiddleware)

    @app.get("/two-cookies")
    def two_cookies():
        response = Response("ok")
        response.set_cookie("first", "1")
        response.set_cookie("second", "2")
        return response

    @app.get("/chats/own-cache")
    def own_cache():
        return JSONResponse({}, headers={"Cache-Control": "public, max-age=60"})

    @app.get("/agent/google/callback")
    def callback():
        return Response("ok", headers={"Content-Security-Policy": "script-src 'nonce-abc'"})

    return app


class SecurityHeadersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(_app())

    def _raw(self, path, name):
        response = self.client.get(path)
        return [value for key, value in response.headers.raw if key.lower() == name]

    def test_repeated_set_cookie_headers_survive(self):
        cookies = self._raw("/two-cookies", b"set-cookie")
        self.assertEqual(len(cookies), 2)
        self.assertTrue(cookies[0].startswith(b"first=1"))
        self.assertTrue(cookies[1].startswith(b"second=2"))

    def test_policy_headers_replace_route_headers_instead_of_doubling(self):
        self.assertEqual(self._raw("/chats/own-cache", b"cache-control"), [b"private, no-store"])
        self.assertEqual(len(self._raw("/two-cookies", b"content-security-policy")), 1)
        self.assertEqual(self._raw("/two-cookies", b"x-frame-options"), [b"DENY"])

    def test_oauth_callback_keeps_its_own_policy(self):
        self.assertEqual(
            self._raw("/agent/google/callback", b"content-security-policy"),
            [b"script-src 'nonce-abc'"],
        )
        self.assertEqual(self._raw("/agent/google/callback", b"referrer-policy"), [b"no-referrer"])


if __name__ == "__main__":
    unittest.main()
