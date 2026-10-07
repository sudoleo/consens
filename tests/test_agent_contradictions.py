"""Agent source checks run as background jobs on the owner's token account.

The turn finalizes with one bound job reference per comparison; the existing
source-check workers settle them later. No fetch or paid source judge runs
inside the turn, and nothing runs twice.
"""
import copy
import json

import pytest

from app.services import agent_contradictions as ac, agent_quota, contradiction_verification as cv
from app.services import source_check_jobs as jobs, source_documents as docs
from app.services.agent_comparison import review_is_bound
from app.services.llm.agent_client import AgentCompletion, measured_usage
from app.services.llm.provider_runtime import ProviderCancelled
from app.services.source_check_repository import SourceCheckRepository
from app.services.source_verification import Limits
from test_agent_comparison import Script, make_loop
from test_agent_runs import UID, AUTH, api, store
from test_contradiction_verification import CONSENSUS, ANSWERS, SOURCES, differences, doc, judge
from test_source_check_repository import FakeDb

JUDGE_USAGE = {"prompt_tokens": 1200, "completion_tokens": 300}


class SourceScript(Script):
    def __init__(self, *, missing=False, repeat=False, revise=False, rewrite_during_check=False):
        super().__init__(missing=missing)
        self.repeat, self.revise = repeat, revise
        self.rewrite_during_check = rewrite_during_check

    def factory(self):
        script = self
        class Completion(AgentCompletion):
            def stream(self, *, model, messages, tools, **kwargs):
                script.calls.append((self.step_id, model.model))
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                if self.step_id.startswith("completion:"):
                    if not tools:
                        self.text, self.finish_reason = CONSENSUS, "stop"
                        yield {"type": "delta", "text": self.text}
                        return
                    index = int(self.step_id.split(":")[-1])
                    if index == 0:
                        action, args = "compare_models", {"question": "Price?", "context": "Compare published prices.", "reason": "Conflicting prices", "next_step": "more_work"}
                    elif index == 1 or (script.revise and index == 4):
                        self.text = CONSENSUS + (" Check the applicable date." if index == 4 else "")
                        yield {"type": "delta", "text": self.text}
                        action, args = "judge_answer", {"finalize": True}
                    else:
                        if script.rewrite_during_check:
                            self.text = 'Here is a completely rewritten answer.'
                            yield {"type": "delta", "text": self.text}
                        if script.missing:
                            self.finish_reason = "stop"
                            return
                        action, args = "check_contradictions", {"finalize": not ((script.repeat or script.revise) and index == 3)}
                    self.tool_calls = [{"id": f"call_{index}", "type": "function", "function": {"name": action, "arguments": json.dumps(args)}}]
                    self.finish_reason = "tool_calls"
                    return
                # The Agent turn itself never asks a source judge.
                assert model.request_config.get("response_format") != {"type": "json_object"}
                provider = "Anthropic" if model.model.startswith("anthropic/") else "OpenAI"
                self.text, self.sources = ANSWERS[provider], SOURCES[provider]
                self.finish_reason = "stop"
                yield {"type": "delta", "text": self.text}
        return Completion()


class Queue:
    """The shared job queue on its own fake Firestore, plus its workers' calls."""

    def __init__(self):
        self.repo = SourceCheckRepository(FakeDb())
        self.fetches, self.judged = [], []

    def jobs(self):
        return [data for path, data in self.repo.db.documents.items()
                if path[0] == self.repo.collection and len(path) == 2]

    def ledger(self):
        return agent_quota.quota_ref(self.repo.db, UID, agent_quota.day_key()).get().to_dict() or {}

    def attach(self, loop):
        # The job's parent reference is the Agent chat.
        self.repo.db.documents[("users", UID, "chats", loop.chat_id)] = {"status": "active"}
        return loop


@pytest.fixture
def queue(monkeypatch):
    queue = Queue()
    monkeypatch.setattr(jobs, "repository", lambda: queue.repo)
    monkeypatch.setattr("app.services.llm.mock_llm.mock_llm_enabled", lambda: False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-server-key")
    def fetch(url, *args):
        queue.fetches.append(url)
        return doc(url, *args)
    def judged(payload, keys, limits):
        queue.judged.append(limits.model)
        raw, _ = judge(payload)
        return raw, dict(JUDGE_USAGE)
    monkeypatch.setattr(docs, "fetch_document", fetch)
    monkeypatch.setattr(cv, "judge_contradictions", judged)
    from app.services.llm import consensus_engine
    data = {**differences(), "judges": {"differences": {"provider": "test"}, "coverage": {"provider": "test"}}}
    monkeypatch.setattr(consensus_engine, "query_differences", lambda *args, **kwargs: ("", copy.deepcopy(data)))
    for state in (jobs._keys, jobs._scans, jobs._active_owners, jobs._heartbeats):
        state.clear()
    yield queue
    jobs._keys.clear()


def run(store, queue, script=None, **kwargs):
    loop = queue.attach(make_loop(store, script or SourceScript(), check_sources=True, **kwargs))
    events = list(loop.run())
    return loop, events, store.get_turn(UID, loop.chat_id, loop.turn_id)


def test_turn_finalizes_with_a_bound_job_and_the_worker_settles_it(store, queue):
    script = SourceScript()
    loop, events, saved = run(store, queue, script)
    assert "check_contradictions" in loop.registry.tools
    review = saved["agent_review"]
    comparison, check = review["comparisons"][0], review["checks"][0]
    verification = check["source_verification"]
    assert saved["status"] == "completed" and saved["consensus"] == CONSENSUS
    # The turn did not wait: nothing was fetched or judged inside it.
    assert verification["status"] == "queued" and verification["job_id"]
    assert queue.fetches == [] and queue.judged == []
    assert (verification["run_id"], verification["basis_hash"], verification["answer_version"]) == (
        comparison["id"], comparison["basis_hash"], review["answer_hash"])
    assert review_is_bound(review, CONSENSUS)
    changed = copy.deepcopy(review)
    changed["checks"][0]["source_verification"]["basis_hash"] = "other"
    assert not review_is_bound(changed, CONSENSUS)
    del changed["checks"][0]["source_verification"]["job_id"]
    changed["checks"][0]["source_verification"]["basis_hash"] = comparison["basis_hash"]
    assert not review_is_bound(changed, CONSENSUS)  # Pending without a job is not an end state.
    assert [e["status"] for e in events if e.get("kind") == "tool" and e.get("name") == "check_contradictions"] == ["running", "succeeded"]
    # The turn's own steps settle on the Agent store as before.
    quota = agent_quota.quota_ref(store.db, UID, agent_quota.day_key()).get().to_dict()
    assert quota["used"] == saved["agent_usage"]["input_tokens"] + saved["agent_usage"]["output_tokens"] == len(script.calls) * 70
    assert quota["reserved"] == 0
    # The job holds its whole bound on the account until it settles.
    bound = jobs.package_token_bound(Limits.configured())
    assert queue.ledger()["reserved"] == bound
    assert jobs.process_one(queue.repo)
    result = queue.repo.page(verification["job_id"], uid=UID)["source_verification"]
    assert result["status"] == "complete" and result["basis_hash"] == comparison["basis_hash"]
    assert result["findings"][0]["verdict"] == "sources_conflict"
    assert len(result["findings"][0]["evidence"]) == 2
    assert len(queue.fetches) == 2 and len(queue.judged) == 1
    ledger = queue.ledger()
    assert ledger["reserved"] == 0 and ledger["used"] == 1500
    assert queue.repo.get(verification["job_id"])["metering"] == {
        "account": "agent", "quota_day": agent_quota.day_key(), "reserved": 0, "charged": 1500, "state": "settled"}


def test_disabled_tool_never_queues_and_keeps_model_agreement_review(store, queue):
    loop = make_loop(store, SourceScript(), check_sources=False)
    assert "check_contradictions" not in loop.registry.tools
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["agent_review"]["status"] == "succeeded"
    assert "source_verification" not in saved["agent_review"]["checks"][0]
    assert queue.jobs() == [] and queue.ledger() == {}


def test_missing_enabled_tool_still_queues_the_check(store, queue):
    loop, _, saved = run(store, queue, SourceScript(missing=True))
    assert saved["status"] == "completed" and review_is_bound(saved["agent_review"], CONSENSUS)
    assert not any("Call check_contradictions now" in m.get("content", "") for m in loop.messages if m["role"] == "user")
    assert saved["agent_review"]["checks"][0]["source_verification"]["status"] == "queued"
    assert len(queue.jobs()) == 1


def test_invalid_original_evidence_is_not_a_successful_source_check(store, queue, monkeypatch):
    def invented(payload, keys, limits):
        raw, _ = judge(payload)
        raw["findings"][0]["evidence"][0]["quote"] = "Invented source evidence."
        return raw, dict(JUDGE_USAGE)
    monkeypatch.setattr(cv, "judge_contradictions", invented)
    _, _, saved = run(store, queue)
    job_id = saved["agent_review"]["checks"][0]["source_verification"]["job_id"]
    assert jobs.process_one(queue.repo)
    result = queue.repo.page(job_id, uid=UID)["source_verification"]
    assert result["status"] == "partial"
    assert not result["findings"][0]["checked"]
    assert result["findings"][0]["validation_errors"]


def test_no_contradictions_skips_without_a_job_or_reservation(store, queue, monkeypatch):
    from app.services.llm import consensus_engine
    monkeypatch.setattr(consensus_engine, "query_differences", lambda *a, **k: ("", {"differences": []}))
    _, _, saved = run(store, queue)
    result = saved["agent_review"]["checks"][0]["source_verification"]
    assert saved["status"] == "completed"
    assert result["status"] == "skipped" and result["reason_code"] == "no_checkable_contradictions"
    assert queue.jobs() == [] and queue.ledger() == {}


def test_job_freezes_the_turns_limits_and_reserves_both_model_attempts(store, queue):
    limits = Limits(model="gemini-3.5-flash-lite", fallback_model="gpt-5.4-mini", output_tokens=2000)
    _, _, saved = run(store, queue, source_limits=limits)
    job_id = saved["agent_review"]["checks"][0]["source_verification"]["job_id"]
    admitted = queue.repo.get_plan(job_id)["limits"]
    assert (admitted["model"], admitted["fallback_model"], admitted["output_tokens"]) == ("gemini-3.5-flash-lite", "gpt-5.4-mini", 2000)
    assert queue.ledger()["reserved"] == limits.input_tokens + 2 * 2000
    assert jobs.process_one(queue.repo)
    assert queue.judged == ["gemini-3.5-flash-lite"]


def test_check_the_account_cannot_cover_is_not_queued_and_the_turn_still_ends(store, queue, monkeypatch):
    bound = jobs.package_token_bound(Limits.configured())
    original = ac.ContradictionChecks.metering
    monkeypatch.setattr(ac.ContradictionChecks, "metering", lambda self: {**original(self), "limit": bound - 1})
    _, _, saved = run(store, queue)
    result = saved["agent_review"]["checks"][0]["source_verification"]
    assert saved["status"] == "completed" and review_is_bound(saved["agent_review"], CONSENSUS)
    assert result["status"] == "failed" and result["reason_code"] == "token_budget_exhausted"
    assert queue.jobs() == [] and queue.ledger() == {}


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
def test_source_check_is_queued_once_even_when_model_requests_more_rounds(store, queue, revise):
    script = SourceScript(repeat=not revise, revise=revise)
    _, _, saved = run(store, queue, script)
    assert len(queue.jobs()) == 1
    assert queue.ledger()["reserved"] == jobs.package_token_bound(Limits.configured())
    assert review_is_bound(saved["agent_review"], saved["consensus"])
    assert len(saved["agent_review"]["versions"]) == 1
    assert saved['consensus'] == CONSENSUS
    # Compare, judge_answer, the answer step; the app then queues the source
    # check itself, so the model gets no further steering step to ask again.
    assert [step for step, _ in script.calls if step.startswith('completion:')] == [
        'completion:0', 'completion:1', 'completion:2']


def test_resubmitting_the_same_comparison_reuses_its_job_and_reservation(store, queue):
    loop, _, saved = run(store, queue)
    stored = saved["agent_review"]["checks"][0]["source_verification"]
    reserved = queue.ledger()["reserved"]
    checks = loop.comparison.contradictions
    assert checks.complete()
    again = checks.submit(loop.comparison.comparisons[0], loop.comparison.review["checks"][0])
    assert again["job_id"] == stored["job_id"]
    assert len(queue.jobs()) == 1 and queue.ledger()["reserved"] == reserved


def test_rewrite_during_source_tool_step_never_reaches_stream_or_saved_answer(store, queue):
    _, events, saved = run(store, queue, SourceScript(rewrite_during_check=True))
    assert ''.join(e['text'] for e in events if e['type'] == 'delta') == CONSENSUS
    assert saved['consensus'] == CONSENSUS
    assert len(saved['agent_review']['versions']) == 1
    assert review_is_bound(saved['agent_review'], CONSENSUS)
    assert len(queue.jobs()) == 1
    first_answer = next(i for i, e in enumerate(events) if e['type'] == 'delta')
    assert not any(e.get('clear_response') for e in events[first_answer + 1:])


def test_stop_before_queuing_keeps_the_answer_and_leaves_no_job(store, queue, monkeypatch):
    original = ac.ContradictionChecks.check
    def stopped(self, args, *, cancellation):
        self.comparison.loop.cancellation.cancel()
        return original(self, args, cancellation=cancellation)
    monkeypatch.setattr(ac.ContradictionChecks, "check", stopped)
    loop = queue.attach(make_loop(store, SourceScript(), check_sources=True))
    with pytest.raises(ProviderCancelled):
        list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "failed" and saved["consensus"] == CONSENSUS
    assert "source_verification" not in saved["agent_review"]["checks"][0]
    assert queue.jobs() == [] and queue.ledger() == {}


def test_deleted_chat_returns_the_jobs_unspent_reservation(store, queue):
    loop, _, saved = run(store, queue)
    job_id = saved["agent_review"]["checks"][0]["source_verification"]["job_id"]
    assert queue.ledger()["reserved"] > 0
    queue.repo.db.documents[("users", UID, "chats", loop.chat_id)] = {"status": "deleting"}
    assert not jobs.process_one(queue.repo)
    assert queue.ledger()["reserved"] == 0 and queue.ledger().get("used", 0) == 0
    assert queue.jobs() == [] and queue.judged == []
    with pytest.raises(Exception):
        queue.repo.get(job_id)


def test_check_gets_the_users_question_and_the_comparison_task_as_its_resolved_form(store, queue, monkeypatch):
    seen = []
    original = jobs.submit_source_check
    def capture(**kwargs):
        seen.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(jobs, "submit_source_check", capture)
    loop, _, _ = run(store, queue)
    user = next(m["content"] for m in reversed(loop.answer_conversation) if m["role"] == "user")
    assert seen and seen[0]["question"] == user and seen[0]["resolved_question"] == "Price?"


def test_late_answers_stay_out_of_the_source_check_like_out_of_the_judges(store, queue, monkeypatch):
    loop, _, _ = run(store, queue)
    seen = []
    monkeypatch.setattr(jobs, "submit_advisory", lambda **kwargs: seen.append(kwargs) or {"status": "queued"})
    comparison = copy.deepcopy(loop.comparison.comparisons[0])
    late = {**comparison["answers"][0], "provider_label": "Late model", "text": "Arrived later.",
            "sources": [{"id": "S9", "url": "https://late.example/doc"}], "late": True}
    comparison["answers"].append(late)
    loop.comparison.contradictions.submit(comparison, loop.comparison.review["checks"][0])
    assert "Late model" not in seen[0]["model_answers"] and "Late model" not in seen[0]["model_sources"]
    assert set(seen[0]["model_answers"]) == {a["provider_label"] for a in comparison["answers"][:-1]}
