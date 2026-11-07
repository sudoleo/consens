"""Temporary chats: an Agent chat that keeps nothing beyond itself. It
does what the account's other chats do (Max): the workspace, Watches, the
search of other chats and the memory, read. What would outlast it stays out: no bookmark (the sidebar's
handle), nothing written to memory or the workspace's notes, no share, and
no other chat's search finds it. Its folder and background processes in the
workspace go with it. The browser deletes it when the user leaves it; a
deadline registry (chat_store.TEMPORARY_CHATS_COLLECTION) deletes it from
the hourly retention loop when a tab closed without that. A chat's deletion
also takes the texts its runs' receipts held. No model calls beyond the
scripted ones.
"""
import json
from datetime import timedelta

import pytest

from app.api.routers import agent
from app.services import agent_memory, prompt_defaults
from app.services.chat_store import (TEMPORARY_CHAT_TTL, ChatNotFound, expire_temporary_chats)
from test_agent_chat_search import earlier, search
from test_agent_comparison import Script
from test_agent_runs import AUTH, UID, api, pending, store  # noqa: F401  (fixtures)
from test_agent_share import UID as SHARE_UID, _saved_turn, share_app  # noqa: F401  (fixture)
from test_agent_vm import NAME, Agent, fake_vm, results, vm_loop  # noqa: F401  (fixture)
from test_agent_watch import watch_loop


def deadline(store, chat_id):
    snapshot = store._temporary_ref(UID, chat_id).get()
    return snapshot.to_dict() if snapshot.exists else None


def test_a_temporary_chat_carries_its_deadline_from_its_creation_and_each_message(store):
    chat = store.create_chat(UID, execution_mode="agent", temporary=True)
    assert chat["temporary"] is True
    first = deadline(store, chat["id"])
    assert first["uid"] == UID and first["chat_id"] == chat["id"]
    assert set(first) == {"uid", "chat_id", "expires_at", "updated_at"}
    assert first["expires_at"] - first["updated_at"] == TEMPORARY_CHAT_TTL
    pending(store, chat_id=chat["id"])
    assert deadline(store, chat["id"])["expires_at"] >= first["expires_at"]
    # A normal chat has none; only an Agent chat can be temporary.
    normal = store.create_chat(UID, execution_mode="agent")
    assert "temporary" not in normal and deadline(store, normal["id"]) is None
    with pytest.raises(ValueError):
        store.create_chat(UID, execution_mode="consensus", temporary=True)


def test_a_message_during_the_sweep_moves_its_deadline_on(store):
    """The query found the deadline due, a message renewed it before the
    sweep came to it: the chat stays."""
    from app.services.chat_store import ChatStore, _expire_temporary_chat
    chat = store.create_chat(UID, execution_mode="agent", temporary=True)
    due = deadline(store, chat["id"])["expires_at"]
    found = store._temporary_ref(UID, chat["id"]).get()
    store._temporary_ref(UID, chat["id"]).update({"expires_at": due + TEMPORARY_CHAT_TTL})
    assert _expire_temporary_chat(ChatStore(store.db), found, now=due + timedelta(seconds=1)) is False
    assert store.get_chat(UID, chat["id"])["temporary"] is True


def test_the_retention_loop_deletes_a_temporary_chat_once_its_deadline_passed(store):
    chat = store.create_chat(UID, execution_mode="agent", temporary=True)
    pending(store, chat_id=chat["id"])
    normal = store.create_chat(UID, execution_mode="agent")["id"]
    due = deadline(store, chat["id"])["expires_at"]
    assert expire_temporary_chats(store.db, now=due - timedelta(seconds=1)) == 0
    assert store.get_chat(UID, chat["id"])["temporary"] is True
    assert expire_temporary_chats(store.db, now=due + timedelta(seconds=1)) == 1
    with pytest.raises(ChatNotFound):
        store.get_chat(UID, chat["id"])
    assert store.db.turns(UID, chat["id"]) == {} and deadline(store, chat["id"]) is None
    assert store.get_chat(UID, normal)
    # A deadline whose chat went another way is dropped alone.
    gone = store.create_chat(UID, execution_mode="agent", temporary=True)["id"]
    store.delete_chat(UID, gone)
    assert deadline(store, gone) is None
    stray = store.create_chat(UID, execution_mode="agent", temporary=True)["id"]
    store._chat_ref(UID, stray).delete()
    assert expire_temporary_chats(store.db, now=due + TEMPORARY_CHAT_TTL * 2) == 0
    assert deadline(store, stray) is None


def test_leaving_it_deletes_it_and_account_deletion_takes_its_deadline(store):
    left = store.create_chat(UID, execution_mode="agent", temporary=True)["id"]
    store.delete_chat(UID, left)
    assert deadline(store, left) is None
    kept = store.create_chat(UID, execution_mode="agent", temporary=True)["id"]
    store.delete_all_chats(UID)
    assert deadline(store, kept) is None


def test_a_deleted_chat_takes_the_texts_its_receipts_held(store):
    chat_id, turn = pending(store)
    ref = store.receipt_ref(UID, chat_id, turn["id"])
    ref.set({"run_status": "succeeded", "estimated_cost_nano_usd": 7,
             "user_notes": [{"id": "n1", "text": "my private words"}],
             "hold": {"id": "h1", "reason": "a reviewer's reason", "request": "a question"},
             "hold_decision": {"id": "h1", "action": "steer"}})
    store.delete_chat(UID, chat_id)
    # The cost stays (billing), the words go with their chat.
    assert ref.get().to_dict() == {"run_status": "succeeded", "estimated_cost_nano_usd": 7}


def test_chat_search_neither_finds_nor_opens_a_temporary_chat(store):
    loop = watch_loop(store, Script())
    bike = earlier(store, "Fahrrad", "Welches Rad?")
    hidden = earlier(store, "Fahrrad geheim", "Welches Rad, geheim?", temporary=True)
    assert [chat["chat_id"] for chat in search(loop, query="fahrrad")["chats"]] == [bike]
    with pytest.raises(ValueError, match="No such chat"):
        search(loop, chat_id=hidden)


def test_its_answers_cannot_be_shared(share_app):
    client, database, store = share_app
    chat_id, turn_id = _saved_turn(database, store)
    database.documents[("users", SHARE_UID, "chats", chat_id)]["temporary"] = True
    response = client.post(f"/agent/chats/{chat_id}/turns/{turn_id}/share-result",
                           headers={"Authorization": "Bearer token"})
    assert response.status_code == 409 and "temporary chat" in response.json()["detail"]


def test_a_temporary_chat_does_what_any_chat_does_and_keeps_nothing_beyond_itself(api, monkeypatch):
    client, store, calls = api
    # An account with the workspace and a memory it may change.
    from app.services import agent_vm
    monkeypatch.setattr(agent, "vm_allowed", lambda uid: True)
    monkeypatch.setattr(agent_vm, "configured", lambda: True)
    monkeypatch.setattr(agent, "_memory_snapshot", lambda uid: agent_memory.MemorySnapshot(
        available=True, enabled=True, auto=True, items=({"id": "m1", "text": "Prefers SECRET-MEMORY."},)))
    assert client.post("/chats", json={"execution_mode": "consensus", "temporary": True},
                       headers=AUTH).status_code == 422
    created = client.post("/chats", json={"execution_mode": "agent", "temporary": True}, headers=AUTH)
    chat_id = created.json()["chat"]["id"]
    assert created.status_code == 201 and created.json()["chat"]["temporary"] is True
    payload = {"chat_id": chat_id, "question": "Something private", "client_request_id": "temp-1",
               "bookmark_id": "b_agent_temporary"}
    response = client.post("/agent", json=payload, headers=AUTH)
    assert response.status_code == 200 and "event: final" in response.text, response.text
    # No sidebar entry, said so to the page.
    bookmark = store.db.collection("users").document(UID).collection("bookmarks").document("b_agent_temporary")
    assert not bookmark.get().exists
    final = client.post("/agent", json=payload, headers=AUTH).json()
    assert final["bookmark_meta"] is None and final["temporary"] is True
    assert not store.db.collection("memory_reviews").document(UID).get().exists
    turn = next(t for t in store.list_turns(UID, chat_id)["turns"] if t["question"] == "Something private")
    settings = store.get_turn(UID, chat_id, turn["id"])["agent_settings"]
    # The account's workspace, as in its other chats; memory read, not written.
    assert settings["temporary"] is True and settings["agent_preferences"] == {"vm": "on"}
    assert settings["memory"] == {"used": True, "auto": False, "hint": False}
    # What the agent is offered and told.
    names = {tool["function"]["name"] for tool in calls[0].get("tools") or [] if tool.get("type") == "function"}
    assert {"compare_models", "search_chats", "open_workspace"} <= names
    # A Watch runs the agent again in its chat (agent_watches.py): a temporary
    # chat keeps nothing, so it has none.
    assert "update_memory" not in names and "prepare_watch" not in names
    system = calls[0]["messages"][0]["content"]
    assert prompt_defaults.AGENT_TEMPORARY_CHAT_PROMPT in system
    assert "SECRET-MEMORY" in system and agent_memory.AUDIT_MEMORY_TEMPORARY_PROMPT in system
    # A normal chat of the same account keeps its bookmark and its memory.
    normal = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]["id"]
    assert client.post("/agent", json={**payload, "chat_id": normal, "client_request_id": "normal-1",
                                       "bookmark_id": "b_agent_normal"}, headers=AUTH).status_code == 200
    assert store.db.collection("users").document(UID).collection("bookmarks").document("b_agent_normal").get().exists
    normal_system = calls[-1]["messages"][0]["content"]
    assert "SECRET-MEMORY" in normal_system and agent_memory.AUDIT_MEMORY_TEMPORARY_PROMPT not in normal_system
    assert prompt_defaults.AGENT_TEMPORARY_CHAT_PROMPT not in normal_system
    normal_names = {tool["function"]["name"] for tool in calls[-1].get("tools") or [] if tool.get("type") == "function"}
    assert "update_memory" in normal_names
    # Only the normal chat brings the daily memory review due (memory_review.py,
    # marked beside the run, so wait for it briefly).
    import time
    review = store.db.collection("memory_reviews").document(UID)
    deadline_at = time.monotonic() + 5
    while not review.get().exists and time.monotonic() < deadline_at:
        time.sleep(0.02)
    assert set(review.get().to_dict()) == {"last_turn_at", "review_after"}


def test_its_memory_is_read_and_never_written():
    """The block and the facts as in any chat, the write rules replaced by
    the temporary chat's fact; no "Let Agent update memory" hint, since that
    would not save anything here either."""
    import dataclasses
    snapshot = agent_memory.MemorySnapshot(available=True, enabled=True, auto=True,
                                           items=({"id": "m1", "text": "Prefers tea."},))
    temporary = dataclasses.replace(snapshot, temporary=True)
    assert snapshot.writable and not temporary.writable
    prompt = agent_memory.orchestrator_prompt(temporary)
    assert "Prefers tea." in prompt and prompt.endswith(agent_memory.AUDIT_MEMORY_TEMPORARY_PROMPT)
    assert "update_memory" not in prompt
    off = dataclasses.replace(temporary, auto=False)
    assert off.settings() == {"used": True, "auto": False, "hint": False}
    assert dataclasses.replace(snapshot, auto=False).settings()["hint"] is True
    # Paused or unreadable memory says so, temporary or not.
    assert agent_memory.orchestrator_prompt(dataclasses.replace(temporary, enabled=False)) == (
        agent_memory.AUDIT_MEMORY_PAUSED_PROMPT)
    # Unreadable: nothing could be saved later either.
    assert agent_memory.orchestrator_prompt(agent_memory.MemorySnapshot(temporary=True)) == (
        agent_memory.AUDIT_MEMORY_TEMPORARY_PROMPT)
    assert agent_memory.orchestrator_prompt(agent_memory.MemorySnapshot()) == (
        agent_memory.AUDIT_MEMORY_UNAVAILABLE_PROMPT)


def test_a_temporary_chat_searches_the_other_chats(store):
    """The search finds saved chats, never a temporary one."""
    loop = watch_loop(store, Script())
    store._chat_ref(UID, loop.chat_id).update({"temporary": True})
    loop.temporary = True
    bike = earlier(store, "Fahrrad", "Welches Rad?")
    assert [chat["chat_id"] for chat in search(loop, query="fahrrad")["chats"]] == [bike]


def test_it_reads_the_workspaces_notes_and_its_file_tools_leave_them_as_they_are(store, fake_vm):
    """The notes outlast the chat (NOTES.md, agent_workspace.py): its first
    result brings them as in any chat, saying they stay as they are; writing
    or editing them is refused, the rest of the workspace is the agent's."""
    from app.services import agent_workspace
    from app.services.agent_vm_tools import NOTES_KEPT
    notes = b"# Notes\nThe blog lives in ~/blog.\n"
    fake_vm.vms[NAME] = {"files": {agent_workspace.NOTES_PATH: notes}, "checkpoints": []}
    script = Agent([[("vm_write_file", {"path": "draft.md", "content": "a"})],
                    [("vm_write_file", {"path": "~/NOTES.md", "content": "private"})],
                    [("vm_edit_file", {"path": "../../NOTES.md", "old_string": "blog", "new_string": "private"})],
                    [("vm_write_file", {"path": "//home/agent/NOTES.md", "content": "private"})]])
    loop = vm_loop(store, script)
    loop.temporary = True
    list(loop.run())
    draft, written, edited, doubled = results(loop)
    assert draft["workspace_notes"] == {"path": agent_workspace.NOTES_PATH, "text": notes.decode(),
                                        "note": agent_workspace.NOTES_TEMPORARY}
    assert written == edited == doubled == {"error": NOTES_KEPT}
    assert fake_vm.vms[NAME]["files"][agent_workspace.NOTES_PATH] == notes
    # Its folder and marker name no title, and its messages take no checkpoint.
    session = loop.vm_tools.session
    assert session.dir.rsplit("/", 1)[1] == f"temporary-{loop.chat_id[:6]}"
    marker = fake_vm.vms[NAME]["files"][f"{session.dir}/{agent_workspace.CHAT_MARKER}"].decode()
    assert "Question one" not in marker and agent_workspace.TEMPORARY_MARKER in marker
    assert not [call for call in fake_vm.calls if call[0] == "checkpoint"]
    assert not (store.get_turn(UID, loop.chat_id, loop.turn_id).get("agent_vm") or {}).get("checkpoint")
    # None yet: no invitation to start them.
    assert agent_workspace.notes_for_agent(None, temporary=True)["note"] == agent_workspace.NOTES_NONE_TEMPORARY
    assert "keep them shorter" not in agent_workspace.notes_for_agent(b"x" * 30_000, temporary=True)["more"]


def test_a_message_stopped_by_its_chats_deletion_sweeps_what_it_wrote_after(store, fake_vm):
    """Left mid-answer: DELETE /chats stops the run before the cascade, and
    the stopped message's end removes what a call still in flight wrote."""
    from app.services import agent_vm_processes
    loop = vm_loop(store, Agent([[("vm_write_file", {"path": "late.txt", "content": "late"})]]))
    list(loop.run())
    session = loop.vm_tools.session
    late = f"{session.dir}/late.txt"
    assert late in fake_vm.vms[NAME]["files"]
    # Still active (a plain Stop): nothing goes.
    session._sweep_deleted()
    assert late in fake_vm.vms[NAME]["files"]
    store._chat_ref(UID, loop.chat_id).update({"status": "deleting"})
    session.backend = fake_vm.backend()
    session._sweep_deleted()
    assert not [path for path in fake_vm.vms[NAME]["files"] if path.startswith(session.dir + "/")]
    assert agent_vm_processes.chat_command(loop.chat_id) in fake_vm.server


def test_leaving_it_mid_answer_stops_the_run_before_the_cascade(api, monkeypatch):
    from app.services.agent_background import agent_background
    from app.services.chat_store import ChatStore
    client, store, calls = api
    chat_id = client.post("/chats", json={"execution_mode": "agent", "temporary": True}, headers=AUTH).json()["chat"]["id"]
    order = []
    monkeypatch.setattr(agent_background, "stop_chat", lambda uid, chat: order.append(("stop", chat)) or 0)
    real = ChatStore.run_chat_deletion
    monkeypatch.setattr(ChatStore, "run_chat_deletion",
                        lambda self, uid, chat: order.append(("cascade", chat)) or real(self, uid, chat))
    assert client.delete(f"/chats/{chat_id}", headers=AUTH).status_code == 200
    assert order == [("stop", chat_id), ("cascade", chat_id)]
    assert client.delete(f"/chats/{chat_id}", headers=AUTH).status_code == 404


def test_deleting_it_takes_its_folder_and_processes_from_the_workspace(store, monkeypatch):
    """The account's workspace stays (browser sign-ins, notes, other chats'
    folders); what the chat made there goes with it."""
    from app.services import agent_vm, agent_vm_processes
    from test_agent_vm import FakeVM
    fake = FakeVM()
    monkeypatch.setattr(agent_vm, "backend", fake.backend)
    name = agent_vm.workspace_name(UID)
    chat_id = store.create_chat(UID, execution_mode="agent", temporary=True)["id"]
    folder = agent_vm.chat_folder("Geheim", chat_id)
    store._chat_ref(UID, chat_id).update({"agent_vm": {"name": name, "workspace": True, "folder": folder}})
    process = agent_vm_processes.process_dir("abcd1234")
    fake.vms[name] = {"files": {f"{agent_vm.chat_dir(chat_id, folder)}/notes.txt": b"private",
                                f"{process}/output.log": b"private output", f"{process}/chat": chat_id.encode(),
                                "/home/agent/NOTES.md": b"# Notes\n", "/home/agent/chats/other-123456/a.txt": b"a"},
                      "checkpoints": []}
    fake.commands[agent_vm_processes.chat_command(chat_id)] = ([("stdout", b"abcd1234 running\n")], 0, .1)
    # Stopped after 100 of the 1800 seconds it was charged today: the rest comes back.
    from app.services import agent_vm_time
    stopped = f"consens-process stopped 0 100 1800 {agent_vm_time.day_key()} 0\n"
    fake.commands[agent_vm_processes.stop_command(process, agent_vm_processes.task_name("abcd1234"))] = (
        [("stdout", stopped.encode())], 0, .1)
    refunds = []
    monkeypatch.setattr(agent_vm_time, "refund", lambda store_, uid, seconds, day: refunds.append((uid, seconds, day)))
    store.delete_chat(UID, chat_id)
    assert refunds == [(UID, 1700, agent_vm_time.day_key())]
    files = fake.vms[name]["files"]
    assert not [path for path in files if path.startswith(agent_vm.chat_dir(chat_id, folder))]
    assert not [path for path in files if path.startswith(process)]
    assert agent_vm_processes.stop_command(process, agent_vm_processes.task_name("abcd1234")) in fake.server
    assert files["/home/agent/NOTES.md"] == b"# Notes\n" and "/home/agent/chats/other-123456/a.txt" in files


def test_a_process_list_that_does_not_come_back_whole_keeps_the_deletion_job(monkeypatch):
    from app.services import agent_vm, agent_vm_processes
    from test_agent_vm import FakeVM
    fake = FakeVM()
    name = agent_vm.workspace_name(UID)
    fake.vms[name] = {"files": {}, "checkpoints": []}
    fake.commands[agent_vm_processes.chat_command("c1")] = ([("stdout", b"abcd1234 run")], None, 30.0)
    with pytest.raises(agent_vm.VMUnavailable):
        agent_vm_processes.delete_for_chat(fake.backend(), name, "c1")


def test_leaving_it_closes_only_its_own_lifetime_to_restore(store, monkeypatch):
    """Its messages take no checkpoint; other chats' checkpoints from its
    lifetime hold its folder and may not come back. Older ones still may: a
    floor at every deletion would end restore for the account's whole past."""
    from datetime import datetime, timezone
    from app.services import agent_vm, agent_workspace
    from test_agent_vm import FakeVM
    monkeypatch.setattr(agent_vm, "backend", FakeVM().backend)
    name = agent_vm.workspace_name(UID)
    agent_workspace.ref(store.db, UID).set({"name": name})
    before = datetime.now(timezone.utc) - timedelta(hours=2)
    chat_id = store.create_chat(UID, execution_mode="agent", temporary=True)["id"]
    lived = datetime.now(timezone.utc) - timedelta(hours=1)
    store._chat_ref(UID, chat_id).update({"agent_vm": {"name": name, "workspace": True,
                                                        "created_at": (lived - timedelta(minutes=5)).isoformat()}})
    store.delete_chat(UID, chat_id)
    record = agent_workspace.record(store.db, UID)
    assert "restore_floor" not in record and len(record["restore_gaps"]) == 1

    def turn_vm(at):
        return {"name": name, "checkpoint": "cp", "checkpoint_at": at.isoformat()}
    assert agent_workspace.restorable(record, turn_vm(before))
    assert not agent_workspace.restorable(record, turn_vm(lived))
    # A normal chat's deletion still raises the floor.
    normal = store.create_chat(UID, execution_mode="agent")["id"]
    store._chat_ref(UID, normal).update({"agent_vm": {"name": name, "workspace": True}})
    store.delete_chat(UID, normal)
    assert not agent_workspace.restorable(agent_workspace.record(store.db, UID), turn_vm(before))


def test_a_run_that_outlives_its_deleted_chat_leaves_no_texts_on_its_receipt(store):
    """Leaving a temporary chat mid-run deletes it at once; the run stops a
    few seconds later (its watcher). What it wrote to its receipt meanwhile
    goes when it ends."""
    from test_agent_runs import receipt
    from app.services.llm.agent_client import AgentModel
    chat_id, turn = pending(store)
    store.claim(UID, chat_id, turn["id"], AgentModel(), run_token="tok")
    store.settle(UID, chat_id, turn["id"], completion=receipt(), status="succeeded")
    store.delete_chat(UID, chat_id)
    ref = store.receipt_ref(UID, chat_id, turn["id"])
    ref.update({"user_notes": [{"id": "n1", "text": "late words"}], "hold": {"id": "h1", "reason": "late"}})
    store.finish_run(UID, chat_id, turn["id"], completion=receipt(), status="cancelled", run_token="tok")
    data = ref.get().to_dict()
    assert data["run_status"] == "cancelled" and not {"user_notes", "hold", "hold_decision"} & set(data)


def test_a_failed_run_in_a_temporary_chat_still_hands_its_saved_answer_to_the_page(api, monkeypatch):
    from app.services.llm.agent_client import AgentCompletion
    from test_agent_runs import receipt
    client, store, calls = api

    def failed(self, **kwargs):
        self.__dict__.update(receipt().__dict__)
        self.text = "Partial"
        yield {"type": "delta", "text": "Partial"}
        raise RuntimeError("Provider failed")
    monkeypatch.setattr(AgentCompletion, "stream", failed)
    chat_id = client.post("/chats", json={"execution_mode": "agent", "temporary": True}, headers=AUTH).json()["chat"]["id"]
    response = client.post("/agent", json={"chat_id": chat_id, "question": "Hi", "client_request_id": "temp-failed",
                                           "bookmark_id": "b_agent_temp"}, headers=AUTH)
    error = json.loads(response.text.split("event: error\ndata: ")[1].split("\n\n")[0])
    saved = error["saved_answer"]
    assert saved["temporary"] is True and saved["bookmark_meta"] is None and saved["turn"]["status"] == "failed"
    bookmark = store.db.collection("users").document(UID).collection("bookmarks").document("b_agent_temp")
    assert not bookmark.get().exists


def test_a_temporary_chat_whose_turn_stays_pending_gets_no_saved_answer(api, monkeypatch):
    """finish_run failed in the run's finally: the turn is still pending and
    the server says "running". A saved_answer next to it made the page take
    the pending turn as the answer instead of following it; a normal chat
    gets none there either."""
    from app.services.agent_runs import AgentRunStore
    from app.services.llm.agent_client import AgentCompletion
    from test_agent_runs import receipt
    client, store, calls = api

    def failed(self, **kwargs):
        self.__dict__.update(receipt().__dict__)
        self.text = "Partial"
        yield {"type": "delta", "text": "Partial"}
        raise RuntimeError("Provider failed")

    def unsaved(self, *args, **kwargs):
        raise RuntimeError("Firestore unavailable")
    monkeypatch.setattr(AgentCompletion, "stream", failed)
    monkeypatch.setattr(AgentRunStore, "finish_run", unsaved)
    chat_id = client.post("/chats", json={"execution_mode": "agent", "temporary": True}, headers=AUTH).json()["chat"]["id"]
    response = client.post("/agent", json={"chat_id": chat_id, "question": "Hi", "client_request_id": "temp-pending",
                                           "bookmark_id": "b_agent_temp"}, headers=AUTH)
    error = json.loads(response.text.split("event: error\ndata: ")[1].split("\n\n")[0])
    assert error["recovery_state"] == "running"
    assert "saved_answer" not in error
