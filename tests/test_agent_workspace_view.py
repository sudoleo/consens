"""The workspace from the browser (routers/agent_workspace.py, since
2026-10-27): the live view's WebSocket through to the VM's gateway, the
user's takeover and signing its browser out. The VM is FakeVM
(test_agent_vm.py), the gateway a fake WebSocket; nothing calls Sprites.
"""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.routers import agent as agent_router
from app.api.routers import agent_workspace as workspace_router
from app.api.routers import chat_history
from app.core.rate_limit import api_uid_limiter, limiter
from app.services import agent_vm, agent_vm_time, agent_workspace
from test_agent_runs import AUTH, UID, pending, store  # noqa: F401  (fixture)
from test_agent_vm import _admin_allowance, fake_vm  # noqa: F401  (fixtures)

NAME = agent_vm.workspace_name(UID)


class Gateway:
    """The VM gateway's side: its states, then the VNC server's bytes."""

    def __init__(self, frames):
        self.frames, self.received, self.closed, self.url = list(frames), [], False, None

    async def send(self, data):
        self.received.append(data)

    async def close(self):
        self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        import asyncio
        if not self.frames:
            # A VNC server sends again only when asked: it stays open.
            await asyncio.sleep(3600)
        return self.frames.pop(0)


@pytest.fixture
def view_api(monkeypatch, store, fake_vm):
    limiter.reset()
    api_uid_limiter.reset()
    # An admin's day: no cap on VM time unless a test sets one.
    monkeypatch.setattr(agent_vm_time, "daily_limit", lambda uid: None)
    for module in (chat_history, workspace_router):
        monkeypatch.setattr(module, "verify_user_token", lambda token: UID if token == "verified" else "other-user",
                            raising=False)
    monkeypatch.setattr(chat_history, "db_firestore", store.db)
    monkeypatch.setattr(workspace_router, "db_firestore", store.db)
    monkeypatch.setattr(agent_router, "db_firestore", store.db)
    monkeypatch.setattr(workspace_router, "_store", lambda: store)
    monkeypatch.setattr(workspace_router, "require_agent_access", lambda uid: None)
    allowed = {UID}
    monkeypatch.setattr(workspace_router, "vm_allowed", lambda uid: uid in allowed)
    gateway = Gateway([json.dumps({"state": "starting"}), json.dumps({"state": "ready"}), b"RFB 003.008\n"])

    async def connect(url):
        gateway.url = url
        return gateway
    monkeypatch.setattr(workspace_router, "connect_upstream", connect)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(workspace_router.router)
    return TestClient(app), store, gateway, allowed


def test_the_view_signs_in_with_its_first_message_and_carries_vnc_both_ways(view_api, fake_vm):
    client, store, gateway, _ = view_api
    with client.websocket_connect("/agent/workspace/view") as ws:
        ws.send_text(json.dumps({"id_token": "verified"}))
        states = [json.loads(ws.receive_text())["state"] for _ in range(3)]
        banner = ws.receive_bytes()
        ws.send_bytes(b"RFB 003.008\n")
    assert states == ["connecting", "starting", "ready"] and banner == b"RFB 003.008\n"
    # The gateway behind the VM's private address; the provider's token never reaches the browser.
    assert gateway.url == f"wss://{NAME}-test.sprites.app/vnc" and gateway.closed
    assert b"RFB 003.008\n" in gateway.received
    # The view opens the workspace even before a chat used it: recorded, created, its tools up to date.
    assert agent_workspace.record(store.db, UID)["name"] == NAME and "lease" not in agent_workspace.record(store.db, UID)
    assert ("ensure", NAME) in fake_vm.calls
    assert fake_vm.vms[NAME]["services"]["view"]["http_port"] == agent_workspace.GATEWAY_PORT


def open_view(client):
    ws = client.websocket_connect("/agent/workspace/view").__enter__()
    ws.send_text(json.dumps({"id_token": "verified"}))
    assert [json.loads(ws.receive_text())["state"] for _ in range(3)] == ["connecting", "starting", "ready"]
    assert ws.receive_bytes() == b"RFB 003.008\n"
    return ws


def test_an_account_has_one_view_and_its_time_counts_as_vm_time(view_api, fake_vm, monkeypatch):
    """Security audit 2026-10-27: any number of views stayed open for an hour
    each and kept the VM awake without counting. Now the newest view wins,
    an older one ends with its reason, and the open time is VM time."""
    client, store, _, _ = view_api
    monkeypatch.setattr(agent_workspace, "VIEW_CHECK_SECONDS", 0.05)
    ws = open_view(client)
    # Another window opens the workspace: this view is no longer the account's.
    agent_workspace.claim_view(store, UID, 60)
    with pytest.raises(WebSocketDisconnect) as closed:
        ws.receive_bytes()
    assert closed.value.code == workspace_router.CLOSE_REPLACED
    assert agent_vm_time.used(store.db, UID) > 0


def test_a_view_never_runs_past_the_days_vm_time(view_api, fake_vm, monkeypatch):
    client, store, gateway, _ = view_api
    monkeypatch.setattr(agent_vm_time, "daily_limit", lambda uid: 100)
    agent_vm_time.charge(store, UID, 100)
    with client.websocket_connect("/agent/workspace/view") as ws:
        ws.send_text(json.dumps({"id_token": "verified"}))
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_text()
    assert closed.value.code == workspace_router.CLOSE_NO_TIME and fake_vm.calls == [] and gateway.url is None
    # With a little left, the view ends when it is used up.
    monkeypatch.setattr(agent_vm_time, "daily_limit", lambda uid: 101.5)
    ws = open_view(client)
    with pytest.raises(WebSocketDisconnect) as closed:
        ws.receive_bytes()
    assert closed.value.code == workspace_router.CLOSE_NO_TIME


def test_opening_the_view_is_rate_limited(view_api, fake_vm, monkeypatch):
    client, _, _, _ = view_api
    monkeypatch.setattr(workspace_router, "VIEWS_PER_MINUTE", 1)
    ws = open_view(client)
    ws.__exit__(None, None, None)
    with client.websocket_connect("/agent/workspace/view") as again:
        again.send_text(json.dumps({"id_token": "verified"}))
        with pytest.raises(WebSocketDisconnect) as closed:
            again.receive_text()
    assert closed.value.code == workspace_router.CLOSE_TOO_MANY


@pytest.mark.parametrize("first", ["", "not json", json.dumps({"id_token": "someone-else"}), json.dumps({})])
def test_a_view_without_an_allowed_sign_in_is_closed_before_the_vm(view_api, fake_vm, first):
    client, _, gateway, _ = view_api
    with client.websocket_connect("/agent/workspace/view") as ws:
        ws.send_text(first)
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_text()
    assert closed.value.code == 4403 and fake_vm.calls == [] and gateway.url is None


def test_the_view_says_so_when_the_vm_is_not_reachable(view_api, fake_vm):
    client, _, gateway, _ = view_api
    fake_vm.fail.add("ensure")
    with client.websocket_connect("/agent/workspace/view") as ws:
        ws.send_text(json.dumps({"id_token": "verified"}))
        assert [json.loads(ws.receive_text())["state"] for _ in range(2)] == ["connecting", "error"]
    assert gateway.url is None


def test_taking_over_and_handing_back_write_the_vms_control_file(view_api, fake_vm, monkeypatch):
    client, store, _, allowed = view_api
    assert client.post("/agent/workspace/control", json={"holder": "user"}, headers=AUTH).status_code == 404
    agent_workspace.record_for_view(store, UID, provider="fake")
    fake_vm.vms[NAME] = {"files": {}, "checkpoints": []}
    monkeypatch.setattr(agent_workspace.time, "time", lambda: 5000.0)
    taken = client.post("/agent/workspace/control", json={"holder": "user"}, headers=AUTH)
    assert taken.status_code == 200 and taken.json() == {"holder": "user", "seconds": agent_workspace.CONTROL_SECONDS}
    control = json.loads(fake_vm.vms[NAME]["files"][agent_workspace.CONTROL_PATH])
    assert control == {"holder": "user", "until": 5000.0 + agent_workspace.CONTROL_SECONDS}
    # The agent pauses completely: the server holds its VM calls (the record),
    # the browser refuses (control.json), then the VM freezes what of it runs,
    # started without the agent's mark so it is not frozen itself.
    assert agent_workspace.record(store.db, UID)["control"] == control
    assert agent_workspace.user_has_browser(store.db, UID, now=5000.0)
    assert [call for call in fake_vm.calls if call[0] in {"write", "exec"}] == [
        ("write", NAME, agent_workspace.CONTROL_PATH),
        ("exec", NAME, agent_workspace.PAUSE_COMMAND, agent_vm.HOME, agent_workspace.PAUSE_START_SECONDS)]
    assert fake_vm.unmarked == [agent_workspace.PAUSE_COMMAND]
    assert client.post("/agent/workspace/control", json={"holder": "agent"}, headers=AUTH).status_code == 200
    assert json.loads(fake_vm.vms[NAME]["files"][agent_workspace.CONTROL_PATH])["holder"] == "agent"
    assert agent_workspace.record(store.db, UID)["control"] == {"holder": "agent", "until": 0}
    assert not agent_workspace.user_has_browser(store.db, UID, now=5000.0)
    # Handing back starts nothing: pause.py sees control.json and lets go.
    assert fake_vm.unmarked == [agent_workspace.PAUSE_COMMAND]
    assert client.post("/agent/workspace/control", json={"holder": "root"}, headers=AUTH).status_code == 422
    allowed.clear()
    assert client.post("/agent/workspace/control", json={"holder": "user"}, headers=AUTH).status_code == 403
    assert client.get("/agent/workspace", headers=AUTH).json() == {"available": False}


def test_signing_the_browser_out_waits_for_the_agent_and_deletes_its_profile(view_api, fake_vm):
    from datetime import datetime, timedelta, timezone
    client, store, _, _ = view_api
    # No workspace yet: nothing to sign out.
    assert client.post("/agent/workspace/reset-browser", headers=AUTH).json() == {"status": "reset"}
    assert fake_vm.calls == []
    chat, _ = pending(store)
    agent_workspace.claim(store, UID, chat, "running", provider="fake")
    assert client.get("/agent/workspace", headers=AUTH).json() == {"available": True, "in_use": True}
    busy = client.post("/agent/workspace/reset-browser", headers=AUTH)
    assert busy.status_code == 409 and busy.json()["code"] == "running"
    agent_workspace.ref(store.db, UID).update({"lease": {
        "chat_id": chat, "turn_id": "running", "until": datetime.now(timezone.utc) - timedelta(seconds=1)}})
    fake_vm.vms[NAME] = {"files": {}, "checkpoints": []}
    assert client.post("/agent/workspace/reset-browser", headers=AUTH).json() == {"status": "reset"}
    [command] = [call[2] for call in fake_vm.calls if call[0] == "exec"]
    assert f"rm -rf {agent_workspace.BROWSER_PROFILE}" in command and "pkill" in command
    # No checkpoint from before brings the sign-ins back (restorable).
    assert isinstance(agent_workspace.record(store.db, UID).get("restore_floor"), datetime)
