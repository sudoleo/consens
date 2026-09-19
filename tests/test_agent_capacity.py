from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading

import anyio
import pytest
from starlette.requests import Request, ClientDisconnect

from app.api.routers import agent
from app.services.agent_runtime import AgentCapacity, AgentCapacityExceeded
from app.services.llm.agent_client import AgentModel
from test_agent_runs import UID, AUTH, api, store, pending, receipt, totals


def test_owner_limit_is_atomic_across_different_chats(store):
    turns = [pending(store, request_id=f"run-{i}") for i in range(12)]
    gate = threading.Barrier(len(turns))

    def claim(item):
        gate.wait(timeout=3)
        chat_id, turn = item
        try:
            store.claim(UID, chat_id, turn["id"], AgentModel())
            return item
        except AgentCapacityExceeded:
            return None

    with ThreadPoolExecutor(max_workers=len(turns)) as pool:
        winners = [item for item in pool.map(claim, turns) if item]
    assert len(winners) == 2
    assert totals(store)["calls"] == 2
    assert len(store.active_ref(UID).get().to_dict()["leases"]) == 2
    # A different user has independent admission; there is no global DB lock document.
    other_chat, other_turn = pending(store, uid="another-owner")
    assert store.claim("another-owner", other_chat, other_turn["id"], AgentModel())
    chat_id, turn = winners[0]
    store.settle(UID, chat_id, turn["id"], completion=receipt(), status="succeeded")
    replacement = next(item for item in turns if item not in winners)
    assert store.claim(UID, replacement[0], replacement[1]["id"], AgentModel())
    # Old settlement retries must not free the replacement's slot.
    assert not store.settle(UID, chat_id, turn["id"], completion=receipt(), status="succeeded")
    assert len(store.active_ref(UID).get().to_dict()["leases"]) == 2


def test_crashed_owner_lease_expires_without_retrying_the_paid_receipt(store):
    old = [pending(store, request_id=f"old-{i}") for i in range(2)]
    for chat_id, turn in old:
        store.claim(UID, chat_id, turn["id"], AgentModel())
    expired = datetime.now(timezone.utc) - timedelta(seconds=1)
    active = store.active_ref(UID)
    store.db.documents[active.path]["leases"] = {key: expired for key in active.get().to_dict()["leases"]}
    chat_id, turn = pending(store, request_id="fresh")
    assert store.claim(UID, chat_id, turn["id"], AgentModel())
    assert len(active.get().to_dict()["leases"]) == 1
    for chat_id, turn in old:
        assert not store.claim(UID, chat_id, turn["id"], AgentModel())
    assert totals(store)["unsettled_calls"] == 3


def test_local_admission_is_bounded_and_release_is_idempotent():
    capacity = AgentCapacity(2)
    leases = [capacity.acquire(), capacity.acquire()]
    with pytest.raises(AgentCapacityExceeded):
        capacity.acquire()
    leases[0].release()
    leases[0].release()
    replacement = capacity.acquire()
    with pytest.raises(AgentCapacityExceeded):
        capacity.acquire()
    replacement.release()
    leases[1].release()


def test_local_capacity_rejects_before_creating_a_turn_and_preserves_replay(api, monkeypatch):
    client, store, calls = api
    capacity = AgentCapacity(1)
    monkeypatch.setattr(agent, "agent_capacity", capacity)
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "first", "bookmark_id": "bm1"}
    held = capacity.acquire()
    try:
        response = client.post("/agent", json=payload, headers=AUTH)
        assert response.status_code == 503 and response.headers["retry-after"] == "5"
        assert store.get_chat(UID, chat_id)["turn_count"] == 0
        assert not calls
    finally:
        held.release()
    assert "event: final" in client.post("/agent", json=payload, headers=AUTH).text
    held = capacity.acquire()
    try:
        assert client.post("/agent", json=payload, headers=AUTH).json()["response"] == "A helpful answer"
    finally:
        held.release()
    assert len(calls) == 1


def test_owner_capacity_failure_unlocks_unclaimed_turn_and_does_not_call_model(api):
    client, store, calls = api
    for i in range(2):
        chat_id, turn = pending(store, request_id=f"running-{i}")
        store.claim(UID, chat_id, turn["id"], AgentModel())
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "busy", "bookmark_id": "bm1"}
    response = client.post("/agent", json=payload, headers=AUTH)
    assert "event: error" in response.text and "already running" in response.text
    assert not calls and totals(store)["calls"] == 2
    assert store.list_turns(UID, chat_id)["turns"][0]["status"] == "failed"
    assert pending(store, chat_id=chat_id, request_id="unlocked")[1]["status"] == "pending"


def test_response_never_entered_releases_pending_turn_without_a_paid_claim(api, monkeypatch):
    client, store, calls = api
    capacity = AgentCapacity(1)
    monkeypatch.setattr(agent, "agent_capacity", capacity)
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    payload = agent.AgentRequest(chat_id=chat_id, question="Hi", client_request_id="never-started", bookmark_id="bm1")
    request = Request({"type": "http", "headers": [(b"authorization", b"Bearer verified")], "client": ("test", 123)})
    response = agent.run_agent.__wrapped__(request, payload)

    async def run():
        async def send(message):
            # Fail the initial HTTP response before body_iterator is entered.
            raise OSError("Client left before response headers")
        async def receive():
            return {"type": "http.disconnect"}
        with pytest.raises(ClientDisconnect):
            await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
        assert [item async for item in response.body_iterator] == []

    anyio.run(run)
    assert not calls
    assert not (store.db.collection("users").document(UID).get().to_dict() or {}).get("agent_usage")
    assert store.list_turns(UID, chat_id)["turns"][0]["status"] == "failed"
    assert store.db.collection("users").document(UID).collection("bookmarks").document("bm1").get().exists
    capacity.acquire().release()
