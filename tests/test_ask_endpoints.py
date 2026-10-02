"""Endpoint-Tests fuer die deduplizierten /ask_*-Handler (handle_ask).

Nagelt die gemeinsamen OpenRouter-Vertraege fest: Own-Key-Bypass der
Usage-Zaehlung, Auth-Verhalten und die Usage-Limit-Antworten.
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.core.config as cfg
from app.api.routers import chat as chat_router
from app.core.rate_limit import limiter
from app.services import agent_budget_config, agent_quota
from app.services.usage_repository import RunKind
from usage_test_support import make_usage_repository


@pytest.fixture(autouse=True)
def reset_rate_limiter(monkeypatch):
    # Die /ask_*-Routen sind mit 3-5/minute limitiert; mehrere Tests teilen
    # sich denselben In-Memory-Limiter (Key: Test-Client-IP).
    limiter.reset()
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


def auth_patches(uid="uid-ask-tests", tier="free"):
    return (
        patch.object(chat_router, "verify_user_token", return_value=uid),
        patch.object(chat_router, "get_user_tier", return_value=tier),
    )


AUTH_HEADER = {"Authorization": "Bearer test-token"}
PNG_ATTACHMENT = {
    "name": "pixel.png",
    "data": "iVBORw0KGgoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==",
}


def test_no_auth_error_is_uniform_across_model_families():
    client = make_client()

    response = client.post(
        "/ask_mistral",
        json={"question": "hello", "model": free_model("mistral")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "No auth provided."

    response = client.post(
        "/ask_gemini",
        json={"question": "hello", "model": free_model("gemini")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "No auth provided."


def test_own_keys_flag_without_openrouter_key_is_rejected():
    client = make_client()
    p1, p2 = auth_patches()
    with p1, p2:
        response = client.post(
            "/ask_gemini",
            headers=AUTH_HEADER,
            json={
                "question": "hello",
                "model": free_model("gemini"),
                "useOwnKeys": "true",
            },
        )
    assert response.status_code == 400
    assert response.json()["detail"] == "Missing user OpenRouter API key."


@pytest.mark.parametrize("tier", ["free", "plus"])
def test_reasoning_switch_is_open_to_every_tier_and_keeps_the_selected_model(tier):
    """The Reasoning switch (wire name deep_search) has no Pro gate and never
    swaps in the family's Pro model: the same selected model just thinks
    longer, with the larger reasoning output cap."""
    client = make_client()
    p1, p2 = auth_patches(tier=tier)
    model = free_model("grok")
    with p1, p2, patch.object(chat_router, "_run_ask", return_value={"ok": True}) as run:
        response = client.post(
            "/ask_grok",
            headers=AUTH_HEADER,
            json={
                "question": "hello",
                "model": model,
                "deep_search": "true",
                "useOwnKeys": True,
                "openrouter_key": "sk-user-key",
            },
        )
    assert response.status_code == 200
    kwargs = run.call_args.kwargs
    assert kwargs["deep_search"] is True
    assert kwargs["model"] == model
    assert kwargs["model"] != cfg.PROVIDERS["grok"].pro_model
    assert kwargs["max_tokens"] == max(
        cfg.get_output_token_limit(tier), cfg.LIMITS["reasoning_max_tokens"]
    )


def test_plus_cannot_ask_a_premium_model():
    client = make_client()
    premium = next(
        model for model in cfg.PROVIDERS["grok"].models if model in cfg.PREMIUM_MODELS
    )
    p1, p2 = auth_patches(tier="plus")
    with p1, p2:
        response = client.post(
            "/ask_grok",
            headers=AUTH_HEADER,
            json={"question": "hello", "model": premium},
        )
    assert response.status_code == 403


def test_plus_may_attach_a_file_and_gets_the_plus_quota():
    client = make_client()
    p1, p2 = auth_patches(tier="plus")
    with p1, p2, patch.object(chat_router, "_run_ask", return_value={"ok": True}) as run:
        response = client.post(
            "/ask_grok",
            headers=AUTH_HEADER,
            json={
                "question": "describe it",
                "model": free_model("grok"),
                "useOwnKeys": True,
                "openrouter_key": "sk-user-key",
                "attachments": [PNG_ATTACHMENT],
            },
        )
    assert response.status_code == 200
    assert len(run.call_args.kwargs["attachments"]) == 1
    extras = run.call_args.kwargs["extras"]
    assert extras["tier"] == "plus"
    # is_pro_user bleibt das Modell-Flag.
    assert extras["is_pro_user"] is False
    # Und das Wortlimit kommt aus dem eigenen Plus-Wert.
    assert cfg.get_word_limit("plus") == cfg.LIMITS["plus_max_words"]


def test_glm_attachment_support_depends_on_the_selected_model():
    client = make_client()
    p1, p2 = auth_patches(tier="pro")
    with p1, p2, patch.object(chat_router, "_run_ask", return_value={"ok": True}) as run:
        flash = client.post(
            "/ask_glm",
            headers=AUTH_HEADER,
            json={
                "question": "describe it",
                "model": cfg.GLM_BASE_MODEL,
                "useOwnKeys": True,
                "openrouter_key": "sk-user-key",
                "attachments": [PNG_ATTACHMENT],
            },
        )
        # Reasoning no longer swaps in GLM 5.3 (text-only): the selected
        # multimodal Flash model keeps reading the attachment.
        reasoning = client.post(
            "/ask_glm",
            headers=AUTH_HEADER,
            json={
                "question": "describe it",
                "model": cfg.GLM_BASE_MODEL,
                "deep_search": True,
                "useOwnKeys": True,
                "openrouter_key": "sk-user-key",
                "attachments": [PNG_ATTACHMENT],
            },
        )
        pro = client.post(
            "/ask_glm",
            headers=AUTH_HEADER,
            json={
                "question": "describe it",
                "model": cfg.PROVIDERS["glm"].pro_model,
                "useOwnKeys": True,
                "openrouter_key": "sk-user-key",
                "attachments": [PNG_ATTACHMENT],
            },
        )

    assert flash.status_code == 200
    assert reasoning.status_code == 200
    assert pro.status_code == 400
    assert pro.json()["detail"] == "GLM 5.3 cannot read attachments."
    assert run.call_count == 2


def test_ask_muse_serves_the_meta_family_and_gates_its_pro_model():
    """Die Route heisst nach dem Produkt, die Familie nach dem Anbieter."""
    client = make_client()
    p1, p2 = auth_patches(tier="plus")
    with p1, p2, patch.object(chat_router, "_run_ask", return_value={"ok": True}) as run:
        free = client.post(
            "/ask_muse",
            headers=AUTH_HEADER,
            json={
                "question": "describe it",
                "model": cfg.MUSE_BASE_MODEL,
                "useOwnKeys": True,
                "openrouter_key": "sk-user-key",
                "attachments": [PNG_ATTACHMENT],
            },
        )
        premium = client.post(
            "/ask_muse",
            headers=AUTH_HEADER,
            json={"question": "hello", "model": cfg.MUSE_PRO_MODEL},
        )

    assert free.status_code == 200
    assert run.call_args.args[0].key == "meta"
    # Glimmer liest Bilder, ist also kein Anhang-Sonderfall wie DeepSeek.
    assert len(run.call_args.kwargs["attachments"]) == 1
    assert premium.status_code == 403


def test_megabyte_style_one_word_question_is_rejected_before_provider_work():
    client = make_client()
    p1, p2 = auth_patches()
    with p1, p2, patch.object(chat_router, "_run_ask") as provider_call:
        response = client.post(
            "/ask_openai",
            headers=AUTH_HEADER,
            json={
                "question": "x" * (chat_router.MAX_QUESTION_CHARS + 1),
                "model": free_model("openai"),
                "openrouter_key": "own-key",
            },
        )

    assert response.status_code == 400
    provider_call.assert_not_called()


def test_multibyte_question_and_system_prompt_obey_utf8_byte_caps():
    client = make_client()
    p1, p2 = auth_patches()
    with p1, p2, patch.object(chat_router, "_run_ask") as provider_call:
        question_response = client.post(
            "/ask_openai",
            headers=AUTH_HEADER,
            json={
                "question": "🙂" * 4_001,
                "model": free_model("openai"),
                "openrouter_key": "own-key",
            },
        )
        prompt_response = client.post(
            "/ask_openai",
            headers=AUTH_HEADER,
            json={
                "question": "small",
                "system_prompt": "🙂" * 8_001,
                "model": free_model("openai"),
                "openrouter_key": "own-key",
            },
        )

    assert question_response.status_code == 400
    assert prompt_response.status_code == 400
    provider_call.assert_not_called()


def _ledger(repository, uid):
    config = agent_budget_config.get_config(repository._db)
    period = agent_quota.period_key(config)
    return repository._db.documents.get(("users", uid, "chat_state", "agent_tokens_" + period)) or {}


def test_usage_limit_blocks_developer_key_path(reset_rate_limiter):
    client = make_client()
    uid = "uid-limit-reached"
    # The day's tokens are spent: a run that skipped /prepare is not admitted.
    admission = reset_rate_limiter.admission("free")
    reset_rate_limiter.reserve(uid, "spent", RunKind.REGULAR, admission)
    reset_rate_limiter.consume(uid, "spent")
    reset_rate_limiter.book_operation(uid, "spent", "ask:openai", measured=admission.limit, estimated=0)
    p1, p2 = auth_patches(uid=uid)
    with p1, p2:
        response = client.post(
            "/ask_deepseek",
            headers=AUTH_HEADER,
            json={"question": "hello", "model": free_model("deepseek")},
        )
    assert response.status_code == 403
    body = response.json()["detail"]
    assert body["error_code"] == "token_budget_exhausted"
    assert body["token_budget"]["remaining"] == 0


def test_gemini_developer_path_uses_openrouter_and_counts_usage(reset_rate_limiter):
    client = make_client()
    uid = "uid-gemini-dev"
    captured = {}

    def fake_run_ask(provider, **kwargs):
        captured["provider"] = provider
        captured.update(kwargs)
        return {"ok": True}

    try:
        p1, p2 = auth_patches(uid=uid)
        with p1, p2, \
             patch.object(chat_router, "resolve_developer_api_keys", return_value={"OpenRouter": "server-key"}), \
             patch.object(chat_router, "_run_ask", side_effect=fake_run_ask):
            response = client.post(
                "/ask_gemini",
                headers=AUTH_HEADER,
                json={"question": "hello", "model": free_model("gemini")},
            )
        assert response.status_code == 200
        assert captured["provider"].label == "Gemini"
        assert captured["key"] == "server-key"
        assert captured["extras"]["key_used"] == "Developer API Key"
        # A run that skipped /prepare is admitted here, once; its answer is
        # metered and booked through the booking handed to _run_ask.
        assert captured["booking"].operation == "ask:gemini"
        assert _ledger(reset_rate_limiter, uid)["pipeline_runs"] == 1
    finally:
        pass


def test_own_key_path_bypasses_usage_counting(reset_rate_limiter):
    client = make_client()
    uid = "uid-own-key"
    captured = {}

    def fake_run_ask(provider, **kwargs):
        captured.update(kwargs)
        return {"ok": True}

    try:
        p1, p2 = auth_patches(uid=uid)
        with p1, p2, patch.object(chat_router, "_run_ask", side_effect=fake_run_ask):
            response = client.post(
                "/ask_claude",
                headers=AUTH_HEADER,
                json={
                    "question": "hello",
                    "model": free_model("anthropic"),
                    "useOwnKeys": True,
                    "openrouter_key": "sk-user-key",
                },
            )
        assert response.status_code == 200
        assert captured["key"] == "sk-user-key"
        assert captured["extras"]["usage"] == "own_keys"
        assert "token_budget" not in captured["extras"]
        assert captured["extras"]["key_used"] == "User API Key"
        assert captured.get("booking") is None
        assert _ledger(reset_rate_limiter, uid) == {}
    finally:
        pass


def test_own_key_without_login_is_rejected_for_every_provider():
    client = make_client()
    for route, provider in [
        ("/ask_openai", "openai"),
        ("/ask_mistral", "mistral"),
        ("/ask_gemini", "gemini"),
    ]:
        response = client.post(
            route,
            json={
                "question": "hello",
                "model": free_model(provider),
                "useOwnKeys": True,
                "openrouter_key": "sk-user-key",
            },
        )
        assert response.status_code == 401, route
        assert response.json()["detail"] == chat_router.OWN_KEYS_LOGIN_REQUIRED
