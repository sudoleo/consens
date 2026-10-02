"""Die Run-Belege der Pipeline auf dem gemeinsamen Tokenkonto, ueber die API-Flows."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.api_core.exceptions import Aborted

import app.core.config as cfg
from app.api.routers import chat as chat_router
from app.api.routers import users as users_router
from app.core.rate_limit import limiter
from app.services import agent_budget_config, agent_quota
from app.services.usage_repository import RunKind
from usage_test_support import make_usage_repository
import receipt_helpers


UID = "run-endpoint-user"
AUTH = {"Authorization": "Bearer test-token"}
FREE_LIMIT = agent_budget_config.DEFAULT_TIER_LIMITS["free"]
FREE_RUN = agent_budget_config.DEFAULT_RUN_ESTIMATES["free"]
PRO_RUN = agent_budget_config.DEFAULT_RUN_ESTIMATES["pro"]
# Every fake answer reports this usage through the transport meter.
ANSWER_USAGE = {"prompt_tokens": 1_000, "completion_tokens": 500}


@pytest.fixture
def run_api(monkeypatch):
    limiter.reset()
    repository, db = make_usage_repository()
    monkeypatch.setattr(chat_router, "run_usage_repository", repository)
    monkeypatch.setattr(users_router, "run_usage_repository", repository)
    monkeypatch.setattr(chat_router, "verify_user_token", lambda token: UID)
    monkeypatch.setattr(users_router, "verify_user_token", lambda token, **kwargs: UID)
    monkeypatch.setattr(chat_router, "get_user_tier", lambda uid: "free")
    monkeypatch.setattr(users_router, "get_user_tier", lambda uid: "free")
    monkeypatch.setattr(users_router, "is_user_admin", lambda uid: False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    receipt_helpers.install(monkeypatch, chat_router)

    # Agent's snapshot repairs query llm_calls, which the fake cannot; the
    # account itself is read from the same fake document.
    def snapshot(db, uid, *, tier=None):
        config = agent_budget_config.get_config(db)
        period = agent_quota.period_key(config)
        data = agent_quota.quota_ref(db, uid, period).get().to_dict() or {}
        return agent_quota.public_snapshot(data, period, config, tier or "free")

    monkeypatch.setattr(agent_quota, "snapshot", snapshot)

    def fake_run_ask(provider, **kwargs):
        # Mirrors _run_ask: the answer is metered, booked and stored as a receipt.
        booking = kwargs.get("booking")
        if booking is not None:
            with booking.metering():
                booking.meter.record(ANSWER_USAGE)
        result = chat_router._with_receipt(
            {"text": f"{provider.label} answer", "sources": [], "completion": "complete"},
            kwargs.get("receipt"),
        )
        extras = {**kwargs["extras"], **(booking.extras() if booking else {})}
        return chat_router.source_response(result, **extras)

    monkeypatch.setattr(chat_router, "_run_ask", fake_run_ask)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(chat_router.router)
    app.include_router(users_router.router)
    return TestClient(app), repository, db


def _ledger(db):
    period = agent_quota.period_key(agent_budget_config.get_config(db))
    return db.documents.get(("users", UID, "chat_state", "agent_tokens_" + period)) or {}


def _prepare(client, key, *, deep=False, mode=None):
    body = {"question": "What changed?", "usage_run_key": key, "deep_search": deep}
    if mode:
        body["run_mode"] = mode
    return client.post("/prepare", headers=AUTH, json=body)


def _ask(client, route, provider, key, *, deep=False):
    return client.post(
        route,
        headers=AUTH,
        json={
            "question": "What changed?",
            "model": cfg.FREE_DEFAULT_MODEL_BY_PROVIDER[provider],
            "usage_run_key": key,
            "deep_search": deep,
        },
    )


def test_prepare_admits_once_and_answers_book_their_measured_tokens(run_api):
    client, _repository, db = run_api
    key = "one-logical-run"

    prepared = _prepare(client, key)
    assert prepared.status_code == 200
    body = prepared.json()
    assert body["usage_run_status"] == "consumed"
    assert body["run_estimate"] == FREE_RUN["consensus"]
    assert body["token_budget"]["used"] == 0
    assert body["token_budget"]["reserved"] == FREE_RUN["consensus"]
    assert body["token_budget"]["run_estimates"] == FREE_RUN
    assert "free_usage_remaining" not in body and "deep_remaining" not in body

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda args: _ask(client, *args, key),
                                  [("/ask_openai", "openai"), ("/ask_mistral", "mistral")]))

    assert all(response.status_code == 200 for response in responses)
    assert all(response.json()["usage_run_status"] == "consumed" for response in responses)
    assert max(response.json()["token_budget"]["used"] for response in responses) == 3_000
    ledger = _ledger(db)
    assert ledger["used"] == ledger["pipeline_used"] == 3_000
    assert ledger["pipeline_runs"] == 1
    assert agent_quota.held_tokens(ledger) == FREE_RUN["consensus"] - 3_000


def test_compare_runs_are_admitted_against_the_compare_estimate(run_api):
    client, _repository, _db = run_api
    prepared = _prepare(client, "compare-run", mode="compare")
    assert prepared.status_code == 200
    assert prepared.json()["run_estimate"] == FREE_RUN["compare"]


def test_prepare_is_refused_when_the_account_does_not_cover_a_run(run_api):
    client, _repository, db = run_api
    period = agent_quota.period_key(agent_budget_config.get_config(db))
    db.documents[("users", UID, "chat_state", "agent_tokens_" + period)] = {
        "used": FREE_LIMIT - FREE_RUN["consensus"] + 1, "revision": 3}

    refused = _prepare(client, "too-big")
    assert refused.status_code == 403
    detail = refused.json()["detail"]
    assert detail["error_code"] == "token_budget_exhausted"
    assert detail["required_tokens"] == FREE_RUN["consensus"]
    assert detail["token_budget"]["remaining"] == FREE_RUN["consensus"] - 1
    # A Compare run is smaller and still fits.
    assert _prepare(client, "smaller", mode="compare").status_code == 200


def test_parallel_same_provider_operation_runs_only_once(run_api, monkeypatch):
    client, _repository, db = run_api
    key = "same-provider-race"
    monkeypatch.setattr(chat_router, "get_system_prompt",
                        lambda: "Reference time at request start: 12:00:00.")
    prepared = _prepare(client, key)
    assert prepared.status_code == 200
    # The browser reuses /prepare's prompt. Without it, a new server clock
    # second changes the effective payload and correctly produces a conflict.
    payload = {
        "question": "What changed?", "usage_run_key": key,
        "model": cfg.FREE_DEFAULT_MODEL_BY_PROVIDER["openai"],
        "system_prompt": prepared.json()["system_prompt"],
    }
    monkeypatch.setattr(chat_router, "get_system_prompt",
                        lambda: "Reference time at request start: 12:00:01.")
    entered, release = Event(), Event()
    provider_calls = []
    original_run_ask = chat_router._run_ask

    def blocked_provider(provider, **kwargs):
        provider_calls.append(provider.label)
        entered.set()
        assert release.wait(10), "Concurrent requests did not finish"
        return original_run_ask(provider, **kwargs)

    monkeypatch.setattr(chat_router, "_run_ask", blocked_provider)

    def ask():
        return client.post("/ask_openai", headers=AUTH, json=payload)

    with ThreadPoolExecutor(max_workers=5) as pool:
        first = pool.submit(ask)
        try:
            assert entered.wait(10), "First request did not reach the provider"
            rejected = list(pool.map(lambda _index: ask(), range(4)))
        finally:
            release.set()
        assert first.result(timeout=10).status_code == 200

    assert len(rejected) == 4
    # Identical replays are rejected both during the call and after booking.
    # The first five requests exhausted the independent per-minute throttle.
    limiter.reset()
    rejected.append(ask())
    assert all(response.status_code == 409 for response in rejected)
    assert all(response.json()["detail"]["error_code"] == "usage_operation_already_claimed"
               for response in rejected)
    assert provider_calls == ["OpenAI"]
    assert _ledger(db)["used"] == 1_500


def test_repeated_operation_with_a_new_generated_prompt_is_a_conflict(run_api, monkeypatch):
    client, _repository, db = run_api
    key = "changed-request-clock"
    original_run_ask = chat_router._run_ask
    provider_calls = []

    def provider(provider, **kwargs):
        provider_calls.append(provider.label)
        return original_run_ask(provider, **kwargs)

    monkeypatch.setattr(chat_router, "_run_ask", provider)
    monkeypatch.setattr(chat_router, "get_system_prompt",
                        lambda: "Reference time at request start: 12:00:00.")
    assert _ask(client, "/ask_openai", "openai", key).status_code == 200
    monkeypatch.setattr(chat_router, "get_system_prompt",
                        lambda: "Reference time at request start: 12:00:01.")
    response = _ask(client, "/ask_openai", "openai", key)

    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == "usage_operation_conflict"
    assert provider_calls == ["OpenAI"]
    assert _ledger(db)["used"] == 1_500


def test_consensus_books_its_judges_once_and_drops_the_hold(run_api):
    client, _repository, db = run_api
    key = "answers-plus-consensus"
    assert _prepare(client, key).status_code == 200
    first = _ask(client, "/ask_openai", "openai", key)
    second = _ask(client, "/ask_mistral", "mistral", key)
    assert first.status_code == second.status_code == 200
    payload = {
        "usage_run_key": key,
        "question": "What changed?",
        "consensus_model": "Gemini",
        "answer_receipts": {
            "openai": first.json()["answer_receipt"],
            "mistral": second.json()["answer_receipt"],
        },
    }

    def synthesize(*_args, **_kwargs):
        # The synthesis call reports through the same transport meter.
        from app.services.llm.usage_meter import current_meter
        current_meter().record({"prompt_tokens": 4_000, "completion_tokens": 1_000})
        return "Consensus"

    with patch.object(chat_router, "query_consensus", side_effect=synthesize) as consensus_mock, \
         patch.object(chat_router, "query_differences", return_value=("Differences", None)), \
         patch.object(chat_router, "persist_pending_result", return_value=None), \
         patch.object(chat_router, "record_differences_stats"):
        response = client.post("/consensus", headers=AUTH, json=payload)
        repeated = client.post("/consensus", headers=AUTH, json=payload)

    assert response.status_code == 200
    assert repeated.status_code == 409
    assert repeated.json()["detail"]["error_code"] == "usage_operation_already_claimed"
    assert consensus_mock.call_count == 1
    synthesized = consensus_mock.call_args.args[1]
    assert synthesized["openai"] == "OpenAI answer"
    assert synthesized["mistral"] == "Mistral answer"
    body = response.json()
    assert body["usage_run_status"] == "consumed"
    assert body["token_budget"]["used"] == 8_000
    assert body["token_budget"]["reserved"] == 0
    ledger = _ledger(db)
    assert ledger["used"] == 8_000 and ledger["pipeline_runs"] == 1


def test_usage_endpoint_reads_the_account_and_release_drops_the_hold(run_api):
    client, repository, db = run_api
    key = "unused-reservation"
    admission = repository.admission("free")
    repository.reserve(UID, key, RunKind.REGULAR, admission)

    usage = client.post("/usage", json={"id_token": "test-token"})
    assert usage.status_code == 200
    budget = usage.json()["token_budget"]
    assert budget["limit"] == FREE_LIMIT and budget["reserved"] == FREE_RUN["consensus"]
    assert budget["remaining"] == FREE_LIMIT - FREE_RUN["consensus"]

    released = client.post("/usage/run/release", json={"id_token": "test-token", "usage_run_key": key})
    assert released.status_code == 200
    assert released.json()["status"] == "released"
    assert agent_quota.held_tokens(_ledger(db)) == 0
    assert client.post("/usage", json={"id_token": "test-token"}).json()["token_budget"]["remaining"] == FREE_LIMIT


def test_requests_without_run_key_are_rejected_before_provider_call(run_api):
    client, _repository, db = run_api
    response = client.post(
        "/ask_openai",
        headers=AUTH,
        json={"question": "What changed?", "model": cfg.FREE_DEFAULT_MODEL_BY_PROVIDER["openai"]},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "usage_run_key_required"
    assert _ledger(db) == {}


def test_exhausted_firestore_contention_returns_structured_503(run_api, monkeypatch):
    client, repository, _db = run_api
    key = "contention-run"
    assert _prepare(client, key).status_code == 200
    monkeypatch.setattr(repository, "authorize_operation",
                        lambda *_args, **_kwargs: (_ for _ in ()).throw(Aborted("contention")))

    response = _ask(client, "/ask_gemini", "gemini", key)

    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == "usage_storage_busy"


def test_free_reasoning_run_passes_prepare_ask_and_consensus_without_pro_gate(run_api):
    """Reasoning (wire name deep_search) is open to Free: no 403 anywhere in
    the run, admitted against the Reasoning estimate (key "deep_think")."""
    client, _repository, _db = run_api
    key = "free-reasoning-run"

    prepared = _prepare(client, key, deep=True)
    assert prepared.status_code == 200
    assert prepared.json()["run_estimate"] == FREE_RUN["deep_think"]
    first = _ask(client, "/ask_openai", "openai", key, deep=True)
    second = _ask(client, "/ask_mistral", "mistral", key, deep=True)
    assert first.status_code == second.status_code == 200
    payload = {
        "usage_run_key": key,
        "question": "What changed?",
        "consensus_model": "Gemini",
        "deep_search": True,
        "answer_receipts": {
            "openai": first.json()["answer_receipt"],
            "mistral": second.json()["answer_receipt"],
        },
    }
    with patch.object(chat_router, "query_consensus", return_value="Consensus"),          patch.object(chat_router, "query_differences", return_value=("Differences", None)),          patch.object(chat_router, "persist_pending_result", return_value=None),          patch.object(chat_router, "record_differences_stats"):
        response = client.post("/consensus", headers=AUTH, json=payload)
    assert response.status_code == 200


def test_reasoning_is_admitted_against_the_reasoning_estimate(run_api, monkeypatch):
    client, _repository, db = run_api
    monkeypatch.setattr(chat_router, "get_user_tier", lambda uid: "pro")
    key = "reasoning-run"

    prepared = _prepare(client, key, deep=True)
    assert prepared.status_code == 200
    assert prepared.json()["run_estimate"] == PRO_RUN["deep_think"]
    response = _ask(client, "/ask_openai", "openai", key, deep=True)

    assert response.status_code == 200
    assert _ledger(db)["used"] == 1_500


def test_admin_role_uses_the_admin_tier(run_api, monkeypatch):
    client, _repository, _db = run_api
    monkeypatch.setattr(agent_quota, "_admin_role", lambda uid: True)
    prepared = _prepare(client, "admin-run")
    assert prepared.json()["token_budget"]["tier"] == "admin"
    assert prepared.json()["token_budget"]["limit"] == agent_budget_config.DEFAULT_TIER_LIMITS["admin"]


@pytest.mark.parametrize("changed,expected_code", [
    ({"question": "Different question"}, "usage_run_conflict"),
    ({"stream": True}, "usage_operation_conflict"),
    ({}, "usage_operation_already_claimed"),
])
def test_authorization_rejections_never_start_a_second_provider(run_api, monkeypatch, changed, expected_code):
    client, _repository, _db = run_api
    # This test compares identical operation payloads. Freeze the injected
    # request clock so crossing a second cannot change their fingerprints.
    prompt = chat_router.get_system_prompt()
    monkeypatch.setattr(chat_router, "get_system_prompt", lambda: prompt)
    calls = []

    def provider(_provider, **kwargs):
        calls.append(True)
        return {"response": "answer", **kwargs["extras"]}
    monkeypatch.setattr(chat_router, "_run_ask", provider)
    payload = {
        "question": "What changed?", "usage_run_key": "bound-operation",
        "model": cfg.FREE_DEFAULT_MODEL_BY_PROVIDER["openai"],
    }
    assert client.post("/ask_openai", headers=AUTH, json=payload).status_code == 200
    response = client.post("/ask_openai", headers=AUTH, json={**payload, **changed})
    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == expected_code
    assert len(calls) == 1


def test_admitted_run_finishes_and_may_overdraw_the_account(run_api):
    client, _repository, db = run_api
    assert _prepare(client, "last-allowed").status_code == 200
    ledger = _ledger(db)
    ledger["used"] = FREE_LIMIT  # another tab spent everything meanwhile
    response = _ask(client, "/ask_openai", "openai", "last-allowed")
    assert response.status_code == 200
    assert response.json()["token_budget"]["used"] == FREE_LIMIT + 1_500
    assert response.json()["token_budget"]["remaining"] == 0
    assert _prepare(client, "next").status_code == 403
