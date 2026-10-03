import io
import json
import logging
import threading
from urllib.error import HTTPError

from app.services import telegram_notifier


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b"{}"


def test_seo_review_notification_is_sent_even_without_open_decisions(monkeypatch):
    captured = {}
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setenv("SEO_ADMIN_URL", "https://example.test/admin#seo")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(telegram_notifier, "urlopen", fake_urlopen)
    result = telegram_notifier.send_seo_review_notification({
        "status": "completed",
        "summary": "Everything is stable.",
        "pages": [{"page_id": "a"}],
        "groups": {"manual_improvement": []},
        "editorial_decisions": {},
        "proposed_topic_brief": None,
    })

    assert result["status"] == "sent"
    assert captured["url"].endswith("/bottest-token/sendMessage")
    assert "Everything is stable." in captured["payload"]["text"]
    assert "Editorial decisions open: 0" in captured["payload"]["text"]
    assert "https://example.test/admin#seo" in captured["payload"]["text"]


def test_seo_review_notification_names_the_judge_failure_and_findings(monkeypatch):
    captured = {}
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    # Only the critical-alert chat id is configured; the review must still land.
    monkeypatch.setenv("CRITICAL_ERROR_TELEGRAM_CHAT_ID", "456")

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data)
        return Response()

    monkeypatch.setattr(telegram_notifier, "urlopen", fake_urlopen)
    result = telegram_notifier.send_seo_review_notification({
        "status": "completed",
        "summary": "Reviewed 12 SEO pages.",
        "pages": [{"page_id": "a"}],
        "groups": {"manual_improvement": []},
        "editorial_decisions": {},
        "judge_called": False,
        "judge_error": "The portfolio judge returned invalid JSON.",
        "findings": {"positive": ["One page is being shown."], "negative": ["Most pages are commodity answers."]},
        "status_counts": {"emerging": 11, "opportunity": 1},
        "delta": {"comparable": True, "changed": [{"title": "Agent pricing", "from": "emerging", "to": "opportunity"}], "new_pages": []},
    })

    text = captured["payload"]["text"]
    assert result["status"] == "sent"
    assert captured["payload"]["chat_id"] == "456"
    assert "Portfolio judge: FAILED" in text
    assert "Most pages are commodity answers." in text
    assert "emerging 11" in text
    assert "Agent pricing: emerging -> opportunity" in text


def test_seo_review_notification_is_recorded_as_skipped_without_config(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("CRITICAL_ERROR_TELEGRAM_CHAT_ID", raising=False)
    result = telegram_notifier.send_seo_review_notification({"status": "error"})
    assert result["status"] == "skipped_not_configured"


def test_critical_error_notification_redacts_and_deduplicates(monkeypatch):
    captured = []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setenv("CRITICAL_ERROR_TELEGRAM_CHAT_ID", "456")
    telegram_notifier.reset_critical_state()

    def fake_urlopen(request, timeout):
        captured.append(json.loads(request.data))
        return Response()

    monkeypatch.setattr(telegram_notifier, "urlopen", fake_urlopen)
    report = {
        "source": "browser",
        "type": "run_failed",
        "phase": "model_fanout",
        "path": "/app",
        "message": "All models failed with token=secret-value",
        "details": "Authorization: Bearer abc.def.ghi",
    }

    first = telegram_notifier.send_critical_error_notification(report)
    second = telegram_notifier.send_critical_error_notification(report)

    assert first["status"] == "sent"
    assert second["status"] == "deduplicated"
    assert len(captured) == 1
    assert captured[0]["chat_id"] == "456"
    assert "secret-value" not in captured[0]["text"]
    assert "abc.def.ghi" not in captured[0]["text"]
    assert captured[0]["text"].startswith("🚨 consens.io critical error")


def test_critical_error_message_includes_safe_resource_class():
    text = telegram_notifier._critical_error_message({
        "source": "browser",
        "type": "resource_load_failed",
        "phase": "asset_load",
        "path": "/app",
        "resource_class": "app_bundle",
        "failure_kind": "stream_read_failed",
        "message": "A required browser script or stylesheet failed to load.",
    })
    assert "Failure: stream_read_failed" in text

    assert "Resource: app_bundle" in text


def test_runtime_locations_are_visible_and_deduplicated_separately(monkeypatch):
    captured = []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("CRITICAL_ERROR_TELEGRAM_CHAT_ID", "456")
    telegram_notifier.reset_critical_state()
    monkeypatch.setattr(telegram_notifier, "send_bot_message",
        lambda chat_id, text: captured.append(text) or {"status": "sent"})
    report = {"source": "browser", "type": "unhandled_error", "phase": "browser_runtime",
        "path": "/app", "message": "An unhandled browser error occurred.", "error_name": "TypeError",
        "script": "app.012345abcdef.js", "line": 1, "column": 42}
    assert telegram_notifier.send_critical_error_notification(report)["status"] == "sent"
    assert telegram_notifier.send_critical_error_notification(report)["status"] == "deduplicated"
    report["column"] = 84
    assert telegram_notifier.send_critical_error_notification(report)["status"] == "sent"
    assert "Error: TypeError" in captured[0]
    assert "Location: app.012345abcdef.js:1:42" in captured[0]
    assert "Location: app.012345abcdef.js:1:84" in captured[1]


def test_asset_names_are_visible_and_deduplicated_separately(monkeypatch):
    captured = []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("CRITICAL_ERROR_TELEGRAM_CHAT_ID", "456")
    telegram_notifier.reset_critical_state()
    monkeypatch.setattr(telegram_notifier, "send_bot_message",
        lambda chat_id, text: captured.append(text) or {"status": "sent"})
    report = {"source": "browser", "type": "resource_load_failed", "phase": "asset_load",
        "path": "/app", "resource_class": "app_bundle", "message": "A required resource failed.",
        "asset": "dist/app.012345abcdef.js"}
    assert telegram_notifier.send_critical_error_notification(report)["status"] == "sent"
    assert telegram_notifier.send_critical_error_notification(report)["status"] == "deduplicated"
    report["asset"] = "dist/firebase.abcdef012345.js"
    assert telegram_notifier.send_critical_error_notification(report)["status"] == "sent"
    assert "Asset: dist/app.012345abcdef.js" in captured[0]
    assert "Asset: dist/firebase.abcdef012345.js" in captured[1]


def test_new_user_registration_notification_is_pii_free(monkeypatch):
    captured = []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setenv("CRITICAL_ERROR_TELEGRAM_CHAT_ID", "456")
    monkeypatch.setenv("ENVIRONMENT", "staging")
    telegram_notifier._registration_seen.clear()

    def fake_urlopen(request, timeout):
        captured.append(json.loads(request.data))
        return Response()

    monkeypatch.setattr(telegram_notifier, "urlopen", fake_urlopen)
    result = telegram_notifier.send_new_user_registration_notification(
        "email/password", "private-firebase-uid"
    )
    duplicate = telegram_notifier.send_new_user_registration_notification(
        "email/password", "private-firebase-uid"
    )

    assert result["status"] == "sent"
    assert duplicate["status"] == "deduplicated"
    assert len(captured) == 1
    assert captured[0]["chat_id"] == "456"
    assert captured[0]["text"].startswith("👤 consens.io new user registered")
    assert "Method: email/password" in captured[0]["text"]
    assert "Environment: staging" in captured[0]["text"]
    assert "@" not in captured[0]["text"]


def test_new_user_registration_notification_is_skipped_without_config(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("CRITICAL_ERROR_TELEGRAM_CHAT_ID", raising=False)

    result = telegram_notifier.send_new_user_registration_notification(
        "email/password", "private-firebase-uid"
    )

    assert result["status"] == "skipped_not_configured"


# --- Fundort, Zustellung und Budgets der Critical-Alerts -------------------

def _configure(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:secretTokenValueAbcdefghijklmnop")
    monkeypatch.setenv("CRITICAL_ERROR_TELEGRAM_CHAT_ID", "456")
    telegram_notifier.reset_critical_state()


def _server_report(**overrides):
    report = {
        "source": "server", "type": "KeyError", "phase": "request",
        "message": "Unhandled server exception.", "path": "POST /consensus", "status": 500,
        "frames": ["app/services/llm/consensus_engine.py:2316:_apply_coverage",
                   "app/api/routers/chat.py:1958:consensus_event_source"],
        "commit": "683a2fa", "instance": "srv-abc-1", "correlation_id": "req-0123456789abcdef",
    }
    report.update(overrides)
    return report


def test_server_alert_names_location_build_and_correlation(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RENDER_SERVICE_NAME", "consensio-web")
    text = telegram_notifier._critical_error_message(_server_report())
    fingerprint = telegram_notifier.critical_fingerprint(_server_report())

    assert "Environment: consensio-web" in text
    assert "Instance: srv-abc-1" in text
    assert "Commit: 683a2fa" in text
    assert "Route: POST /consensus -> 500" in text
    assert "Correlation: req-0123456789abcdef" in text
    assert "Frames (innermost first):\napp/services/llm/consensus_engine.py:2316:_apply_coverage" in text
    assert text.splitlines()[-1] == (
        f"fix-context: fp={fingerprint} commit=683a2fa route=POST /consensus "
        "corr=req-0123456789abcdef frames=app/services/llm/consensus_engine.py:2316:_apply_coverage"
        " < app/api/routers/chat.py:1958:consensus_event_source"
    )
    assert len(fingerprint) == 8


def test_fix_context_survives_truncation_to_the_telegram_limit():
    text = telegram_notifier._critical_error_message(_server_report(
        details="d" * 5_000, stack="s" * 5_000,
        frames=[f"app/module_{index}.py:{index}:{'f' * 150}" for index in range(20)],
    ))
    assert len(text) <= 4096
    assert text.splitlines()[-1].startswith("fix-context: fp=")
    # Hoechstens acht Frames, auch wenn mehr geliefert werden.
    assert "app/module_7.py" in text and "app/module_8.py" not in text


def test_fingerprint_follows_the_innermost_frame_not_the_message():
    base = telegram_notifier.critical_fingerprint(_server_report())
    assert telegram_notifier.critical_fingerprint(_server_report(message="other")) == base
    assert telegram_notifier.critical_fingerprint(_server_report(correlation_id="req-x")) == base
    moved = _server_report(frames=["app/api/routers/chat.py:1:other"])
    assert telegram_notifier.critical_fingerprint(moved) != base


def test_environment_is_local_without_render(monkeypatch):
    for name in ("RENDER", "RENDER_SERVICE_NAME", "ENVIRONMENT"):
        monkeypatch.delenv(name, raising=False)
    assert telegram_notifier.alert_environment() == "local"
    monkeypatch.setenv("ENVIRONMENT", "staging")
    assert telegram_notifier.alert_environment() == "staging"
    monkeypatch.delenv("ENVIRONMENT")
    monkeypatch.setenv("RENDER", "true")
    assert telegram_notifier.alert_environment() == "production"


def test_failed_send_releases_the_slot_and_logs_the_telegram_description(monkeypatch, caplog):
    _configure(monkeypatch)
    answers = [
        b'{"ok": false, "error_code": 400, "description": "Bad Request: chat not found"}',
        b'{"ok": true, "result": {}}',
    ]

    class Body(Response):
        def __init__(self, raw):
            self.raw = raw

        def read(self):
            return self.raw

    monkeypatch.setattr(telegram_notifier, "urlopen", lambda request, timeout: Body(answers.pop(0)))
    with caplog.at_level(logging.WARNING):
        first = telegram_notifier.send_critical_error_notification(_server_report())
    second = telegram_notifier.send_critical_error_notification(_server_report())

    assert first["status"] == "failed_api"
    assert second["status"] == "sent"
    assert "chat not found" in caplog.text
    assert "secretTokenValue" not in caplog.text


def test_http_error_description_is_logged_without_the_token(monkeypatch, caplog):
    _configure(monkeypatch)

    def reject(request, timeout):
        raise HTTPError(request.full_url, 403, "Forbidden", {},
                        io.BytesIO(b'{"ok":false,"description":"Forbidden: bot was blocked by the user"}'))

    monkeypatch.setattr(telegram_notifier, "urlopen", reject)
    with caplog.at_level(logging.WARNING):
        result = telegram_notifier.send_critical_error_notification(_server_report())

    assert result["status"] == "failed_http"
    assert "bot was blocked by the user" in caplog.text
    assert "secretTokenValue" not in caplog.text
    # Freigegeben: der naechste Versuch darf wieder senden.
    assert telegram_notifier._critical_seen == {}


def test_suppressed_duplicates_are_counted_on_the_next_alert(monkeypatch):
    _configure(monkeypatch)
    sent = []
    monkeypatch.setattr(telegram_notifier, "send_bot_message",
                        lambda chat_id, text: sent.append(text) or {"status": "sent"})
    clock = [1_000.0]
    monkeypatch.setattr(telegram_notifier.time, "monotonic", lambda: clock[0])

    assert telegram_notifier.send_critical_error_notification(_server_report())["status"] == "sent"
    for _ in range(3):
        assert telegram_notifier.send_critical_error_notification(_server_report())["status"] == "deduplicated"
    clock[0] += telegram_notifier._CRITICAL_DEDUPE_SECONDS + 1
    assert telegram_notifier.send_critical_error_notification(_server_report())["status"] == "sent"

    assert "similar since last alert" not in sent[0]
    assert "(+3 similar since last alert)" in sent[1]


def test_browser_alerts_cannot_exhaust_the_server_budget(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(telegram_notifier, "send_bot_message",
                        lambda chat_id, text: {"status": "sent"})
    browser_limit = telegram_notifier._CRITICAL_RATE_LIMITS["browser"]
    statuses = [
        telegram_notifier.send_critical_error_notification({
            "source": "browser", "type": "unhandled_error", "path": "/app",
            "script": "app.012345abcdef.js", "line": 1, "column": index + 1,
        })["status"]
        for index in range(browser_limit + 2)
    ]
    assert statuses[:browser_limit] == ["sent"] * browser_limit
    assert statuses[browser_limit:] == ["rate_limited", "rate_limited"]
    assert telegram_notifier.send_critical_error_notification(_server_report())["status"] == "sent"


def test_dispatch_sends_on_its_own_thread(monkeypatch):
    _configure(monkeypatch)
    delivered = threading.Event()
    seen = {}

    def fake_send(chat_id, text):
        seen["thread"] = threading.current_thread().name
        seen["text"] = text
        delivered.set()
        return {"status": "sent"}

    monkeypatch.setattr(telegram_notifier, "send_bot_message", fake_send)
    result = telegram_notifier.dispatch_critical_error_notification(_server_report())

    assert result["status"] == "dispatched"
    assert delivered.wait(5)
    assert seen["thread"] == "critical-alert"
    assert "fix-context: fp=" in seen["text"]
    # Dedup greift schon beim Einreihen, ohne weiteren Thread.
    assert telegram_notifier.dispatch_critical_error_notification(_server_report())["status"] == "deduplicated"


def test_browser_alert_shows_mapped_location_and_bundle():
    text = telegram_notifier._critical_error_message({
        "source": "browser", "type": "unhandled_error", "path": "/app",
        "message": "An unhandled browser error occurred.", "error_name": "TypeError",
        "error_message": "Cannot read properties of undefined (reading 'x')",
        "script": "app.012345abcdef.js", "line": 1, "column": 4711,
        "location": "static/js/agent-chat.js:120:9", "bundle": "app.012345abcdef.js",
        "frames": ["static/js/agent-chat.js:120:9", "static/js/app-core.js:40:3"], "commit": "683a2fa",
    })
    assert "Error: TypeError: Cannot read properties of undefined (reading 'x')" in text
    assert "Location: static/js/agent-chat.js:120:9 (bundle app.012345abcdef.js:1:4711)" in text
    assert "Bundle: app.012345abcdef.js" in text
    last = text.splitlines()[-1]
    assert "bundle=app.012345abcdef.js" in last
    assert "loc=static/js/agent-chat.js:120:9" in last
    assert "frames=static/js/agent-chat.js:120:9 < static/js/app-core.js:40:3" in last
