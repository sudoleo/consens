"""The Telegram webhook checks its secret before it reads the update (audit
2026-10-28): FastAPI parsed anyone's JSON body first, and a header with a
non-ASCII character made the secret check raise (500 and an alert)."""

import os
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import watch as watch_router
from app.core.rate_limit import limiter
from app.services import telegram_watch

SECRET = "test-webhook-secret"


@pytest.fixture
def client():
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(watch_router.router)
    with patch.dict(os.environ, {"TELEGRAM_WEBHOOK_SECRET": SECRET}):
        yield TestClient(app)


def test_a_wrong_secret_is_refused_before_the_body_is_parsed(client):
    with patch.object(watch_router.telegram_watch, "handle_update") as handle:
        # Not even JSON: before, FastAPI answered 422 from its body parsing.
        response = client.post("/api/telegram/webhook", content=b"{not json",
                               headers={"Content-Type": "application/json",
                                        "X-Telegram-Bot-Api-Secret-Token": "wrong"})
    assert response.status_code == 403
    handle.assert_not_called()


def test_a_valid_update_is_handled_and_a_broken_one_acknowledged(client):
    headers = {"X-Telegram-Bot-Api-Secret-Token": SECRET}
    with patch.object(watch_router.telegram_watch, "handle_update") as handle:
        assert client.post("/api/telegram/webhook", json={"update_id": 7}, headers=headers).status_code == 200
        handle.assert_called_once_with({"update_id": 7})
        for body in (b"{not json", b"[1, 2]"):
            response = client.post("/api/telegram/webhook", content=body,
                                   headers={**headers, "Content-Type": "application/json"})
            assert response.status_code == 200 and response.json() == {"ok": True}
        assert handle.call_count == 1


@pytest.mark.parametrize("candidate", ["tést-webhook-secret", "ÿ", "", None])
def test_a_non_ascii_secret_header_is_refused_not_raised(candidate):
    with patch.dict(os.environ, {"TELEGRAM_WEBHOOK_SECRET": SECRET}):
        assert telegram_watch.verify_webhook_secret(candidate) is False
        assert telegram_watch.verify_webhook_secret(SECRET) is True


def test_a_non_ascii_header_reaches_the_route_as_a_403(client):
    response = client.post("/api/telegram/webhook", json={"update_id": 1},
                           headers=[("X-Telegram-Bot-Api-Secret-Token", "tést".encode("latin-1"))])
    assert response.status_code == 403
