"""Messages into a running response (since 2026-10-26, with Agent VM): the
user presses Enter while the agent works, the message lands on the run's root
receipt (routers/agent.py add_agent_note, AgentSessionStore.add_user_note),
the watcher reads it with the lease check, and the agent gets it before its
next step. Stop stays Stop. No provider and no VM provider is called.
"""
import json
import threading

import pytest

from app.services import agent_delegation
from app.services.agent_delegation import NOTES_UNREAD, USER_NOTE_OPEN
from app.services.agent_sessions import USER_NOTES_MAX
from app.services.chat_store import TurnStatusConflict, _idempotent_turn_id
from app.services.llm.agent_client import AgentCompletion, measured_usage
from test_agent_long_runs import LongAgent
from test_agent_runs import AUTH, UID, api, pending, store, priced  # noqa: F401  (fixtures)
from test_agent_vm import ANSWER, _admin_allowance, fake_vm, vm_loop  # noqa: F401  (fixtures)


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


def test_only_a_running_vm_response_takes_messages(api):
    client, store, _ = api
    chat, _, _ = running(store, vm="off")
    refused = client.post(f"/agent/chats/{chat}/requests/req-1/notes", json={"text": "hi"}, headers=AUTH)
    assert refused.status_code == 409 and refused.json()["code"] == "notes_unavailable"
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
