from fastapi import FastAPI
import pytest
from fastapi.testclient import TestClient

from app.api.routers import client_errors
from app.core import sourcemaps
from app.core.rate_limit import limiter
from tests.frontend_order import group_of, loads_before
from tests.sourcemap_fixtures import write_map


def _client(monkeypatch, captured, *, commit=""):
    limiter.reset()
    # Der Commit kommt sonst aus dem Checkout und machte die exakten
    # Erwartungen unten vom Arbeitsverzeichnis abhaengig.
    monkeypatch.setattr(client_errors, "get_commit_short", lambda: commit)
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


# --- Source-Map-Aufloesung, Frames und Code-Fehlermeldungen -----------------

BUNDLE = "app.0123456789ab.js"


@pytest.fixture
def mapped_bundle(tmp_path, monkeypatch):
    sourcemaps.clear_cache()
    monkeypatch.setattr(sourcemaps, "DIST_DIR", tmp_path)
    write_map(tmp_path, BUNDLE, ["static/js/agent-chat.js", "static/js/app-core.js"], [
        [(0, 0, 0, 0), (100, 0, 119, 8), (400, 1, 39, 2)],
    ])
    yield
    sourcemaps.clear_cache()


def test_runtime_location_and_frames_resolve_through_the_source_map(monkeypatch, mapped_bundle):
    captured = []
    response = _client(monkeypatch, captured, commit="683a2fa").post("/api/client-errors", json={
        "type": "unhandled_error", "phase": "browser_runtime", "path": "/app/private-chat-id",
        "message": "Uncaught TypeError: Cannot read properties of undefined (reading 'turns')",
        "error_name": "TypeError", "script": BUNDLE, "line": 1, "column": 150,
        "bundle": BUNDLE,
        "frames": [
            [BUNDLE, 1, 150], [BUNDLE, 1, 401], ["head.012345abcdef.js", 1, 9],
            ["https://evil.example/x.js", 1, 1], [BUNDLE, "1", 2], [BUNDLE, 1, 0],
            [BUNDLE, 1, 1],  # sechster Eintrag: jenseits der fuenf erlaubten
        ],
    })
    assert response.status_code == 202
    report = captured[0]
    assert report["location"] == "static/js/agent-chat.js:120:9"
    assert report["frames"] == [
        "static/js/agent-chat.js:120:9",
        "static/js/app-core.js:40:3",
        "head.012345abcdef.js:1:9",  # ohne Map bleibt die Bundle-Koordinate
    ]
    assert report["bundle"] == BUNDLE
    assert report["commit"] == "683a2fa"
    assert report["path"] == "/app/{view}"
    assert report["error_message"] == "Cannot read properties of undefined (reading 'turns')"


@pytest.mark.parametrize("frames", ["app.0123456789ab.js:1:2", {"a": 1}, [["x"]], [[BUNDLE, 1]]])
def test_malformed_frames_are_dropped(monkeypatch, frames):
    captured = []
    response = _client(monkeypatch, captured).post("/api/client-errors", json={
        "type": "unhandled_error", "message": "private", "frames": frames,
    })
    assert response.status_code == 202
    assert "frames" not in captured[0]


def test_code_error_message_is_scrubbed(monkeypatch):
    captured = []
    response = _client(monkeypatch, captured).post("/api/client-errors", json={
        "type": "unhandled_rejection", "error_name": "SyntaxError",
        "message": ('SyntaxError: Unexpected token \'p\', "private question text with details" is not valid '
                    "JSON at https://private.example/path?token=abc for person@example.test "
                    "Authorization: Bearer abc.def.ghi " + "x" * 400),
    })
    assert response.status_code == 202
    message = captured[0]["error_message"]
    assert message.startswith("Unexpected token 'p', … is not valid JSON at [url] for [email]")
    assert len(message) <= 200
    for leaked in ("private", "person@", "abc.def.ghi", "token=abc"):
        assert leaked not in message


@pytest.mark.parametrize("error_name", ["Error", "SecurityError", "private"])
def test_other_error_messages_stay_generic(monkeypatch, error_name):
    captured = []
    response = _client(monkeypatch, captured).post("/api/client-errors", json={
        "type": "unhandled_error", "error_name": error_name, "message": "Provider said: private answer",
    })
    assert response.status_code == 202
    assert "error_message" not in captured[0]
    assert "private" not in str(captured)


@pytest.mark.parametrize("bundle", ["app.private.js", "https://x/app.0123456789ab.js", "app.0123456789ab.js?x"])
def test_bundle_name_is_allowlisted(monkeypatch, bundle):
    captured = []
    _client(monkeypatch, captured).post("/api/client-errors", json={
        "type": "run_failed", "message": "Failed", "bundle": bundle,
    })
    assert "bundle" not in captured[0]
