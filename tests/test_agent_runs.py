from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
pytestmark = pytest.mark.usefixtures("deepseek_default_agent")

from app.core import config as cfg
from app.api.routers import agent, chat_history
from app.core.rate_limit import limiter, api_uid_limiter
from app.services import agent_runs, persistence_guard
from app.services.agent_comparison import AgentPreferences
from app.services.agent_runs import APP_CONTEXT_OPEN, AgentRunStore, strip_app_context
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


# Receipts are priced with fixed (GPT-6 Luna) prices, so these ledger tests do
# not change whenever the default chat model does.
PRICED = AgentModel(model="openai/gpt-6-luna", label="GPT-6 Luna", selection_id="gpt-6-luna",
                    input_usd_per_million="0.10", output_usd_per_million="0.50",
                    cache_read_usd_per_million="0.01", cache_write_usd_per_million="")


def receipt(*, measured=True):
    completion = AgentCompletion()
    completion.text = "A helpful answer"
    completion.finish_reason = "stop"
    completion.generation_id = "generation-test"
    completion.usage = measured_usage({"prompt_tokens": 1000, "completion_tokens": 100,
        "prompt_tokens_details": {"cached_tokens": 200},
        "completion_tokens_details": {"reasoning_tokens": 50}}, PRICED) if measured else None
    return completion


def totals(store):
    return store.db.collection("users").document(UID).get().to_dict()["agent_usage"]


def priced(amount):
    """The cost (nano-USD) of a reservation that holds ``amount`` micro-euros
    of the account (agent_budget_config.NANO_USD_PER_MICRO_EUR)."""
    from app.services.agent_budget_config import NANO_USD_PER_MICRO_EUR
    return amount * NANO_USD_PER_MICRO_EUR


def allowance(model, inputs, outputs=0):
    """The micro-euros the account holds for ``inputs`` and ``outputs``
    tokens of ``model`` at their reservation's worst-case price."""
    from app.services.agent_budget_config import micro_eur
    from app.services.agent_costs import worst_case_nanos
    return micro_eur(worst_case_nanos(model, inputs, outputs))


def test_usage_uses_reported_tokens_and_does_not_double_count_reasoning():
    usage = receipt().usage
    assert usage["input_tokens"] == 1000
    assert usage["output_tokens"] == 100
    assert usage["estimated_cost_nano_usd"] == 132000
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
    assert totals(store)["estimated_cost_nano_usd"] == 132000
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
    assert [message["content"] for message in messages[1:-1]] == ["Question one", "A helpful answer"]
    # The newest message carries the app's per-message context ahead of the
    # user's words; replayed history stays exactly what was said (cacheable).
    assert strip_app_context(messages[-1]["content"]) == "What next?"
    assert messages[-1]["content"].startswith(APP_CONTEXT_OPEN)


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
    assert totals(store)["estimated_cost_nano_usd"] == 132000
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


class Calls(list):
    """The agent's model calls of the ``api`` fixture; ``reviews`` holds the
    reviewers' calls."""

    def __init__(self):
        super().__init__()
        self.reviews = []


@pytest.fixture
def api(monkeypatch, store):
    limiter.reset()
    api_uid_limiter.reset()
    monkeypatch.setattr(chat_history, "verify_user_token", lambda token: UID if token == "verified" else "other-user")
    monkeypatch.setattr(chat_history, "db_firestore", store.db)
    monkeypatch.setattr(agent, "db_firestore", store.db)
    monkeypatch.setattr(agent, "is_user_pro", lambda uid: True)
    monkeypatch.setattr(agent, "is_user_admin", lambda uid: False)
    monkeypatch.setattr(agent, "get_user_tier", lambda uid: "pro")
    monkeypatch.setattr(agent, "resolve_developer_api_keys", lambda: {"OpenRouter": "test"})
    monkeypatch.setattr(agent, "mock_llm_enabled", lambda: False)
    calls = Calls()
    def stream(self, **kwargs):
        if not self.step_id.startswith("completion:"):
            # Every account's turn is reviewed by its comparison models (the
            # one mode, 2026-10-31): they mark nothing and cost nothing here,
            # so ``calls`` and the ledger's cost are the agent's own.
            calls.reviews.append(kwargs)
            self.usage = measured_usage({"prompt_tokens": 0, "completion_tokens": 0}, kwargs["model"])
            self.text, self.finish_reason = json.dumps({"marks": []}), "stop"
            yield {"type": "delta", "text": self.text}
            return
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


def test_the_date_follows_the_users_device_and_an_unknown_zone_the_apps(api):
    """Harness review 2026-10-27: the date was always Berlin's, wherever the
    user was. The browser sends its zone; one the server does not know (or
    none, an older tab) leaves the app's reference zone."""
    client, _, calls = api
    chat_id = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]["id"]
    contexts = []
    for request_id, zone in (("zone-1", "America/New_York"), ("zone-2", "Mars/Olympus"), ("zone-3", None)):
        payload = {"chat_id": chat_id, "question": "What day is it?", "client_request_id": request_id,
                   "bookmark_id": "agent_test", **({"timezone": zone} if zone else {})}
        assert client.post("/agent", json=payload, headers=AUTH).status_code == 200
        contexts.append(next(m["content"] for m in reversed(calls[-1]["messages"])
                             if str(m["content"]).startswith(APP_CONTEXT_OPEN)))
    device, unknown, absent = contexts
    assert "Reference timezone: America/New_York (UTC-0" in device and "timezone of the user's device" in device
    for context in (unknown, absent):
        assert "Reference timezone: Europe/Berlin" in context and "application default" in context


def test_the_next_message_repeats_the_question_exactly_as_it_was_sent(api):
    """With OpenRouter's search tool a Claude request caches only at its end
    (live probe 2026-10-23): the next message reads the previous one's first
    step only if its prompt starts with exactly that step's prompt, the
    question's app context (clock to the second) included."""
    client, store, calls = api
    chat_id = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]["id"]
    sent = []
    for request_id, question in (("first", "Hi"), ("second", "And then?")):
        payload = {"chat_id": chat_id, "question": question, "client_request_id": request_id,
                   "bookmark_id": "agent_test"}
        assert client.post("/agent", json=payload, headers=AUTH).status_code == 200
        sent.append([dict(message) for message in calls[-1]["messages"]])
    first, second = sent
    assert second[:2] == first[:2]
    assert first[1]["content"].startswith(APP_CONTEXT_OPEN) and strip_app_context(first[1]["content"]) == "Hi"
    assert [message["role"] for message in second[:4]] == ["system", "user", "assistant", "user"]
    assert strip_app_context(second[3]["content"]) == "And then?"
    # The turn keeps the context it was sent with; its projection never shows it.
    turn_id = next(turn["id"] for turn in store.list_turns(UID, chat_id)["turns"] if turn["question"] == "Hi")
    stored = store._turn_ref(UID, chat_id, turn_id).get().to_dict()["app_context"]
    assert first[1]["content"] == agent_runs.with_app_context("Hi", stored)
    assert "app_context" not in store.get_turn(UID, chat_id, turn_id)


def test_a_turn_keeps_only_a_short_app_context(store):
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    model = AgentModel()
    with pytest.raises(ValueError):
        store.create_turn(UID, chat_id, question="Q", mode="Agent", deep_search=False,
                          selected_models=[model.model], consensus_model=model.model,
                          execution_mode="agent", app_context="x" * 4001)


def test_endpoint_single_call_replay_and_cumulative_costs(api, monkeypatch):
    client, store, calls = api
    created = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH)
    assert created.status_code == 201, created.text
    chat_id = created.json()["chat"]["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "first", "bookmark_id": "agent_test"}
    response = client.post("/agent", json=payload, headers=AUTH)
    assert response.status_code == 200 and "event: final" in response.text, response.text
    final = json.loads(response.text.split("event: final\ndata: ", 1)[1].split("\n", 1)[0])
    # The composer learns from the final event whether the next message needs Google consent.
    assert final["google_data"] is False
    assert len(calls) == 1
    paid = totals(store)["calls"]
    monkeypatch.setattr(agent, "agent_model", lambda: pytest.fail("Replay must not consult new model config"))
    replay = client.post("/agent", json=payload, headers=AUTH)
    assert replay.status_code == 200, replay.text
    assert replay.json()["response"] == "A helpful answer"
    assert len(calls) == 1 and totals(store)["calls"] == paid
    assert totals(store)["estimated_cost_nano_usd"] == 132000


@pytest.mark.parametrize("pro,admin", [(False, False), (True, False), (False, True)])
def test_agent_is_open_to_every_account_and_premium_models_stay_pro(api, monkeypatch, pro, admin):
    client, store, calls = api
    monkeypatch.setattr(agent, "is_user_pro", lambda uid: pro)
    monkeypatch.setattr(agent, "is_user_admin", lambda uid: admin)
    assert client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).status_code == 201
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "r1", "bookmark_id": "bm1"}
    assert client.post("/agent", json=payload, headers=AUTH).status_code == 200
    assert len(calls) == 1
    premium = {**payload, "client_request_id": "r2", "model_id": cfg.ANTHROPIC_PRO_MODEL}
    response = client.post("/agent", json=premium, headers=AUTH)
    assert response.status_code == (200 if pro or admin else 403)
    comparison = {**payload, "client_request_id": "r3",
                  "comparison_models": {"openai": cfg.OPENAI_SOL_MODEL, "deepseek": cfg.DEEPSEEK_PRO_MODEL}}
    assert client.post("/agent", json=comparison, headers=AUTH).status_code == (200 if pro or admin else 403)
    assert len(calls) == (3 if pro or admin else 1)


# What a page from before the one mode (2026-10-31) sends as agent_preferences.
LEGACY_PREFERENCES = {"depth": "quick", "quorum": "fast", "autonomy": "free", "judges": "off", "audit": "off",
                      "vm": "on"}


def test_old_preferences_read_in_todays_form():
    assert AgentPreferences.model_validate(LEGACY_PREFERENCES).model_dump() == {"vm": "on"}
    assert AgentPreferences.model_validate({"audit": "on", "judges": "off"}).model_dump() == {"vm": "off"}


def test_every_account_runs_the_one_mode_whatever_an_older_page_sends(api, monkeypatch):
    """Since 2026-10-31 the Agent has one mode for every account, Free
    included: the comparison models follow the work and review the answer. A
    page from before still sends its comparison-mode preferences: accepted
    and ignored, the turn keeps what the route set."""
    client, store, calls = api
    monkeypatch.setattr(agent, "is_user_pro", lambda uid: False)
    monkeypatch.setattr(agent, "get_user_tier", lambda uid: "free")
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "old-tab", "bookmark_id": "bm1",
               "agent_preferences": LEGACY_PREFERENCES}
    response = client.post("/agent", json=payload, headers=AUTH)
    assert response.status_code == 200 and "event: final" in response.text, response.text
    turn = next(t for t in store.list_turns(UID, chat_id)["turns"] if t["question"] == "Hi")
    settings = store.get_turn(UID, chat_id, turn["id"])["agent_settings"]
    assert settings["agent_preferences"] == {"vm": "off"} and "audit_compare" not in settings
    names = {tool["function"]["name"] for tool in calls[0].get("tools") or [] if tool.get("type") == "function"}
    assert "compare_models" in names and "check_text" not in names
    assert len(calls) == 1 and calls.reviews
    # Whatever an older page held, also a value its own rules refused, is no 422.
    for preferences in ({"depth": "deep"}, {}, None, LEGACY_PREFERENCES):
        replay = client.post("/agent", json={**payload, "agent_preferences": preferences}, headers=AUTH)
        assert replay.status_code == 200 and replay.json()["response"] == "A helpful answer"
    assert len(calls) == 1


def test_an_old_turn_with_the_comparison_preferences_still_recovers(api, monkeypatch):
    """A turn from before the one mode froze six preferences, one from before
    the account's VM access changed another vm. Neither is part of the
    request identity: the replay returns the saved answer without a model
    call, from an older page and from today's."""
    client, store, calls = api
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "before", "bookmark_id": "bm1"}
    assert "event: final" in client.post("/agent", json=payload, headers=AUTH).text
    turn = next(t for t in store.list_turns(UID, chat_id)["turns"] if t["question"] == "Hi")
    ref = store._turn_ref(UID, chat_id, turn["id"])
    ref.update({"agent_settings": {**ref.get().to_dict()["agent_settings"],
                                   "agent_preferences": {**LEGACY_PREFERENCES, "vm": "off"}}})
    monkeypatch.setenv("AGENT_VM_ACCESS", "all")
    for body in ({**payload, "agent_preferences": LEGACY_PREFERENCES}, payload, {**payload, "recover_only": True}):
        replay = client.post("/agent", json=body, headers=AUTH)
        assert replay.status_code == 200, replay.text
        assert replay.json()["response"] == "A helpful answer"
        assert replay.json()["turn"]["agent_settings"]["agent_preferences"]["audit"] == "off"
    assert len(calls) == 1


def test_recovering_a_failed_turn_never_calls_a_model_and_names_its_request(api):
    """recover_only returns a failed turn as saved, without a model call or a
    charge. Its comparison models are part of the request identity; the
    preferences an older page still sends are not."""
    from app.services import agent_quota
    client, store, calls = api
    chat_id, turn = pending(store)
    store.claim(UID, chat_id, turn["id"], AgentModel())
    store.settle(UID, chat_id, turn["id"], completion=receipt(), status="failed")
    payload = {"chat_id": chat_id, "question": "Question one", "client_request_id": "one", "bookmark_id": "bm1",
               "recover_only": True}
    ledger = agent_quota.quota_ref(store.db, UID, agent_quota.day_key() + agent_quota.LEDGER_UNIT)
    before = ledger.get().to_dict()
    response = client.post("/agent", json=payload, headers=AUTH)
    assert response.status_code == 200, response.text
    assert response.json()["turn"]["status"] == "failed"
    other = {**payload, "comparison_models": {"openai": "gpt-5.4-mini", "anthropic": "claude-haiku-4-5"}}
    assert client.post("/agent", json=other, headers=AUTH).status_code == 409
    for preferences in (LEGACY_PREFERENCES, {"depth": "deep"}):
        assert client.post("/agent", json={**payload, "agent_preferences": preferences}, headers=AUTH).status_code == 200
    assert calls == [] and calls.reviews == [] and ledger.get().to_dict() == before


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


def test_full_bookmark_storage_says_so_and_recovers_after_space_is_freed(api):
    """Local run 2026-10-19: the answer finished, the bookmark cap refused its
    sidebar entry and "Recover saved answer" ended in a 500 Chat storage error."""
    client, store, calls = api
    usage = store.db.collection(persistence_guard.USAGE_COLLECTION).document(
        persistence_guard._owner_key("bookmarks", UID))
    usage.set({"bookmark_count": persistence_guard.MAX_BOOKMARKS_PER_USER, "bookmark_bytes": 0})
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "full", "bookmark_id": "bm1"}
    response = client.post("/agent", json=payload, headers=AUTH)
    assert "event: final" not in response.text
    error = json.loads(response.text.split("event: error\ndata: ")[1].split("\n\n")[0])
    assert error["code"] == "bookmark_count_limit"
    assert "chats are full" in error["error"]
    assert error["recoverable"] is True and error["recovery_state"] == "saved"
    recover = {**payload, "recover_only": True}
    refused = client.post("/agent", json=recover, headers=AUTH)
    assert refused.status_code == 409
    assert refused.json()["code"] == "bookmark_count_limit" and refused.json()["recoverable"] is True
    usage.set({"bookmark_count": persistence_guard.MAX_BOOKMARKS_PER_USER - 1, "bookmark_bytes": 0})
    recovered = client.post("/agent", json=recover, headers=AUTH)
    assert recovered.status_code == 200 and recovered.json()["response"] == "A helpful answer"
    assert recovered.json()["bookmark_meta"]
    assert len(calls) == 1


def test_old_replay_keeps_newest_bookmark_and_sums_both_calls(api):
    client, store, calls = api
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat_id, "question": "First", "client_request_id": "first", "bookmark_id": "bm1"}
    assert "event: final" in client.post("/agent", json=payload, headers=AUTH).text
    assert "event: final" in client.post("/agent", json={**payload, "question": "Second", "client_request_id": "second"}, headers=AUTH).text
    assert client.post("/agent", json={**payload, "recover_only": True}, headers=AUTH).status_code == 200
    saved = store.db.collection("users").document(UID).collection("bookmarks").document("bm1").get().to_dict()
    assert saved["query"] == "Second"
    assert len(calls) == 2 and totals(store)["estimated_cost_nano_usd"] == 264000


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
    assert "event: delta" not in response.text
    # The step broke off before the user saw a word, so it ran once more
    # (since 2026-10-27); both attempts are paid.
    assert totals(store)["measured_calls"] == 2
    assert totals(store)["estimated_cost_nano_usd"] == 2 * 132000
    assert store.list_turns(UID, chat_id)["turns"][0]["status"] == "failed"
    error = json.loads(response.text.split("event: error\ndata: ")[1].split("\n\n")[0])
    # What each attempt cost, $0.000132, in micro-euros (1 EUR = 1.15 USD,
    # rounded up), twice.
    assert error["token_budget"]["used"] == 2 * 115
    assert error["token_budget"]["reserved"] == 0
    assert error["token_budget"]["remaining"] == 250000 - 2 * 115
    receipts = [r for r in store.db.documents.values() if isinstance(r, dict) and "quota_charged" in r]
    assert [r["quota_charged"] for r in receipts] == [115, 115]
    assert error['recoverable'] is True
    count = len(store.db.documents)
    for _ in range(3):
        retry = client.post('/agent', json={'chat_id': chat_id, 'question': 'Hi', 'client_request_id': 'failed',
            'bookmark_id': 'bm1', 'recover_only': True}, headers=AUTH)
        assert retry.status_code == 200
        assert retry.json()['response'] == ''  # Unfinished routing text was never published.
        assert retry.json()['turn']['status'] == 'failed'
        assert retry.json()['turn']['agent_failure']['code'] == 'provider_error'
    assert len(store.db.documents) == count
    assert totals(store)['calls'] == 2
    turn = store.list_turns(UID, chat_id)["turns"][0]
    data = client.get(f"/agent/chats/{chat_id}/turns/{turn['id']}/agents", headers=AUTH).json()
    assert data["token_budget"]["remaining"] == 250000 - 2 * 115
    assert data["token_budget"]["observed_at"] >= error["token_budget"]["observed_at"]


def test_quota_failure_returns_current_allowance_and_reservation_reason(api):
    from app.services import agent_quota
    client, store, calls = api
    agent_quota.quota_ref(store.db, UID, agent_quota.day_key() + agent_quota.LEDGER_UNIT).set({"used": 249900})
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
    # The pinned default (deepseek_default_agent) is the registry's DeepSeek
    # Flash since 2026-10-15, so it is listed once, by its registry ID.
    assert models[cfg.DEEPSEEK_FLASH_MODEL]["reasoning_efforts"] == ["default", "low", "high", "max"]
    assert "none" not in models[cfg.DEFAULT_GEMINI_MODEL]["reasoning_efforts"]
    # Grok 4.3 is one entry whose level the menu sets (no "No reasoning" variant).
    assert cfg.GROK_NO_REASONING_MODEL not in models
    assert models["grok-4.3"]["label"] == "Grok 4.3"
    assert models["grok-4.3"]["reasoning_efforts"] == ["default", "none", "low", "medium", "high"]
    expected = set(cfg.ALL_ALLOWED_MODELS)
    assert set(models) == expected
    assert len(response.json()["models"]) == len(models)
    assert {item['provider'] for item in models.values()} == set(cfg.PROVIDERS)
    # Unter ZDR nicht bedienbare Modelle (z. B. Muse Spark) bietet Agent nicht an.
    pro_models = {p.pro_model for p in cfg.PROVIDERS.values()} - cfg.ZDR_UNAVAILABLE_MODEL_IDS
    assert not set(models) & cfg.ZDR_UNAVAILABLE_MODEL_IDS
    for provider in cfg.PROVIDERS.values():
        if provider.pro_model not in pro_models:
            continue
        assert models[provider.pro_model]['provider'] == provider.key
        assert models[provider.pro_model]['provider_label'] == provider.label
    assert all("web_search" in item["tools_by_effort"]["default"] for item in models.values() if item['available'])
    # Admin presets may contain only a subset of families; the chat catalog
    # must still offer every configured Pro model.
    monkeypatch.setitem(cfg.CONSENSUS_PRESET_MODELS, 'thorough', {'answers': {
        'openai': cfg.OPENAI_SOL_MODEL, 'deepseek': cfg.DEEPSEEK_PRO_MODEL}})
    trimmed_preset_models = {item['id'] for item in client.get('/agent/models', headers=AUTH).json()['models']}
    assert cfg.PREMIUM_MODELS <= trimmed_preset_models
    assert pro_models <= trimmed_preset_models
    # Every account sees the catalog; premium models carry their flag.
    monkeypatch.setattr(agent, "is_user_pro", lambda uid: False)
    listed = client.get("/agent/models", headers=AUTH)
    assert listed.status_code == 200
    assert {item['id'] for item in listed.json()['models'] if item.get('premium')} == cfg.PREMIUM_MODELS & trimmed_preset_models
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


def test_high_reasoning_levels_are_pro(api, monkeypatch):
    client, store, calls = api
    monkeypatch.setattr(agent, "is_user_pro", lambda uid: False)
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "first", "bookmark_id": "bm1",
        "model_id": "gpt-5.6-luna", "reasoning_effort": "high"}
    response = client.post("/agent", json=payload, headers=AUTH)
    assert response.status_code == 403 and "Pro" in response.json()["detail"]
    assert store.get_chat(UID, chat_id)["turn_count"] == 0 and not calls
    assert "event: final" in client.post("/agent", json={**payload, "reasoning_effort": "low"}, headers=AUTH).text


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
    # The earlier question comes back as it was sent, its app context included (prompt cache).
    earlier = calls[1]["messages"][1:3]
    assert [message["role"] for message in earlier] == ["user", "assistant"]
    assert strip_app_context(earlier[0]["content"]) == "Hi" and earlier[0]["content"].startswith(APP_CONTEXT_OPEN)
    assert earlier[1]["content"] == "A helpful answer"
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
    assert requests[0]["provider"] == {"sort": "throughput", "data_collection": "deny"}
    assert completion.text == "Answer"
    assert completion.reasoning_truncated
    assert completion.reasoning_chars == 32000
    serialized = json.dumps(completion.activity)
    assert "secret" not in serialized and "duplicate" not in serialized
    assert "Summary continued" in serialized and "legacy alias" in serialized
    assert all(event["version"] == 1 for event in events if event["type"] == "activity")


@pytest.mark.real_prices
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
    # Exceed the token window, not just its byte count, while the history
    # still fits the character budget that would cut it (history_start):
    # sized from that budget, not a fixed count. 10000 repeats stood within
    # 20 characters of it, and a longer prompt (2026-10-30) cut the history.
    from app.services import prompt_config
    budget = agent_runs.CONTEXT_CHAR_LIMIT - len(prompt_config.get_config()["prompts"]["agent"]) - len("Continue")
    value.text = "Old answer " * ((budget - 2000) // len("Old answer "))
    store.claim(UID, chat_id, turn["id"], AgentModel())
    store.settle(UID, chat_id, turn["id"], completion=value, status="succeeded")
    monkeypatch.setenv("AGENT_MODEL", "openai/gpt-3.5-turbo")
    response = client.post("/agent", headers=AUTH, json={"chat_id": chat_id, "question": "Continue",
        "client_request_id": "small", "bookmark_id": "bm1"})
    assert response.status_code == 422 and "too long" in response.text
    assert totals(store)["calls"] == 1
    assert not calls


def test_history_start_keeps_the_newest_messages_and_moves_in_steps():
    from app.services.agent_runs import history_start
    assert history_start([10] * 5, 100) == 0
    # The smallest cut is rounded up to a multiple of HISTORY_STEP_TURNS (4),
    # so the replayed history starts at the same message for a while.
    assert [history_start([10] * n, 105) for n in range(20, 24)] == [12, 12, 12, 16]
    # Rounding never drops the last messages that still fit.
    assert history_start([50, 50, 50], 100) == 1
    # The newest earlier message alone is too long: only the new question.
    assert history_start([10, 200], 100) == 2


def _answered(store, chat_id, request_id, answer):
    _, turn = pending(store, chat_id=chat_id, request_id=request_id, question=f"Question {request_id}")
    value = receipt()
    value.text = answer
    store.claim(UID, chat_id, turn["id"], AgentModel())
    store.settle(UID, chat_id, turn["id"], completion=value, status="succeeded")


def test_a_long_chat_keeps_its_newest_messages_instead_of_failing(store, monkeypatch):
    """Audit A9: past CONTEXT_CHAR_LIMIT every further message failed, and
    the failed turn was saved as "provider_error, trying again usually works"."""
    from app.services import agent_runs
    system = "Answer."
    monkeypatch.setattr(agent_runs.prompt_config, "get_config", lambda: {
        "prompts": {"agent": system}, "reference_timezone": "Europe/Berlin"})
    monkeypatch.setattr(agent_runs, "CONTEXT_CHAR_LIMIT", 40_000)
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    for index in range(10):
        _answered(store, chat_id, f"r{index}", "x" * 9_000)
    _, target = pending(store, chat_id=chat_id, request_id="new", question="Continue")
    messages = store.messages(UID, chat_id, target)
    kept = [m["content"] for m in messages[1:-1] if m["role"] == "user"]
    # Four messages fit; the cut (6) is rounded up to the next step (8).
    assert kept == ["Question r8", "Question r9"]
    assert agent_runs.HISTORY_OMITTED_NOTE in messages[-1]["content"]
    assert agent_runs.strip_app_context(messages[-1]["content"]) == "Continue"
    assert sum(len(m["content"]) for m in messages[:-1]) <= 40_000
    # A short chat says nothing about omitted messages.
    short = store.create_chat(UID, execution_mode="agent")["id"]
    _answered(store, short, "s0", "Short answer")
    _, target = pending(store, chat_id=short, request_id="s1", question="Continue")
    assert agent_runs.HISTORY_OMITTED_NOTE not in store.messages(UID, short, target)[-1]["content"]


def test_refusals_that_would_repeat_never_say_try_again():
    from app.services.agent_files import FileUnavailable
    from app.services.agent_provider_limits import agent_failure
    from app.services.agent_runs import ConversationTooLong
    from app.services.google_connections import GoogleError

    class Rejected(Exception):
        status_code = 400

    class Busy(Exception):
        status_code = 502

    cases = {"provider_rejected": Rejected("raw provider body"),
             "conversation_too_long": ConversationTooLong("This conversation is too long for the selected model."),
             "file_unavailable": FileUnavailable("The file has expired or is no longer available."),
             "google_error": GoogleError("Google authorization expired or was revoked. Reconnect the account.", 401)}
    for code, error in cases.items():
        failure = agent_failure(error)
        assert failure["code"] == code
        assert "try again" not in failure["error"].lower() and "raw provider body" not in failure["error"]
    assert agent_failure(cases["file_unavailable"])["error"] == "The file has expired or is no longer available."
    assert agent_failure(Busy())["code"] == "provider_error"


def test_agent_history_never_queries_empty_model_answers(store, monkeypatch):
    chat_id, turn = pending(store)
    monkeypatch.setattr(store, "_model_answers", lambda *args: pytest.fail("Agent turns have no model_answers subcollection"))
    assert store.get_turn(UID, chat_id, turn["id"])["id"] == turn["id"]
    assert len(store.list_turns(UID, chat_id)["turns"]) == 1


@pytest.mark.real_prices
@pytest.mark.parametrize("model_id", ["moonshotai/kimi-k3.1-pro", "openai/gpt-4o"])
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
