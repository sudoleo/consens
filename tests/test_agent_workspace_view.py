"""The workspace from the browser (routers/agent_workspace.py, since
2026-10-27): the live view's WebSocket through to the browser VM's relay on
the provider's exec API, the user's takeover and signing its browser out.
The VMs are FakeVM (test_agent_vm.py), the exec socket a fake; nothing calls
Sprites.
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
BROWSER = agent_vm.browser_name(UID)


class Relay:
    """The relay's exec socket: its states as JSON lines on stderr (0x02),
    then the VNC server's bytes on stdout (0x01)."""

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
    gateway = Relay([json.dumps({"type": "session_info", "session_id": "1"}),
                     b"\x02" + json.dumps({"state": "starting"}).encode() + b"\n{\"state\": ",
                     b"\x02\"ready\"}\n", b"\x01RFB 003.008\n"])

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
    # The relay on the provider's exec API (security audit 2026-10-27,
    # finding 1): the token goes to api.sprites.dev only, never to an address
    # of the VM; the view's bytes reach its stdin (0x00), which ends (0x04).
    assert gateway.url.startswith(f"wss://api.sprites.dev/v1/sprites/{BROWSER}/exec?") and gateway.closed
    assert b"\x00RFB 003.008\n" in gateway.received and gateway.received[-1] == b"\x04"
    # The view opens the browser VM even before a chat used it: both VMs
    # recorded first, the browser created with the open web, its tools up to date.
    record = agent_workspace.record(store.db, UID)
    assert record["name"] == NAME and record["browser"] == BROWSER and "lease" not in record
    assert ("ensure", BROWSER) in fake_vm.calls and ("ensure", NAME) not in fake_vm.calls
    assert fake_vm.vms[BROWSER]["policy"] == agent_vm.BROWSER_RULES
    assert fake_vm.vms[BROWSER]["files"][agent_workspace.VERSION_PATH] == agent_workspace.BROWSER_VERSION.encode()


# --- The user's terminal on the workbench (since 2026-10-28) --------------------------

def terminal_api(view_api, monkeypatch, frames):
    """The view API with the terminal's exec socket: a fake TTY that sends
    ``frames`` (raw output, or the provider's JSON messages)."""
    client, store, _, allowed = view_api
    shell = Relay(frames)

    async def connect(url):
        shell.url = url
        return shell
    monkeypatch.setattr(workspace_router, "connect_upstream", connect)
    return client, store, shell


def test_the_terminal_is_a_shell_with_the_agents_rights_in_the_users_size(view_api, fake_vm, monkeypatch):
    client, store, shell = terminal_api(view_api, monkeypatch, [b"agent@workbench:~$ "])
    with client.websocket_connect("/agent/workspace/terminal") as ws:
        ws.send_text(json.dumps({"id_token": "verified", "cols": 120, "rows": 30}))
        assert [json.loads(ws.receive_text())["state"] for _ in range(2)] == ["connecting", "ready"]
        assert ws.receive_bytes() == b"agent@workbench:~$ "
        ws.send_bytes(b"ls\r")
        ws.send_text(json.dumps({"type": "resize", "cols": 100, "rows": 40}))
        # Only two checked numbers make a resize; nothing else goes on.
        for ignored in (json.dumps({"type": "resize", "cols": "100; rm", "rows": 40}),
                        json.dumps({"type": "resize", "cols": 9999, "rows": 40}), json.dumps({"type": "other"}),
                        "not json"):
            ws.send_text(ignored)
    assert shell.received == [b"ls\r", json.dumps({"type": "resize", "cols": 100, "rows": 40})]
    assert shell.url.endswith("cmd=terminal") and shell.closed
    # A login shell as the agent's user (agent-run --terminal), in its home, with a TTY of the user's size.
    [(_, name, argv, tty)] = [call for call in fake_vm.calls if call[0] == "exec_url"]
    assert name == NAME and tty == (120, 30)
    assert argv[:5] == ("sudo", "-n", "/bin/bash", agent_vm.AGENT_RUN, "--terminal")
    assert argv[-3:] == (agent_vm.HOME, "bash", "-l")
    # One terminal per account, apart from the browser's view (its time counts
    # like the view's: _carry, test_an_account_has_one_view_and_...).
    record = agent_workspace.record(store.db, UID)
    assert record["terminal"]["id"] and "view" not in record


def test_the_terminal_ends_with_its_shell_and_leaves_a_running_chats_network_rules(view_api, fake_vm, monkeypatch):
    client, _, shell = terminal_api(view_api, monkeypatch, [b"bye\r\n", json.dumps({"type": "exit", "exit_code": 0})])
    fake_vm.vms[NAME] = {"files": {}, "checkpoints": [], "policy": ["the running chat's rules"]}
    with client.websocket_connect("/agent/workspace/terminal") as ws:
        ws.send_text(json.dumps({"id_token": "verified", "cols": "wide", "rows": 30}))
        assert [json.loads(ws.receive_text())["state"] for _ in range(2)] == ["connecting", "ready"]
        assert ws.receive_bytes() == b"bye\r\n"
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_bytes()
    assert closed.value.code == 1000
    # An unusable size falls back to 80 x 24; an existing workbench keeps its rules.
    assert [call[3] for call in fake_vm.calls if call[0] == "exec_url"] == [(80, 24)]
    assert fake_vm.vms[NAME]["policy"] == ["the running chat's rules"]
    assert not [call for call in fake_vm.calls if call[0] in {"ensure", "policy"} and call[1] == NAME]


def test_the_terminal_needs_the_vm_and_counts_against_the_rate_limit(view_api, fake_vm, monkeypatch):
    client, _, shell = terminal_api(view_api, monkeypatch, [])
    allowed = view_api[3]
    allowed.clear()
    with client.websocket_connect("/agent/workspace/terminal") as ws:
        ws.send_text(json.dumps({"id_token": "verified", "cols": 80, "rows": 24}))
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_text()
    assert closed.value.code == 4403 and shell.url is None and fake_vm.calls == []


def test_the_view_connects_to_the_providers_api_only(monkeypatch):
    import asyncio
    with pytest.raises(ValueError):
        asyncio.run(workspace_router.connect_upstream(f"wss://{BROWSER}-x1.sprites.app/vnc"))


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


def test_taking_over_and_handing_back_write_the_vms_control_files(view_api, fake_vm, monkeypatch):
    client, store, _, allowed = view_api
    assert client.post("/agent/workspace/control", json={"holder": "user"}, headers=AUTH).status_code == 404
    agent_workspace.record_for_view(store, UID, provider="fake")
    fake_vm.vms[NAME] = {"files": {}, "checkpoints": []}
    fake_vm.vms[BROWSER] = {"files": {}, "checkpoints": []}
    monkeypatch.setattr(agent_workspace.time, "time", lambda: 5000.0)
    taken = client.post("/agent/workspace/control", json={"holder": "user"}, headers=AUTH)
    assert taken.status_code == 200 and taken.json() == {"holder": "user", "seconds": agent_workspace.CONTROL_SECONDS}
    control = json.loads(fake_vm.vms[BROWSER]["files"][agent_workspace.BROWSER_CONTROL])
    assert control == {"holder": "user", "until": 5000.0 + agent_workspace.CONTROL_SECONDS}
    assert json.loads(fake_vm.vms[NAME]["files"][agent_workspace.CONTROL_PATH]) == control
    # The agent pauses completely: the server holds its calls (the record),
    # the browser refuses (control.json there), then the workbench freezes
    # what of the agent runs there, by its user (pause.py, as root).
    assert agent_workspace.record(store.db, UID)["control"] == control
    assert agent_workspace.user_has_browser(store.db, UID, now=5000.0)
    assert [call for call in fake_vm.calls if call[0] in {"write", "exec"}] == [
        ("write", BROWSER, agent_workspace.BROWSER_CONTROL), ("write", NAME, agent_workspace.CONTROL_PATH),
        ("exec", NAME, agent_workspace.PAUSE_COMMAND, agent_vm.SERVER_HOME, agent_workspace.PAUSE_START_SECONDS)]
    assert fake_vm.server == [agent_workspace.PAUSE_COMMAND]
    assert all(path.startswith("/home/sprite/.consens/") for _, path in fake_vm.server_files)
    assert client.post("/agent/workspace/control", json={"holder": "agent"}, headers=AUTH).status_code == 200
    assert json.loads(fake_vm.vms[BROWSER]["files"][agent_workspace.BROWSER_CONTROL])["holder"] == "agent"
    assert json.loads(fake_vm.vms[NAME]["files"][agent_workspace.CONTROL_PATH])["holder"] == "agent"
    assert agent_workspace.record(store.db, UID)["control"] == {"holder": "agent", "until": 0}
    assert not agent_workspace.user_has_browser(store.db, UID, now=5000.0)
    # Handing back starts nothing: pause.py sees control.json and lets go.
    assert fake_vm.server == [agent_workspace.PAUSE_COMMAND]
    # A workbench no chat made has nothing to freeze.
    del fake_vm.vms[NAME]
    fake_vm.server.clear()
    assert client.post("/agent/workspace/control", json={"holder": "user"}, headers=AUTH).status_code == 200
    assert fake_vm.server == [] and NAME not in fake_vm.vms
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
    fake_vm.vms[BROWSER] = {"files": {}, "checkpoints": []}
    assert client.post("/agent/workspace/reset-browser", headers=AUTH).json() == {"status": "reset"}
    # On the browser VM, as the server.
    [(name, command)] = [(call[1], call[2]) for call in fake_vm.calls if call[0] == "exec"]
    assert name == BROWSER and f"rm -rf {agent_workspace.BROWSER_PROFILE}" in command and "pkill" in command
    assert fake_vm.server == [command]
    # No checkpoint from before brings the sign-ins back (restorable).
    assert isinstance(agent_workspace.record(store.db, UID).get("restore_floor"), datetime)
