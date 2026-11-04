"""What the independent review of 2026-11-01 found in the reviewers setting
and the temporary chats, each as it must hold now: an unreviewed answer has
no "Reviewed the answer" step and may still close after paid work, the
"workspace" reviewers start once the workspace opened with its rules (never
for ask_user alone), the comparison result names no reviewers that do not
exist; a temporary chat survives the chat cap's reclaim, its deadline keeps
the promised 24 hours, one failing deadline never stops the sweep, Compare
chats are deleted without receipt reads, and no bookmark binds to one.
"""
from datetime import timedelta
import json
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict
import pytest

from app.api.routers import bookmarks as bookmarks_router
from app.core.rate_limit import limiter
from app.services import chat_store
from app.services.agent_audit import BRIEF_WORKSPACE, tool_brief
from app.services.agent_tools import ReadOnlyTool, ToolRegistry
from app.services.agent_vm_tools import OPEN_WORKSPACE
from app.services.chat_store import (TEMPORARY_CHAT_DELETED_WITHIN, TEMPORARY_CHAT_RETRY, TEMPORARY_CHAT_TTL,
                                     UNREACHABLE_CHAT_MIN_AGE, expire_temporary_chats)
from test_agent_audit import Audit, audit_loop, saved
from test_agent_runs import UID, store  # noqa: F401  (fixture)


@pytest.fixture(autouse=True)
def _admin_allowance(monkeypatch):
    from app.services import agent_budget_config
    monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, "pro", 5_000_000)


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    task: str = ""


def tool(name):
    return ReadOnlyTool(name, f"{name}.", Args, lambda args, *, cancellation: {"text": "ok"})


# --- Reviewers ---------------------------------------------------------------------

def test_an_unreviewed_answer_has_no_reviewed_step_in_its_activity(store):
    loop = audit_loop(store, Audit(), reviewers="off")
    events = list(loop.run())
    assert saved(store, loop)["agent_review"]["status"] == "off"
    assert not any(event.get("kind") == "tool" and event.get("name") == "audit_answer" for event in events)
    assert not any(item.get("name") == "audit_answer" for item in saved(store, loop).get("agent_activity") or [])


@pytest.mark.parametrize("setting", ["off", "workspace"])
def test_without_reviewers_paid_work_still_closes_with_an_answer(store, setting):
    loop = audit_loop(store, Audit(), reviewers=setting)
    assert loop._paid_audit() is False
    loop.messages.append({"role": "assistant", "content": "A paid step."})
    assert loop._paid_audit() is True


def test_workspace_reviewers_start_once_it_opened_and_know_its_rules(store):
    loop = audit_loop(store, Audit(), reviewers="workspace")
    loop.registry = ToolRegistry([*loop.registry.tools.values(), tool(OPEN_WORKSPACE)],
                                 argument_limit=loop.registry.argument_limit)
    loop.workspace_closed = True

    def tool_list():
        loop.workspace_names = frozenset({"vm_exec", "ask_user"})
        return [tool("vm_exec"), tool("ask_user")]
    loop._workspace_tool_list = tool_list
    auditor = loop.comparison.auditor
    # The step that asks to open it starts nothing: the opening may still be refused.
    loop._review_from_here(SimpleNamespace(tool_calls=[{"function": {"name": OPEN_WORKSPACE}}], step_id="completion:0"))
    assert not auditor.sessions
    try:
        loop._open_workspace()
        assert auditor.sessions
        # The brief has the workspace's tools as the app describes them, and its facts.
        assert auditor._brief_parts["tools"] == tool_brief(loop.registry)
        assert {"vm_exec", "ask_user"} <= set(auditor._brief_parts["tools"])
        assert BRIEF_WORKSPACE in auditor._brief_parts["instructions"]
        opened = [(entry, text) for entry, text in loop.work_log.entries_after(0) if entry.get("name") == "workspace_opened"]
        assert len(opened) == 1
        content = json.loads(opened[0][1])
        assert content == {"text": BRIEF_WORKSPACE, "tools": {"ask_user": "ask_user.", "vm_exec": "vm_exec."}}
    finally:
        loop.comparison.close()


def test_a_question_to_the_user_alone_starts_no_workspace_reviewers(store):
    loop = audit_loop(store, Audit(), reviewers="workspace")
    loop.workspace_names = frozenset({"vm_exec", "ask_user", "request_domain"})
    auditor = loop.comparison.auditor
    loop._review_from_here(SimpleNamespace(tool_calls=[{"function": {"name": "ask_user"}}], step_id="completion:0"))
    assert not auditor.sessions
    try:
        loop._review_from_here(SimpleNamespace(tool_calls=[{"function": {"name": "vm_exec"}}], step_id="completion:1"))
        assert auditor.sessions
    finally:
        loop.comparison.close()


@pytest.mark.parametrize("setting", ["always", "off"])
def test_the_comparison_result_names_reviewers_only_where_they_are(store, setting):
    from test_agent_audit_compare import Advised, advised_loop, tool_results
    loop = advised_loop(store, Advised(), reviewers=setting)
    list(loop.run())
    [result] = tool_results(loop, "compare_models")
    assert ("the reviewers read them too" in result["instruction"]) is (setting == "always")
    assert "The user can read them under your answer" in result["instruction"]


# --- Temporary chats -----------------------------------------------------------------

def test_the_deadline_keeps_the_promised_day_with_an_hourly_sweep():
    assert TEMPORARY_CHAT_DELETED_WITHIN == timedelta(hours=24)
    assert TEMPORARY_CHAT_TTL + timedelta(hours=1) <= TEMPORARY_CHAT_DELETED_WITHIN


def test_the_chat_caps_reclaim_leaves_temporary_chats_to_their_deadline(store):
    temporary = store.create_chat(UID, execution_mode="agent", temporary=True)["id"]
    unreachable = store.create_chat(UID, execution_mode="agent")["id"]
    later = max(data["updated_at"] for data in store.db.chats(UID).values()) + UNREACHABLE_CHAT_MIN_AGE * 2
    assert store.reclaim_unreachable_chats(UID, now=later) == 1
    assert store.get_chat(UID, temporary)["temporary"] is True
    assert store.db.chats(UID)[unreachable]["status"] == chat_store.CHAT_STATUS_DELETING


def test_one_failing_deadline_never_stops_the_sweep(store, monkeypatch):
    first = store.create_chat(UID, execution_mode="agent", temporary=True)["id"]
    second = store.create_chat(UID, execution_mode="agent", temporary=True)["id"]
    due = max(store._temporary_ref(UID, c).get().to_dict()["expires_at"] for c in (first, second))
    real = chat_store._expire_temporary_chat

    def flaky(store_, snapshot, *, now):
        if (snapshot.to_dict() or {}).get("chat_id") == first:
            raise RuntimeError("outage")
        return real(store_, snapshot, now=now)
    monkeypatch.setattr(chat_store, "_expire_temporary_chat", flaky)
    now = due + timedelta(seconds=1)
    assert expire_temporary_chats(store.db, now=now) == 1
    assert store._temporary_ref(UID, first).get().to_dict()["expires_at"] == now + TEMPORARY_CHAT_RETRY
    assert store._temporary_ref(UID, second).get().exists is False
    # A chat already being deleted belongs to its deletion job: its deadline goes alone.
    third = store.create_chat(UID, execution_mode="agent", temporary=True)["id"]
    store.request_chat_deletion(UID, third)
    monkeypatch.setattr(chat_store, "_expire_temporary_chat", real)
    # Later the postponed one goes too; the third's deadline is dropped, its job deletes it.
    assert expire_temporary_chats(store.db, now=now + TEMPORARY_CHAT_TTL * 2) == 1
    assert store._temporary_ref(UID, third).get().exists is False
    assert store._temporary_ref(UID, first).get().exists is False


def test_a_compare_chat_is_deleted_without_reading_agent_receipts(store):
    chat = store.create_chat(UID, execution_mode="consensus")["id"]
    store.db.read_log.clear()
    store.delete_chat(UID, chat)
    assert not any("llm_calls" in path for path in store.db.read_log)


def test_no_bookmark_binds_to_a_temporary_chat(store):
    chat = store.create_chat(UID, execution_mode="agent", temporary=True)["id"]
    app = FastAPI()
    app.state.limiter = limiter
    limiter.reset()
    bookmarks_router.api_uid_limiter.reset()
    app.include_router(bookmarks_router.router)
    with (patch.object(bookmarks_router, "verify_user_token", return_value=UID),
          patch.object(bookmarks_router, "db_firestore", store.db),
          patch.object(bookmarks_router, "_chat_store", lambda: store)):
        response = TestClient(app).post("/bookmark", json={
            "id_token": "token", "bookmarkId": "b_forged", "question": "Q", "response": "A",
            "modelName": "OpenAI", "mode": "Standard", "chatId": chat, "turnId": "a" * 32})
    assert response.status_code == 409
    assert ("users", UID, "bookmarks", "b_forged") not in store.db.documents
