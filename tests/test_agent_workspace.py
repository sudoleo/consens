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
import shutil
import subprocess
from pathlib import Path

import httpx
import pytest

from app.services import agent_browser, agent_vm, agent_workspace
from app.services.agent_vm import SpritesBackend
from test_agent_runs import UID, pending, store  # noqa: F401  (fixture)
from test_agent_vm import fake_vm  # noqa: F401  (fixture)

VM_FILES = Path(agent_workspace.__file__).with_name("workspace_vm")


def load(name, kind="browser"):
    spec = importlib.util.spec_from_file_location(f"workspace_vm_{kind}_{name}", VM_FILES / kind / f"{name}.py")
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
    assert set(workbench) == {"agent-run", "pause.py", "setup.sh"}
    assert set(browser) == {"browser.py", "display.sh", "relay.py", "setup.sh"}
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


def run_helper(browser, monkeypatch, capsys, request):
    import io
    monkeypatch.setattr(browser.sys, "stdin", type("In", (), {"buffer": io.BytesIO(json.dumps(request).encode())})())
    assert browser.main() == 0
    return json.loads(capsys.readouterr().out)


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
    assert browser.ACTIONS == set(agent_browser.ACTIONS)
    assert set(browser.KEYS) == set(agent_browser.KEYS)
    with pytest.raises(browser.Refused, match="missing"):
        browser.act(None, None, "upload", {"ref": "e1", "file": "/etc/passwd"})
    with pytest.raises(browser.Refused, match="no ref"):
        browser.element(None, "e1; drop")


def test_a_takeover_freezes_the_agents_user_until_the_user_hands_back(tmp_path, monkeypatch):
    """pause.py: the agent's cgroup where the VM has the freezer (measured on
    a Sprite 2026-10-27), else every process of its user stops while the
    user has the browser, also what appears meanwhile, and goes on when
    they hand back or the takeover expires, also after a failure. Since
    2026-10-27 by its user, not by a mark in its environment it could drop."""
    import os
    pause = load("pause", "workbench")
    proc = tmp_path / "proc"
    statuses = {"101": "Uid:\t1500\t1500\t1500\t1500\n", "102": "Uid:\t1001\t1001\t1001\t1001\n",
                "103": "Uid:\t0\t0\t0\t0\n", str(os.getpid()): "Uid:\t1500\t1500\t1500\t1500\n",
                "self": "Uid:\t1500\n"}
    for pid, status in statuses.items():
        (proc / pid).mkdir(parents=True)
        (proc / pid / "status").write_text("Name:\tx\n" + status)
    # A process that ended between the listing and the read.
    (proc / "104").mkdir()
    assert pause.agent_pids(str(proc)) == [101] and pause.AGENT_UID == agent_vm.AGENT_UID
    sent, turns = [], iter([True, True, False])

    def appears():
        # Started in the moment of the takeover: stopped at the next look.
        if len(sent) == 1:
            (proc / "105").mkdir()
            (proc / "105" / "status").write_text("Uid:\t1500\t1500\t1500\t1500\n")
        return pause.agent_pids(str(proc))
    pause.pause(held=lambda: next(turns), find=appears, kill=lambda pid, sig: sent.append((pid, sig)),
                sleep=lambda seconds: None, group=str(tmp_path / "no-cgroup"))
    assert sent == [(101, pause.STOP), (101, pause.STOP), (105, pause.STOP), (101, pause.CONT), (105, pause.CONT)]
    # With a cgroup: frozen whole while held, thawed after, also after a failure.
    group = tmp_path / "cgroup"
    group.mkdir()
    (group / "cgroup.freeze").write_text("0")
    seen = []

    def held():
        seen.append((group / "cgroup.freeze").read_text())
        if len(seen) == 2:
            raise RuntimeError("lost")
        return True
    sent.clear()
    with pytest.raises(RuntimeError):
        pause.pause(held=held, find=lambda: [101], kill=lambda pid, sig: sent.append((pid, sig)),
                    sleep=lambda seconds: None, group=str(group))
    assert seen == ["1", "1"] and (group / "cgroup.freeze").read_text() == "0" and sent == []
    # It reads the takeover from the server's own folder.
    control = tmp_path / "control.json"
    monkeypatch.setattr(pause, "CONTROL", str(control))
    assert pause.user_control() is False
    control.write_bytes(agent_workspace.control_payload("user"))
    assert pause.user_control() is True
    control.write_bytes(agent_workspace.control_payload("agent"))
    assert pause.user_control() is False
    assert agent_workspace.PAUSE_COMMAND.startswith("sudo -n setsid nohup ")
    assert f"{agent_workspace.WORKSPACE_DIR}/pause.py" in agent_workspace.PAUSE_COMMAND


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
    monkeypatch.setattr(relay, "run", lambda script: scripts.append(script) or True)
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


def test_a_relay_without_its_browser_says_so(monkeypatch, capfd):
    relay = load("relay")
    monkeypatch.setattr(relay, "run", lambda script: script == "setup.sh")
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
