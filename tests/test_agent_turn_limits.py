"""Soft per-turn guards of account-mode Agent chat (AgentPolicy.for_chat).

The daily ledger stays the spending limit. A turn that loops on valid
calls still ends: at most four comparisons, a step cap and a deadline, and no
identical calls. A limit ends in one last step whose tools are listed but
not callable: the agent writes the answer from what it has (_merged_wrap_up),
its own work carries it.
"""
from dataclasses import replace
import json

import pytest

from app.services import agent_delegation
from app.services.agent_comparison import answer_hash, comparison_selection
from app.services.agent_delegation import DelegationLoop, TURN_WRAP_UP_SECONDS
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.llm.agent_client import measured_usage, resolve_agent_model
from app.services.llm.provider_runtime import AnalysisBudget, AnalysisBudgetExceeded, ProviderCancellation
from test_agent_comparison import Script, make_loop
from test_agent_runs import UID, pending, store  # noqa: F401  (fixture)


def chat_loop(store, script, **kwargs):
    """make_loop with the chat's policy (AgentPolicy.for_chat): its turn
    guards and no run budget."""
    loop = make_loop(store, script, **kwargs)
    loop.policy = AgentPolicy.for_chat(loop.config)
    loop.costs.policy = loop.policy
    loop.budget = AnalysisBudget(unlimited=True)
    return loop


def reviewed(review, text):
    """The saved review is the reviewers' review of exactly ``text``."""
    return review.get("mode") == "audit" and review.get("answer_hash") == answer_hash(text)


def tool_result(loop, call_id):
    return json.loads(next(m["content"] for m in loop.messages
                           if m.get("role") == "tool" and m.get("tool_call_id") == call_id))


def routing_steps(script):
    # Comparison answers run as agent:<id> steps; every step of the agent,
    # also the one that writes the answer, is a completion step.
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


def test_compare_models_states_the_per_message_comparison_limit(store):
    """The limit stands in the tool's description (AUDIT_COMPARE), not in
    the prompt; a bounded run has none."""
    chat, turn = pending(store)
    config = {**defaults(), "enabled": False, "max_searches": 0}
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"),
        messages=[{"role": "system", "content": "Answer."}, {"role": "user", "content": "Compare options"}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.for_chat(config),
        delegation_config=config, completion_factory=Script().factory,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-6-luna"}))
    assert loop.registry.tools["compare_models"].description.endswith(" At most 4 times per message.")
    assert "comparisons per message" not in loop.messages[0]["content"]
    bounded = make_loop(store, Script())
    assert "At most" not in bounded.registry.tools["compare_models"].description


def test_fifth_comparison_is_refused_and_the_answer_uses_the_first_four(store):
    script = Script(compares=6)
    loop = chat_loop(store, script)
    list(loop.run())
    saved = saved_turn(store, loop)
    review = saved["agent_review"]
    assert saved["status"] == "completed" and len(review["comparisons"]) == 4
    assert reviewed(review, saved["consensus"])
    assert "last comparison allowed" in tool_result(loop, "call_3")["instruction"]
    for refused in ("call_4", "call_5"):
        error = tool_result(loop, refused)["error"]
        assert "maximum of 4 comparisons" in error and "go on from the comparisons you already have" in error
    # Nothing paid started for the refused calls: four comparisons of two answers.
    assert len([s for s, _ in script.calls if not s.startswith("completion:")]) == 4 * 2


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
    assert reviewed(saved["agent_review"], saved["consensus"])
    # Three steering steps, then one step writes the answer; no fourth steering step.
    assert len(routing_steps(script)) == 4
    assert [steering(kwargs) for kwargs in requests] == [True, True, True, False]
    # The last step keeps the tools listed (prompt cache) but cannot call them.
    assert requests[-1]["tools"] and requests[-1]["native_searches"] == 0
    assert requests[-1]["messages"][-1]["content"].startswith("App rule: this message has reached its limit.")


def test_step_cap_with_single_answers_still_ends_in_an_answer(store):
    """One answer per comparison is advice like two: the agent's own work
    carries the answer."""
    script = Script(compares=10, fail_model=True)
    loop = chat_loop(store, script)
    loop.policy = replace(loop.policy, turn_steps=2, turn_comparisons=10)
    list(loop.run())
    saved = saved_turn(store, loop)
    assert saved["status"] == "completed" and loop.completion.wrap_up["reason"] == "steps"
    assert reviewed(saved["agent_review"], saved["consensus"])
    comparisons = saved["agent_review"]["comparisons"]
    assert len(comparisons) == 2 and all(len(c["answers"]) == 1 and c["status"] == "partial" for c in comparisons)
    # Two steering steps, then the step that writes the answer.
    assert len(routing_steps(script)) == 3


@pytest.mark.parametrize("fail_model", [False, True])
def test_deadline_wraps_up_without_sleeping(store, fail_model):
    script = Script(compares=10, fail_model=fail_model)
    loop = chat_loop(store, script)
    # Time jumps past the soft deadline once the first comparison exists,
    # still inside the wrap-up grace before the hard stop.
    loop.clock = lambda: loop.turn_started + (loop.policy.turn_seconds + 1 if loop.comparison.comparisons else 0)
    list(loop.run())
    saved = saved_turn(store, loop)
    assert saved["status"] == "completed" and len(saved["agent_review"]["comparisons"]) == 1
    assert loop.completion.wrap_up["reason"] == "time"
    assert reviewed(saved["agent_review"], saved["consensus"])


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
    """With two answers or one per comparison alike, the turn ends in its
    answer."""
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
            args = {"question": "Evaluate option 1", "context": "Budget is 100."}
            self.tool_calls = [{"id": f"same_{index}", "type": "function",
                                "function": {"name": "compare_models", "arguments": json.dumps(args)}}]
            self.finish_reason = "tool_calls"
            yield from ()

    loop = chat_loop(store, script)
    loop.factory = Looping
    list(loop.run())
    saved = saved_turn(store, loop)
    assert saved["status"] == "completed" and loop.completion.wrap_up["reason"] == "repeat"
    assert reviewed(saved["agent_review"], saved["consensus"])
    # Two runs, one refusal, then the fourth identical request ends the turn.
    assert len(saved["agent_review"]["comparisons"]) == 2
    error = tool_result(loop, "same_2")["error"]
    assert "identical compare_models call already ran 2 times" in error
    # Never run; closed with a result in its batch before the last step that
    # writes the answer (every call gets one, T2; providers reject a tool
    # call without one).
    assert tool_result(loop, "same_3") == {"error": "Not run: this message reached its limit."}
    assert len([s for s, _ in script.calls if s.startswith("completion:")]) == 4 + 1


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
    assert saved["status"] == "completed" and saved["agent_review"]["comparisons"] == []
    assert saved["assistant_response"] == "The first option costs 100."
    assert "".join(e["text"] for e in events if e["type"] == "delta") == "The first option costs 100."


@pytest.mark.parametrize("fail_model", [False, True])
def test_three_invalid_rounds_still_end_in_an_answer(store, fail_model):
    """Three rejected calls (a malformed field) after paid comparisons end
    the turn with an answer, also when a comparison had a single answer."""
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
    list(loop.run())
    saved = saved_turn(store, loop)
    assert all("error" in tool_result(loop, f"s{n}_0") for n in (1, 2, 3))
    assert saved["status"] == "completed" and reviewed(saved["agent_review"], saved["consensus"])
    assert loop.completion.wrap_up["reason"] == "invalid"
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
    # The VM tools too: a command's result depends on the VM's state, which
    # every command may change (the tests again after an edit; test_agent_vm),
    # and sharing a file again after it changed is a new file for the user.
    # Reading a background process's output again is waiting for it, and
    # rendering the same deck again after an edit is checking the edit.
    # The same plan between work steps says where the agent stands; refusing
    # it would end a long VM run at its fourth unchanged plan.
    assert agent_delegation.REPEATABLE_TOOLS == {"wait_agents", "vm_exec", "vm_read_file", "vm_write_file",
                                                 "vm_edit_file", "vm_share_file", "vm_start_process",
                                                 "vm_process_output", "vm_stop_process", "vm_view_image",
                                                 "vm_render_office", "vm_install_packages", "update_plan",
                                                 "browser"}
    plan = {"id": "p", "type": "function", "function": {"name": "update_plan", "arguments": json.dumps(
        {"items": [{"content": "Run the tests", "status": "in_progress"}]})}}
    assert all(loop._identical_call(plan) is None for _ in range(5))


def with_probe(loop, outcomes):
    """Adds a tool ``probe`` to the loop: call n returns ``outcomes[n]`` or
    raises it (the last one repeats). Returns the list of the calls it got."""
    from pydantic import BaseModel, ConfigDict
    from app.services.agent_tools import ReadOnlyTool, ToolRegistry

    class Args(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        path: str = ""
    seen = []

    def probe(args, *, cancellation):
        outcome = outcomes[min(len(seen), len(outcomes) - 1)]
        seen.append(args.path)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    loop.registry = ToolRegistry([*loop.registry.tools.values(), ReadOnlyTool("probe", "A probe.", Args, probe)],
                                 argument_limit=24_000)
    return seen


def probes(count, *, same=False):
    """``count`` steps of one probe call each, then the answer."""
    return [*([("probe", {"path": "a" if same else f"file-{n}"})] for n in range(count)), None]


def test_calls_that_ran_and_failed_are_the_tools_answers_not_invalid_requests(store):
    """An edit whose text was not found, a file that is not there, a
    workspace that did not start: the tool ran and said why. Three such
    steps in a row ended real work as "invalid tool requests"."""
    from app.services.agent_delegation import FAILED_TOOL_ROUNDS, INVALID_TOOL_ROUNDS
    assert FAILED_TOOL_ROUNDS > INVALID_TOOL_ROUNDS == 3
    script = Script()
    loop = chat_loop(store, script)
    seen = with_probe(loop, [ValueError("No file at that path.")])
    loop.factory = planned(script, probes(FAILED_TOOL_ROUNDS - 1))
    list(loop.run())
    saved = saved_turn(store, loop)
    assert len(seen) == FAILED_TOOL_ROUNDS - 1 and tool_result(loop, "s0_0") == {"error": "No file at that path."}
    assert saved["status"] == "completed" and getattr(loop.completion, "wrap_up", None) is None
    assert saved["assistant_response"] == "The first option costs 100."


def test_tools_that_keep_failing_end_the_turn_with_its_answer_and_the_true_reason(store):
    from app.services.agent_delegation import FAILED_TOOL_ROUNDS
    script = Script()
    requests = []
    loop = chat_loop(store, script)
    seen = with_probe(loop, [ValueError("The workspace did not start just now; nothing ran.")])
    planned_type = planned(script, probes(FAILED_TOOL_ROUNDS + 3))

    class Recorded(planned_type):
        def stream(self, **kwargs):
            if self.step_id.startswith("completion:"):
                requests.append(kwargs)
            yield from super().stream(**kwargs)
    loop.factory = Recorded
    list(loop.run())
    saved = saved_turn(store, loop)
    assert len(seen) == FAILED_TOOL_ROUNDS and saved["status"] == "completed"
    assert loop.completion.wrap_up["reason"] == "tools" and saved["agent_wrap_up"]["reason"] == "tools"
    # The closing step is told what happened, in words that are true of it.
    closing = json.dumps(requests[-1]["messages"])
    assert f"failed {FAILED_TOOL_ROUNDS} times in a row" in closing and "invalid" not in closing.split("consens.io")[-1]
    assert not steering(requests[-1])


def test_a_call_that_works_between_failures_starts_the_count_anew(store):
    from app.services.agent_delegation import FAILED_TOOL_ROUNDS
    script = Script()
    loop = chat_loop(store, script)
    failed = ValueError("old_string was not found in the file.")
    outcomes = [*[failed] * (FAILED_TOOL_ROUNDS - 1), {"text": "ok"}, *[failed] * (FAILED_TOOL_ROUNDS - 1), {"text": "ok"}]
    seen = with_probe(loop, outcomes)
    loop.factory = planned(script, probes(len(outcomes)))
    list(loop.run())
    assert len(seen) == len(outcomes) and getattr(loop.completion, "wrap_up", None) is None
    assert saved_turn(store, loop)["status"] == "completed"


def test_a_call_that_failed_may_come_again_unchanged(store):
    """The repeat guard counts calls whose results are in hand. A call that
    came to nothing (a service that was busy, a workspace still starting) is
    no repetition yet: the same call may be what works next. Once: what
    fails the same way again is one."""
    script = Script()
    loop = chat_loop(store, script)
    busy = ValueError("The service is busy right now; the same call may work in a moment.")
    seen = with_probe(loop, [busy, {"text": "ok"}, {"text": "ok"}, {"text": "ok"}])
    loop.factory = planned(script, probes(8, same=True))
    list(loop.run())
    # The failure, two that worked, then the guard: refused once, and the next identical call ends the turn.
    assert len(seen) == 3 and "already ran 2 times" in tool_result(loop, "s3_0")["error"]
    assert loop.completion.wrap_up["reason"] == "repeat"
    # A call that only ever fails gets one attempt more than the guard allows, not an endless row.
    script = Script()
    loop = chat_loop(store, script)
    seen = with_probe(loop, [busy])
    loop.factory = planned(script, probes(8, same=True))
    list(loop.run())
    assert len(seen) == 3 and loop.completion.wrap_up["reason"] == "repeat"


def test_a_tool_that_breaks_on_the_apps_side_fails_that_call_not_the_turn(store, caplog):
    """A storage error inside a tool (a file's bytes, the chat's documents)
    ended the whole turn as "the model provider could not finish this
    request"."""
    from app.services.agent_delegation import TOOL_BROKE
    script = Script()
    loop = chat_loop(store, script)
    seen = with_probe(loop, [RuntimeError("bucket unreachable: secret detail"), {"text": "ok"}])
    loop.factory = planned(script, probes(2))
    list(loop.run())
    saved = saved_turn(store, loop)
    assert tool_result(loop, "s0_0") == {"error": TOOL_BROKE} and tool_result(loop, "s1_0") == {"text": "ok"}
    assert saved["status"] == "completed" and saved.get("agent_failure") is None
    assert "Agent tool broke on the app's side tool=probe category=RuntimeError" in caplog.text
    assert "secret detail" not in caplog.text


def test_a_failure_with_a_meaning_of_its_own_still_ends_the_turn(store):
    from app.services.agent_provider_limits import AgentRunInterrupted
    script = Script()
    loop = chat_loop(store, script)
    with_probe(loop, [AgentRunInterrupted("The response lost its saved chat state.")])
    loop.factory = planned(script, probes(1))
    with pytest.raises(AgentRunInterrupted):
        list(loop.run())
    assert saved_turn(store, loop)["agent_failure"]["code"] == "run_interrupted"


def cut_calls(script, cut_steps, *, characters=5000):
    """Steering steps ``cut_steps`` end at the output limit in the middle of
    a probe call with ``characters`` of arguments written (as the client
    leaves such a step: ModelOutputLimit, the half call in _tool_parts);
    every other step is Script's."""
    from app.services.agent_provider_limits import ModelOutputLimit
    base = type(script.factory())

    class Cut(base):
        def stream(self, *, model, messages, **kwargs):
            index = int(self.step_id.split(":")[-1]) if self.step_id.startswith("completion:") else None
            if index not in cut_steps or not steering(kwargs):
                script.requests.append(messages) if index is not None else None
                yield from super().stream(model=model, messages=messages, **kwargs)
                return
            script.calls.append((self.step_id, model.model))
            self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 2000}, model)
            self._tool_parts = {0: {"id": "cut", "type": "function",
                                    "function": {"name": "probe", "arguments": '{"path": "' + "x" * characters}}}
            self.finish_reason = "length"
            yield from ()
            raise ModelOutputLimit()
    script.requests = []
    return Cut


def test_a_call_cut_off_at_the_output_limit_is_said_and_the_work_goes_on(store):
    """A whole file in one vm_write_file can pass a step's output limit: the
    call is cut in half. No lighter reasoning makes it fit, and the turn
    failed with "used its whole output allowance on reasoning" after an hour
    of work. The model is told what happened instead."""
    script = Script(compares=0)
    loop = chat_loop(store, script)
    with_probe(loop, [{"text": "ok"}])
    loop.factory = cut_calls(script, {0})
    list(loop.run())
    saved = saved_turn(store, loop)
    assert saved["status"] == "completed" and saved.get("agent_failure") is None
    assert getattr(loop.completion, "wrap_up", None) is None
    # The next step reads the fact, in place of a result of the call that never ran.
    [said] = [m["content"] for m in script.requests[0] if "output limit" in str(m.get("content"))]
    assert "in the middle of a probe call" in said and "after 5010 characters" in said and "did not run" in said
    assert said.startswith(agent_delegation.PROGRESS_OPEN)
    # The half call is no message of the conversation.
    assert not any(m.get("tool_calls") for m in loop.messages if m.get("role") == "assistant")


def test_calls_that_keep_being_cut_off_end_the_turn_with_its_answer(store):
    script = Script(compares=0)
    loop = chat_loop(store, script)
    with_probe(loop, [{"text": "ok"}])
    loop.factory = cut_calls(script, {0, 1, 2, 3, 4})
    list(loop.run())
    assert saved_turn(store, loop)["status"] == "completed" and loop.completion.wrap_up["reason"] == "invalid"
    assert len(routing_steps(script)) == agent_delegation.INVALID_TOOL_ROUNDS + 1


def test_a_call_cut_off_after_a_few_characters_is_a_step_that_reasoned_through_its_allowance(store):
    """Little of the call was written: the reasoning before it took the
    allowance. That is the lighter-reasoning retry's case, as before."""
    assert DelegationLoop._cut_call(type("Value", (), {
        "finish_reason": "length", "tool_calls": [],
        "_tool_parts": {0: {"function": {"name": "probe", "arguments": '{"path": "a'}}}})()) is None
    assert DelegationLoop._cut_call(type("Value", (), {
        "finish_reason": "stop", "tool_calls": [],
        "_tool_parts": {0: {"function": {"name": "probe", "arguments": "x" * 9000}}}})()) is None


def test_a_turn_that_ended_at_a_limit_leaves_its_work_for_the_follow_up(store):
    """Its answer says a follow-up can go on with the work: the next message
    then needs what was done. Without the workspace nothing was kept, and
    "Continue" started the research again."""
    script = Script()
    loop = chat_loop(store, script)
    seen = with_probe(loop, [{"text": "found it"}])
    loop.policy = replace(loop.policy, turn_steps=2, turn_comparisons=10)
    loop.factory = planned(script, probes(5))
    list(loop.run())
    saved = saved_turn(store, loop)
    assert loop.completion.wrap_up["reason"] == "steps" and len(seen) == 2
    record = store._turn_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()["agent_work_record"]
    assert "1. probe" in record and "2. probe" in record and "3. probe" not in record
    # A turn that simply answered keeps none.
    script = Script()
    plain = chat_loop(store, script)
    with_probe(plain, [{"text": "found it"}])
    plain.factory = planned(script, probes(1))
    list(plain.run())
    assert "agent_work_record" not in store._turn_ref(UID, plain.chat_id, plain.turn_id).get().to_dict()


def test_the_work_record_says_what_was_searched_for_and_read():
    from app.services.agent_compaction import describe
    found = {"note": "n", "searches": [
        {"query": "a", "results": [{"url": "https://www.example.org/x"}, {"url": "https://example.org/y"}]},
        {"query": "b", "results": [{"url": "https://example.net/z"}], "also_above": ["https://www.example.org/x"]},
        {"query": "c", "failed": "The search service did not answer."}]}
    assert describe("web_search", json.dumps({"queries": ["price option one", "option one 2026", "c"]}),
                    json.dumps(found)) == ("web_search price option one | option one 2026 | c -> pages of "
                                           "example.org, example.net")
    assert describe("web_search", json.dumps({"queries": ["q"]}),
                    json.dumps({"searches": [{"query": "q", "results": []}]})) == "web_search q -> nothing found"
    assert describe("read_source", json.dumps({"url": "https://example.org/report", "start": 24000}),
                    json.dumps({"status": "completed", "title": "Annual report"})) == (
        "read_source https://example.org/report from 24000 -> completed: Annual report")
    assert describe("read_source", json.dumps({"url": "https://example.org/gone"}),
                    json.dumps({"status": "failed"})) == "read_source https://example.org/gone -> failed"


def test_the_runs_closing_write_is_tried_again_through_a_short_outage(store, monkeypatch):
    """Without it the turn stayed pending until its lease ran out, and the
    reaper closed it empty: no answer, no activity, no work record."""
    from google.api_core.exceptions import ServiceUnavailable
    monkeypatch.setattr(agent_delegation.time, "sleep", lambda seconds: None)
    script = Script()
    loop = chat_loop(store, script)
    real, calls = store.finish_run, []

    def flaky(*args, **kwargs):
        calls.append(kwargs["status"])
        if len(calls) < 3:
            raise ServiceUnavailable("Firestore is briefly away")
        return real(*args, **kwargs)
    monkeypatch.setattr(store, "finish_run", flaky)
    list(loop.run())
    saved = saved_turn(store, loop)
    assert calls == ["succeeded"] * 3 and saved["status"] == "completed"
    assert saved["assistant_response"] == "The first option costs 100."
    # An error that no further try heals is not tried again.
    other = chat_loop(store, Script())
    attempts = []

    def closed(*args, **kwargs):
        attempts.append(1)
        raise ValueError("Agent run owner does not match")
    monkeypatch.setattr(store, "finish_run", closed)
    with pytest.raises(ValueError):
        list(other.run())
    assert len(attempts) == 1
