"""Pipeline token metering in the transport layer and booking per operation."""

import json
from types import SimpleNamespace

import pytest

from app.services.llm import engines, provider_runtime, provider_transport, streaming, usage_meter
from app.services.llm.engines import _ProviderHTTPStatusError
from app.services.run_metering import OperationBooking, metered_events


PAYLOAD = {"model": "m", "messages": [{"role": "user", "content": "hello"}], "max_tokens": 1000}


def sse(*chunks, done=True):
    pairs = [(None, json.dumps(chunk)) for chunk in chunks]
    if done:
        pairs.append((None, "[DONE]"))
    return pairs


def test_streamed_request_reports_provider_usage(monkeypatch):
    sent = {}

    def fake_sse(*, api_key, request_payload):
        sent.update(request_payload)
        yield from sse({"choices": [{"delta": {"content": "Hi"}}]},
                       {"choices": [{"delta": {}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 120, "completion_tokens": 30,
                                  "completion_tokens_details": {"reasoning_tokens": 10}}})

    monkeypatch.setattr(streaming, "_openrouter_sse", fake_sse)
    meter = usage_meter.UsageMeter()
    with usage_meter.bind_usage_meter(meter):
        events = list(streaming._iter_openrouter_chunks(api_key="k", payload=PAYLOAD))
    assert sent["stream_options"] == {"include_usage": True}
    assert {"type": "delta", "text": "Hi"} in events
    totals = meter.close()
    assert totals["measured"] == 150 and totals["reasoning_tokens"] == 10
    assert totals["estimated"] == 0 and totals["calls"] == 1


def test_cut_stream_is_estimated_and_rejection_is_free(monkeypatch):
    def cut(*, api_key, request_payload):
        yield from sse({"choices": [{"delta": {"content": "Hi"}}]}, done=False)

    monkeypatch.setattr(streaming, "_openrouter_sse", cut)
    meter = usage_meter.UsageMeter()
    with usage_meter.bind_usage_meter(meter):
        list(streaming._iter_openrouter_chunks(api_key="k", payload=PAYLOAD))
    totals = meter.totals()
    assert totals["measured"] == 0 and totals["missing_calls"] == 1
    # Half of input estimate + output cap, like Agent's bounded estimate.
    assert totals["estimated"] >= 500

    def rejected(*, api_key, request_payload):
        raise _ProviderHTTPStatusError(429)
        yield  # pragma: no cover

    monkeypatch.setattr(streaming, "_openrouter_sse", rejected)
    other = usage_meter.UsageMeter()
    with usage_meter.bind_usage_meter(other), pytest.raises(_ProviderHTTPStatusError):
        list(streaming._iter_openrouter_chunks(api_key="k", payload=PAYLOAD))
    assert other.totals() == {**other.totals(), "measured": 0, "estimated": 0, "calls": 1}


def test_without_a_bound_meter_nothing_is_metered(monkeypatch):
    monkeypatch.setattr(streaming, "_openrouter_sse", lambda **_: iter(sse({"usage": {"prompt_tokens": 1, "completion_tokens": 1}})))
    assert usage_meter.current_meter() is None
    list(streaming._iter_openrouter_chunks(api_key="k", payload=PAYLOAD))
    assert usage_meter.start_call(PAYLOAD) is usage_meter.NULL_CALL


def test_non_streaming_judge_call_reports_usage(monkeypatch):
    async def fake_guard(awaitable, *_args, **_kwargs):
        awaitable.close()
        return SimpleNamespace(status_code=200, json=lambda: {
            "choices": [{"message": {"content": "{}"}}],
            "usage": {"prompt_tokens": 900, "completion_tokens": 100}})

    monkeypatch.setattr(provider_runtime, "_guard_provider_io", fake_guard)
    meter = usage_meter.UsageMeter()
    with usage_meter.bind_usage_meter(meter):
        provider_runtime.cancellable_post_json("https://example.invalid", json=PAYLOAD, headers={})
    assert meter.totals()["measured"] == 1000


def test_non_streaming_answer_reports_usage(monkeypatch):
    class Response:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "Answer"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 50, "completion_tokens": 25}}

        def close(self):
            pass

    monkeypatch.setattr(engines.requests, "post", lambda *a, **k: Response())
    meter = usage_meter.UsageMeter()
    with usage_meter.bind_usage_meter(meter):
        result = engines.query_model("openai", "Q?", "key")
    assert result.get("text") or result.get("response")
    assert meter.totals()["measured"] == 75


def test_parallel_fan_out_reports_into_the_callers_meter():
    def provider_call(provider, model, question, keys, tier, deep_think):
        usage_meter.current_meter().record({"prompt_tokens": 10, "completion_tokens": 5})
        return {"text": f"{provider} answer", "sources": [], "completion": "complete"}

    meter = usage_meter.UsageMeter()
    with usage_meter.bind_usage_meter(meter):
        answers = provider_transport.fan_out_provider_answers(
            question="Q", provider_models={"openai": "a", "mistral": "b"}, keys={},
            tier="free", deep_think=False, provider_call=provider_call)
    assert len(answers) == 2
    assert meter.totals()["measured"] == 30


class Repo:
    def __init__(self):
        self.booked = []

    def book_operation(self, uid, key, operation, *, measured, estimated, final=False):
        self.booked.append((operation, measured, estimated, final))
        return {"used": measured, "limit": 1000}


def test_operation_booking_books_once_and_survives_storage_errors():
    repo = Repo()
    booking = OperationBooking(repo, "uid", "run", "ask:openai")
    with booking.metering():
        usage_meter.current_meter().record({"prompt_tokens": 40, "completion_tokens": 2})
    assert booking.extras() == {"token_budget": {"used": 42, "limit": 1000}}
    assert booking.finish() == {"used": 42, "limit": 1000}
    assert repo.booked == [("ask:openai", 42, 0, False)]

    class Broken:
        def book_operation(self, *args, **kwargs):
            raise RuntimeError("firestore down")

    assert OperationBooking(Broken(), "uid", "run", "consensus").extras() == {}


def test_metered_events_put_the_booked_account_on_the_final_event_and_book_on_close():
    def events():
        usage_meter.current_meter().record({"prompt_tokens": 7, "completion_tokens": 3})
        yield {"type": "delta", "text": "x"}
        yield {"type": "final", "result": {"text": "x"}}

    repo = Repo()
    out = list(metered_events(events(), OperationBooking(repo, "uid", "run", "ask:openai")))
    assert out[-1]["extras"] == {"token_budget": {"used": 10, "limit": 1000}}

    def interrupted():
        usage_meter.current_meter().record({"prompt_tokens": 7, "completion_tokens": 3})
        yield {"type": "delta", "text": "x"}
        yield {"type": "delta", "text": "y"}

    repo = Repo()
    stream = metered_events(interrupted(), OperationBooking(repo, "uid", "run", "ask:mistral"))
    next(stream)
    stream.close()  # client left before the final event
    assert repo.booked == [("ask:mistral", 10, 0, False)]
    assert usage_meter.current_meter() is None
