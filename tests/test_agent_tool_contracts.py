"""What the harness tells the model about its calls, and how it answers a
call it cannot run: facts the model can act on, never a dead end.
(docs/agent-mode.md, "Ein gescheiterter Aufruf ist keine ungültige Anfrage".)"""
from dataclasses import replace
import json
import threading

import pytest
from pydantic import BaseModel, ConfigDict

from app.services import agent_ask, agent_delegation
from app.services.agent_tools import ArgumentsTooLong, ReadOnlyTool, ToolRegistry
from app.services.prompt_defaults import AGENT_AUDIT_ANSWER_SECTION, AGENT_VM_PROMPT
from test_agent_comparison import Script
from test_agent_runs import UID, store  # noqa: F401  (fixture)
from test_agent_turn_limits import chat_loop, planned, probes, saved_turn, tool_result, with_probe


def test_the_prompt_says_when_text_beside_a_call_is_the_answer_and_how_many_calls_a_step_runs():
    """Text beside a memory save or a prepared card is the answer and ends
    the turn (agent_answer_mode.SIDE_TOOLS). The prompt only said "a note on
    your work": "I'll note that, then compare the options." beside
    update_memory became the whole answer."""
    assert "text beside tool calls shows the user as a note on your work. One exception" in AGENT_AUDIT_ANSWER_SECTION
    assert "is your answer as well, and the turn ends with it" in AGENT_AUDIT_ANSWER_SECTION
    # In every chat, not only with the workspace; and true of reads, which run side by side.
    assert "A step runs up to four tool calls" in AGENT_AUDIT_ANSWER_SECTION
    assert "run side by side" in AGENT_AUDIT_ANSWER_SECTION and "one after another, in your order, up to four" not in AGENT_VM_PROMPT


def test_a_step_the_user_asked_for_exactly_needs_no_second_yes_in_the_browser_either():
    """The principle lets a step in the user's name go ahead when they asked
    for exactly that. The browser's paragraph and the reviewers' brief say the
    rule again and carry the same exception: without it "send exactly this
    mail" has two answers, and a reviewer holds the sent mail against the agent."""
    from app.services.agent_audit import tool_brief
    from app.services.prompt_defaults import AGENT_AUDIT_SYSTEM_PROMPT
    assert "waits for their yes unless they asked for exactly that" in AGENT_AUDIT_SYSTEM_PROMPT
    assert "waits for their yes through ask_user unless they asked for exactly that" in AGENT_VM_PROMPT
    assert "waits for their yes through ask_user unless the user asked for exactly that" in " ".join(tool_brief(["browser"]))


class Text(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = ""


def test_a_call_longer_than_its_tool_takes_says_so_and_leaves_the_conversation(store):
    script = Script()
    loop = chat_loop(store, script)
    written = []
    loop.registry = ToolRegistry([*loop.registry.tools.values(), ReadOnlyTool(
        "write", "Writes.", Text, lambda args, *, cancellation: written.append(args.text) or {"ok": True},
        argument_limit=30_000)], argument_limit=24_000)
    long_call = ("write", {"text": "x" * 40_000})
    loop.factory = planned(script, [[long_call], [("write", {"text": "short"})], None])
    list(loop.run())
    refused = tool_result(loop, "s0_0")["error"]
    # What happened and what to do, in the tool's name; no word of permission.
    assert refused.startswith("write did not run: its arguments are longer than the 30,000 characters")
    assert "smaller calls" in refused and "authorized" not in refused
    assert written == ["short"] and saved_turn(store, loop)["status"] == "completed"
    # The forty thousand characters are not re-sent with every later step.
    [call] = next(m["tool_calls"] for m in loop.messages if m.get("role") == "assistant" and m.get("tool_calls"))
    assert call["id"] == "s0_0" and call["function"] == {"name": "write", "arguments": "{}"}
    assert len(json.dumps(loop.messages)) < 20_000
    with pytest.raises(ArgumentsTooLong):
        loop.registry.validate({"function": {"name": "write", "arguments": json.dumps({"text": "x" * 40_000})}})


def test_an_argument_named_twice_says_which(store):
    loop = chat_loop(store, Script())
    with_probe(loop, [{"ok": True}])
    with pytest.raises(ValueError, match='probe arguments name "path" twice'):
        loop.registry.validate({"function": {"name": "probe", "arguments": '{"path": "a", "path": "b"}'}})


def test_the_reads_of_a_step_run_beside_its_other_calls(store):
    """A plan update or a memory save next to three reads made all of them
    wait their turn: only a step of reads alone ran them side by side."""
    script = Script()
    loop = chat_loop(store, script)
    order, both = [], threading.Barrier(2, timeout=5)

    def slow(args, *, cancellation):
        order.append("other starts")
        return {"ok": True}

    def read(args, *, cancellation):
        both.wait()  # Passes only when the two reads run at the same time.
        order.append(f"read {args.text}")
        return {"text": args.text}
    loop.registry = ToolRegistry([*loop.registry.tools.values(), ReadOnlyTool("update_plan", "Other.", Text, slow),
                                  ReadOnlyTool("read_file", "Reads.", Text, read)], argument_limit=24_000)
    loop.factory = planned(script, [[("update_plan", {}), ("read_file", {"text": "a"}), ("read_file", {"text": "b"})],
                                    None])
    list(loop.run())
    assert tool_result(loop, "s0_1") == {"text": "a"} and tool_result(loop, "s0_2") == {"text": "b"}
    assert sorted(order) == ["other starts", "read a", "read b"]
    # The results stand in the calls' order, whatever finished first.
    tools = [m["tool_call_id"] for m in loop.messages if m.get("role") == "tool"]
    assert tools == ["s0_0", "s0_1", "s0_2"]


def test_a_message_without_the_workspace_learns_of_its_limits_near_their_end(store):
    script = Script()
    loop = chat_loop(store, script)
    with_probe(loop, [{"ok": True}])
    loop.policy = replace(loop.policy, turn_steps=5, turn_comparisons=10)
    loop.factory = planned(script, probes(4))
    list(loop.run())
    notes = [m["content"] for m in loop.messages if str(m.get("content")).startswith(agent_delegation.PROGRESS_OPEN)]
    # Nothing for the first steps; from four fifths of the steps on, the fact.
    assert len(notes) == 1 and "step 4 of at most 5" in notes[0] and "waiting" in notes[0]


def test_what_the_user_writes_into_the_run_counts_as_their_own_words(store):
    """A settings change asks for the user's own words (agent_settings): a
    message sent into the running response is theirs like the first one."""
    loop = chat_loop(store, Script())
    before = len(loop.answer_conversation)
    loop.notes.append({"id": "n1", "text": "Take Sonnet from now on."})
    assert loop._take_notes("completion:1")
    assert loop.answer_conversation[before:] == [{"role": "user", "content": "Take Sonnet from now on."}]
    assert loop.messages[-1]["content"].endswith("Take Sonnet from now on.")


def test_ask_user_takes_its_choices_as_the_registry_does():
    """Claude sends a list as its JSON text now and then; the registry takes
    it, so the card must open too."""
    call = {"function": {"name": agent_ask.TOOL, "arguments": json.dumps(
        {"request": "Which one?", "choices": json.dumps(["Red", "Blue"])})}}
    assert agent_ask.requested(call)[3] == ["Red", "Blue"]
    assert agent_ask.requested({"function": {"name": agent_ask.TOOL, "arguments": '{"request": 5}'}}) is None
