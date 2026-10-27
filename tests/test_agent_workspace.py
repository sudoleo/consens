"""The account's workspace (agent_workspace.py, since 2026-10-27): its lease,
its tools in the VM (workspace_vm/) and the Sprites calls behind them. The
loop's use of it is in test_agent_vm.py; nothing here calls Sprites or starts
a browser: the gateway runs against a local echo server, browser.py's
helpers without Playwright.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from app.services import agent_vm, agent_workspace
from app.services.agent_vm import SpritesBackend
from test_agent_runs import UID, pending, store  # noqa: F401  (fixture)

VM_FILES = Path(agent_workspace.__file__).with_name("workspace_vm")


def load(name):
    spec = importlib.util.spec_from_file_location(f"workspace_vm_{name}", VM_FILES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- Lease ------------------------------------------------------------------------

def test_one_chats_message_at_a_time_and_a_lease_ends_or_expires(store):
    first, _ = pending(store)
    second, _ = pending(store, request_id="second")
    assert agent_workspace.claim(store, UID, first, "turn-1", provider="fake").restored is False
    workspace = agent_workspace.record(store.db, UID)
    assert workspace["name"] == agent_vm.workspace_name(UID) and workspace["lease"]["chat_id"] == first
    assert agent_workspace.held_by(store.db, UID) == first
    with pytest.raises(agent_workspace.WorkspaceBusy):
        agent_workspace.claim(store, UID, second, "turn-2", provider="fake")
    # The same chat's next message (one at a time per chat) takes it over.
    agent_workspace.claim(store, UID, first, "turn-3", provider="fake")
    assert agent_workspace.renew(store, UID, "turn-1") is False and agent_workspace.renew(store, UID, "turn-3")
    agent_workspace.release(store, UID, "turn-1")  # not this message's: kept
    assert agent_workspace.held_by(store.db, UID) == first
    agent_workspace.release(store, UID, "turn-3")
    assert agent_workspace.held_by(store.db, UID) is None
    agent_workspace.claim(store, UID, second, "turn-4", provider="fake")
    # Expired: blocks nobody.
    agent_workspace.ref(store.db, UID).update({"lease": {"chat_id": second, "turn_id": "turn-4",
                                                         "until": datetime.now(timezone.utc) - timedelta(seconds=1)}})
    assert agent_workspace.held_by(store.db, UID) is None
    agent_workspace.claim(store, UID, first, "turn-5", provider="fake")


def test_a_restore_is_told_once_to_every_chat_that_used_the_workspace_before(store):
    first, _ = pending(store)
    second, _ = pending(store, request_id="second")
    fresh, _ = pending(store, request_id="fresh")
    for chat in (first, second):
        agent_workspace.claim(store, UID, chat, f"turn-{chat}", provider="fake")
        agent_workspace.release(store, UID, f"turn-{chat}")
    agent_workspace.mark_restored(store, UID)
    assert agent_workspace.claim(store, UID, second, "again", provider="fake").restored is True
    agent_workspace.release(store, UID, "again")
    assert agent_workspace.claim(store, UID, second, "once-more", provider="fake").restored is False
    agent_workspace.release(store, UID, "once-more")
    # A chat that never used it has nothing to be told.
    assert agent_workspace.claim(store, UID, fresh, "new", provider="fake").restored is False


def test_a_deleted_chat_takes_no_lease(store):
    chat, _ = pending(store)
    store._chat_ref(UID, chat).update({"status": "deleting"})
    from app.services.chat_store import ChatNotFound
    with pytest.raises(ChatNotFound):
        agent_workspace.claim(store, UID, chat, "turn", provider="fake")
    assert agent_workspace.record(store.db, UID) == {}


# --- Tools in the VM ------------------------------------------------------------------

def test_the_vms_tools_are_lf_and_their_version_follows_their_bytes():
    files = agent_workspace.tool_files()
    assert set(files) == {"browser.py", "display.sh", "gateway.py", "pause.py", "setup.sh"}
    assert all(b"\r\n" not in data for data in files.values())
    assert agent_workspace.VERSION == agent_workspace._version() and len(agent_workspace.VERSION) == 16
    gateway = load("gateway")
    assert gateway.GATEWAY_PORT == agent_workspace.GATEWAY_PORT
    # Both scripts and the tools that check it name the same setup marker.
    marker = "setup-done-2"
    assert marker in files["setup.sh"].decode() and marker in files["gateway.py"].decode()
    assert marker in files["browser.py"].decode()


def test_the_takeover_expires_unless_the_view_refreshes_it(tmp_path, monkeypatch):
    browser = load("browser")
    control = tmp_path / "control.json"
    monkeypatch.setattr(browser, "CONTROL", str(control))
    assert browser.user_control() is False
    control.write_bytes(agent_workspace.control_payload("user", now=1000.0))
    monkeypatch.setattr(browser.time, "time", lambda: 1000.0 + agent_workspace.CONTROL_SECONDS - 1)
    assert browser.user_control() is True
    monkeypatch.setattr(browser.time, "time", lambda: 1000.0 + agent_workspace.CONTROL_SECONDS + 1)
    assert browser.user_control() is False
    control.write_bytes(agent_workspace.control_payload("agent"))
    assert browser.user_control() is False and json.loads(control.read_text())["holder"] == "agent"
    control.write_text("not json")
    assert browser.user_control() is False


def test_the_browser_refuses_to_act_while_the_user_has_it(tmp_path, monkeypatch, capsys):
    browser = load("browser")
    control = tmp_path / "control.json"
    control.write_bytes(agent_workspace.control_payload("user"))
    monkeypatch.setattr(browser, "CONTROL", str(control))
    monkeypatch.setattr(browser.sys, "argv", ["browser", "click", "e3"])
    started = []
    monkeypatch.setattr(browser, "ensure_browser", lambda: started.append(True))
    assert browser.main() == 3 and started == []
    assert "taken over the browser" in capsys.readouterr().out
    monkeypatch.setattr(browser.sys, "argv", ["browser", "--help"])
    assert browser.main() == 0 and "screenshot" in capsys.readouterr().out


def test_a_takeover_freezes_the_agents_processes_until_the_user_hands_back(tmp_path, monkeypatch):
    """pause.py: what carries the agent's mark (agent_vm.AGENT_MARK) stops
    while the user has the browser, also what appears meanwhile, and goes on
    when they hand back or the takeover expires, also after a failure."""
    import os
    pause = load("pause")
    proc = tmp_path / "proc"
    environs = {"101": b"PATH=/bin\0CONSENS_AGENT=1\0", "102": b"PATH=/bin\0DISPLAY=:1\0",
                "103": b"CONSENS_AGENT=10\0", str(os.getpid()): b"CONSENS_AGENT=1\0", "self": b"CONSENS_AGENT=1\0"}
    for pid, environ in environs.items():
        (proc / pid).mkdir(parents=True)
        (proc / pid / "environ").write_bytes(environ)
    # A process that ended between the listing and the read.
    (proc / "104").mkdir()
    assert pause.marked(str(proc)) == [101]
    assert agent_vm.AGENT_MARK.encode() == pause.MARK
    sent, turns = [], iter([True, True, False])

    def appears():
        # Started in the moment of the takeover: frozen at the next look.
        if len(sent) == 1:
            (proc / "105").mkdir()
            (proc / "105" / "environ").write_bytes(b"CONSENS_AGENT=1\0")
        return pause.marked(str(proc))
    pause.pause(held=lambda: next(turns), find=appears, kill=lambda pid, sig: sent.append((pid, sig)),
                sleep=lambda seconds: None)
    assert sent == [(101, pause.STOP), (101, pause.STOP), (105, pause.STOP), (101, pause.CONT), (105, pause.CONT)]
    # A process gone meanwhile stops nothing; a failure still continues the others.
    sent.clear()

    def kill(pid, sig):
        if pid == 101:
            raise ProcessLookupError(pid)
        sent.append((pid, sig))

    def failing():
        raise RuntimeError("lost")
    with pytest.raises(RuntimeError):
        pause.pause(held=failing, find=lambda: pause.marked(str(proc)), kill=kill, sleep=lambda seconds: None)
    assert sent == [(105, pause.CONT)]
    # It reads the takeover as the browser does.
    control = tmp_path / "control.json"
    monkeypatch.setattr(pause, "CONTROL", str(control))
    assert pause.user_control() is False
    control.write_bytes(agent_workspace.control_payload("user"))
    assert pause.user_control() is True
    control.write_bytes(agent_workspace.control_payload("agent"))
    assert pause.user_control() is False


def test_the_workspaces_own_programs_never_carry_the_agents_mark(monkeypatch):
    import os
    browser = load("browser")
    monkeypatch.setenv("CONSENS_AGENT", "1")
    assert "CONSENS_AGENT" not in browser.unmarked() and browser.unmarked()["PATH"] == os.environ["PATH"]
    assert "unset CONSENS_AGENT" in agent_workspace.tool_files()["display.sh"].decode()
    assert agent_workspace.PAUSE_COMMAND.startswith("env -u CONSENS_AGENT setsid nohup python3 ")
    assert agent_vm.wrapped_command("ls", 30)[3:6] == ["env", agent_vm.AGENT_MARK, "bash"]
    assert agent_vm.wrapped_command("ls", 30, agent=False)[3:5] == ["bash", "-c"]


def test_the_record_says_whether_the_user_has_the_browser(store):
    agent_workspace.record_for_view(store, UID, provider="fake")
    assert agent_workspace.user_has_browser(store.db, UID) is False
    for control, held in (({"holder": "user", "until": 2000.0}, True), ({"holder": "user", "until": 1000.0}, False),
                          ({"holder": "agent", "until": 0}, False), ({"holder": "user", "until": "soon"}, False),
                          ("user", False)):
        agent_workspace.ref(store.db, UID).update({"control": control})
        assert agent_workspace.user_has_browser(store.db, UID, now=1500.0) is held


def test_long_pages_are_read_in_pieces():
    browser = load("browser")
    lines = [f"[e{n}] link \"{'x' * 40}\"" for n in range(1, 401)]
    shown, rest = browser.paged(lines, 0, 1000)
    assert shown == lines[:len(shown)] and sum(len(line) + 1 for line in shown) <= 1000 and rest == 400 - len(shown)
    later, left = browser.paged(lines, len(shown), 1000)
    assert later[0] == lines[len(shown)]
    # A single line over the limit is still shown.
    assert browser.paged(["y" * 5000], 0, 1000) == (["y" * 5000], 0)


def test_the_gateway_reports_its_states_then_carries_vnc_both_ways(monkeypatch):
    """The live view's way in: a WebSocket on /vnc, text states while the
    browser is set up and started, then the VNC bytes as binary frames."""
    gateway = load("gateway")
    scripts = []

    async def run(script):
        scripts.append(script)
        return True
    monkeypatch.setattr(gateway, "run", run)
    monkeypatch.setattr(gateway.os.path, "exists", lambda path: False)

    async def scenario():
        async def echo(reader, writer):
            writer.write(b"RFB 003.008\n")
            while data := await reader.read(1024):
                writer.write(data)
                await writer.drain()
        vnc = await asyncio.start_server(echo, "127.0.0.1", 0)
        monkeypatch.setattr(gateway, "VNC", vnc.sockets[0].getsockname()[:2])
        server = await asyncio.start_server(gateway.handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        from websockets.asyncio.client import connect
        async with connect(f"ws://127.0.0.1:{port}/vnc") as ws:
            states = [json.loads(await ws.recv())["state"] for _ in range(3)]
            banner = await ws.recv()
            await ws.send(b"\x01" * 70_000)  # longer than a 16-bit frame
            echoed = b""
            while len(echoed) < 70_000:
                echoed += await ws.recv()
        refused = None
        try:
            async with connect(f"ws://127.0.0.1:{port}/other"):
                pass
        except Exception as exc:
            refused = exc
        server.close()
        vnc.close()
        return states, banner, echoed, refused
    states, banner, echoed, refused = asyncio.run(scenario())
    assert states == ["setup", "starting", "ready"] and scripts == ["setup.sh", "display.sh"]
    assert banner == b"RFB 003.008\n" and echoed == b"\x01" * 70_000
    assert "404" in str(refused)


def test_a_gateway_frame_reads_back_as_written():
    gateway = load("gateway")

    async def roundtrip(payload):
        reader = asyncio.StreamReader()
        mask = b"\x01\x02\x03\x04"
        raw = gateway.frame(2, payload)
        # A client's frame is masked: set the bit, add the key, mask the payload.
        head = bytearray(raw[:len(raw) - len(payload)])
        head[1] |= 0x80
        reader.feed_data(bytes(head) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))
        return await gateway.read_frame(reader)
    for size in (0, 125, 126, 65535, 65536):
        assert asyncio.run(roundtrip(b"\x07" * size)) == (2, b"\x07" * size)


# --- Sprites calls ---------------------------------------------------------------------

def sprites(handler):
    return SpritesBackend("secret-token", transport=httpx.MockTransport(handler))


def test_a_service_is_made_anew_and_paths_and_modes_go_to_the_file_api():
    """Sprites neither replaces a service (409) nor restarts one with the
    same config, so the gateway would keep running its old code."""
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, json.loads(request.content or b"null")))
        if request.method == "DELETE" and request.url.path.endswith("/services/view"):
            return httpx.Response(404)  # none yet: fine
        if request.url.path.endswith("/consens-w-a"):
            return httpx.Response(200, json={"name": "consens-w-a", "url": "https://consens-w-a-x1.sprites.app"})
        return httpx.Response(200, json={})
    backend = sprites(handler)
    backend.put_service("consens-w-a", "view", {"cmd": "python3", "args": ["gateway.py"], "http_port": 6080})
    backend.delete_path("consens-w-a", "/home/sprite/chats/c1")
    backend.chmod("consens-w-a", "/home/sprite/.local/bin/browser", "755")
    assert backend.url("consens-w-a") == "https://consens-w-a-x1.sprites.app"
    assert [(method, path) for method, path, _ in seen] == [
        ("DELETE", "/v1/sprites/consens-w-a/services/view"), ("PUT", "/v1/sprites/consens-w-a/services/view"),
        ("DELETE", "/v1/sprites/consens-w-a/fs/delete"), ("POST", "/v1/sprites/consens-w-a/fs/chmod"),
        ("GET", "/v1/sprites/consens-w-a")]
    assert seen[1][2] == {"needs": [], "cmd": "python3", "args": ["gateway.py"], "http_port": 6080}
    assert seen[2][2] == {"path": "/home/sprite/chats/c1", "workingDir": "/home/sprite", "recursive": True,
                          "asRoot": False}
    assert seen[3][2]["mode"] == "755"


def test_a_chat_folder_is_only_ever_a_folder_of_its_own():
    assert agent_vm.chat_dir("abc123") == "/home/sprite/chats/abc123"
    for bad in ("", "../x", "a/b", "a b", None):
        with pytest.raises(ValueError):
            agent_vm.chat_dir(bad)
