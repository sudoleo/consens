from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.routers import agent, chat_history
from app.core.rate_limit import limiter, api_uid_limiter
from app.services import persistence_guard
from app.services.agent_runs import AgentRunStore
from app.services.chat_store import ChatStore, TurnStatusConflict
from app.services.llm import agent_client
from app.services.llm.agent_client import AgentModel, AgentCompletion, measured_usage
from test_chat_history import FakeChatDatabase


UID = "agent-user"
AUTH = {"Authorization": "Bearer verified"}


class Database(FakeChatDatabase):
    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()

    def run_transaction(self, operation):
        with self.lock:
            return super().run_transaction(operation)


@pytest.fixture
def store():
    return AgentRunStore(Database())


def pending(store, *, uid=UID, chat_id=None, request_id="one", question="Question one"):
    chat_id = chat_id or store.create_chat(uid, execution_mode="agent")["id"]
    model = AgentModel()
    turn = store.create_turn(uid, chat_id, question=question, mode="Agent", deep_search=False,
        selected_models=[model.model], consensus_model=model.model,
        client_request_id=request_id, execution_mode="agent")
    return chat_id, turn


def receipt(*, measured=True):
    completion = AgentCompletion()
    completion.text = "A helpful answer"
    completion.finish_reason = "stop"
    completion.generation_id = "generation-test"
    completion.usage = measured_usage({"prompt_tokens": 1000, "completion_tokens": 100,
        "prompt_tokens_details": {"cached_tokens": 200},
        "completion_tokens_details": {"reasoning_tokens": 50}}, AgentModel()) if measured else None
    return completion


def totals(store):
    return store.db.collection("users").document(UID).get().to_dict()["agent_usage"]


def test_usage_uses_reported_tokens_and_does_not_double_count_reasoning():
    usage = receipt().usage
    assert usage["input_tokens"] == 1000
    assert usage["output_tokens"] == 100
    assert usage["estimated_cost_nano_usd"] == 180600
    assert usage["billing_mode"] == "simulation"
    for invalid in ({}, {"prompt_tokens": True, "completion_tokens": 2},
                    {"prompt_tokens": 2.4, "completion_tokens": 2},
                    {"prompt_tokens": 2, "completion_tokens": -1}):
        assert measured_usage(invalid, AgentModel()) is None
    assert measured_usage({"prompt_tokens": 0, "completion_tokens": 0}, AgentModel())["input_tokens"] == 0


def test_parallel_claims_and_settlement_are_exactly_once(store):
    chat_id, turn = pending(store)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: store.claim(UID, chat_id, turn["id"], AgentModel()), range(2)))
    assert sorted(claims) == [False, True]
    assert totals(store)["calls"] == 1
    assert totals(store)["unsettled_calls"] == 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        settled = list(pool.map(lambda _: store.settle(UID, chat_id, turn["id"], completion=receipt(), status="succeeded"), range(2)))
    assert sorted(settled) == [False, True]
    assert totals(store)["estimated_cost_nano_usd"] == 180600
    assert totals(store)["unsettled_calls"] == 0
    assert store.get_turn(UID, chat_id, turn["id"])["consensus"] == "A helpful answer"
    assert not any("usage_runs" in path for path in store.db.documents)


def test_followups_use_all_completed_messages_without_compression(store):
    chat_id, first = pending(store)
    assert store.claim(UID, chat_id, first["id"], AgentModel())
    store.settle(UID, chat_id, first["id"], completion=receipt(), status="succeeded")
    _, second = pending(store, chat_id=chat_id, request_id="two", question="What next?")
    messages = store.messages(UID, chat_id, second)
    assert [message["role"] for message in messages] == ["system", "user", "assistant", "user"]
    assert [message["content"] for message in messages[1:]] == ["Question one", "A helpful answer", "What next?"]


def test_final_turn_keeps_search_sources_from_previous_steps(store):
    chat_id, turn = pending(store)
    assert store.claim(UID, chat_id, turn["id"], AgentModel())
    completion = receipt()
    completion.activity = [{"kind": "tool", "name": "web_search", "sources": [
        {"url": "https://example.org/search", "title": "Primary source"}, {"url": "javascript:bad()"}]}]
    completion.sources = [{"url": "https://example.org/answer", "title": "Answer citation"}]
    store.settle(UID, chat_id, turn["id"], completion=completion, status="succeeded")
    assert {s["url"] for s in store.get_turn(UID, chat_id, turn["id"])["sources"]} == {
        "https://example.org/search", "https://example.org/answer"}


def test_chat_lock_prevents_two_different_turns_running_together(store):
    chat_id, first = pending(store)
    with pytest.raises(TurnStatusConflict):
        pending(store, chat_id=chat_id, request_id="two")
    # Identical requests may resolve to the same turn, never another one.
    assert pending(store, chat_id=chat_id)[1]["id"] == first["id"]


@pytest.mark.parametrize("status", ["failed", "cancelled"])
def test_missing_usage_is_unknown_instead_of_zero(store, status):
    chat_id, turn = pending(store)
    store.claim(UID, chat_id, turn["id"], AgentModel())
    store.settle(UID, chat_id, turn["id"], completion=receipt(measured=False), status=status)
    assert totals(store)["unmetered_calls"] == 1
    assert "estimated_cost_nano_usd" not in totals(store)
    assert store.get_turn(UID, chat_id, turn["id"])["status"] == "failed"
    assert store.receipt_ref(UID, chat_id, turn["id"]).get().to_dict()["usage"] is None


def test_chat_deletion_does_not_erase_cost_or_resurrect_turn(store):
    chat_id, turn = pending(store)
    store.claim(UID, chat_id, turn["id"], AgentModel())
    store.delete_chat(UID, chat_id)
    store.settle(UID, chat_id, turn["id"], completion=receipt(), status="succeeded")
    assert totals(store)["estimated_cost_nano_usd"] == 180600
    assert not store._chat_ref(UID, chat_id).get().exists
    assert not store._turn_ref(UID, chat_id, turn["id"]).get().exists


def test_account_tombstone_fences_settlement(store):
    chat_id, turn = pending(store)
    store.claim(UID, chat_id, turn["id"], AgentModel())
    store.db.documents[("account_deletion_jobs", UID)] = {"status": "pending", "created_at": datetime.now(timezone.utc)}
    with pytest.raises(persistence_guard.AccountDeletionInProgress):
        store.settle(UID, chat_id, turn["id"], completion=receipt(), status="succeeded")
    assert totals(store)["unsettled_calls"] == 1


def test_failed_transaction_can_settle_again_without_partial_accounting(store):
    chat_id, turn = pending(store)
    store.claim(UID, chat_id, turn["id"], AgentModel())
    store.db.fail_transaction_after_staged_writes = 2
    with pytest.raises(RuntimeError):
        store.settle(UID, chat_id, turn["id"], completion=receipt(), status="succeeded")
    assert totals(store)["unsettled_calls"] == 1
    assert store.get_turn(UID, chat_id, turn["id"])["status"] == "pending"
    store.db.fail_transaction_after_staged_writes = None
    assert store.settle(UID, chat_id, turn["id"], completion=receipt(), status="succeeded")


def test_conversation_cannot_switch_pipeline(store):
    chat_id, turn = pending(store)
    with pytest.raises(TurnStatusConflict):
        ChatStore(store.db).create_turn(UID, chat_id, question="Q", mode="Standard", deep_search=False,
            selected_models=["DeepSeek"], consensus_model="OpenAI")
    with pytest.raises(TurnStatusConflict):
        store.validate_turn_for_completion(UID, chat_id, turn["id"], question=turn["question"])


def test_client_makes_one_tool_free_request_and_reads_final_usage_chunk(monkeypatch):
    requests = []
    def lines(url, **kwargs):
        requests.append(kwargs["json"])
        for event in [
            {"id": "gen-1", "choices": [{"delta": {"content": "Hello"}}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 3}},
        ]:
            yield "data: " + json.dumps(event)
            yield ""
        yield "data: [DONE]"
        yield ""
    monkeypatch.setattr(agent_client, "cancellable_sse_lines", lines)
    completion = AgentCompletion()
    messages = [{"role": "user", "content": "Hi"}]
    events = list(completion.stream(model=AgentModel(), messages=messages, api_key="test"))
    assert [event for event in events if event["type"] == "delta"] == [{"type": "delta", "text": "Hello"}]
    assert events[0]["status"] == "responding"
    assert len(requests) == 1
    assert "tools" not in requests[0] and "plugins" not in requests[0]
    assert requests[0]["stream_options"] == {"include_usage": True}
    assert requests[0]["messages"] == messages
    assert completion.usage["input_tokens"] == 12


@pytest.fixture
def api(monkeypatch, store):
    limiter.reset()
    api_uid_limiter.reset()
    monkeypatch.setattr(chat_history, "verify_user_token", lambda token: UID if token == "verified" else "other-user")
    monkeypatch.setattr(chat_history, "db_firestore", store.db)
    monkeypatch.setattr(agent, "db_firestore", store.db)
    monkeypatch.setattr(agent, "is_user_pro", lambda uid: True)
    monkeypatch.setattr(agent, "is_user_admin", lambda uid: False)
    monkeypatch.setattr(agent, "resolve_developer_api_keys", lambda: {"OpenRouter": "test"})
    monkeypatch.setattr(agent, "mock_llm_enabled", lambda: False)
    calls = []
    def stream(self, **kwargs):
        calls.append(kwargs)
        value = receipt()
        self.__dict__.update(value.__dict__)
        yield {"type": "delta", "text": self.text}
    monkeypatch.setattr(AgentCompletion, "stream", stream)
    # The bookmark quota helper expects merge-capable transactions.
    original = persistence_guard._set
    def set_compatible(tx, ref, data, merge=False):
        if tx is not None and merge:
            current = ref.database.documents.get(ref.path, {})
            return tx.set(ref, persistence_guard._deep_merge(current, data))
        return original(tx, ref, data, merge=merge)
    monkeypatch.setattr(persistence_guard, "_set", set_compatible)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(chat_history.router)
    app.include_router(agent.router)
    return TestClient(app), store, calls


def test_endpoint_single_call_replay_and_cumulative_costs(api, monkeypatch):
    client, store, calls = api
    created = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH)
    assert created.status_code == 201, created.text
    chat_id = created.json()["chat"]["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "first", "bookmark_id": "agent_test"}
    response = client.post("/agent", json=payload, headers=AUTH)
    assert response.status_code == 200 and "event: final" in response.text, response.text
    assert len(calls) == 1
    monkeypatch.setattr(agent, "agent_model", lambda: pytest.fail("Replay must not consult new model config"))
    replay = client.post("/agent", json=payload, headers=AUTH)
    assert replay.status_code == 200, replay.text
    assert replay.json()["response"] == "A helpful answer"
    assert len(calls) == 1 and totals(store)["calls"] == 1
    assert totals(store)["estimated_cost_nano_usd"] == 180600


@pytest.mark.parametrize("pro,admin,allowed", [(False, False, False), (True, False, True), (False, True, True)])
def test_access_is_enforced_on_server(api, monkeypatch, pro, admin, allowed):
    client, store, calls = api
    monkeypatch.setattr(agent, "is_user_pro", lambda uid: pro)
    monkeypatch.setattr(agent, "is_user_admin", lambda uid: admin)
    response = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH)
    assert response.status_code == (201 if allowed else 403)
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    response = client.post("/agent", json={"chat_id": chat_id, "question": "Hi", "client_request_id": "r1", "bookmark_id": "bm1"}, headers=AUTH)
    assert response.status_code == (200 if allowed else 403)
    assert len(calls) == (1 if allowed else 0)


def test_foreign_chat_and_client_supplied_models_or_usage_are_rejected(api):
    client, store, calls = api
    chat_id = store.create_chat("other-user", execution_mode="agent")["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "r1", "bookmark_id": "bm1"}
    assert client.post("/agent", json=payload, headers=AUTH).status_code == 404
    for extra in ({"model": "expensive-model"}, {"attachments": []}, {"usage": {"input_tokens": 1}}, {"useOwnKeys": True}):
        assert client.post("/agent", json={**payload, **extra}, headers=AUTH).status_code == 422
    assert calls == []


def test_recovery_never_starts_a_new_call(api):
    client, store, calls = api
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    response = client.post("/agent", json={"chat_id": chat_id, "question": "Hi",
        "client_request_id": "missing", "bookmark_id": "bm1", "recover_only": True}, headers=AUTH)
    assert response.status_code == 404
    assert calls == []
    assert store.get_chat(UID, chat_id)["turn_count"] == 0


def test_old_replay_keeps_newest_bookmark_and_sums_both_calls(api):
    client, store, calls = api
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat_id, "question": "First", "client_request_id": "first", "bookmark_id": "bm1"}
    assert "event: final" in client.post("/agent", json=payload, headers=AUTH).text
    assert "event: final" in client.post("/agent", json={**payload, "question": "Second", "client_request_id": "second"}, headers=AUTH).text
    assert client.post("/agent", json={**payload, "recover_only": True}, headers=AUTH).status_code == 200
    saved = store.db.collection("users").document(UID).collection("bookmarks").document("bm1").get().to_dict()
    assert saved["query"] == "Second"
    assert len(calls) == 2 and totals(store)["estimated_cost_nano_usd"] == 361200


def test_provider_error_after_usage_still_records_cost(api, monkeypatch):
    client, store, calls = api
    def failed(self, **kwargs):
        self.__dict__.update(receipt().__dict__)
        self.text = "Partial"
        yield {"type": "delta", "text": "Partial"}
        raise RuntimeError("Provider failed")
    monkeypatch.setattr(AgentCompletion, "stream", failed)
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    response = client.post("/agent", json={"chat_id": chat_id, "question": "Hi",
        "client_request_id": "failed", "bookmark_id": "bm1"}, headers=AUTH)
    assert "event: error" in response.text and "event: final" not in response.text
    assert totals(store)["measured_calls"] == 1
    assert totals(store)["estimated_cost_nano_usd"] == 180600
    assert store.list_turns(UID, chat_id)["turns"][0]["status"] == "failed"
    error = json.loads(response.text.split("event: error\ndata: ")[1].split("\n\n")[0])
    assert error["token_budget"]["used"] == 1100
    assert error["token_budget"]["reserved"] == 0
    assert error["token_budget"]["remaining"] == 248900
    assert error['recoverable'] is True
    count = len(store.db.documents)
    for _ in range(3):
        retry = client.post('/agent', json={'chat_id': chat_id, 'question': 'Hi', 'client_request_id': 'failed',
            'bookmark_id': 'bm1', 'recover_only': True}, headers=AUTH)
        assert retry.status_code == 200
        assert retry.json()['response'] == 'Partial'
        assert retry.json()['turn']['status'] == 'failed'
        assert retry.json()['turn']['agent_failure']['code'] == 'provider_error'
    assert len(store.db.documents) == count
    assert totals(store)['calls'] == 1
    turn = store.list_turns(UID, chat_id)["turns"][0]
    data = client.get(f"/agent/chats/{chat_id}/turns/{turn['id']}/agents", headers=AUTH).json()
    assert data["token_budget"]["remaining"] == 248900
    assert data["token_budget"]["observed_at"] >= error["token_budget"]["observed_at"]


def test_quota_failure_returns_current_allowance_and_reservation_reason(api):
    from app.services import agent_quota
    client, store, calls = api
    agent_quota.quota_ref(store.db, UID, agent_quota.day_key()).set({"used": 249900})
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    response = client.post("/agent", json={"chat_id": chat_id, "question": "Hi",
        "client_request_id": "quota", "bookmark_id": "bm1"}, headers=AUTH)
    error = json.loads(response.text.split("event: error\ndata: ")[1].split("\n\n")[0])
    assert error["code"] == "agent_token_reservation"
    assert error["token_budget"]["remaining"] == error["available_tokens"] == 100
    assert error["required_tokens"] > 100
    assert error['recoverable'] is True
    assert error['saved_answer']['response'] == ''
    assert error['saved_answer']['turn']['agent_failure']['code'] == 'agent_token_reservation'
    assert store.db.collection('users').document(UID).collection('bookmarks').document('bm1').get().exists
    replay = client.post('/agent', json={'chat_id': chat_id, 'question': 'Hi',
        'client_request_id': 'quota', 'bookmark_id': 'bm1', 'recover_only': True}, headers=AUTH)
    assert replay.status_code == 200 and replay.json()['turn']['status'] == 'failed'
    budget = client.get('/agent/budget', headers=AUTH)
    assert budget.status_code == 200 and budget.json()['token_budget']['remaining'] == 100
    assert budget.headers['cache-control'] == 'private, no-store'
    assert calls == []


def test_disconnect_closes_producer_and_settles_unknown_usage(store):
    from app.services.llm.streaming import iter_sse_with_keepalive
    from app.services.llm.provider_runtime import ProviderCancellation
    chat_id, turn = pending(store)
    store.claim(UID, chat_id, turn["id"], AgentModel())
    cancellation = ProviderCancellation()
    settled = threading.Event()
    def events():
        try:
            cancellation.cancel()
            yield "started"
        finally:
            store.settle(UID, chat_id, turn["id"], completion=receipt(measured=False), status="cancelled")
            settled.set()
    assert list(iter_sse_with_keepalive(events(), interval_seconds=.01, cancellation=cancellation)) == []
    assert settled.wait(1)
    assert totals(store)["unmetered_calls"] == 1


def test_account_cleanup_removes_step_receipts(store):
    from app.services.account_deletion import FirestoreAccountDeletion
    chat_id, turn = pending(store)
    store.claim(UID, chat_id, turn["id"], AgentModel())
    FirestoreAccountDeletion(store.db)._delete_user_subcollections(UID)
    assert not store.receipt_ref(UID, chat_id, turn["id"]).get().exists


def test_catalog_reuses_allowlist_and_restricts_reasoning(api, monkeypatch):
    from app.core import config as cfg
    client, store, calls = api
    response = client.get("/agent/models", headers=AUTH)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    models = {item["id"]: item for item in response.json()["models"]}
    assert models["deepseek/deepseek-v4.1-flash"]["reasoning_efforts"] == ["default", "low", "high", "max"]
    assert "none" not in models[cfg.DEFAULT_GEMINI_MODEL]["reasoning_efforts"]
    assert models[cfg.GROK_NO_REASONING_MODEL]["reasoning_efforts"] == ["default"]
    expected = {model_id for preset in ("fast", "thorough")
                for model_id in cfg.CONSENSUS_PRESET_MODELS[preset]["answers"].values()}
    expected.update(cfg.PREMIUM_MODELS)
    expected.update(model_id for provider in cfg.PROVIDERS.values()
                    for model_id in (provider.base_model, provider.pro_model))
    assert set(models) == expected | {"deepseek/deepseek-v4.1-flash"}
    assert len(response.json()["models"]) == len(models)
    assert {item['provider'] for item in models.values()} == set(cfg.PROVIDERS)
    for provider in cfg.PROVIDERS.values():
        assert models[provider.pro_model]['provider'] == provider.key
        assert models[provider.pro_model]['provider_label'] == provider.label
    assert all("web_search" in item["tools_by_effort"]["default"] for item in models.values())
    # Admin presets may contain only a subset of families; the chat catalog
    # must still offer every configured Pro model.
    monkeypatch.setitem(cfg.CONSENSUS_PRESET_MODELS, 'thorough', {'answers': {
        'openai': cfg.OPENAI_SOL_MODEL, 'deepseek': cfg.DEEPSEEK_PRO_MODEL}})
    trimmed_preset_models = {item['id'] for item in client.get('/agent/models', headers=AUTH).json()['models']}
    assert cfg.PREMIUM_MODELS <= trimmed_preset_models
    assert {p.pro_model for p in cfg.PROVIDERS.values()} <= trimmed_preset_models
    monkeypatch.delitem(cfg.MODEL_CONFIGS, cfg.DEFAULT_ANTHROPIC_MODEL)
    assert cfg.DEFAULT_ANTHROPIC_MODEL not in {item["id"] for item in client.get("/agent/models", headers=AUTH).json()["models"]}
    monkeypatch.setattr(agent, "is_user_pro", lambda uid: False)
    assert client.get("/agent/models", headers=AUTH).status_code == 403
    assert client.get("/agent/models").status_code == 401
    assert not calls


@pytest.mark.parametrize("selection", [
    {"model_id": "not-a-model"},
    {"model_id": "deepseek/deepseek-v4.1-flash", "reasoning_effort": "medium"},
    {"model_id": "gpt-4o", "reasoning_effort": "high"},
    {"model_id": "gemini-3.5-flash", "reasoning_effort": "none"},
])
def test_invalid_selections_do_not_start_or_lock_a_turn(api, selection):
    client, store, calls = api
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    response = client.post("/agent", headers=AUTH, json={"chat_id": chat_id, "question": "Hi",
        "client_request_id": "first", "bookmark_id": "bm1", **selection})
    assert response.status_code == 422
    assert store.get_chat(UID, chat_id)["turn_count"] == 0
    assert not calls


@pytest.mark.parametrize("model_id", ["gpt-5.6-luna", "gpt-5.6-sol"])
def test_model_effort_snapshot_switch_and_recovery_identity(api, monkeypatch, model_id):
    client, store, calls = api
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "first", "bookmark_id": "bm1",
        "model_id": model_id, "reasoning_effort": "low"}
    assert "event: final" in client.post("/agent", json=payload, headers=AUTH).text
    assert calls[0]["model"].model == f"openai/{model_id}"
    assert calls[0]["model"].request_config["reasoning"] == {"effort": "low", "exclude": False, "summary": "auto"}
    saved = client.post("/agent", json=payload, headers=AUTH).json()["turn"]
    assert saved["agent_settings"]["model_id"] == model_id
    assert saved["agent_settings"]["reasoning_effort"] == "low"
    assert saved["agent_activity"][-1]["status"] == "succeeded"
    assert saved["agent_usage"]["input_tokens"] == 1000
    assert client.post("/agent", json={**payload, "reasoning_effort": "high"}, headers=AUTH).status_code == 409
    next_payload = {**payload, "client_request_id": "second", "model_id": "deepseek/deepseek-v4.1-flash"}
    assert "event: final" in client.post("/agent", json=next_payload, headers=AUTH).text
    assert calls[1]["model"].model == "deepseek/deepseek-v4.1-flash"
    assert calls[1]["messages"][1:3] == [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "A helpful answer"}]
    monkeypatch.setattr(agent, "resolve_agent_model", lambda *a: pytest.fail("Replay must use saved settings"))
    assert client.post("/agent", json={**payload, "recover_only": True}, headers=AUTH).status_code == 200
    assert len(calls) == 2


def test_reasoning_stream_formats_are_bounded_and_never_leak_encrypted_data(monkeypatch):
    chunks = [
        {"reasoning": "legacy "}, {"reasoning_content": "alias"},
        {"reasoning": "duplicate", "reasoning_details": [{"type": "reasoning.summary", "summary": "Summary ", "index": 1}]},
        {"reasoning_details": [{"type": "reasoning.summary", "summary": "continued", "index": 1}]},
        {"reasoning_details": [{"type": "reasoning.encrypted", "data": "secret", "text": "secret"}]},
        {"reasoning": "x" * 40000}, {"content": "Answer"},
    ]
    requests = []
    def lines(url, **kwargs):
        requests.append(kwargs["json"])
        for delta in chunks:
            yield "data: " + json.dumps({"choices": [{"delta": delta}]})
            yield ""
        yield 'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}'
        yield ""
    monkeypatch.setattr(agent_client, "cancellable_sse_lines", lines)
    completion = AgentCompletion()
    model = agent_client.resolve_agent_model("gpt-5.6-luna", "medium")
    events = list(completion.stream(model=model, messages=[], api_key="test"))
    assert requests[0]["reasoning"]["effort"] == "medium"
    assert requests[0]["provider"] == {"zdr": True}
    assert completion.text == "Answer"
    assert completion.reasoning_truncated
    assert completion.reasoning_chars == 32000
    serialized = json.dumps(completion.activity)
    assert "secret" not in serialized and "duplicate" not in serialized
    assert "Summary continued" in serialized and "legacy alias" in serialized
    assert all(event["version"] == 1 for event in events if event["type"] == "activity")


def test_selected_model_prices_and_mandatory_provider_routes(monkeypatch):
    model = agent_client.resolve_agent_model("gpt-5.6-luna", "low")
    usage = measured_usage({"prompt_tokens": 1000, "completion_tokens": 100,
        "prompt_tokens_details": {"cached_tokens": 200}}, model)
    assert usage["estimated_cost_nano_usd"] == 284000
    from app.core import config as cfg
    monkeypatch.setenv("AGENT_MODEL", cfg.MODEL_CONFIGS[cfg.KIMI_PRO_MODEL].api_model)
    kimi = agent_client.resolve_agent_model(reasoning_effort="low")
    assert kimi.request_config["provider"]["only"] == ["moonshotai"]


def test_context_check_precedes_paid_claim_for_small_model(api, monkeypatch):
    client, store, calls = api
    chat_id, turn = pending(store)
    value = receipt()
    value.text = "Old answer " * 10000  # Exceed the token window, not just its byte count.
    store.claim(UID, chat_id, turn["id"], AgentModel())
    store.settle(UID, chat_id, turn["id"], completion=value, status="succeeded")
    monkeypatch.setenv("AGENT_MODEL", "openai/gpt-3.5-turbo")
    response = client.post("/agent", headers=AUTH, json={"chat_id": chat_id, "question": "Continue",
        "client_request_id": "small", "bookmark_id": "bm1"})
    assert response.status_code == 422 and "too long" in response.text
    assert totals(store)["calls"] == 1
    assert not calls


def test_agent_history_never_queries_empty_model_answers(store, monkeypatch):
    chat_id, turn = pending(store)
    monkeypatch.setattr(store, "_model_answers", lambda *args: pytest.fail("Agent turns have no model_answers subcollection"))
    assert store.get_turn(UID, chat_id, turn["id"])["id"] == turn["id"]
    assert len(store.list_turns(UID, chat_id)["turns"]) == 1


@pytest.mark.parametrize("model_id", ["moonshotai/kimi-k3", "openai/gpt-3.5-turbo"])
def test_configured_default_uses_its_own_prices_context_and_routing(monkeypatch, model_id):
    from app.core import config as cfg
    from decimal import Decimal
    monkeypatch.setenv("AGENT_MODEL", model_id)
    model = agent_client.resolve_agent_model()
    metadata = agent_client._CATALOG["models"][model_id]
    assert model.context_length == metadata["context_length"]
    assert Decimal(model.input_usd_per_million) == Decimal(metadata["pricing"]["prompt"]) * 1_000_000
    entry = next(entry for entry in cfg.MODEL_CONFIGS.values() if entry.api_model == model_id)
    assert model.label == entry.label
    if model_id.startswith("moonshotai/"):
        assert model.request_config["provider"]["only"] == ["moonshotai"]
    monkeypatch.setenv("AGENT_INPUT_USD_PER_MILLION", "0.23")
    assert agent_client.resolve_agent_model().input_usd_per_million == "0.23"


def test_unknown_default_requires_catalog_instead_of_assuming_deepseek_limits(monkeypatch):
    monkeypatch.setenv("AGENT_MODEL", "unknown/future-model")
    with pytest.raises(ValueError, match="catalog entry"):
        agent_client.agent_model()


def test_bookmark_conflict_and_nonstream_request_are_rejected_before_model_call(api):
    client, store, calls = api
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "first", "bookmark_id": "bm1"}
    assert client.post("/agent", json={**payload, "stream": False}, headers=AUTH).status_code == 422
    store.db.documents[("users", UID, "bookmarks", "bm1")] = {"chat_id": "c" * 32}
    assert client.post("/agent", json=payload, headers=AUTH).status_code == 409
    assert not calls
    assert store.get_chat(UID, chat_id)["turn_count"] == 0
