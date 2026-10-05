"""A request that never reached the provider costs nothing; a sent one is estimated."""

import asyncio
import http.client
import json

import httpx
import pytest
import requests
from urllib3.exceptions import (
    MaxRetryError,
    NameResolutionError,
    NewConnectionError,
    ProtocolError,
    ReadTimeoutError,
)

from app.services import agent_quota
from app.services.llm import engines, provider_runtime, streaming, usage_meter
from app.services.llm.agent_client import AgentCompletion, metered_model
from app.services.llm.provider_dispatch import mark_not_dispatched, never_reached_provider
from app.services.llm.provider_runtime import (
    AnalysisBudget,
    ProviderCancellation,
    ProviderCancelled,
    bind_analysis_budget,
    bind_provider_cancellation,
)
from test_agent_delegation import make_loop
from test_agent_loop import loop_for, packet, transport
from test_agent_runs import UID, store  # noqa: F401  (pytest fixture)

PAYLOAD = {"model": "m", "messages": [{"role": "user", "content": "hello"}], "max_tokens": 1000}
URL = "https://openrouter.invalid/api/v1/chat/completions"


def _dns_failure():
    reason = NameResolutionError("openrouter.ai", None, OSError("getaddrinfo failed"))
    return requests.exceptions.ConnectionError(MaxRetryError(None, "/api", reason))


def _refused():
    reason = NewConnectionError(None, "Failed to establish a new connection: [Errno 111] refused")
    return requests.exceptions.ConnectionError(MaxRetryError(None, "/api", reason))


def _aborted_after_send():
    return requests.exceptions.ConnectionError(
        ProtocolError("Connection aborted.", http.client.RemoteDisconnected("closed")))


# --- classifier -------------------------------------------------------------

@pytest.mark.parametrize("error", [
    _dns_failure(),
    _refused(),
    requests.exceptions.ConnectTimeout("connect timed out"),
    httpx.ConnectError("dns"),
    httpx.ConnectTimeout("connect"),
    httpx.PoolTimeout("pool"),
    mark_not_dispatched(ProviderCancelled("stopped before send")),
    mark_not_dispatched(provider_runtime.AnalysisBudgetExceeded("deadline")),
], ids=lambda e: type(e).__name__)
def test_connect_phase_failures_never_reached_the_provider(error):
    assert never_reached_provider(error)


@pytest.mark.parametrize("error", [
    None,
    _aborted_after_send(),
    requests.exceptions.ConnectionError(ReadTimeoutError(None, "/api", "Read timed out.")),
    requests.exceptions.ConnectionError("bare"),
    requests.exceptions.ChunkedEncodingError("cut body"),
    requests.exceptions.ReadTimeout("read"),
    requests.exceptions.SSLError(MaxRetryError(None, "/api", OSError("tls"))),
    requests.exceptions.ProxyError(MaxRetryError(None, "/api", NewConnectionError(None, "proxy"))),
    httpx.ReadError("cut"),
    httpx.ReadTimeout("read"),
    httpx.RemoteProtocolError("closed"),
    httpx.WriteError("write"),
    ProviderCancelled("client left"),
    provider_runtime.AnalysisBudgetExceeded("deadline"),
    TimeoutError("stall"),
    RuntimeError("other"),
], ids=lambda e: type(e).__name__)
def test_everything_else_counts_as_started(error):
    assert not never_reached_provider(error)


# --- non-streaming answer (requests) -----------------------------------------

def _query_with(monkeypatch, error):
    def post(*args, **kwargs):
        raise error
    monkeypatch.setattr(engines.requests, "post", post)
    meter = usage_meter.UsageMeter()
    with usage_meter.bind_usage_meter(meter):
        result = engines.query_model("openai", "Q?", "key")
    assert result.get("error")
    return meter.close()


@pytest.mark.parametrize("error", [_dns_failure(), _refused(), requests.exceptions.ConnectTimeout("c")])
def test_query_model_connect_failure_is_free(monkeypatch, error):
    totals = _query_with(monkeypatch, error)
    assert totals["calls"] == 1 and totals["estimated"] == 0 and totals["missing_calls"] == 0


@pytest.mark.parametrize("error", [_aborted_after_send(), requests.exceptions.ReadTimeout("read")])
def test_query_model_failure_after_send_stays_estimated(monkeypatch, error):
    totals = _query_with(monkeypatch, error)
    assert totals["missing_calls"] == 1 and totals["estimated"] >= 500


# --- streamed answer, requests path (no analysis budget) ----------------------

class _CutStream:
    status_code = 200

    def iter_lines(self):
        yield ('data: ' + json.dumps({"choices": [{"delta": {"content": "Hi"}}]})).encode()
        yield b""
        raise requests.exceptions.ChunkedEncodingError("connection broken mid-body")

    def close(self):
        pass


def _stream_with(monkeypatch, post):
    monkeypatch.setattr(streaming.requests, "post", post)
    meter = usage_meter.UsageMeter()
    events = []
    with usage_meter.bind_usage_meter(meter), pytest.raises(Exception):
        for event in streaming._iter_openrouter_chunks(api_key="k", payload=PAYLOAD):
            events.append(event)
    return meter.close(), events


def test_stream_dns_failure_is_free(monkeypatch):
    def post(*args, **kwargs):
        raise _dns_failure()
    totals, _ = _stream_with(monkeypatch, post)
    assert totals["calls"] == 1 and totals["estimated"] == 0 and totals["missing_calls"] == 0


def test_stream_cut_mid_body_stays_estimated(monkeypatch):
    totals, events = _stream_with(monkeypatch, lambda *a, **k: _CutStream())
    assert {"type": "delta", "text": "Hi"} in events
    assert totals["missing_calls"] == 1 and totals["estimated"] >= 500


# --- httpx transports (judges and analysis-budgeted streams) ------------------

@pytest.fixture
def mock_httpx(monkeypatch):
    """Route provider_runtime's AsyncClient through an in-process transport."""
    calls = []

    def install(handler):
        real = httpx.AsyncClient

        def client(*args, **kwargs):
            def record(request):
                calls.append(request)
                return handler(request)
            return real(*args, transport=httpx.MockTransport(record), **kwargs)
        monkeypatch.setattr(provider_runtime.httpx, "AsyncClient", client)
        return calls
    return install


def _post_json(error_type=Exception):
    meter = usage_meter.UsageMeter()
    with usage_meter.bind_usage_meter(meter), pytest.raises(error_type):
        provider_runtime.cancellable_post_json(URL, json=PAYLOAD, headers={})
    return meter.close()


@pytest.mark.parametrize("error", [httpx.ConnectError("dns"), httpx.ConnectTimeout("connect")])
def test_judge_connect_failure_is_free(mock_httpx, error):
    def handler(request):
        raise error
    mock_httpx(handler)
    totals = _post_json(type(error))
    assert totals["calls"] == 1 and totals["estimated"] == 0 and totals["missing_calls"] == 0


def test_judge_read_timeout_stays_estimated(mock_httpx):
    def handler(request):
        raise httpx.ReadTimeout("no response")
    mock_httpx(handler)
    totals = _post_json(httpx.ReadTimeout)
    assert totals["missing_calls"] == 1 and totals["estimated"] >= 500


def test_judge_cancelled_before_dispatch_is_free_and_never_sent(mock_httpx):
    calls = mock_httpx(lambda request: httpx.Response(200, json={}))
    cancellation = ProviderCancellation()
    cancellation.cancel()
    with bind_provider_cancellation(cancellation):
        totals = _post_json(ProviderCancelled)
    assert calls == []
    assert totals["calls"] == 1 and totals["estimated"] == 0 and totals["missing_calls"] == 0


def test_judge_cancelled_while_waiting_for_the_provider_stays_estimated(mock_httpx):
    cancellation = ProviderCancellation()

    async def handler(request):
        cancellation.cancel()  # the client leaves after the request was sent
        await asyncio.sleep(5)
        return httpx.Response(200, json={})
    calls = mock_httpx(handler)
    with bind_provider_cancellation(cancellation):
        totals = _post_json(ProviderCancelled)
    assert len(calls) == 1
    assert totals["missing_calls"] == 1 and totals["estimated"] >= 500


class _BrokenBody(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield ('data: ' + json.dumps({"choices": [{"delta": {"content": "Hi"}}]}) + "\n\n").encode()
        raise httpx.ReadError("connection reset mid-body")


def _budgeted_stream():
    meter = usage_meter.UsageMeter()
    events = []
    with bind_analysis_budget(AnalysisBudget()), usage_meter.bind_usage_meter(meter), pytest.raises(Exception):
        for event in streaming._iter_openrouter_chunks(api_key="k", payload=PAYLOAD):
            events.append(event)
    return meter.close(), events


def test_budgeted_stream_connect_failure_is_free(mock_httpx):
    def handler(request):
        raise httpx.ConnectError("name resolution failed")
    mock_httpx(handler)
    totals, _ = _budgeted_stream()
    assert totals["calls"] == 1 and totals["estimated"] == 0 and totals["missing_calls"] == 0


def test_budgeted_stream_read_error_mid_body_stays_estimated(mock_httpx):
    mock_httpx(lambda request: httpx.Response(200, stream=_BrokenBody()))
    totals, events = _budgeted_stream()
    assert {"type": "delta", "text": "Hi"} in events
    assert totals["missing_calls"] == 1 and totals["estimated"] >= 500


def test_sse_lines_mark_a_stop_before_the_send_task_ran(mock_httpx):
    calls = mock_httpx(lambda request: httpx.Response(200, text="data: [DONE]\n\n"))
    cancellation = ProviderCancellation()
    cancellation.cancel()
    with bind_provider_cancellation(cancellation):
        lines = provider_runtime.cancellable_sse_lines(URL, json=PAYLOAD, headers={})
        with pytest.raises(ProviderCancelled) as raised:
            next(lines)
    assert calls == [] and never_reached_provider(raised.value)


# --- Agent ledger --------------------------------------------------------------

def test_agent_receipt_records_connect_failure_as_free_usage():
    model = metered_model("claude-haiku-4-5")
    value = AgentCompletion()
    value.record_rejection(httpx.ConnectError("dns"), model)
    assert value.usage["source"] == "not_dispatched"
    assert agent_quota.measured_tokens(value.usage) == 0

    streamed = AgentCompletion()
    streamed.text = "Partial"
    streamed.record_rejection(httpx.ConnectError("dns"), model)
    assert streamed.usage is None


@pytest.mark.parametrize("error", [httpx.ReadError("cut"), ProviderCancelled("client left")])
def test_agent_receipt_keeps_sent_requests_unknown(error):
    value = AgentCompletion()
    value.record_rejection(error, metered_model("claude-haiku-4-5"))
    assert value.usage is None


def _assert_free_receipt(store, loop):  # noqa: F811
    budget = agent_quota.snapshot(store.db, UID)
    assert budget["used"] == budget["reserved"] == budget["unknown"] == budget["estimated"] == 0
    assert budget["remaining"] == budget["limit"]
    saved = store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert saved["usage"]["source"] == "not_dispatched"


def test_agent_loop_step_that_never_connected_is_free(store, monkeypatch):  # noqa: F811
    transport(monkeypatch, [[httpx.ConnectError("name resolution failed")]])
    loop = loop_for(store)
    with pytest.raises(httpx.ConnectError):
        list(loop.run())
    _assert_free_receipt(store, loop)


def test_delegation_step_that_never_connected_is_free(store, monkeypatch):  # noqa: F811
    transport(monkeypatch, [[httpx.ConnectTimeout("connect")]])
    loop = make_loop(store)
    with pytest.raises(httpx.ConnectTimeout):
        list(loop.run())
    _assert_free_receipt(store, loop)


def test_delegation_step_cancelled_before_dispatch_is_free(store, monkeypatch):  # noqa: F811
    transport(monkeypatch, [[mark_not_dispatched(ProviderCancelled("stopped before send"))]])
    loop = make_loop(store)
    with pytest.raises(ProviderCancelled):
        list(loop.run())
    _assert_free_receipt(store, loop)


def test_delegation_step_cut_after_streaming_stays_estimated(store, monkeypatch):  # noqa: F811
    transport(monkeypatch, [[packet({"content": "Partial"}), httpx.ReadError("cut")]])
    loop = make_loop(store)
    with pytest.raises(httpx.ReadError):
        list(loop.run())
    budget = agent_quota.snapshot(store.db, UID)
    assert budget["estimated"] > 0 and budget["unknown"] > 0
