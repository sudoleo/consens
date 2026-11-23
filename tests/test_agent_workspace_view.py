"""The workspace from the browser (routers/agent_workspace.py): the live
view's WebSocket through to the relay on the workspace's VM over the
provider's exec API, the user's takeover and signing its browser out.
The VMs are FakeVM (test_agent_vm.py), the exec socket a fake; nothing calls
Sprites.
"""
import json
import time

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
# What whoever waits for the browser of a VM made just now is told.
NEW_VM_SECONDS = agent_workspace.START_SECONDS["setup"] + agent_workspace.START_SECONDS["install"]


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
    # The relay on the provider's exec API: the token goes to
    # api.sprites.dev only, never to an address of the VM; the view's bytes reach its stdin (0x00), which ends (0x04).
    assert gateway.url.startswith(f"wss://api.sprites.dev/v1/sprites/{NAME}/exec?") and gateway.closed
    assert b"\x00RFB 003.008\n" in gateway.received and gateway.received[-1] == b"\x04"
    # The view opens the workspace even before a chat used it: recorded
    # first, created with the open web, its tools up to date.
    record = agent_workspace.record(store.db, UID)
    assert record["name"] == NAME and "browser" not in record and "lease" not in record
    assert ("ensure", NAME) in fake_vm.calls
    assert fake_vm.vms[NAME]["policy"] == agent_vm.RULES
    assert fake_vm.vms[NAME]["files"][agent_workspace.VERSION_PATH] == agent_workspace.VERSION.encode()


def test_the_views_start_says_about_when_it_ends_and_ends_with_ready(view_api, fake_vm):
    """The view counts the browser's start down over its
    skeleton (start-progress.js): a VM made just now needs its setup and
    then the browser's own installation (agent_workspace.START_SECONDS:
    with the setup's time alone the bar stood at "Almost done…" for the
    whole installation), and the relay's starting carries the
    estimate. Once ready, the start is over for everyone who waits."""
    from datetime import datetime, timezone
    client, _, _, _ = view_api
    with client.websocket_connect("/agent/workspace/view") as ws:
        ws.send_text(json.dumps({"id_token": "verified"}))
        messages = [json.loads(ws.receive_text()) for _ in range(3)]
        ws.receive_bytes()
        assert agent_workspace.start_until(UID) is None
    assert [message["state"] for message in messages] == ["connecting", "starting", "ready"]
    left = (datetime.fromisoformat(messages[1]["until"]) - datetime.now(timezone.utc)).total_seconds()
    assert NEW_VM_SECONDS - 10 < left <= NEW_VM_SECONDS
    assert "until" not in messages[0] and "until" not in messages[2]


def test_the_view_counts_down_while_the_server_wakes_the_vm(view_api, fake_vm, monkeypatch):
    """A VM that sleeps takes its wake before the relay's first state, and
    the view would show "Starting your workspace…" without a bar. While
    opening takes longer than WAKE_FIRST_SECONDS, "waking" carries the
    estimate, once per new one."""
    import time as clock
    from datetime import datetime, timezone
    opened = workspace_router._open

    def slow_open(uid, seconds, start=None):
        url = opened(uid, seconds, start)
        clock.sleep(0.4)
        return url
    monkeypatch.setattr(workspace_router, "_open", slow_open)
    monkeypatch.setattr(workspace_router, "WAKE_FIRST_SECONDS", 0.05)
    monkeypatch.setattr(workspace_router, "WAKE_LOOK_SECONDS", 0.05)
    client, _, _, _ = view_api
    with client.websocket_connect("/agent/workspace/view") as ws:
        ws.send_text(json.dumps({"id_token": "verified"}))
        messages = [json.loads(ws.receive_text()) for _ in range(4)]
        ws.receive_bytes()
    assert [message["state"] for message in messages] == ["connecting", "waking", "starting", "ready"]
    left = (datetime.fromisoformat(messages[1]["until"]) - datetime.now(timezone.utc)).total_seconds()
    assert NEW_VM_SECONDS - 10 < left <= NEW_VM_SECONDS
    assert messages[2]["until"] == messages[1]["until"]


def test_a_view_or_terminal_gone_before_its_first_state_ends_quietly():
    """A tab closed while it connects: the first state finds no socket, and
    the terminal's start ends without an error in the log."""
    import asyncio

    class Gone:
        def __init__(self, error):
            self.error = error

        async def send_text(self, text):
            raise self.error

    assert asyncio.run(workspace_router._state(Gone(WebSocketDisconnect(1005)), "connecting")) is False
    assert asyncio.run(workspace_router._state(Gone(RuntimeError("closed")), "connecting")) is False


# --- The user's terminal in the workspace ---------------------------------------------

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
    # like the view's: _carry, test_an_account_has_one_view_and_its_time_counts_as_vm_time).
    record = agent_workspace.record(store.db, UID)
    assert record["terminal"]["id"] and "view" not in record


def test_the_terminal_ends_with_its_shell_and_leaves_the_vm_as_it_is(view_api, fake_vm, monkeypatch):
    client, _, shell = terminal_api(view_api, monkeypatch, [b"bye\r\n", json.dumps({"type": "exit", "exit_code": 0})])
    fake_vm.vms[NAME] = {"files": {agent_workspace.VERSION_PATH: agent_workspace.VERSION.encode()},
                         "checkpoints": [], "policy": list(agent_vm.RULES)}
    with client.websocket_connect("/agent/workspace/terminal") as ws:
        ws.send_text(json.dumps({"id_token": "verified", "cols": "wide", "rows": 30}))
        assert [json.loads(ws.receive_text())["state"] for _ in range(2)] == ["connecting", "ready"]
        assert ws.receive_bytes() == b"bye\r\n"
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_bytes()
    assert closed.value.code == 1000
    # An unusable size falls back to 80 x 24; a workspace at this version is
    # not set up again, nor are its rules touched.
    assert [call[3] for call in fake_vm.calls if call[0] == "exec_url"] == [(80, 24)]
    assert fake_vm.vms[NAME]["policy"] == agent_vm.RULES
    assert not [call for call in fake_vm.calls if call[0] in {"policy", "exec"}]


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
        asyncio.run(workspace_router.connect_upstream(f"wss://{NAME}-x1.sprites.app/vnc"))


def open_view(client):
    ws = client.websocket_connect("/agent/workspace/view").__enter__()
    ws.send_text(json.dumps({"id_token": "verified"}))
    assert [json.loads(ws.receive_text())["state"] for _ in range(3)] == ["connecting", "starting", "ready"]
    assert ws.receive_bytes() == b"RFB 003.008\n"
    return ws


def test_an_account_has_one_view_and_its_time_counts_as_vm_time(view_api, fake_vm, monkeypatch):
    """The newest view wins, an older one ends with its reason, and the open
    time is VM time: else any number of views could stay open for an hour
    each and keep the VM awake without counting."""
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


def _never_starts(monkeypatch):
    """The view's _open as against a VM the provider does not start: the
    gateway's 502 marks it (SpritesBackend) until something reaches it. The
    tries so far, and _open as it was."""
    opened, tries = workspace_router._open, []

    def stuck_open(uid, seconds, start=None):
        tries.append(uid)
        if agent_vm.unresponsive_status(NAME) is not None or len(tries) == 1:
            agent_vm.mark_unresponsive(NAME, 502)
            raise agent_vm.VMUnavailable("read: HTTP 502", 502)
        return opened(uid, seconds, start)
    monkeypatch.setattr(workspace_router, "_open", stuck_open)
    return tries


def test_the_view_waits_while_a_vm_that_did_not_start_is_brought_back(view_api, fake_vm, monkeypatch):
    """Prod 2026-11-20: the provider did not start the VM, the view said
    "not reachable" after 49 s, and "Reconnect" met the same answer while the
    server restored the VM behind it. The view now waits for that with
    "repairing" and about how long, and opens once the VM is reached again."""
    import threading
    from datetime import datetime, timezone
    client, _, gateway, _ = view_api
    tries = _never_starts(monkeypatch)
    monkeypatch.setattr(workspace_router, "REPAIR_LOOK_SECONDS", .02)
    # Its restore runs (agent_workspace.heal) and brings it back shortly.
    monkeypatch.setattr(agent_workspace, "healing", lambda uid: True)
    threading.Timer(.3, agent_vm.forget_unresponsive, args=(NAME,)).start()
    with client.websocket_connect("/agent/workspace/view") as ws:
        ws.send_text(json.dumps({"id_token": "verified"}))
        messages = [json.loads(ws.receive_text()) for _ in range(4)]
        assert ws.receive_bytes() == b"RFB 003.008\n"
    assert [message["state"] for message in messages] == ["connecting", "repairing", "starting", "ready"]
    left = (datetime.fromisoformat(messages[1]["until"]) - datetime.now(timezone.utc)).total_seconds()
    assert workspace_router.REPAIR_SECONDS - 10 < left <= workspace_router.REPAIR_SECONDS
    assert len(tries) == 2 and gateway.url is not None


def test_a_vm_that_nothing_brings_back_ends_the_view_with_its_reason(view_api, fake_vm, monkeypatch):
    """No probe asks the VM and no restore runs (none it may go back to, or
    the provider refused them all): the view says so with a close code of
    its own, since "Reconnect" may help later, not now."""
    client, _, gateway, _ = view_api
    _never_starts(monkeypatch)
    with client.websocket_connect("/agent/workspace/view") as ws:
        ws.send_text(json.dumps({"id_token": "verified"}))
        assert [json.loads(ws.receive_text())["state"] for _ in range(2)] == ["connecting", "stuck"]
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_text()
    assert closed.value.code == workspace_router.CLOSE_STUCK and gateway.url is None
    # A VM still stuck after its restore ended ends the same way.
    monkeypatch.setattr(workspace_router, "REPAIR_LOOK_SECONDS", .02)
    healing = [True]
    monkeypatch.setattr(agent_workspace, "healing", lambda uid: healing[0])
    with client.websocket_connect("/agent/workspace/view") as ws:
        ws.send_text(json.dumps({"id_token": "verified"}))
        assert [json.loads(ws.receive_text())["state"] for _ in range(2)] == ["connecting", "repairing"]
        healing[0] = False
        assert json.loads(ws.receive_text())["state"] == "stuck"
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_text()
    assert closed.value.code == workspace_router.CLOSE_STUCK


def _stuck_with_a_file(store, fake_vm):
    """The account's workspace with a file on it, which this process knows as stuck."""
    agent_workspace.record_for_view(store, UID, provider="fake")
    agent_workspace.open_workspace(fake_vm.backend(), UID, db=store.db)
    fake_vm.vms[NAME]["files"]["/home/agent/notes.md"] = b"old"
    agent_vm.mark_unresponsive(NAME, 502)


def test_a_stuck_workspace_gets_a_new_computer_on_the_users_word(view_api, fake_vm, monkeypatch):
    """Prod 2026-11-21: after the restore failed four times the user could
    only wait for someone to set the workspace up anew by hand. The view's
    "stuck" now offers that itself (workspace-view.js startNew). Only for a
    workspace this process knows as stuck, never under a message, once an
    hour, behind the view's own locks; the request answers at once and the
    work runs behind it."""
    import threading
    from datetime import datetime, timezone
    from app.services import workspace_guard
    client, store, _, allowed = view_api
    release, threads = threading.Event(), []
    replace, replace_later = agent_workspace.replace, agent_workspace.replace_later

    def held(db, uid, **kwargs):
        release.wait(10)
        return replace(db, uid, **kwargs)

    def later(*args, **kwargs):
        threads.append(replace_later(*args, **kwargs))
        return threads[-1]
    monkeypatch.setattr(agent_workspace, "replace", held)
    monkeypatch.setattr(agent_workspace, "replace_later", later)

    def ask():
        # Each on its own: the route's pace (a few a minute) is not what this asks about.
        limiter.reset()
        return client.post("/agent/workspace/replace", headers=AUTH)
    _stuck_with_a_file(store, fake_vm)
    # Reached again meanwhile: nothing to replace, and nothing is.
    agent_vm.forget_unresponsive(NAME)
    assert ask().json() == {"replacing": False} and threads == []
    agent_vm.mark_unresponsive(NAME, 502)
    chat, _ = pending(store)
    agent_workspace.claim(store, UID, chat, "turn", provider="fake")
    answer = ask()
    assert answer.status_code == 409 and answer.json()["code"] == "running" and threads == []
    agent_workspace.release(store, UID, "turn")
    # The view's own locks: the safety rules and the day's VM time.
    with monkeypatch.context() as patch:
        patch.setattr(workspace_guard, "status", lambda uid: workspace_guard.Status("locked", None, "rule"))
        assert ask().status_code == 403
    with monkeypatch.context() as patch:
        patch.setattr(agent_vm_time, "daily_limit", lambda uid: 100)
        agent_vm_time.charge(store, UID, 100)
        assert ask().status_code == 403
    assert threads == [] and "/home/agent/notes.md" in fake_vm.vms[NAME]["files"]
    answer = ask()
    assert answer.status_code == 200 and answer.json()["replacing"] is True
    left = (datetime.fromisoformat(answer.json()["until"]) - datetime.now(timezone.utc)).total_seconds()
    assert NEW_VM_SECONDS - 10 < left <= NEW_VM_SECONDS
    # A second click while it runs starts no second one.
    assert ask().json()["replacing"] is True and len(threads) == 1
    release.set()
    threads[0].join(10)
    assert [call for call in fake_vm.calls if call[0] == "delete"] == [("delete", NAME)]
    files = fake_vm.vms[NAME]["files"]
    assert "/home/agent/notes.md" not in files
    assert files[agent_workspace.VERSION_PATH] == agent_workspace.VERSION.encode()
    assert fake_vm.warmed == [NAME] and fake_vm.rested == [NAME]
    # The new one stuck too within the hour: its restore is the way, not another new one.
    agent_vm.mark_unresponsive(NAME, 502)
    answer = ask()
    assert answer.status_code == 429 and answer.json()["code"] == "recent" and len(threads) == 1
    allowed.clear()
    assert ask().status_code == 403


def test_the_view_and_the_terminal_wait_for_the_new_computer(view_api, fake_vm, monkeypatch):
    """While the new computer is made, whoever opens the view hears
    "replacing" with about how long (the bar of a first setup) and gets the
    picture once it stands; the terminal waits the same way. Neither meets a
    VM half deleted or half set up."""
    import threading
    from datetime import datetime, timezone
    client, store, gateway, _ = view_api
    monkeypatch.setattr(workspace_router, "REPAIR_LOOK_SECONDS", .02)
    release, replace = threading.Event(), agent_workspace.replace

    def held(db, uid, **kwargs):
        release.wait(10)
        return replace(db, uid, **kwargs)
    monkeypatch.setattr(agent_workspace, "replace", held)
    _stuck_with_a_file(store, fake_vm)
    fake_vm.calls.clear()
    thread = agent_workspace.replace_later(store.db, UID)
    with client.websocket_connect("/agent/workspace/view") as ws:
        ws.send_text(json.dumps({"id_token": "verified"}))
        messages = [json.loads(ws.receive_text()) for _ in range(2)]
        assert [message["state"] for message in messages] == ["connecting", "replacing"]
        left = (datetime.fromisoformat(messages[1]["until"]) - datetime.now(timezone.utc)).total_seconds()
        assert NEW_VM_SECONDS - 10 < left <= NEW_VM_SECONDS
        # Nothing of the view reached the VM meanwhile, nor does the app's
        # warm-up: the new computer starts its browser itself.
        agent_workspace.warm_later(store, UID, intent=True).join(10)
        assert [call for call in fake_vm.calls if call[0] != "close"] == [] and gateway.url is None
        release.set()
        states = []
        while not states or states[-1] != "ready":
            states.append(json.loads(ws.receive_text())["state"])
        # A new estimate may come while the new VM is made; then the picture.
        assert set(states[:-2]) <= {"replacing"} and states[-2:] == ["starting", "ready"]
        assert ws.receive_bytes() == b"RFB 003.008\n"
    thread.join(10)
    assert "/home/agent/notes.md" not in fake_vm.vms[NAME]["files"]
    # The terminal, opened while another one is on its way.
    limiter.reset()
    api_uid_limiter.reset()
    release.clear()
    shell = Relay([b"agent@workbench:~$ "])

    async def connect(url):
        shell.url = url
        return shell
    monkeypatch.setattr(workspace_router, "connect_upstream", connect)
    thread = agent_workspace.replace_later(store.db, UID)
    with client.websocket_connect("/agent/workspace/terminal") as ws:
        ws.send_text(json.dumps({"id_token": "verified", "cols": 80, "rows": 24}))
        assert [json.loads(ws.receive_text())["state"] for _ in range(2)] == ["connecting", "replacing"]
        assert shell.url is None
        release.set()
        states = []
        while not states or states[-1] != "ready":
            states.append(json.loads(ws.receive_text())["state"])
        assert set(states[:-1]) <= {"replacing"}
        assert ws.receive_bytes() == b"agent@workbench:~$ "
    thread.join(10)


def test_a_handshake_a_waking_vm_breaks_off_is_tried_again_the_long_way(view_api, fake_vm, monkeypatch):
    """A VM reached a moment ago is opened without a request that waits for
    its wake (agent_workspace._ready), so the exec socket's handshake meets a
    VM that paused meanwhile, and a waking VM breaks the first one off (test
    Sprite 2026-11-20). The view opens it once more the long way instead of
    ending with an error; the provider's refusal with a status stays one."""
    from websockets.exceptions import InvalidMessage, InvalidStatus
    client, _, gateway, _ = view_api
    agent_workspace.open_workspace(fake_vm.backend(), UID)
    agent_vm._touch(NAME)
    fake_vm.calls.clear()
    tries = []

    async def connect(url):
        tries.append(url)
        if len(tries) == 1:
            raise InvalidMessage("did not receive a valid HTTP response")
        gateway.url = url
        return gateway
    monkeypatch.setattr(workspace_router, "connect_upstream", connect)
    with client.websocket_connect("/agent/workspace/view") as ws:
        ws.send_text(json.dumps({"id_token": "verified"}))
        assert [json.loads(ws.receive_text())["state"] for _ in range(3)] == ["connecting", "starting", "ready"]
        assert ws.receive_bytes() == b"RFB 003.008\n"
    assert len(tries) == 2
    # First nothing but the relay's address, then the VM itself is asked.
    assert [call[0] for call in fake_vm.calls if call[0] != "close"] == ["exec_url", "ensure", "read", "exec_url"]

    async def refused(url):
        tries.append(url)
        raise InvalidStatus(type("Response", (), {"status_code": 404})())
    monkeypatch.setattr(workspace_router, "connect_upstream", refused)
    with client.websocket_connect("/agent/workspace/view") as ws:
        ws.send_text(json.dumps({"id_token": "verified"}))
        assert [json.loads(ws.receive_text())["state"] for _ in range(2)] == ["connecting", "error"]
    assert len(tries) == 3


def test_the_app_warms_the_workspace_before_the_user_opens_it(view_api, fake_vm, monkeypatch):
    """The view waited for the VM's wake and Chrome's start after the click
    (15 to 30 s from cold). The app asks for the workspace beforehand
    (workspace-view.js warm): woken, its Chrome started and held awake as
    after a message. Never a VM that is not there, without the user's hand
    on the button only for an account that opened the view before, never
    under a message, and no more often than WARM_EVERY_SECONDS."""
    client, store, _, _ = view_api
    threads, warm_later = [], agent_workspace.warm_later

    def later(*args, **kwargs):
        threads.append(warm_later(*args, **kwargs))
        return threads[-1]
    monkeypatch.setattr(agent_workspace, "warm_later", later)
    monkeypatch.setattr(agent_workspace, "WARM_EVERY_SECONDS", 0)

    def warm(intent):
        answer = client.post("/agent/workspace/warm", json={"intent": intent}, headers=AUTH)
        assert answer.status_code == 200
        if threads[-1] is not None:
            threads[-1].join(10)
        return answer.json()["warming"]
    # No workspace yet: a warm-up makes none.
    assert warm(True) is True and fake_vm.backends == 0 and NAME not in fake_vm.vms
    agent_workspace.record_for_view(store, UID, provider="fake")
    # The app's own warm-up (it loaded, the user is active) waits for an account that opened the view.
    assert warm(False) is True and fake_vm.backends == 0
    # The user reaches for the button: the VM wakes, Chrome starts, the hold is a message's end's.
    assert warm(True) is True
    assert fake_vm.warmed == [NAME] and fake_vm.rested == [NAME]
    assert fake_vm.vms[NAME]["files"][agent_workspace.VERSION_PATH] == agent_workspace.VERSION.encode()
    agent_workspace.claim_view(store, UID, 60)
    assert warm(False) is True and fake_vm.warmed == [NAME] * 2
    # A message has the workspace: it is awake, and its own calls hold it.
    chat, _ = pending(store)
    agent_workspace.claim(store, UID, chat, "turn", provider="fake")
    assert warm(True) is True and fake_vm.warmed == [NAME] * 2
    agent_workspace.release(store, UID, "turn")
    # The day's VM time is used up: the view would not open either.
    monkeypatch.setattr(agent_vm_time, "daily_limit", lambda uid: 100)
    agent_vm_time.charge(store, UID, 100)
    assert warm(True) is True and fake_vm.warmed == [NAME] * 2
    monkeypatch.setattr(agent_vm_time, "daily_limit", lambda uid: None)
    # The user has the browser: the start would look at the Chrome under their hands.
    agent_workspace.set_control(store.db, UID, fake_vm.backend(), "user")
    assert warm(True) is True and fake_vm.warmed == [NAME] * 2
    agent_workspace.set_control(store.db, UID, fake_vm.backend(), "agent")
    # An open view keeps the workspace awake itself: another tab of the account asks in vain.
    ws = open_view(client)
    assert warm(True) is False and fake_vm.warmed == [NAME] * 2
    ws.__exit__(None, None, None)
    for _ in range(200):
        if not workspace_router._viewing:
            break
        time.sleep(.02)
    assert warm(True) is True and fake_vm.warmed == [NAME] * 3
    # Paced: an open tab asks with every key, the VM wakes every few minutes at most.
    monkeypatch.setattr(agent_workspace, "WARM_EVERY_SECONDS", 240)
    assert warm(True) is False and fake_vm.warmed == [NAME] * 3
    # The switch (AGENT_WORKSPACE_WARM=off) and an account without the workspace.
    monkeypatch.setattr(agent_workspace, "WARM_EVERY_SECONDS", 0)
    monkeypatch.setenv("AGENT_WORKSPACE_WARM", "off")
    assert warm(True) is False and fake_vm.warmed == [NAME] * 3
    view_api[3].clear()
    assert client.post("/agent/workspace/warm", json={"intent": True}, headers=AUTH).status_code == 403


def test_a_warm_up_that_waited_for_the_account_does_not_hold_up_the_users_reach(store, fake_vm, monkeypatch):
    """The app's own warm-up of an account that never opened the view does
    nothing; the user's first reach for the button right after must not
    meet its pace."""
    agent_workspace.record_for_view(store, UID, provider="fake")
    agent_workspace.warm_later(store, UID).join(10)
    assert fake_vm.warmed == []
    agent_workspace.warm_later(store, UID, intent=True).join(10)
    assert fake_vm.warmed == [NAME]
    assert agent_workspace.warm_later(store, UID, intent=True) is None


def test_taking_over_and_handing_back_write_the_vms_control_files(view_api, fake_vm, monkeypatch):
    client, store, _, allowed = view_api
    assert client.post("/agent/workspace/control", json={"holder": "user"}, headers=AUTH).status_code == 404
    agent_workspace.record_for_view(store, UID, provider="fake")
    fake_vm.vms[NAME] = {"files": {}, "checkpoints": []}
    monkeypatch.setattr(agent_workspace.time, "time", lambda: 5000.0)
    taken = client.post("/agent/workspace/control", json={"holder": "user"}, headers=AUTH)
    assert taken.status_code == 200 and taken.json() == {"holder": "user", "seconds": agent_workspace.CONTROL_SECONDS}
    control = json.loads(fake_vm.vms[NAME]["files"][agent_workspace.BROWSER_CONTROL])
    assert control == {"holder": "user", "until": 5000.0 + agent_workspace.CONTROL_SECONDS}
    # The agent waits: the server holds its calls (the record) and the
    # browser refuses (control.json next to it). What the agent runs goes
    # on (the agent's server answers the browser), so nothing else is touched.
    assert agent_workspace.record(store.db, UID)["control"] == control
    assert agent_workspace.user_has_browser(store.db, UID, now=5000.0)
    assert [call for call in fake_vm.calls if call[0] in {"write", "exec"}] == [
        ("write", NAME, agent_workspace.BROWSER_CONTROL)]
    assert fake_vm.server == []
    assert all(path.startswith("/home/sprite/.consens/") for _, path in fake_vm.server_files)
    assert client.post("/agent/workspace/control", json={"holder": "agent"}, headers=AUTH).status_code == 200
    assert json.loads(fake_vm.vms[NAME]["files"][agent_workspace.BROWSER_CONTROL])["holder"] == "agent"
    # Handing back is noted, so a waiting run sees it between two looks too.
    assert agent_workspace.record(store.db, UID)["control"] == {"holder": "agent", "until": 0, "returned_at": 5000.0}
    assert agent_workspace.control_state(store.db, UID, now=5000.0) == (False, 5000.0)
    assert not agent_workspace.user_has_browser(store.db, UID, now=5000.0)
    assert fake_vm.server == []
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
    # In the workspace, as the server, ending only its own user's processes.
    [(name, command)] = [(call[1], call[2]) for call in fake_vm.calls if call[0] == "exec"]
    assert name == NAME and f"rm -rf {agent_workspace.BROWSER_PROFILE}" in command
    assert 'pkill -u "$(id -u)"' in command
    assert fake_vm.server == [command]
    # No checkpoint from before brings the sign-ins back (restorable).
    assert isinstance(agent_workspace.record(store.db, UID).get("restore_floor"), datetime)


def test_logging_out_everywhere_also_deletes_the_browser_vm_from_before_the_move(view_api, fake_vm):
    """Before it moved into the workspace the browser had a VM of its own
    with its own profile. An account that has not opened its workspace since
    the move (retire_old_browser) still has that VM and every sign-in in it:
    "Log out everywhere" deletes it, also for one that only used the live
    view and has no workspace VM, where nothing runs."""
    from app.services import agent_vm
    client, store, _, _ = view_api
    old = agent_vm.old_browser_name(UID)
    agent_workspace.ref(store.db, UID).set({"browser": old, "sign_ins": [{"site": "github.com"}]}, merge=True)
    fake_vm.vms[old] = {"files": {}, "checkpoints": []}
    assert client.post("/agent/workspace/reset-browser", headers=AUTH).json() == {"status": "reset"}
    assert old not in fake_vm.vms and ("delete", old) in [call[:2] for call in fake_vm.calls]
    kept = agent_workspace.record(store.db, UID)
    assert kept.get("browser") is None and kept.get("sign_ins") == []
    # Nothing ran on a workspace VM that is not there.
    assert not [call for call in fake_vm.calls if call[0] == "exec"]


def test_settings_list_where_the_browser_is_logged_in_and_take_a_site_off(view_api, fake_vm):
    """The sites the agent noted (note_sign_in), in Settings → Connections:
    one can go, and logging out everywhere empties the list."""
    client, store, _, allowed = view_api
    assert client.get("/agent/workspace/sign-ins", headers=AUTH).json() == {"sign_ins": []}
    agent_workspace.note_sign_in(store.db, UID, "web.whatsapp.com", "WhatsApp", True)
    agent_workspace.note_sign_in(store.db, UID, "github.com", "GitHub", True)
    listed = client.get("/agent/workspace/sign-ins", headers=AUTH)
    assert [entry["site"] for entry in listed.json()["sign_ins"]] == ["web.whatsapp.com", "github.com"]
    assert listed.headers["cache-control"] == "private, no-store"
    left = client.post("/agent/workspace/sign-ins/remove", json={"site": "web.whatsapp.com"}, headers=AUTH)
    assert [entry["name"] for entry in left.json()["sign_ins"]] == ["GitHub"]
    assert client.post("/agent/workspace/sign-ins/remove", json={}, headers=AUTH).status_code == 422
    # Logged out everywhere: nowhere on the list either.
    chat, _ = pending(store)
    agent_workspace.claim(store, UID, chat, "done", provider="fake")
    agent_workspace.release(store, UID, "done")
    fake_vm.vms[NAME] = {"files": {}, "checkpoints": []}
    assert client.post("/agent/workspace/reset-browser", headers=AUTH).json() == {"status": "reset"}
    assert client.get("/agent/workspace/sign-ins", headers=AUTH).json() == {"sign_ins": []}
    # Only for an account with the workspace.
    allowed.clear()
    assert client.get("/agent/workspace/sign-ins", headers=AUTH).status_code == 403


# --- Runtime audit 2026-10-30 (V4, I8) ----------------------------------------------------

def test_the_view_names_what_is_left_of_the_days_vm_time(view_api, fake_vm, monkeypatch):
    """The panel's head shows the day's VM time left (V4): the first state
    carries it, and nothing without a cap."""
    client, store, _, _ = view_api
    with client.websocket_connect("/agent/workspace/view") as ws:
        ws.send_text(json.dumps({"id_token": "verified"}))
        first = json.loads(ws.receive_text())
    assert first == {"state": "connecting"}
    monkeypatch.setattr(agent_vm_time, "daily_limit", lambda uid: 7200)
    agent_vm_time.charge(store, UID, 1200.4)
    with client.websocket_connect("/agent/workspace/view") as ws:
        ws.send_text(json.dumps({"id_token": "verified"}))
        first = json.loads(ws.receive_text())
    assert first == {"state": "connecting", "left_seconds": 5999}


def test_a_views_end_is_logged_with_its_code_and_counted_without_the_account(view_api, fake_vm, monkeypatch,
                                                                             caplog):
    """I8: why a view ended, in numbers and labels only, and today's
    anonymous counters."""
    import logging
    client, _, _, _ = view_api
    counted = []
    monkeypatch.setattr(workspace_router, "_count", lambda kind, outcome, seconds=None: counted.append(
        (kind, outcome, seconds is not None)))
    caplog.set_level(logging.INFO)
    ws = open_view(client)
    ws.close(code=1001)
    import time as clock
    deadline = clock.monotonic() + 5
    # Until everything asserted below happened: the view's own line (a line of
    # another kind with "closed" in it ended the wait too early) and its end
    # counter, which the server writes after the line (twice on CI).
    def ended():
        return any("Agent workspace view closed" in record.getMessage() for record in caplog.records)             and any(outcome.startswith("end_") for _, outcome, _ in counted)
    while not ended() and clock.monotonic() < deadline:
        clock.sleep(0.02)
    # Only then the test client's session ends: leaving it cancels the
    # server's task wherever it is, and the line or the counter went missing
    # (on a push's CI, and in 1 of 3 local runs).
    ws.__exit__(None, None, None)
    [line] = [record.getMessage() for record in caplog.records if "Agent workspace view closed" in record.getMessage()]
    assert "code=1000 by=browser browser_code=1001" in line and UID not in line
    assert counted[0] == ("view", "opened", False) and ("view", "end_browser", True) in counted
    # A refusal says why, before anything opened.
    allowed = view_api[3]
    allowed.clear()
    with client.websocket_connect("/agent/workspace/view") as refused:
        refused.send_text(json.dumps({"id_token": "verified"}))
        with pytest.raises(WebSocketDisconnect):
            refused.receive_text()
    # Counted before the close (_refuse): once the client has its close, the count is there.
    assert ("view", "refused_forbidden", False) in counted
    assert any("Agent workspace view refused code=4403" in record.getMessage() for record in caplog.records)


def test_the_views_counters_are_one_anonymous_merge_per_day(monkeypatch):
    from google.cloud import firestore
    writes = []

    class Doc:
        def __init__(self, name):
            self.name = name

        def set(self, data, merge=False):
            writes.append((self.name, data, merge))

    class Db:
        def collection(self, name):
            assert name == "ops_metrics"
            return type("C", (), {"document": lambda _, doc: Doc(doc)})()

    monkeypatch.setattr(workspace_router, "_metrics_on", lambda: True)
    monkeypatch.setattr(workspace_router, "db_firestore", Db())
    monkeypatch.setattr(agent_vm_time, "day_key", lambda: "2026-10-30")
    workspace_router._count("view", "end_browser", 95.7)
    [(name, data, merge)] = writes
    assert name == "workspace-view-2026-10-30" and merge and data["day"] == "2026-10-30"
    counts = data["view"]
    assert set(counts) == {"end_browser", "seconds", "open_le120"}
    assert all(isinstance(value, firestore.Increment) for value in counts.values())
    # Off in tests and mock profiles; a failed write is only logged.
    monkeypatch.setattr(workspace_router, "_metrics_on", lambda: False)
    workspace_router._count("view", "opened")
    assert len(writes) == 1
    monkeypatch.setattr(workspace_router, "_metrics_on", lambda: True)
    monkeypatch.setattr(workspace_router, "db_firestore", None)
    workspace_router._count("view", "opened")


# --- An app on a card, in the user's own browser (open_workspace_app) --------------


def test_an_apps_card_gets_its_address_only_while_its_process_runs(view_api, fake_vm, monkeypatch):
    """The click on the card asks the server where the app's process stands:
    running, it answers the address a new tab opens, on the service's host
    for apps and good for a minute; ended or gone, it says so and wakes
    nothing more. Only for the account's own workspace."""
    from app.services import agent_app_tunnel, agent_apps, agent_vm_processes
    client, store, _, _ = view_api
    body = {"process": "abcd1234", "port": 3000, "path": "/app?x=1"}
    monkeypatch.delenv("AGENT_APP_HOST", raising=False)
    assert client.post("/agent/workspace/app", json=body, headers=AUTH).status_code == 404
    monkeypatch.setenv("AGENT_APP_HOST", "apps.example.com")
    check = agent_vm_processes.app_command(agent_vm_processes.process_dir("abcd1234"), 3000)
    fake_vm.commands[check] = ([("stdout", b"consens-app running 1795400000 1800 - chat-1\n")], 0, .1)
    # A tab left open on the app after it had ended is answered without the VM; a new opening lifts that.
    agent_app_tunnel._idle.add(UID)
    answer = client.post("/agent/workspace/app", json=body, headers=AUTH)
    assert answer.status_code == 200 and answer.headers["cache-control"] == "private, no-store"
    opened = answer.json()
    assert opened["running"] is True and opened["ends_at"] == 1795401800 * 1000
    assert UID not in agent_app_tunnel._idle
    prefix = "https://apps.example.com" + agent_apps.OPEN_PATH + "?t="
    assert opened["url"].startswith(prefix)
    session, path = agent_apps.read_open(opened["url"][len(prefix):])
    assert (session.uid, session.port, path) == (UID, 3000, "/app?x=1")
    # Which app it is: the chat that started the process, as the workspace says it.
    assert session.key == agent_apps.app_key(UID, "chat-1", 3000)
    # Ended, or its folder gone with its chat: nothing to open.
    fake_vm.commands[check] = ([("stdout", b"consens-app 0 1795400000 1800 - chat-1\n")], 0, .1)
    assert client.post("/agent/workspace/app", json=body, headers=AUTH).json() == {"running": False}
    fake_vm.commands[check] = ([], 5, .1)
    assert client.post("/agent/workspace/app", json=body, headers=AUTH).json() == {"running": False}
    # Another account has no workspace here; a port no app may listen on is no request.
    assert client.post("/agent/workspace/app", json=body, headers={"Authorization": "Bearer other"}).status_code == 403
    assert client.post("/agent/workspace/app", json={**body, "port": 80}, headers=AUTH).status_code == 422
    assert client.post("/agent/workspace/app", json={**body, "process": "../x"}, headers=AUTH).status_code == 422


def test_a_closed_workspace_opens_no_app(view_api, fake_vm, monkeypatch):
    from app.services import workspace_guard
    client, _, _, _ = view_api
    monkeypatch.setenv("AGENT_APP_HOST", "apps.example.com")
    monkeypatch.setattr(workspace_guard, "status", lambda uid: workspace_guard.Status(state="closed"))
    answer = client.post("/agent/workspace/app", json={"process": "abcd1234", "port": 3000}, headers=AUTH)
    assert answer.status_code == 403 and answer.json()["code"] == "guarded"
