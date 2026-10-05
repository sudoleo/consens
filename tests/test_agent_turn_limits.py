"""Soft per-turn guards of account-mode Agent chat (AgentPolicy.for_chat).

The daily token ledger stays the spending limit. A turn that loops on valid
calls still ends: at most four comparisons, a step cap and a deadline (both
answer from a usable comparison when there is one), and no identical calls.
"""
from dataclasses import replace
import json

import pytest

from app.services import agent_delegation
from app.services.agent_comparison import AgentPreferences, comparison_selection, review_is_bound
from app.services.agent_delegation import (DelegationLoop, TURN_REPEAT_LIMIT, TURN_STEP_LIMIT, TURN_TIME_LIMIT,
                                           TURN_WRAP_UP_SECONDS)
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.llm.agent_client import measured_usage, resolve_agent_model
from app.services.llm.provider_runtime import AnalysisBudgetExceeded, ProviderCancellation
from test_agent_chat_integrity import chat_loop
from test_agent_comparison import Script, make_loop
from test_agent_runs import UID, pending, store  # noqa: F401  (fixture)


def tool_result(loop, call_id):
    return json.loads(next(m["content"] for m in loop.messages
                           if m.get("role") == "tool" and m.get("tool_call_id") == call_id))


def routing_steps(script):
    # Comparison answers and judges run as agent:<id> steps; synthesis as a
    # completion step, so count the steps that offered tools via the script.
    return [step for step, _ in script.calls if step.startswith("completion:")]


def saved_turn(store, loop):
    return store.get_turn(UID, loop.chat_id, loop.turn_id)


def test_chat_policy_sets_turn_guards_and_bounded_policy_keeps_its_snapshot():
    chat = AgentPolicy.for_chat(defaults())
    assert (chat.turn_comparisons, chat.turn_steps, chat.turn_seconds, chat.turn_identical_calls) == (4, 24, 900, 2)
    assert chat.snapshot()["turn_steps"] == 24
    bounded = AgentPolicy.from_config({**defaults(), "enabled": True})
    assert bounded.turn_comparisons is bounded.turn_steps is bounded.turn_seconds is None
    assert not any(key.startswith("turn_") for key in bounded.snapshot())


@pytest.mark.parametrize("autonomy", ["guided", "free"])
def test_prompt_states_the_per_message_comparison_limit(store, autonomy):
    chat, turn = pending(store)
    config = {**defaults(), "enabled": False, "max_searches": 0}
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"),
        messages=[{"role": "system", "content": "Answer."}, {"role": "user", "content": "Compare options"}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.for_chat(config),
        delegation_config=config, completion_factory=Script().factory,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}),
        agent_preferences=AgentPreferences(autonomy=autonomy))
    system = loop.messages[0]["content"]
    assert "At most 4 comparisons per message before the single checked answer." in system
    assert "no elapsed-time limit" not in system
    assert ("at most 4 for this message" in system) == (autonomy == "free")
    bounded = make_loop(store, Script(), preferences=AgentPreferences(autonomy=autonomy))
    assert "At most three comparisons" in bounded.messages[0]["content"]
    assert "At most 4 comparisons" not in bounded.messages[0]["content"]


def test_fifth_comparison_is_refused_and_the_answer_uses_the_first_four(store):
    script = Script(compares=6)
    loop = chat_loop(store, script)
    list(loop.run())
    saved = saved_turn(store, loop)
    review = saved["agent_review"]
    assert saved["status"] == "completed" and len(review["comparisons"]) == 4
    assert review_is_bound(review, saved["consensus"])
    assert loop.comparison.judge_calls == 8
    assert "last comparison allowed" in tool_result(loop, "call_3")["instruction"]
    for refused in ("call_4", "call_5"):
        error = tool_result(loop, refused)["error"]
        assert "maximum of 4 comparisons" in error and "judge_answer" in error
    # Nothing paid started for the refused calls: four comparisons of two answers.
    assert len([s for s, _ in script.calls if not s.startswith("completion:")]) == 4 * 2 + 4 * 2


def test_step_cap_answers_from_existing_comparisons(store):
    script = Script(compares=10)
    loop = chat_loop(store, script)
    loop.policy = replace(loop.policy, turn_steps=3, turn_comparisons=10)
    list(loop.run())
    saved = saved_turn(store, loop)
    assert saved["status"] == "completed" and len(saved["agent_review"]["comparisons"]) == 3
    assert review_is_bound(saved["agent_review"], saved["consensus"])
    # Three routing steps, then the synthesis step; no fourth routing step.
    assert len(routing_steps(script)) == 4


def test_step_cap_without_a_usable_comparison_stops_and_keeps_partial_results(store):
    script = Script(compares=10, fail_model=True)
    loop = chat_loop(store, script)
    loop.policy = replace(loop.policy, turn_steps=2, turn_comparisons=10)
    with pytest.raises(AnalysisBudgetExceeded, match="step limit"):
        list(loop.run())
    saved = saved_turn(store, loop)
    assert saved["status"] == "failed"
    assert saved["agent_failure"] == {"code": "run_limit", "error": TURN_STEP_LIMIT}
    comparisons = saved["agent_review"]["comparisons"]
    assert len(comparisons) == 2 and all(len(c["answers"]) == 1 for c in comparisons)
    assert len(routing_steps(script)) == 2  # No synthesis from single answers.


@pytest.mark.parametrize("fail_model", [False, True])
def test_deadline_wraps_up_or_stops_without_sleeping(store, fail_model):
    script = Script(compares=10, fail_model=fail_model)
    loop = chat_loop(store, script)
    # Time jumps past the soft deadline once the first comparison exists,
    # still inside the wrap-up grace before the hard stop.
    loop.clock = lambda: loop.turn_started + (loop.policy.turn_seconds + 1 if loop.comparison.comparisons else 0)
    if fail_model:
        with pytest.raises(AnalysisBudgetExceeded, match="time limit"):
            list(loop.run())
        saved = saved_turn(store, loop)
        assert saved["status"] == "failed" and saved["agent_failure"]["error"] == TURN_TIME_LIMIT
        assert len(saved["agent_review"]["comparisons"]) == 1
        return
    list(loop.run())
    saved = saved_turn(store, loop)
    assert saved["status"] == "completed" and len(saved["agent_review"]["comparisons"]) == 1
    assert review_is_bound(saved["agent_review"], saved["consensus"])


def test_hard_deadline_stops_inside_a_step_only_in_account_mode(store):
    loop = chat_loop(store, Script())
    now = [loop.turn_started + loop.policy.turn_seconds + TURN_WRAP_UP_SECONDS - 1]
    loop.clock = lambda: now[0]
    loop._check()
    now[0] += 1
    with pytest.raises(AnalysisBudgetExceeded, match="time limit"):
        loop._check()
    bounded = make_loop(store, Script())
    bounded.clock = lambda: now[0] + 10_000
    bounded._check()
    assert bounded._turn_limit() is None


@pytest.mark.parametrize("fail_model", [False, True])
def test_identical_calls_are_refused_then_end_the_turn(store, fail_model):
    script = Script(fail_model=fail_model)
    base = type(script.factory())

    class Looping(base):
        def stream(self, *, model, messages, **kwargs):
            if not self.step_id.startswith("completion:") or not kwargs["tools"]:
                yield from super().stream(model=model, messages=messages, **kwargs)
                return
            index = int(self.step_id.split(":")[-1])
            script.calls.append((self.step_id, model.model))
            self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20}, model)
            # Only the free-text progress line changes; the request is the same.
            args = {"question": "Evaluate option 1", "context": "Budget is 100.", "reason": "Compare",
                    "next_step": "more_work", "status_update": f"Checking again ({index})"}
            self.tool_calls = [{"id": f"same_{index}", "type": "function",
                                "function": {"name": "compare_models", "arguments": json.dumps(args)}}]
            self.finish_reason = "tool_calls"
            yield from ()

    loop = chat_loop(store, script)
    loop.factory = Looping
    if fail_model:
        with pytest.raises(AnalysisBudgetExceeded, match="same tool request"):
            list(loop.run())
        saved = saved_turn(store, loop)
        assert saved["status"] == "failed" and saved["agent_failure"]["error"] == TURN_REPEAT_LIMIT
    else:
        list(loop.run())
        saved = saved_turn(store, loop)
        assert saved["status"] == "completed"
        assert review_is_bound(saved["agent_review"], saved["consensus"])
    # Two runs, one refusal, then the fourth identical request ends the turn.
    assert len(saved["agent_review"]["comparisons"]) == 2
    error = tool_result(loop, "same_2")["error"]
    assert "identical compare_models call already ran 2 times" in error
    assert not any(m.get("tool_call_id") == "same_3" for m in loop.messages)
    assert len([s for s, _ in script.calls if s.startswith("completion:")]) == 4 + (0 if fail_model else 1)


def test_repeated_polling_is_not_counted_as_identical_calls(store):
    loop = chat_loop(store, Script())
    call = {"id": "w", "type": "function", "function": {"name": "wait_agents", "arguments": '{"seconds":0}'}}
    assert all(loop._identical_call(call) is None for _ in range(10))
    other = {"id": "c", "type": "function", "function": {"name": "read_file", "arguments": '{"b":1,"a":2}'}}
    reordered = {"id": "d", "type": "function", "function": {"name": "read_file", "arguments": '{"a":2,"b":1}'}}
    assert [loop._identical_call(c) for c in (other, reordered, other, reordered)] == [None, None, "refuse", "stop"]
    assert agent_delegation.REPEATABLE_TOOLS == {"wait_agents"}
