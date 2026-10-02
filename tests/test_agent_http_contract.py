"""HTTP binding of private agent detail, pagination, Stop and admission errors."""
from copy import deepcopy
from dataclasses import replace
import pytest
from app.api.routers import agent, chat_history
from app.core import security
from app.core.rate_limit import api_uid_limiter
from app.services.agent_runs import AgentRunStore
from app.services.agent_policy import AgentPolicy
from app.services.agent_runtime import AgentCapacity
from app.services.llm.agent_client import AgentModel
from app.services.llm.provider_runtime import ProviderCancelled
from adapter_test_support import http_adapter, api_adapter, login
from test_agent_runs import pending
from test_chat_history import FakeDocumentRef


@pytest.fixture
def agent_http(http_adapter, monkeypatch):
    h = http_adapter
    monkeypatch.setattr(agent, "db_firestore", h.db)
    monkeypatch.setattr(chat_history, "db_firestore", h.db)
    h.db.collection("users").document("owner").set({"tier": "pro"})
    h.db.collection("users").document("stranger").set({"tier": "pro"})
    h.store = AgentRunStore(h.db)
    h.chat, h.turn = pending(h.store, uid="owner")
    h.agent_id = "a" * 32
    h.token = "producer-one"
    h.store.claim(
        "owner",
        h.chat,
        h.turn["id"],
        AgentModel(),
        policy=replace(AgentPolicy(), delegation=True).snapshot(),
        run_token=h.token,
        reservation=(100, 100),
    )
    for i in range(7):
        h.store.publish_agent(
            "owner",
            h.chat,
            h.turn["id"],
            run_token=h.token,
            agent_id=h.agent_id,
            patch={
                "assignment": {"goal": "Owner private assignment"},
                "status": "working",
            },
            message={"role": "assistant", "text": "Message " + str(i)},
            event_id="e" + str(i),
        )
    h.base = f"/agent/chats/{h.chat}/turns/{h.turn['id']}"
    return h


def test_detail_pages_are_owner_bound_and_never_start_provider(agent_http):
    h = agent_http
    before = deepcopy(h.db.documents)
    cursor = 0
    messages = []
    while True:
        response = h.client.get(
            h.base + "/agents/" + h.agent_id,
            params={"after": cursor, "limit": 3},
            headers=login("owner"),
        )
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "private, no-store"
        data = response.json()
        assert data["agent"]["id"] == h.agent_id
        assert data["agent"]["assignment"]["goal"] == "Owner private assignment"
        assert 1 <= len(data["messages"]) <= 3
        messages.extend(data["messages"])
        cursor = data["messages"][-1]["seq"]
        if not data["has_more"]:
            break
    assert [m["text"] for m in messages] == ["Message " + str(i) for i in range(7)]
    for headers, path, status in [
        ({}, h.base, 401),
        (login("stranger"), h.base, 404),
        (login("owner"), h.base.replace(h.turn["id"], "f" * 32), 404),
    ]:
        assert (
            h.client.get(path + "/agents/" + h.agent_id, headers=headers).status_code
            == status
        )
    for query in ({"after": -1}, {"limit": 0}, {"limit": 51}):
        assert (
            h.client.get(
                h.base + "/agents/" + h.agent_id, params=query, headers=login("owner")
            ).status_code
            == 422
        )
    assert h.db.documents == before


def test_stop_fences_only_bound_turn_repeatedly_and_rejects_late_worker(agent_http):
    h = agent_http
    other_chat, other_turn = pending(h.store, uid="owner", request_id="control")
    h.store.claim(
        "owner",
        other_chat,
        other_turn["id"],
        AgentModel(),
        policy=replace(AgentPolicy(), delegation=True).snapshot(),
        run_token="other",
        reservation=(100, 100),
    )
    control = deepcopy(
        h.store.receipt_ref("owner", other_chat, other_turn["id"]).get().to_dict()
    )
    assert h.client.post(h.base + "/stop", headers=login("stranger")).status_code == 404
    assert (
        not h.store.receipt_ref("owner", h.chat, h.turn["id"])
        .get()
        .to_dict()
        .get("cancel_requested")
    )
    for _ in range(2):
        response = h.client.post(h.base + "/stop", headers=login("owner"))
        assert response.status_code == 200 and response.json() == {"status": "stopping"}
        assert response.headers["cache-control"] == "private, no-store"
    assert (
        h.store.receipt_ref("owner", h.chat, h.turn["id"])
        .get()
        .to_dict()["cancel_requested"]
        is True
    )
    assert (
        h.store.receipt_ref("owner", other_chat, other_turn["id"]).get().to_dict()
        == control
    )
    with pytest.raises(ProviderCancelled):
        h.store.publish_agent(
            "owner",
            h.chat,
            h.turn["id"],
            run_token=h.token,
            agent_id=h.agent_id,
            patch={"status": "completed"},
        )
    assert (
        h.store.agent_ref("owner", h.chat, h.turn["id"], h.agent_id)
        .get()
        .to_dict()["status"]
        == "working"
    )


@pytest.mark.parametrize(
    "tier,role,expected",
    [("free", "", 403), ("plus", "", 403), ("pro", "", 200), ("free", "admin", 200)],
)
def test_detail_and_stop_use_real_tier_policy(agent_http, tier, role, expected):
    h = agent_http
    h.db.collection("users").document("owner").update({"tier": tier, "role": role})
    security.invalidate_tier_cache("owner")
    before = deepcopy(h.db.documents)
    assert (
        h.client.get(
            h.base + "/agents/" + h.agent_id, headers=login("owner")
        ).status_code
        == expected
    )
    assert (
        h.client.post(h.base + "/stop", headers=login("owner")).status_code == expected
    )
    if expected == 403:
        assert h.db.documents == before


def test_agent_role_outage_is_retryable_without_private_data_or_write(agent_http):
    h = agent_http
    before = deepcopy(h.db.documents)
    security.invalidate_tier_cache("owner")
    h.flags["outage"] = True
    for method, path in (
        ("GET", h.base + "/agents/" + h.agent_id),
        ("POST", h.base + "/stop"),
    ):
        response = h.client.request(method, path, headers=login("owner"))
        assert response.status_code == 503, response.text
        assert "private" not in response.text
    assert h.db.documents == before


def test_actual_agent_capacity_through_main_preserves_retry_header(
    http_adapter, monkeypatch
):
    h = http_adapter
    monkeypatch.setattr(agent, "db_firestore", h.db)
    h.db.collection("users").document("owner").set({"tier": "pro"})
    store = AgentRunStore(h.db)
    chat = store.create_chat("owner", execution_mode="agent")["id"]
    # Model config reads use ordinary SDK keyword arguments, not a policy mock.
    original = FakeDocumentRef.get
    monkeypatch.setattr(
        FakeDocumentRef,
        "get",
        lambda self, transaction=None, **kwargs: original(
            self, transaction=transaction
        ),
    )
    capacity = AgentCapacity(1)
    monkeypatch.setattr(agent, "agent_capacity", capacity)
    held = capacity.acquire()
    before = deepcopy(h.db.documents)
    try:
        response = h.client.post(
            "/agent",
            headers={**login("owner"), "Retry-After": "evil"},
            json={
                "chat_id": chat,
                "question": "Hello",
                "client_request_id": "request",
                "bookmark_id": "bookmark",
            },
        )
    finally:
        held.release()
    assert response.status_code == 503, response.text
    assert response.headers["retry-after"] == "5"
    assert (
        "capacity" in response.json()["error"].lower()
        or "busy" in response.json()["error"].lower()
    )
    assert store.get_chat("owner", chat)["turn_count"] == 0
    assert not any("agent_receipts" in p for p in h.db.documents)
    assert h.db.documents == before


def test_actual_api_uid_limit_through_main_preserves_only_server_retry_header(
    api_adapter,
):
    h = api_adapter
    for _ in range(120):
        api_uid_limiter.check("owner", "get", 120)
    before = deepcopy(h.db.documents)
    response = h.client.get(
        "/api/v1/consensus/runs/" + "a" * 32,
        headers={"X-API-Key": h.key, "Retry-After": "evil"},
    )
    assert response.status_code == 429
    assert response.json() == {"error": "Consensus API rate limit exceeded"}
    assert response.headers["retry-after"] == "60"
    after = deepcopy(h.db.documents)
    for path, data in after.items():
        if path[0] == "api_consensus_keys":
            data.pop("last_used_at", None)
    assert after == before  # Only authentication metadata may change.
    # Another account remains independent and reaches the real missing-run guard.
    assert (
        h.client.get(
            "/api/v1/consensus/runs/" + "a" * 32, headers={"X-API-Key": h.other_key}
        ).status_code
        == 404
    )
