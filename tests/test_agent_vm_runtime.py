"""The workspace at run time (runtime audit 2026-10-30,
docs/agent-workspace-runtime-audit-2026-10-30.md): its start while the
model thinks (T1), the browser on the lease alone (T5), the rules only when
they change (T6), a failure that costs one call (A1, A3), the lease kept
while the message waits (A2), the end that never waits on the network
(A6), the localhost tunnel only while someone may look (K1, T7), the browser
told to rest (K2), and what the turn and the log keep of it (I2-I5, V3).
The VMs are FakeVM (test_agent_vm.py); nothing calls Sprites.
"""
from datetime import datetime, timedelta, timezone
import json
import logging
import threading
import time

import httpx
import pytest

from app.services import agent_browser, agent_tunnel, agent_vm, agent_vm_tools, agent_workspace
from app.services.agent_browser import BrowserArgs
from app.services.agent_vm_tools import VmExecArgs, VMTools
from app.services.llm.provider_runtime import ProviderCancellation
from test_agent_runs import UID, store  # noqa: F401  (fixture)
from test_agent_vm import (ANSWER, NAME, Agent, FakeSocket, _admin_allowance, _FakeBackend, fake_vm,  # noqa: F401
                           results, tool_events, vm_loop)

BROWSER = agent_vm.browser_name(UID)
# The real start before the first call; the shared fixture turns it off.
PREWARM = VMTools.prewarm


@pytest.fixture(autouse=True)
def clean_tunnel_state():
    yield
    for uid in list(agent_tunnel._tunnels):
        agent_tunnel.close(uid)
    for state in (agent_tunnel._asked, agent_tunnel._working, agent_tunnel._kept_until, agent_tunnel._local_page):
        state.clear()


def wait_for(condition, seconds=5.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(.02)
    return condition()


def browse(loop, **arguments):
    return loop.vm_tools._browser_tools(agent_browser.BrowserTools).call(
        BrowserArgs(**arguments), cancellation=ProviderCancellation())


def bench_calls(fake_vm):
    return [call for call in fake_vm.calls if len(call) > 1 and call[1] == NAME]


# --- T1: the start while the model thinks -------------------------------------------


class Watching(Agent):
    """Agent whose step ``at`` first waits until ``ready()`` holds (the
    start ran beside the model's step) and notes whether it did."""

    def __init__(self, steps, at, ready):
        super().__init__(steps)
        self.at, self.ready, self.seen = at, ready, None

    def factory(self):
        inner, script = super().factory(), self
        stream = inner.stream

        def watched(**kwargs):
            if int(inner.step_id.split(":")[1]) == script.at:
                script.seen = wait_for(script.ready)
            yield from stream(**kwargs)
        inner.stream = watched
        return inner


def test_open_workspace_starts_it_while_the_model_thinks(store, fake_vm, monkeypatch):
    monkeypatch.setattr(VMTools, "prewarm", PREWARM)
    holder = {}
    script = Watching([[("open_workspace", {"task": "Run the script"})], [("vm_exec", {"command": "ls"})]], at=1,
                      ready=lambda: holder["loop"].vm_tools.session.state == "ready" and fake_vm.warmed == [BROWSER])
    loop = holder["loop"] = vm_loop(store, script, workspace_closed=True)
    list(loop.run())
    # Before the step after open_workspace answered, the workbench was ready
    # and the browser warm: the first call waited for nothing.
    assert script.seen is True
    assert results(loop)[1]["exit_code"] == 0
    assert [call[0] for call in bench_calls(fake_vm)].count("ensure") == 1
    turn = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert {"lease", "rules", "tools", "chat", "checkpoint"} <= set(turn["agent_vm"]["phases"])


def test_a_message_that_starts_open_warms_only_the_browser_and_lets_it_rest(store, fake_vm, monkeypatch):
    monkeypatch.setattr(VMTools, "prewarm", PREWARM)
    loop = vm_loop(store, Agent())
    assert wait_for(lambda: fake_vm.warmed == [BROWSER])
    list(loop.run())
    # Nothing of the workbench, no lease, no checkpoint: no call needed them.
    assert not bench_calls(fake_vm) and not agent_workspace.record(store.db, UID).get("lease")
    assert "agent_vm" not in store.get_turn(UID, loop.chat_id, loop.turn_id)
    # The warmed browser goes to rest with the message (K2).
    assert fake_vm.rested == [BROWSER]


def test_no_start_before_the_first_call_without_time_or_after_stop(store, fake_vm, monkeypatch):
    from app.services import agent_vm_time
    monkeypatch.setattr(VMTools, "prewarm", PREWARM)
    monkeypatch.setattr(agent_vm_time, "daily_limit", lambda uid: 10)
    agent_vm_time.charge(store, UID, 10)
    loop = vm_loop(store, Agent(), workspace_closed=True)
    loop.vm_tools.prewarm(bench=True).join(5)
    stopped = vm_loop(store, Agent(), workspace_closed=True, request_id="stopped")
    stopped.cancellation.cancel()
    stopped.vm_tools.prewarm(bench=True).join(5)
    assert fake_vm.calls == [] and fake_vm.warmed == []


def test_a_start_the_message_never_used_gives_the_lease_back(store, fake_vm):
    """open_workspace, then the answer at once: the start may still run
    when the message ends; its lease goes with it."""
    loop = vm_loop(store, Agent())
    session = loop.vm_tools.session
    gate = threading.Event()
    original = agent_workspace.claim

    def slow_claim(*args, **kwargs):
        gate.wait(5)
        return original(*args, **kwargs)
    agent_workspace.claim = slow_claim
    try:
        session.start(ProviderCancellation(), bench=True)
        session.close()
        gate.set()
        session.closer.join(5)
        assert wait_for(lambda: all(job.done.is_set() for job in session._jobs.values()))
    finally:
        agent_workspace.claim = original
    assert not agent_workspace.record(store.db, UID).get("lease")
    assert not bench_calls(fake_vm)


# --- T5: the browser on the lease alone ---------------------------------------------


def test_the_browser_needs_only_the_lease_and_the_turn_counts_its_calls(store, fake_vm):
    script = Agent([[("browser", {"action": "read"})], [("browser", {"action": "click", "ref": "e1"})]])
    loop = vm_loop(store, script)
    events = list(loop.run())
    read, click = results(loop)
    # No workbench: no rules, tools, folder, checkpoint or notes for a web run.
    assert not bench_calls(fake_vm) and "workspace_notes" not in read and "chat_folder" not in read
    turn = store.get_turn(UID, loop.chat_id, loop.turn_id)
    vm = turn["agent_vm"]
    assert vm["checkpoint"] is None and vm["browser_calls"] == 2 and vm["browser_seconds"] >= 0
    assert set(vm["phases"]) == {"lease"}
    # A browser run is a long run, as after open_workspace.
    assert loop._long_run()
    # Each step says when the browser itself began and how long it took (V3, I4).
    saved = [e for e in turn["agent_activity"] if e.get("name") == "browser"]
    assert all(isinstance(e["duration_ms"], int) and datetime.fromisoformat(e["started_at"]) for e in saved)
    running = [e for e in tool_events(events, "browser") if e["status"] == "running"]
    assert running[0].get("started_at") is None and any(e.get("started_at") for e in running)
    # The lease went with the message, the browser rests (K2).
    assert agent_workspace.record(store.db, UID)["lease"] is None and fake_vm.rested == [BROWSER]


def test_a_download_brings_the_workbench_after_its_checkpoint(store, fake_vm):
    fake_vm.browser = lambda request: {"status": "ok", "text": 'Page: "Shop"\nURL: https://shop.example/\n',
                                       "downloads": [{"file": f"{agent_workspace.BROWSER_DOWNLOADS}/bill.pdf"}]}
    fake_vm.vms[BROWSER] = {"files": {f"{agent_workspace.BROWSER_DOWNLOADS}/bill.pdf": b"%PDF-1"},
                            "checkpoints": []}
    loop = vm_loop(store, Agent([[("browser", {"action": "click", "ref": "e1"})]]))
    list(loop.run())
    result = results(loop)[0]
    assert result["downloads"][0]["path"].endswith("/downloads/bill.pdf")
    checkpoint = next(index for index, call in enumerate(fake_vm.calls) if call[0] == "checkpoint")
    written = next(index for index, call in enumerate(fake_vm.calls)
                   if call[0] == "write" and call[2].endswith("/downloads/bill.pdf"))
    assert checkpoint < written and "chat_folder" in result


# --- T6: the rules only when they change, the account read once -------------------


def recorded_rules(monkeypatch):
    seen = []
    ensure, policy = _FakeBackend.ensure, _FakeBackend.set_policy

    def ensuring(self, name, rules=None):
        if name == NAME:
            seen.append(("ensure", None if rules is None else list(rules)))
        return ensure(self, name, rules)

    def setting(self, name, rules):
        if name == NAME:
            seen.append(("policy", list(rules)))
        return policy(self, name, rules)
    monkeypatch.setattr(_FakeBackend, "ensure", ensuring)
    monkeypatch.setattr(_FakeBackend, "set_policy", setting)
    return seen


def test_the_rules_go_out_only_when_they_change_and_always_come_back(store, fake_vm, monkeypatch):
    from app.services import agent_domains
    seen = recorded_rules(monkeypatch)
    base = agent_workspace.policy_key(agent_vm.WORKBENCH_RULES)
    first = vm_loop(store, Agent([[("vm_exec", {"command": "ls"})]]))
    list(first.run())
    assert seen[0] == ("ensure", agent_vm.WORKBENCH_RULES)
    # Confirmed at the message's end; unknown while a message holds the lease.
    assert agent_workspace.record(store.db, UID)["policy"] == base
    seen.clear()
    second = vm_loop(store, Agent([[("vm_exec", {"command": "ls"})]]), chat_id=first.chat_id, request_id="two")
    list(second.run())
    assert seen == [("ensure", None)]
    # A chat with a domain sets its rules and takes them back at its end.
    seen.clear()
    other = vm_loop(store, Agent([[("vm_exec", {"command": "ls"})]]), request_id="other")
    agent_domains.grant(store, UID, other.chat_id, "api.example.com", "t0")
    list(other.run())
    assert seen == [("ensure", agent_domains.rules(["api.example.com"])), ("policy", agent_vm.WORKBENCH_RULES)]
    assert agent_workspace.record(store.db, UID)["policy"] == base


def test_rules_whose_reset_failed_are_set_again_by_the_next_message(store, fake_vm, monkeypatch):
    from app.services import agent_domains
    seen = recorded_rules(monkeypatch)
    loop = vm_loop(store, Agent([[("vm_exec", {"command": "ls"})]]))
    agent_domains.grant(store, UID, loop.chat_id, "api.example.com", "t0")
    setting = _FakeBackend.set_policy

    def failing(self, name, rules):
        raise agent_vm.VMUnavailable("policy: no connection")
    monkeypatch.setattr(_FakeBackend, "set_policy", failing)
    list(loop.run())
    assert agent_workspace.record(store.db, UID)["policy"] is None
    monkeypatch.setattr(_FakeBackend, "set_policy", setting)
    seen.clear()
    later = vm_loop(store, Agent([[("vm_exec", {"command": "ls"})]]), request_id="later")
    list(later.run())
    assert seen[0] == ("ensure", agent_vm.WORKBENCH_RULES)
    # So are rules a setup's widening may have left (agent_workspace._open_for_setup).
    agent_workspace._policy_unsure.add(NAME)
    try:
        seen.clear()
        list(vm_loop(store, Agent([[("vm_exec", {"command": "ls"})]]), request_id="unsure").run())
        assert seen[0] == ("ensure", agent_vm.WORKBENCH_RULES)
    finally:
        agent_workspace._policy_unsure.discard(NAME)


def test_rules_left_unknown_by_a_failed_setup_go_back_at_the_messages_end(store, fake_vm, monkeypatch):
    # A setup widens the rules for a moment; when it fails, they are unknown,
    # and the message's end still sets the base list (the chat's domain too).
    from app.services import agent_domains
    seen = recorded_rules(monkeypatch)
    loop = vm_loop(store, Agent([[("vm_exec", {"command": "ls"})]]))
    agent_domains.grant(store, UID, loop.chat_id, "api.example.com", "t0")

    def failing(*args, **kwargs):
        raise agent_vm.VMUnavailable("setup: no connection")
    monkeypatch.setattr(agent_workspace, "prepare", failing)
    list(loop.run())
    assert seen[-1] == ("policy", agent_vm.WORKBENCH_RULES)
    assert agent_workspace.record(store.db, UID)["policy"] == agent_workspace.policy_key(agent_vm.WORKBENCH_RULES)


def test_the_chats_folder_notes_and_keys_come_in_one_command(store, fake_vm):
    from app.services import agent_secrets
    fake_vm.vms[NAME] = {"files": {agent_secrets.path("OPENAI_API_KEY"): b"sk-test-123456789",
                                   agent_workspace.NOTES_PATH: b"# notes\n"}, "checkpoints": []}
    agent_workspace.ref(store.db, UID).set({"secret_names": ["OPENAI_API_KEY"]})
    loop = vm_loop(store, Agent([[("vm_exec", {"command": "ls"})]]))
    list(loop.run())
    first = results(loop)[0]
    assert first["workspace_notes"]["text"] == "# notes\n" and first["workspace_keys"]["names"] == ["OPENAI_API_KEY"]
    assert agent_secrets.scrub(UID, "key sk-test-123456789") == "key [secret ~/.secrets/OPENAI_API_KEY, hidden from you]"
    # The agent's own commands only: no separate read of the keys (agent_secrets.LOAD_SCRIPT).
    assert not [call for call in fake_vm.calls if call[0] == "run" and call[1] == NAME]


def test_the_takeover_is_read_once_per_call_and_a_takeover_forgets_it(store, monkeypatch):
    reads = []
    real = agent_workspace.control_state

    def counting(db, uid, now=None):
        reads.append(uid)
        return real(db, uid, now)
    monkeypatch.setattr(agent_workspace, "control_state", counting)
    agent_workspace.ref(store.db, UID).set({"name": NAME})
    assert agent_workspace.user_has_browser(store.db, UID) is False
    assert agent_workspace.user_has_browser(store.db, UID) is False
    assert len(reads) == 1

    class Quiet:
        def write_file(self, *args, **kwargs):
            pass
    agent_workspace.set_control(store.db, UID, Quiet(), "user")
    assert agent_workspace.user_has_browser(store.db, UID) is True and len(reads) == 2
    # A wait for the hand-back reads anew.
    assert agent_workspace.user_has_browser(store.db, UID, fresh=True) is True and len(reads) == 3


# --- A1-A6 ----------------------------------------------------------------------


def test_a_store_failure_while_sharing_is_the_calls_error_never_the_runs(store, fake_vm, monkeypatch):
    reported = []
    monkeypatch.setattr(agent_vm_tools, "report_server_exception",
                        lambda exc, **kwargs: reported.append((type(exc).__name__, kwargs["where"])))

    class Broken:
        def save(self, *args, **kwargs):
            raise RuntimeError("503 ServiceUnavailable")
    script = Agent([[("vm_write_file", {"path": "a.txt", "content": "a"})],
                    [("vm_share_file", {"path": "a.txt"})]])
    loop = vm_loop(store, script)
    loop.vm_tools._files = Broken()
    list(loop.run())
    turn = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert results(loop)[1] == {"error": agent_vm_tools.TOOL_FAILED}
    assert reported == [("RuntimeError", "agent_vm.vm_share_file")]


def test_the_lease_is_kept_while_the_message_waits(store, fake_vm, monkeypatch):
    monkeypatch.setattr(agent_vm_tools, "LEASE_KEEP_SECONDS", .05)
    loop = vm_loop(store, Agent())
    session = loop.vm_tools.session
    session.ready(ProviderCancellation(), bench=False)
    renewed = agent_workspace.record(store.db, UID)["lease"]["until"]
    assert wait_for(lambda: agent_workspace.record(store.db, UID)["lease"]["until"] > renewed)
    # Another message took it meanwhile: busy from now on.
    agent_workspace.ref(store.db, UID).update({"lease": {"chat_id": "other", "turn_id": "other",
                                                          "until": datetime.now(timezone.utc) + timedelta(minutes=5)}})
    assert wait_for(lambda: session.state == "busy")
    session.close()
    assert agent_workspace.record(store.db, UID)["lease"]["turn_id"] == "other"


def test_a_restore_waits_for_a_running_response_also_past_its_lease(store, fake_vm):
    loop = vm_loop(store, Agent())
    agent_workspace.claim(store, UID, loop.chat_id, loop.turn_id, provider="fake")
    agent_workspace.ref(store.db, UID).update({"lease": {"chat_id": loop.chat_id, "turn_id": loop.turn_id,
                                                          "until": datetime.now(timezone.utc) - timedelta(seconds=1)}})
    assert agent_workspace.held_by(store.db, UID) is None
    assert agent_workspace.in_use(store, UID) is True
    store._chat_ref(UID, loop.chat_id).update({"agent_lock_until": datetime.now(timezone.utc) - timedelta(seconds=1)})
    assert agent_workspace.in_use(store, UID) is False


def test_the_message_ends_without_waiting_for_the_rules(store, fake_vm, monkeypatch):
    from app.services import agent_domains
    monkeypatch.setattr(agent_vm_tools, "CLOSE_WAIT_SECONDS", .2)
    loop = vm_loop(store, Agent([[("vm_exec", {"command": "ls"})]]))
    agent_domains.grant(store, UID, loop.chat_id, "api.example.com", "t0")
    loop.vm_tools.exec(VmExecArgs(command="ls"), cancellation=ProviderCancellation())
    gate, setting = threading.Event(), _FakeBackend.set_policy

    def slow(self, name, rules):
        gate.wait(5)
        return setting(self, name, rules)
    monkeypatch.setattr(_FakeBackend, "set_policy", slow)
    started = time.monotonic()
    loop.vm_tools.session.close()
    assert time.monotonic() - started < 1
    # The lease stays until the rules are back: no other chat meets them.
    assert agent_workspace.record(store.db, UID)["lease"]["turn_id"] == loop.turn_id
    gate.set()
    loop.vm_tools.session.closer.join(5)
    record = agent_workspace.record(store.db, UID)
    assert record["lease"] is None and record["policy"] == agent_workspace.policy_key(agent_vm.WORKBENCH_RULES)
    assert fake_vm.vms[NAME]["policy"] == agent_vm.WORKBENCH_RULES


def test_the_start_waits_no_longer_than_the_answer_allows(store, fake_vm, monkeypatch):
    ensure = _FakeBackend.ensure

    def slow(self, name, rules=None):
        time.sleep(.6)
        return ensure(self, name, rules)
    monkeypatch.setattr(_FakeBackend, "ensure", slow)
    loop = vm_loop(store, Agent())
    loop.answer_time_left = lambda: agent_vm_tools.MIN_COMMAND_SECONDS + .2
    with pytest.raises(ValueError, match="Not enough time"):
        loop.vm_tools.exec(VmExecArgs(command="ls"), cancellation=ProviderCancellation())
    # The start goes on and the next call finds it done.
    loop.answer_time_left = lambda: None
    assert loop.vm_tools.exec(VmExecArgs(command="ls"), cancellation=ProviderCancellation())["exit_code"] == 0


def test_a_browser_call_shares_its_time_between_the_start_and_the_helper(store, fake_vm, monkeypatch):
    loop = vm_loop(store, Agent())
    browser = loop.vm_tools._browser_tools(agent_browser.BrowserTools)

    class Warming:
        ok, refused = True, None

        def join(self, seconds=None):
            time.sleep(.3)
    timeouts, helper = [], agent_browser.BrowserTools._helper

    def recording(self, request, timeout, cancellation, backend=None, counted=True):
        if request.get("action") not in {"warm", "rest"}:
            timeouts.append(timeout)
        return helper(self, request, timeout, cancellation, backend=backend, counted=counted)
    monkeypatch.setattr(agent_browser.BrowserTools, "_helper", recording)
    browser.warming = Warming()
    loop.answer_time_left = lambda: 16
    browse(loop, action="read")
    assert timeouts == [15]
    browser.ready, browser.warming = False, Warming()
    loop.answer_time_left = lambda: agent_vm_tools.MIN_COMMAND_SECONDS + .2
    with pytest.raises(ValueError, match="Not enough time"):
        browse(loop, action="read")


def test_sprites_exec_counts_from_the_open_socket_and_wakes_a_quiet_vm_first(monkeypatch):
    from test_agent_vm import Clock
    clock, paths = Clock(), []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, json=[])

    def connect(url, token):
        clock.now += 30  # A handshake that waited for the VM.
        return FakeSocket([b"\x03\x00"])
    backend = agent_vm.SpritesBackend("t", transport=httpx.MockTransport(handler), connect=connect, clock=clock)
    outcome = backend.exec("quiet-vm", "ls", cwd="/home/agent", timeout=60, on_output=lambda *a: None,
                           cancellation=ProviderCancellation())
    assert outcome.seconds == 0 and paths == []
    agent_vm._contact["quiet-vm"] = time.monotonic() - agent_vm.WAKE_AFTER_SECONDS - 1
    backend.exec("quiet-vm", "ls", cwd="/home/agent", timeout=60, on_output=lambda *a: None,
                 cancellation=ProviderCancellation())
    assert paths == ["/v1/sprites/quiet-vm/fs/list"]


def test_a_handshake_that_ran_out_of_time_is_not_tried_again():
    """Whether the provider starts the command before its answer is not
    known: a second try could run it twice (A4)."""
    attempts = []

    def connect(url, token):
        attempts.append(url)
        raise TimeoutError("timed out during opening handshake")
    backend = agent_vm.SpritesBackend("t", transport=httpx.MockTransport(lambda request: httpx.Response(200)),
                                      connect=connect)
    with pytest.raises(agent_vm.VMUnavailable, match="handshake timed out"):
        backend.exec("vm", "rm -rf build", cwd="/home/agent", timeout=60, on_output=lambda *a: None,
                     cancellation=ProviderCancellation())
    assert len(attempts) == 1


def test_sprites_says_whether_a_vm_was_cold_and_kills_quickly():
    timeouts = []

    def handler(request):
        if request.url.path.endswith("/kill"):
            timeouts.append(request.extensions["timeout"]["read"])
            return httpx.Response(200, content=b'{"type":"complete"}\n')
        return httpx.Response(200, json={"name": "vm", "status": "cold"})
    backend = agent_vm.SpritesBackend("t", transport=httpx.MockTransport(handler))
    backend.ensure("vm")
    assert backend.statuses == {"vm": "cold"}
    backend._kill("vm", "7")
    assert timeouts == [agent_vm.KILL_SECONDS]


# --- I2, I3, I5 ---------------------------------------------------------------------


def test_the_turn_and_the_log_say_how_the_start_went(store, fake_vm, monkeypatch, caplog):
    monkeypatch.setattr(_FakeBackend, "statuses", {NAME: "cold", BROWSER: "warm"}, raising=False)
    caplog.set_level(logging.INFO)
    loop = vm_loop(store, Agent([[("vm_exec", {"command": "ls"})], [("browser", {"action": "read"})]]))
    list(loop.run())
    vm = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_vm"]
    assert vm["cold"] == {"workbench": True, "browser": False} and vm["browser_calls"] == 1
    tag = f"turn={loop.turn_id[:8]} step="
    assert any(record.getMessage().startswith("Agent VM ready") and tag in record.getMessage()
               for record in caplog.records)
    assert any(record.getMessage().startswith("Agent browser call") and tag in record.getMessage()
               for record in caplog.records)


# --- K1, T7: the tunnel only while someone may look ----------------------------------


def test_the_tunnel_is_wanted_while_a_message_runs_or_the_view_is_open(monkeypatch):
    uid = "tunnel-wanted"
    assert not agent_tunnel.wanted(uid)
    agent_tunnel.begin(uid)
    assert agent_tunnel.wanted(uid)
    monkeypatch.setattr(agent_tunnel, "KEEP_SECONDS", 0)
    agent_tunnel.end(uid)
    assert not agent_tunnel.wanted(uid)
    agent_tunnel.viewing(uid)
    assert agent_tunnel.wanted(uid)
    # Nobody wants it: it does not start again.
    agent_tunnel._kept_until.clear()
    agent_tunnel.seed(uid, [3000])
    assert agent_tunnel.resume(uid, backend_factory=lambda: pytest.fail("no tunnel")) is None


def test_the_open_view_is_the_tunnels_heartbeat(store):
    agent_workspace.record_for_view(store, UID, provider="fake")
    agent_tunnel._kept_until.clear()
    view = agent_workspace.claim_view(store, UID, 60)
    assert agent_tunnel.wanted(UID)
    agent_tunnel._kept_until.clear()
    assert agent_workspace.holds_view(store.db, UID, view) and agent_tunnel.wanted(UID)
    agent_tunnel._kept_until.clear()
    # The terminal is no view of the agent's app.
    terminal = agent_workspace.claim_view(store, UID, 60, "terminal")
    assert agent_workspace.holds_view(store.db, UID, terminal, "terminal") and not agent_tunnel.wanted(UID)


class Stream:
    """A tunnel side whose page keeps connecting (O) and never sends data."""

    def __init__(self, clock):
        self.clock, self.sent, self.closed = clock, [], False

    def recv(self, timeout):
        self.clock.now += agent_tunnel.POLL_SECONDS
        return agent_tunnel.frame(b"O", 7, (3000).to_bytes(2, "big"))

    def send(self, data):
        self.sent.append(data)

    def close(self):
        self.closed = True


def test_a_page_that_keeps_calling_its_server_keeps_no_tunnel_alive():
    from test_agent_vm import Clock
    clock = Clock()
    uid = "tunnel-busy-page"
    tunnel = agent_tunnel.Tunnel(uid, None, clock=clock)
    tunnel.stream, tunnel.bench = Stream(clock), Stream(clock)
    tunnel.ports.add(3000)
    agent_tunnel.begin(uid)
    used = tunnel.used
    tunnel._from_browser(b"O", 1, (3000).to_bytes(2, "big"))
    # A connection attempt is no use: only its data is.
    assert tunnel.used == used
    agent_tunnel._working.clear()
    agent_tunnel._kept_until.clear()
    reader = threading.Thread(target=tunnel._read, args=(tunnel.stream, tunnel._from_browser), daemon=True)
    reader.start()
    reader.join(5)
    assert not reader.is_alive() and tunnel.closing


def test_the_tunnel_comes_back_only_for_a_localhost_page(store, fake_vm, monkeypatch):
    resumed = []
    monkeypatch.setattr(agent_tunnel, "resume", lambda uid, **kwargs: resumed.append(uid))
    agent_tunnel.seed(UID, [3000])
    loop = vm_loop(store, Agent())
    browse(loop, action="read")
    # The page in front is example.com: no tunnel, no wait (T7, K1).
    assert resumed == [] and agent_tunnel.page_local(UID) is False
    fake_vm.browser = lambda request: {"status": "ok", "text": 'Page: "App"\nURL: http://localhost:3000/\n'}
    browse(loop, action="read")
    assert agent_tunnel.page_local(UID) is True
    browse(loop, action="click", ref="e1")
    assert resumed == [UID]
    # The next message's first call knows the account's last page.
    loop.vm_tools.session.close()
    later = vm_loop(store, Agent(), request_id="later")
    browse(later, action="click", ref="e1")
    assert resumed == [UID, UID]


# --- K4 -----------------------------------------------------------------------------


def test_checkpoints_are_taken_only_for_messages_that_use_the_workbench(store, fake_vm):
    """The REST API cannot delete a checkpoint (OpenAPI 2026-10-30: GET and
    POST only), so none is taken where nothing could change (K4)."""
    list(vm_loop(store, Agent([[("browser", {"action": "read"})]])).run())
    assert not [call for call in fake_vm.calls if call[0] == "checkpoint"]
    json.dumps(fake_vm.calls)
