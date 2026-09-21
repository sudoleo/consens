"""Agent chat boundaries: ordered evidence, interrupted history and final review."""
import json

import pytest

from app.services.agent_comparison import review_is_bound
from app.services.agent_policy import AgentPolicy
from app.services.llm.agent_client import measured_usage
from app.services.llm.provider_runtime import AnalysisBudget, AnalysisBudgetExceeded
from test_agent_answer_lifecycle import answer_factory, ANSWER
from test_agent_comparison import Script, make_loop
from test_agent_runs import UID, pending, store


def chat_loop(store, script, **kwargs):
    loop = make_loop(store, script, **kwargs)
    loop.policy = AgentPolicy.for_chat(loop.config)
    loop.costs.policy = loop.policy
    loop.budget = AnalysisBudget(unlimited=True)
    return loop


def tool(name, args, identity):
    return {"id": identity, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


@pytest.mark.parametrize("before", [0, 1])
def test_comparisons_in_a_batch_finish_before_its_judge_and_synthesis(store, before):
    script = Script()
    base = type(script.factory())

    class Batched(base):
        def stream(self, *, model, **kwargs):
            if self.step_id == f"completion:{before}":
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20}, model)
                self.text = "INTERNAL_PREVIEW_DO_NOT_PUBLISH"
                yield {"type": "delta", "text": self.text}
                self.tool_calls = [tool("compare_models", {"question": "Additional constraint", "context": "Budget is 100", "reason": "Complete evidence"}, "additional"),
                                   tool("judge_answer", {}, "review")]
                self.finish_reason = "tool_calls"
                return
            if self.step_id.startswith("completion:") and not kwargs["tools"]:
                assert len(script.loop.comparison.comparisons) == before + 1
                assert all(c["status"] == "succeeded" for c in script.loop.comparison.comparisons)
            yield from super().stream(model=model, **kwargs)

    loop = chat_loop(store, script)
    loop.factory = Batched
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed"
    assert len(saved["agent_review"]["comparisons"]) == before + 1
    assert review_is_bound(saved["agent_review"], saved["consensus"])
    assert "".join(e["text"] for e in events if e["type"] == "delta") == saved["consensus"]


@pytest.mark.parametrize("question,answer", [("Hi", "Hallo!"), ("Danke!", "Gern!"),
    ("Kannst du das bearbeiten?", "Welchen Text soll ich bearbeiten?")])
def test_direct_reply_is_published_once_after_complete_non_tool_response(store, question, answer):
    script = Script()
    base = type(script.factory())
    finished = []

    class Direct(base):
        def stream(self, *, model, **kwargs):
            self.usage = measured_usage({"prompt_tokens": 20, "completion_tokens": 10}, model)
            self.text = answer
            yield {"type": "delta", "text": answer}
            finished.append(True)
            self.finish_reason = "stop"

    loop = chat_loop(store, script)
    loop.messages[-1]["content"] = question
    loop.factory = Direct
    text = []
    for event in loop.run():
        if event["type"] == "delta":
            assert finished
            text.append(event["text"])
    assert text == [answer] and not loop.comparison.comparisons


def test_interrupted_visible_answer_is_in_next_turn_context_without_private_failure(store):
    script = Script()
    loop = chat_loop(store, script)
    loop.factory = answer_factory(script, ending="length")
    with pytest.raises(AnalysisBudgetExceeded):
        list(loop.run())
    _, followup = pending(store, chat_id=loop.chat_id, request_id="next", question="Explain point 2.")
    messages = store.messages(UID, loop.chat_id, followup)
    assert messages[1]["role"] == "user" and messages[1]["content"] == "Question one"
    assert messages[2]["role"] == "assistant" and ANSWER in messages[2]["content"]
    assert "incomplete or unreviewed" in messages[2]["content"]
    assert messages[-1]["content"] == "Explain point 2."


def test_failed_turn_without_an_answer_keeps_the_users_request(store):
    chat, first = pending(store, question="Keep the price below 100.")
    store.release_unclaimed(UID, chat, first["id"])
    _, following = pending(store, chat_id=chat, request_id="retry", question="Please try again.")
    messages = store.messages(UID, chat, following)
    assert messages[1]["content"] == "Keep the price below 100."
    assert "No assistant answer was saved" in messages[2]["content"]


@pytest.mark.parametrize("text", ["Error 429 indicates a rate limit.", "A" * 6000, "A" * 6001], ids=["error-word", "6000-chars", "6001-chars"])
def test_valid_comparison_text_is_retained_with_consistent_session_status(store, text):
    script = Script()
    base = type(script.factory())

    class Answer(base):
        def stream(self, *, model, **kwargs):
            if self.step_id.startswith("agent:") and not model.request_config.get("response_format"):
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 1800}, model)
                self.text, self.finish_reason = text, "stop"
                yield {"type": "delta", "text": text}
                return
            yield from super().stream(model=model, **kwargs)

    loop = chat_loop(store, script)
    loop.factory = Answer
    list(loop.run())
    comparison = loop.comparison.comparisons[0]
    assert len(comparison["answers"]) == 2 and not comparison["failed_models"]
    assert all(a["text"] == text for a in comparison["answers"])
    agents = store.delegation_view(UID, loop.chat_id, loop.turn_id)["agents"]
    assert all(a["status"] == "completed" for a in agents if a.get("kind") == "comparison")


def test_missing_judge_call_starts_existing_judges_without_more_orchestrator_requests(store):
    script = Script(missing=True)
    loop = chat_loop(store, script)
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and review_is_bound(saved["agent_review"], saved["consensus"])
    assert len([s for s, _ in script.calls if s.startswith("completion:")]) == 3
    assert loop.comparison.judge_calls == 2


def test_repeated_invalid_tools_stop_without_exhausting_daily_allowance(store):
    script = Script()
    base = type(script.factory())
    calls = []

    class Invalid(base):
        def stream(self, *, model, **kwargs):
            calls.append(self.step_id)
            self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20}, model)
            self.tool_calls = [tool("compare_models", {"invalid": True}, f"bad_{len(calls)}")]
            self.finish_reason = "tool_calls"
            yield from ()

    loop = chat_loop(store, script)
    loop.factory = Invalid
    with pytest.raises(AnalysisBudgetExceeded, match="without progress"):
        list(loop.run())
    assert len(calls) == 3
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["status"] == "failed"


@pytest.mark.parametrize("mode", ["accepted", "rework", "fallback"])
def test_late_worker_results_reach_synthesis_after_review_without_stale_or_private_data(store, mode):
    from test_agent_delegation import assignment
    script = Script()
    base = type(script.factory())
    captured = []
    action_number = []
    did_rework = []

    class Delegated(base):
        def stream(self, *, model, messages, tools, **kwargs):
            if self.step_id.startswith("agent:") and messages[0]["content"].startswith("You are a research worker"):
                script.calls.append((self.step_id, model.model))
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20}, model)
                if mode == "fallback":
                    raise RuntimeError("Worker unavailable")
                self._reasoning_text = "PRIVATE_WORKER_THOUGHTS"
                self.text = "OUTDATED_FINDING" if mode == "rework" and self.step_id.endswith(":0") else "VERIFIED_CURRENT_FINDING"
                self.sources = [{"url": "https://example.org/worker", "title": "Worker evidence"}]
                self.finish_reason = "stop"
                yield {"type": "delta", "text": self.text}
                return
            if self.step_id.startswith("completion:"):
                if not tools:
                    captured.append(json.dumps(messages))
                elif script.loop.comparison.comparisons:
                    assert not captured, "No new routing generation after the complete answer and checks"
                    script.calls.append((self.step_id, model.model))
                    self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20}, model)
                    workers = list(script.loop.workers.values())
                    action_number.append(True)
                    identity = str(len(action_number))
                    if not workers:
                        self.tool_calls = [tool("start_agent", assignment("Supporting constraint"), identity)]
                    else:
                        worker = workers[0]
                        if worker.state in {"review", "failed"} and not worker.reviewed:
                            self.tool_calls = [tool("review_agent", {"agent_id": worker.id, "accepted": mode != "fallback",
                                "use_fallback": mode == "fallback", "check": "VERIFIED_FALLBACK_FINDING" if mode == "fallback" else "Checked the supporting fact."}, identity)]
                            if mode == "rework" and not did_rework:
                                did_rework.append(True)
                                self.tool_calls.append(tool("send_agent", {"agent_id": worker.id, "kind": "rework", "text": "Update the stale finding."}, identity + "_rework"))
                            else:
                                self.tool_calls.append(tool("judge_answer", {}, identity + "_judge"))
                        else:
                            self.tool_calls = [tool("wait_agents", {"seconds": 1}, identity)]
                    self.finish_reason = "tool_calls"
                    return
            yield from super().stream(model=model, messages=messages, tools=tools, **kwargs)

    loop = chat_loop(store, script, delegation=True)
    loop.factory = Delegated
    list(loop.run())
    assert len(captured) == 1
    assert ("VERIFIED_FALLBACK_FINDING" if mode == "fallback" else "VERIFIED_CURRENT_FINDING") in captured[0]
    assert "OUTDATED_FINDING" not in captured[0] and "PRIVATE_WORKER_THOUGHTS" not in captured[0]
    if mode != "fallback":
        assert "https://example.org/worker" in captured[0]
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and review_is_bound(saved["agent_review"], saved["consensus"])
    assert all(not w.thread.is_alive() for w in loop.workers.values())
