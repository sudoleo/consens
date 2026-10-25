"""What /prepare and /ask_* put into a Compare answer's system prompt.

Since 2026-10-25 a question asked through /ask_* continues no chat: the
browser asks these endpoints only for Compare, and follow-ups run in Agent.
A context a cached page still sends (``context``, chat or context ids) never
reaches the prompt.
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.core.config as cfg
from app.api.routers import chat as chat_router
from app.core.rate_limit import limiter
from usage_test_support import make_usage_repository


@pytest.fixture(autouse=True)
def reset_rate_limiter(monkeypatch):
    limiter.reset()
    # Signed-in runs without an own key go through the server's developer key.
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-server-key")
    repository, _ = make_usage_repository()
    monkeypatch.setattr(chat_router, "run_usage_repository", repository)
    monkeypatch.setattr(
        chat_router,
        "get_usage_run_key",
        lambda data: str(data.get("usage_run_key") or "test-run-key"),
    )
    yield repository


def make_client():
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(chat_router.router)
    return TestClient(app)


def free_model(provider: str) -> str:
    return cfg.FREE_DEFAULT_MODEL_BY_PROVIDER[provider]


def auth_patches(uid="uid-ask-prompt-tests", tier="free"):
    return (
        patch.object(chat_router, "verify_user_token", return_value=uid),
        patch.object(chat_router, "get_user_tier", return_value=tier),
    )


AUTH_HEADER = {"Authorization": "Bearer test-token"}


def test_a_sent_follow_up_context_never_reaches_the_prompt():
    client = make_client()
    captured = {}

    def fake_run_ask(provider, **kwargs):
        captured.update(kwargs)
        return {"ok": True}

    p1, p2 = auth_patches()
    with p1, p2, patch.object(chat_router, "_run_ask", side_effect=fake_run_ask):
        response = client.post(
            "/ask_gemini",
            headers=AUTH_HEADER,
            json={
                "question": "and how is it used?",
                "model": free_model("gemini"),
                "system_prompt": "BASE PROMPT",
                "context": {
                    "previous_question": "What is quantum entanglement?",
                    "previous_consensus": "Quantum entanglement is a correlation.",
                },
                "chat_id": "a" * 32,
                "turn_id": "b" * 32,
                "context_version_id": "c" * 32,
            },
        )
    assert response.status_code == 200
    assert "quantum" not in captured["system_prompt"].lower()
    assert captured["system_prompt"].startswith("BASE PROMPT\n\nPersistent Memory")


@pytest.mark.parametrize("custom", ["", "My personal answer instructions."])
def test_prepare_uses_admin_answer_default_unless_user_has_custom_instructions(monkeypatch, custom):
    from app.services import prompt_config

    config = prompt_config.defaults()
    config["prompts"]["answers"] = "Admin-configured answer instructions."
    monkeypatch.setattr(prompt_config, "get_config", lambda: config)
    client = make_client()
    p1, p2 = auth_patches()
    with p1, p2:
        response = client.post("/prepare", headers=AUTH_HEADER,
                               json={"question": "hello", "system_prompt": custom})
    assert response.status_code == 200
    actual = response.json()["system_prompt"]
    if custom:
        assert actual == custom
    else:
        assert "Admin-configured answer instructions." in actual
        assert "Current date:" in actual


@pytest.mark.parametrize("answer_prompt", ["x" * 10000, "😀" * 7000], ids=["char-limit", "utf8-limit"])
def test_maximum_admin_prompt_survives_prepare_to_ask_round_trip(monkeypatch, answer_prompt):
    from app.services import prompt_config

    config = prompt_config.defaults()
    # Prompts are code-owned; this pins the largest size they may grow to.
    assert len(answer_prompt) <= prompt_config.MAX_PROMPT_CHARS
    assert len(answer_prompt.encode("utf-8")) <= prompt_config.MAX_PROMPT_BYTES
    config["prompts"]["answers"] = answer_prompt
    monkeypatch.setattr(prompt_config, "get_config", lambda: config)
    captured = {}

    def fake_run_ask(provider, **kwargs):
        captured.update(kwargs)
        return {"ok": True}

    client = make_client()
    p1, p2 = auth_patches()
    with p1, p2, patch.object(chat_router, "_run_ask", side_effect=fake_run_ask):
        prepared = client.post("/prepare", headers=AUTH_HEADER,
                               json={"question": "hello", "system_prompt": ""})
        assert prepared.status_code == 200
        actual = prepared.json()["system_prompt"]
        response = client.post("/ask_gemini", headers=AUTH_HEADER, json={
            "question": "hello", "model": free_model("gemini"), "system_prompt": actual,
        })
    assert response.status_code == 200
    assert answer_prompt in captured["system_prompt"]
    assert captured["system_prompt"].count("Current date:") == 1


def test_ask_only_adds_the_memory_write_boundary():
    client = make_client()
    captured = {}

    def fake_run_ask(provider, **kwargs):
        captured.update(kwargs)
        return {"ok": True}

    p1, p2 = auth_patches(uid="uid-ask-prompt-none", tier="pro")
    with p1, p2, patch.object(chat_router, "_run_ask", side_effect=fake_run_ask):
        response = client.post(
            "/ask_gemini",
            headers=AUTH_HEADER,
            json={
                "question": "hello",
                "model": free_model("gemini"),
                "system_prompt": "BASE PROMPT",
            },
        )
    assert response.status_code == 200
    assert captured["system_prompt"].startswith("BASE PROMPT\n\nPersistent Memory")
    assert "Never say or imply that you saved, changed, or will remember" in captured[
        "system_prompt"
    ]
