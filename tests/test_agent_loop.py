"""Provider protocol + durable orchestration. No real paid model calls."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json

from pydantic import BaseModel, ConfigDict, Field
import pytest

from app.services.agent_loop import AgentLoop
from app.services.agent_policy import AgentPolicy, tools_for_model
from app.services.agent_tools import ReadOnlyTool, ToolRegistry, configured_model
from app.services.chat_store import ChatNotFound, TurnStatusConflict
from app.services.llm import agent_client
from app.services.llm.agent_client import AgentCompletion, resolve_agent_model
from app.services.llm.provider_runtime import AnalysisBudgetExceeded, ProviderCancellation, ProviderCancelled, current_analysis_budget
from test_agent_runs import AUTH, UID, api, pending, receipt, store, totals


REAL_STREAM = AgentCompletion.stream


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    number: int = Field(ge=0, le=100)


def client_registry(executed):
    def execute(args, *, cancellation):
        executed.append(args.number)
        return {"result": args.number * 2}
    return ToolRegistry([ReadOnlyTool("double", "Double a small integer", Arguments, execute)])


def call(arguments='{"number":2}', name="double", identity="call_one"):
    return {"index": 0, "id": identity, "type": "function", "function": {"name": name, "arguments": arguments}}


def packet(delta=None, finish=None, usage=None):
    result = {"choices": [{"index": 0, "delta": delta or {}, **({"finish_reason": finish} if finish else {})}]}
    if usage is not None:
        result["usage"] = usage
    return result


def usage(searches=0):
    return {"prompt_tokens": 100, "completion_tokens": 20, "server_tool_use": {"web_search_requests": searches}}


def transport(monkeypatch, responses):
    requests, budgets, closed = [], [], []
    def lines(url, **kwargs):
        index = len(requests)
        requests.append(kwargs["json"])
        budget = current_analysis_budget()
        budgets.append(budget)
        budget.consume()  # same shared transport admission as real HTTP
        try:
            for value in responses[index]:
                if isinstance(value, BaseException):
                    raise value
                yield "data: " + json.dumps(value)
                yield ""
            yield "data: [DONE]"
            yield ""
        finally:
            closed.append(index)
    monkeypatch.setattr(agent_client, "cancellable_sse_lines", lines)
    return requests, budgets, closed


def loop_for(store, **kwargs):
    chat_id, turn = pending(store)
    model = configured_model(resolve_agent_model("claude-haiku-4-5"))
    return AgentLoop(store=store, uid=UID, chat_id=chat_id, turn_id=turn["id"], model=model,
                     messages=store.messages(UID, chat_id, turn, model=model), api_key="test",
                     cancellation=ProviderCancellation(), **kwargs)


def test_native_search_stays_in_selected_model_request_with_real_citations(store, monkeypatch):
    sources = [{"type": "url_citation", "url_citation": {"url": "https://example.com/report", "title": "Report"}},
               {"type": "url_citation", "url_citation": {"url": "javascript:alert(1)", "title": "Bad"}}]
    requests, _, closed = transport(monkeypatch, [[packet({"content": "Answer", "annotations": sources}), packet(finish="stop", usage=usage(2))]])
    loop = loop_for(store)
    events = list(loop.run())
    assert len(requests) == 1 and closed == [0]
    request = requests[0]
    assert request["model"] == "anthropic/claude-haiku-4.5"
    assert request["tools"] == [{"type": "openrouter:web_search", "parameters": {
        "engine": "auto", "max_uses": 2, "max_results": 5, "max_total_results": 10, "max_characters": 2000}}]
    assert request["max_tool_calls"] == 2
    assert request["provider"] == {"zdr": True}
    assert "tool_choice" not in request
    assert "plugins" not in request
    assert "parallel_tool_calls" not in request
    tool_events = [event for event in events if event and event.get("kind") == "tool"]
    assert len(tool_events) == 1 and tool_events[0]["status"] == "succeeded"
    assert tool_events[0]["count"] == 2
    assert tool_events[0]["sources"] == [{"url": "https://example.com/report", "title": "Report"}]
    assert "query" not in tool_events[0]  # native API doesn't expose it
    assert totals(store)["calls"] == 1
    assert totals(store)["estimated_cost_nano_usd"] == 20_200_000
    assert loop.completion.usage["complete"] is True
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["consensus"] == "Answer"
    assert saved["agent_activity"][-1]["status"] == "succeeded"
    assert len(store.active_ref(UID).get().to_dict()["leases"]) == 0


def test_explicit_tool_loop_validates_executes_and_settles_each_step_once(store, monkeypatch):
    requests, budgets, closed = transport(monkeypatch, [
        [packet({"tool_calls": [call(arguments='{"num')] }),
         packet({"tool_calls": [{"index": 0, "function": {"arguments": 'ber":2}'}}]}, finish="tool_calls", usage=usage())],
        [packet({"content": "Result: 4"}), packet(finish="stop", usage=usage(1))],
    ])
    executed = []
    loop = loop_for(store, registry=client_registry(executed))
    events = list(loop.run())
    assert executed == [2] and len(requests) == 2 and closed == [0, 1]
    assert budgets[0] is budgets[1] and budgets[0].calls == 2
    assert requests[1]["messages"][-1] == {"role": "tool", "tool_call_id": "call_one", "content": '{"result": 4}'}
    assert requests[1]["tools"][-1]["parameters"]["max_uses"] == 1
    assert totals(store)["calls"] == totals(store)["measured_calls"] == 2
    assert loop.completion.usage["input_tokens"] == 200
    assert loop.completion.usage["estimated_cost_nano_usd"] == totals(store)["estimated_cost_nano_usd"]
    assert not store.claim(UID, loop.chat_id, loop.turn_id, loop.model, step="completion:1", run_token=loop.run_token)
    assert not store.settle(UID, loop.chat_id, loop.turn_id, step="completion:1", completion=receipt(), status="succeeded", final=False)
    assert not store.finish_run(UID, loop.chat_id, loop.turn_id, completion=loop.completion, status="succeeded", run_token=loop.run_token)
    assert any(e and e.get("clear_response") for e in events)
    assert {e["step_id"] for e in loop.completion.activity} >= {"completion:0", "tool:0", "completion:1", "run"}


@pytest.mark.parametrize("arguments,name", [('{}', 'double'), ('{"number":true}', 'double'), ('{"number":101}', 'double'),
    ('{"number":2,"command":"write"}', 'double'), ('{"number":1,"number":2}', 'double'), ('{"number":2}', 'write_file'), ('[1]', 'double'), ('{', 'double')])
def test_invalid_or_unapproved_tool_never_executes_or_spawns_another_paid_call(store, monkeypatch, arguments, name):
    requests, _, _ = transport(monkeypatch, [[packet({"tool_calls": [call(arguments, name)]}, finish="tool_calls", usage=usage())]])
    executed = []
    loop = loop_for(store, registry=client_registry(executed))
    with pytest.raises(ValueError):
        list(loop.run())
    assert not executed and len(requests) == totals(store)["calls"] == 1
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["status"] == "failed"
    assert not store.active_ref(UID).get().to_dict()["leases"]


@pytest.mark.parametrize("fragment", [[call(), {**call(), "index": 1}], [{**call(), "index": -1}],
    [call(arguments="x" * 2049)], [call(identity="bad id")]])
def test_malformed_streamed_tool_calls_close_transport(store, monkeypatch, fragment):
    _, _, closed = transport(monkeypatch, [[packet({"tool_calls": fragment}, finish="tool_calls", usage=usage())]])
    loop = loop_for(store, registry=client_registry([]))
    with pytest.raises(ValueError):
        list(loop.run())
    assert closed == [0] and totals(store)["calls"] == 1


def test_repeated_tool_identity_stops_without_reexecution(store, monkeypatch):
    response = [packet({"tool_calls": [call()]}, finish="tool_calls", usage=usage())]
    requests, _, _ = transport(monkeypatch, [response, response])
    executed = []
    loop = loop_for(store, registry=client_registry(executed))
    with pytest.raises(TurnStatusConflict):
        list(loop.run())
    assert executed == [2] and len(requests) == 2


@pytest.mark.parametrize("budget", [replace(AgentPolicy(), max_tools=0), replace(AgentPolicy(), max_calls=1),
    replace(AgentPolicy(), max_tokens=10), replace(AgentPolicy(), max_cost_nano_usd=1), replace(AgentPolicy(), seconds=0)])
def test_limits_prevent_unapproved_work(store, monkeypatch, budget):
    requests, _, _ = transport(monkeypatch, [[packet({"tool_calls": [call()]}, finish="tool_calls", usage=usage())]])
    executed = []
    loop = loop_for(store, registry=client_registry(executed), policy=budget)
    with pytest.raises((AnalysisBudgetExceeded, RuntimeError)):
        list(loop.run())
    assert not executed and len(requests) <= 1
    assert not (store.active_ref(UID).get().to_dict() or {}).get("leases")


@pytest.mark.parametrize("failure", [ProviderCancelled(), RuntimeError("provider failure")])
def test_cancel_or_failure_in_second_step_keeps_first_usage_and_never_retries(store, monkeypatch, failure):
    requests, _, closed = transport(monkeypatch, [
        [packet({"tool_calls": [call()]}, finish="tool_calls", usage=usage())], [failure]])
    loop = loop_for(store, registry=client_registry([]))
    with pytest.raises(type(failure)):
        list(loop.run())
    assert len(requests) == 2 and closed == [0, 1]
    assert totals(store)["measured_calls"] == 1 and totals(store)["unmetered_calls"] == 1
    assert totals(store)["unsettled_calls"] == 0
    assert loop.completion.usage["complete"] is False
    assert not store.active_ref(UID).get().to_dict()["leases"]


def test_cancel_between_tool_and_model_prevents_next_claim(store, monkeypatch):
    requests, _, _ = transport(monkeypatch, [[packet({"tool_calls": [call()]}, finish="tool_calls", usage=usage())]])
    loop = loop_for(store, registry=client_registry([]))
    source = loop.run()
    for event in source:
        if event and event.get("kind") == "tool" and event.get("status") == "succeeded":
            loop.cancellation.cancel()
            break
    with pytest.raises(ProviderCancelled):
        list(source)
    assert len(requests) == totals(store)["calls"] == 1


def test_close_during_provider_stream_settles_cancelled_and_closes_socket(store, monkeypatch):
    _, _, closed = transport(monkeypatch, [[packet({"content": "partial"}), packet(finish="stop", usage=usage())]])
    loop = loop_for(store)
    source = loop.run()
    for event in source:
        if event and event["type"] == "delta":
            source.close()
            break
    assert closed == [0]
    assert totals(store)["unmetered_calls"] == 1
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["error_code"] == "cancelled"


def test_missing_native_usage_is_partial_and_keeps_reservation(store, monkeypatch):
    raw = usage()
    raw.pop("server_tool_use")
    transport(monkeypatch, [[packet({"content": "Answer"}, finish="stop", usage=raw)]])
    loop = loop_for(store)
    events = list(loop.run())
    assert loop.completion.usage["complete"] is False
    assert loop.costs.tokens == 600_000
    assert totals(store)["incomplete_calls"] == 1
    assert any(e and e.get("kind") == "tool" and e["status"] == "unknown" for e in events)


@pytest.mark.parametrize("selection_id", [m.selection_id for m, _ in agent_client.agent_models()])
def test_every_offered_model_can_use_the_consensus_search_route(store, monkeypatch, selection_id):
    from app.services.agent_tools import search_family
    from app.services.llm.engines import build_provider_payload
    requests, _, _ = transport(monkeypatch, [[packet({"content": "Answer"}, finish="stop", usage=usage())]])
    loop = loop_for(store)
    loop.model = resolve_agent_model(selection_id)
    list(loop.run())
    assert tools_for_model(loop.model) == ("web_search",)
    family = search_family(loop.model)
    reference = build_provider_payload(family)["payload"]
    assert requests[0]["tools"][0]["parameters"]["engine"] == reference["tools"][0]["parameters"]["engine"]
    assert requests[0]["max_tool_calls"] == 2
    assert loop.completion.usage["complete"] is True


def test_crash_receipts_and_continuation_claim_races_remain_fenced(store):
    loop = loop_for(store)
    args = (UID, loop.chat_id, loop.turn_id, loop.model)
    assert store.claim(*args, run_token=loop.run_token, policy=loop.policy.snapshot())
    with pytest.raises(TurnStatusConflict):
        store.claim(*args, step="completion:1", run_token=loop.run_token)
    store.settle(*args[:3], completion=receipt(), status="succeeded", final=False)
    assert len(store.active_ref(UID).get().to_dict()["leases"]) == 1
    with pytest.raises(TurnStatusConflict):
        store.claim(*args, step="completion:1", run_token="another-process")
    with ThreadPoolExecutor(max_workers=4) as pool:
        result = list(pool.map(lambda _: store.claim(*args, step="completion:1", run_token=loop.run_token), range(4)))
    assert sum(result) == 1 and totals(store)["calls"] == 2
    assert not store.claim(*args)  # process recovery never repeats root


def test_deletion_between_steps_preserves_accounting_and_fences_next_call(store, monkeypatch):
    requests, _, _ = transport(monkeypatch, [[packet({"tool_calls": [call()]}, finish="tool_calls", usage=usage())]])
    loop = loop_for(store, registry=client_registry([]))
    source = loop.run()
    for event in source:
        if event and event.get("kind") == "tool" and event.get("status") == "succeeded":
            store.delete_chat(UID, loop.chat_id)
            break
    with pytest.raises(ChatNotFound):
        list(source)
    assert len(requests) == totals(store)["calls"] == 1
    assert not store._chat_ref(UID, loop.chat_id).get().exists
    assert not store.active_ref(UID).get().to_dict()["leases"]


def test_native_endpoint_replay_uses_receipt_and_does_not_search_again(api, monkeypatch):
    client, store, _ = api
    monkeypatch.setattr(AgentCompletion, "stream", REAL_STREAM)
    requests, _, _ = transport(monkeypatch, [[packet({"content": "Found answer"}, finish="stop", usage=usage(1))]])
    chat = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]
    payload = {"chat_id": chat["id"], "question": "Research", "client_request_id": "native", "bookmark_id": "native",
               "model_id": "claude-haiku-4-5"}
    assert "event: final" in client.post("/agent", json=payload, headers=AUTH).text
    replay = client.post("/agent", json={**payload, "recover_only": True}, headers=AUTH)
    assert replay.status_code == 200 and replay.json()["response"] == "Found answer"
    assert len(requests) == 1
    assert replay.json()["turn"]["agent_settings"]["tools"] == ["web_search"]
    assert client.post("/agent", json={**payload, "tools": ["shell"]}, headers=AUTH).status_code == 422


def test_known_search_charge_survives_missing_tokens_without_inventing_zero_tokens(store, monkeypatch):
    transport(monkeypatch, [[packet({"content": "Answer"}, finish="stop", usage={"server_tool_use": {"web_search_requests": 1}})]])
    loop = loop_for(store)
    list(loop.run())
    assert loop.completion.usage["input_tokens"] is None
    assert loop.completion.usage["output_tokens"] is None
    assert loop.completion.usage["estimated_cost_nano_usd"] == 10_000_000
    assert loop.completion.usage["complete"] is False
    assert "input_tokens" not in totals(store)
    assert totals(store)["unmetered_calls"] == 1
    assert totals(store)["estimated_cost_nano_usd"] == 10_000_000


def test_reported_native_limit_violation_is_accounted_and_stops(store, monkeypatch):
    transport(monkeypatch, [[packet({"content": "Answer"}, finish="stop", usage=usage(3))]])
    loop = loop_for(store)
    with pytest.raises(RuntimeError, match="native search limit"):
        list(loop.run())
    assert totals(store)["estimated_cost_nano_usd"] == 30_200_000
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["status"] == "failed"


def test_usage_beyond_total_budget_stops_after_accounting(store, monkeypatch):
    raw = {**usage(1), "prompt_tokens": 4_100_000}
    transport(monkeypatch, [[packet({"content": "Answer"}, finish="stop", usage=raw)]])
    loop = loop_for(store)
    with pytest.raises(AnalysisBudgetExceeded, match="beyond"):
        list(loop.run())
    assert totals(store)["input_tokens"] == 4_100_000
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["status"] == "failed"


def test_two_client_tools_then_final_answer_use_three_steps_and_one_owner_slot(store, monkeypatch):
    requests, _, _ = transport(monkeypatch, [
        [packet({"tool_calls": [call()]}, finish="tool_calls", usage=usage())],
        [packet({"tool_calls": [call(identity="call_two")]}, finish="tool_calls", usage=usage())],
        [packet({"content": "Done"}, finish="stop", usage=usage())]])
    executed = []
    loop = loop_for(store, registry=client_registry(executed))
    for event in loop.run():
        if event and event.get("kind") == "tool" and event["status"] == "running":
            assert len(store.active_ref(UID).get().to_dict()["leases"]) == 1
    assert len(requests) == 3 and executed == [2, 2]
    assert requests[2]["tool_choice"] == "none"
    assert all(tool["type"] == "function" for tool in requests[2]["tools"])
    assert totals(store)["calls"] == totals(store)["measured_calls"] == 3


def test_oversized_tool_result_never_reaches_next_model(store, monkeypatch):
    requests, _, _ = transport(monkeypatch, [[packet({"tool_calls": [call()]}, finish="tool_calls", usage=usage())]])
    registry = ToolRegistry([ReadOnlyTool("double", "Test", Arguments, lambda args, **kwargs: "x" * 8001)])
    loop = loop_for(store, registry=registry)
    with pytest.raises(ValueError, match="result exceeds"):
        list(loop.run())
    assert len(requests) == 1
    assert all(len(event.get("text", "")) < 8000 for event in loop.completion.activity)


def test_close_on_tool_started_persists_stopped_instead_of_working(store, monkeypatch):
    transport(monkeypatch, [[packet({"tool_calls": [call()]}, finish="tool_calls", usage=usage())]])
    executed = []
    loop = loop_for(store, registry=client_registry(executed))
    source = loop.run()
    for event in source:
        if event and event.get("kind") == "tool" and event.get("status") == "running":
            source.close()
            break
    assert not executed
    tool = next(e for e in loop.completion.activity if e["kind"] == "tool")
    assert tool["status"] == "cancelled"


def test_normalized_input_output_usage_aliases():
    model = resolve_agent_model()
    value = agent_client.measured_usage({"input_tokens": 100, "output_tokens": 20}, model)
    assert value["input_tokens"] == 100 and value["output_tokens"] == 20


def test_search_and_token_usage_in_separate_chunks_are_merged_once(store, monkeypatch):
    transport(monkeypatch, [[packet({"content": "Answer"}, finish="stop",
        usage={"server_tool_use": {"web_search_requests": 1}}),
        packet(usage={"prompt_tokens": 100, "completion_tokens": 20})]])
    loop = loop_for(store)
    list(loop.run())
    assert loop.completion.usage["complete"] is True
    assert totals(store)["estimated_cost_nano_usd"] == 10_200_000
