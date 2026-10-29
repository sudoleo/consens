"""ask_user and the takeover wait (agent_ask.py, since 2026-10-29): the run
pauses on the user's own card. Handing the browser back answers a browser
card, allow and deny a confirmation, a message on the card is the user's
answer; the agent hears only that. While the user took over the browser on
their own, a call into the workspace waits on a card instead of failing
after 120 s. Without an answer the agent finishes instead of stopping.
"""
import json
import threading
import time
from types import SimpleNamespace

import pytest

from app.services import agent_ask, agent_delegation, agent_workspace
from app.services.agent_tools import ReadOnlyTool, ToolRegistry
from test_agent_audit import ANSWER, Audit, LookupArgs, audit_loop, decide_when_held, saved
from test_agent_runs import UID, store  # noqa: F401  (fixture)

REQUEST = "Bitte melde dich bei der Post an, dann mache ich weiter."


@pytest.fixture(autouse=True)
def quick_poll(monkeypatch):
    monkeypatch.setattr(agent_ask, "HANDBACK_POLL_SECONDS", 0)


class Browser:
    """Who has the workspace's browser, as control_state reads it."""

    def __init__(self, monkeypatch, holding=False):
        self.holding = holding
        self.returned_at = 0.0
        self.reads = 0
        monkeypatch.setattr(agent_workspace, "control_state", self.read)

    def read(self, db, uid, now=None):
        self.reads += 1
        return self.holding, self.returned_at

    def take_over(self):
        self.holding = True

    def hand_back(self):
        self.holding, self.returned_at = False, time.time()


class BrowserArgs(LookupArgs):
    action: str = ""


def asking(store, *, args, then_browser=False):
    """An audit turn whose first step calls ask_user with ``args`` (and, with
    ``then_browser``, whose second calls a fake browser); then it answers."""
    steps = {0: "ask_user", **({1: "browser"} if then_browser else {})}
    step_args = {0: args, **({1: {"action": "read"}} if then_browser else {})}
    script = Audit(tool_steps=len(steps), step_tools=steps, step_args=step_args, live={})
    loop = audit_loop(store, script)
    ran = []

    def browse(arguments, *, cancellation):
        ran.append(arguments.action)
        return {"action": arguments.action, "page": "Signed in."}
    ask = agent_ask.AskTools(SimpleNamespace(loop=loop)).tools()
    loop.registry = ToolRegistry([*loop.registry.tools.values(), *ask,
                                  ReadOnlyTool("browser", "Use the browser.", BrowserArgs, browse)],
                                 argument_limit=loop.registry.argument_limit)
    loop.workspace_tools = frozenset({"browser"})
    return script, loop, ran


def results(loop):
    return [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"]


def holds(events):
    return [e["hold"] for e in events if e.get("type") == "hold" and e.get("hold")]


def when_held(loop, then):
    """Runs ``then(hold)`` once the run waits on a card."""
    def watch():
        while loop.hold is None:
            time.sleep(.01)
        time.sleep(.05)
        then(loop.hold)
    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    return thread


def test_handing_the_browser_back_lets_the_agent_go_on(store, monkeypatch):
    browser = Browser(monkeypatch)
    script, loop, ran = asking(store, args={"request": REQUEST, "browser": True}, then_browser=True)
    taken = []

    def take_over_and_hand_back(hold):
        taken.append(hold)
        # Quicker than the run looks: the noted hand-back still counts.
        browser.take_over()
        browser.hand_back()
    watcher = when_held(loop, take_over_and_hand_back)
    events = list(loop.run())
    watcher.join(5)
    card = holds(events)
    assert len(card) == 1 and card[0]["ask"] == "browser" and card[0]["request"] == REQUEST
    assert card[0]["kind"] == "ask" and card[0]["reviewer"] == "" and card[0]["timeout_seconds"] == 1800
    assert results(loop)[0] == agent_ask.ANSWERS[("browser", "handed_back")]
    # The browser call after it ran: the user had handed it back.
    assert ran == ["read"]
    ended = [e for e in events if e.get("type") == "activity" and e.get("kind") == "hold"]
    assert ended[0]["ask"] == "browser" and ended[0]["request"] == REQUEST and ended[-1]["state"] == "handed_back"
    said = [content for entry, content in loop.work_log.entries_after(0) if entry["kind"] == "app"]
    assert f"The agent asks the user to act in the browser: {REQUEST}" in said
    assert "The user handed the browser back." in said
    assert saved(store, loop)["status"] == "completed"


def test_a_browser_card_waits_until_the_user_had_the_browser(store, monkeypatch):
    """Not taken over yet is not handed back: the card stays until they had it."""
    browser = Browser(monkeypatch)
    script, loop, ran = asking(store, args={"request": REQUEST, "browser": True})
    seen = []

    def later(hold):
        time.sleep(.5)
        seen.append(loop.hold is not None)
        # Seen to have it, then not, without a noted hand-back (the
        # takeover ran out when the view closed).
        browser.take_over()
        time.sleep(.5)
        browser.holding = False
    watcher = when_held(loop, later)
    list(loop.run())
    watcher.join(5)
    assert seen == [True] and browser.reads > 2
    assert results(loop)[0]["status"] == "handed_back"


@pytest.mark.parametrize("decision,status", [("continue", "allowed"), ("deny", "declined")])
def test_a_confirmation_is_allowed_or_declined_on_the_card(store, monkeypatch, decision, status):
    browser = Browser(monkeypatch)
    script, loop, ran = asking(store, args={"request": "Soll ich die Nachricht an Anna senden?"})
    waiter = decide_when_held(loop, store, decision)
    events = list(loop.run())
    waiter.join(5)
    card = holds(events)
    assert len(card) == 1 and card[0]["ask"] == "confirm"
    assert results(loop) == [agent_ask.ANSWERS[("confirm", decision)]] and results(loop)[0]["status"] == status
    # A confirmation never reads who has the browser.
    assert browser.reads == 0
    said = [content for entry, content in loop.work_log.entries_after(0) if entry["kind"] == "app"]
    assert ("The user allowed it." if decision == "continue" else "The user did not allow it.") in said
    assert saved(store, loop)["status"] == "completed"


def test_a_message_on_the_card_is_the_users_answer(store, monkeypatch):
    Browser(monkeypatch)
    script, loop, ran = asking(store, args={"request": REQUEST, "browser": True}, then_browser=False)
    waiter = decide_when_held(loop, store, "steer", "Ich habe kein Konto dort.")
    list(loop.run())
    waiter.join(5)
    assert results(loop) == [agent_ask.ANSWERS[("browser", "steer")]]
    notes = [m for m in loop.messages if m.get("role") == "user" and "Ich habe kein Konto dort." in str(m["content"])]
    assert len(notes) == 1


def test_without_an_answer_the_agent_finishes_instead_of_stopping(store, monkeypatch):
    Browser(monkeypatch)
    script, loop, ran = asking(store, args={"request": "Darf ich bestellen?"})
    started = time.monotonic()
    clock = {"skew": 0.0}
    loop.clock = lambda: time.monotonic() + clock["skew"]
    watcher = when_held(loop, lambda hold: clock.update(skew=agent_delegation.HOLD_TIMEOUT_SECONDS + 1))
    events = list(loop.run())
    watcher.join(5)
    assert time.monotonic() - started < 10
    assert results(loop) == [agent_ask.ANSWERS[("confirm", "timeout")]]
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert [e["state"] for e in events if e.get("type") == "activity" and e.get("kind") == "hold"][-1] == "timeout"


def test_an_ask_with_invalid_arguments_needs_no_card(store, monkeypatch):
    Browser(monkeypatch)
    script, loop, ran = asking(store, args={"request": "x"})
    events = list(loop.run())
    assert not holds(events)
    assert "error" in results(loop)[0]


def test_a_call_into_the_workspace_waits_while_the_user_has_the_browser(store, monkeypatch):
    """Max, 2026-10-29: he had taken over, the agent waited 120 s per call
    and then gave up. Now the call waits on a card until he hands it back."""
    browser = Browser(monkeypatch, holding=True)
    script = Audit(tool_steps=1, step_tools={0: "browser"}, step_args={0: {"action": "read"}}, live={})
    loop = audit_loop(store, script)
    ran = []

    def browse(arguments, *, cancellation):
        ran.append((arguments.action, browser.holding))
        return {"action": arguments.action, "page": "done"}
    loop.registry = ToolRegistry([*loop.registry.tools.values(),
                                  ReadOnlyTool("browser", "Use the browser.", BrowserArgs, browse)],
                                 argument_limit=loop.registry.argument_limit)
    loop.workspace_tools = frozenset({"browser"})
    watcher = when_held(loop, lambda hold: browser.hand_back())
    events = list(loop.run())
    watcher.join(5)
    card = holds(events)
    assert len(card) == 1 and card[0]["ask"] == "takeover" and card[0]["request"] == ""
    # It ran once the browser was back, never while the user had it.
    assert ran == [("read", False)]
    said = [content for entry, content in loop.work_log.entries_after(0) if entry["kind"] == "app"]
    assert "The user has the browser: the agent waits until they hand it back." in said


def test_a_takeover_never_handed_back_leaves_the_call_unrun(store, monkeypatch):
    Browser(monkeypatch, holding=True)
    script = Audit(tool_steps=1, step_tools={0: "browser"}, step_args={0: {"action": "read"}}, live={})
    loop = audit_loop(store, script)
    ran = []
    loop.registry = ToolRegistry([*loop.registry.tools.values(), ReadOnlyTool(
        "browser", "Use the browser.", BrowserArgs, lambda arguments, *, cancellation: ran.append(1))],
        argument_limit=loop.registry.argument_limit)
    loop.workspace_tools = frozenset({"browser"})
    clock = {"skew": 0.0}
    loop.clock = lambda: time.monotonic() + clock["skew"]
    watcher = when_held(loop, lambda hold: clock.update(skew=agent_delegation.HOLD_TIMEOUT_SECONDS + 1))
    list(loop.run())
    watcher.join(5)
    assert ran == []
    assert results(loop) == [{"error": agent_ask.TAKEOVER_TIMEOUT}]
    assert saved(store, loop)["status"] == "completed"


def test_a_reviewers_halt_during_the_users_card_comes_before_the_next_call(store, monkeypatch):
    """One hold at a time: a reviewer's halt that comes while the user's own
    card is open waits for it, then holds the agent's next call."""
    browser = Browser(monkeypatch)
    script, loop, ran = asking(store, args={"request": REQUEST, "browser": True}, then_browser=True)
    halt = {"reviewer": "GPT-5.4 mini", "provider": "openai", "kind": "injection", "reason": "Obeys the page.",
            "entry": 1, "step": "", "step_name": "", "step_kind": "", "step_source": ""}
    decided = []

    def halt_then_hand_back(hold):
        assert loop.request_hold(halt) is False
        browser.take_over()
        browser.hand_back()
        while loop.hold is None or not loop.hold.get("reviewer"):
            time.sleep(.01)
        decided.append(loop.hold["reviewer"])
        assert ran == []
        store.decide_hold(UID, loop.chat_id, loop.turn_id, loop.hold["id"], "continue")
        loop._receive_hold(store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict())
    watcher = when_held(loop, halt_then_hand_back)
    events = list(loop.run())
    watcher.join(5)
    assert decided == ["GPT-5.4 mini"]
    assert [h.get("ask") or h["kind"] for h in holds(events)] == ["browser", "injection"]
    assert ran == ["read"]


def test_the_tool_is_offered_with_the_workspace_and_returns_only_the_answer():
    loop = SimpleNamespace(ask_answer={"status": "allowed", "note": "The user allowed it."})
    tool = agent_ask.AskTools(SimpleNamespace(loop=loop)).tools()[0]
    assert tool.name == "ask_user" and "browser" in json.dumps(tool.schema())
    assert tool.execute(agent_ask.AskUserArgs(request="Darf ich?"), cancellation=None)["status"] == "allowed"
    assert loop.ask_answer is None
    with pytest.raises(ValueError):
        tool.execute(agent_ask.AskUserArgs(request="Darf ich?"), cancellation=None)
    assert tool.activity(agent_ask.AskUserArgs(request="Darf ich?", browser=True), {"status": "handed_back"}) == {
        "request": "Darf ich?", "ask": "browser", "ask_status": "handed_back"}
