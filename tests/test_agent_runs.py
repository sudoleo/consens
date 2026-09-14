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
    assert list(completion.stream(model=AgentModel(), messages=messages, api_key="test")) == [{"type": "delta", "text": "Hello"}]
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
