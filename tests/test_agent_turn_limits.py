"""Soft per-turn guards of account-mode Agent chat (AgentPolicy.for_chat).

The daily token ledger stays the spending limit. A turn that loops on valid
calls still ends: at most four comparisons, a step cap and a deadline, and no
identical calls. A limit with a usable comparison ends in one last step whose
tools are listed but not callable: the agent writes the answer from the
comparisons it has (_merged_wrap_up). Without one the turn stops.
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
    # Comparison answers and judges run as agent:<id> steps; every step of the
    # agent, also the one that writes the answer, is a completion step.
    return [step for step, _ in script.calls if step.startswith("completion:")]


def steering(kwargs):
    """A step whose tools the agent may call (not the wrap-up's last step)."""
    return bool(kwargs["tools"]) and kwargs.get("allow_tool_calls") is not False


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
    assert "At most 4 comparisons per message." in system
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
        assert "maximum of 4 comparisons" in error and "write the answer now" in error
    # Nothing paid started for the refused calls: four comparisons of two answers.
    assert len([s for s, _ in script.calls if not s.startswith("completion:")]) == 4 * 2 + 4 * 2


def test_step_cap_answers_from_existing_comparisons(store):
    script = Script(compares=10)
    base = type(script.factory())
    requests = []

    class Recorded(base):
        def stream(self, **kwargs):
            if self.step_id.startswith("completion:"):
                # A copy: the loop appends to its live conversation afterwards.
                requests.append({**kwargs, "messages": json.loads(json.dumps(kwargs["messages"]))})
            yield from super().stream(**kwargs)

    loop = chat_loop(store, script)
    loop.factory = Recorded
    loop.policy = replace(loop.policy, turn_steps=3, turn_comparisons=10)
    list(loop.run())
    saved = saved_turn(store, loop)
    assert saved["status"] == "completed" and len(saved["agent_review"]["comparisons"]) == 3
    assert review_is_bound(saved["agent_review"], saved["consensus"])
    # Three steering steps, then one step writes the answer; no fourth steering step.
    assert len(routing_steps(script)) == 4
    assert [steering(kwargs) for kwargs in requests] == [True, True, True, False]
    # The last step keeps the tools listed (prompt cache) but cannot call them.
    assert requests[-1]["tools"] and requests[-1]["native_searches"] == 0
    assert requests[-1]["messages"][-1]["content"].startswith("App rule: this message has reached its limit.")


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
    assert len(routing_steps(script)) == 2  # No answer step from single answers.


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
    # A small start keeps the arithmetic exact; on Linux the large monotonic
    # clock loses the last bits and "exactly on the limit" lands just before it.
    loop.turn_started = 0.0
    now = [loop.policy.turn_seconds + TURN_WRAP_UP_SECONDS - 1]
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
            if not self.step_id.startswith("completion:") or not steering(kwargs):
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
    if fail_model:
        assert not any(m.get("tool_call_id") == "same_3" for m in loop.messages)
    else:
        # Never run; closed with a result before the last step writes the
        # answer (providers reject a tool call without one).
        assert tool_result(loop, "same_3") == {"error": "Not run: this message reached its limit."}
    assert len([s for s, _ in script.calls if s.startswith("completion:")]) == 4 + (0 if fail_model else 1)


def planned(script, plan):
    """Steering step n sends the tool calls plan[n] (the last entry repeats);
    an entry None writes the answer as plain text (Script)."""
    base = type(script.factory())

    class Planned(base):
        def stream(self, *, model, messages, **kwargs):
            index = int(self.step_id.split(":")[-1]) if self.step_id.startswith("completion:") else None
            if index is None or not steering(kwargs) or plan[min(index, len(plan) - 1)] is None:
                yield from super().stream(model=model, messages=messages, **kwargs)
                return
            script.calls.append((self.step_id, model.model))
            self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20}, model)
            self.tool_calls = [{"id": f"s{index}_{n}", "type": "function",
                                "function": {"name": name, "arguments": json.dumps(args)}}
                               for n, (name, args) in enumerate(plan[min(index, len(plan) - 1)])]
            self.finish_reason = "tool_calls"
            yield from ()
    return Planned


def test_an_answer_after_rejected_calls_is_no_repeat_and_completes_the_turn(store):
    """The answer is the agent's plain text, never a tool call: rejected
    calls before it neither count against it nor keep the turn from ending."""
    invalid = ("compare_models", {"question": "Who won?", "depth": "deep"})
    script = Script()
    loop = chat_loop(store, script)
    loop.factory = planned(script, [[invalid], [invalid], None])
    events = list(loop.run())
    assert "error" in tool_result(loop, "s0_0") and "error" in tool_result(loop, "s1_0")
    saved = saved_turn(store, loop)
    assert saved["status"] == "completed" and loop.comparison.direct
    assert saved["assistant_response"] == "The first option costs 100."
    assert "".join(e["text"] for e in events if e["type"] == "delta") == "The first option costs 100."


@pytest.mark.parametrize("fail_model", [False, True])
def test_three_invalid_rounds_answer_from_a_usable_comparison(store, fail_model):
    """Review 2026-10-12: three rejected calls (a malformed field) ended a
    turn whose comparisons were paid, without an answer."""
    script = Script(fail_model=fail_model)
    requests = []
    compare = ("compare_models", {"question": "Evaluate option 1", "context": "Budget is 100."})
    # Different each round (no identical call), each refused by the schema.
    malformed = [("compare_models", {"question": "Evaluate option 1", "context": "Budget is 100.", "bogus": n})
                 for n in range(1, 4)]
    loop = chat_loop(store, script)
    planned_type = planned(script, [[compare], *([call] for call in malformed)])

    class Recorded(planned_type):
        def stream(self, **kwargs):
            if self.step_id.startswith("completion:"):
                requests.append(kwargs)
            yield from super().stream(**kwargs)

    loop.factory = Recorded
    if fail_model:
        with pytest.raises(AnalysisBudgetExceeded, match="invalid tool requests"):
            list(loop.run())
        assert saved_turn(store, loop)["status"] == "failed"
        # Single answers: no step writes an unchecked answer.
        assert len(requests) == 4
        return
    list(loop.run())
    saved = saved_turn(store, loop)
    assert all("error" in tool_result(loop, f"s{n}_0") for n in (1, 2, 3))
    assert saved["status"] == "completed" and review_is_bound(saved["agent_review"], saved["consensus"])
    # The answer comes from one last step without callable tools.
    assert len(requests) == 5 and not steering(requests[-1])
    assert len(saved["agent_review"]["comparisons"]) == 1


def test_repeated_polling_is_not_counted_as_identical_calls(store):
    loop = chat_loop(store, Script())
    call = {"id": "w", "type": "function", "function": {"name": "wait_agents", "arguments": '{"seconds":0}'}}
    assert all(loop._identical_call(call) is None for _ in range(10))
    other = {"id": "c", "type": "function", "function": {"name": "read_file", "arguments": '{"b":1,"a":2}'}}
    reordered = {"id": "d", "type": "function", "function": {"name": "read_file", "arguments": '{"a":2,"b":1}'}}
    assert [loop._identical_call(c) for c in (other, reordered, other, reordered)] == [None, None, "refuse", "stop"]
    assert agent_delegation.REPEATABLE_TOOLS == {"wait_agents"}


def test_each_check_runs_two_differences_passes_in_production(store, monkeypatch):
    from app.services import agent_comparison
    monkeypatch.setattr(agent_comparison, "DIFFERENCES_PASSES", 2)
    script = Script(compares=6)
    loop = chat_loop(store, script)
    list(loop.run())
    saved = saved_turn(store, loop)
    assert saved["status"] == "completed" and len(saved["agent_review"]["comparisons"]) == 4
    # Per check: two differences passes and one coverage judge.
    assert loop.comparison.judge_calls == 12
