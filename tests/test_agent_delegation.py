"""Helper sessions (delegate) with deterministic providers; no paid calls."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import threading
from datetime import datetime, timedelta, timezone

import pytest
pytestmark = pytest.mark.usefixtures("deepseek_default_agent")

from app.services.agent_delegation import DelegationLoop
from app.services.agent_provider_limits import AgentRunInterrupted
from app.services.agent_delegation_config import defaults
from app.services.agent_costs import RunCosts
from app.services.agent_policy import AgentPolicy
from app.services.chat_store import ChatNotFound, TurnStatusConflict
from app.services.llm.agent_client import AgentCompletion, measured_usage, resolve_agent_model
from app.services.llm.provider_runtime import AnalysisBudgetExceeded, ProviderCancellation, ProviderCancelled
from test_agent_runs import UID, AUTH, api, pending, receipt, store, totals, priced
from test_agent_loop import packet, transport


def assignment(title):
    """A helper's session as the store keeps it."""
    return {"goal": title, "context": "A=2, B=3"}


def make_loop(store, factory=AgentCompletion, **kwargs):
    chat, turn = pending(store)
    config = defaults()
    config["enabled"] = True
    config["max_searches"] = 0
    return DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"), messages=[{"role": "system", "content": "Answer."},
        {"role": "user", "content": "Verify two independent calculations."}], api_key="test-delegation",
        cancellation=ProviderCancellation(), policy=AgentPolicy.from_config(config), delegation_config=config,
        completion_factory=factory, **kwargs)


def call(name, data, identity):
    return {"id": identity, "type": "function", "function": {"name": name, "arguments": json.dumps(data)}}


def task_of(messages):
    """A helper's first task: its conversation's first user message."""
    return messages[1]["content"].split("\n", 1)[0]


class Conversation:
    """The agent delegates two calculations in one step; the multiply helper
    reports a wrong product, the agent sends it a next task in the same
    session, and answers once both reports stand."""

    def __init__(self):
        self.gate = threading.Barrier(2)
        self.loop = None
        self.actions = []
        self.helper_contexts = []
        self.agent_messages = []
        self.failure = None

    def factory(self):
        plan = self
        class Completion(AgentCompletion):
            def stream(self, *, model, messages, **kwargs):
                calls = []
                if self.step_id.startswith("agent:"):
                    index = int(self.step_id.split(":")[-1])
                    task = task_of(messages)
                    plan.helper_contexts.append(json.loads(json.dumps(messages)))
                    if index == 0:
                        plan.gate.wait(timeout=5)  # Both paid helper steps really overlap.
                    if task == "multiply" and index == 0:
                        self.text = "5"
                    elif task == "multiply":
                        assert "Next task from the agent:\nCheck 2 times 3; 5 is incorrect." in messages[-1]["content"]
                        self.text = "6"
                    elif plan.failure:
                        raise plan.failure
                    else:
                        self.text = "5"
                else:
                    plan.agent_messages.append(json.loads(json.dumps(messages)))
                    helpers = {task_of(w.messages): w for w in plan.loop.workers.values()}
                    if not helpers:
                        calls = [call("delegate", {"task": "multiply", "context": "A=2, B=3"}, "call_1"),
                                 call("delegate", {"task": "sum", "context": "A=2, B=3"}, "call_2")]
                    elif helpers["multiply"].calls == 1:
                        calls = [call("delegate", {"task": "Check 2 times 3; 5 is incorrect.",
                                                   "helper_id": helpers["multiply"].id}, "call_3")]
                    else:
                        self.text = "Product 6; sum 5."
                self.usage = measured_usage({"prompt_tokens": 100, "completion_tokens": 20, "cost": .0002}, model)
                if calls:
                    plan.actions.extend(c["function"]["name"] for c in calls)
                    self.tool_calls = calls
                    self.finish_reason = "tool_calls"
                else:
                    self.finish_reason = "stop"
                    yield {"type": "delta", "text": self.text}
        return Completion()


def tool_results(messages):
    return {m["tool_call_id"]: json.loads(m["content"]) for m in messages if m.get("role") == "tool"}


def test_two_helpers_work_side_by_side_and_a_next_task_goes_on_in_the_same_session(store):
    script = Conversation()
    loop = script.loop = make_loop(store, script.factory)
    events = list(loop.run())
    assert loop.completion.text == "Product 6; sum 5."
    assert len(loop.workers) == 2 and script.actions == ["delegate"] * 3
    assert all(not w.thread.is_alive() for w in loop.workers.values())
    multiply = next(w for w in loop.workers.values() if task_of(w.messages) == "multiply")
    # The reports reach the agent as the calls' results, in the order of its calls.
    first = tool_results(script.agent_messages[1])
    assert first["call_1"] == {"helper_id": multiply.id, "report": "5"}
    assert first["call_2"]["report"] == "5"
    assert tool_results(script.agent_messages[2])["call_3"] == {"helper_id": multiply.id, "report": "6"}
    # The helper sees its task and the agent's context, never the agent's chat.
    helper_view = json.dumps(script.helper_contexts[0])
    assert "A=2, B=3" in helper_view and "Verify two independent calculations" not in helper_view
    detail = store.delegation_view(UID, loop.chat_id, loop.turn_id, agent_id=multiply.id)
    assert [m["kind"] for m in detail["messages"]] == ["result", "message", "result"]
    assert [m["text"] for m in detail["messages"] if m["kind"] == "result"] == ["5", "6"]
    assert detail["agent"]["assignment"] == assignment("multiply")
    assert detail["agent"]["title"] == "multiply" and detail["agent"]["status"] == "completed"
    seqs = [e["seq"] for e in events if e["type"] == "delegation"]
    assert seqs == sorted(set(seqs))
    assert totals(store)["calls"] == loop.costs.calls
    assert totals(store)["estimated_cost_nano_usd"] == loop.costs.calls * 200_000
    assert loop.completion.usage["estimated_cost_nano_usd"] == totals(store)["estimated_cost_nano_usd"]
    assert detail["agent"]["usage"]["estimated_cost_nano_usd"] == 400_000
    view = store.delegation_view(UID, loop.chat_id, loop.turn_id)
    assert view["usage"] == loop.completion.usage
    page = store.delegation_view(UID, loop.chat_id, loop.turn_id, agent_id=multiply.id, limit=2)
    assert page["has_more"] and len(page["messages"]) == 2
    next_page = store.delegation_view(UID, loop.chat_id, loop.turn_id, agent_id=multiply.id,
                                      after=page["messages"][-1]["seq"])
    assert len(next_page["messages"]) == 1
    with pytest.raises(ChatNotFound):
        store.delegation_view("other-owner", loop.chat_id, loop.turn_id, agent_id=multiply.id)


def test_simple_request_does_not_delegate_or_repeat_after_reload(store, monkeypatch):
    requests, _, _ = transport(monkeypatch, [[packet({"content": "Hello"}, finish="stop",
        usage={"prompt_tokens": 10, "completion_tokens": 2, "cost": .001})]])
    loop = make_loop(store)
    list(loop.run())
    assert not loop.workers and len(requests) == 1
    assert [tool["function"]["name"] for tool in requests[0]["tools"]] == ["delegate"]
    assert store.delegation_view(UID, loop.chat_id, loop.turn_id)["agents"] == []
    assert not store.claim(UID, loop.chat_id, loop.turn_id, loop.model, run_token=loop.run_token,
                          policy=loop.policy.snapshot(), reservation=(10, priced(10)))


def test_a_failed_helper_reports_why_and_unknown_cost_and_the_agent_still_answers(store):
    script = Conversation()
    script.failure = RuntimeError("Upstream unavailable")
    loop = script.loop = make_loop(store, script.factory)
    list(loop.run())
    assert loop.completion.text == "Product 6; sum 5."
    failed = tool_results(script.agent_messages[1])["call_2"]
    assert failed["status"] == "failed" and failed["reason"]
    assert loop.completion.usage["complete"] is False
    assert loop.completion.usage["cost_complete"] is False
    assert totals(store)["unmetered_calls"] == 1
    assert totals(store)["estimated_cost_nano_usd"] == (loop.costs.calls - 1) * 200_000


def test_activity_view_reuses_the_receipt_read_for_lease_check(store):
    loop = make_loop(store)
    assert store.claim(UID, loop.chat_id, loop.turn_id, loop.model, run_token=loop.run_token,
                       policy=loop.policy.snapshot(), reservation=(100, priced(100)))
    store.db.read_log.clear()
    assert store.delegation_view(UID, loop.chat_id, loop.turn_id)['status'] == 'running'
    path = store.receipt_ref(UID, loop.chat_id, loop.turn_id).path
    assert store.db.read_log.count(path) == 1


def test_atomic_durable_and_memory_budget_reservations(store):
    loop = make_loop(store)
    policy = replace(loop.policy, max_cost_nano_usd=100)
    args = (UID, loop.chat_id, loop.turn_id, loop.model)
    # The run's own cost budget in nano-USD (max_cost_nano_usd=100); the
    # account holds a rounded-up micro-euro for each.
    assert store.claim(*args, policy=policy.snapshot(), run_token=loop.run_token, reservation=(1, 10))
    store.settle(*args[:3], completion=receipt(measured=False), status="succeeded", final=False)
    ids = ["a" * 32, "b" * 32]
    for agent_id in ids:
        store.publish_agent(*args[:3], run_token=loop.run_token, agent_id=agent_id, patch={"assignment": {"goal": "test"}, "status": "waiting"})
    def claim(agent_id):
        try:
            return store.claim(*args, step=f"agent:{agent_id}:0", run_token=loop.run_token, reservation=(1, 80))
        except AnalysisBudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(claim, ids)) == 1
    assert store.receipt_ref(*args[:3]).get().to_dict()["reserved_cost"] == 90
    costs = RunCosts(replace(loop.policy, max_calls=1))
    def reserve(_):
        try:
            costs.reserve(loop.model, [])
            return True
        except AnalysisBudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(reserve, range(2))) == 1


def test_crashed_process_never_restarts_paid_steps_and_deduplicates_events(store):
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, policy=loop.policy.snapshot(), run_token=loop.run_token, reservation=(10, priced(10)))
    aid = "f" * 32
    publish = dict(run_token=loop.run_token, agent_id=aid, event_id="same", patch={"assignment": {"goal": "Test"}, "status": "working"})
    assert store.publish_agent(*args, **publish) == store.publish_agent(*args, **publish)
    first = f"agent:{aid}:0"
    store.claim(*args, loop.model, step=first, run_token=loop.run_token, reservation=(2000, priced(2000)))
    store.settle(*args, completion=receipt(), status="succeeded", step=first, final=False)
    store.claim(*args, loop.model, step=f"agent:{aid}:1", run_token=loop.run_token, reservation=(2000, priced(2000)))
    root = store.receipt_ref(*args)
    store._transaction(lambda tx: tx.update(root, {"lease_until": datetime.now(timezone.utc) - timedelta(seconds=1)}))
    view = store.delegation_view(*args)
    assert view["status"] == "cancelled" and view["agents"][0]["status"] == "stopped"
    assert totals(store)["calls"] == 3 and totals(store)["unmetered_calls"] == 2
    assert view["agents"][0]["usage"]["cost_complete"] is False
    assert view["agents"][0]["usage"]["estimated_cost_nano_usd"] == receipt().usage["estimated_cost_nano_usd"]
    assert not store.claim(*args, loop.model, policy=loop.policy.snapshot(), run_token=loop.run_token, reservation=(10, priced(10)))
    with pytest.raises(TurnStatusConflict):
        store.publish_agent(*args, run_token=loop.run_token, agent_id=aid, patch={"status": "completed"})
    store.delete_chat(UID, loop.chat_id)
    assert not any("agents" in path or "agent_events" in path for path in store.db.documents)


def test_reasoning_continuation_preserves_signed_blocks_without_public_exposure(store, monkeypatch):
    # Gemini shape: readable thought and its signature share index 0; the
    # signature is discrete and replayed byte for byte, never joined or dropped.
    thought = {"type": "reasoning.text", "index": 0, "format": "google-gemini-v1", "text": "private-thought"}
    encrypted = {"type": "reasoning.encrypted", "index": 0, "id": "wait", "format": "google-gemini-v1", "data": "private-token"}
    requests, _, _ = transport(monkeypatch, [
        [packet({"reasoning_details": [thought]}), packet({"reasoning_details": [encrypted],
          "tool_calls": [{"index": 0, "id": "wait", "function": {"name": "delegate", "arguments": '{}'}}]},
          finish="tool_calls", usage={"prompt_tokens": 10, "completion_tokens": 2, "cost": .001})],
        [packet({"content": "Done"}, finish="stop", usage={"prompt_tokens": 10, "completion_tokens": 2, "cost": .001})],
    ])
    loop = make_loop(store)
    events = list(loop.run())
    continuation = requests[1]["messages"][2]
    assert continuation["reasoning_details"] == [encrypted]
    assert "private-token" not in json.dumps(events)
    assert "private-token" not in json.dumps(store.get_turn(UID, loop.chat_id, loop.turn_id), default=str)
    assert requests[0]["parallel_tool_calls"] is True


def test_bounded_parallel_tool_batch_is_replayed_with_every_result(store, monkeypatch):
    # Refused before any helper starts (no task): each call still gets its result.
    calls = [{"index": i, "id": f"wait_{i}", "function": {"name": "delegate", "arguments": '{}'}} for i in range(2)]
    requests, _, _ = transport(monkeypatch, [
        [packet({"tool_calls": calls}, finish="tool_calls", usage={"prompt_tokens": 10, "completion_tokens": 2, "cost": .001})],
        [packet({"content": "Done"}, finish="stop", usage={"prompt_tokens": 10, "completion_tokens": 2, "cost": .001})]])
    loop = make_loop(store)
    list(loop.run())
    assert [m["tool_call_id"] for m in requests[1]["messages"] if m["role"] == "tool"] == ["wait_0", "wait_1"]
    assert loop.tools_used == 2


def test_delegation_endpoints_are_owner_bound_and_read_only(api):
    client, store, _ = api
    loop = make_loop(store, mock_answer="Answer")
    list(loop.run())
    url = f"/agent/chats/{loop.chat_id}/turns/{loop.turn_id}/agents"
    assert client.get(url, headers=AUTH).status_code == 200
    assert client.get(url, headers=AUTH).headers["cache-control"] == "private, no-store"
    assert client.get(url).status_code == 401
    assert client.get(url.replace(loop.chat_id, "f" * 32), headers=AUTH).status_code == 404
    assert client.get(url + "/" + "a" * 32 + "?limit=51", headers=AUTH).status_code == 422
    assert totals(store)["calls"] == 1


def test_admin_enabled_delegation_is_frozen_and_replay_does_not_consult_new_config(api, monkeypatch):
    from app.api.routers import agent
    from app.services import prompt_config
    client, store, calls = api
    config = {**prompt_config.defaults(), "revision": 7}
    assert config["delegation"]["enabled"] is False  # Off until the paired measurement passes.
    config["delegation"].update(enabled=True, max_agents=2)
    monkeypatch.setattr(prompt_config, "get_config", lambda: config)
    chat = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat, "question": "Hi", "client_request_id": "enabled", "bookmark_id": "enabled"}
    response = client.post("/agent", json=payload, headers=AUTH)
    assert response.status_code == 200 and "event: final" in response.text, response.text
    assert any(tool.get("function", {}).get("name") == "delegate" for tool in calls[0]["tools"])
    monkeypatch.setattr(prompt_config, "get_config", lambda: pytest.fail("Replay must use the saved turn"))
    replay = client.post("/agent", json=payload, headers=AUTH).json()
    settings = replay["turn"]["agent_settings"]
    assert settings["config_revision"] == 7 and settings["policy"]["delegation"] is True
    assert settings["delegation_config"]["max_agents"] == 2
    assert len(calls) == 1


def test_stop_joins_all_helpers_and_accounts_every_started_step(store):
    script = Conversation()
    loop = script.loop = make_loop(store, script.factory)
    source = loop.run()
    for event in source:
        if event.get("agent", {}).get("status") == "completed":
            loop.cancellation.cancel()
            break
    with pytest.raises(ProviderCancelled):
        list(source)
    assert all(not worker.thread.is_alive() for worker in loop.workers.values())
    assert totals(store)["unsettled_calls"] == 0
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["error_code"] == "cancelled"


def test_remote_stop_cancels_a_helper_with_an_active_stream(store, monkeypatch):
    """A stop saved by another process reaches the run at its watcher's next
    look (WATCH_SECONDS, 10 s; shortened here), also while delegate waits."""
    from app.services import agent_delegation
    from app.services.llm.provider_runtime import current_provider_cancellation
    monkeypatch.setattr(agent_delegation, "WATCH_SECONDS", .2)
    entered = threading.Event()
    class Completion(AgentCompletion):
        def stream(self, *, model, **kwargs):
            if self.step_id.startswith("agent:"):
                entered.set()
                cancellation = current_provider_cancellation()
                while True:
                    cancellation.raise_if_cancelled()
                    threading.Event().wait(.01)
                    yield {"type": "delta", "text": "still working"}
            self.tool_calls = [call("delegate", {"task": "Check"}, "call")]
            self.finish_reason = "tool_calls"
            self.usage = measured_usage({"prompt_tokens": 10, "completion_tokens": 2, "cost": .001}, model)
    loop = make_loop(store, Completion)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(lambda: list(loop.run()))
        assert entered.wait(5)
        store.stop_delegation(UID, loop.chat_id, loop.turn_id)
        with pytest.raises(ProviderCancelled):
            future.result(timeout=5)
    assert all(not w.thread.is_alive() for w in loop.workers.values())
    assert totals(store)["unsettled_calls"] == 0 and totals(store)["unmetered_calls"] == 1


def test_a_rate_limited_helper_waits_once_then_reports_why_it_failed(store):
    """A helper's 429 before any output waits out Retry-After and tries
    again, as the agent's own step does; a second one ends the helper, not
    the run. The cooldown lands on the helper's model ("fast" here), never
    on the agent's next step."""
    from app.services.agent_provider_limits import ProviderCooldowns
    from app.services.llm.engines import _ProviderHTTPStatusError
    helper_calls, sent = [], []
    class Completion(AgentCompletion):
        def stream(self, *, model, messages, **kwargs):
            if self.step_id.startswith("agent:"):
                helper_calls.append((self.step_id, model.model))
                raise _ProviderHTTPStatusError(429, retry_after=.1)
            sent.append(messages)
            self.usage = measured_usage({"prompt_tokens": 10, "completion_tokens": 2, "cost": .001}, model)
            if len(sent) == 1:
                self.tool_calls = [call("delegate", {"task": "Check 2 + 3", "model": "fast"}, "call")]
                self.finish_reason = "tool_calls"
                return
            self.text, self.finish_reason = "5", "stop"
            yield {"type": "delta", "text": self.text}
    loop = make_loop(store, Completion, cooldowns=ProviderCooldowns())
    events = list(loop.run())
    assert loop.completion.text == "5"
    assert len(helper_calls) == 2 and helper_calls[0][1] != loop.model.model
    [helper] = loop.workers.values()
    assert [step for step, _ in helper_calls] == [f"agent:{helper.id}:0", f"agent:{helper.id}:1"]
    result = tool_results(sent[1])["call"]
    assert result["status"] == "failed" and result["helper_id"] == helper.id
    assert any(e.get("agent", {}).get("failure", {}).get("code") == "provider_rate_limited"
               for e in events if e.get("agent", {}).get("failure"))
    assert loop.completion.usage["cost_complete"] is True


def test_a_helpers_last_step_on_a_task_writes_its_report_without_tools(store):
    seen = []
    class Completion(AgentCompletion):
        def stream(self, *, model, messages, allow_tool_calls=True, **kwargs):
            self.usage = measured_usage({"prompt_tokens": 10, "completion_tokens": 2, "cost": .001}, model)
            if self.step_id.startswith("agent:"):
                seen.append((allow_tool_calls, messages[-1]["content"]))
                if allow_tool_calls:
                    self.tool_calls = [call("web_search", {"queries": ["2 + 3"]}, f"search_{len(seen)}")]
                    self.finish_reason = "tool_calls"
                    return
                self.text, self.finish_reason = "Report: 5", "stop"
            elif self.step_id == "completion:0":
                self.tool_calls = [call("delegate", {"task": "Check 2 + 3"}, "call")]
                self.finish_reason = "tool_calls"
                return
            else:
                self.text, self.finish_reason = "5", "stop"
            yield {"type": "delta", "text": self.text}
    loop = make_loop(store, Completion)
    loop.policy = replace(loop.policy, worker_calls=3)
    list(loop.run())
    assert [allowed for allowed, _ in seen] == [True, True, False]
    assert "last step on this task" in seen[-1][1]
    assert tool_results(loop.messages)["call"]["report"] == "Report: 5"


def test_a_reviewers_halt_holds_the_helpers_until_the_user_decides(store):
    started = threading.Event()
    class Completion(AgentCompletion):
        def stream(self, *, model, messages, **kwargs):
            started.set()
            self.usage = measured_usage({"prompt_tokens": 10, "completion_tokens": 2, "cost": .001}, model)
            self.text, self.finish_reason = "Report", "stop"
            yield {"type": "delta", "text": self.text}
    from app.services.agent_delegation import Delegate
    loop = make_loop(store, Completion)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(1, priced(1)))
    store.settle(*args, completion=receipt(), status="succeeded", final=False)
    loop.hold, loop.hold_started = {"id": "halt", "reasons": []}, loop.clock()
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            report = pool.submit(loop.delegate, Delegate(task="Check"), cancellation=loop.cancellation)
            assert not started.wait(.6)
            # The user's decision reaches the helpers while the card is still
            # open: the run takes it only after the delegate call that waits.
            with loop.condition:
                loop.hold_decision = "continue"
                loop.condition.notify_all()
            assert report.result(timeout=5)["report"] == "Report"
            # A stop ends a held helper; the agent hears why.
            started.clear()
            with loop.condition:
                loop.hold, loop.hold_decision = {"id": "halt2", "reasons": []}, None
            stopped = pool.submit(loop.delegate, Delegate(task="Check again"), cancellation=loop.cancellation)
            assert not started.wait(.4)
            with loop.condition:
                loop.hold_decision = "stop"
                loop.condition.notify_all()
            assert stopped.result(timeout=5)["status"] == "stopped" and not started.is_set()
            # The user's own card (ask_user) holds none.
            with loop.condition:
                loop.hold, loop.hold_decision = {"id": "ask", "ask": {"question": "Which?"}}, None
            assert pool.submit(loop.delegate, Delegate(task="Third"),
                               cancellation=loop.cancellation).result(timeout=5)["report"] == "Report"
    finally:
        loop.closed.set()
        loop.cancellation.cancel()
        for worker in loop.workers.values():
            worker.thread.join(timeout=5)


def test_delegate_refuses_what_a_helper_cannot_do(store):
    from types import SimpleNamespace
    from app.services.agent_delegation import Delegate, Worker
    loop = make_loop(store)
    with pytest.raises(ValueError, match="No helper"):
        loop.delegate(Delegate(task="Again", helper_id="a" * 32), cancellation=loop.cancellation)
    working = loop.workers["b" * 32] = Worker("b" * 32, loop.model, [], state="working")
    with pytest.raises(ValueError, match="still working"):
        loop.delegate(Delegate(task="Again", helper_id=working.id), cancellation=loop.cancellation)
    with pytest.raises(ValueError, match="only task"):
        loop.delegate(Delegate(task="Again", context="More", helper_id=working.id), cancellation=loop.cancellation)
    working.state = "failed"
    with pytest.raises(ValueError, match="has ended"):
        loop.delegate(Delegate(task="Again", helper_id=working.id), cancellation=loop.cancellation)
    loop.policy = replace(loop.policy, max_agents=1)
    with pytest.raises(ValueError, match="the most it may"):
        loop.delegate(Delegate(task="New"), cancellation=loop.cancellation)
    # The description names what a helper has; in a run with its own search
    # and reading the tools themselves.
    assert "web search inside its own requests" in loop.registry.tools["delegate"].description
    # Helpers only on the user's request: the allowance has no cap per message.
    assert "only when the user asked for helpers" in loop.registry.tools["delegate"].description
    loop.web_search = SimpleNamespace(tool=SimpleNamespace(name="web_search"))
    assert "It can use web_search, nothing else" in loop._delegate_tool().description


def test_a_helpers_page_reads_count_toward_its_own_step():
    from types import SimpleNamespace
    from app.services.agent_read_source import SourceReader, helper_step
    reader = SourceReader.__new__(SourceReader)
    reader.loop = SimpleNamespace(routing_steps=3)
    assert reader._step() == 3
    token = helper_step.set("a" * 32 + ":0")
    try:
        assert reader._step() == "a" * 32 + ":0"
    finally:
        helper_step.reset(token)


def test_one_update_the_database_refuses_costs_no_other_session_of_its_batch(store, monkeypatch):
    """A Firestore commit is all or nothing, so one update it refuses for
    good (a document over 1 MiB) would refuse every session of the journal's
    batch: the others are written one by one. A closed run still refuses the
    batch at once, without a write per update."""
    from types import SimpleNamespace
    from uuid import uuid4
    from google.api_core.exceptions import InvalidArgument
    from app.services.agent_journal import JournalJob
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(100, priced(100)))
    publish, calls, closed = store.publish_agents, [], []

    def strict(*a, updates, **k):
        calls.append(len(updates))
        if closed:
            raise TurnStatusConflict("Agent session is closed")
        if any(patch.get("title") == "huge" for _, patch, _, _ in updates):
            raise InvalidArgument("Document exceeds the maximum size")
        return publish(*a, updates=updates, **k)
    monkeypatch.setattr(store, "publish_agents", strict)

    def jobs(*titles):
        return [JournalJob(SimpleNamespace(id=uuid4().hex, state="waiting", session_seq=0),
                           {"title": title, "assignment": assignment(title), "status": "waiting"}, None,
                           progress=False, urgent=False, order=n) for n, title in enumerate(titles)]
    first, huge, second = loop._journal_write(jobs("one", "huge", "two"))
    assert isinstance(huge, InvalidArgument)
    assert first["agent"]["title"] == "one" and second["agent"]["title"] == "two"
    closed.append(True)
    calls.clear()
    with pytest.raises(TurnStatusConflict):
        loop._journal_write(jobs("three", "four"))
    assert calls == [2]


def test_a_retried_session_update_is_saved_once_without_an_event_document(store):
    """A journal batch whose commit was ambiguous is sent again with the same
    event ids (_journal_write): the second time returns what the first saved,
    moves no sequence and adds no message. The session keeps the ids itself:
    event documents (agent_events), read by nothing else, would cost a write
    and a read per update."""
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(100, priced(100)))
    agent_id, event_id = "a" * 32, "e" * 32
    first = store.publish_agent(*args, run_token=loop.run_token, agent_id=agent_id, event_id=event_id,
                                patch={"assignment": assignment("Verify"), "status": "working"},
                                message={"kind": "note", "text": "Started."})
    again = store.publish_agent(*args, run_token=loop.run_token, agent_id=agent_id, event_id=event_id,
                                patch={"assignment": assignment("Verify"), "status": "working"},
                                message={"kind": "note", "text": "Started."})
    assert again["seq"] == first["seq"] and again["id"] == event_id and again["agent"]["status"] == "working"
    assert store.receipt_ref(*args).get().to_dict()["event_seq"] == first["seq"]
    session = store.agent_ref(*args, agent_id).get().to_dict()
    assert session["event_ids"] == [event_id] and "event_ids" not in first["agent"]
    turn_ref = store._turn_ref(*args)
    assert len(list(turn_ref.collection("agents").document(agent_id).collection("messages").stream())) == 1
    assert not list(turn_ref.collection("agent_events").stream())
    # The browser's view of the sessions carries neither the ids nor the assignment.
    [view] = store.delegation_view(*args)["agents"]
    assert "event_ids" not in view and "assignment" not in view
    # Only the newest ids stay with the session.
    for index in range(10):
        store.publish_agent(*args, run_token=loop.run_token, agent_id=agent_id, event_id=f"{index:032x}",
                            patch={"status": "working"})
    assert store.agent_ref(*args, agent_id).get().to_dict()["event_ids"] == [f"{index:032x}" for index in range(2, 10)]


def test_a_receipt_the_runs_end_cannot_write_still_closes_the_workspace(store, monkeypatch):
    """A step's receipt that cannot be written at the run's end (its chat
    deleted meanwhile, the account being deleted) does not break off the
    cleanup before VMSession.close(): else the message's VM seconds would
    never be charged."""
    from types import SimpleNamespace
    closed = []

    class Session:
        started = False

        def summary(self):
            return {"seconds": 0}

        def close(self):
            closed.append(True)
    loop = make_loop(store, mock_answer="Answer")
    loop.vm_tools = SimpleNamespace(session=Session(), take_pictures=lambda: [], interrupt=lambda: None)

    def refused(*args, **kwargs):
        raise ChatNotFound("Agent receipt not found")
    monkeypatch.setattr(store, "settle", refused)
    with pytest.raises(ChatNotFound):
        list(loop.run())
    assert closed == [True] and loop.completion.vm == {"seconds": 0}


def test_a_batch_that_breaks_off_waits_for_the_reads_it_started_beside(store):
    """A step's read-only calls run side by side (_prefetch). When the batch
    breaks off at its first call, the run waits for the later ones: else a
    page read still claiming or settling its paid step would meet finish_run
    ("Agent step has not settled"), and the turn would stay pending until the
    reaper."""
    from pydantic import BaseModel, ConfigDict
    from app.services.agent_tools import ReadOnlyTool, ToolRegistry

    class Args(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        n: int = 0
    beside, release, reads = threading.Event(), threading.Event(), []

    def read(args, *, cancellation):
        if args.n == 0:
            beside.wait(5)
            raise AgentRunInterrupted("The first read broke.")
        reads.append(threading.current_thread())
        beside.set()
        # Until the run's end looks (finish_run), at most a second.
        release.wait(1)
        return {"text": "read"}

    class Reads(AgentCompletion):
        def stream(self, *, model, messages, **kwargs):
            self.usage = measured_usage({"prompt_tokens": 10, "completion_tokens": 2, "cost": .0001}, model)
            self.tool_calls = [{"id": f"read_{n}", "type": "function",
                                "function": {"name": "read_file", "arguments": json.dumps({"n": n})}} for n in (0, 1)]
            self.finish_reason = "tool_calls"
            return
            yield
    loop = make_loop(store, Reads)
    loop.registry = ToolRegistry([*loop.registry.tools.values(), ReadOnlyTool("read_file", "Read.", Args, read)],
                                 argument_limit=loop.registry.argument_limit)
    finish, running = store.finish_run, []

    def looked(*args, **kwargs):
        running.append(reads[0].is_alive())
        release.set()
        return finish(*args, **kwargs)
    store.finish_run = looked
    with pytest.raises(RuntimeError):
        list(loop.run())
    assert running == [False]


def test_a_waiting_helper_writes_the_receipt_whose_own_thread_already_failed(store, monkeypatch):
    """The agent's step receipt is written in a thread of its own
    (_settle_later). When that write has already failed, a helper waiting for
    allowance (_admit_chat_step) must not leave the step to that thread and
    wait until the turn's time limit ("Waiting for active model calls"). A
    thread still writing keeps it; a failed one does not."""
    from types import SimpleNamespace
    from app.services.agent_quota import AgentTokenBudgetExceeded
    loop = make_loop(store)
    failed = threading.Thread(target=lambda: None)
    failed.start()
    failed.join()
    loop.unsettled["completion:0"] = ({}, "succeeded")
    loop.settling = (failed, {"error": RuntimeError("The receipt write failed.")}, "completion:0")
    settled, attempts = [], []

    def settle(step, value, status):
        settled.append(step)
        with loop.condition:
            loop.unsettled.pop(step, None)
    loop._settle_step = settle

    def reserve(*args, **kwargs):
        attempts.append(True)
        if "completion:0" not in loop.unsettled:
            return None
        if len(attempts) > 3:
            raise AssertionError("Still waiting for a receipt nobody writes.")
        # The unsettled step's reservation holds the allowance.
        raise AgentTokenBudgetExceeded(10 ** 9, 1, reserved=10 ** 6)
    monkeypatch.setattr(loop.costs, "reserve", reserve)
    monkeypatch.setattr(loop.store, "claim", lambda *args, **kwargs: True)
    monkeypatch.setattr(loop, "_state", lambda *args, **kwargs: None)
    helper = SimpleNamespace(id="a1", kind="worker")
    admission = loop._admit_chat_step(loop.model, loop.messages, "agent:a1:0", loop.registry, loop.cancellation, 0,
                                      {}, helper)
    try:
        while True:
            next(admission)
    except StopIteration as done:
        claimed = done.value[5]
    assert settled == ["completion:0"] and claimed is True
    # Written after all: the agent's next claim goes on.
    loop._join_settling()
    assert loop.settling is None


def reads_beside(store, read, *, calls=2, policy=None):
    """A loop whose first step calls ``read_file`` ``calls`` times (n = 0, 1,
    ...; the later ones start beside the first, _prefetch), the next answers."""
    from pydantic import BaseModel, ConfigDict
    from app.services.agent_tools import ReadOnlyTool, ToolRegistry

    class Args(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        n: int = 0
    sent = []

    class Reads(AgentCompletion):
        def stream(self, *, model, messages, **kwargs):
            self.usage = measured_usage({"prompt_tokens": 10, "completion_tokens": 2, "cost": .0001}, model)
            sent.append(messages)
            if len(sent) == 1:
                self.tool_calls = [{"id": f"read_{n}", "type": "function",
                                    "function": {"name": "read_file", "arguments": json.dumps({"n": n})}}
                                   for n in range(calls)]
                self.finish_reason = "tool_calls"
                return
            self.text, self.finish_reason = "Done.", "stop"
            yield {"type": "delta", "text": self.text}
    loop = make_loop(store, Reads)
    if policy:
        loop.policy = replace(loop.policy, **policy)
    loop.registry = ToolRegistry([*loop.registry.tools.values(), ReadOnlyTool("read_file", "Read.", Args, read)],
                                 argument_limit=loop.registry.argument_limit)
    return loop, sent


def test_a_read_started_beside_that_breaks_gets_not_run_once_the_batch_stopped(store):
    """A read the batch started beside its first (_prefetch) and then takes
    on its stopped path (a pause after a call of the step) does not raise its
    error out of the run: it gets "Not run", as if it had not run at all, and
    the run goes on."""
    from app.services.agent_delegation import CALL_AFTER_PAUSE
    first_read = threading.Event()

    def read(args, *, cancellation):
        if args.n:
            raise AgentRunInterrupted("The read beside broke.")
        first_read.set()
        return {"text": "read"}
    loop, sent = reads_beside(store, read)
    hold_wait, paused = loop._hold_wait, []

    def pause_after_the_first(poll=None):
        if first_read.is_set() and not paused:
            # The user let the work go on after a pause between the calls.
            paused.append(True)
            return "continue"
        return (yield from hold_wait(poll))
    loop._hold_wait = pause_after_the_first
    list(loop.run())
    assert paused and loop.completion.text == "Done."
    results = tool_results(sent[1])
    assert results["read_0"] == {"text": "read"} and results["read_1"] == {"error": CALL_AFTER_PAUSE}
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["status"] == "completed"


def test_a_read_started_beside_that_breaks_after_the_repeat_guard_ended_the_batch_is_not_run(store):
    """The same for a read the batch never reached (the repeat guard ended
    it at its first call): it gets the limit's "Not run" like the rest."""
    from app.services.agent_delegation import CALL_AT_LIMIT

    def read(args, *, cancellation):
        raise AgentRunInterrupted("The read beside broke.")
    loop, sent = reads_beside(store, read, policy={"account_budget_only": True, "turn_identical_calls": 1})
    first = {"id": "read_0", "function": {"name": "read_file", "arguments": json.dumps({"n": 0})}}
    # Read twice before: this third one ends the batch.
    loop.identical_calls[loop._identical_key(first)] = 2
    # A run without comparison tools ends at the guard (_wrap_up), with
    # every call's result kept, not with the read's error.
    with pytest.raises(AnalysisBudgetExceeded, match="repeated the same tool request"):
        list(loop.run())
    results = tool_results(loop.messages)
    assert results == {"read_0": {"error": CALL_AT_LIMIT}, "read_1": {"error": CALL_AT_LIMIT}}
