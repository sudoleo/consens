"""The account's workspace (agent_workspace.py, since 2026-10-27): its lease,
its tools in the two VMs (workspace_vm/workbench, workspace_vm/browser) and
the Sprites calls behind them. The loop's use of it is in test_agent_vm.py
and test_agent_browser.py; nothing here calls Sprites or starts a browser:
the relay runs against a local echo server, browser.py's helpers without
Playwright, agent-run and setup.sh are checked as text (they ran on a test
Sprite, docs/agent-mode.md).
"""
import asyncio
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import httpx
import pytest

from app.services import agent_browser, agent_vm, agent_workspace
from app.services.agent_vm import SpritesBackend
from test_agent_runs import UID, pending, store  # noqa: F401  (fixture)
from test_agent_vm import fake_vm  # noqa: F401  (fixture)

VM_FILES = Path(agent_workspace.__file__).with_name("workspace_vm")


def load(name, kind="browser"):
    path = VM_FILES / kind / f"{name}.py"
    # Run by both VMs (tunnel.py): in the folder above.
    spec = importlib.util.spec_from_file_location(f"workspace_vm_{kind}_{name}",
                                                  path if path.exists() else VM_FILES / f"{name}.py")
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


# --- Tools in the VMs -----------------------------------------------------------------

def test_the_vms_tools_are_lf_and_their_versions_follow_their_bytes():
    workbench, browser = agent_workspace.tool_files("workbench"), agent_workspace.tool_files("browser")
    assert set(workbench) == {"agent-run", "setup.sh", "tunnel.py"}
    # One tunnel.py for both VMs; the workbench installs it where its agent's user reads it.
    assert workbench["tunnel.py"] == browser["tunnel.py"]
    assert f'install -D -m 0644 "$(dirname -- "$0")/tunnel.py" {agent_workspace.WORKBENCH_TUNNEL}' in (
        workbench["setup.sh"].decode())
    assert set(browser) == {"browser.py", "display.sh", "relay.py", "setup.sh", "tunnel.py"}
    assert all(b"\r\n" not in data for data in [*workbench.values(), *browser.values()])
    assert agent_workspace.VERSION == agent_workspace._version("workbench") and len(agent_workspace.VERSION) == 16
    assert agent_workspace.BROWSER_VERSION == agent_workspace._version("browser")
    assert agent_workspace.VERSION != agent_workspace.BROWSER_VERSION
    # The browser's setup, its helper and the relay name the same marker.
    marker = "setup-done-1"
    assert all(marker in browser[name].decode() for name in ("setup.sh", "browser.py", "relay.py"))


def test_the_agent_runs_as_its_own_user_without_the_providers_socket():
    """agent-run (security audit 2026-10-27, findings 1 to 3): a mount
    namespace of its own hides the management socket, the checkpoints and
    the logs; then the agent's user with no way back to root. Checked as
    text here; on a test Sprite it ran (docs/agent-mode.md)."""
    run = agent_workspace.tool_files("workbench")["agent-run"].decode()
    assert "unshare --mount --propagation private" in run
    assert "mount --bind /dev/null /.sprite/api.sock || exit 125" in run
    assert "/.sprite/checkpoints /.sprite/logs" in run and "mount -t tmpfs -o ro" in run
    assert '--reuid="$user" --regid="$user" --init-groups --no-new-privs' in run
    assert "/usr/bin/env -i HOME=" in run and 'timeout --kill-after=5 "$seconds"' in run
    # Never in the provider's namespace: there it would hide the socket from the provider too.
    assert 'readlink /proc/self/ns/mnt)" = "$(readlink /proc/1/ns/mnt)' in run
    assert "user=agent" in run and f"home={agent_vm.HOME}" in run
    assert agent_vm.agent_argv(["ls"], 30, "/home/agent/x") == ["sudo", "-n", "/bin/bash", agent_vm.AGENT_RUN, "30",
                                                                "/home/agent/x", "ls"]
    setup = agent_workspace.tool_files("workbench")["setup.sh"].decode()
    assert f"--uid {agent_vm.AGENT_UID}" in setup.replace('"$uid"', str(agent_vm.AGENT_UID))
    assert 'gpasswd -d "$user" sudo' in setup and 'chmod 750 "$legacy"' in setup and 'chmod 700 "$home"' in setup
    # Once: the agent's files out of the provider's home, the old browser and its sign-ins gone.
    for moved in ('move "$legacy/chats" "$home/chats"', 'move "$legacy/NOTES.md" "$home/NOTES.md"',
                  'move "$legacy/repos" "$home/repos"', 'rm -rf "$legacy/.consens/browser"'):
        assert moved in setup


def test_every_workbench_gets_ripgrep_and_headless_chrome_and_loses_the_old_screen():
    """setup.sh (Paket 4, ran on a test Sprite 2026-10-28, docs/agent-mode.md):
    ripgrep from the Ubuntu mirrors and Chrome from Google's server, each only
    when missing and without questions; the old layout's screen, VNC server
    and window manager purged where installed, Chrome kept. A failed install
    never fails the setup (the agent's user does not depend on it)."""
    setup = agent_workspace.tool_files("workbench")["setup.sh"].decode()
    assert "export DEBIAN_FRONTEND=noninteractive" in setup and " -y -qq " in setup
    assert "if ! command -v rg " in setup and "apt_get install --no-install-recommends ripgrep poppler-utils" in setup
    # pdftotext for the PDFs the agent reads (DeepSeek's feedback 2026-10-28).
    assert "! command -v pdftotext" in setup
    assert "if ! command -v google-chrome " in setup
    # Google's apt source never stays (the workbench cannot reach it, every
    # apt run warned), and Chrome's daily job does not add it again.
    assert 'repo_add_once="false"' in setup and "> /etc/default/google-chrome" in setup
    assert "rm -f /etc/apt/sources.list.d/google-chrome.list" in setup
    tools = setup[setup.index("tools() {"):setup.index("\ntools ||")]
    assert tools.count("no_chrome_source") == 2 and tools.index("no_chrome_source") < tools.index("apt_get update")
    assert f"https://{agent_workspace.CHROME_DOMAIN}/linux/direct/google-chrome-stable_current_amd64.deb" in setup
    # Downloaded where only root can open it: the agent's user shares /tmp.
    assert 'download=$(mktemp -d)' in setup and 'apt_get install "$download/chrome.deb"' in setup
    assert "/tmp/" not in setup
    assert "for package in xvfb x11vnc openbox; do" in setup and 'if installed "$package"' in setup
    assert "apt_get purge $old" in setup
    assert not [line for line in setup.splitlines() if "purge" in line and "chrome" in line.lower()]
    assert 'tools || echo "setup: a tool could not be installed' in setup
    # Only the old browser (the provider's user) is ended, never the agent's headless Chrome.
    assert "pkill -KILL -u sprite -f '/opt/google/chrome/'" in setup
    # Its leftovers in /tmp go, only those of the provider's user (2026-10-28).
    assert "find /tmp -maxdepth 1 -user sprite \\( -name 'playwright*'" in setup


def _recording_setup(fake_vm, name, *, stop=False):
    """A backend whose exec notes the policy each command ran under, and is
    stopped at the setup when ``stop``."""
    from app.services.llm.provider_runtime import ProviderCancelled
    backend, during = fake_vm.backend(), []
    run = backend.exec

    def recording(vm_name, command, **kwargs):
        during.append(list(fake_vm.vms[vm_name]["policy"]))
        if stop:
            raise ProviderCancelled()
        return run(vm_name, command, **kwargs)
    backend.exec = recording
    return backend, during


def test_only_the_setup_reaches_chromes_download_server_and_a_chats_domains_stay(fake_vm):
    """prepare reads the rules, adds dl.google.com for setup.sh alone, then
    sets exactly what it read: a running chat's domains (agent_domains.py)
    stay, never the base list. Also when the setup fails or is stopped."""
    from app.services import agent_domains
    from app.services.llm.provider_runtime import ProviderCancelled
    from test_agent_vm import SETUP
    name = agent_vm.workspace_name(UID)
    chat_rules = agent_domains.rules(["api.example.com"])
    fake_vm.vms[name] = {"files": {}, "checkpoints": [], "policy": list(chat_rules)}
    backend, during = _recording_setup(fake_vm, name)
    assert agent_workspace.prepare(backend, name) is True
    assert during == [[*chat_rules, {"domain": "dl.google.com", "action": "allow"}]]
    assert fake_vm.vms[name]["policy"] == chat_rules
    assert [call[0] for call in fake_vm.calls if call[0] in {"get_policy", "policy", "exec"}] == [
        "get_policy", "policy", "exec", "policy"]
    # Up to date: the policy is not touched.
    fake_vm.calls.clear()
    assert agent_workspace.prepare(backend, name) is False
    assert not [call for call in fake_vm.calls if call[0] in {"get_policy", "policy"}]
    # A failed setup: the same rules come back and the version stays unwritten, so it runs again.
    del fake_vm.vms[name]["files"][agent_workspace.VERSION_PATH]
    fake_vm.commands[SETUP] = ([("stderr", b"useradd: failed\n")], 1, .5)
    with pytest.raises(agent_vm.VMUnavailable):
        agent_workspace.prepare(backend, name)
    assert during[-1] == during[0] and fake_vm.vms[name]["policy"] == chat_rules
    assert agent_workspace.VERSION_PATH not in fake_vm.vms[name]["files"]
    # Stopped during the setup: the same.
    stopped, during = _recording_setup(fake_vm, name, stop=True)
    with pytest.raises(ProviderCancelled):
        agent_workspace.prepare(stopped, name)
    assert during == [[*chat_rules, agent_workspace.CHROME_RULE]] and fake_vm.vms[name]["policy"] == chat_rules


def test_a_policy_that_lets_google_through_already_stays_untouched(fake_vm):
    """None set (open), the domain allowed for the chat, or everything: no
    second rule, no change."""
    name = agent_vm.workspace_name(UID)
    for rules in ([], [*agent_vm.WORKBENCH_RULES, agent_workspace.CHROME_RULE], [{"domain": "*", "action": "allow"}]):
        fake_vm.vms[name] = {"files": {}, "checkpoints": [], "policy": list(rules)}
        fake_vm.calls.clear()
        backend, during = _recording_setup(fake_vm, name)
        assert agent_workspace.prepare(backend, name) is True
        assert during == [rules] and fake_vm.vms[name]["policy"] == rules
        assert not [call for call in fake_vm.calls if call[0] == "policy"]


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


def run_helper(browser, monkeypatch, capsys, request, awake=None):
    """One call of browser.py in this process (no resident helper runs)."""
    import io
    monkeypatch.setattr(browser.sys, "stdin", type("In", (), {"buffer": io.BytesIO(json.dumps(request).encode())})())
    monkeypatch.setattr(browser, "stay_awake", lambda: (awake if awake is not None else []).append(True))
    monkeypatch.setattr(browser, "through_server", lambda request: None)
    assert browser.main() == 0
    answer = json.loads(capsys.readouterr().out)
    # For the server's log: the helper's own seconds, and not the resident helper's answer.
    seconds, served = answer.pop("seconds", None), answer.pop("served", None)
    assert (isinstance(seconds, float) and served is False) or answer["status"] == "failed"
    return answer


def test_every_call_holds_the_browser_vm_awake_for_ten_minutes(monkeypatch, capsys):
    """Measured 2026-10-29: without a command the VM froze 46 of 60 seconds,
    and a game on foony.com went offline between two of the agent's moves.
    Each call, also a refused one, renews an expiring Tasks API hold (like
    agent_vm_processes); with it the test VM stayed awake through 60 idle
    seconds."""
    browser = load("browser")
    awake = []
    assert run_helper(browser, monkeypatch, capsys, {"action": "rm -rf /"}, awake)["status"] == "refused"
    assert awake == [True]
    fresh, ran = load("browser"), []
    monkeypatch.setattr(fresh.subprocess, "run", lambda argv, **kwargs: ran.append(argv))
    fresh.stay_awake()
    [argv] = ran
    assert argv[:5] == ["curl", "-s", "--max-time", "5", "--unix-socket"] and argv[5] == "/.sprite/api.sock"
    assert f"http://sprite/v1/tasks/{fresh.AWAKE_TASK}" in argv and json.loads(argv[-1]) == {"expire": "10m"}

    def unreachable(argv, **kwargs):
        raise OSError("no curl")
    # No hold API reachable (a test machine): the call answers all the same.
    monkeypatch.setattr(fresh.subprocess, "run", unreachable)
    fresh.stay_awake()


def test_the_helper_adds_the_picture_after_an_action_only_when_asked():
    """screenshot_after (since 2026-10-29): the action's answer and then the
    picture of the page, with its size for click and drag."""
    browser = load("browser")

    class Page:
        def screenshot(self, type):
            return b"png-bytes"

        def evaluate(self, script):
            return [1280, 720]
    answer = {"text": "Clicked e4."}
    assert browser.with_picture(Page(), {"action": "click"}, answer) is answer
    pictured = browser.with_picture(Page(), {"action": "click", "screenshot_after": True}, answer)
    assert pictured["text"] == "Clicked e4.\nPicture: 1280x720 pixels, the x,y that click and drag take."
    assert pictured["png"] == "cG5nLWJ5dGVz"


def test_the_helpers_page_picture_is_chromes_scaled_viewport_or_nothing():
    """An opened page's card (since 2026-10-29): Chrome scales the visible
    part of the page to PREVIEW_WIDTH itself; a browser that gives none
    costs the card its picture, never the step."""
    browser = load("browser")
    sent = []

    class Session:
        def send(self, method, params):
            sent.append((method, params))
            return {"data": "/9j/AAA="}

        def detach(self):
            sent.append("detached")

    class Context:
        def new_cdp_session(self, page):
            return Session()

    class Page:
        context = Context()

        def evaluate(self, script):
            return [0, 640, 1280, 800]
    assert browser.preview(Page()) == "/9j/AAA="
    [(method, params), detached] = sent
    assert method == "Page.captureScreenshot" and params["format"] == "jpeg" and detached == "detached"
    assert params["clip"] == {"x": 0, "y": 640, "width": 1280, "height": 800, "scale": browser.PREVIEW_WIDTH / 1280}

    class Broken(Page):
        def evaluate(self, script):
            raise RuntimeError("Target closed")
    assert browser.preview(Broken()) == ""


def test_the_browser_vm_sets_its_network_rules_with_a_new_version_only(fake_vm, monkeypatch):
    """Prod 2026-10-29: every opening set the rules anew, a request that
    waits while the VM wakes; once it ran into its limit and the browser was
    off for the message. They only change with a new version, which sets
    them (the rules are part of BROWSER_VERSION)."""
    backend = fake_vm.backend()
    name = agent_workspace.open_browser(backend, UID)
    assert fake_vm.vms[name]["policy"] == agent_vm.BROWSER_RULES
    assert [call for call in fake_vm.calls if call[0] == "policy"] == [("policy", name)]
    # Current: no policy request, so a failing one costs nothing.
    fake_vm.fail.add("policy")
    agent_workspace.open_browser(backend, UID)
    assert len([call for call in fake_vm.calls if call[0] == "policy"]) == 1
    monkeypatch.setattr(agent_vm, "BROWSER_RULES", [{"domain": "*", "action": "allow"}])
    assert agent_workspace._version("browser") != agent_workspace.BROWSER_VERSION


def test_the_browser_helper_takes_one_typed_action_and_refuses_while_the_user_has_it(tmp_path, monkeypatch, capsys):
    """browser.py on the browser VM: JSON in, JSON out, no shell. While the
    user has the browser it acts on nothing; an upload takes only a file the
    server put into its folder for the call."""
    browser = load("browser")
    control = tmp_path / "control.json"
    control.write_bytes(agent_workspace.control_payload("user"))
    monkeypatch.setattr(browser, "CONTROL", str(control))
    started = []
    monkeypatch.setattr(browser, "ensure_browser", lambda: started.append(True))
    assert run_helper(browser, monkeypatch, capsys, {"action": "click", "ref": "e3"})["status"] == "user"
    assert started == []
    assert run_helper(browser, monkeypatch, capsys, {"action": "rm -rf /"}) == {
        "status": "refused", "text": "Unknown action rm -rf /."}
    # "warm" is the server's own start of the browser (agent_browser._warm):
    # never one of the agent's actions, and it reads nothing of the pages.
    assert browser.ACTIONS == set(agent_browser.ACTIONS) | {"warm"} and "warm" not in browser.ACTING
    assert run_helper(browser, monkeypatch, capsys, {"action": "warm"})["text"] == ""
    assert started == [True]
    assert set(browser.KEYS) == set(agent_browser.KEYS)
    with pytest.raises(browser.Refused, match="missing"):
        browser.act(None, None, "upload", {"ref": "e1", "file": "/etc/passwd"})
    with pytest.raises(browser.Refused, match="no ref"):
        browser.element(None, "e1; drop")


def test_the_workbench_no_longer_freezes_at_a_takeover():
    """From 2026-10-27 to 2026-10-29 pause.py froze the agent's processes
    while the user had the browser. Since the browser has a VM of its own,
    nothing of the workbench sees it, and the agent's dev server must answer
    the browser meanwhile (agent_tunnel.py): setup.sh ends a pause still
    running and thaws what it froze; agent-run joins no cgroup any more."""
    setup = (agent_workspace._FILES / "workbench" / "setup.sh").read_text()
    assert 'pkill -KILL -f "$legacy/.consens/workspace/pause.py"' in setup
    assert 'echo 0 > "$group/cgroup.freeze"' in setup and 'pkill -CONT -u "$user"' in setup
    run = (agent_workspace._FILES / "workbench" / "agent-run").read_text()
    assert "cgroup.procs" not in run
    assert not hasattr(agent_workspace, "PAUSE_COMMAND") and not hasattr(agent_workspace, "CONTROL_PATH")


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


class FakePage:
    """A page as browser.py sees it through Playwright: its title and
    address, its context's cookies, and the answers of its two scripts
    (read's SNAPSHOT_JS, find's FIND_JS). The scripts themselves run in
    tests/js/workspace-browser-refs.test.mjs."""

    def __init__(self, browser, url="https://shop.example/cart", cookies=(), lines=(), found=None):
        self.browser, self.url, self.lines, self.found = browser, url, list(lines), found
        self.scripts, self.asked = [], []
        # The page is its own main frame here, without frames of its own.
        self.main_frame, self.child_frames = self, []
        self.frames = [self]
        page = self

        class Context:
            def cookies(self, urls):
                page.asked.append(urls)
                if isinstance(cookies, Exception):
                    raise cookies
                return list(cookies)
        self.context = Context()

    def title(self):
        return "Shop"

    def evaluate(self, script, arg=None):
        if script == self.browser.SNAPSHOT_JS:
            self.scripts.append(("read", arg))
            given = sum(1 for line in self.lines if line.startswith("[e"))
            return {"lines": self.lines, "count": arg + given}
        if script == self.browser.FIND_JS:
            self.scripts.append(("find", arg))
            return self.found
        raise AssertionError(script)


def test_typing_with_enter_presses_it_on_the_keyboard_not_on_the_field():
    """2026-10-28: pressed on the field, Enter waited 30 s while Wikipedia's
    suggestion list covered it; the keyboard presses it at once, the field
    has the focus after fill."""
    browser = load("browser")
    done = []

    class Field:
        first = None

        def count(self):
            return 1

        def evaluate(self, script):
            return False

        def fill(self, text, timeout):
            done.append(("fill", text))

        def press(self, key, **kwargs):
            raise AssertionError("pressed on the field")
    Field.first = Field()

    class Page:
        keyboard = type("Keyboard", (), {"press": staticmethod(lambda key: done.append(("key", key)))})()

        @property
        def main_frame(self):
            return self

        @property
        def frames(self):
            return [self]

        def locator(self, selector):
            return Field()
    said = browser.act(None, Page(), "type", {"ref": "e7", "text": "Paris", "enter": True})
    assert done == [("fill", "Paris"), ("key", "Enter")] and said == "Typed into e7 and pressed Enter."


SESSION_COOKIE = {"name": "sid", "value": "s3cr3t-session-value", "domain": "shop.example", "path": "/"}


def test_the_page_head_says_whether_the_browser_holds_sign_in_data_for_the_site(tmp_path, monkeypatch):
    """Since 2026-10-28: yes or no from the context's cookies for the page's
    address, never a cookie's name, value or their number."""
    browser = load("browser")
    monkeypatch.setattr(browser, "REF_COUNTER", str(tmp_path / "ref-count"))
    signed = FakePage(browser, cookies=[SESSION_COOKIE, {**SESSION_COOKIE, "name": "csrf", "value": "t0k3n"}])
    head = browser.header(signed)
    assert head == ('Page: "Shop"\nURL: https://shop.example/cart\nCookies saved for this site: yes')
    assert signed.asked == [["https://shop.example/cart"]]
    assert not any(secret in head for secret in ("sid", "s3cr3t", "csrf", "t0k3n", "2"))
    assert browser.header(FakePage(browser)).endswith("\nCookies saved for this site: no")
    # No web address, or cookies it cannot read: no line rather than a guess.
    blank = FakePage(browser, url="about:blank", cookies=[SESSION_COOKIE])
    assert browser.header(blank) == 'Page: "Shop"\nURL: about:blank' and blank.asked == []
    assert "sign-in" not in browser.header(FakePage(browser, cookies=RuntimeError("cdp")))
    # Every page head carries it: read, text, find.
    page = FakePage(browser, cookies=[SESSION_COOKIE], lines=['[e1] link "More"'],
                    found={"total": 0, "matches": []})
    assert "Cookies saved for this site: yes" in browser.read_text(page)
    assert "Cookies saved for this site: yes" in browser.find_text(page, "price")


def test_find_lists_the_places_of_a_text_with_reads_refs(tmp_path, monkeypatch):
    """find (since 2026-10-28): read numbers the page first, with the same
    counter, so a ref find names is the one read gives; up to FIND_MATCHES
    places, each with the page around it."""
    browser = load("browser")
    monkeypatch.setattr(browser, "REF_COUNTER", str(tmp_path / "ref-count"))
    (tmp_path / "ref-count").write_text("7")
    lines = ['heading "Prices"', '[e8] link "Sale price list"', '[e9] button "Buy"', "frame https://ads.example"]
    found = {"total": 2, "matches": [{"snippet": "Prices", "ref": ""}, {"snippet": "Sale price list", "ref": "e8"}]}
    page = FakePage(browser, lines=lines, found=found)
    text = browser.find_text(page, "price")
    assert page.scripts == [("read", 7), ("find", {"query": "price", "refs": ["e8", "e9"],
                                                   "limit": browser.FIND_MATCHES, "around": browser.FIND_AROUND})]
    assert (tmp_path / "ref-count").read_text() == "9"
    assert text.split("\n")[3:] == ['2 matches for "price":', '"Prices"', '[e8] "Sale price list"']
    # More places than it lists: it says how many there are.
    many = {"total": 57, "matches": [{"snippet": f"Item {n}", "ref": f"e{n}"} for n in range(1, 21)]}
    text = browser.find_text(FakePage(browser, found=many), "item")
    assert '57 matches for "item", the first 20:' in text and text.count("\n[e") == 20
    one = browser.find_text(FakePage(browser, found={"total": 1, "matches": [{"snippet": "x", "ref": ""}]}), "x")
    assert '1 match for "x":' in one
    # No place: it says so.
    none = browser.find_text(FakePage(browser, found={"total": 0, "matches": []}), "checkout")
    assert none.endswith('"checkout" is neither in the text the page shows nor in the name of an element.')


class FakeFrame:
    """A frame as with_frames sees it: its address, its frame element's mark,
    its own frames, and read's answer for it."""

    def __init__(self, browser, url, mark, lines, children=()):
        self.browser, self.url, self.mark, self.lines = browser, url, mark, list(lines)
        self.child_frames, self.asked = list(children), []
        frame = self

        class Element:
            def get_attribute(self, name):
                assert name == "data-consens-frame"
                return frame.mark
        self.element = Element()

    def frame_element(self):
        return self.element

    def evaluate(self, script, start):
        assert script == self.browser.SNAPSHOT_JS
        self.asked.append(start)
        given = sum(1 for line in self.lines if line.startswith("[e"))
        return {"lines": self.lines, "count": start + given}


def test_read_lists_the_elements_of_a_frame_with_refs_of_their_own(tmp_path, monkeypatch):
    """2026-10-30, bild.de: the consent dialog was a frame, read said only
    "open its address" (which leaves the page), and three clicks at x,y
    missed its button. Now its elements come under its line, numbered on;
    a tracking pixel, a frame of the browser's own computer and frames past
    FRAMES_READ are not read. The action read reads every frame; the read
    after an action only one over the page, as a frame that hangs would hold
    every action (Playwright gives an evaluate no limit)."""
    browser = load("browser")
    monkeypatch.setattr(browser, "REF_COUNTER", str(tmp_path / "ref-count"))
    monkeypatch.setattr(browser, "FRAME_REFS", str(tmp_path / "frame-refs.json"))
    inner = FakeFrame(browser, "https://cmp.example/inner", "f1", ['[e9] link "Details"'])
    consent = FakeFrame(browser, "https://cmp.example/", "f1",
                        ['heading "Datenschutz"', '[e9] button "Alle akzeptieren"', "frame f1 300x200 https://cmp.example/inner"],
                        children=[inner])
    pixel = FakeFrame(browser, "https://ads.example/", "f2", ['[e9] link "ad"'])
    own = FakeFrame(browser, "http://192.168.0.1/", "f3", ['[e9] link "router"'])
    video = FakeFrame(browser, "https://video.example/", "f4", ['[e9] button "Play"'])
    page = FakePage(browser, lines=["(over the page:)", "frame f1 600x400 https://cmp.example/", "(the page under it:)",
                                    '[e1] link "Story"', "frame f2 1x1 https://ads.example/",
                                    "frame f3 300x300 http://192.168.0.1/", "frame f4 640x360 https://video.example/"])
    page.child_frames = [consent, pixel, own, video]
    lines = browser.page_lines(page, "all")
    assert lines == ["(over the page:)", "frame https://cmp.example/, its elements:", '  heading "Datenschutz"',
                     '  [e9] button "Alle akzeptieren"', "  frame https://cmp.example/inner, its elements:",
                     '    [e9] link "Details"', "(the page under it:)", '[e1] link "Story"', "frame https://ads.example/",
                     "frame http://192.168.0.1/ (the browser's own computer, which you do not read)",
                     "frame https://video.example/, its elements:", '  [e9] button "Play"']
    # Numbered on: the page's one ref, then the consent frame's, the inner frame's, the video's.
    assert consent.asked == [1] and inner.asked == [2] and video.asked == [3] and pixel.asked == own.asked == []
    assert (tmp_path / "ref-count").read_text() == "4"
    # After an action: only what lies over the page.
    video.asked.clear()
    after = browser.page_lines(page)
    assert "frame https://video.example/ (read lists its elements)" in after and video.asked == []
    assert '  [e9] button "Alle akzeptieren"' in after
    # find reads none of them.
    consent.asked.clear()
    browser.page_lines(page, "none")
    assert consent.asked == []
    # At most FRAMES_READ frames of one page.
    monkeypatch.setattr(browser, "FRAMES_READ", 1)
    assert "frame https://cmp.example/inner (not read)" in "\n".join(browser.page_lines(page, "all"))


def test_a_frames_ref_is_looked_for_in_its_frame_only(tmp_path, monkeypatch):
    """element finds a ref read in a frame in that frame, by its address:
    the page or another frame holding the same mark never gets the text,
    and frames read never listed (an ad that may hang) are not asked; a
    frame of the browser's own computer, or one inside it, never."""
    browser = load("browser")
    monkeypatch.setattr(browser, "FRAME_REFS", str(tmp_path / "frame-refs.json"))
    browser.remember_frames({"e9": "https://cmp.example/", "e7": "about:srcdoc"})
    asked = []

    class Locator:
        def __init__(self, frame):
            self.frame, self.first = frame, f"element in {frame.url}"

        def count(self):
            asked.append(self.frame.url)
            return 1

    class Frame:
        def __init__(self, url, parent=None):
            self.url, self.parent_frame = url, parent

        def locator(self, selector):
            return Locator(self)
    main = Frame("https://www.bild.de/")
    router = Frame("http://192.168.0.1/", main)
    inside = Frame("about:srcdoc", router)
    ad, cmp = Frame("https://ads.example/", main), Frame("https://cmp.example/", main)
    page = type("Page", (), {"main_frame": main, "frames": [main, router, inside, ad, cmp]})()
    assert browser.element(page, "e9") == "element in https://cmp.example/" and asked == ["https://cmp.example/"]
    # A ref of the page itself: the page alone.
    asked.clear()
    assert browser.element(page, "e3") == "element in https://www.bild.de/" and asked == ["https://www.bild.de/"]
    # A frame inside one of the browser's own computer is not looked in.
    with pytest.raises(browser.Refused, match="not on the page any more"):
        browser.element(page, "e7")
    # The map keeps the newest FRAME_REFS_KEPT refs.
    monkeypatch.setattr(browser, "FRAME_REFS_KEPT", 2)
    browser.remember_frames({"e10": "https://cmp.example/"})
    assert list(browser.frame_refs()) == ["e7", "e10"]


def test_find_names_elements_whose_name_holds_the_text(tmp_path, monkeypatch):
    """A search box named only by its label is in no page text (feedback
    2026-10-28): find lists it from read's lines, by its name alone."""
    browser = load("browser")
    monkeypatch.setattr(browser, "REF_COUNTER", str(tmp_path / "ref-count"))
    lines = ['[e1] searchbox "Wikipedia durchsuchen" (empty)', '[e2] button "Suchen"', '[e3] link "Spenden"',
             '[e4] list "Sprache" selected="Wikipedia durchsuchen"']
    none = {"total": 0, "matches": []}
    text = browser.find_text(FakePage(browser, lines=lines, found=none), "wikipedia DURCHSUCHEN")
    # By the name, not by an option's value or the role.
    assert text.split("\n")[3:] == ['Elements whose name holds "wikipedia DURCHSUCHEN":',
                                    '[e1] searchbox "Wikipedia durchsuchen" (empty)']
    assert "searchbox" not in browser.find_text(FakePage(browser, lines=lines, found=none), "box")
    # An element the text matches already is not named twice.
    found = {"total": 1, "matches": [{"snippet": "Suchen", "ref": "e2"}]}
    text = browser.find_text(FakePage(browser, lines=lines, found=found), "suchen")
    assert text.split("\n")[3:] == ['1 match for "suchen":', '[e2] "Suchen"', 'Elements whose name holds "suchen":',
                                    '[e1] searchbox "Wikipedia durchsuchen" (empty)']


def test_downloads_are_saved_by_their_name_and_handed_over_once_finished(tmp_path, monkeypatch):
    """The helper's side of downloads (since 2026-10-28): what an action
    started is saved in DOWNLOADS under a safe, free name; Chrome's own
    finished files (the user's in the view) move there too, unfinished ones
    stay; main names them all for the server."""
    browser = load("browser")
    monkeypatch.setattr(browser, "DOWNLOADS", str(tmp_path / "downloads"))
    # Not "Downloads": on Windows that is the same folder as "downloads".
    monkeypatch.setattr(browser, "CHROME_DOWNLOADS", str(tmp_path / "chrome"))
    assert browser.safe_name("../../etc/pass wd") == "pass wd" and browser.safe_name("") == "download"
    assert browser.safe_name("Rechnung März?.pdf") == "Rechnung März_.pdf"

    class Download:
        def __init__(self, name, data=b"%PDF", fails=False):
            self.suggested_filename, self.data, self.fails = name, data, fails

        def save_as(self, path):
            if self.fails:
                raise RuntimeError("canceled")
            with open(path, "wb") as handle:
                handle.write(self.data)
    assert browser.keep_downloads([Download("invoice.pdf"), Download("invoice.pdf"), Download("x", fails=True)]) == [
        "invoice.pdf", "invoice (2).pdf"]
    chrome = tmp_path / "chrome"
    chrome.mkdir()
    (chrome / "export.csv").write_text("a,b")
    (chrome / "half.zip.crdownload").write_text("…")
    files = browser.finished_downloads()
    assert [item["name"] for item in files] == ["export.csv", "invoice (2).pdf", "invoice.pdf"]
    assert files[0]["bytes"] == 3 and files[0]["file"] == str(tmp_path / "downloads" / "export.csv")
    assert sorted(os.listdir(chrome)) == ["half.zip.crdownload"]


def test_download_fetches_with_the_browsers_sign_ins_but_never_its_own_computer(tmp_path, monkeypatch):
    browser = load("browser")
    monkeypatch.setattr(browser, "DOWNLOADS", str(tmp_path / "downloads"))
    asked = []

    class Response:
        def __init__(self, url, status=200, disposition=""):
            self.url, self.status, self.ok = url, status, status < 400
            self.headers = {"content-disposition": disposition} if disposition else {}

        def body(self):
            return b"%PDF-1.7 invoice"

    class Context:
        def __init__(self, response):
            self.request = self
            self.response = response

        def get(self, url, **kwargs):
            asked.append(url)
            return self.response
    page = type("Page", (), {"url": "https://shop.example/viewer/invoice-7.pdf"})()
    said = browser.fetch(Context(Response("https://shop.example/viewer/invoice-7.pdf")), page, "")
    assert said == "Downloaded invoice-7.pdf (16 bytes)." and asked == ["https://shop.example/viewer/invoice-7.pdf"]
    named = Response("https://shop.example/get?id=7", disposition="attachment; filename=\"Rechnung 7.pdf\"")
    assert browser.fetch(Context(named), page, "https://shop.example/get?id=7") == "Downloaded Rechnung 7.pdf (16 bytes)."
    assert sorted(os.listdir(tmp_path / "downloads")) == ["Rechnung 7.pdf", "invoice-7.pdf"]
    for url in ("http://localhost:9222/json", "http://127.0.0.1/", "file:///etc/passwd", "http://10.0.0.1/x"):
        with pytest.raises(browser.Refused):
            browser.fetch(Context(Response(url)), page, url)
    # A redirect to the browser's own computer is refused as well, and an error says its status.
    with pytest.raises(browser.Refused, match="private network"):
        browser.fetch(Context(Response("http://127.0.0.1:9222/json")), page, "https://shop.example/r")
    with pytest.raises(browser.Refused, match="HTTP 403"):
        browser.fetch(Context(Response("https://shop.example/x", status=403)), page, "https://shop.example/x")


def test_drag_presses_the_mouse_along_each_stroke_and_click_takes_a_place():
    """A canvas gets lines (small steps between points), each stroke its own
    press; bad points never reach the mouse (2026-10-28)."""
    browser = load("browser")
    moves = []

    class Mouse:
        def move(self, x, y, steps=1):
            moves.append(("move", x, y, steps))

        def down(self):
            moves.append(("down",))

        def up(self):
            moves.append(("up",))

        def click(self, x, y):
            moves.append(("click", x, y))
    page = type("Page", (), {"mouse": Mouse()})()
    said = browser.drag(page, [[[0, 0], [80, 0], [80, 40]], [[5, 5], [6, 6]]])
    assert said == "Dragged 2 strokes (5 points)."
    assert moves == [("move", 0, 0, 1), ("down",), ("move", 80, 0, 10), ("move", 80, 40, 5), ("up",),
                     ("move", 5, 5, 1), ("down",), ("move", 6, 6, 1), ("up",)]
    moves.clear()
    for strokes in ([], [[[1, 1]]], [[[1, 1], [2]]], [[[1, 1], [2, -1]]], [[[1, 1], [2, "x"]]], "nope"):
        with pytest.raises(browser.Refused):
            browser.drag(page, strokes)
    assert moves == []
    assert browser.act(None, page, "click", {"x": 640, "y": 300}) == "Clicked at 640,300."
    # The mouse there first, as the click would move it (look_at).
    assert moves == [("move", 640, 300, 1), ("click", 640, 300)]
    with pytest.raises(browser.Refused, match="x and y"):
        browser.act(None, page, "click", {"x": 640})


PIECE = {"tag": "div.piece.wn.square-21", "name": "", "ref": "", "box": [300, 585, 375, 660], "drawn": False,
         "in": {"tag": "wc-chess-board#board-single.board", "name": "", "ref": "", "box": [0, 60, 600, 660],
                "drawn": False}}


class BoardPage:
    """A page as look_at and hit_report see it: the mouse, HIT_JS's two
    answers (the script itself runs in tests/js/workspace-browser-refs.test.mjs)
    and the pictures of drawn content around a point."""

    def __init__(self, browser, hits, changes, url="https://www.chess.com/play/computer", pictures=()):
        self.browser, self.hits, self.changes, self.url = browser, hits, changes, url
        self.pictures, self.done = list(pictures), []
        page = self

        class Mouse:
            def move(self, x, y, steps=1):
                page.done.append(("move", x, y))

            def down(self):
                page.done.append(("down",))

            def up(self):
                page.done.append(("up",))

            def click(self, x, y):
                page.done.append(("click", x, y))
        self.mouse = Mouse()

    def evaluate(self, script, arg=None):
        assert script == self.browser.HIT_JS
        self.done.append((arg["mode"], [tuple(point) for point in arg["points"]]))
        if arg["mode"] == "before":
            return {"view": [1280, 720], "at": self.hits}
        return self.changes

    def screenshot(self, type, clip, caret, timeout):
        # The caret as it is: hiding it sets every field's style, a change;
        # and soon, never Playwright's 30 s for a page's fonts.
        assert caret == "initial" and timeout == self.browser.PICTURE_SECONDS * 1000
        self.done.append(("picture", clip["x"], clip["y"], clip["width"], clip["height"]))
        return self.pictures.pop(0)


def test_a_click_or_drag_at_a_place_says_what_lay_there_and_what_changed():
    """2026-10-30, chess.com: "Clicked at 337,623." and nothing more, and
    DeepSeek V4.1 Flash spent 20 steps on one move, guessing the squares
    from screenshots. Now the answer says what lay at each point (looked at
    with the mouse there, before the press) with its box and the board's,
    and what changed after it, nearest first."""
    browser = load("browser")
    changes = {"count": 4, "changed": [
        {"tag": "div.piece.wn.square-33", "name": "", "ref": "", "box": [150, 435, 225, 510], "how": "class"},
        {"tag": "div.highlight.square-21", "name": "", "ref": "", "box": [300, 585, 375, 660], "how": "new"},
        {"tag": "span.clock-time", "name": "6:31", "ref": "e40", "box": [700, 60, 760, 80], "how": "text"}],
        "removed": [{"tag": "div.piece.bp.square-33", "name": "", "ref": "", "box": [0, 0, 0, 0]}]}
    page = BoardPage(browser, [PIECE, {**PIECE, "tag": "wc-chess-board#board-single.board", "in": None,
                                       "box": [0, 60, 600, 660]}], changes)
    seen = []
    assert browser.act(None, page, "drag", {"strokes": [[[337, 623], [187, 473]]]}, seen) == \
        "Dragged 1 stroke (2 points)."
    assert page.done[:3] == [("move", 337, 623), ("before", [(337, 623), (187, 473)]), ("down",)]
    assert browser.hit_report(seen[0], page) == (
        "Pressed at 337,623: div.piece.wn.square-21 (box x 300-375, y 585-660), in "
        "wc-chess-board#board-single.board (box x 0-600, y 60-660).\n"
        "Released at 187,473: wc-chess-board#board-single.board (box x 0-600, y 60-660).\n"
        "Changed after it: 4 elements, nearest first: div.piece.wn.square-33 (box x 150-225, y 435-510) class "
        "changed; div.highlight.square-21 (box x 300-375, y 585-660) new; span.clock-time \"6:31\" [e40] "
        "(box x 700-760, y 60-80) text changed; removed: div.piece.bp.square-33.")
    assert page.done[-1] == ("after", [(337, 623), (187, 473)])

    # A click: the same, its point named "At"; nothing changed, or the page went.
    page = BoardPage(browser, [PIECE], {"count": 0, "changed": [], "removed": []})
    seen = []
    assert browser.act(None, page, "click", {"x": 337, "y": 623}, seen) == "Clicked at 337,623."
    assert page.done == [("move", 337, 623), ("before", [(337, 623)]), ("click", 337, 623)]
    assert browser.hit_report(seen[0], page).splitlines()[1:] == ["No element of the page changed after it."]
    page.changes = None
    assert browser.hit_report(seen[0], page).endswith("\nThe page loaded anew after it.")
    # A link that opened another tab: the page in front is another.
    assert browser.hit_report(seen[0], object()).endswith("\nAnother tab is in front now.")

    # Outside the view, and a page that answers nonsense.
    page = BoardPage(browser, [None], {"count": "many", "changed": ["x", {"box": "no", "how": ["?"]}],
                                       "removed": None})
    seen = []
    browser.act(None, page, "click", {"x": 1500, "y": 300}, seen)
    assert browser.hit_report(seen[0], page) == (
        "At 1500,300: nothing, it lies outside the page's view (1280x720).\n"
        "Changed after it: 1 element: element changed.")
    # Infinity and NaN come as floats, lists as anything: never a failed click
    # (review 2026-10-30: the click ran, and the agent heard "failed").
    endless = {**PIECE, "box": [float("inf"), 0, 10, float("nan")], "in": {"tag": 5, "box": None}}
    page = BoardPage(browser, [endless], {"count": float("inf"), "changed": 5, "removed": True})
    seen = []
    browser.act(None, page, "click", {"x": 1, "y": 1}, seen)
    assert browser.hit_report(seen[0], page) == (
        "At 1,1: div.piece.wn.square-21, in element.\nNo element of the page changed after it.")


def test_on_a_canvas_a_click_compares_the_picture_around_its_point():
    """What a canvas, a frame or a video shows is no element: its picture
    around the point, before the press and after the page settled."""
    browser = load("browser")
    canvas = {"tag": "canvas#game", "name": "", "ref": "", "box": [0, 0, 600, 600], "drawn": True, "in": None}
    page = BoardPage(browser, [canvas], {"count": 0, "changed": [], "removed": []}, pictures=[b"before", b"after"])
    seen = []
    browser.act(None, page, "click", {"x": 20, "y": 300}, seen)
    assert page.done[2] == ("picture", 0, 260, 60, 80)
    assert browser.hit_report(seen[0], page) == (
        "At 20,300: canvas#game (box x 0-600, y 0-600).\n"
        "No element of the page changed after it.\n"
        "The picture around 20,300 changed.")
    page = BoardPage(browser, [canvas], {"count": 0, "changed": [], "removed": []}, pictures=[b"same", b"same"])
    seen = []
    browser.act(None, page, "click", {"x": 300, "y": 300}, seen)
    assert browser.hit_report(seen[0], page).endswith("\nThe picture around 300,300 did not change.")


def test_a_click_on_the_browsers_own_computer_looks_at_nothing():
    """A page the agent does not read (own_computer) is not described either."""
    browser = load("browser")
    page = BoardPage(browser, [PIECE], None, url="file:///etc/passwd")
    seen = []
    assert browser.act(None, page, "click", {"x": 5, "y": 5}, seen) == "Clicked at 5,5."
    assert seen == [None] and browser.hit_report(None, page) == ""
    assert page.done == [("move", 5, 5), ("click", 5, 5)]
    # A click that led there: what lay at its point, nothing of the page after it.
    page = BoardPage(browser, [PIECE], {"count": 9, "changed": [], "removed": []})
    seen = []
    browser.act(None, page, "click", {"x": 337, "y": 623}, seen)
    page.url = "http://192.168.0.1/"
    assert browser.hit_report(seen[0], page) == (
        "At 337,623: div.piece.wn.square-21 (box x 300-375, y 585-660), in "
        "wc-chess-board#board-single.board (box x 0-600, y 60-660).")
    assert page.done[-1] == ("click", 337, 623)
    # Inside the view, yet nothing there (Chrome found no element).
    page = BoardPage(browser, [None], {"count": 0, "changed": [], "removed": []})
    seen = []
    browser.act(None, page, "click", {"x": 10, "y": 10}, seen)
    assert browser.hit_report(seen[0], page).splitlines()[0] == "At 10,10: nothing, no element there."


# --- The resident helper (browser.py --serve, since 2026-10-30) ---------------

def helper_end(browser, said, answer=b"", free=True):
    """A resident helper on the other end of a socket pair: FREE (unless
    ``free`` is False: busy with another call), one request line, then
    ``said``; after TOOK it waits for the call's GO and then sends
    ``answer``. Returns the call's end and what it got."""
    import socket
    import threading
    ours, theirs = socket.socketpair()
    got = []

    def helper():
        with theirs:
            if not free:
                time.sleep(2)
                return
            theirs.sendall(browser.FREE)
            line, _ = browser.read_line(theirs, browser.REQUEST_BYTES)
            got.append(json.loads(line))
            if said:
                theirs.sendall(said)
            if said == browser.TOOK:
                go, _ = browser.read_line(theirs, 16)
                got.append(go)
                if answer:
                    theirs.sendall(answer)
    threading.Thread(target=helper, daemon=True).start()
    return ours, got


def test_a_call_hands_its_request_to_the_resident_helper_and_never_runs_it_twice(monkeypatch):
    """A call started a process and Playwright's driver every time: about
    1 s of a read's 1.5 s in Prod. The resident helper keeps the driver; it
    acts only on the call's GO after its TOOK, so a request runs here only
    when it was not taken, and one that was taken never runs here again."""
    browser = load("browser")
    started, stopped = [], []
    monkeypatch.setattr(browser, "start_server", lambda: started.append(True))
    monkeypatch.setattr(browser, "stop_server", lambda: stopped.append(True))
    click = {"action": "click", "ref": "e3"}
    answer = {"status": "ok", "text": "Clicked e3.", "downloads": []}
    conn, got = helper_end(browser, browser.TOOK, json.dumps(answer).encode())
    with conn:
        assert browser.exchange(conn, click) == answer
    assert got == [{"version": browser.VERSION, "request": click}, b"go"] and started == stopped == []
    # Not taken (it ended first, declined, or is of another version): the
    # call runs here, and a helper starts for the next one.
    for said in (b"", browser.DECLINED, browser.STALE):
        conn, got = helper_end(browser, said)
        with conn:
            assert browser.exchange(conn, click) is None
        assert len(got) == 1
    assert len(started) == 3 and stopped == []
    # Busy with another call (another chat's wait): not waited for, and no
    # second helper; the call runs here at once.
    conn, got = helper_end(browser, b"", free=False)
    begun = time.monotonic()
    with conn:
        assert browser.exchange(conn, click) is None
    assert time.monotonic() - begun < browser.SERVE_FREE_SECONDS + 1 and len(started) == 3 and got == []
    # Taken and never answered: an action fails, never a second click; a read reads here.
    conn, _ = helper_end(browser, browser.TOOK)
    with conn:
        assert browser.exchange(conn, click) == {"status": "failed", "text": browser.NOT_FINISHED}
    conn, _ = helper_end(browser, browser.TOOK, b'{"half": ')
    with conn:
        assert browser.exchange(conn, {"action": "read"}) is None
    assert len(stopped) == 2
    # The folder of the scripts keeps its name (FREE is the signal).
    assert isinstance(browser.HERE, str) and os.path.isfile(os.path.join(browser.HERE, "display.sh"))


def test_the_resident_helper_acts_only_on_the_calls_go(monkeypatch):
    """Of its own version, with the browser ready; a call that gave up
    waiting (no GO) runs itself, and nothing happens here."""
    import socket
    browser = load("browser")
    ran, readied, left = [], [], []
    monkeypatch.setattr(browser, "answer_for", lambda request: ran.append(request) or {"status": "ok", "text": "read"})
    monkeypatch.setattr(browser, "ready", lambda request: readied.append(request) or True)
    monkeypatch.setattr(browser, "disconnect", lambda: left.append(True))
    request = {"action": "read"}
    line = json.dumps({"version": browser.VERSION, "request": request}).encode() + b"\n"

    def ask(message, go=True):
        ours, theirs = socket.socketpair()
        with ours, theirs:
            ours.sendall(message)
            if go:
                ours.sendall(browser.GO)
            else:
                ours.shutdown(socket.SHUT_WR)
            go_on = browser.serve_one(theirs)
            theirs.close()
            data = bytearray()
            while chunk := ours.recv(65536):
                data.extend(chunk)
        return go_on, bytes(data)
    assert ask(line) == (True, browser.FREE + browser.TOOK + b'{"status": "ok", "text": "read"}')
    assert ran == readied == [request] and left == [True] and browser._sink is browser._to_stdout
    assert ask(line, go=False) == (True, browser.FREE + browser.TOOK) and ran == [request] and len(left) == 2
    # Another version of this file: it ends, the call starts the new one.
    assert ask(json.dumps({"version": "old", "request": request}).encode() + b"\n", go=False) == (
        False, browser.FREE + browser.STALE)
    # Anything else is no request.
    assert ask(b"GET / HTTP/1.1\r\n\r\n", go=False) == (True, browser.FREE)
    # The browser not ready (Chrome or the helper's Playwright broke): it
    # declines and ends; the call runs itself and heals the browser.
    monkeypatch.setattr(browser, "ready", lambda request: False)
    assert ask(line, go=False) == (False, browser.FREE + browser.DECLINED)
    assert ran == [request]


def test_a_call_that_ends_before_its_answer_ends_the_action_with_the_helper(monkeypatch):
    """Review 2026-10-30: the server's limit or Stop ended the call, and the
    helper went on with the action (a type and Enter still sent). Before,
    the action was the call's own process and ended with it."""
    import socket
    import threading
    browser = load("browser")
    exits, acting, released = [], threading.Event(), threading.Event()

    def answer_for(request):
        acting.set()
        released.wait(5)
        return {"status": "ok", "text": "typed"}

    def exit(code):
        exits.append(code)
        released.set()
    monkeypatch.setattr(browser, "answer_for", answer_for)
    monkeypatch.setattr(browser, "ready", lambda request: True)
    monkeypatch.setattr(browser, "disconnect", lambda: None)
    monkeypatch.setattr(browser.os, "_exit", exit)
    ours, theirs = socket.socketpair()
    with theirs:
        ours.sendall(json.dumps({"version": browser.VERSION, "request": {"action": "type"}}).encode() + b"\n")
        ours.sendall(browser.GO)
        helper = threading.Thread(target=browser.serve_one, args=(theirs,), daemon=True)
        helper.start()
        assert acting.wait(5)
        ours.close()
        helper.join(5)
    assert exits == [1]


def test_the_resident_helper_connects_for_each_call_and_lets_go_after_it(monkeypatch):
    """Connected, Playwright makes Chrome save downloads into its own folder
    and closes every dialog, also the user's in the live view (review
    2026-10-30): the helper keeps only the driver and holds Chrome for a
    call; what run refuses before a page needs no connection."""
    browser = load("browser")
    made, closed = [], []

    class Chromium:
        def connect_over_cdp(self, endpoint, timeout):
            if fail:
                raise RuntimeError("Connection closed")
            made.append(endpoint)
            return type("Browser", (), {"close": lambda self: closed.append(True)})()
    monkeypatch.setitem(browser.KEPT, "playwright", type("Playwright", (), {"chromium": Chromium()})())
    monkeypatch.setattr(browser, "ensure_browser", lambda: None)
    monkeypatch.setattr(browser, "user_control", lambda: False)
    fail = False
    assert browser.ready({"action": "read"}) is True and made == [browser.CDP] and browser.KEPT["prepared"]
    with browser.chrome() as kept:
        assert kept is browser.KEPT["browser"]
    browser.disconnect()
    assert closed == [True] and "browser" not in browser.KEPT and "prepared" not in browser.KEPT
    # The server's warm-up and an action while the user has the browser look at no page.
    assert browser.ready({"action": "warm"}) is True and len(made) == 1
    browser.disconnect()
    monkeypatch.setattr(browser, "user_control", lambda: True)
    assert browser.ready({"action": "click", "ref": "e1"}) is True and len(made) == 1
    # Handed back between ready and the action: the helper's own driver connects, never a second one.
    with browser.chrome() as late:
        assert late is browser.KEPT["browser"] and len(made) == 2
    browser.disconnect()
    fail = True
    assert browser.ready({"action": "read"}) is False and "browser" not in browser.KEPT and "prepared" not in browser.KEPT


def test_the_resident_helper_answers_over_its_socket(tmp_path, monkeypatch):
    """The whole way on a real unix socket (Linux, as on the browser VM): it
    starts, answers its own version and ends at another one."""
    import socket
    import threading
    if not hasattr(socket, "AF_UNIX"):
        pytest.skip("no unix sockets here")
    browser = load("browser")
    monkeypatch.setattr(browser, "STATE", str(tmp_path))
    monkeypatch.setattr(browser, "SERVE_SOCKET", str(tmp_path / "serve.sock"))
    monkeypatch.setattr(browser, "SERVE_LOCK", str(tmp_path / "serve.lock"))
    stopped = []
    playwright = type("Playwright", (), {"stop": lambda self: stopped.append(True)})()
    monkeypatch.setattr(browser, "load_playwright", lambda: lambda: type("Start", (), {"start": lambda self: playwright})())
    monkeypatch.setattr(browser, "ready", lambda request: True)
    monkeypatch.setattr(browser, "answer_for", lambda request: {"status": "ok", "text": request["action"]})
    monkeypatch.setattr(browser, "start_server", lambda: None)
    helper = threading.Thread(target=browser.serve, daemon=True)
    helper.start()
    deadline = time.time() + 5
    while not (tmp_path / "serve.sock").exists() and time.time() < deadline:
        time.sleep(0.02)
    assert oct((tmp_path / "serve.sock").stat().st_mode & 0o777) == "0o600"
    assert (tmp_path / "serve.lock").read_text() == str(os.getpid())
    assert browser.through_server({"action": "read"}) == {"status": "ok", "text": "read"}
    # A call of another version of the file (here the helper shares this
    # process's VERSION, so the call is written by hand): stale, and it ends.
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as other:
        other.settimeout(5)
        other.connect(str(tmp_path / "serve.sock"))
        other.sendall(json.dumps({"version": "next", "request": {"action": "read"}}).encode() + b"\n")
        said = bytearray()
        while chunk := other.recv(64):
            said.extend(chunk)
        assert bytes(said) == browser.FREE + browser.STALE
    helper.join(5)
    assert not helper.is_alive() and stopped == [True] and not (tmp_path / "serve.sock").exists()
    # None runs: the call runs itself.
    assert browser.through_server({"action": "read"}) is None


def test_chrome_starts_with_software_webgl_and_an_old_one_restarts_once():
    """No graphics card on the browser VM, and Chrome no longer falls back to
    software WebGL by itself: maps, design tools and canvas apps failed in
    Laura's test (2026-10-28). A Chrome running without it restarts once."""
    display = (VM_FILES / "browser" / "display.sh").read_text(encoding="utf-8")
    assert "--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader" in display
    restart = display[display.index("# WebGL without a graphics card"):display.index('if [ -z "$(browser_pid)" ]')]
    # By the marker written at Chrome's start, never by its command line:
    # Chrome rewrites it, and a search for the flag restarted Chrome on every
    # call (test Sprite 2026-10-28).
    assert '[ "$(cat "$dir/chrome-flags" 2>/dev/null)" != "$flags" ]' in restart
    assert "swiftshader" not in restart.split("then", 1)[0].split("flags=", 1)[1].split("\n", 1)[1]
    assert '[ -n "$why" ] && stop_chrome' in restart
    start = display[display.index('if [ -z "$(browser_pid)" ]'):display.index('if ! runs "^x11vnc')]
    assert 'echo "$flags" >"$dir/chrome-flags"' in start


def test_a_chrome_that_no_longer_answers_starts_anew():
    """Max's browser VM, 2026-10-28: a page load and the next connection ran
    into their limits, Chrome died two minutes later, and the open view stayed
    black. display.sh now tells Chrome's browser process from its children,
    restarts one whose debugging port does not answer (or that is gone while
    children remain), and only after every process of the profile ended."""
    import re
    display = (VM_FILES / "browser" / "display.sh").read_text(encoding="utf-8")
    # The browser process runs under its starter's name, its children as
    # /opt/google/chrome/chrome (test Sprite 2026-10-28: the old pattern found
    # only the children). Both belong to the profile, nothing else does.
    profile = "/home/sprite/.consens/browser/profile"
    pattern = re.search(r'^chrome="(.*)"$', display, re.M).group(1).replace("$profile", profile)
    for line in (f"/usr/bin/google-chrome --user-data-dir={profile} --remote-debugging-port=9222",
                 f"/opt/google/chrome/chrome --type=renderer --user-data-dir={profile} --lang=en-US"):
        assert re.search(pattern, line), line
    for line in (f"/opt/google/chrome/chrome_crashpad_handler --database={profile}/Crash Reports",
                 f"/usr/bin/google-chrome --user-data-dir={profile}2", f"bash display.sh --keep"):
        assert not re.search(pattern, line), line
    # The children carry the profile's --user-data-dir too: they are not Chrome.
    assert 'grep -q -- " --type="' in display.split("browser_pid() {", 1)[1].split("}", 1)[0]
    # Alive means its main thread answers: the target list, not the version.
    assert 'curl -s -m 5 -o /dev/null "http://127.0.0.1:9222/json/list"' in display
    decide = display[display.index('pid="$(browser_pid)"'):display.index('[ -n "$why" ] && stop_chrome')]
    assert '[ "$mode" != "--keep" ]' in decide and '[ "$mode" = "--restart" ]' in decide
    assert "! listens 9222 || { ! answers && ! answers; }" in decide
    assert 'elif [ -z "$pid" ] && runs "$chrome"; then' in decide
    # Never two Chromes on one profile: KILL after TERM, then wait until all are gone.
    stop = display.split("stop_chrome() {", 1)[1].split("\n}", 1)[0]
    assert stop.index("pkill -TERM") < stop.index("pkill -KILL") < stop.rindex('runs "$chrome" || return 0')
    # Earlier starts stay in the log, each with its reason, up to about 1 MB.
    start = display[display.index('if [ -z "$(browser_pid)" ]'):display.index('if ! runs "^x11vnc')]
    assert 'Chrome starts${why:+, restarted: $why}" >>"$log"' in start and '>>"$log" 2>&1' in start
    assert '-gt 1000000 ] && mv -f "$log" "$log.1"' in start


def test_the_browser_helper_restarts_chrome_once_when_it_takes_no_connection(monkeypatch):
    browser = load("browser")
    restarts, tries = [], []
    monkeypatch.setattr(browser, "restart_browser", lambda: restarts.append(True))

    class Chromium:
        def connect_over_cdp(self, url, timeout):
            tries.append(timeout)
            if len(tries) == 1:
                raise TimeoutError("BrowserType.connect_over_cdp: Timeout 15000ms exceeded.")
            return "browser"
    playwright = type("Playwright", (), {"chromium": Chromium()})()
    assert browser.connect(playwright) == "browser"
    assert restarts == [True] and tries == [browser.CONNECT_SECONDS * 1000] * 2


def test_open_returns_a_page_that_answered_but_is_still_loading():
    browser = load("browser")

    class Page:
        url = "https://linktr.ee/XQN_TheSad"

        def __init__(self, answers=True):
            self.answers, self.waits = answers, []

        def bring_to_front(self):
            pass

        def goto(self, url, wait_until, timeout):
            assert wait_until == "commit" and timeout == browser.OPEN_SECONDS * 1000
            if not self.answers:
                raise TimeoutError("Page.goto: Timeout 30000ms exceeded.")

        def wait_for_load_state(self, state, timeout):
            self.waits.append((state, timeout))
            raise TimeoutError("Timeout 10000ms exceeded.")
    page = Page()
    assert browser.act(None, page, "open", {"url": Page.url}) == \
        f"Opened {Page.url} (still loading: this is what it shows so far)"
    assert page.waits == [("domcontentloaded", browser.LOADED_SECONDS * 1000)]
    with pytest.raises(RuntimeError, match="did not answer within 30 s"):
        browser.act(None, Page(answers=False), "open", {"url": Page.url})


def test_a_call_the_browser_does_not_finish_ends_with_one_answer_and_a_restart(monkeypatch, capsys):
    """The watchdog: the call answers "failed" after its limit, restarts
    Chrome for the next call and ends the process; main then writes nothing."""
    import threading
    browser = load("browser")
    restarted, ended = [], threading.Event()
    monkeypatch.setattr(browser, "restart_browser", lambda: restarted.append(True))
    monkeypatch.setattr(browser.os, "_exit", lambda code: ended.set())
    with browser._ANSWER_LOCK:
        browser._answered = False
    browser.watchdog(0.01)
    assert ended.wait(5) and restarted == [True]
    answer = json.loads(capsys.readouterr().out)
    assert answer["status"] == "failed" and "restarted with its tabs and sign-ins" in answer["text"]
    assert browser.answer_once({"status": "ok", "text": "late"}) is False
    assert capsys.readouterr().out == ""


def test_text_brings_the_main_content_first():
    browser = load("browser")

    class Page:
        url = "https://de.wikipedia.org/wiki/Ironman_Hawaii"
        context = type("Context", (), {"cookies": lambda self, urls: []})()

        def __init__(self, main):
            self.main = main

        def title(self):
            return "Ironman Hawaii"

        def evaluate(self, script, arg=None):
            assert script == browser.TEXT_JS
            return {"main": self.main, "all": "Hauptmenü\nSuchen\n" + (self.main or "Ironman Hawaii\nKona") + "\nImpressum"}
    text = browser.page_text(Page("Ironman Hawaii\nKona"), 0)
    assert text.split("\n")[3:] == ["Ironman Hawaii", "Kona", "(outside the main content: header, navigation, footer)",
                                    "Hauptmenü", "Suchen", "Impressum"]
    # Without a main region the page's own order.
    assert browser.page_text(Page(""), 0).split("\n")[3:] == ["Hauptmenü", "Suchen", "Ironman Hawaii", "Kona",
                                                              "Impressum"]


def test_find_takes_one_to_200_characters_and_reads_while_the_user_has_the_browser(tmp_path, monkeypatch, capsys):
    browser = load("browser")
    assert browser.find_query({"text": "  total \n price "}) == "total price"
    for text in ("", "   ", "x" * 201, None):
        with pytest.raises(browser.Refused, match="1 to 200"):
            browser.find_query({"text": text})
    started = []

    def ensure_browser():
        started.append(True)
        raise browser.SettingUp("The browser is being set up.")
    monkeypatch.setattr(browser, "ensure_browser", ensure_browser)
    assert run_helper(browser, monkeypatch, capsys, {"action": "find", "text": ""})["status"] == "refused"
    assert started == []
    # Like read and text it only reads: the user's takeover does not stop it.
    control = tmp_path / "control.json"
    control.write_bytes(agent_workspace.control_payload("user"))
    monkeypatch.setattr(browser, "CONTROL", str(control))
    assert "find" not in browser.ACTING and {"read", "text"}.isdisjoint(browser.ACTING)
    assert run_helper(browser, monkeypatch, capsys, {"action": "find", "text": "price"})["status"] == "setup"
    assert started == [True]


def test_the_relay_reports_its_states_then_carries_vnc_both_ways(monkeypatch, capfd):
    """The live view's way in since 2026-10-27, over the provider's exec API:
    states as JSON lines on stderr while the browser is set up and started,
    then the VNC bytes between stdin and stdout."""
    import io
    import socket
    import threading
    relay = load("relay")
    scripts = []
    monkeypatch.setattr(relay, "run", lambda script, *args: scripts.append(script) or True)
    monkeypatch.setattr(relay.os.path, "exists", lambda path: False)
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    # The VNC server's Unix socket on the VM; a local TCP one here (Windows too).
    monkeypatch.setattr(relay, "connect_vnc", lambda: socket.create_connection(server.getsockname(), timeout=10))
    received = []

    def vnc():
        connection, _ = server.accept()
        try:
            connection.sendall(b"RFB 003.008\n")
            while data := connection.recv(65536):
                received.append(data)
        except OSError:
            pass  # the relay closed it: its stdin ended
        connection.close()
    server_thread = threading.Thread(target=vnc, daemon=True)
    server_thread.start()
    stdin, stdout = io.BytesIO(b"\x01" * 70_000), io.BytesIO()

    class Stream:
        def __init__(self, raw):
            self.buffer = type("Buffer", (), {"raw": raw})()
    monkeypatch.setattr(relay.sys, "stdin", Stream(stdin))
    monkeypatch.setattr(relay.sys, "stdout", Stream(stdout))
    assert relay.main() == 0
    # The relay returns once it has sent everything; the VNC side may still be
    # reading it (CI read 65536 of 70000 bytes before this join).
    server_thread.join(10)
    server.close()
    states = [json.loads(line)["state"] for line in capfd.readouterr().err.splitlines()]
    assert states == ["setup", "starting", "ready"] and scripts == ["setup.sh", "display.sh"]
    assert stdout.getvalue().startswith(b"RFB 003.008\n") or stdout.getvalue() == b""
    assert sum(len(chunk) for chunk in received) == 70_000


def test_the_open_view_starts_a_chrome_that_ended_again(monkeypatch):
    """2026-10-28: Chrome died while Max watched, and the screen stayed black
    until the agent's next call. While the view is open the relay asks
    display.sh every KEEP_SECONDS to start a Chrome that is gone, never to
    end one (--keep)."""
    import threading
    relay = load("relay")
    calls, done = [], threading.Event()

    def run(script, *args):
        calls.append((script, *args))
        if len(calls) == 2:
            done.set()
        return True
    monkeypatch.setattr(relay, "run", run)
    monkeypatch.setattr(relay, "KEEP_SECONDS", 0.01)
    relay.keep_chrome(done)
    assert calls == [("display.sh", "--keep")] * 2
    display = (VM_FILES / "browser" / "display.sh").read_text(encoding="utf-8")
    assert '[ -n "$pid" ] && [ "$mode" != "--keep" ]' in display


def test_a_relay_without_its_browser_says_so(monkeypatch, capfd):
    relay = load("relay")
    monkeypatch.setattr(relay, "run", lambda script, *args: script == "setup.sh")
    monkeypatch.setattr(relay.os.path, "exists", lambda path: True)
    assert relay.main() == 1
    assert [json.loads(line)["state"] for line in capfd.readouterr().err.splitlines()] == ["starting", "error"]


# --- Sprites calls ---------------------------------------------------------------------

def sprites(handler):
    return SpritesBackend("secret-token", transport=httpx.MockTransport(handler))


def test_the_old_gateway_service_and_the_servers_paths_go_through_the_api():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, json.loads(request.content or b"null")))
        if request.method == "DELETE" and request.url.path.endswith("/services/view"):
            return httpx.Response(404)  # gone already: fine
        return httpx.Response(200, json={})
    backend = sprites(handler)
    backend.delete_service("consens-w-a", "view")
    backend.delete_path("consens-w-a", "/home/sprite/chats/c1", agent=False)
    backend.set_policy("consens-w-a", [{"domain": "pypi.org", "action": "allow"}])
    assert [(method, path) for method, path, _ in seen] == [
        ("DELETE", "/v1/sprites/consens-w-a/services/view"), ("DELETE", "/v1/sprites/consens-w-a/fs/delete"),
        ("POST", "/v1/sprites/consens-w-a/policy/network")]
    assert seen[1][2] == {"path": "/home/sprite/chats/c1", "workingDir": "/home/sprite", "recursive": True,
                          "asRoot": False}
    assert seen[2][2] == {"rules": [{"domain": "pypi.org", "action": "allow"}]}


def test_a_chat_folder_moves_as_the_agent_and_never_over_another(monkeypatch, tmp_path):
    """move_path (since 2026-10-28, a chat's folder after a new title): as
    the agent's user through agent-run, "missing" and "taken" by exit code;
    the script itself, in a real bash, never moves over what exists."""
    backend = sprites(lambda request: httpx.Response(200, json={}))
    ran = []

    def collect(name, argv, *, limit, input=None):
        ran.append(argv)
        return {"a": 0, "b": 44, "c": 47}[argv[-2][-1]], b""
    monkeypatch.setattr(backend, "_collect", collect)
    assert [backend.move_path("consens-w-a", f"/home/agent/chats/{x}", "/home/agent/chats/new") for x in "abc"] == [
        "moved", "missing", "taken"]
    assert ran[0][:3] == ["sudo", "-n", "/bin/bash"] and "move" in ran[0]
    monkeypatch.setattr(backend, "_collect", lambda name, argv, *, limit, input=None: (1, b""))
    with pytest.raises(agent_vm.VMUnavailable):
        backend.move_path("consens-w-a", "/home/agent/chats/a", "/home/agent/chats/new")
    found = shutil.which("bash")
    if not found:
        return
    (tmp_path / "old").mkdir()
    (tmp_path / "old" / "f.txt").write_text("f")
    (tmp_path / "other").mkdir()

    def move(source, target):
        return subprocess.run([found, "-c", agent_vm.MOVE_SCRIPT, "move", source, target], cwd=tmp_path).returncode
    assert move("other", "old") == 47 and (tmp_path / "other").is_dir()
    assert move("nothing", "new") == 44
    assert move("old", "new") == 0 and (tmp_path / "new" / "f.txt").read_text() == "f"
    assert not (tmp_path / "old").exists()


def test_the_policy_is_read_as_its_rules_or_not_at_all():
    """get_policy (agent_workspace.prepare restores what it read): the rules
    as set_policy takes them; anything else is the provider failing."""
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        return httpx.Response(200, json={"rules": [{"domain": "pypi.org", "action": "allow"}]})
    assert sprites(handler).get_policy("consens-w-a") == [{"domain": "pypi.org", "action": "allow"}]
    assert seen == [("GET", "/v1/sprites/consens-w-a/policy/network")]
    assert sprites(lambda request: httpx.Response(200, json={"rules": []})).get_policy("consens-w-a") == []
    for answer in (httpx.Response(200, json={}), httpx.Response(200, json={"rules": "all"}),
                   httpx.Response(200, json={"rules": ["pypi.org"]}), httpx.Response(200, text="<html>"),
                   httpx.Response(502)):
        with pytest.raises(agent_vm.VMUnavailable):
            sprites(lambda request, answer=answer: answer).get_policy("consens-w-a")


def test_a_chat_folder_is_only_ever_a_folder_of_its_own():
    assert agent_vm.chat_dir("abc123") == "/home/agent/chats/abc123"
    for bad in ("", "../x", "a/b", "a b", None):
        with pytest.raises(ValueError):
            agent_vm.chat_dir(bad)


# --- Deletion ------------------------------------------------------------------------------

def test_the_accounts_deletion_deletes_both_vms_by_their_names(store, fake_vm):
    """Also without a record (security audit 2026-10-27): the names follow
    from the account."""
    fake_vm.vms[agent_vm.workspace_name(UID)] = {"files": {}, "checkpoints": []}
    fake_vm.vms[agent_vm.browser_name(UID)] = {"files": {}, "checkpoints": []}
    agent_workspace.delete_for_account(store.db, UID, factory=fake_vm.backend)
    assert ("delete", agent_vm.workspace_name(UID)) in fake_vm.calls
    assert ("delete", agent_vm.browser_name(UID)) in fake_vm.calls and fake_vm.vms == {}
    assert agent_workspace.record(store.db, UID) == {}


def test_a_chats_folder_goes_as_the_agent_and_from_where_it_lay_before(store, fake_vm):
    name = agent_vm.workspace_name(UID)
    fake_vm.vms[name] = {"files": {"/home/agent/chats/c1/a.txt": b"a", "/home/sprite/chats/c1/old.txt": b"o"},
                         "checkpoints": []}
    agent_vm.delete_chat_vm(UID, "c1", {"name": name, "workspace": True}, factory=fake_vm.backend)
    assert fake_vm.vms[name]["files"] == {**{path: data for path, data in fake_vm.vms[name]["files"].items()
                                             if path.startswith("/home/sprite/.consens/")}}
    # The legacy folder through the server, the agent's through its user.
    assert ("delete", "/home/sprite/chats/c1") in fake_vm.server_files
    assert ("delete", "/home/agent/chats/c1") not in fake_vm.server_files
    # A workbench that is gone is not made again for it.
    fake_vm.calls.clear()
    agent_vm.delete_chat_vm(UID, "c2", {"name": agent_vm.workspace_name("someone"), "workspace": True},
                            factory=fake_vm.backend)
    agent_vm.delete_chat_vm("other", "c3", {"name": agent_vm.workspace_name("other"), "workspace": True},
                            factory=fake_vm.backend)
    assert not [call for call in fake_vm.calls if call[0] in {"ensure", "exec", "write"}]
