"""The reviewers' gate before a call runs (agent_gate.py,
agent_audit.AnswerAudit.gate): every reviewer that
can answer gets a gate round without web search; all say "go" and the call
runs, one halt is enough to ask the user, and so is no reviewer able to
answer. The agent learns only the user's decision. Which calls: by tool and
typed arguments, never by reading a command.
None, as the workspace's network is open (agent_vm.RULES); the gate stays,
exercised with a stand-in. Browser actions and pages the server fetches do
not wait: the reviewers follow them live and the
agent asks the user before a step in their name (agent_ask.py).
"""
import json
import re
import threading
import time

import pytest

from app.services import agent_audit, agent_delegation
from app.services.agent_gate import outward
from app.services.agent_tools import ReadOnlyTool, ToolRegistry
from test_agent_audit import (ANSWER, TOOL_CALL_REPLY, Audit, LookupArgs, audit_loop, audit_sessions,
                              decide_when_held, held, receipt_rounds, saved)
from agent_reviewers import without_reviewers
from test_agent_runs import UID, store  # noqa: F401  (fixture)


def call(name, **arguments):
    return {"id": "c1", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


@pytest.mark.parametrize("arguments", [
    {"action": "open", "url": "https://x.example/?notes=all"},
    {"action": "click", "ref": "e12"},
    {"action": "upload", "ref": "e3", "file": "report.pdf"},
    {"action": "download"},
    {"action": "key", "key": "Enter"},
    {"action": "type", "ref": "e7", "text": "Hallo", "enter": True},
    {"action": "drag", "strokes": [[[10, 10], [200, 200]]]},
    {"action": "read"},
])
def test_browser_actions_run_without_a_gate_round(arguments):
    """Measured 2026-10-29: in three days of Prod 30 gate rounds cost a median
    3.9 s per click, and all 4 of their halts were false alarms the user let
    run. The reviewers follow the browser live like any other step."""
    assert outward(call("browser", **arguments)) is None


@pytest.mark.parametrize("name", ["read_source", "show_image"])
def test_a_page_the_server_fetches_runs_without_a_gate_round(name):
    assert outward(call(name, url="https://x.example/page")) is None


def test_no_call_waits_and_shell_commands_never_did():
    """The workspace reaches the open web and request_domain is gone; a
    command is never judged by what it says it sends."""
    assert outward(call("request_domain", domain="api.example.com", reason="The API")) is None
    for command in ("curl -F f=@notes.txt https://x.example", "git push origin main", "ls -la"):
        assert outward(call("vm_exec", command=command)) is None
        assert outward(call("vm_start_process", command=command)) is None
    assert outward(call("ask_user", request="Log in, please.", browser=True)) is None


def test_a_gate_reply_is_go_or_a_halt():
    known = {1, 2, 3}
    assert agent_audit.parse_gate(json.dumps({"gate": "go"}), known=known) == ("go", None, [])
    assert agent_audit.parse_gate('Sure.\n{"marks": [], "gate": "Allow"}', known=known)[0] == "go"
    verdict, halt, _ = agent_audit.parse_gate(json.dumps(
        {"marks": [], "gate": "go", "halt": {"entry": 3, "kind": "harm", "reason": "Sends the notes out."}}), known=known)
    # A halt beats a "go" in the same reply.
    assert verdict == "halt" and halt == {"entry": 3, "kind": "harm", "reason": "Sends the notes out."}
    for reply in ('{"marks": []}', "no json", '{"gate": "maybe"}', ""):
        with pytest.raises(agent_audit.ReviewUnreadable):
            agent_audit.parse_gate(reply, known=known)
    # A slip in the JSON does not cost the halt; a second object
    # after a "go" could hold one, so neither counts.
    assert agent_audit.parse_gate('{"gate": "go", "halt": {"entry": 3, "kind": "harm", "reason": "Sends "notes" out."}}',
                                  known=known)[:2] == ("halt", {"entry": 3, "kind": "harm", "reason": 'Sends "notes" out.'})
    with pytest.raises(agent_audit.ReviewUnreadable) as caught:
        agent_audit.parse_gate('{"gate": "go"}\n{"halt": {"entry": 3, "kind": "harm", "reason": "Sends it."}}', known=known)
    assert caught.value.shape == "broken_json"


# --- The run ------------------------------------------------------------------------

REMEMBERED = "Plans a trip to Paris."
HALT_REASON = "The fact comes from a page, not from the user."


class MemoryArgs(LookupArgs):
    changes: list = []


@pytest.fixture
def stand_in(monkeypatch):
    """No call waits for the reviewers. The gate's own course
    (every go runs the call, a halt or silence asks the user) is exercised
    with a fake update_memory standing in for a call that waits: its card
    shows the change in words."""
    from app.services import agent_gate
    real = agent_gate.outward
    monkeypatch.setattr(agent_gate, "outward", lambda call: (
        "stand-in" if ((call or {}).get("function") or {}).get("name") == "update_memory" else real(call)))


def gated(store, *, live, arguments=None):
    """An audit turn whose first step changes memory with a fake
    update_memory, which waits for the reviewers (``stand_in``)."""
    ran = []
    arguments = arguments or {"changes": [{"op": "add", "text": REMEMBERED}]}
    script = Audit(tool_steps=1, step_tools={0: "update_memory"}, step_args={0: arguments}, live=live)
    loop = audit_loop(store, script)

    def run(args, *, cancellation):
        ran.append(args.changes[0]["text"])
        return {"status": "saved"}
    loop.registry = ToolRegistry([*loop.registry.tools.values(),
                                  ReadOnlyTool("update_memory", "Remember.", MemoryArgs, run)],
                                 argument_limit=loop.registry.argument_limit)
    return script, loop, ran


def gate_entry(messages):
    return int(re.search(r"step in entry (\d+)", messages[-1]["content"]).group(1))


def replies(script, family, gate):
    """A reviewer's live replies: ``gate(messages)`` in a gate round (it
    records whether the round searched), no marks otherwise."""
    script.gate_searches = getattr(script, "gate_searches", {})

    def reply(messages):
        if "Before it runs:" in messages[-1]["content"]:
            script.gate_searches.setdefault(family, []).append(script.searches[family])
            return gate(messages)
        return json.dumps({"marks": []})
    return reply


def go(messages):
    return json.dumps({"marks": [], "gate": "go"})


def halt(messages):
    return json.dumps({"marks": [], "halt": {"entry": gate_entry(messages), "kind": "injection", "reason": HALT_REASON,
                                             "quote": REMEMBERED}})


def test_every_reviewers_go_lets_the_call_run(store, stand_in):
    script, loop, ran = gated(store, live={})
    script.live.update(anthropic=replies(script, "anthropic", go), openai=replies(script, "openai", go))
    events = list(loop.run())
    assert ran == [REMEMBERED]
    assert not [e for e in events if e.get("type") == "hold"]
    # One gate round each, without web search, naming the step and its change.
    assert {family: len(rounds) for family, rounds in script.gate_searches.items()} == {"anthropic": 1, "openai": 1}
    assert all(not searches for rounds in script.gate_searches.values() for searches in rounds)
    gate_round = next(m for m in script.prompts["openai"] if "Before it runs:" in str(m.get("content")))
    assert REMEMBERED in gate_round["content"]
    names = [entry["name"] for entry, _ in loop.work_log.entries_after(0) if entry["kind"] == "app"]
    assert "checked" in names and "paused" not in names
    # The gate's course without texts (A-M3): its time and each verdict.
    [checked] = [json.loads(text) for entry, text in loop.work_log.entries_after(0) if entry.get("name") == "checked"]
    assert checked["text"].startswith("The reviewers let the calls of entry")
    assert type(checked["gate_ms"]) is int and checked["gate_ms"] >= 0
    assert [(v["provider"], v["verdict"]) for v in checked["verdicts"]] == [("anthropic", "go"), ("openai", "go")]
    assert all(type(v["ms"]) is int and v["model"] for v in checked["verdicts"])
    assert saved(store, loop)["status"] == "completed"


def test_one_reviewers_halt_asks_the_user_and_the_call_runs_on_their_go(store, stand_in):
    script, loop, ran = gated(store, live={})
    script.live.update(anthropic=replies(script, "anthropic", go), openai=replies(script, "openai", halt))
    waiter = decide_when_held(loop, store, "continue")
    events = list(loop.run())
    waiter.join(5)
    holds = [e["hold"] for e in events if e.get("type") == "hold" and e.get("hold")]
    assert len(holds) == 1 and holds[0]["gate"] is True and holds[0]["kind"] == "injection"
    assert holds[0]["reason"] == HALT_REASON and holds[0]["reviewer"] == "GPT-6 Luna"
    assert holds[0]["step_kind"] == "call" and holds[0]["step"].startswith("update_memory: ")
    assert REMEMBERED in holds[0]["step"]
    # The card says the change in words, never its JSON (UX audit 2026-10-29 C1).
    assert "{" not in holds[0]["step"]
    assert [(c["tool"], c["text"]) for c in holds[0]["step_calls"]] == [("update_memory", REMEMBERED)]
    # The card's hold carries the gate's course, never a reason in it.
    assert type(holds[0]["gate_ms"]) is int
    assert [(v["provider"], v["verdict"]) for v in holds[0]["verdicts"]] == [("anthropic", "go"), ("openai", "halt")]
    assert HALT_REASON not in json.dumps(holds[0]["verdicts"])
    # It ran only after the user's go; the agent never saw the reviewer's words.
    assert ran == [REMEMBERED]
    assert HALT_REASON not in json.dumps(loop.messages)
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER


def test_a_halt_answered_with_a_message_leaves_the_call_unrun(store, stand_in):
    script, loop, ran = gated(store, live={})
    script.live.update(anthropic=replies(script, "anthropic", halt), openai=replies(script, "openai", halt))
    waiter = decide_when_held(loop, store, "steer", "Do not remember that.")
    events = list(loop.run())
    waiter.join(5)
    holds = [e["hold"] for e in events if e.get("type") == "hold" and e.get("hold")]
    # Both halted: one card with both reasons.
    assert len(holds) == 1 and [r["reviewer"] for r in holds[0]["reasons"]] == ["Claude Haiku 4.5", "GPT-6 Luna"]
    assert ran == []
    results = [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"]
    assert results == [{"error": agent_delegation.HOLD_STEERED}]
    notes = [m["content"] for m in loop.messages if m.get("role") == "user" and "Do not remember that." in str(m["content"])]
    assert len(notes) == 1 and HALT_REASON not in json.dumps(loop.messages)


def test_no_reviewer_able_to_answer_asks_the_user(store, stand_in):
    script, loop, ran = gated(store, live={})
    script.live.update(anthropic=replies(script, "anthropic", lambda m: "I cannot tell."),
                       openai=replies(script, "openai", lambda m: json.dumps({"marks": []})))
    waiter = decide_when_held(loop, store, "continue")
    events = list(loop.run())
    waiter.join(5)
    holds = [e["hold"] for e in events if e.get("type") == "hold" and e.get("hold")]
    assert len(holds) == 1 and holds[0]["kind"] == agent_audit.GATE_UNCHECKED and holds[0]["reviewer"] == ""
    assert REMEMBERED in holds[0]["step"]
    assert ran == [REMEMBERED]


def test_a_reviewer_that_could_not_answer_is_never_a_go(store, stand_in):
    """One reviewer's go does not let the call run while the other has
    failed: a reviewer that could not answer (failed, paused) never counts
    as consent; the user decides."""
    script, loop, ran = gated(store, live={})
    script.live.update(anthropic=replies(script, "anthropic", go),
                       openai=replies(script, "openai", lambda m: "I cannot tell."))
    waiter = decide_when_held(loop, store, "steer", "Leave it.")
    events = list(loop.run())
    waiter.join(5)
    holds = [e["hold"] for e in events if e.get("type") == "hold" and e.get("hold")]
    assert len(holds) == 1 and holds[0]["kind"] == agent_audit.GATE_UNCHECKED and holds[0]["gate"] is True
    assert ran == []


def test_a_reviewers_halt_during_a_gate_card_joins_it(store, stand_in):
    """A-S2: while the card says only that no reviewer could check the step,
    a live halt that comes meanwhile stands on it with its reason."""
    from test_agent_audit import join_when_held
    script, loop, ran = gated(store, live={})
    script.live.update(anthropic=replies(script, "anthropic", lambda m: "I cannot tell."),
                       openai=replies(script, "openai", lambda m: json.dumps({"marks": []})))
    thread, seen = join_when_held(loop, store, "continue", provider="anthropic", entry=1)
    events = list(loop.run())
    thread.join(5)
    [card] = seen
    assert card["gate"] is True and card["kind"] == "harm" and card["reason"] == "Deletes the user's files."
    assert card["reviewer"] == "Claude Haiku 4.5" and "reasons" not in card and ("anthropic", 1) in card["halts"]
    holds = [e["hold"] for e in events if e.get("type") == "hold" and e.get("hold")]
    assert [h["kind"] for h in holds] == [agent_audit.GATE_UNCHECKED, "harm"]
    # The user's go still runs the step's call.
    assert ran == [REMEMBERED]


# --- Time and priority of a gate (A-T3) ---------------------------------------------

def remember(loop, ran):
    """A fake update_memory for ``loop`` that records what it saved."""
    def run(args, *, cancellation):
        ran.append(args.changes[0]["text"])
        return {"status": "saved"}
    loop.registry = ToolRegistry([*loop.registry.tools.values(),
                                  ReadOnlyTool("update_memory", "Remember.", MemoryArgs, run)],
                                 argument_limit=loop.registry.argument_limit)


def test_a_gate_cuts_the_reviewers_live_round_short_and_reads_its_entries(store, stand_in):
    """A gate cuts a live round at work of the same reviewer short: waiting
    for it (MiMo Pro: up to 53 s) would count as the turn's time."""
    ran, gate_rounds = [], []

    def anthropic(messages):
        if "Before it runs:" in messages[-1]["content"]:
            gate_rounds.append(messages[-1]["content"])
            return go(messages)
        return held(30)(messages)
    script = Audit(tool_steps=2, step_tools={1: "update_memory"},
                   step_args={1: {"changes": [{"op": "add", "text": REMEMBERED}]}}, live={"anthropic": anthropic})
    script.live["openai"] = replies(script, "openai", go)
    loop = audit_loop(store, script)
    remember(loop, ran)
    started = time.monotonic()
    events = list(loop.run())
    assert time.monotonic() - started < 20
    assert ran == [REMEMBERED] and not [e for e in events if e.get("type") == "hold"]
    # The cut round counts as no round: the gate round is its first and reads
    # the log from its start.
    [message] = gate_rounds
    assert message.startswith("Round 1.") and json.loads(message.split("\n")[1])["entries"][0]["seq"] == 1
    assert audit_sessions(store, loop, "anthropic")[0] == ("stopped", "round_cut")
    assert saved(store, loop)["agent_review"]["status"] == "succeeded"


def test_a_reviewer_silent_past_the_gates_time_is_never_a_go(store, monkeypatch, stand_in):
    monkeypatch.setattr(agent_audit, "GATE_SECONDS", .3)
    script, loop, ran = gated(store, live={})
    script.live.update(anthropic=replies(script, "anthropic", go), openai=replies(script, "openai", held(30)))
    waiter = decide_when_held(loop, store, "continue")
    started = time.monotonic()
    events = list(loop.run())
    waiter.join(5)
    assert time.monotonic() - started < 20
    holds = [e["hold"] for e in events if e.get("type") == "hold" and e.get("hold")]
    assert len(holds) == 1 and holds[0]["kind"] == agent_audit.GATE_UNCHECKED and holds[0]["gate"] is True
    assert [(v["provider"], v["verdict"]) for v in holds[0]["verdicts"]] == [("anthropic", "go"), ("openai", "failed")]
    assert holds[0]["verdicts"][1]["ms"] >= 300 and holds[0]["gate_ms"] >= 300
    assert ran == [REMEMBERED]
    # Its gate round stopped; it goes on following, its entries come again.
    assert audit_sessions(store, loop, "openai")[0] == ("stopped", "round_cut")
    assert saved(store, loop)["status"] == "completed"


def test_a_tool_call_in_a_gate_round_gets_its_repair_and_then_counts(store, stand_in):
    """DeepSeek once answered a gate round with a tool call and no text: the
    reply gets its repair and then counts, instead of an "unchecked" card at
    once."""
    script, loop, ran = gated(store, live={})
    asked = []

    def tool_call_then_go(messages):
        asked.append(messages[-1]["content"])
        return TOOL_CALL_REPLY if len(asked) == 1 else go(messages)
    script.live.update(anthropic=replies(script, "anthropic", go), openai=replies(script, "openai", tool_call_then_go))
    events = list(loop.run())
    assert ran == [REMEMBERED] and not [e for e in events if e.get("type") == "hold"]
    assert len(asked) == 2 and asked[1].endswith(agent_audit.REPAIR_NOTE)
    assert receipt_rounds(store, loop) == {"anthropic": ["gate", "final"], "openai": ["gate", "repair", "final"]}
    # One session: the repair went on in it.
    assert audit_sessions(store, loop, "openai") == [("completed", None)]


def test_the_gate_wait_pauses_the_turns_clock(store, stand_in):
    script, loop, ran = gated(store, live={})
    samples = []

    def slow_go(messages):
        deadline = time.monotonic() + 5
        while loop.gate_started is None and time.monotonic() < deadline:
            time.sleep(.01)
        samples.append(loop._turn_elapsed())
        time.sleep(.2)
        samples.append(loop._turn_elapsed())
        return go(messages)
    script.live.update(anthropic=replies(script, "anthropic", go), openai=replies(script, "openai", slow_go))
    list(loop.run())
    assert ran == [REMEMBERED]
    assert samples[1] == pytest.approx(samples[0], abs=1e-6)
    assert loop.gate_paused >= .2 and loop.gate_started is None


class BrowserArgs(LookupArgs):
    action: str = ""
    ref: str = ""


def test_a_browser_click_runs_at_once_while_the_reviewers_follow_it_live(store):
    """A click does not wait for a gate round: reviewers
    that would halt one before it ran never get asked."""
    ran = []
    script = Audit(tool_steps=1, step_tools={0: "browser"}, step_args={0: {"action": "click", "ref": "e4"}},
                   live={})
    script.live.update(anthropic=replies(script, "anthropic", halt), openai=replies(script, "openai", halt))
    loop = audit_loop(store, script)

    def run(args, *, cancellation):
        ran.append(args.action)
        return {"action": args.action, "page": "done"}
    loop.registry = ToolRegistry([*loop.registry.tools.values(),
                                  ReadOnlyTool("browser", "Use the browser.", BrowserArgs, run)],
                                 argument_limit=loop.registry.argument_limit)
    events = list(loop.run())
    assert ran == ["click"] and not getattr(script, "gate_searches", {})
    assert not [e for e in events if e.get("type") == "hold"]
    names = [entry["name"] for entry, _ in loop.work_log.entries_after(0) if entry["kind"] == "app"]
    assert "checked" not in names


def read_args(url):
    return {"url": url}


def test_a_page_of_its_own_choice_is_read_at_once(store, monkeypatch):
    """GPT-6.1 Terra searched 15 times in four days and kept 1 source: its
    provider sends no hits to the app, so a read_source bound to the hits
    would refuse what it found. It reads any public page while reviewers
    follow the work, without a gate round first."""
    from test_agent_web_fetch import PAGE, fake_fetch
    from app.services.agent_read_source import LABEL_CHOSEN, LABEL_SEARCH
    monkeypatch.delenv("AGENT_READ_SOURCES", raising=False)
    fetched = fake_fetch(monkeypatch)
    found, chosen = "https://www.toureiffel.paris/en", "https://de.wikipedia.org/wiki/Eiffelturm"
    script = Audit(tool_steps=2, step_tools={0: "read_source", 1: "read_source"},
                   step_args={0: read_args(found), 1: read_args(chosen)}, live={})
    script.live.update(anthropic=replies(script, "anthropic", halt), openai=replies(script, "openai", halt))
    loop = audit_loop(store, script)
    events = list(loop.run())
    results = [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"]
    assert [r["status"] for r in results] == ["completed", "completed"]
    assert results[0]["cited_by"] == [LABEL_SEARCH] and results[1]["cited_by"] == [LABEL_CHOSEN]
    assert results[1]["untrusted_page_text"] == PAGE and len(fetched) == 2
    assert not getattr(script, "gate_searches", {})
    assert not [e for e in events if e.get("type") == "hold"]


# --- A memory change never waits ---------------------------------------------------

def test_a_memory_change_never_waits_for_the_reviewers():
    """Not even with outside content in view: the agent decides what to
    keep, the user sees and can undo every change."""
    change = call("update_memory", changes=[{"op": "add", "text": "Likes towers."}])
    assert outward(change) is None
    assert outward(call("read_settings")) is None


MEMORY_TEXT = "Is planning a trip to the Eiffel Tower."
MEMORY_CHANGE = {"op": "add", "text": MEMORY_TEXT}


def remembering(store, *, live, reviewers=True):
    """A turn whose first step searched (every scripted step does) and saves
    a memory with it, with a page in view too (as after read_source).
    ``reviewers=False``: they never start (agent_reviewers.InertAnswerAudit)."""
    from test_agent_memory import repo, set_profile
    set_profile(store.db, auto_memory=True)
    script = Audit(tool_steps=1, step_tools={0: "update_memory"}, step_args={0: {"changes": [MEMORY_CHANGE]}},
                   live=live)
    loop = audit_loop(store, script, memory=repo(store).snapshot(UID))
    loop.outside_in_view = True
    if not reviewers:
        without_reviewers(loop)
    return script, loop, lambda: [item["text"] for item in repo(store).get(UID)[0]]


@pytest.mark.parametrize("reviewers", [True, False])
def test_a_memory_change_with_outside_content_in_view_runs_at_once(store, reviewers):
    """The agent searches in nearly every first step: a lock after it would
    keep an opted-in account's memory empty."""
    script, loop, memories = remembering(store, live={}, reviewers=reviewers)
    if reviewers:
        script.live.update(anthropic=replies(script, "anthropic", halt), openai=replies(script, "openai", halt))
    events = list(loop.run())
    assert memories() == [MEMORY_TEXT]
    assert not [e for e in events if e.get("type") == "hold" and (e.get("hold") or {}).get("gate")]
    assert not any("Before it runs:" in str(m.get("content")) for m in script.prompts.get("openai", []))
    assert saved(store, loop)["status"] == "completed"


def test_a_memory_needs_no_quote(store):
    """The model decides what is worth remembering, also a preference the
    user never put into words; the user sees and can undo every change."""
    from test_agent_memory import repo, set_profile
    set_profile(store.db, auto_memory=True)
    preference = {"op": "add", "text": "Prefers short answers."}
    script = Audit(search=False, tool_steps=1, step_tools={0: "update_memory"},
                   step_args={0: {"changes": [preference]}}, live={})
    loop = audit_loop(store, script, memory=repo(store).snapshot(UID))
    list(loop.run())
    assert [item["text"] for item in repo(store).get(UID)[0]] == ["Prefers short answers."]
    tool = next(t for t in loop.registry.tools.values() if t.name == "update_memory")
    assert "evidence" not in json.dumps(tool.schema()) and "can undo it" in tool.description


def test_a_request_for_a_domain_opens_no_gate(store):
    """A model that still calls request_domain (gone) gets its refusal
    ("unknown tool") at once: no paid gate round, and no card whose yes
    would end in that refusal."""
    script = Audit(tool_steps=1, step_tools={0: "request_domain"},
                   step_args={0: {"domain": "api.example.com", "reason": "Docs"}})
    script.live.update(anthropic=replies(script, "anthropic", halt), openai=replies(script, "openai", halt))
    loop = audit_loop(store, script)
    assert "request_domain" not in loop.registry.tools
    events = list(loop.run())
    assert not getattr(script, "gate_searches", {})
    assert not [e for e in events if e.get("type") == "hold"]
    [result] = [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"]
    assert "unknown tool" in result["error"]
    assert saved(store, loop)["status"] == "completed"
