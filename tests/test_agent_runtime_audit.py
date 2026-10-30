"""The workspace at run time, audit 2026-10-30
(docs/agent-workspace-runtime-audit-2026-10-30.md): what the operator can
measure afterwards (I1, I4, I7, I9), what the agent reads about its own run
(L1, L3, L6, L7), several calls per step while the workspace is open (T2),
the browser's reads without a live round of their own (K6) and the settlement
in fewer round trips (T3). Fakes only: no model, no VM, no Firestore.
"""
from dataclasses import replace
from datetime import datetime, timezone
import json
import re

from pydantic import BaseModel, ConfigDict
import pytest

from app.services import agent_delegation
from app.services.llm import agent_client
from app.services.llm.agent_client import AgentCompletion, AgentModel, measured_usage
from test_agent_runs import UID, pending, receipt, store  # noqa: F401  (fixture)
from test_agent_vm import ANSWER, Agent, fake_vm, results, vm_loop  # noqa: F401  (fixture)


class Steps(Agent):
    """Agent, whose wrap-up step (tools listed, not callable) answers; it
    records what each step's request asked for."""

    def __init__(self, steps=()):
        super().__init__(steps)
        self.parallel, self.requests = [], []

    def factory(self):
        base, script = type(super().factory()), self

        class Completion(base):
            def stream(self, *, model, messages, **kwargs):
                script.parallel.append(self.parallel_tool_calls)
                script.requests.append(json.loads(json.dumps(messages, default=str)))
                if kwargs.get("allow_tool_calls") is False:
                    self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                    self.text, self.finish_reason = ANSWER, "stop"
                    yield {"type": "delta", "text": self.text}
                    return
                yield from super().stream(model=model, messages=messages, **kwargs)
                # As AgentCompletion keeps them (keep_over_limit): past the
                # step's limit, without arguments, by id.
                if self.keep_over_limit and len(self.tool_calls) > self.tool_call_limit:
                    for call in self.tool_calls[self.tool_call_limit:]:
                        call["function"]["arguments"] = "{}"
                        self.over_limit_ids.add(call["id"])
        return Completion()


def log_entries(loop, kind=None, name=None):
    return [(entry, text) for entry, text in loop.work_log.entries_after(0)
            if (kind is None or entry["kind"] == kind) and (name is None or entry["name"] == name)]


# --- I7: when a request left, its first token came and its stream ended ------------

def test_a_streamed_step_keeps_its_request_times_and_the_receipt_saves_them(store, monkeypatch):
    def lines(url, **kwargs):
        for event in [{"id": "gen-1", "choices": [{"delta": {"content": "Hello"}}]},
                      {"choices": [{"delta": {}, "finish_reason": "stop"}]},
                      {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 3}}]:
            yield "data: " + json.dumps(event)
            yield ""
        yield "data: [DONE]"
        yield ""
    monkeypatch.setattr(agent_client, "cancellable_sse_lines", lines)
    completion = AgentCompletion()
    list(completion.stream(model=AgentModel(), messages=[{"role": "user", "content": "Hi"}], api_key="test"))
    started, first, ended = completion.request_started_at, completion.first_token_at, completion.stream_ended_at
    assert all(isinstance(value, datetime) and value.tzinfo is timezone.utc for value in (started, first, ended))
    assert started <= first <= ended
    # The receipt keeps them beside created_at and settled_at (AgentRunStore.settle).
    chat_id, turn = pending(store)
    store.claim(UID, chat_id, turn["id"], AgentModel())
    value = receipt()
    value.request_started_at, value.first_token_at, value.stream_ended_at = started, first, ended
    store.settle(UID, chat_id, turn["id"], completion=value, status="succeeded")
    saved = store.receipt_ref(UID, chat_id, turn["id"]).get().to_dict()
    assert (saved["request_started_at"], saved["first_token_at"], saved["stream_ended_at"]) == (started, first, ended)


def test_a_step_without_a_stream_saves_no_request_times(store):
    chat_id, turn = pending(store)
    store.claim(UID, chat_id, turn["id"], AgentModel())
    store.settle(UID, chat_id, turn["id"], completion=receipt(), status="succeeded")
    saved = store.receipt_ref(UID, chat_id, turn["id"]).get().to_dict()
    assert not {"request_started_at", "first_token_at", "stream_ended_at"} & set(saved)


# --- I4: a tool entry says when its call started and how long it ran ----------------

def test_tool_entries_of_the_work_log_carry_start_and_duration(store, fake_vm):
    script = Agent([[("vm_exec", {"command": "python3 stats.py"})], [("vm_read_file", {"path": "stats.py"})]])
    loop = vm_loop(store, script)
    list(loop.run())
    tools = [entry for entry, _ in log_entries(loop, kind="tool")]
    assert [entry["name"] for entry in tools] == ["vm_exec", "vm_read_file"]
    for entry in tools:
        assert type(entry["duration_ms"]) is int and entry["duration_ms"] >= 0
        assert datetime.fromisoformat(entry["started_at"]) <= datetime.fromisoformat(entry["at"])
    # Other entries keep their shape.
    assert not any("duration_ms" in entry for entry, _ in log_entries(loop) if entry["kind"] != "tool")


def test_entry_fields_are_measurements_only(store):
    from app.services.agent_work_log import WorkLog
    log = WorkLog(store, UID, "chat", "turn", ready=lambda: False)
    log.app("checked", {"text": "x"}, step="completion:3", gate_ms=812)
    log.app("paused", "text", gate_ms=True)
    log.app("paused", "text", gate_ms=-1, duration_ms="x" * 41)
    first, second, third = (entry for entry, _ in log.entries_after(0))
    assert first["step"] == "completion:3" and first["gate_ms"] == 812
    assert "gate_ms" not in second and "gate_ms" not in third and "duration_ms" not in third


# --- I1: which limit ended the work ---------------------------------------------------

def test_a_wrap_up_says_which_limit_in_the_log_on_the_turn_and_to_the_agent(store, fake_vm):
    script = Steps([[("vm_exec", {"command": "ls"})]] * 6)
    loop = vm_loop(store, script)
    loop.policy = replace(loop.policy, turn_steps=2, vm_turn_steps=2)
    list(loop.run())
    turn = store._turn_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert turn["status"] == "completed" and turn["assistant_response"] == ANSWER
    assert turn["agent_wrap_up"]["reason"] == "steps" and turn["agent_wrap_up"]["steps"] == 2
    assert isinstance(turn["agent_wrap_up"]["seconds"], float)
    [(entry, text)] = log_entries(loop, kind="app", name="limit")
    assert entry["actor"] == "app" and json.loads(text)["reason"] == "steps"
    # The agent reads which limit, and that a follow-up message can go on.
    wrap = next(m["content"] for m in reversed(loop.messages) if m.get("role") == "user")
    assert wrap.startswith("App rule: this message has reached its limit.")
    assert "step limit (2 steps per message)" in wrap and "follow-up message" in wrap


def test_a_turn_that_ends_by_itself_has_no_wrap_up(store, fake_vm):
    loop = vm_loop(store, Agent([[("vm_exec", {"command": "ls"})]]))
    list(loop.run())
    assert "agent_wrap_up" not in store._turn_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert not log_entries(loop, kind="app", name="limit")


def test_the_limit_fact_names_each_limit():
    loop = type("Loop", (), {"_turn_seconds": lambda self: 7200, "_turn_steps": lambda self: 200})()
    fact = agent_delegation.DelegationLoop._limit_fact
    assert fact(loop, agent_delegation.TURN_TIME_LIMIT)[0] == "It reached its time limit (120 minutes per message)."
    assert "allowance" in fact(loop, agent_delegation.TURN_ALLOWANCE_LIMIT)[1]
    for reason in agent_delegation.WRAP_UP_REASONS:
        text, then = fact(loop, reason)
        assert text and then


# --- I9: a gate's entry names its step and its wait -----------------------------------

def test_a_gate_entry_names_its_step_and_its_wait(store):
    from test_agent_gate import gated, go, replies
    script, loop, ran = gated(store, live={})
    script.live.update(anthropic=replies(script, "anthropic", go), openai=replies(script, "openai", go))
    list(loop.run())
    assert ran
    [(checked, text)] = log_entries(loop, kind="app", name="checked")
    # As fields of the entry, where scripts/audit_report.py reads them first.
    assert checked["step"] == "completion:0" and checked["gate_ms"] == json.loads(text)["gate_ms"]


def test_a_gate_the_user_decides_keeps_its_step_and_wait_on_the_pause(store):
    from test_agent_audit import decide_when_held
    from test_agent_gate import gated, go, halt, replies
    script, loop, ran = gated(store, live={})
    script.live.update(anthropic=replies(script, "anthropic", go), openai=replies(script, "openai", halt))
    waiter = decide_when_held(loop, store, "continue")
    list(loop.run())
    waiter.join(5)
    [(paused, _)] = log_entries(loop, kind="app", name="paused")
    assert paused["step"] == "completion:0" and type(paused["gate_ms"]) is int


# --- L7: what an unknown tool's refusal says ------------------------------------------

def _refusal(names, called="browser"):
    from pydantic import BaseModel, ConfigDict
    from app.services.agent_tools import ReadOnlyTool, ToolRegistry

    class Args(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)

    registry = ToolRegistry([ReadOnlyTool(name, name, Args, lambda args, **kw: {}) for name in names])
    with pytest.raises(ValueError) as refused:
        registry.validate({"function": {"name": called, "arguments": "{}"}})
    return str(refused.value)


def test_an_unknown_tool_refusal_says_only_what_holds():
    # read_source: no claim which pages it opens (in audit mode any public page).
    text = _refusal(["read_source", "find_pictures"])
    assert "Of these, read_source opens web pages." in text and "cited" not in text
    # A direct call of the browser while the workspace is closed names open_workspace.
    text = _refusal(["read_source", "open_workspace"])
    assert "open_workspace ran" in text and "unknown tool" in text
    # Without any way to a page, as before.
    assert "There is no tool that opens web pages." in _refusal(["compare_models"], called="open_url")
    # With the browser listed, nothing more to say.
    assert _refusal(["browser", "vm_exec"], called="fetch").endswith("Available tools: browser, vm_exec.")


# --- K6: the browser's reads wait for the next round ----------------------------------

def _step(*calls):
    return ({"kind": "step"}, json.dumps({"tool_calls": [
        {"id": f"c{n}", "name": name, "arguments": json.dumps(arguments) if isinstance(arguments, dict) else arguments}
        for n, (name, arguments) in enumerate(calls)]}))


@pytest.mark.parametrize("action", ["read", "text", "find", "tabs", "screenshot"])
def test_a_browser_read_is_quiet_like_reading_a_file(action):
    from app.services.agent_audit import QUIET_STEPS, work_goes_on
    read = _step(("browser", {"action": action, "text": "Login"}))
    assert not work_goes_on([read]) and not work_goes_on([read] * (QUIET_STEPS - 1))
    # Quiet steps still get their round once QUIET_STEPS of them came.
    assert work_goes_on([read] * QUIET_STEPS)
    assert not work_goes_on([_step(("browser", {"action": action}), ("vm_read_file", {"path": "a"}))])


@pytest.mark.parametrize("arguments", [
    {"action": "open", "url": "https://example.com"}, {"action": "click", "ref": "e1"},
    {"action": "type", "ref": "e2", "text": "read"}, {"action": "wait", "seconds": 5},
    {"action": "download"}, {"action": "key", "key": "Enter"}, {"action": "scroll", "direction": "down"},
    {}, "not json", '["read"]'])
def test_every_other_browser_call_gets_its_round(arguments):
    from app.services.agent_audit import work_goes_on
    assert work_goes_on([_step(("browser", arguments))])
    # Also beside a quiet read in the same step.
    assert work_goes_on([_step(("browser", {"action": "read"}), ("browser", arguments))])


# --- T2: several calls per step while the workspace is open ---------------------------

def tool_results(loop):
    """Every tool result by its call's id, in order (each id at most once)."""
    found = {}
    for message in loop.messages:
        if message.get("role") == "tool":
            assert message["tool_call_id"] not in found
            found[message["tool_call_id"]] = json.loads(message["content"])
    return found


def every_call_answered(loop):
    calls = [call["id"] for m in loop.messages if m.get("role") == "assistant" for call in m.get("tool_calls") or []]
    return sorted(calls) == sorted(tool_results(loop))


def ran(fake_vm, command):
    return any(call[0] == "exec" and call[2] == command for call in fake_vm.calls)


def test_several_calls_per_step_only_while_the_workspace_is_open(store, fake_vm):
    script = Steps([[("vm_exec", {"command": "ls"}), ("vm_exec", {"command": "pwd"})]])
    list(vm_loop(store, script).run())
    assert script.parallel == [True, True]
    # Closed: one call per step until open_workspace ran, from the next step
    # on several, together with its tools (one cache break), never back.
    script = Steps([[("open_workspace", {"task": "Run the script"})], [("vm_exec", {"command": "ls"})]])
    list(vm_loop(store, script, request_id="two", workspace_closed=True).run())
    assert script.parallel == [False, True, True]
    # Without the workspace: one call per step, as before.
    script = Steps([[("no_such_tool", {})]])
    list(vm_loop(store, script, request_id="three", vm="off").run())
    assert script.parallel and set(script.parallel) == {False}


def test_the_calls_of_a_step_run_in_order_and_a_fifth_gets_a_result(store, fake_vm):
    from app.services.prompt_defaults import AGENT_VM_PROMPT
    commands = ["ls", "pwd", "whoami", "date", "uptime"]
    script = Steps([[("vm_exec", {"command": command}) for command in commands]])
    loop = vm_loop(store, script)
    list(loop.run())
    found = tool_results(loop)
    assert [found[f"call_0_{n}"].get("exit_code") for n in range(4)] == [0, 0, 0, 0]
    assert found["call_0_4"] == {"error": agent_delegation.CALL_OVER_LIMIT}
    assert [ran(fake_vm, command) for command in commands] == [True, True, True, True, False]
    assert every_call_answered(loop)
    # The prompt says what holds, as a fact.
    words = ["", "one", "two", "three", "four"]
    assert f"up to {words[agent_delegation.TOOL_CALLS_PER_STEP]}." in AGENT_VM_PROMPT


def test_the_client_keeps_a_call_past_the_limit_without_its_arguments():
    value = AgentCompletion()
    value.tool_call_limit, value.keep_over_limit = 2, True
    value._tool_delta([{"index": n, "id": f"c{n}", "type": "function",
                        "function": {"name": "vm_exec", "arguments": '{"command": "ls"}'}} for n in range(3)])
    calls = value._completed_tool_calls()
    assert [call["function"]["arguments"] for call in calls] == ['{"command": "ls"}', '{"command": "ls"}', "{}"]
    assert value.over_limit_ids == {"c2"} and value.skipped_tool_parts == 0
    # Off (other loops, workers): skipped as before.
    value = AgentCompletion()
    value.tool_call_limit = 2
    value._tool_delta([{"index": n, "id": f"c{n}", "type": "function", "function": {"name": "x", "arguments": "{}"}}
                       for n in range(3)])
    assert [call["id"] for call in value._completed_tool_calls()] == ["c0", "c1"] and value.skipped_tool_parts == 1


def test_the_request_asks_for_several_calls_only_when_the_loop_does(monkeypatch):
    sent = []

    def lines(url, **kwargs):
        sent.append(kwargs["json"])
        yield "data: " + json.dumps({"choices": [{"delta": {"content": "Hi"}, "finish_reason": "stop"}],
                                     "usage": {"prompt_tokens": 1, "completion_tokens": 1}})
        yield ""
    monkeypatch.setattr(agent_client, "cancellable_sse_lines", lines)
    tools = [{"type": "function", "function": {"name": "x", "description": "x", "parameters": {"type": "object"}}}]
    for parallel in (False, True):
        completion = AgentCompletion()
        completion.parallel_tool_calls = parallel
        list(completion.stream(model=AgentModel(), messages=[{"role": "user", "content": "Hi"}], api_key="k",
                               tools=tools, allow_tool_calls=True))
    assert [body["parallel_tool_calls"] for body in sent] == [False, True]


class ProbeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def probing(store, steps, action):
    """A workspace turn with a tool ``probe`` that runs ``action(loop)``."""
    from app.services.agent_tools import ReadOnlyTool, ToolRegistry
    loop = vm_loop(store, Steps(steps))

    def probe(args, *, cancellation):
        action(loop)
        return {"status": "done"}
    loop.registry = ToolRegistry([*loop.registry.tools.values(), ReadOnlyTool("probe", "Probe.", ProbeArgs, probe)],
                                 argument_limit=loop.registry.argument_limit)
    return loop


HALT = {"reviewer": "Claude Haiku 4.5", "provider": "anthropic", "kind": "harm", "reason": "Sends the notes out.",
        "entry": 1}


@pytest.mark.parametrize("decision, expected", [("continue", agent_delegation.CALL_AFTER_PAUSE),
                                                ("steer", agent_delegation.HOLD_STEERED)])
def test_a_halt_between_calls_ends_the_steps_later_calls(store, fake_vm, decision, expected):
    from test_agent_audit import decide_when_held
    loop = probing(store, [[("probe", {}), ("vm_exec", {"command": "ls"}), ("vm_exec", {"command": "pwd"})]],
                   lambda loop: loop.request_hold(dict(HALT)))
    waiter = decide_when_held(loop, store, decision, "Not that file.")
    list(loop.run())
    waiter.join(5)
    found = tool_results(loop)
    assert found["call_0_0"] == {"status": "done"}
    assert found["call_0_1"] == found["call_0_2"] == {"error": expected}
    assert not ran(fake_vm, "ls") and not ran(fake_vm, "pwd") and every_call_answered(loop)
    # The reviewer's words never reach the agent.
    assert HALT["reason"] not in json.dumps(loop.messages)


def test_a_halt_before_the_first_call_lets_the_step_run_on_the_users_go(store, fake_vm):
    from test_agent_audit import decide_when_held
    loop = vm_loop(store, Steps([[("vm_exec", {"command": "ls"}), ("vm_exec", {"command": "pwd"})]]))
    halts = [dict(HALT)]

    def halt_after_the_step(value):
        # Once the step is settled, before its first call (the reviewers
        # follow its log entry, which lists the calls).
        if halts:
            loop.request_hold(halts.pop())
    loop._open_gate = halt_after_the_step
    waiter = decide_when_held(loop, store, "continue")
    list(loop.run())
    waiter.join(5)
    assert ran(fake_vm, "ls") and ran(fake_vm, "pwd")


def test_asking_the_user_ends_the_steps_later_calls(store, fake_vm):
    from app.services import agent_ask
    from test_agent_audit import decide_when_held
    loop = vm_loop(store, Steps([[("ask_user", {"request": "May I delete the file?"}),
                                  ("vm_exec", {"command": "rm notes.txt"})]]))
    waiter = decide_when_held(loop, store, "continue")
    list(loop.run())
    waiter.join(5)
    found = tool_results(loop)
    assert found["call_0_0"] == agent_ask.ANSWERS[("confirm", "continue")]
    assert found["call_0_1"] == {"error": agent_delegation.CALL_AFTER_ASK}
    assert not ran(fake_vm, "rm notes.txt") and every_call_answered(loop)


def test_an_ask_without_a_card_leaves_the_steps_later_calls_running(store, fake_vm):
    # Arguments ask_user refuses: no card, nothing asked, the step goes on.
    loop = vm_loop(store, Steps([[("ask_user", {"request": "?"}), ("vm_exec", {"command": "ls"})]]))
    list(loop.run())
    found = tool_results(loop)
    assert "error" in found["call_0_0"] and found["call_0_1"]["exit_code"] == 0 and ran(fake_vm, "ls")


def test_the_users_turn_in_the_browser_ends_the_steps_later_calls(store, fake_vm):
    loop = vm_loop(store, Steps([[("vm_exec", {"command": "ls"}), ("vm_exec", {"command": "pwd"}),
                                  ("vm_exec", {"command": "whoami"})]]))
    answers = iter([None, "handed_back"])

    def takeover():
        return next(answers)
        yield
    loop._takeover_wait = takeover
    list(loop.run())
    found = tool_results(loop)
    assert found["call_0_0"]["exit_code"] == 0
    assert found["call_0_1"] == found["call_0_2"] == {"error": agent_delegation.CALL_AFTER_TAKEOVER}
    assert not ran(fake_vm, "pwd") and every_call_answered(loop)


def test_a_refused_domain_ends_the_steps_later_calls(store, fake_vm):
    from app.services.agent_domains import DOMAIN_DENIED
    from test_agent_audit import decide_when_held
    loop = vm_loop(store, Steps([[("request_domain", {"domain": "api.example.com", "reason": "Its API."}),
                                  ("vm_exec", {"command": "curl https://api.example.com"})]]))
    waiter = decide_when_held(loop, store, "deny")
    list(loop.run())
    waiter.join(5)
    found = tool_results(loop)
    assert found["call_0_0"] == {"error": DOMAIN_DENIED.format(domain="api.example.com")}
    assert found["call_0_1"] == {"error": agent_delegation.CALL_AFTER_DENIAL.format(domain="api.example.com")}
    assert every_call_answered(loop)


# --- L3: a line of facts after each batch ---------------------------------------------

def test_each_batch_ends_with_the_steps_and_minutes_of_the_message(store, fake_vm):
    script = Steps([[("vm_exec", {"command": "ls"})], [("vm_exec", {"command": "pwd"})]])
    loop = vm_loop(store, script)
    list(loop.run())
    first, second, third = script.requests
    line = re.compile(r"\[consens\.io, written by the app: step (\d) of at most (\d+), \d+\.\d of (\d+) minutes "
                      r"in this message\.\]")
    assert [line.fullmatch(request[-1]["content"]).group(1) for request in (second, third)] == ["1", "2"]
    steps, minutes = line.fullmatch(third[-1]["content"]).group(2, 3)
    assert (int(steps), int(minutes)) == (loop._turn_steps(), loop._turn_seconds() // 60)
    # New content at the end only: each request continues the one before.
    assert second[:len(first)] == first and third[:len(second)] == second
    # A message without the workspace has no such line.
    script = Steps([[("no_such_tool", {})]])
    list(vm_loop(store, script, request_id="two", vm="off").run())
    assert not any(str(m.get("content")).startswith(agent_delegation.PROGRESS_OPEN)
                   for request in script.requests for m in request)


# --- L1, L6: pictures of the batch stay, older ones leave together ----------------------

def test_pictures_of_this_batch_stay_and_older_ones_leave_together(store, fake_vm):
    from app.services import agent_compaction
    from app.services.agent_browser import SCREENSHOT_INTRO
    from app.services.agent_vm_tools import PICTURE_INTRO
    from app.services.agent_web_images import INTRO
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 64
    loop = vm_loop(store, Steps())

    class Pictures:
        batch = []

        def take_pictures(self):
            batch, self.batch = self.batch, []
            return batch
    loop.image_tools = pictures = Pictures()

    def batch(*intros):
        loop.messages.append({"role": "assistant", "content": ""})
        pictures.batch = [("p", "image/webp", png, intro) for intro in intros]
        before = list(loop.messages)
        loop._show_pictures()
        return before

    def shown():
        return [m["content"][1].get("text") or "image" for m in loop.messages[loop.turn_start:]
                if agent_compaction.is_picture(m)]
    web = [INTRO.format(id=f"p{n}", url="https://example.com") for n in range(1, 7)]
    # find_pictures' six pictures all reach the agent (before: three left at once).
    batch(*web)
    assert shown() == ["image"] * 6
    # Up to PICTURES_SHOWN nothing earlier changes: the cached prefix stays.
    screenshot = SCREENSHOT_INTRO.format(url="https://example.com")
    before = batch(screenshot, PICTURE_INTRO.format(path="/home/agent/chart.png"))
    assert loop.messages[:len(before)] == before
    # Past it, every seen picture but the newest PICTURES_KEPT leaves at once,
    # never one of this batch; each says the way back by where it came from.
    batch(*web[:3])
    assert shown() == ([agent_compaction.WEB_PICTURE_GONE] * 6 + [agent_compaction.SCREENSHOT_GONE,
                       agent_compaction.PICTURE_GONE] + ["image"] * 3)
    assert agent_compaction.PICTURES_KEPT == 3


# --- T3: the settlement reads its ledger day in its one round trip ----------------------

def _counting_store():
    from app.services.agent_runs import AgentRunStore
    from test_agent_runs import Database
    from test_chat_history import FakeTransaction
    trips = []

    class Counting(FakeTransaction):
        def get(self, ref):
            trips.append(("get", ref.path))
            return super().get(ref)

        def get_all(self, refs):
            refs = list(refs)
            trips.append(("get_all", len(refs)))
            return [FakeTransaction.get(self, ref) for ref in refs]

    class CountingDatabase(Database):
        def run_transaction(self, operation):
            with self.lock:
                transaction = Counting(self)
                result = operation(transaction)
                transaction.commit()
                return result
    return AgentRunStore(CountingDatabase()), trips


def _settled_step(guess):
    """A delegated step claimed and settled; ``guess``: whether the
    settlement may read the expected ledger day with the rest."""
    from app.services import agent_quota
    from test_agent_delegation import make_loop
    store, trips = _counting_store()
    if not guess:
        store._expected_daily = lambda uid: None
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(500, 100))
    del trips[:]
    store.settle(*args, completion=receipt(), status="succeeded", final=False)
    saved = store.receipt_ref(*args).get().to_dict()
    day = agent_quota.quota_ref(store.db, UID, saved["quota_day"])
    ledger = {key: value for key, value in store.db.documents[day.path].items() if not key.endswith("_at")}
    return trips, saved, ledger


def test_a_settlement_is_one_read_round_trip_and_books_the_same():
    trips, saved, ledger = _settled_step(guess=True)
    # One batched read (the ledger day with the rest), no read of its own.
    assert [kind for kind, _ in trips] == ["get_all"]
    before_trips, before_saved, before_ledger = _settled_step(guess=False)
    assert [kind for kind, _ in before_trips] == ["get_all", "get"]
    # The allowance and the receipt come out exactly the same.
    assert ledger == before_ledger
    assert saved["quota_charged"] == before_saved["quota_charged"] and saved["usage"] == before_saved["usage"]


def test_a_step_claimed_on_another_ledger_day_reads_its_own(monkeypatch):
    """A call claimed before midnight (or a reset) settles into its own day."""
    from app.services import agent_quota
    from app.services.agent_runs import AgentRunStore
    store, trips = _counting_store()
    from test_agent_delegation import make_loop
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(500, 100))
    monkeypatch.setattr(AgentRunStore, "_expected_daily",
                        lambda self, uid: agent_quota.quota_ref(store.db, uid, "2026-10-31"))
    del trips[:]
    store.settle(*args, completion=receipt(), status="succeeded", final=False)
    assert [kind for kind, _ in trips] == ["get_all", "get"]
    assert store.receipt_ref(*args).get().to_dict()["status"] == "succeeded"


# --- I6: anonymous times of every workspace turn ---------------------------------------

def test_a_workspace_turn_counts_its_times_without_any_name(store, fake_vm, monkeypatch):
    from app.services import agent_audit_metrics
    recorded = []
    monkeypatch.setattr(agent_audit_metrics, "record", recorded.append)
    script = Steps([[("vm_exec", {"command": "ls"})], [("browser", {"action": "read"})]])
    loop = vm_loop(store, script, audit="off")
    list(loop.run())
    # Outside audit mode too: the turn used the workspace.
    assert recorded == [loop]
    captured = agent_audit_metrics.capture(loop)
    run = captured["workspace_run"]
    assert captured["audit"] is False and run["steps"] == 3 and run["outages"] == []
    assert run["first"]["kind"] == "vm" and type(run["first"]["ms"]) is int and run["first"]["failed"] is False
    turn = store._turn_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    counters = agent_audit_metrics.turn_counters(turn, captured)
    # Its own fields only, never the audit counters.
    assert set(counters) == {"ws_turns", "ws_steps", "ws_active_s", "ws_first_call_s", "ws_first_result_s"}
    assert counters["ws_turns"] == {"completed": 1} and counters["ws_steps"] == {"le3": 1}
    assert list(counters["ws_first_call_s"]) == ["vm"]
    # Nothing that names the account, the chat, the turn or any text.
    written = json.dumps(counters)
    assert not any(value in written for value in (UID, loop.chat_id, loop.turn_id, "ls", ANSWER))


def test_a_turn_without_the_workspace_adds_no_workspace_fields(store, fake_vm, monkeypatch):
    from app.services import agent_audit_metrics
    recorded = []
    monkeypatch.setattr(agent_audit_metrics, "record", recorded.append)
    loop = vm_loop(store, Steps(), audit="off")
    list(loop.run())
    assert recorded == []
    loop = vm_loop(store, Steps(), request_id="two")
    list(loop.run())
    # An audit turn counts as before, without workspace fields.
    assert recorded == [loop] and "workspace_run" not in agent_audit_metrics.capture(loop)


def test_outages_failed_turns_and_wrap_ups_are_counted_by_code():
    from app.services.agent_audit_metrics import turn_counters
    captured = {"audit": False, "wrap_up": "time", "ended_at": datetime.now(timezone.utc), "workspace_run": {
        "steps": 120, "active_s": 7300.0, "outages": ["vm_unavailable", "browser_off"],
        "first": {"kind": "browser", "ms": 59_000, "after_s": 12.0, "failed": True}}}
    counters = turn_counters({"status": "failed", "agent_failure": {"code": "run_limit"}}, captured)
    assert counters["wrap_up"] == {"time": 1} and counters["ws_steps"] == {"le200": 1}
    assert counters["ws_active_s"] == {"over7200": 1} and counters["ws_first_call_s"] == {"browser": {"le60": 1}}
    assert counters["ws_first_result_s"] == {"le90": 1}
    assert counters["ws_failures"] == {"first_call": 1, "vm_unavailable": 1, "browser_off": 1, "turn_run_limit": 1}


def test_the_report_reads_workspace_counters_and_the_step_split():
    from datetime import timedelta
    from scripts.audit_report import render, report, step_split
    t0 = datetime(2026, 10, 30, 10, tzinfo=timezone.utc)
    at = lambda seconds: t0 + timedelta(seconds=seconds)  # noqa: E731
    receipts = [{"account": "guest", "own": False, "chat": "c1", "turn": "t1", "step": f"completion:{n}",
                 "created_at": at(10 * n), "request_started_at": at(10 * n + .3),
                 "first_token_at": at(10 * n + 1.3), "stream_ended_at": at(10 * n + 3.3),
                 "settled_at": at(10 * n + 3.5)} for n in range(3)]
    split = step_split([*receipts, {"step": "agent:" + "a" * 32 + ":0", "created_at": at(0)}])
    assert (split["before_request"]["p50"], split["to_first_token"]["p50"], split["stream"]["p50"],
            split["after_stream"]["p50"]) == (.3, 1.0, 3.0, .2)
    counters = [{"day": "2026-10-30", "ws_turns": {"completed": 2}, "ws_steps": {"le10": 2},
                 "ws_failures": {"browser_off": 1}, "wrap_up": {"steps": 1}}]
    result = report({"receipts": receipts, "turns": {}, "counters": counters, "since": t0})
    assert result["workspace"]["ws_turns"] == {"completed": 2} and result["workspace"]["wrap_up"] == {"steps": 1}
    assert result["times"]["agent_step"]["stream"]["n"] == 3
    shown = render(result)
    assert "Workspace turns" in shown and "browser_off" in shown and "agent step after_stream" in shown
