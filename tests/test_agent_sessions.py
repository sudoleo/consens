"""Agent sessions (comparison answers, reviewers, page reads) on the run's root: journal, views, reaper."""
from datetime import datetime, timedelta, timezone

import pytest
pytestmark = pytest.mark.usefixtures("deepseek_default_agent")

from agent_reviewers import without_reviewers
from app.services.agent_comparison import comparison_selection
from app.services.agent_loop import AgentLoop
from app.services.agent_policy import AgentPolicy
from app.services.chat_store import TurnStatusConflict
from app.services.llm.agent_client import AgentCompletion, resolve_agent_model
from app.services.llm.provider_runtime import ProviderCancellation
from test_agent_runs import UID, AUTH, api, pending, priced, receipt, store, totals  # noqa: F401  (fixtures)


def make_loop(store, factory=AgentCompletion, **kwargs):
    """A chat turn of the agent with ``factory``'s completions and no reviewers."""
    chat, turn = pending(store)
    return without_reviewers(AgentLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"), messages=[{"role": "system", "content": "Answer."},
        {"role": "user", "content": "Verify two independent calculations."}], api_key="test-sessions",
        cancellation=ProviderCancellation(), policy=AgentPolicy(), completion_factory=factory,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}),
        **kwargs))


def test_activity_view_reuses_the_receipt_read_for_lease_check(store):
    loop = make_loop(store)
    assert store.claim(UID, loop.chat_id, loop.turn_id, loop.model, run_token=loop.run_token,
                       policy=loop.policy.snapshot(), reservation=(100, priced(100)))
    store.db.read_log.clear()
    assert store.delegation_view(UID, loop.chat_id, loop.turn_id)['status'] == 'running'
    path = store.receipt_ref(UID, loop.chat_id, loop.turn_id).path
    assert store.db.read_log.count(path) == 1


def test_crashed_process_never_restarts_paid_steps_and_deduplicates_events(store):
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, policy=loop.policy.snapshot(), run_token=loop.run_token, reservation=(10, priced(10)))
    aid = "f" * 32
    publish = dict(run_token=loop.run_token, agent_id=aid, event_id="same", patch={"assignment": {"goal": "Test"}, "status": "working"})
    assert store.publish_agent(*args, **publish) == store.publish_agent(*args, **publish)
    first = f"agent:{aid}:0"
    store.claim(*args, loop.model, step=first, run_token=loop.run_token, policy=loop.policy.snapshot(),
                reservation=(2000, priced(2000)))
    store.settle(*args, completion=receipt(), status="succeeded", step=first)
    store.claim(*args, loop.model, step=f"agent:{aid}:1", run_token=loop.run_token, policy=loop.policy.snapshot(),
                reservation=(2000, priced(2000)))
    root = store.receipt_ref(*args)
    store._transaction(lambda tx: tx.update(root, {"lease_until": datetime.now(timezone.utc) - timedelta(seconds=1)}))
    view = store.delegation_view(*args)
    assert view["status"] == "cancelled" and view["agents"][0]["status"] == "stopped"
    assert totals(store)["calls"] == 3 and totals(store)["unmetered_calls"] == 2
    assert view["agents"][0]["usage"]["cost_complete"] is False
    assert view["agents"][0]["usage"]["estimated_cost_nano_usd"] == receipt().usage["estimated_cost_nano_usd"]
    assert not store.claim(*args, loop.model, policy=loop.policy.snapshot(), run_token=loop.run_token, reservation=(10, priced(10)))
    with pytest.raises(TurnStatusConflict):
        store.publish_agent(*args, run_token=loop.run_token, agent_id=aid, patch={"status": "completed"})
    store.delete_chat(UID, loop.chat_id)
    assert not any("agents" in path or "agent_events" in path for path in store.db.documents)


def test_session_endpoints_are_owner_bound_and_read_only(api):
    client, store, _ = api
    loop = make_loop(store, mock_answer="Answer")
    list(loop.run())
    url = f"/agent/chats/{loop.chat_id}/turns/{loop.turn_id}/agents"
    assert client.get(url, headers=AUTH).status_code == 200
    assert client.get(url, headers=AUTH).headers["cache-control"] == "private, no-store"
    assert client.get(url).status_code == 401
    assert client.get(url.replace(loop.chat_id, "f" * 32), headers=AUTH).status_code == 404
    assert client.get(url + "/" + "a" * 32 + "?limit=51", headers=AUTH).status_code == 422
    assert totals(store)["calls"] == 1


def test_a_retried_session_update_is_saved_once_without_an_event_document(store):
    """A journal batch whose commit was ambiguous is sent again with the same
    event ids (_journal_write): the second time returns what the first saved,
    moves no sequence and adds no message. The session keeps the ids itself;
    event documents of their own would cost a write and a read per update."""
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(100, priced(100)))
    agent_id, event_id = "a" * 32, "e" * 32
    assignment = {"goal": "Verify", "context": "A=2, B=3"}
    first = store.publish_agent(*args, run_token=loop.run_token, agent_id=agent_id, event_id=event_id,
                                patch={"assignment": assignment, "status": "working"},
                                message={"kind": "note", "text": "Started."})
    again = store.publish_agent(*args, run_token=loop.run_token, agent_id=agent_id, event_id=event_id,
                                patch={"assignment": assignment, "status": "working"},
                                message={"kind": "note", "text": "Started."})
    assert again["seq"] == first["seq"] and again["id"] == event_id and again["agent"]["status"] == "working"
    assert store.receipt_ref(*args).get().to_dict()["event_seq"] == first["seq"]
    session = store.agent_ref(*args, agent_id).get().to_dict()
    assert session["event_ids"] == [event_id] and "event_ids" not in first["agent"]
    turn_ref = store._turn_ref(*args)
    assert len(list(turn_ref.collection("agents").document(agent_id).collection("messages").stream())) == 1
    assert not list(turn_ref.collection("agent_events").stream())
    # The browser's view of the sessions carries neither the ids nor the assignment.
    [view] = store.delegation_view(*args)["agents"]
    assert "event_ids" not in view and "assignment" not in view
    # Only the newest ids stay with the session.
    for index in range(10):
        store.publish_agent(*args, run_token=loop.run_token, agent_id=agent_id, event_id=f"{index:032x}",
                            patch={"status": "working"})
    assert store.agent_ref(*args, agent_id).get().to_dict()["event_ids"] == [f"{index:032x}" for index in range(2, 10)]
