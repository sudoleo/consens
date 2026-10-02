"""ASGI body cap must reject declared and chunked payloads before parsing."""

import asyncio
import pytest

from starlette.responses import StreamingResponse

from app.core.request_limits import RequestBodyLimitMiddleware
from app.core.request_limits import configured_max_request_body_bytes, DEFAULT_MAX_REQUEST_BODY_BYTES


def run_asgi(messages, *, headers=(), limit=8):
    received_by_app = []
    sent = []

    async def inner(scope, receive, send):
        received_by_app.append(await receive())
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    queue = list(messages)

    async def receive():
        if queue:
            return queue.pop(0)
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/json",
        "headers": list(headers),
    }
    asyncio.run(RequestBodyLimitMiddleware(inner, limit)(scope, receive, send))
    return sent, received_by_app


def test_declared_oversized_body_is_rejected_without_reading_or_parsing():
    sent, received = run_asgi(
        [{"type": "http.request", "body": b"ignored", "more_body": False}],
        headers=[(b"content-length", b"9")],
    )

    assert sent[0]["status"] == 413
    assert received == []


def test_chunked_body_is_counted_across_receive_messages():
    sent, received = run_asgi(
        [
            {"type": "http.request", "body": b"12345", "more_body": True},
            {"type": "http.request", "body": b"6789", "more_body": False},
        ]
    )

    assert sent[0]["status"] == 413
    assert received == []


def test_exact_limit_body_is_replayed_once_to_the_application():
    sent, received = run_asgi(
        [
            {"type": "http.request", "body": b"1234", "more_body": True},
            {"type": "http.request", "body": b"5678", "more_body": False},
        ]
    )

    assert sent[0]["status"] == 204
    assert received == [
        {"type": "http.request", "body": b"12345678", "more_body": False}
    ]


@pytest.mark.parametrize("value", [b"-1", b"invalid", b"1.2", b"", b"999999999999999999999999999999"])
def test_invalid_or_oversized_length_never_reaches_handler(value):
    sent, received = run_asgi([], headers=[(b"content-length", value)])
    assert received == []
    assert sent[0]["status"] == 413
    assert (b"cache-control", b"no-store") in sent[0]["headers"]


@pytest.mark.parametrize("value,expected", [(None, DEFAULT_MAX_REQUEST_BODY_BYTES), (" ", DEFAULT_MAX_REQUEST_BODY_BYTES), ("1024", 1024), ("33554432", 33554432)])
def test_request_limit_configuration_boundaries(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("MAX_REQUEST_BODY_BYTES", raising=False)
    else:
        monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", value)
    assert configured_max_request_body_bytes() == expected
    assert RequestBodyLimitMiddleware(None).max_body_bytes == expected


@pytest.mark.parametrize("value", ["-1", "0", "1023", "33554433", "NaN", "1.5"])
def test_invalid_configuration_fails_before_serving(monkeypatch, value):
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", value)
    with pytest.raises(RuntimeError, match="MAX_REQUEST_BODY_BYTES"):
        RequestBodyLimitMiddleware(None)


@pytest.mark.parametrize("partial", [b"", b"{}"])
def test_early_disconnect_does_not_replay_partial_body_as_complete(partial):
    messages = ([{"type":"http.request", "body":partial, "more_body":True}] if partial else [])
    sent, received = run_asgi([*messages, {"type":"http.disconnect"}])
    assert received == [{"type":"http.disconnect"}]


def test_non_http_scope_passes_through_without_reading_body():
    scope = {"type":"websocket"}
    seen = []
    async def receive():
        raise AssertionError("middleware must not read websocket frames")
    async def send(message):
        raise AssertionError("middleware must not respond to websocket")
    async def app(actual, actual_receive, actual_send):
        seen.append((actual, actual_receive, actual_send))
    asyncio.run(RequestBodyLimitMiddleware(app)(scope, receive, send))
    assert seen == [(scope, receive, send)]


def test_replayed_body_does_not_synthesize_disconnect_for_delayed_stream():
    sent = []
    request_messages = [
        {"type": "http.request", "body": b"{}", "more_body": False}
    ]

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/ask_openai",
        "raw_path": b"/ask_openai",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"content-length", b"2")],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    async def run_streaming_scenario():
        connection_closed = asyncio.Event()

        async def receive():
            if request_messages:
                return request_messages.pop(0)
            await connection_closed.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)

        async def inner(inner_scope, inner_receive, inner_send):
            assert await inner_receive() == {
                "type": "http.request",
                "body": b"{}",
                "more_body": False,
            }

            async def delayed_sse():
                await asyncio.sleep(0.01)
                yield b'event: final\ndata: {"response":"ok"}\n\n'

            response = StreamingResponse(
                delayed_sse(), media_type="text/event-stream"
            )
            await response(inner_scope, inner_receive, inner_send)

        await RequestBodyLimitMiddleware(inner, max_body_bytes=8)(
            scope, receive, send
        )

    asyncio.run(run_streaming_scenario())

    body_messages = [
        message for message in sent if message["type"] == "http.response.body"
    ]
    assert body_messages == [
        {
            "type": "http.response.body",
            "body": b'event: final\ndata: {"response":"ok"}\n\n',
            "more_body": True,
        },
        {"type": "http.response.body", "body": b"", "more_body": False},
    ]
