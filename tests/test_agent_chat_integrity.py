"""Agent chat boundaries: ordered evidence, interrupted history and final review."""
import json

import pytest

from app.services.agent_comparison import answer_hash
from app.services.agent_policy import AgentPolicy
from app.services.llm.agent_client import measured_usage
from app.services.llm.provider_runtime import AnalysisBudget, AnalysisBudgetExceeded
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
def test_comparisons_in_a_batch_finish_before_the_answer_and_its_review(store, before):
    script = Script()
    base = type(script.factory())

    class Batched(base):
        def stream(self, *, model, **kwargs):
            if self.step_id == f"completion:{before}":
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20}, model)
                self.text = "INTERNAL_PREVIEW_DO_NOT_PUBLISH"
                yield {"type": "delta", "text": self.text}
                self.tool_calls = [tool("compare_models", {"question": "Additional constraint", "context": "Budget is 100"}, "additional"),
                                   tool("audit_answer", {}, "review")]
                self.finish_reason = "tool_calls"
                return
            if self.step_id == f"completion:{before + 1}":
                # The step after the batch writes the answer.
                answer_steps.append(self.step_id)
                assert len(script.loop.comparison.comparisons) == before + 1
                assert all(c["status"] == "succeeded" for c in script.loop.comparison.comparisons)
            yield from super().stream(model=model, **kwargs)

    answer_steps = []
    loop = chat_loop(store, script)
    loop.factory = Batched
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and answer_steps == [f"completion:{before + 1}"]
    # The review is the app's: the model's own audit_answer call is refused.
    review_call = next(json.loads(m["content"]) for m in loop.messages if m.get("tool_call_id") == "review")
    assert "error" in review_call
    assert len(saved["agent_review"]["comparisons"]) == before + 1
    assert saved["agent_review"]["answer_hash"] == answer_hash(saved["consensus"])
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
    base = type(script.factory())
    # Long enough to stream while it is written (ANSWER_HOLD_CHARS).
    answer = "The first option costs 100 euros a month and includes the support plan. " * 6

    class Cut(base):
        def stream(self, *, model, **kwargs):
            if self.step_id == "completion:1":
                # The step after the comparison writes the answer and stops at its output limit.
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20}, model)
                for start in range(0, len(answer), 100):
                    self.text += answer[start:start + 100]
                    yield {"type": "delta", "text": answer[start:start + 100]}
                self.finish_reason = "length"
                return
            yield from super().stream(model=model, **kwargs)

    loop = chat_loop(store, script)
    loop.factory = Cut
    events = []
    with pytest.raises(AnalysisBudgetExceeded, match="output token limit"):
        for event in loop.run():
            events.append(event)
    assert "".join(e["text"] for e in events if e["type"] == "delta") == answer
    _, followup = pending(store, chat_id=loop.chat_id, request_id="next", question="Explain point 2.")
    messages = store.messages(UID, loop.chat_id, followup)
    assert messages[1]["role"] == "user" and messages[1]["content"] == "Question one"
    assert messages[2]["role"] == "assistant" and answer in messages[2]["content"]
    assert "output token limit" not in messages[2]["content"]
    assert "incomplete or unreviewed" in messages[2]["content"]
    assert messages[-1]["content"].endswith("\n\nExplain point 2.")


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


def test_the_app_starts_the_review_without_more_agent_requests(store):
    """The written answer ends the steering; the app has it reviewed itself."""
    script = Script()
    loop = chat_loop(store, script, reviewers=True)
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    review = saved["agent_review"]
    assert saved["status"] == "completed" and review["status"] == "succeeded"
    assert review["answer_hash"] == answer_hash(saved["consensus"])
    # The comparison step and the step that writes the answer.
    assert len([s for s, _ in script.calls if s.startswith("completion:")]) == 2
    # Each reviewer gave its final round on the fixed answer.
    assert {model for _, model in script.reviews} == {"anthropic/claude-haiku-4.5", "openai/gpt-5.4-mini"}


def test_repeated_invalid_tools_end_with_the_answer_without_exhausting_daily_allowance(store):
    """Three rounds of invalid tool calls end the agent's work: one last step
    without tools writes the answer from what it has (since 2026-10-31 in
    every turn; until then a turn without a comparison failed here)."""
    from app.services import agent_quota
    script = Script()
    base = type(script.factory())
    calls = []

    class Invalid(base):
        def stream(self, *, model, **kwargs):
            calls.append(self.step_id)
            self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20}, model)
            if kwargs.get("allow_tool_calls") is False:
                self.text, self.finish_reason = "What I have so far.", "stop"
                yield {"type": "delta", "text": self.text}
                return
            self.tool_calls = [tool("compare_models", {"invalid": True}, f"bad_{len(calls)}")]
            self.finish_reason = "tool_calls"
            yield from ()

    loop = chat_loop(store, script)
    loop.factory = Invalid
    list(loop.run())
    assert len(calls) == 4
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["consensus"] == "What I have so far."
    assert loop.completion.wrap_up["reason"] == "invalid" and not loop.comparison.comparisons
    assert agent_quota.snapshot(store.db, UID)["reserved"] == 0


@pytest.mark.parametrize("mode", ["accepted", "rework", "fallback"])
def test_late_worker_results_reach_the_answer_only_after_review_without_private_data(store, mode):
    """The agent writes the answer itself once every worker result is
    reviewed; worker reasoning never reaches it, and a result sent back for
    rework stands before the rework request, superseded by the new one."""
    from test_agent_delegation import assignment
    script = Script()
    base = type(script.factory())
    captured = []
    answer_steps = []
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
            if self.step_id.startswith("completion:") and script.loop.comparison.comparisons:
                assert not answer_steps, "No routing generation after the answer"
                script.calls.append((self.step_id, model.model))
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20}, model)
                workers = list(script.loop.workers.values())
                action_number.append(True)
                identity = str(len(action_number))
                if not workers:
                    self.tool_calls = [tool("start_agent", assignment("Supporting constraint"), identity)]
                else:
                    worker = workers[0]
                    if worker.reviewed and not worker.inbox:
                        # Every result is reviewed: this step writes the answer.
                        captured.append(json.dumps(messages))
                        answer_steps.append(self.step_id)
                        self.text, self.finish_reason = "The first option costs 100.", "stop"
                        yield {"type": "delta", "text": self.text}
                        return
                    # Like a model, review only a result that reached the
                    # conversation: the worker's state flips before its result
                    # is delivered (wait_agents), and a review sent in between
                    # put the rework request ahead of the result it reworks.
                    latest = (None if mode == "fallback" else
                              "OUTDATED_FINDING" if mode == "rework" and not did_rework else "VERIFIED_CURRENT_FINDING")
                    if (worker.state in {"review", "failed"} and not worker.reviewed
                            and (latest is None or latest in json.dumps(messages))):
                        self.tool_calls = [tool("review_agent", {"agent_id": worker.id, "accepted": mode != "fallback",
                            "use_fallback": mode == "fallback", "check": "VERIFIED_FALLBACK_FINDING" if mode == "fallback" else "Checked the supporting fact."}, identity)]
                        if mode == "rework" and not did_rework:
                            did_rework.append(True)
                            self.tool_calls.append(tool("send_agent", {"agent_id": worker.id, "kind": "rework", "text": "Update the stale finding."}, identity + "_rework"))
                    else:
                        self.tool_calls = [tool("wait_agents", {"seconds": 1}, identity)]
                self.finish_reason = "tool_calls"
                return
            yield from super().stream(model=model, messages=messages, tools=tools, **kwargs)

    loop = chat_loop(store, script, delegation=True)
    loop.factory = Delegated
    list(loop.run())
    assert len(captured) == 1
    # The answer is the last orchestrator step.
    assert [s for s, _ in script.calls if s.startswith("completion:")][-1] == answer_steps[0]
    context = captured[0]
    assert ("VERIFIED_FALLBACK_FINDING" if mode == "fallback" else "VERIFIED_CURRENT_FINDING") in context
    assert "PRIVATE_WORKER_THOUGHTS" not in context
    if mode == "rework":
        # The agent keeps its own history: the stale result stays in its context,
        # before its rework request and the current result.
        assert (context.index("OUTDATED_FINDING") < context.index("Update the stale finding.")
                < context.rindex("VERIFIED_CURRENT_FINDING"))
    else:
        assert "OUTDATED_FINDING" not in context
    if mode != "fallback":
        assert "https://example.org/worker" in context
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["consensus"] == "The first option costs 100."
    assert saved["agent_review"]["answer_hash"] == answer_hash(saved["consensus"])
    assert all(not w.thread.is_alive() for w in loop.workers.values())
