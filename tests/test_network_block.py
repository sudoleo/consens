"""The crawler wave from two clouds is refused before the app runs."""
import asyncio

import pytest

from app.core.network_block import BLOCKED_NETWORKS, NetworkBlockMiddleware, is_blocked


def _ask(path="/s/some-page-AbCdEfGhIjKlMnOp", *, connecting=None, forwarded=None, client=None, kind="http"):
    reached, sent = [], []

    async def app(scope, receive, send):
        reached.append(scope["path"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"page"})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    headers = []
    if connecting:
        headers.append((b"cf-connecting-ip", connecting.encode()))
    if forwarded:
        headers.append((b"x-forwarded-for", forwarded.encode()))
    scope = {"type": kind, "method": "GET", "path": path, "headers": headers, "client": client}
    asyncio.run(NetworkBlockMiddleware(app)(scope, receive, send))
    return reached, sent


@pytest.mark.parametrize("address", [
    "47.82.11.5", "47.79.51.200", "47.74.0.0", "47.87.255.255", "8.217.172.9", "8.208.0.1",
    "43.173.180.14", "43.153.62.1", "43.134.3.77", "43.128.0.0", "43.191.255.255",
    "49.51.183.2", "129.226.195.4", "161.120.177.30", "170.106.35.8",
])
def test_the_wave_gets_403_and_the_app_never_runs(address):
    reached, sent = _ask(connecting=address)

    assert reached == []
    assert sent[0]["status"] == 403
    assert sent[1]["body"] == b"Forbidden"
    assert dict(sent[0]["headers"])[b"content-length"] == str(len(sent[1]["body"])).encode()


@pytest.mark.parametrize("address", [
    # Right outside the refused ranges: 47.73 is Vodafone's customers, 47.128
    # Amazon, 8.230 Google, 162.120.188 Chrome's prefetch proxy.
    "47.73.255.255", "47.88.0.0", "47.128.36.9", "8.207.255.255", "8.224.0.0", "8.230.109.3",
    "43.127.255.255", "43.192.0.0", "49.50.255.255", "162.120.188.7",
    "87.145.20.1", "2a02:8108:1:2::3", "not-an-address", "",
])
def test_everyone_else_reaches_the_app(address):
    reached, sent = _ask(connecting=address)

    assert reached == ["/s/some-page-AbCdEfGhIjKlMnOp"]
    assert sent[0]["status"] == 200


def test_only_the_address_cloudflare_saw_decides():
    # X-Forwarded-For is whatever the client wrote in front (rate_limit.client_ip_key).
    assert _ask(connecting="87.145.20.1", forwarded="47.82.11.5")[1][0]["status"] == 200
    assert _ask(connecting="47.82.11.5", forwarded="87.145.20.1")[1][0]["status"] == 403


def test_the_keyed_api_stays_open_for_servers_in_those_clouds():
    reached, sent = _ask("/api/v1/consensus", connecting="47.82.11.5")

    assert reached == ["/api/v1/consensus"]
    assert sent[0]["status"] == 200


def test_other_connection_kinds_pass_untouched():
    reached, _sent = _ask(connecting="47.82.11.5", kind="websocket")

    assert reached == ["/s/some-page-AbCdEfGhIjKlMnOp"]


def test_the_list_holds_whole_allocations_only():
    # A single address or a /24 would chase a wave that changes its address
    # with every request.
    assert all(network.version == 4 and network.prefixlen <= 16 for network in BLOCKED_NETWORKS)
    assert is_blocked("47.82.11.5") and not is_blocked("47.128.36.9")


def test_main_app_refuses_before_any_other_layer():
    import main

    # Starlette runs the middleware added last first.
    assert main.app.user_middleware[0].cls is NetworkBlockMiddleware
