"""Long Agent chats use the account ledger, without time/round cutoffs or paid retries."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import httpx
import pytest

from app.services import agent_sessions, agent_quota
from app.services.agent_delegation import DelegationLoop
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.agent_provider_limits import AgentRunInterrupted
from app.services.llm.agent_client import AgentCompletion, measured_usage, resolve_agent_model
from app.services.llm.provider_runtime import AnalysisBudget, AnalysisBudgetExceeded, ProviderCancellation, ProviderCancelled
from test_agent_runs import UID, AUTH, api, pending, store, totals
from test_agent_comparison import Script, make_loop as comparison_loop


def chat_loop(store, factory):
    chat, turn = pending(store)
    # Persisted old admin values must not silently impose chat cutoffs.
    config = {**defaults(), "max_calls": 1, "max_tools": 1, "seconds": 1,
              "max_tokens": 1, "max_cost_nano_usd": 1, "worker_calls": 1, "max_searches": 0}
    model = resolve_agent_model("claude-haiku-4-5")
    model = replace(model, request_config={**model.request_config, "_agent_bounded_search": True})
    return DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"], model=model,
        messages=[{"role": "system", "content": "Answer."}, {"role": "user", "content": "Work through the task."}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.for_chat(config),
        delegation_config=config, completion_factory=factory)


def clock(monkeypatch):
    class ClockMeta(type):
        def __instancecheck__(cls, instance):
            return isinstance(instance, datetime)
    class Clock(metaclass=ClockMeta):
        stamp = datetime.now(timezone.utc)
        @classmethod
        def now(cls, tz=None):
            return cls.stamp
    monkeypatch.setattr(agent_sessions, "datetime", Clock)
    return Clock


def test_more_than_one_hundred_steps_and_seventeen_minutes_complete_with_live_lease(store, monkeypatch):
    timer = clock(monkeypatch)
    started = timer.stamp
    searches = []
    class Completion(AgentCompletion):
        def stream(self, *, model, native_searches, **kwargs):
            timer.stamp += timedelta(seconds=10)
            store.check_delegation(UID, loop.chat_id, loop.turn_id, loop.run_token)
            loop.budget.consume()
            searches.append(native_searches)
            self.usage = measured_usage({"prompt_tokens": 100, "completion_tokens": 20, "cost": .1}, model)
            index = int(self.step_id.split(":")[-1])
            if index < 101:
                self.tool_calls = [{"id": f"wait-{index}", "type": "function", "function": {
                    "name": "wait_agents", "arguments": '{"seconds":0}'}}]
                self.finish_reason = "tool_calls"
            else:
                self.text, self.finish_reason = "Finished after many rounds.", "stop"
                yield {"type": "delta", "text": self.text}
    loop = chat_loop(store, Completion)
    assert loop.budget.deadline == float("inf")
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    root = store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert saved["status"] == "completed" and saved["consensus"] == "Finished after many rounds."
    assert timer.stamp - started == timedelta(minutes=17)
    assert root["step_states"]["completion:101"] == "succeeded"
    assert root["policy"]["seconds"] is None and root["policy"]["max_calls"] is None
    assert loop.tools_used == 101 and loop.budget.calls == 102
    assert totals(store)["unsettled_calls"] == 0
    assert all(searches)  # Search remains available after the old two-search cap.
    quota = agent_quota.snapshot(store.db, UID)
    assert quota["used"] == 102 * 120 and quota["reserved"] == 0


def test_daily_budget_still_stops_before_any_additional_paid_step_and_saves_reason(store):
    class Completion(AgentCompletion):
        def stream(self, *, model, **kwargs):
            # One paid step exhausts the actual daily budget. The next step must
            # not be dispatched, even with no per-run caps.
            self.usage = measured_usage({"prompt_tokens": 249990, "completion_tokens": 10, "cost": .1}, model)
            self.tool_calls = [{"id": "wait", "type": "function", "function": {"name": "wait_agents", "arguments": '{"seconds":0}'}}]
            self.finish_reason = "tool_calls"
            yield from ()
    loop = chat_loop(store, Completion)
    with pytest.raises(agent_quota.AgentTokenBudgetExceeded):
        list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["agent_failure"]["code"] == "agent_tokens_exhausted"
    assert totals(store)["calls"] == 1 and totals(store)["unsettled_calls"] == 0
    assert agent_quota.snapshot(store.db, UID)["reserved"] == 0


@pytest.mark.parametrize("failure", ["stop", "expired", "superseded"])
def test_lease_renewal_keeps_all_fences_in_sync_but_never_revives_a_stopped_run(store, monkeypatch, failure):
    timer = clock(monkeypatch)
    loop = chat_loop(store, AgentCompletion)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, policy=loop.policy.snapshot(), run_token=loop.run_token, reservation=(1, 1))
    root, chat, active = store.receipt_ref(*args), store._chat_ref(UID, loop.chat_id), store.active_ref(UID)
    original = root.get().to_dict()["lease_until"]
    timer.stamp += timedelta(seconds=35)
    store.check_delegation(*args, loop.run_token)
    renewed = root.get().to_dict()["lease_until"]
    assert renewed > original
    assert chat.get().to_dict()["agent_lock_until"] == active.get().to_dict()["leases"][root.id] == renewed
    store.check_delegation(*args, loop.run_token)
    assert root.get().to_dict()["lease_until"] == renewed
    timer.stamp += timedelta(seconds=35)
    if failure == "stop":
        store.stop_delegation(*args)
    elif failure == "expired":
        timer.stamp = renewed + timedelta(seconds=1)
    else:
        store._transaction(lambda tx: tx.update(chat, {"agent_turn_id": "f" * 32}))
    with pytest.raises((ProviderCancelled, AgentRunInterrupted)):
        store.check_delegation(*args, loop.run_token)
    assert root.get().to_dict()["lease_until"] == renewed


def test_mid_answer_provider_timeout_preserves_text_and_safe_reason_in_history(store):
    class Completion(AgentCompletion):
        def stream(self, *, model, **kwargs):
            self.text = "Already available result."
            self.usage = measured_usage({"prompt_tokens": 20, "completion_tokens": 10}, model)
            yield {"type": "delta", "text": self.text}
            raise httpx.ReadTimeout("private provider body must not be saved")
    loop = chat_loop(store, Completion)
    with pytest.raises(httpx.ReadTimeout):
        list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["consensus"] == "Already available result."
    assert saved["agent_failure"]["code"] == "provider_timeout"
    assert "private provider" not in json.dumps(saved, default=str)


def test_many_comparisons_use_actual_call_reservations_without_fixed_review_hold(store):
    script = Script(compares=5, revise=True)
    loop = comparison_loop(store, script)
    loop.policy = AgentPolicy.for_chat(loop.config)
    loop.costs.policy = loop.policy
    loop.budget = AnalysisBudget(unlimited=True)
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and len(saved["agent_review"]["comparisons"]) == 5
    assert loop.comparison.judge_calls >= 20
    assert store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()["review_hold"] == 0


def test_consensus_and_legacy_analysis_budgets_remain_bounded():
    budget = AnalysisBudget(seconds=0, max_calls=1)
    with pytest.raises(AnalysisBudgetExceeded, match="deadline"):
        budget.check()
    assert not AgentPolicy.from_config(defaults()).account_budget_only


def test_further_comparison_after_review_and_four_revisions_check_the_current_basis(store):
    from app.services.agent_comparison import review_is_bound
    script = Script()
    base = type(script.factory())
    class Completion(base):
        def stream(self, *, model, messages, **kwargs):
            if not self.step_id.startswith("completion:"):
                yield from super().stream(model=model, messages=messages, **kwargs)
                return
            index = int(self.step_id.split(":")[-1])
            self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
            if index in {0, 2}:
                action = "compare_models"
                args = {"question": f"Check option {index}", "context": "Budget is 100.", "reason": "New perspective"}
            else:
                self.text = "The first option costs 100." + (f" Revision {index - 2}." if index >= 4 else "")
                yield {"type": "delta", "text": self.text}
                action, args = "judge_answer", {"finalize": index == 6}
            self.tool_calls = [{"id": str(index), "type": "function", "function": {"name": action, "arguments": json.dumps(args)}}]
            self.finish_reason = "tool_calls"
    loop = comparison_loop(store, script)
    loop.factory = Completion
    loop.policy = AgentPolicy.for_chat(loop.config)
    loop.costs.policy = loop.policy
    loop.budget = AnalysisBudget(unlimited=True)
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    review = saved["agent_review"]
    assert saved["status"] == "completed" and len(review["comparisons"]) == 2
    assert len(review["versions"]) == 4 and len(review["checks"]) == 2
    assert review_is_bound(review, saved["consensus"])


def test_brief_database_outage_does_not_cancel_a_healthy_producer(store, monkeypatch):
    from google.api_core.exceptions import ServiceUnavailable
    loop = chat_loop(store, AgentCompletion)
    loop.claimed = True
    checks = []
    def check(*args):
        checks.append(args)
        if len(checks) == 1:
            raise ServiceUnavailable("temporary")
    class CloseAfterTwoChecks:
        def wait(self, seconds):
            assert seconds == 3
            return len(checks) == 2
    monkeypatch.setattr(store, "check_delegation", check)
    loop.closed = CloseAfterTwoChecks()
    loop._watch()
    assert len(checks) == 2 and not loop.cancellation.cancelled and loop.watch_error is None


def test_partial_direct_answer_recovery_is_read_only_and_preserves_failure(api, monkeypatch):
    client, store, calls = api
    def stream(self, **kwargs):
        calls.append(kwargs)
        self.text = "Available partial answer."
        self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20}, kwargs["model"])
        yield {"type": "delta", "text": self.text}
        raise httpx.ReadTimeout("private body")
    monkeypatch.setattr(AgentCompletion, "stream", stream)
    chat = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat, "question": "Long task", "client_request_id": "partial", "bookmark_id": "partial_answer"}
    response = client.post("/agent", json=payload, headers=AUTH)
    assert '"code": "provider_timeout"' in response.text and "private body" not in response.text
    error = next(json.loads(line[6:]) for line in response.text.splitlines()
                 if line.startswith('data: ') and '"saved_answer"' in line)
    assert error["recovery_state"] == "saved"
    assert error["saved_answer"]["turn"]["status"] == "failed"
    assert error["saved_answer"]["bookmark_meta"]["id"] == "partial_answer"
    assert store.db.collection("users").document(UID).collection("bookmarks").document("partial_answer").get().exists
    before = agent_quota.snapshot(store.db, UID)["used"]
    for _ in range(2):
        recovered = client.post("/agent", json={**payload, "recover_only": True}, headers=AUTH)
        assert recovered.status_code == 200
        assert recovered.json()["response"] == "Available partial answer."
        assert recovered.json()["turn"]["agent_failure"]["code"] == "provider_timeout"
        assert recovered.json()["turn"]["status"] == "failed"
    assert len(calls) == 1 and agent_quota.snapshot(store.db, UID)["used"] == before


def test_failure_before_answer_preserves_question_activity_and_bookmark(api, monkeypatch):
    client, store, calls = api
    def stream(self, **kwargs):
        calls.append(kwargs)
        yield {"type": "activity", "kind": "reasoning", "id": "thinking", "step_id": self.step_id,
               "format": "summary", "text": "Checking the available information."}
        raise httpx.ReadTimeout("private provider body")
    monkeypatch.setattr(AgentCompletion, "stream", stream)
    chat = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat, "question": "Preserve this failed question", "client_request_id": "empty", "bookmark_id": "empty_answer"}
    response = client.post('/agent', json=payload, headers=AUTH)
    failure = json.loads(response.text.split('event: error\ndata: ')[1].split('\n\n')[0])
    saved = failure['saved_answer']
    assert saved['response'] == '' and saved['turn']['status'] == 'failed'
    assert saved['turn']['agent_failure']['code'] == 'provider_timeout'
    assert any(event.get('status') == 'working' for event in saved['turn']['agent_activity'])
    assert not any(event.get('kind') == 'reasoning' for event in saved['turn']['agent_activity'])
    bookmark = store.db.collection('users').document(UID).collection('bookmarks').document('empty_answer').get()
    assert bookmark.exists and bookmark.to_dict()['query'] == payload['question']
    recovered = client.post('/agent', json={**payload, 'recover_only': True}, headers=AUTH)
    assert recovered.status_code == 200 and recovered.json()['response'] == ''
    assert len(calls) == 1


def test_recovery_reaps_expired_producer_and_restores_checkpoint_without_paid_retry(api):
    client, store, calls = api
    loop = chat_loop(store, AgentCompletion)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(100, 100))
    value = AgentCompletion()
    value.usage = measured_usage({"prompt_tokens": 20, "completion_tokens": 10}, loop.model)
    store.settle(*args, completion=value, status="succeeded", final=False)
    store.save_review(*args, loop.run_token, {"status": "running", "comparisons": [], "versions": []}, "Checkpointed answer.")
    payload = {"chat_id": loop.chat_id, "question": "Question one", "client_request_id": "one",
               "bookmark_id": "expired_answer", "recover_only": True}
    running = client.post('/agent', json=payload, headers=AUTH)
    assert running.status_code == 409 and running.json()["recovery_state"] == "running"
    root = store.receipt_ref(*args)
    store._transaction(lambda tx: tx.update(root, {"lease_until": datetime.now(timezone.utc) - timedelta(seconds=1)}))
    recovered = client.post('/agent', json=payload, headers=AUTH)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["response"] == "Checkpointed answer."
    assert recovered.json()["turn"]["status"] == "failed" and root.get().to_dict()["run_status"] == "cancelled"
    assert store.db.collection("users").document(UID).collection("bookmarks").document("expired_answer").get().exists
    assert calls == [] and totals(store)["input_tokens"] == 20
