"""Server-Alerts: Fundort, Correlation-ID und Versand unabhaengig vom Response."""

from __future__ import annotations

import asyncio
import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

import main
from app.core import background_tasks, error_context
from app.core.observability import CorrelationFilter, CorrelationMiddleware
from app.services import error_alerts
from app.services.llm.provider_runtime import ProviderCancelled


class _CorrelationCapture(logging.Handler):
    """Wie die Produktions-Handler: der CorrelationFilter setzt ``corr``."""

    def __init__(self):
        super().__init__()
        self.addFilter(CorrelationFilter())
        self.records = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def alert_app(monkeypatch):
    captured = []
    monkeypatch.setattr(main, "dispatch_critical_error_notification", captured.append)
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware)
    app.add_exception_handler(Exception, main.handle_unexpected_exception)

    @app.get("/boom/{item_id}")
    def boom(item_id: str):
        return {}[item_id]

    @app.get("/stream")
    def stream():
        def events():
            yield "data: started\n\n"
            raise KeyError("private stream content")
        return StreamingResponse(events(), media_type="text/event-stream")

    handler = _CorrelationCapture()
    logging.getLogger().addHandler(handler)
    try:
        yield TestClient(app, raise_server_exceptions=False), captured, handler.records
    finally:
        logging.getLogger().removeHandler(handler)


def test_500_carries_the_correlation_id_of_the_log_line_and_the_alert(alert_app):
    client, captured, records = alert_app
    response = client.get("/boom/private-item-id")

    assert response.status_code == 500
    corr = response.headers["x-correlation-id"]
    assert corr.startswith("req-")
    report = captured[0]
    assert report["correlation_id"] == corr
    assert report["path"] == "GET /boom/{item_id}"
    assert report["status"] == 500
    assert report["type"] == "KeyError"
    assert report["frames"][0].startswith("tests/test_error_alerts.py:")
    assert report["frames"][0].endswith(":boom")
    assert "private-item-id" not in json.dumps(report)
    log = next(record for record in records if "Unhandled request exception" in record.getMessage())
    assert log.correlation_id == corr
    assert "test_error_alerts.py" in log.getMessage()


def test_alert_fires_when_the_stream_had_already_started(alert_app):
    client, captured, _records = alert_app
    response = client.get("/stream")

    # Der Status war schon gesendet; frueher hing der Alert als BackgroundTask
    # an einem 500er, der in diesem Fall nie ausgeliefert wurde.
    assert response.status_code == 200
    assert len(captured) == 1
    assert captured[0]["path"] == "GET /stream"
    assert "private stream content" not in json.dumps(captured[0])


def test_alert_frames_are_repo_relative_innermost_first_without_library_frames():
    def parse():
        return json.loads("{")  # Der innerste Frame liegt in der Standardbibliothek.

    def outer():
        return parse()

    try:
        outer()
    except ValueError as exc:
        frames = error_context.alert_frames(exc)

    assert [frame.rsplit(":", 1)[1] for frame in frames] == [
        "parse", "outer", "test_alert_frames_are_repo_relative_innermost_first_without_library_frames",
    ]
    assert all(frame.startswith("tests/test_error_alerts.py:") for frame in frames)


def test_alert_frames_are_capped():
    def recurse(depth):
        if depth == 0:
            raise IndexError("private")
        recurse(depth - 1)

    try:
        recurse(20)
    except IndexError as exc:
        assert len(error_context.alert_frames(exc)) == error_context.ALERT_FRAMES


def _raised(exc):
    try:
        raise exc
    except BaseException as caught:
        return caught


class _ProviderStatusError(RuntimeError):
    status_code = 400


@pytest.mark.parametrize("exc", [
    ProviderCancelled("stopped"), TimeoutError("slow"), ValueError("domain"),
    ConnectionError("network"), _ProviderStatusError("bad request"), RuntimeError("provider"),
])
def test_expected_failures_in_streams_do_not_alert(monkeypatch, exc):
    sent = []
    monkeypatch.setattr(error_alerts, "dispatch_critical_error_notification", sent.append)
    assert error_alerts.report_server_exception(_raised(exc), where="chat.consensus_stream") is None
    assert sent == []


@pytest.mark.parametrize("exc", [
    TypeError("private-detail"), KeyError("private-detail"),
    AttributeError("private-detail"), IndexError("private-detail"),
])
def test_programming_errors_in_streams_alert_with_location(monkeypatch, exc):
    sent = []
    monkeypatch.setattr(error_alerts, "dispatch_critical_error_notification",
                        lambda report: sent.append(report) or {"status": "dispatched"})
    result = error_alerts.report_server_exception(_raised(exc), where="chat.consensus_stream")

    assert result == {"status": "dispatched"}
    report = sent[0]
    assert report["source"] == "server"
    assert report["phase"] == "stream"
    assert report["path"] == "chat.consensus_stream"
    assert report["type"] == type(exc).__name__
    assert report["frames"][0].startswith("tests/test_error_alerts.py:")
    assert "private-detail" not in json.dumps(report)


def test_report_server_exception_never_raises(monkeypatch):
    def broken(_report):
        raise RuntimeError("telegram down")

    monkeypatch.setattr(error_alerts, "dispatch_critical_error_notification", broken)
    assert error_alerts.report_server_exception(_raised(TypeError("x")), where="agent.turn_stream") is None


def test_background_crash_alert_names_the_frames():
    alerts = []

    async def crash():
        {}["missing"]

    asyncio.run(background_tasks.supervise_background_task(
        "alert-frames-worker", crash, alert=alerts.append, restart=False,
    ))

    assert alerts[0]["type"] == "background_task_repeated_failure"
    assert alerts[0]["path"] == "alert-frames-worker"
    assert alerts[0]["frames"][0].startswith("tests/test_error_alerts.py:")
    assert alerts[0]["frames"][0].endswith(":crash")
    assert "instance" in alerts[0] and "commit" in alerts[0]
