"""Temporary chats (since 2026-11-01): an Agent chat that keeps nothing
beyond itself. No bookmark (the sidebar's handle), no memory read or
written, no workspace, no Watch, no search of other chats and none of them
of it, no share. The browser deletes it when the user leaves it; a deadline
registry (chat_store.TEMPORARY_CHATS_COLLECTION) deletes it from the hourly
retention loop when a tab closed without that. A chat's deletion also takes
the texts its runs' receipts held. No model calls beyond the scripted ones.
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


def test_a_temporary_chat_keeps_nothing_beyond_itself(api, monkeypatch):
    client, store, calls = api
    # An account with the workspace and a memory it may change.
    monkeypatch.setattr(agent, "vm_allowed", lambda uid: True)
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
    turn = next(t for t in store.list_turns(UID, chat_id)["turns"] if t["question"] == "Something private")
    settings = store.get_turn(UID, chat_id, turn["id"])["agent_settings"]
    assert settings["temporary"] is True and settings["agent_preferences"] == {"vm": "off"}
    assert settings["memory"] == {"used": False, "auto": False, "hint": False}
    # What the agent is offered and told.
    names = {tool["function"]["name"] for tool in calls[0].get("tools") or [] if tool.get("type") == "function"}
    assert not names & {"update_memory", "search_chats", "prepare_watch", "open_workspace"}
    assert "compare_models" in names
    system = calls[0]["messages"][0]["content"]
    assert prompt_defaults.AGENT_TEMPORARY_CHAT_PROMPT in system
    # The memory, read beside the other reads, goes nowhere.
    assert agent_memory.AUDIT_MEMORY_TEMPORARY_PROMPT in system and "SECRET-MEMORY" not in system
    # A normal chat of the same account keeps its bookmark and its memory.
    normal = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]["id"]
    assert client.post("/agent", json={**payload, "chat_id": normal, "client_request_id": "normal-1",
                                       "bookmark_id": "b_agent_normal"}, headers=AUTH).status_code == 200
    assert store.db.collection("users").document(UID).collection("bookmarks").document("b_agent_normal").get().exists
    assert "SECRET-MEMORY" in calls[-1]["messages"][0]["content"]


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
