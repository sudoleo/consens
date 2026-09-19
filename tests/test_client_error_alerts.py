from fastapi import FastAPI
import pytest
from fastapi.testclient import TestClient

from app.api.routers import client_errors
from app.core.rate_limit import limiter
from tests.frontend_order import group_of, loads_before


def _client(monkeypatch, captured):
    limiter.reset()
    monkeypatch.setattr(
        client_errors,
        "send_critical_error_notification",
        lambda report: captured.append(report) or {"status": "sent"},
    )
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(client_errors.router)
    return TestClient(app)


@pytest.mark.parametrize("kind", [
    "request_failed", "stream_read_failed", "stream_handler_failed",
    "stream_incomplete", "consensus_processing_failed", "private@example.test",
])
def test_consensus_failure_kind_is_allowlisted(monkeypatch, kind):
    captured = []
    response = _client(monkeypatch, captured).post("/api/client-errors", json={
        "type": "consensus_failed", "phase": "consensus_connection",
        "message": "private prompt", "failure_kind": kind, "path": "/app",
    })
    assert response.status_code == 202
    assert captured[0].get("failure_kind") == (None if "@" in kind else kind)
    assert "private" not in str(captured)


def test_client_error_report_is_accepted_and_sanitized(monkeypatch):
    captured = []
    client = _client(monkeypatch, captured)

    response = client.post(
        "/api/client-errors",
        headers={"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
        json={
            "type": "run_failed",
            "phase": "model_fanout",
            "message": "private.prompt@example.test token=browser-secret",
            "details": "OpenAI body: private provider response",
            "stack": "stack containing browser-secret",
            "path": "/s/private-share-id",
        },
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert captured == [{
        "source": "browser",
        "type": "run_failed",
        "phase": "model_fanout",
        "message": "A browser run failed.",
        "path": "/s/{share_id}",
    }]


def test_resource_failure_keeps_only_allowlisted_resource_class(monkeypatch):
    captured = []
    client = _client(monkeypatch, captured)

    response = client.post(
        "/api/client-errors",
        headers={"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
        json={
            "type": "resource_load_failed",
            "phase": "asset_load",
            "message": "Failed to load SCRIPT https://private.example/token",
            "details": "https://private.example/token",
            "resource_class": "jsdelivr_dependency",
            "path": "/app",
        },
    )

    assert response.status_code == 202
    assert captured == [{
        "source": "browser",
        "type": "resource_load_failed",
        "phase": "asset_load",
        "message": "A required browser script or stylesheet failed to load.",
        "path": "/app",
        "resource_class": "jsdelivr_dependency",
    }]


def test_resource_failure_drops_unknown_resource_class(monkeypatch):
    captured = []
    client = _client(monkeypatch, captured)

    response = client.post(
        "/api/client-errors",
        json={
            "type": "resource_load_failed",
            "message": "private runtime text",
            "resource_class": "private-resource@example.test",
            "path": "/app",
        },
    )

    assert response.status_code == 202
    assert "resource_class" not in captured[0]


def test_client_error_report_replaces_unknown_phase_and_route(monkeypatch):
    captured = []
    client = _client(monkeypatch, captured)

    response = client.post(
        "/api/client-errors",
        headers={"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
        json={
            "type": "unhandled_error",
            "phase": "secret-phase@example.test",
            "message": "private runtime text",
            "path": "/account/private-user-id",
        },
    )

    assert response.status_code == 202
    assert captured == [{
        "source": "browser",
        "type": "unhandled_error",
        "phase": "browser",
        "message": "An unhandled browser error occurred.",
        "path": "/other",
    }]


def test_client_error_report_rejects_cross_origin(monkeypatch):
    captured = []
    client = _client(monkeypatch, captured)

    response = client.post(
        "/api/client-errors",
        headers={"Origin": "https://attacker.example", "Sec-Fetch-Site": "cross-site"},
        json={"type": "unhandled_error", "message": "boom", "path": "/app"},
    )

    assert response.status_code == 403
    assert captured == []


def test_client_error_report_rejects_foreign_origin_without_fetch_metadata(
    monkeypatch,
):
    captured = []
    client = _client(monkeypatch, captured)

    response = client.post(
        "/api/client-errors",
        headers={"Origin": "https://attacker.example"},
        json={"type": "unhandled_error", "message": "boom", "path": "/app"},
    )

    assert response.status_code == 403
    assert captured == []


def test_error_reporter_loads_before_app_modules():
    # Must be in place before anything can throw: the head group is
    # render-blocking, the app group is deferred.
    assert group_of("error-reporter.js") == "head"
    assert loads_before("error-reporter.js", "app-core.js")


@pytest.mark.parametrize("asset,allowed", [
    ("dist/app.012345abcdef.js", True),
    ("dist/app.012345abcdef.css", True),
    ("vendor/katex/0.17.0/dist/katex.min.js", True),
    ("vendor/katex/0.17.0/dist/contrib/auto-render.min.js", True),
    ("js/analytics-opt-out.js", True),
    ("dist/app.012345abcdef.js?token=private", False),
    ("dist/app.private.js", False),
    ("https://example.test/static/dist/app.012345abcdef.js", False),
    ("vendor/private@example.test", False),
])
def test_asset_report_keeps_only_known_file_names(monkeypatch, asset, allowed):
    captured = []
    response = _client(monkeypatch, captured).post("/api/client-errors", json={
        "type": "resource_load_failed", "message": "private", "asset": asset,
    })
    assert response.status_code == 202
    assert captured[0].get("asset") == (asset if allowed else None)
    assert "private" not in str(captured)


@pytest.mark.parametrize("error_type", ["unhandled_error", "unhandled_rejection"])
def test_runtime_report_retains_only_safe_code_location(monkeypatch, error_type):
    captured = []
    response = _client(monkeypatch, captured).post("/api/client-errors", json={
        "type": error_type, "phase": "browser_runtime", "path": "/app",
        "message": "private@example.test", "stack": "private stack", "details": "private URL",
        "error_name": "TypeError", "script": "app.012345abcdef.js", "line": 1, "column": 18420,
    })
    assert response.status_code == 202
    assert captured[0]["error_name"] == "TypeError"
    assert captured[0]["script"] == "app.012345abcdef.js"
    assert captured[0]["line"] == 1
    assert captured[0]["column"] == 18420
    assert "private" not in str(captured)


@pytest.mark.parametrize("script", [
    "app.012345abcdef.js?token=private", "private@example.test", "app.012345abcdef.js/secret",
    "https://example.test/static/dist/app.012345abcdef.js",
])
def test_runtime_report_rejects_free_form_metadata(monkeypatch, script):
    captured = []
    response = _client(monkeypatch, captured).post("/api/client-errors", json={
        "type": "unhandled_error", "message": "private", "error_name": "private", "script": script,
        "line": 1, "column": 23,
    })
    assert response.status_code == 202
    assert not {"error_name", "script", "line", "column"}.intersection(captured[0])


@pytest.mark.parametrize("number", [True, 1.5, -1, 0, 10_000_001, "private"])
def test_runtime_report_rejects_invalid_coordinates(monkeypatch, number):
    captured = []
    response = _client(monkeypatch, captured).post("/api/client-errors", json={
        "type": "unhandled_error", "message": "private", "script": "head.012345abcdef.js",
        "line": number, "column": number,
    })
    assert response.status_code == 202
    assert "line" not in captured[0]
    assert "column" not in captured[0]
