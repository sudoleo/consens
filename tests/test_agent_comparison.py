"""Paid-step accounting and exact-version review through the real shared judges."""
from dataclasses import replace
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services import agent_quota, agent_budget_config
from app.services.agent_comparison import comparison_selection, review_is_bound
from app.services.agent_delegation import DelegationLoop
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.llm.agent_client import AgentCompletion, measured_usage, resolve_agent_model
from app.services.llm.provider_runtime import ProviderCancellation, ProviderCancelled, AnalysisBudgetExceeded
from test_agent_runs import UID, AUTH, api, pending, receipt, store


class Script:
    def __init__(self, *, compares=1, revise=False, missing=False, fail_coverage=False, fail_model=False):
        self.compares, self.revise, self.missing = compares, revise, missing
        self.fail_coverage, self.fail_model = fail_coverage, fail_model
        self.calls, self.prompts = [], []
        self.loop = None

    def factory(self):
        script = self
        class Completion(AgentCompletion):
            def stream(self, *, model, messages, **kwargs):
                script.calls.append((self.step_id, model.model))
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001,
                    "prompt_tokens_details": {"cached_tokens": 20}, "completion_tokens_details": {"reasoning_tokens": 10}}, model)
                if self.step_id.startswith("completion:"):
                    index = int(self.step_id.split(":")[-1])
                    if index < script.compares:
                        if script.compares > 1:
                            self.text = f"I will compare perspective {index + 1}."
                            yield {"type": "delta", "text": self.text}
                        args = {"question": f"Evaluate option {index + 1}", "context": "Budget is 100. Source: https://example.org/report", "reason": "Compare trade-offs"}
                        action = "compare_models"
                    else:
                        self.text = "The first option costs 100."
                        if script.revise and index > script.compares:
                            self.text = "The first option costs 100. The constraint matters."
                        yield {"type": "delta", "text": self.text}
                        if script.missing:
                            self.finish_reason = "stop"
                            return
                        action, args = "judge_answer", {"finalize": not script.revise or index > script.compares}
                    self.tool_calls = [{"id": f"call_{index}", "type": "function", "function": {"name": action, "arguments": json.dumps(args)}}]
                    self.finish_reason = "tool_calls"
                    return
                schema = (model.request_config.get("response_format") or {}).get("json_schema", {}).get("schema")
                if schema:
                    if "sentences" in schema["properties"]:
                        if script.fail_coverage:
                            raise RuntimeError("Coverage unavailable")
                        properties = schema["properties"]["sentences"]["items"]["properties"]
                        self.text = json.dumps({"sentences": [{"id": key, "classification": "claim", "models": {name: "supports" for name in properties["models"]["properties"]}, "counter_quotes": []} for key in properties["id"]["enum"]]})
                    else:
                        self.text = json.dumps({"differences": [], "best_model": "Model A"})
                else:
                    script.prompts.append(messages)
                    if script.fail_model and model.model.startswith("anthropic"):
                        raise RuntimeError("Comparison unavailable")
                    self.text = "The first option costs 100. The constraint matters."
                self.finish_reason = "stop"
                yield {"type": "delta", "text": self.text}
        return Completion()


def make_loop(store, script, *, check_sources=False, source_limits=None):
    chat, turn = pending(store)
    config = {**defaults(), "enabled": False, "max_searches": 0, "context_chars": 120_000}
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"), messages=[{"role": "system", "content": "Answer."}, {"role": "user", "content": "Compare options"}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.from_config({**config, "enabled": True}),
        delegation_config=config, completion_factory=script.factory,
        check_sources=check_sources, source_limits=source_limits,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}))
    script.loop = loop
    return loop


@pytest.mark.parametrize("compares,revise", [(1, False), (2, False), (1, True)])
def test_real_judges_exact_versions_context_sources_and_all_usage(store, compares, revise):
    script = Script(compares=compares, revise=revise)
    loop = make_loop(store, script)
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    review = saved["agent_review"]
    assert saved["status"] == "completed"
    assert review["status"] == "succeeded"
    assert len(review["versions"]) == 1 + revise
    assert saved["consensus"] == review["versions"][-1]["text"]
    assert len(review["checks"]) == compares
    assert review_is_bound(review, saved["consensus"])
    assert not review_is_bound(review, saved["consensus"] + "changed")
    assert all(c["differences_data"]["judges"]["differences"]["provider"] != "Claude" for c in review["checks"])
    assert all(c["answer_hash"] == review["answer_hash"] for c in review["checks"])
    for i in range(compares):
        assert script.prompts[2 * i] == script.prompts[2 * i + 1]
        assert "https://example.org/report" in script.prompts[2 * i][1]["content"]
        assert "first option costs" not in script.prompts[2 * i][1]["content"]
    usage = saved["agent_usage"]
    assert usage["input_tokens"] + usage["output_tokens"] == len(script.calls) * 70
    quota = agent_quota.quota_ref(store.db, UID, agent_quota.day_key()).get().to_dict()
    assert quota["used"] == len(script.calls) * 70 and quota["reserved"] == 0
    assert any(e["type"] == "review" and e["review"]["status"] == "running" for e in events)
    tools = [e for e in events if e.get("kind") == "tool" and e.get("name") == "compare_models"]
    assert [e["status"] for e in tools] == [s for _ in range(compares) for s in ("running", "succeeded")]
    assert sum(e["type"] == "delta" for e in events) == 1 + revise + (compares if compares > 1 else 0)
    assert all("I will compare" not in v["text"] for v in review["versions"])
    assert store.delegation_view(UID, loop.chat_id, loop.turn_id)["agents"]


@pytest.mark.parametrize("failure,expected", [("fail_coverage", "partial"), ("fail_model", "failed")])
def test_partial_or_failed_checks_never_certify_success(store, failure, expected):
    script = Script(**{failure: True})
    loop = make_loop(store, script)
    list(loop.run())
    review = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]
    assert review["status"] == expected


def test_missing_tool_is_bounded_and_persists_unchecked_answer(store):
    script = Script(missing=True)
    loop = make_loop(store, script)
    with pytest.raises(AnalysisBudgetExceeded, match="required answer review"):
        list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "failed"
    assert saved["agent_review"]["status"] == "missing"
    assert saved["consensus"] == "The first option costs 100."
    assert len(script.calls) == 5


def test_atomic_daily_budget_and_duplicate_settlement(store, monkeypatch):
    monkeypatch.setenv("AGENT_DAILY_TOKEN_LIMIT", "100")
    loops = [make_loop(store, Script()) for _ in range(2)]
    def claim(loop):
        try:
            return store.claim(UID, loop.chat_id, loop.turn_id, loop.model, run_token=loop.run_token,
                policy=loop.policy.snapshot(), reservation=(60, 100))
        except AnalysisBudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(claim, loops))
    assert sum(claims) == 1
    loop = loops[claims.index(True)]
    value = receipt()
    value.usage = measured_usage({"prompt_tokens": 10, "completion_tokens": 5,
        "prompt_tokens_details": {"cached_tokens": 5}, "completion_tokens_details": {"reasoning_tokens": 5}}, loop.model)
    for _ in range(2):
        store.settle(UID, loop.chat_id, loop.turn_id, completion=value, status="cancelled", final=False)
    quota = agent_quota.quota_ref(store.db, UID, agent_quota.day_key()).get().to_dict()
    assert quota["used"] == 15 and quota["reserved"] == 0


@pytest.mark.parametrize("remaining", [0, 40000])
def test_quota_rejection_distinguishes_empty_from_insufficient_reservation(remaining):
    data = {"used": 250000 - remaining}
    with pytest.raises(agent_quota.AgentTokenBudgetExceeded) as error:
        agent_quota.reserve(data, 50000)
    assert error.value.remaining == remaining and error.value.required == 50000
    assert error.value.code == ("agent_token_reservation" if remaining else "agent_tokens_exhausted")
    if remaining:
        assert 'Completed calls release their reservations' in str(error.value)
    assert "reserved" not in data


def test_admin_budget_is_enforced_and_reset_isolated_from_inflight_settlement(store):
    config = agent_budget_config.store(store.db)
    config.save(expected_revision=0, updated_by='admin', daily_token_limit=2000)
    loop = make_loop(store, Script())
    params = dict(run_token=loop.run_token, policy=loop.policy.snapshot())
    with pytest.raises(agent_quota.AgentTokenBudgetExceeded):
        store.claim(UID, loop.chat_id, loop.turn_id, loop.model, reservation=(2001, 100), **params)
    assert store.claim(UID, loop.chat_id, loop.turn_id, loop.model, reservation=(1500, 100), **params)
    store.protect_review(UID, loop.chat_id, loop.turn_id, loop.run_token, 400)
    assert agent_quota.snapshot(store.db, UID)['remaining'] == 100
    config.save(expected_revision=1, updated_by='admin', reset=True)
    assert agent_quota.snapshot(store.db, UID)['remaining'] == 2000
    store.settle(UID, loop.chat_id, loop.turn_id, completion=receipt(), status='succeeded', final=False)
    assert agent_quota.snapshot(store.db, UID)['used'] == 0
    # Review holds move once to the fresh generation before further work.
    store.protect_review(UID, loop.chat_id, loop.turn_id, loop.run_token, 600)
    assert agent_quota.snapshot(store.db, UID)['reserved'] == 600
    old = agent_quota.quota_ref(store.db, UID, agent_quota.day_key()).get().to_dict()
    assert old['used'] == 1100 and old['reserved'] == 0
    assert store.claim(UID, loop.chat_id, loop.turn_id, loop.model, step='completion:1', reservation=(800, 100), **params)
    assert agent_quota.snapshot(store.db, UID)['reserved'] == 800
    store.settle(UID, loop.chat_id, loop.turn_id, completion=receipt(), status='succeeded', step='completion:1', final=False)
    assert agent_quota.snapshot(store.db, UID)['used'] == 1100



@pytest.mark.parametrize("remaining,succeeds,context_room", [(70000, True, None), (100, False, None), (70000, False, 0)])
def test_search_reservation_can_fall_back_without_extra_paid_claim(store, remaining, succeeds, context_room):
    calls = []
    class Completion(AgentCompletion):
        def stream(self, *, model, messages, **kwargs):
            calls.append(kwargs)
            assert "Web search is unavailable" in messages[0]["content"]
            assert kwargs["native_searches"] == 0
            self.text, self.finish_reason = "Answer from existing evidence.", "stop"
            self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20}, model)
            yield {"type": "delta", "text": self.text}
    loop = make_loop(store, Script())
    loop.factory = Completion
    loop.search_remaining = 1
    loop.model = replace(loop.model, request_config={**loop.model.request_config, "_agent_bounded_search": True})
    if context_room is not None:
        loop.policy = replace(loop.policy, context_chars=len(json.dumps(loop.messages, ensure_ascii=False)) + context_room)
    ref = agent_quota.quota_ref(store.db, UID, agent_quota.day_key())
    ref.set({"used": 250000 - remaining})
    if succeeds:
        events = list(loop.run())
        assert len(calls) == 1 and loop.costs.calls == 1
        assert any(e.get("name") == "web_search" and e.get("status") == "blocked" for e in events)
        assert ref.get().to_dict()["used"] == 250000 - remaining + 70
        assert ref.get().to_dict()["reserved"] == 0
    else:
        with pytest.raises(AnalysisBudgetExceeded, match="context limit" if context_room is not None else "reservation"):
            list(loop.run())
        assert calls == [] and loop.costs.calls == 0 and loop.costs.tokens == 0
        assert ref.get().to_dict() == {"used": 250000 - remaining}
    assert loop.search_remaining == 1


def test_unknown_terminal_usage_releases_admission_and_utc_day_is_separate(store, monkeypatch):
    loop = make_loop(store, Script())
    monkeypatch.setattr(agent_quota, "day_key", lambda: "2026-09-19")
    assert store.claim(UID, loop.chat_id, loop.turn_id, loop.model, run_token=loop.run_token,
        policy=loop.policy.snapshot(), reservation=(500, 100))
    store.settle(UID, loop.chat_id, loop.turn_id, completion=receipt(measured=False), status="cancelled", final=False)
    quota = agent_quota.quota_ref(store.db, UID, "2026-09-19").get().to_dict()
    assert quota['reserved'] == 0 and quota['unknown'] == quota['unknown_released'] == 500
    assert agent_quota.public(agent_quota.quota_ref(store.db, UID, "2026-09-20").get().to_dict())["remaining"] == 250000


def test_configured_default_uses_cross_family_judges(store):
    loop = make_loop(store, Script())
    loop.model = resolve_agent_model()
    list(loop.run())
    review = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]
    assert review["status"] == "succeeded"
    assert review["checks"][0]["differences_data"]["judges"]["differences"]["provider"] != "DeepSeek"


def test_midnight_moves_only_unspent_review_hold(store, monkeypatch):
    loop = make_loop(store, Script())
    args = (UID, loop.chat_id, loop.turn_id)
    monkeypatch.setattr(agent_quota, "day_key", lambda: "2026-09-19")
    assert store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(100, 100))
    store.settle(*args, completion=receipt(measured=False), status="succeeded", final=False)
    store.protect_review(*args, loop.run_token, 200)
    monkeypatch.setattr(agent_quota, "day_key", lambda: "2026-09-20")
    assert store.claim(*args, loop.model, step="completion:1", run_token=loop.run_token, reservation=(50, 100))
    previous = agent_quota.quota_ref(store.db, UID, '2026-09-19').get().to_dict()
    assert previous['reserved'] == 0 and previous['unknown'] == previous['unknown_released'] == 100
    assert agent_quota.quota_ref(store.db, UID, "2026-09-20").get().to_dict()["reserved"] == 200


def test_disconnect_during_review_settles_every_paid_call_and_marks_stopped(store):
    loop = make_loop(store, Script())
    source = loop.run()
    for event in source:
        if event["type"] == "review" and event["review"]["status"] == "running":
            loop.cancellation.cancel()
            break
    source.close()
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "failed"
    assert saved["agent_review"]["status"] == "cancelled"
    root = store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert "running" not in root["step_states"].values()
    assert root["run_status"] == "cancelled"


def test_failed_review_recovery_preserves_status_and_never_calls_provider(api):
    client, store, calls = api
    loop = make_loop(store, Script(missing=True))
    with pytest.raises(AnalysisBudgetExceeded):
        list(loop.run())
    payload = {"chat_id": loop.chat_id, "question": "Question one", "client_request_id": "one",
               "bookmark_id": "agent_review_recovery", "recover_only": True}
    before = agent_quota.quota_ref(store.db, UID, agent_quota.day_key()).get().to_dict()
    response = client.post("/agent", json=payload, headers=AUTH)
    assert response.status_code == 200, response.text
    assert response.json()["turn"]["agent_review"]["status"] == "missing"
    assert response.json()["turn"]["status"] == "failed"
    assert calls == []
    assert agent_quota.quota_ref(store.db, UID, agent_quota.day_key()).get().to_dict() == before
    assert client.post("/agent", json={**payload, "comparison_models": {"openai": "gpt-5.4-mini", "anthropic": "claude-haiku-4-5"}}, headers=AUTH).status_code == 409


@pytest.mark.parametrize("committed,failures", [(False, 1), (True, 1), (False, 3)])
def test_transient_settlement_failure_never_repeats_model_or_leaves_run_pending(store, monkeypatch, committed, failures):
    from google.api_core.exceptions import ServiceUnavailable
    original = store.settle
    failed = []
    def settle(*args, **kwargs):
        step = kwargs.get("step", "")
        if step.startswith("agent:") and len(failed) < failures and (not failed or step == failed[0]):
            failed.append(step)
            if committed:
                original(*args, **kwargs)
            raise ServiceUnavailable("temporary settlement failure")
        return original(*args, **kwargs)
    monkeypatch.setattr(store, "settle", settle)
    script = Script()
    loop = make_loop(store, script)
    list(loop.run())
    assert failed and len(script.calls) == len({step for step, model in script.calls})
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed"
    assert saved["agent_review"]["status"] == ("succeeded" if failures == 1 else "failed")
    root = store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert root["run_status"] == "succeeded" and "running" not in root["step_states"].values()
    assert store.db.collection("users").document(UID).get().to_dict()["agent_usage"]["unsettled_calls"] == 0
    assert saved["agent_usage"]["input_tokens"] + saved["agent_usage"]["output_tokens"] == len(script.calls) * 70
