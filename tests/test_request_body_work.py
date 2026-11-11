"""What a request body may cost before anyone has shown a login.

The size limit (test_request_body_limits.py) does not bound the work of
parsing, nor how many big bodies wait in memory at once. Both are decided in
the same middleware, before the framework parses anything.
"""

import asyncio
import json
import random

import pytest

from app.core import request_limits
from app.core.request_limits import BigBodies, RequestBodyLimitMiddleware, client_of, json_elements_within


def post(body: bytes, *, path="/ask_openai", places=None, client="203.0.113.7"):
    """One POST through the middleware: its status, and the bodies the app got."""
    got = []
    sent = []

    async def inner(scope, receive, send):
        message = await receive()
        got.append(message.get("body"))
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    queue = [{"type": "http.request", "body": body, "more_body": False}]

    async def receive():
        return queue.pop(0) if queue else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": path, "client": (client, 1),
             "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]}
    asyncio.run(RequestBodyLimitMiddleware(inner, places=places or BigBodies())(scope, receive, send))
    return sent[0]["status"], got


@pytest.mark.parametrize("unit", [b"[],", b"1,", b'"",', b'{"a":1},', b'"\\"",'])
def test_a_body_of_countless_values_never_reaches_the_parser(unit):
    # A megabyte of them is hundreds of thousands of values: a quarter of a
    # second and 24 MB to parse, on a route that takes a megabyte from anyone.
    body = b"[" + unit * (900_000 // len(unit)) + b"0]"
    status, got = post(body, path="/agent")
    assert status == 413
    assert got == []


def test_a_real_body_passes_whatever_its_strings_hold():
    # Two files as base64, a text full of the bytes that count outside a
    # string (commas, brackets, braces, quotes, backslashes) and a long list
    # of sources: the largest body the app itself sends.
    text = '{"a": [1, 2, {"b": "c"}], "path": "C:\\\\x\\\\", "say": "\\"hi\\", she said"}, ' * 20_000
    payload = {"question": text, "id_token": "t",
               "attachments": [{"name": "a.pdf", "data": "A" * 7_000_000}, {"name": "b.png", "data": "B" * 5_000_000}],
               "sources": [{"url": f"https://example.org/{index}", "title": "T", "snippet": "S, with a [comma]"}
                           for index in range(3000)]}
    body = json.dumps(payload).encode()
    assert len(body) > 12_000_000
    status, got = post(body)
    assert status == 204
    assert got == [body]


def counted(value) -> int:
    """The commas, brackets and braces of ``value`` as JSON, outside its strings."""
    if isinstance(value, dict):
        return 1 + max(0, len(value) - 1) + sum(counted(item) for item in value.values())
    if isinstance(value, list):
        return 1 + max(0, len(value) - 1) + sum(counted(item) for item in value)
    return 0


def test_the_count_is_exact_whatever_the_strings_hold():
    rng = random.Random(7)
    words = ["plain", "a,b", "[x]", "{y}", 'say "hi"', "back\\slash", "ends in backslash\\", '\\"', "", "é,ü"]

    def build(depth):
        kind = rng.random()
        if depth == 0 or kind < 0.4:
            return rng.choice([rng.choice(words), rng.randint(-5, 5), None, True, 1.5])
        if kind < 0.7:
            return [build(depth - 1) for _ in range(rng.randint(0, 5))]
        return {rng.choice(words) + str(index): build(depth - 1) for index in range(rng.randint(0, 5))}

    for _ in range(300):
        document = [build(4) for _ in range(40)]
        body = json.dumps(document, ensure_ascii=rng.random() < 0.5).encode()
        exact = counted(document)
        assert json_elements_within(body, exact) is True, body[:200]
        assert json_elements_within(body, exact - 1) is False, body[:200]
        assert json_elements_within(bytearray(body), exact - 1) is False


def test_an_unfinished_string_is_left_to_the_parser():
    # No closing quote: the parser stops at its first byte past the counted
    # part; the count neither refuses the body nor reads it twice.
    body = b'{"a": "' + b'\\"' * 400_000
    assert json_elements_within(body, 1000) is True


def test_only_so_many_big_bodies_are_in_flight_and_every_place_comes_back():
    places = BigBodies(total=3, per_client=2)
    big = b'{"data":"' + b"A" * (request_limits.SMALL_REQUEST_BODY_BYTES + 10) + b'"}'

    async def scenario():
        release = asyncio.Event()
        statuses = []

        async def inner(scope, receive, send):
            await receive()
            await release.wait()
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        async def one(client):
            queue = [{"type": "http.request", "body": big, "more_body": False}]
            sent = []

            async def receive():
                return queue.pop(0) if queue else {"type": "http.disconnect"}

            async def send(message):
                sent.append(message)

            scope = {"type": "http", "method": "POST", "path": "/ask_openai", "client": ("10.0.0.1", 1),
                     "headers": [(b"content-length", str(len(big)).encode()), (b"cf-connecting-ip", client.encode())]}
            await RequestBodyLimitMiddleware(inner, places=places)(scope, receive, send)
            statuses.append((client, sent[0]["status"], dict(sent[0]["headers"]).get(b"retry-after")))

        first = [asyncio.create_task(one("198.51.100.1")) for _ in range(3)]
        other = asyncio.create_task(one("198.51.100.2"))
        await asyncio.sleep(0.2)
        # Two of the first client's three are in and its third was refused
        # at once, as a throttle; the other client has the last place.
        assert statuses == [("198.51.100.1", 429, b"5")]
        assert places.held == {"198.51.100.1": 2, "198.51.100.2": 1}
        late = asyncio.create_task(one("198.51.100.3"))
        await asyncio.sleep(0.1)
        assert statuses[-1] == ("198.51.100.3", 429, b"5")
        release.set()
        await asyncio.gather(*first, other, late)
        assert places.held == {}
        await one("198.51.100.3")
        assert statuses[-1][:2] == ("198.51.100.3", 204)

    asyncio.run(scenario())


def test_a_refused_big_body_is_never_read():
    places = BigBodies(total=0, per_client=0)
    read = []

    async def scenario():
        sent = []

        async def receive():
            read.append(True)
            return {"type": "http.request", "body": b"x", "more_body": False}

        async def send(message):
            sent.append(message)

        async def inner(scope, receive, send):
            raise AssertionError("refused before the app")

        scope = {"type": "http", "method": "POST", "path": "/ask_openai", "client": ("203.0.113.9", 1),
                 "headers": [(b"content-length", str(5 * 1024 * 1024).encode())]}
        await RequestBodyLimitMiddleware(inner, places=places)(scope, receive, send)
        return sent

    sent = asyncio.run(scenario())
    assert sent[0]["status"] == 429
    assert json.loads(sent[1]["body"])["code"] == "rate_limited"
    assert read == []


def test_a_small_body_needs_no_place():
    status, got = post(b'{"question":"hi"}', path="/agent", places=BigBodies(total=0, per_client=0))
    assert status == 204 and got == [b'{"question":"hi"}']


def test_a_place_is_per_customer_not_per_address():
    assert client_of({b"cf-connecting-ip": b"2001:db8:1:2:aaaa::1"}, None) == client_of(
        {b"cf-connecting-ip": b"2001:db8:1:2:bbbb::9"}, None)
    assert client_of({b"cf-connecting-ip": b"2001:db8:1:3::1"}, None) != client_of(
        {b"cf-connecting-ip": b"2001:db8:1:2::1"}, None)
    assert client_of({b"cf-connecting-ip": b"::ffff:203.0.113.5"}, None) == "203.0.113.5"
    # Cloudflare's header counts, never one a client can write before it.
    assert client_of({b"cf-connecting-ip": b"203.0.113.5", b"x-forwarded-for": b"10.0.0.1"},
                     ("127.0.0.1", 1)) == "203.0.113.5"
    assert client_of({}, ("127.0.0.1", 1)) == "127.0.0.1"
    assert client_of({b"cf-connecting-ip": b"not an address"}, None) == "not an address"


def test_a_big_body_that_does_not_arrive_gives_its_place_back(monkeypatch):
    monkeypatch.setattr(request_limits, "BIG_BODY_SECONDS", 0.05)
    places = BigBodies()
    sent = []

    async def scenario():
        async def receive():
            await asyncio.sleep(3600)

        async def send(message):
            sent.append(message)

        async def inner(scope, receive, send):
            raise AssertionError("an unfinished body must not reach the app")

        scope = {"type": "http", "method": "POST", "path": "/ask_openai", "client": ("203.0.113.9", 1),
                 "headers": [(b"content-length", str(5 * 1024 * 1024).encode())]}
        await RequestBodyLimitMiddleware(inner, places=places)(scope, receive, send)

    asyncio.run(scenario())
    assert sent[0]["status"] == 408
    assert places.held == {}
