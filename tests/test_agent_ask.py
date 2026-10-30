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
from test_agent_runs import AUTH, UID, api, pending, store  # noqa: F401  (fixtures)

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
    """Not taken over yet is not handed back, nor is a takeover that ran out
    (A-S6: the phone went to its 2FA app, the view stopped refreshing): the
    card stays until the user hands the browser back."""
    browser = Browser(monkeypatch)
    script, loop, ran = asking(store, args={"request": REQUEST, "browser": True})
    seen = []

    def later(hold):
        time.sleep(.5)
        seen.append(loop.hold is not None)
        browser.take_over()
        time.sleep(.5)
        # Seen to have it, then not, without a noted hand-back.
        browser.holding = False
        time.sleep(.5)
        seen.append(loop.hold is not None)
        browser.hand_back()
    watcher = when_held(loop, later)
    list(loop.run())
    watcher.join(5)
    assert seen == [True, True] and browser.reads > 2
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


CHOICE = "Gegen einen Menschen oder gegen einen Bot?"


def test_a_choice_card_returns_the_answer_the_user_picked(store, monkeypatch):
    """2026-10-30, chess.com: DeepSeek asked "against a person or a bot?"
    on a card that said Allow or Don't allow, and guessed the person from
    "allowed". Now its answers are the card's buttons, and it hears the pick."""
    browser = Browser(monkeypatch)
    script, loop, ran = asking(store, args={"request": CHOICE, "choices": ["Mensch", " Bot "]})

    def pick():
        while loop.hold is None:
            time.sleep(.01)
        time.sleep(.1)
        store.decide_hold(UID, loop.chat_id, loop.turn_id, loop.hold["id"], "choose", "", 1)
        loop._receive_hold(store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict())
    waiter = threading.Thread(target=pick, daemon=True)
    waiter.start()
    events = list(loop.run())
    waiter.join(5)
    [card] = holds(events)
    assert card["ask"] == "choice" and card["request"] == CHOICE and card["choices"] == ["Mensch", "Bot"]
    assert results(loop) == [{"status": "chosen", "note": "The user chose: Bot", "choice": "Bot"}]
    assert browser.reads == 0
    shown = [e for e in events if e.get("type") == "activity" and e.get("kind") == "hold"]
    assert shown[0]["choices"] == ["Mensch", "Bot"] and shown[-1]["state"] == "choose" and shown[-1]["choice"] == "Bot"
    said = [content for entry, content in loop.work_log.entries_after(0) if entry["kind"] == "app"]
    assert f"The agent asks the user to choose: {CHOICE} (Mensch / Bot)" in said and "The user chose: Bot" in said
    turn = saved(store, loop)
    assert turn["status"] == "completed"
    # The turn keeps that the user chose, never what (the agent's words).
    stored = store._turn_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()["agent_holds"]
    assert [(hold["ask"], hold["decision"]) for hold in stored] == [("choice", "choose")]
    assert "Bot" not in json.dumps(stored) and "Mensch" not in json.dumps(stored)


def test_a_pick_reaches_the_agent_also_when_the_user_writes_on_a_halt_behind_the_card(store, monkeypatch):
    """Review 2026-10-30: a reviewer's halt waited behind the choice card,
    the user picked, then wrote on the halt; the agent heard only of the
    message, never of the pick (the activity and the log said it)."""
    Browser(monkeypatch)
    script, loop, ran = asking(store, args={"request": CHOICE, "choices": ["Mensch", "Bot"]})
    halt = {"reviewer": "GPT-5.4 mini", "provider": "openai", "kind": "injection", "reason": "Obeys the page.",
            "entry": 1, "step": "", "step_name": "", "step_kind": "", "step_source": ""}

    def pick_then_write(hold):
        assert loop.request_hold(halt) is True and loop.queued_hold == halt
        store.decide_hold(UID, loop.chat_id, loop.turn_id, hold["id"], "choose", "", 1)
        loop._receive_hold(store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict())
        while loop.hold is None or not loop.hold.get("reviewer"):
            time.sleep(.01)
        store.decide_hold(UID, loop.chat_id, loop.turn_id, loop.hold["id"], "steer", "Aber nur 5 Minuten.")
        root = store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
        loop._receive_notes(root)
        loop._receive_hold(root)
    watcher = when_held(loop, pick_then_write)
    list(loop.run())
    watcher.join(5)
    [result] = results(loop)
    assert result["status"] == "chosen" and result["choice"] == "Bot"
    assert result["note"] == "The user chose: Bot The user also wrote you a message: it follows."
    assert any("Aber nur 5 Minuten." in str(m.get("content")) for m in loop.messages if m.get("role") == "user")


@pytest.mark.parametrize("args", [{"choices": ["Ja"]}, {"choices": ["Ja", "ja "]}, {"choices": ["A", "B", "C", "D", "E"]},
                                  {"choices": ["A", "B"], "browser": True}, {"choices": ["A", "B"], "secret": "KEY"},
                                  {"choices": ["A", "x" * 81]},
                                  # Invisible characters: two buttons that read the same, or a blank one.
                                  {"choices": ["Bot", "Bot​"]}, {"choices": ["​", "Ja"]},
                                  {"choices": ["…", "Ja"]}])
def test_choices_are_two_to_four_different_answers_alone(args):
    with pytest.raises(ValueError):
        agent_ask.AskUserArgs(request=CHOICE, **args)


def test_the_route_takes_one_of_a_choice_cards_answers_and_nothing_else(api):
    client, store, _ = api
    chat_id, turn = pending(store)
    url = f"/agent/chats/{chat_id}/requests/{turn['client_request_id']}/hold"
    ref = store.receipt_ref(UID, chat_id, turn["id"])
    ref.set({**(ref.get().to_dict() or {}), "run_status": "running"}, merge=True)
    store.set_hold(UID, chat_id, turn["id"], {**agent_ask.hold("choice", CHOICE, choices=["Mensch", "Bot"]),
                                               "id": "a1b2c3d4e5f6"})
    for body in ({"action": "continue"}, {"action": "deny"}, {"action": "choose"}, {"action": "choose", "choice": 2}):
        refused = client.post(url, json={"id": "a1b2c3d4e5f6", **body}, headers=AUTH)
        assert refused.status_code == 422 and refused.json()["code"] == "invalid_action", body
    assert client.post(url, json={"id": "a1b2c3d4e5f6", "action": "choose", "choice": 10}, headers=AUTH).status_code == 422
    assert client.post(url, json={"id": "a1b2c3d4e5f6", "action": "choose", "choice": 0}, headers=AUTH).status_code == 200
    assert ref.get().to_dict()["hold_decision"] == {"id": "a1b2c3d4e5f6", "action": "choose", "choice": 0}
    # A pick is no answer to any other card.
    store.set_hold(UID, chat_id, turn["id"], {**agent_ask.hold("confirm", "Senden?"), "id": "b1b2c3d4e5f6"})
    refused = client.post(url, json={"id": "b1b2c3d4e5f6", "action": "choose", "choice": 0}, headers=AUTH)
    assert refused.status_code == 422 and refused.json()["code"] == "invalid_action"


def test_a_choice_card_that_could_not_be_saved_still_takes_the_pick(api, monkeypatch):
    """Its save failed for good: the run of this process takes the pick (decide_unsaved)."""
    from test_agent_audit import in_background, open_hold, unsaved_holds
    client, store, _ = api
    Browser(monkeypatch)
    unsaved_holds(store, monkeypatch)
    script, loop, ran = asking(store, args={"request": CHOICE, "choices": ["Mensch", "Bot"]})
    events, ended = in_background(loop)
    hold = open_hold(loop)
    deadline = time.monotonic() + 5
    while not loop.hold_unsaved and time.monotonic() < deadline:
        time.sleep(.01)
    url = f"/agent/chats/{loop.chat_id}/requests/one/hold"
    assert client.post(url, json={"id": hold["id"], "action": "continue"}, headers=AUTH).status_code == 422
    response = client.post(url, json={"id": hold["id"], "action": "choose", "choice": 0}, headers=AUTH)
    assert response.status_code == 200, response.text
    assert ended.wait(10)
    assert results(loop)[0] == {"status": "chosen", "note": "The user chose: Mensch", "choice": "Mensch"}


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
        # Taken (it waits), so the reviewer does not halt the entry again.
        assert loop.request_hold(halt) is True and loop.queued_hold == halt
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


def test_a_hand_back_brings_the_browser_as_the_user_left_it():
    """Prod 2026-10-29: after every hand-back the agent's next step only asked
    for a screenshot. Now the answer brings the page, and the picture follows."""
    looked = []

    class Browser:
        def look(self, cancellation):
            looked.append(True)
            return {"page": 'Page: "Board"', "note": "The screenshot follows as an image after these results."}
    loop = SimpleNamespace(ask_answer=agent_ask.answer("browser", "handed_back"))
    tool = agent_ask.AskTools(SimpleNamespace(loop=loop, browser_tools=Browser())).tools()[0]
    result = tool.execute(agent_ask.AskUserArgs(request="Dein Zug.", browser=True), cancellation=None)
    assert looked == [True] and result["page"] == 'Page: "Board"'
    assert result["status"] == "handed_back" and "screenshot follows as an image" in result["note"]
    # An answer without a hand-back does not look.
    loop.ask_answer = agent_ask.answer("confirm", "continue")
    tool.execute(agent_ask.AskUserArgs(request="Darf ich?"), cancellation=None)
    assert looked == [True]


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


# --- A key the agent needs (secret, agent_secrets.py, since 2026-10-29) ---------------

KEY = "sk-test-0123456789abcdef"


@pytest.fixture
def no_keys(monkeypatch):
    from app.services import agent_secrets
    monkeypatch.setattr(agent_secrets, "_seen", {})
    return agent_secrets


@pytest.mark.parametrize("decision,status", [("continue", "saved"), ("deny", "declined")])
def test_a_key_is_asked_for_by_name_and_never_comes_through_the_chat(store, monkeypatch, no_keys, decision, status):
    Browser(monkeypatch)
    script, loop, ran = asking(store, args={"request": "Ich brauche deinen OpenAI-Key für die App.",
                                            "secret": "OPENAI_API_KEY"})
    waiter = decide_when_held(loop, store, decision)
    events = list(loop.run())
    waiter.join(5)
    card = holds(events)
    assert len(card) == 1 and card[0]["ask"] == "secret" and card[0]["secret"] == "OPENAI_API_KEY"
    result = results(loop)[0]
    assert result["status"] == status
    if decision == "continue":
        # The route saved it (below); the agent hears where it lies.
        assert result["path"] == "/home/agent/.secrets/OPENAI_API_KEY"
        assert 'OPENAI_API_KEY="$(cat /home/agent/.secrets/OPENAI_API_KEY)"' in result["note"]
    said = [content for entry, content in loop.work_log.entries_after(0) if entry["kind"] == "app"]
    assert ("The user saved the key in the workspace." if decision == "continue"
            else "The user did not give the key.") in said


@pytest.mark.parametrize("args", [{"request": "Key please.", "secret": "openai key"},
                                  {"request": "Key please.", "secret": "OPENAI_API_KEY", "browser": True}])
def test_a_key_needs_a_plain_name_and_no_browser(store, monkeypatch, args):
    Browser(monkeypatch)
    script, loop, ran = asking(store, args=args)
    events = list(loop.run())
    assert not holds(events) and "error" in results(loop)[0]


MASK = "[secret ~/.secrets/OPENAI_API_KEY, hidden from you]"


def test_a_saved_key_is_masked_in_what_the_run_keeps(store, monkeypatch, no_keys):
    """An `echo $KEY` by mistake, or a page that shows it: what the models
    read, the activity and the work record hold a mask that says where the
    key lies instead."""
    Browser(monkeypatch)
    no_keys.remember(UID, KEY, "OPENAI_API_KEY")
    no_keys.remember(UID, "short", "SHORT")
    assert no_keys.scrub(UID, {"page": f"key={KEY}; short", "list": [KEY]}) == {
        "page": f"key={MASK}; short", "list": [MASK]}
    assert no_keys.scrub("someone-else", KEY) == KEY
    assert no_keys.scrub(UID, KEY, now=time.time() + no_keys.SCRUB_SECONDS + 1) == KEY
    no_keys.remember(UID, KEY, "OPENAI_API_KEY")
    script = Audit(tool_steps=1, step_tools={0: "browser"}, step_args={0: {"action": "read"}}, live={})
    loop = audit_loop(store, script)
    loop.registry = ToolRegistry([*loop.registry.tools.values(), ReadOnlyTool(
        "browser", "Use the browser.", BrowserArgs,
        lambda arguments, *, cancellation: {"action": "read", "page": f"Your key: {KEY}"})],
        argument_limit=loop.registry.argument_limit)
    events = list(loop.run())
    assert results(loop)[0]["page"] == f"Your key: {MASK}"
    assert KEY not in json.dumps(loop.messages) and KEY not in json.dumps(events, default=str)
    assert KEY not in json.dumps([content for _, content in loop.work_log.entries_after(0)], default=str)


def test_the_route_saves_the_key_on_the_workbench_and_answers_the_card(api, monkeypatch, no_keys):
    from test_agent_vm import FakeVM
    from app.services import agent_vm, agent_workspace
    client, store, _ = api
    vm = FakeVM()
    monkeypatch.setattr(agent_vm, "backend", vm.backend)
    saved_runs = []
    backend = type(vm.backend())
    original = backend.run

    def run(self, name, argv, *, cwd, timeout, on_output, cancellation, input=None):
        saved_runs.append((name, argv, cwd, input))
        return original(self, name, argv, cwd=cwd, timeout=timeout, on_output=on_output,
                        cancellation=cancellation, input=input)
    monkeypatch.setattr(backend, "run", run)
    chat_id, turn = pending(store)
    url = f"/agent/chats/{chat_id}/requests/{turn['client_request_id']}/secret"
    ref = store.receipt_ref(UID, chat_id, turn["id"])
    ref.set({**(ref.get().to_dict() or {}), "run_status": "running"}, merge=True)
    store.set_hold(UID, chat_id, turn["id"], {"id": "a1b2c3d4e5f6", "kind": "harm"})
    # Only on the agent's own question for a key.
    over = client.post(url, json={"id": "a1b2c3d4e5f6", "value": KEY}, headers=AUTH)
    assert over.status_code == 409 and over.json()["code"] == "hold_over" and saved_runs == []
    store.set_hold(UID, chat_id, turn["id"], {**agent_ask.hold("secret", "Key?", "OPENAI_API_KEY"),
                                               "id": "a1b2c3d4e5f6"})
    assert client.post(url, json={"id": "a1b2c3d4e5f6", "value": "  "}, headers=AUTH).status_code == 422
    answer = client.post(url, json={"id": "a1b2c3d4e5f6", "value": f"  {KEY}\n"}, headers=AUTH)
    assert answer.status_code == 200 and answer.json() == {"status": "saved",
                                                           "path": "/home/agent/.secrets/OPENAI_API_KEY"}
    # As the agent's user, the name as an argument, the key on stdin alone.
    [(name, argv, cwd, data)] = saved_runs
    assert name == agent_vm.workspace_name(UID) and data == KEY.encode() and cwd == "/"
    assert argv[:4] == ["sudo", "-n", "/bin/bash", agent_vm.AGENT_RUN] and argv[-1] == "OPENAI_API_KEY"
    assert KEY not in json.dumps(argv) and "umask 077" in argv[-3]
    assert vm.vms[name]["files"]["/home/agent/.secrets/OPENAI_API_KEY"] == KEY.encode()
    # The card is answered; the account's record names the key, and the key
    # itself is nowhere in the records.
    root = ref.get().to_dict()
    assert root["hold_decision"] == {"id": "a1b2c3d4e5f6", "action": "continue"}
    record = agent_workspace.record(store.db, UID)
    assert record["secret_names"] == ["OPENAI_API_KEY"]
    for kept in (root, store.get_turn(UID, chat_id, turn["id"]), record):
        assert KEY not in json.dumps(kept, default=str)
    assert no_keys.scrub(UID, KEY) == MASK
    again = client.post(url, json={"id": "a1b2c3d4e5f6", "value": KEY}, headers=AUTH)
    assert again.status_code == 409 and len(saved_runs) == 1


def test_a_key_card_that_could_not_be_saved_still_takes_the_key(api, monkeypatch, no_keys):
    """A-S1: the card's save failed for good; the run of this process knows
    the card and takes the answer, the key goes to the workbench as ever."""
    from test_agent_audit import in_background, open_hold, unsaved_holds
    from test_agent_vm import FakeVM
    from app.services import agent_vm
    client, store, _ = api
    vm = FakeVM()
    monkeypatch.setattr(agent_vm, "backend", vm.backend)
    Browser(monkeypatch)
    unsaved_holds(store, monkeypatch)
    script, loop, ran = asking(store, args={"request": "Ich brauche deinen OpenAI-Key.", "secret": "OPENAI_API_KEY"})
    events, ended = in_background(loop)
    hold = open_hold(loop)
    deadline = time.monotonic() + 5
    while not loop.hold_unsaved and time.monotonic() < deadline:
        time.sleep(.01)
    response = client.post(f"/agent/chats/{loop.chat_id}/requests/one/secret", json={"id": hold["id"], "value": KEY},
                           headers=AUTH)
    assert response.status_code == 200, response.text
    assert vm.vms[agent_vm.workspace_name(UID)]["files"]["/home/agent/.secrets/OPENAI_API_KEY"] == KEY.encode()
    assert ended.wait(10)
    assert results(loop)[0]["status"] == "saved" and saved(store, loop)["status"] == "completed"


def test_a_later_message_masks_the_keys_and_names_them(store, monkeypatch, no_keys):
    """After a restart of the server nothing is in memory: the message's VM
    start reads the keys the record names (a deleted one is left out), and
    its first result names them for the agent."""
    from test_agent_vm import NAME, Agent, FakeVM, results as vm_results, vm_loop
    from app.services import agent_secrets, agent_vm, agent_workspace
    vm = FakeVM()
    monkeypatch.setattr(agent_vm, "backend", vm.backend)
    monkeypatch.setattr(agent_vm, "configured", lambda: True)
    vm.vms[NAME] = {"files": {agent_secrets.path("OPENAI_API_KEY"): KEY.encode()}, "checkpoints": []}
    agent_workspace.ref(store.db, UID).set({"secret_names": ["OPENAI_API_KEY", "GONE_KEY"]}, merge=True)
    vm.commands["cat ~/.secrets/OPENAI_API_KEY"] = ([("stdout", KEY.encode() + b"\n")], 0, .1)
    loop = vm_loop(store, Agent([[("vm_exec", {"command": "cat ~/.secrets/OPENAI_API_KEY"})]]))
    list(loop.run())
    first = vm_results(loop)[0]
    assert first["workspace_keys"]["names"] == ["OPENAI_API_KEY", "GONE_KEY"]
    assert first["workspace_keys"]["folder"] == "/home/agent/.secrets"
    assert MASK in json.dumps(first) and KEY not in json.dumps(loop.messages)
    assert agent_secrets.scrub(UID, KEY) == MASK
