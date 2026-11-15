"""Messages into a running response, as in Claude Code: the
user presses Enter while the agent works, the message lands on the run's root
receipt (routers/agent.py add_agent_note, AgentSessionStore.add_user_note),
the watcher reads it with the lease check, and the agent gets it before its
next step. "Send now" (``now``) breaks off what runs for it instead
(DelegationLoop._hurry). Stop stays Stop. No provider and no VM provider is
called.
"""
import json
import threading
import time

import pytest

from app.services import agent_delegation
from app.services.agent_delegation import CALL_AFTER_MESSAGE, NOTES_UNREAD, USER_NOTE_OPEN
from app.services.agent_sessions import USER_NOTES_MAX
from app.services.chat_store import TurnStatusConflict, _idempotent_turn_id
from app.services.llm.agent_client import AgentCompletion, measured_usage
from app.services.llm.provider_runtime import ProviderCancelled
from test_agent_long_runs import LongAgent
from test_agent_runs import AUTH, UID, api, pending, store, priced  # noqa: F401  (fixtures)
from test_agent_vm import ANSWER, _FakeBackend, _admin_allowance, fake_vm, vm_loop  # noqa: F401  (fixtures)


def running(store, *, vm="on", request_id="req-1"):
    """A pending turn whose run has claimed its first step."""
    chat, turn = pending(store, request_id=request_id)
    assert turn["id"] == _idempotent_turn_id(chat, request_id)
    store._transaction(lambda tx: tx.update(store._turn_ref(UID, chat, turn["id"]),
                                            {"agent_settings": {"agent_preferences": {"vm": vm}}}))
    loop = vm_loop(store, LongAgent(), chat_id=chat, request_id=request_id)
    store.claim(UID, chat, turn["id"], loop.model, policy=loop.policy.snapshot(), run_token=loop.run_token,
                reservation=(1, priced(1)))
    return chat, turn["id"], loop


def test_a_message_goes_onto_the_running_response(api):
    client, store, _ = api
    chat, turn_id, loop = running(store)
    url = f"/agent/chats/{chat}/requests/req-1/notes"
    response = client.post(url, json={"text": "  Use pytest, not unittest.  "}, headers=AUTH)
    assert response.status_code == 200 and response.json()["status"] == "added"
    root = store.check_delegation(UID, chat, turn_id, loop.run_token)
    [note] = root["user_notes"]
    assert note["text"] == "Use pytest, not unittest." and note["id"] == response.json()["id"]
    assert client.post(url, json={"text": "   "}, headers=AUTH).status_code == 422
    assert client.post(url, json={"text": "x" * 4001}, headers=AUTH).status_code == 422
    # At most USER_NOTES_MAX per response.
    for _ in range(USER_NOTES_MAX - 1):
        assert client.post(url, json={"text": "more"}, headers=AUTH).status_code == 200
    refused = client.post(url, json={"text": "one too many"}, headers=AUTH)
    assert refused.status_code == 409 and refused.json()["code"] == "not_running"


def test_a_message_reaches_a_run_of_this_process_at_once(api):
    """A-T4: the run has it when the request answers, not with its watcher's
    next look; that look finds it on the root again and takes it once."""
    from app.services.agent_background import agent_background
    client, store, _ = api
    chat, turn_id, loop = running(store)
    release = threading.Event()
    agent_background.start(uid=UID, chat_id=chat, request_id="req-1", turn_id=turn_id, target=release.wait,
                           cancel=release.set, interrupt=lambda reason: release.set(), loop=loop)
    try:
        response = client.post(f"/agent/chats/{chat}/requests/req-1/notes", json={"text": "Run the tests."},
                               headers=AUTH)
        assert response.status_code == 200
        assert [(note["id"], note["text"]) for note in loop.notes] == [(response.json()["id"], "Run the tests.")]
        loop._receive_notes(store.check_delegation(UID, chat, turn_id, loop.run_token))
        assert len(loop.notes) == 1
    finally:
        release.set()


def test_every_running_response_takes_messages(api):
    """Not only one with the workspace: a short search reads them as well."""
    client, store, _ = api
    chat, turn_id, loop = running(store, vm="off")
    added = client.post(f"/agent/chats/{chat}/requests/req-1/notes", json={"text": "hi"}, headers=AUTH)
    assert added.status_code == 200
    assert [note["text"] for note in store.check_delegation(UID, chat, turn_id, loop.run_token)["user_notes"]] == ["hi"]
    gone = client.post(f"/agent/chats/{chat}/requests/unknown/notes", json={"text": "hi"}, headers=AUTH)
    assert gone.status_code == 409 and gone.json()["code"] == "not_running"
    chat, turn_id, _ = running(store, request_id="req-2")
    store.stop_delegation(UID, chat, turn_id)
    with pytest.raises(TurnStatusConflict):
        store.add_user_note(UID, chat, turn_id, "too late")


def test_the_agent_reads_the_message_before_its_next_step(store, fake_vm):
    script = LongAgent([[("vm_exec", {"command": "make"})], [("vm_exec", {"command": "make test"})]])
    loop = vm_loop(store, script)
    original = script.factory

    def factory():
        completion = original()
        stream = completion.stream

        def first_step_hears_the_user(**kwargs):
            if completion.step_id == "completion:0":
                # What the watcher does when the root carries a new message.
                loop._receive_notes({"user_notes": [{"id": "n1", "text": "Run the tests too."}]})
                loop._receive_notes({"user_notes": [{"id": "n1", "text": "Run the tests too."}]})
            return stream(**kwargs)
        completion.stream = first_step_hears_the_user
        return completion
    loop.factory = factory
    events = list(loop.run())
    second = script.seen[1]
    notes = [m for m in second if m["role"] == "user" and str(m["content"]).startswith(USER_NOTE_OPEN)]
    assert [m["content"] for m in notes] == [f"{USER_NOTE_OPEN}\nRun the tests too."]
    # After the first step's results and the app's line of facts about the
    # message (audit L3), before the second step: once.
    assert second[-1] == notes[0] and second[-3]["role"] == "tool"
    assert second[-2]["content"].startswith(agent_delegation.PROGRESS_OPEN)
    shown = [e for e in events if e.get("type") == "activity" and e.get("from_user")]
    assert len(shown) == 1 and shown[0]["text"] == "Run the tests too."
    # The work log: the user's own words.
    entry = next(e for e, t in loop.work_log.entries_after(0) if e["kind"] == "context" and t.startswith(USER_NOTE_OPEN))
    assert entry["data"] == "user"


def test_a_message_after_the_answer_is_said_to_be_unread(store, fake_vm):
    """The line says what happened, not what to do: the page sends a waiting
    message after the response itself, or puts it back into the field
    (flushQueue in static/js/agent-chat.js)."""
    assert "again" not in NOTES_UNREAD
    script = LongAgent()
    loop = vm_loop(store, script)
    original = script.factory

    def factory():
        completion = original()
        stream = completion.stream

        def answer_step(**kwargs):
            loop._receive_notes({"user_notes": [{"id": "late", "text": "Also add docs."}]})
            return stream(**kwargs)
        completion.stream = answer_step
        return completion
    loop.factory = factory
    list(loop.run())
    activity = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_activity"]
    assert any(e.get("text") == NOTES_UNREAD for e in activity)
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["consensus"] == ANSWER


# --- "Send now": Claude Code's interrupt -------------------------------------------

def test_send_now_marks_the_message_and_breaks_off_the_run_once(api):
    """On a message already sent (its row's "Send now") or with the message
    itself (Ctrl+Enter): saved on the root, where the watcher would find it
    too, and handed to the run of this process at once."""
    from app.services.agent_background import agent_background
    client, store, _ = api
    chat, turn_id, loop = running(store, vm="off")
    hurried = []
    loop._hurry = lambda: hurried.append(loop.hurried)
    release = threading.Event()
    agent_background.start(uid=UID, chat_id=chat, request_id="req-1", turn_id=turn_id, target=release.wait,
                           cancel=release.set, interrupt=lambda reason: release.set(), loop=loop)
    url = f"/agent/chats/{chat}/requests/req-1/notes"
    try:
        note_id = client.post(url, json={"text": "Use pytest."}, headers=AUTH).json()["id"]
        assert hurried == []
        response = client.post(f"{url}/{note_id}/now", headers=AUTH)
        assert response.status_code == 200 and response.json()["status"] == "now"
        root = store.check_delegation(UID, chat, turn_id, loop.run_token)
        assert root["user_notes"][0]["now"] is True and hurried == [True]
        # The watcher's next look finds the same: nothing breaks off again.
        loop._receive_notes(root)
        assert hurried == [True]
        # The agent read it: the run goes on as before.
        loop._take_notes("completion:1")
        assert loop.hurried is False
        assert client.post(url, json={"text": "Stop, use the 2026 figures.", "now": True}, headers=AUTH).status_code == 200
        assert hurried == [True, True]
        assert client.post(f"{url}/{'f' * 12}/now", headers=AUTH).status_code == 404
        assert client.post(f"{url}/not-a-note/now", headers=AUTH).status_code == 404
    finally:
        release.set()
    store.stop_delegation(UID, chat, turn_id)
    ended = client.post(f"{url}/{note_id}/now", headers=AUTH)
    assert ended.status_code == 409 and ended.json()["code"] == "not_running"


def test_send_now_on_a_message_already_read_breaks_off_nothing(store, fake_vm):
    loop = vm_loop(store, LongAgent())
    hurried = []
    loop._hurry = lambda: hurried.append(True)
    loop._receive_notes({"user_notes": [{"id": "n1", "text": "Run the tests too."}]})
    loop._take_notes("completion:1")
    loop._receive_notes({"user_notes": [{"id": "n1", "text": "Run the tests too.", "now": True}]})
    assert hurried == [] and loop.hurried is False


def _first_step(script, loop, step):
    """``script``'s completions, with ``step`` (a generator function taking
    the completion) as the agent's first step."""
    original = script.factory

    def factory():
        completion = original()
        stream = completion.stream

        def streamed(**kwargs):
            if completion.step_id == "completion:0":
                yield from step(completion)
                return
            yield from stream(**kwargs)
        completion.stream = streamed
        return completion
    loop.factory = factory


def test_a_message_sent_now_breaks_off_the_answer_as_it_streams(store, fake_vm):
    """The agent writes its answer; the user sends a message now: the text
    goes back, and the agent's next step has the message, as after a
    reviewer's halt (_past_halts). The turn goes on instead of ending."""
    script = LongAgent()
    loop = vm_loop(store, script)
    draft = "A long first draft of the answer. " * 20

    def answer(completion):
        completion.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001},
                                          loop.model)
        completion.text = draft
        yield {"type": "delta", "text": draft}
        loop._receive_notes({"user_notes": [{"id": "n1", "text": "Answer in German.", "now": True}]})
        completion.text += "More."
        yield {"type": "delta", "text": "More."}
        raise AssertionError("the step reads on after the user's message")
    _first_step(script, loop, answer)
    events = list(loop.run())
    [after] = script.seen
    assert after[-1] == {"role": "user", "content": f"{USER_NOTE_OPEN}\nAnswer in German."}
    assert not any(draft in str(message.get("content")) for message in after)
    shown = [e for e in events if e.get("type") == "activity" and e.get("from_user")]
    assert [e["text"] for e in shown] == ["Answer in German."]
    turn = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert turn["consensus"] == ANSWER and turn["status"] == "completed"
    entries = loop.work_log.entries_after(0)
    assert any(e["kind"] == "app" and e["name"] == "retract" and t == draft for e, t in entries)
    [first] = [json.loads(t) for e, t in entries if e["kind"] == "step" and e.get("step") == "completion:0"]
    assert first["status"] == "cancelled"


def test_a_message_sent_now_ends_the_running_command_and_the_batchs_later_calls(store, fake_vm, monkeypatch):
    script = LongAgent([[("vm_exec", {"command": "sleep 600"}), ("vm_exec", {"command": "make"})]])
    loop = vm_loop(store, script)
    plain = _FakeBackend.exec

    def exec(backend, name, command, *, cwd, timeout, on_output, cancellation, agent=True):
        if command != "sleep 600":
            return plain(backend, name, command, cwd=cwd, timeout=timeout, on_output=on_output,
                         cancellation=cancellation, agent=agent)
        on_output("stdout", b"waiting\n")
        loop._receive_notes({"user_notes": [{"id": "n1", "text": "Skip the wait.", "now": True}]})
        deadline = time.monotonic() + 5
        while not cancellation.cancelled and time.monotonic() < deadline:
            time.sleep(.01)
        raise ProviderCancelled("stopped")
    monkeypatch.setattr(_FakeBackend, "exec", exec)
    list(loop.run())
    after = script.seen[1]
    results = [json.loads(m["content"]) for m in after if m["role"] == "tool"]
    assert results[0]["stopped"] is True and results[0]["note"] == "The user stopped this command before it finished."
    assert results[1] == {"error": CALL_AFTER_MESSAGE}
    assert after[-1] == {"role": "user", "content": f"{USER_NOTE_OPEN}\nSkip the wait."}
    assert not [call for call in fake_vm.calls if call[0] == "exec" and call[2] == "make"]
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["consensus"] == ANSWER


def test_a_message_sent_now_after_the_answer_stands_breaks_off_nothing(store, fake_vm):
    """Once the answer is fixed the run takes no more steps: nothing breaks
    off, and the page sends the message as the next one (NOTES_UNREAD)."""
    loop = vm_loop(store, LongAgent())
    loop.answer_fixed = True
    loop.step_halt = halt = type("Halt", (), {"cancelled": False, "cancel": lambda self: setattr(self, "cancelled", True)})()
    loop._receive_notes({"user_notes": [{"id": "late", "text": "Also add docs.", "now": True}]})
    assert halt.cancelled is False
