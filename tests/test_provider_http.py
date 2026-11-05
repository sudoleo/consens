"""The shared provider transport (provider_runtime.ProviderHTTP): one event
loop thread and one pooled httpx.AsyncClient per process. Connection reuse is
checked against a local keep-alive HTTP server (the peer port names the TCP
connection); cancellation, deadline and progress against httpx.MockTransport.
No provider is called."""

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time

import httpx
import pytest

from app.services.llm import provider_runtime as runtime
from app.services.llm.engines import _ProviderHTTPStatusError
from app.services.llm.provider_dispatch import never_reached_provider

EVENT = 'data: {"choices":[{"delta":{"content":"Hi"}}]}'


@pytest.fixture
def provider_http(monkeypatch):
    installed = []

    def install(transport=None):
        http = runtime.ProviderHTTP(transport=transport)
        monkeypatch.setattr(runtime, "_provider_http", http)
        installed.append(http)
        return http
    yield install
    for http in installed:
        http.shutdown()


def mock(handler):
    return httpx.MockTransport(handler)


def settle(http):
    """Wait for background releases (the drain after ``[DONE]``)."""
    for future in list(http._releasing):
        future.result(3)


class Server:
    """A keep-alive HTTP/1.1 server recording the peer port of each request."""

    def __init__(self):
        self.ports = []
        self.tail_delay = 0.0
        self.hold = threading.Event()
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                server.ports.append(self.client_address[1])
                if self.path == "/json":
                    body = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                try:
                    self.chunk(EVENT + "\n\n")
                    if self.path == "/hold":
                        server.hold.wait(3)
                    self.chunk("data: [DONE]\n\n")
                    if server.tail_delay:
                        time.sleep(server.tail_delay)
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                except OSError:
                    self.close_connection = True

            def chunk(self, text):
                data = text.encode()
                self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
                self.wfile.flush()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()

    def close(self):
        self.hold.set()
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server(monkeypatch):
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    value = Server()
    yield value
    value.close()


def read_until_done(url):
    """Read like AgentCompletion: stop at [DONE], then close the stream."""
    seen = []
    lines = runtime.cancellable_sse_lines(url, json={"stream": True}, headers={})
    try:
        for line in lines:
            seen.append(line)
            if line == "data: [DONE]":
                break
    finally:
        lines.close()
    return seen


def test_consecutive_streams_reuse_one_connection(provider_http, server):
    http = provider_http()
    # The chunked body's end arrives after [DONE]: the caller has already
    # stopped reading, the background drain returns the connection.
    server.tail_delay = 0.05
    with runtime.bind_analysis_budget(runtime.AnalysisBudget(unlimited=True)):
        first = read_until_done(server.url + "/sse")
        session = http.session()
        settle(http)
        second = read_until_done(server.url + "/sse")
        settle(http)
        # Read to the end of the body (no break): the connection stays as well.
        third = list(runtime.cancellable_sse_lines(server.url + "/sse", json={}, headers={}))
    assert first == second == [EVENT, "", "data: [DONE]"]
    assert third == [EVENT, "", "data: [DONE]", ""]
    assert len(server.ports) == 3 and len(set(server.ports)) == 1, "one TCP connection for all three"
    assert http.session() is session and session.thread.name == "provider-http"


def test_json_posts_share_the_pool_with_streams(provider_http, server):
    provider_http()
    with runtime.bind_analysis_budget(runtime.AnalysisBudget(unlimited=True)):
        assert runtime.cancellable_post_json(server.url + "/json", json={}, headers={})["choices"]
        assert runtime.cancellable_post_json(server.url + "/json", json={}, headers={})["choices"]
        assert read_until_done(server.url + "/sse")[-1] == "data: [DONE]"
    assert len(server.ports) == 3 and len(set(server.ports)) == 1


def test_stream_closed_before_its_end_drops_the_connection(provider_http, server):
    """A caller that stops mid-stream (cap, error, disconnect) closes the
    response at once: the provider sees the disconnect, the connection is
    not reused."""
    http = provider_http()
    with runtime.bind_analysis_budget(runtime.AnalysisBudget(unlimited=True)):
        lines = runtime.cancellable_sse_lines(server.url + "/hold", json={}, headers={})
        assert next(lines) == EVENT
        lines.close()
        assert not http._releasing
        server.hold.set()
        assert read_until_done(server.url + "/sse")[-1] == "data: [DONE]"
    assert len(server.ports) == 2 and server.ports[0] != server.ports[1]


def test_lines_split_across_chunks_like_aiter_lines(provider_http):
    chunks = [b"data: one\r", b"\n\r\ndata: t", b"wo\n", b"\n: comment\ndata: [DO", b"NE]\n\ntrailing"]

    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            for chunk in chunks:
                yield chunk
    provider_http(mock(lambda request: httpx.Response(200, stream=Body())))
    expected = list(httpx.Response(200, content=b"".join(chunks)).iter_lines())
    lines = list(runtime.cancellable_sse_lines("https://example.invalid/chat", json={}, headers={}))
    assert lines == expected == ["data: one", "", "data: two", "", ": comment", "data: [DONE]", "", "trailing"]


@pytest.mark.parametrize("stop", ["disconnect", "deadline"])
def test_stream_is_cancelled_while_waiting_for_headers(provider_http, stop):
    started, stopped = threading.Event(), threading.Event()
    cancellation = runtime.ProviderCancellation()
    budget = runtime.AnalysisBudget(seconds=5)

    async def waiting(request):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()
    provider_http(mock(waiting))

    def stop_while_waiting():
        assert started.wait(2)
        if stop == "disconnect":
            cancellation.cancel()
        else:
            budget.deadline = time.monotonic()
    worker = threading.Thread(target=stop_while_waiting)
    worker.start()
    try:
        with runtime.bind_provider_cancellation(cancellation), runtime.bind_analysis_budget(budget):
            with pytest.raises((runtime.ProviderCancelled, runtime.AnalysisBudgetExceeded)) as raised:
                next(runtime.cancellable_sse_lines("https://example.invalid/chat", json={}, headers={}))
    finally:
        worker.join(2)
    assert stopped.is_set(), "the HTTP task itself must be cancelled, not abandoned"
    # The request had left: the usage meter charges its estimate.
    assert not never_reached_provider(raised.value)


@pytest.mark.parametrize("call", ["stream", "post"])
def test_stop_before_dispatch_is_marked_not_dispatched(provider_http, call):
    requests = []
    provider_http(mock(lambda request: requests.append(request) or httpx.Response(200, json={})))
    cancellation = runtime.ProviderCancellation()
    cancellation.cancel()
    with runtime.bind_provider_cancellation(cancellation):
        with pytest.raises(runtime.ProviderCancelled) as raised:
            if call == "stream":
                next(runtime.cancellable_sse_lines("https://example.invalid/chat", json={}, headers={}))
            else:
                runtime.cancellable_post_json("https://example.invalid/chat", json={}, headers={})
    assert never_reached_provider(raised.value) and not requests


def test_stream_is_cancelled_during_body_read_and_closed(provider_http):
    closed, interrupted = threading.Event(), threading.Event()
    cancellation = runtime.ProviderCancellation()

    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield (EVENT + "\n\n").encode()
            try:
                await asyncio.Event().wait()
            finally:
                interrupted.set()

        async def aclose(self):
            closed.set()
    http = provider_http(mock(lambda request: httpx.Response(200, stream=Body())))
    with runtime.bind_provider_cancellation(cancellation):
        lines = runtime.cancellable_sse_lines("https://example.invalid/chat", json={}, headers={})
        assert [next(lines), next(lines)] == [EVENT, ""]
        threading.Timer(0.03, cancellation.cancel).start()
        with pytest.raises(runtime.ProviderCancelled) as raised:
            next(lines)
    assert interrupted.is_set() and closed.is_set() and not http._releasing
    assert not never_reached_provider(raised.value)


@pytest.mark.parametrize("stop", ["progress", "disconnect"])
def test_checks_run_before_every_line_of_a_chunk(provider_http, stop):
    """One network chunk carries several lines; a stop between two of them
    ends the stream as the per-line guarded read did."""
    provider_http(mock(lambda request: httpx.Response(200, content=(EVENT + "\n\n") * 3)))
    cancellation = runtime.ProviderCancellation()
    progress = runtime.ProviderProgressWatchdog(60)
    with runtime.bind_provider_cancellation(cancellation):
        lines = runtime.cancellable_sse_lines("https://example.invalid/chat", json={}, headers={},
                                              progress=progress)
        assert next(lines) == EVENT
        if stop == "progress":
            progress.deadline = time.monotonic()
        else:
            cancellation.cancel()
        with pytest.raises(TimeoutError if stop == "progress" else runtime.ProviderCancelled):
            next(lines)
        lines.close()


def test_progress_watchdog_ends_a_stream_of_heartbeats(provider_http):
    closed = threading.Event()

    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield (EVENT + "\n\n").encode()
            while True:
                await asyncio.sleep(0.01)
                yield b": OPENROUTER PROCESSING\n\n"

        async def aclose(self):
            closed.set()
    provider_http(mock(lambda request: httpx.Response(200, stream=Body())))
    progress = runtime.ProviderProgressWatchdog(0.15)
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="no progress"):
        # Heartbeats keep the socket busy; only the consumer's touch() counts.
        for _ in runtime.cancellable_sse_lines("https://example.invalid/chat", json={}, headers={},
                                               progress=progress):
            pass
    assert time.monotonic() - started < 2 and closed.is_set()


def test_a_hung_request_does_not_block_another(provider_http):
    release = threading.Event()

    async def handler(request):
        if request.url.path == "/hung":
            while not release.is_set():
                await asyncio.sleep(0.01)
        return httpx.Response(200, json={"ok": True})
    provider_http(mock(handler))
    cancellation = runtime.ProviderCancellation()
    errors = []

    def hung():
        with runtime.bind_provider_cancellation(cancellation):
            try:
                next(runtime.cancellable_sse_lines("https://example.invalid/hung", json={}, headers={}))
            except BaseException as exc:
                errors.append(exc)
    worker = threading.Thread(target=hung)
    worker.start()
    try:
        started = time.monotonic()
        assert runtime.cancellable_post_json("https://example.invalid/fast", json={}, headers={}) == {"ok": True}
        assert time.monotonic() - started < 1
    finally:
        cancellation.cancel()
        worker.join(2)
        release.set()
    assert isinstance(errors[0], runtime.ProviderCancelled)


def test_http_error_keeps_the_status_contract_and_closes(provider_http):
    closed = threading.Event()

    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{"error": {"code": 429, "message": "' + b"x" * 40_000 + b'"}}'

        async def aclose(self):
            closed.set()
    provider_http(mock(lambda request: httpx.Response(429, headers={"Retry-After": "7"}, stream=Body())))
    with pytest.raises(_ProviderHTTPStatusError) as raised:
        next(runtime.cancellable_sse_lines("https://example.invalid/chat", json={}, headers={}))
    assert raised.value.status_code == 429 and raised.value.retry_after == 7 and closed.is_set()


def test_a_dead_loop_thread_is_replaced(provider_http):
    http = provider_http(mock(lambda request: httpx.Response(200, json={"n": 1})))
    assert runtime.cancellable_post_json("https://example.invalid/chat", json={}, headers={}) == {"n": 1}
    dead = http.session()
    dead.loop.call_soon_threadsafe(dead.loop.stop)
    dead.thread.join(2)
    assert not dead.thread.is_alive()
    assert runtime.cancellable_post_json("https://example.invalid/chat", json={}, headers={}) == {"n": 1}
    assert http.session().thread is not dead.thread and http.session().thread.is_alive()


def test_a_call_from_a_running_event_loop_is_refused(provider_http):
    """As asyncio.run/run_until_complete refused before: blocking would stall
    FastAPI's loop, or deadlock on the provider loop itself."""
    http = provider_http(mock(lambda request: httpx.Response(200)))
    session = http.session()

    async def nested():
        http.call(session, lambda: asyncio.sleep(0))
    with pytest.raises(RuntimeError, match="running event loop"):
        asyncio.run_coroutine_threadsafe(nested(), session.loop).result(2)
    with pytest.raises(RuntimeError, match="running event loop"):
        asyncio.run(nested())
