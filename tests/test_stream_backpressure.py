import threading

import pytest

from app.services.llm import streaming
from app.services.llm.provider_runtime import ProviderCancellation


def test_slow_client_has_a_bounded_buffer_and_disconnect_releases_producer(monkeypatch):
    monkeypatch.setattr(streaming, "SSE_QUEUE_SIZE", 2)
    filled, closed = threading.Event(), threading.Event()
    produced = []

    def source():
        try:
            for i in range(10_000):
                produced.append(i)
                if i == 3:
                    filled.set()
                yield str(i)
        finally:
            closed.set()

    downstream = streaming.iter_sse_with_keepalive(source(), interval_seconds=.01)
    assert next(downstream) == "0"
    assert filled.wait(1)
    assert len(produced) <= 4  # one consumed, two buffered, one awaiting space
    downstream.close()
    assert closed.wait(1)
    assert len(produced) <= 4


def test_stalled_client_times_out_instead_of_holding_a_worker_forever(monkeypatch):
    monkeypatch.setattr(streaming, "SSE_QUEUE_SIZE", 1)
    monkeypatch.setattr(streaming, "SSE_BACKPRESSURE_TIMEOUT_SECONDS", .05)
    closed = threading.Event()
    cancellation = ProviderCancellation()

    def source():
        try:
            for i in range(10_000):
                yield str(i)
        finally:
            closed.set()

    downstream = streaming.iter_sse_with_keepalive(source(), interval_seconds=.01, cancellation=cancellation)
    assert next(downstream) == "0"
    assert closed.wait(1)
    assert list(downstream) == ["1"]


def test_bounded_buffer_preserves_data_before_terminal_errors(monkeypatch):
    monkeypatch.setattr(streaming, "SSE_QUEUE_SIZE", 1)

    def source():
        yield "first"
        yield "second"
        raise ValueError("provider stopped")

    downstream = streaming.iter_sse_with_keepalive(source(), interval_seconds=.01)
    assert next(downstream) == "first"
    assert next(downstream) == "second"
    with pytest.raises(ValueError, match="provider stopped"):
        next(downstream)
