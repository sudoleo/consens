"""Source evidence uses the shared validator and paid Agent steps, never a second run."""
import copy
import json

import pytest

from app.services import agent_contradictions as ac, agent_quota
from app.services.agent_comparison import review_is_bound
from app.services.llm.agent_client import AgentCompletion, measured_usage
from app.services.llm.provider_runtime import ProviderCancelled, AnalysisBudgetExceeded
from app.services.source_verification import Limits
from test_agent_comparison import Script, make_loop
from test_agent_runs import UID, AUTH, api, store
from test_contradiction_verification import CONSENSUS, ANSWERS, SOURCES, differences, doc, judge


class SourceScript(Script):
    def __init__(self, *, missing=False, invalid=False, unavailable=False, repeat=False, revise=False, rewrite_during_check=False):
        super().__init__(missing=missing)
        self.invalid, self.unavailable = invalid, unavailable
        self.source_calls = 0
        self.repeat, self.revise = repeat, revise
        self.rewrite_during_check = rewrite_during_check

    def factory(self):
        script = self
        class Completion(AgentCompletion):
            def stream(self, *, model, messages, tools, **kwargs):
                script.calls.append((self.step_id, model.model))
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                if self.step_id.startswith("completion:"):
                    index = int(self.step_id.split(":")[-1])
                    if index == 0:
                        action, args = "compare_models", {"question": "Price?", "context": "Compare published prices.", "reason": "Conflicting prices"}
                    elif index == 1 or (script.revise and index == 3):
                        self.text = CONSENSUS + (" Check the applicable date." if index == 3 else "")
                        yield {"type": "delta", "text": self.text}
                        action, args = "judge_answer", {"finalize": True}
                    else:
                        if script.rewrite_during_check:
                            self.text = 'Here is a completely rewritten answer.'
                            yield {"type": "delta", "text": self.text}
                        if script.missing:
                            self.finish_reason = "stop"
                            return
                        action, args = "check_contradictions", {"finalize": not ((script.repeat or script.revise) and index == 2)}
                    self.tool_calls = [{"id": f"call_{index}", "type": "function", "function": {"name": action, "arguments": json.dumps(args)}}]
                    self.finish_reason = "tool_calls"
                    return
                if model.request_config.get("response_format") == {"type": "json_object"}:
                    script.source_calls += 1
                    assert tools == []  # No new search, worker delegation or unmetered provider calls.
                    if script.unavailable and script.source_calls == 1:
                        raise TimeoutError("Source judge unavailable")
                    payload = json.loads(messages[-1]["content"])
                    result, _ = judge(payload)
                    if script.invalid:
                        result["findings"][0]["evidence"][0]["quote"] = "Invented source evidence."
                    self.text = json.dumps(result)
                else:
                    provider = "Anthropic" if model.model.startswith("anthropic/") else "OpenAI"
                    self.text, self.sources = ANSWERS[provider], SOURCES[provider]
                self.finish_reason = "stop"
                yield {"type": "delta", "text": self.text}
        return Completion()


@pytest.fixture
def shared_judges(monkeypatch):
    from app.services.llm import consensus_engine
    data = {**differences(), "judges": {"differences": {"provider": "test"}, "coverage": {"provider": "test"}}}
    monkeypatch.setattr(consensus_engine, "query_differences", lambda *args, **kwargs: ("", copy.deepcopy(data)))
    original = ac.execute_source_package
    fetches = []
    def fetch(url, limits):
        fetches.append(url)
        return doc(url, limits)
    monkeypatch.setattr(ac, "execute_source_package", lambda **kwargs: original(**kwargs, fetch=fetch))
    return fetches


def test_enabled_tool_persists_original_evidence_exact_binding_and_all_usage(store, shared_judges):
    script = SourceScript()
    loop = make_loop(store, script, check_sources=True)
    assert "check_contradictions" in loop.registry.tools
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    review = saved["agent_review"]
    verification = review["checks"][0]["source_verification"]
    assert saved["status"] == "completed" and saved["consensus"] == CONSENSUS
    assert verification["status"] == "complete"
    assert verification["findings"][0]["verdict"] == "sources_conflict"
    assert len(verification["findings"][0]["evidence"]) == 2
    assert review_is_bound(review, CONSENSUS)
    changed = copy.deepcopy(review)
    changed["checks"][0]["source_verification"]["basis_hash"] = "other"
    assert not review_is_bound(changed, CONSENSUS)
    assert not review_is_bound(review, CONSENSUS + "Changed.")
    assert len(shared_judges) == 2 and script.source_calls == 1
    quota = agent_quota.quota_ref(store.db, UID, agent_quota.day_key()).get().to_dict()
    assert quota["used"] == saved["agent_usage"]["input_tokens"] + saved["agent_usage"]["output_tokens"] == len(script.calls) * 70
    assert quota["reserved"] == 0
    assert [e["status"] for e in events if e.get("kind") == "tool" and e.get("name") == "check_contradictions"] == ["running", "succeeded"]
    assert any(c.get("source_verification", {}).get("status") == "queued"
               for e in events if e["type"] == "review" for c in e["review"].get("checks", []))


def test_disabled_tool_never_fetches_and_keeps_model_agreement_review(store, shared_judges):
    loop = make_loop(store, SourceScript(), check_sources=False)
    assert "check_contradictions" not in loop.registry.tools
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["agent_review"]["status"] == "succeeded"
    assert "source_verification" not in saved["agent_review"]["checks"][0]
    assert shared_judges == []


def test_missing_enabled_tool_cannot_silently_finalize(store, shared_judges):
    loop = make_loop(store, SourceScript(missing=True), check_sources=True)
    with pytest.raises(AnalysisBudgetExceeded, match="required answer review"):
        list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "failed" and not review_is_bound(saved["agent_review"], CONSENSUS)
    assert any("Call check_contradictions now" in m.get("content", "") for m in loop.messages if m["role"] == "user")
    assert shared_judges == []


def test_invalid_original_evidence_is_not_a_successful_source_check(store, shared_judges):
    loop = make_loop(store, SourceScript(invalid=True), check_sources=True)
    list(loop.run())
    result = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]["checks"][0]["source_verification"]
    assert result["status"] == "partial"
    assert not result["findings"][0]["checked"]
    assert result["findings"][0]["validation_errors"]


def test_no_contradictions_skips_fetch_and_paid_source_judge(store, shared_judges, monkeypatch):
    from app.services.llm import consensus_engine
    monkeypatch.setattr(consensus_engine, "query_differences", lambda *a, **k: ("", {"differences": []}))
    script = SourceScript()
    loop = make_loop(store, script, check_sources=True)
    list(loop.run())
    result = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]["checks"][0]["source_verification"]
    assert result["status"] == "skipped" and result["reason_code"] == "no_checkable_contradictions"
    assert not shared_judges and script.source_calls == 0


def test_source_fallback_is_metered_and_not_a_new_comparison(store, shared_judges):
    script = SourceScript(unavailable=True)
    loop = make_loop(store, script, check_sources=True,
        source_limits=Limits(model="gemini-3.5-flash-lite", fallback_model="gpt-5.4-mini"))
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    result = saved["agent_review"]["checks"][0]["source_verification"]
    assert result["runtime"]["fallback_used"] and result["status"] == "complete"
    assert script.source_calls == 2
    assert saved["agent_usage"]["input_tokens"] + saved["agent_usage"]["output_tokens"] == len(script.calls) * 70


def test_api_freezes_setting_and_recovery_rejects_different_tool_permission(api):
    client, store, calls = api
    chat = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat, "question": "A direct answer", "client_request_id": "sources-on", "bookmark_id": "source_toggle", "check_sources": True}
    response = client.post("/agent", json=payload, headers=AUTH)
    assert response.status_code == 200, response.text
    saved = store.get_turn(UID, chat, store.list_turns(UID, chat)["turns"][0]["id"])
    assert saved["agent_settings"]["check_sources"] is True
    assert saved["agent_settings"]["source_check_limits"]["model"]
    count = len(calls)
    assert client.post("/agent", json={**payload, "recover_only": True}, headers=AUTH).status_code == 200
    assert client.post("/agent", json={**payload, "recover_only": True, "check_sources": False}, headers=AUTH).status_code == 409
    assert len(calls) == count


@pytest.mark.parametrize("revise", [False, True])
def test_source_check_finishes_once_even_when_model_requests_more_rounds(store, shared_judges, revise):
    script = SourceScript(repeat=not revise, revise=revise)
    loop = make_loop(store, script, check_sources=True)
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert script.source_calls == 1
    assert review_is_bound(saved["agent_review"], saved["consensus"])
    assert len(saved["agent_review"]["versions"]) == 1
    assert saved['consensus'] == CONSENSUS
    assert len([step for step, _ in script.calls if step.startswith('completion:')]) == 3


def test_rewrite_during_source_tool_step_never_reaches_stream_or_saved_answer(store, shared_judges):
    script = SourceScript(rewrite_during_check=True)
    loop = make_loop(store, script, check_sources=True)
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert ''.join(e['text'] for e in events if e['type'] == 'delta') == CONSENSUS
    assert saved['consensus'] == CONSENSUS
    assert len(saved['agent_review']['versions']) == 1
    assert review_is_bound(saved['agent_review'], CONSENSUS)
    assert script.source_calls == 1
    first_answer = next(i for i, e in enumerate(events) if e['type'] == 'delta')
    assert not any(e.get('clear_response') for e in events[first_answer + 1:])


def test_cancellation_during_retrieval_keeps_answer_and_terminal_check(store, shared_judges, monkeypatch):
    script = SourceScript()
    loop = make_loop(store, script, check_sources=True)
    execute = ac.execute_source_package
    def cancel(**kwargs):
        loop.cancellation.cancel()
        return execute(**kwargs)
    monkeypatch.setattr(ac, "execute_source_package", cancel)
    with pytest.raises(ProviderCancelled):
        list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "failed" and saved["consensus"] == CONSENSUS
    result = saved["agent_review"]["checks"][0]["source_verification"]
    assert result["status"] == "failed" and result["reason_code"] == "cancelled"
    assert all(f["state"] != "pending" for f in result["findings"])
    assert script.source_calls == 0
