import unittest

from starlette.requests import Request

from app.core.rate_limit import (
    ApiUidRateLimitExceeded,
    ApiUidRateLimiter,
    api_key_rate_key,
    client_ip_key,
)


def make_request(headers=None, client=("10.0.0.1", 80)):
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": client,
        "headers": [
            (key.lower().encode("latin-1"), value.encode("latin-1"))
            for key, value in (headers or {}).items()
        ],
    }
    return Request(scope)


class ClientIpKeyTests(unittest.TestCase):
    def test_without_proxy_header_uses_socket_address(self):
        request = make_request(client=("203.0.113.7", 1234))
        self.assertEqual(client_ip_key(request), "203.0.113.7")

    def test_forwarded_for_without_cloudflare_yields_client_ip(self):
        # Ohne Cloudflare (lokal, E2E-Proxy) bleibt XFF der Rückfall.
        request = make_request(headers={"X-Forwarded-For": "198.51.100.23"})
        self.assertEqual(client_ip_key(request), "198.51.100.23")

    def test_forwarded_for_chain_uses_first_entry(self):
        request = make_request(
            headers={"X-Forwarded-For": "198.51.100.23, 5.6.7.8, 1.2.3.4"}
        )
        self.assertEqual(client_ip_key(request), "198.51.100.23")

    def test_visitors_behind_the_same_proxy_get_distinct_buckets(self):
        first = make_request(
            headers={"X-Forwarded-For": "198.51.100.23, 172.16.0.9"}
        )
        second = make_request(
            headers={"X-Forwarded-For": "203.0.113.44, 172.16.0.9"}
        )
        self.assertNotEqual(client_ip_key(first), client_ip_key(second))

    def test_empty_header_falls_back(self):
        request = make_request(headers={"X-Forwarded-For": "  "},
                               client=("203.0.113.7", 1234))
        self.assertEqual(client_ip_key(request), "203.0.113.7")

    def test_cloudflare_connecting_ip_beats_spoofed_forwarded_for(self):
        # Render hängt an XFF nur an; ein vom Client gesetzter Eintrag steht
        # vorn. CF-Connecting-IP setzt Cloudflare selbst.
        request = make_request(
            headers={
                "X-Forwarded-For": "10.9.1.7, 198.51.100.23",
                "CF-Connecting-IP": "198.51.100.23",
            }
        )
        self.assertEqual(client_ip_key(request), "198.51.100.23")

    def test_spoofed_forwarded_for_shares_the_cloudflare_bucket(self):
        first = make_request(
            headers={
                "X-Forwarded-For": "10.9.1.7, 198.51.100.23",
                "CF-Connecting-IP": "198.51.100.23",
            }
        )
        second = make_request(
            headers={
                "X-Forwarded-For": "10.9.2.7, 198.51.100.23",
                "CF-Connecting-IP": "198.51.100.23",
            }
        )
        self.assertEqual(client_ip_key(first), client_ip_key(second))

    def test_blank_cloudflare_header_falls_back_to_forwarded_for(self):
        request = make_request(
            headers={"CF-Connecting-IP": " ", "X-Forwarded-For": "198.51.100.23"}
        )
        self.assertEqual(client_ip_key(request), "198.51.100.23")

    def test_api_key_bucket_hashes_secret(self):
        request = make_request(headers={"X-API-Key": "cns_live_super-secret"})
        bucket = api_key_rate_key(request)
        self.assertTrue(bucket.startswith("api-key:"))
        self.assertNotIn("super-secret", bucket)

    def test_invalid_api_key_bucket_falls_back_to_ip(self):
        request = make_request(
            headers={"X-API-Key": "random-value"}, client=("203.0.113.7", 1234)
        )
        self.assertEqual(api_key_rate_key(request), "ip:203.0.113.7")

    def test_uid_limiter_cannot_be_bypassed_with_another_key(self):
        limiter = ApiUidRateLimiter()
        limiter.check("same-user", "create", 1)
        with self.assertRaises(ApiUidRateLimitExceeded):
            limiter.check("same-user", "create", 1)
        limiter.check("other-user", "create", 1)


if __name__ == "__main__":
    unittest.main()
