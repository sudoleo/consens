"""Provider protocol + durable orchestration. No real paid model calls."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import re

from pydantic import BaseModel, ConfigDict, Field
import pytest

from app.core.openrouter_contract import provider_session_id
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


def reviewed_transport(monkeypatch, answer, *, searches=0):
    """The provider for POST /agent in the one mode (2026-10-31): the
    agent's request (it offers compare_models) streams ``answer``, each
    reviewer's request a review without marks. Returns both lists of
    requests, the agent's and the reviewers'."""
    agent, reviews = [], []

    def lines(url, **kwargs):
        body = kwargs["json"]
        own = any(tool.get("function", {}).get("name") == "compare_models" for tool in body.get("tools") or [])
        (agent if own else reviews).append(body)
        current_analysis_budget().consume()
        chunks = [answer[i:i + 100] for i in range(0, len(answer), 100)] if own else [json.dumps({"marks": []})]
        for chunk in chunks:
            yield "data: " + json.dumps(packet({"content": chunk}))
            yield ""
        yield "data: " + json.dumps(packet(finish="stop", usage=usage(searches if own else 0)))
        yield ""
        yield "data: [DONE]"
        yield ""
    monkeypatch.setattr(agent_client, "cancellable_sse_lines", lines)
    return agent, reviews


def loop_for(store, **kwargs):
    chat_id, turn = pending(store)
    model = configured_model(resolve_agent_model("claude-haiku-4-5"))
    return AgentLoop(store=store, uid=UID, chat_id=chat_id, turn_id=turn["id"], model=model,
                     messages=store.messages(UID, chat_id, turn, model=model), api_key="test",
                     cancellation=ProviderCancellation(), **kwargs)


def test_a_service_tier_of_the_model_config_reaches_the_request(store, monkeypatch):
    # The way judges ask for OpenAI's priority lane (ComparisonTools.judge_transport).
    requests, _, _ = transport(monkeypatch, [[packet({"content": "Answer"}), packet(finish="stop", usage=usage())]])
    chat_id, turn = pending(store)
    model = configured_model(resolve_agent_model("claude-haiku-4-5"))
    model = replace(model, request_config={**model.request_config, "service_tier": "priority"})
    loop = AgentLoop(store=store, uid=UID, chat_id=chat_id, turn_id=turn["id"], model=model,
                     messages=store.messages(UID, chat_id, turn, model=model), api_key="test",
                     cancellation=ProviderCancellation())
    list(loop.run())
    assert requests[0]["service_tier"] == "priority"
    assert requests[0]["provider"] == {"sort": "throughput", "data_collection": "deny"}


def recording_transport(monkeypatch, responses):
    """transport() that also keeps each request's headers."""
    requests, _, _ = transport(monkeypatch, responses)
    lines, headers = agent_client.cancellable_sse_lines, []
    def recording(url, **kwargs):
        headers.append(kwargs["headers"])
        return lines(url, **kwargs)
    monkeypatch.setattr(agent_client, "cancellable_sse_lines", recording)
    return requests, headers


def test_every_step_of_a_chat_stays_on_the_endpoint_holding_its_cached_prefix(store, monkeypatch):
    # One opaque session per chat (openrouter_contract.provider_session_id):
    # OpenRouter keeps the steps on one endpoint from the first request on.
    requests, headers = recording_transport(monkeypatch, [
        [packet({"tool_calls": [call()]}, finish="tool_calls", usage=usage())],
        [packet({"content": "Result: 4"}), packet(finish="stop", usage=usage())],
    ])
    chat_id, turn = pending(store)
    model = configured_model(resolve_agent_model("claude-haiku-4-5"))
    # The adapter owns the session: a registry value never reaches the request.
    model = replace(model, request_config={**model.request_config, "session_id": "from-registry"})
    loop = AgentLoop(store=store, uid=UID, chat_id=chat_id, turn_id=turn["id"], model=model,
                     messages=store.messages(UID, chat_id, turn, model=model), api_key="test",
                     cancellation=ProviderCancellation(), registry=client_registry([]))
    list(loop.run())
    assert len(requests) == len(headers) == 2
    session = headers[0]["x-session-id"]
    assert headers[1]["x-session-id"] == session == provider_session_id(UID, chat_id)
    assert re.fullmatch(r"[0-9a-f]{32}", session) and UID not in session and chat_id not in session
    assert session not in {provider_session_id(UID, "other-chat"), provider_session_id("other-user", chat_id)}
    assert all("session_id" not in request for request in requests)
    assert headers[0]["Authorization"] == "Bearer test"
    assert requests[0]["provider"] == {"sort": "throughput", "data_collection": "deny"}


def test_a_request_without_a_session_keeps_the_plain_routing(monkeypatch):
    # Helper steps (comparison answers, judges, page reads) keep the plain
    # fastest-endpoint routing.
    requests, headers = recording_transport(monkeypatch, [
        [packet({"content": "Hi"}, finish="stop", usage=usage())]])
    from app.services.llm.provider_runtime import AnalysisBudget, bind_analysis_budget
    with bind_analysis_budget(AnalysisBudget(seconds=30, max_calls=1)):
        list(AgentCompletion().stream(model=resolve_agent_model("claude-haiku-4-5"),
                                      messages=[{"role": "user", "content": "Hi"}], api_key="test"))
    assert "x-session-id" not in headers[0] and "session_id" not in requests[0]


# --- Cache points (agent_client.with_cache_points) ----------------------------

EPHEMERAL = {"type": "ephemeral"}


def follow_up_loop(store, model="claude-haiku-4-5", **kwargs):
    """An AgentLoop for a chat's second message: system prompt, one earlier
    question and answer, then the new question."""
    chat_id, first = pending(store)
    assert store.claim(UID, chat_id, first["id"], resolve_agent_model(model))
    store.settle(UID, chat_id, first["id"], completion=receipt(), status="succeeded")
    _, second = pending(store, chat_id=chat_id, request_id="two", question="What next?")
    model = configured_model(resolve_agent_model(model))
    messages = store.messages(UID, chat_id, second, model=model)
    return AgentLoop(store=store, uid=UID, chat_id=chat_id, turn_id=second["id"], model=model, messages=messages,
                     api_key="test", cancellation=ProviderCancellation(), **kwargs), messages


def marked(content):
    return [{"type": "text", "text": content, "cache_control": EPHEMERAL}]


def test_the_next_message_finds_the_system_prompt_and_history_cached(store, monkeypatch):
    # 2026-10-22: with only the top-level marker on the last block, no first
    # step of a message read the cache (Sonnet, 20 of 20), because the next
    # message never reaches a point an earlier one had written.
    requests, _, _ = transport(monkeypatch, [
        [packet({"tool_calls": [call()]}, finish="tool_calls", usage=usage())],
        [packet({"content": "Result: 4"}), packet(finish="stop", usage=usage())],
    ])
    loop, messages = follow_up_loop(store, registry=client_registry([]))
    assert [message["role"] for message in messages] == ["system", "user", "assistant", "user"]
    list(loop.run())
    assert len(requests) == 2
    for request in requests:
        sent = request["messages"]
        # The system prompt and the chat's last earlier message carry points of
        # their own, with the same bytes; the top-level marker keeps the tail.
        assert sent[0] == {"role": "system", "content": marked(messages[0]["content"])}
        assert sent[2] == {"role": "assistant", "content": marked("A helpful answer")}
        assert sent[1] == messages[1] and sent[3] == messages[3]
        assert request["cache_control"] == EPHEMERAL
        # At most four breakpoints per request: two here plus the top-level one.
        assert json.dumps(sent).count('"cache_control"') == 2
    # The second step continues the first: same marked prefix, then its tool turn.
    assert requests[1]["messages"][:4] == requests[0]["messages"]
    # Nothing leaks into the loop's own conversation.
    assert loop.messages[0]["content"] == messages[0]["content"]


def test_a_chats_first_message_marks_only_its_system_prompt(store, monkeypatch):
    requests, _, _ = transport(monkeypatch, [[packet({"content": "Answer"}), packet(finish="stop", usage=usage())]])
    loop = loop_for(store)
    list(loop.run())
    sent = requests[0]["messages"]
    assert [message["role"] for message in sent] == ["system", "user"]
    assert sent[0]["content"][0]["cache_control"] == EPHEMERAL
    assert isinstance(sent[1]["content"], str)


def test_providers_that_cache_on_their_own_get_the_plain_conversation(store, monkeypatch):
    requests, _, _ = transport(monkeypatch, [[packet({"content": "Answer"}), packet(finish="stop", usage=usage())]])
    loop, messages = follow_up_loop(store, model="gpt-5.6-luna")
    list(loop.run())
    assert requests[0]["messages"] == messages and "cache_control" not in requests[0]


@pytest.mark.parametrize("history_end", [None, 0, 3, 4, -1, "2"])
def test_cache_points_never_mark_the_last_block_or_a_foreign_index(history_end):
    from app.services.llm.agent_client import with_cache_points
    messages = [{"role": "system", "content": "System"}, {"role": "user", "content": "One"},
                {"role": "assistant", "content": "Answer"}, {"role": "user", "content": "Two"}]
    sent = with_cache_points(messages, EPHEMERAL, history_end)
    # Only the system prompt: the last message has the top-level marker,
    # anything else is not the end of the chat's history.
    assert sent[0]["content"] == marked("System") and sent[1:] == messages[1:]
    assert messages[0]["content"] == "System"


def test_cache_points_skip_what_cannot_carry_one():
    from app.services.llm.agent_client import with_cache_points
    blocks = [{"type": "text", "text": "Answer"}]
    assert with_cache_points([{"role": "user", "content": "Only"}], EPHEMERAL) is None
    assert with_cache_points([{"role": "system", "content": ""}, {"role": "user", "content": "Q"}], EPHEMERAL) is None
    messages = [{"role": "user", "content": "One"}, {"role": "assistant", "content": blocks},
                {"role": "user", "content": "Two"}]
    assert with_cache_points(messages, EPHEMERAL, history_end=1) is None
    assert with_cache_points(messages[:1] + [{"role": "assistant", "content": "Answer"}] + messages[2:],
                             EPHEMERAL, history_end=1)[1]["content"] == marked("Answer")


def test_a_refused_cache_point_never_costs_the_answer(store, monkeypatch):
    """The points are not probed live: should a provider refuse them (HTTP 400
    before any line, never billed), the same request goes once more without
    them, and the process stops sending them."""
    from app.services.llm.engines import _ProviderHTTPStatusError
    monkeypatch.setattr(agent_client, "_CACHE_POINTS_REFUSED", False)
    requests, _, closed = transport(monkeypatch, [
        [_ProviderHTTPStatusError(400)],
        [packet({"content": "Answer"}), packet(finish="stop", usage=usage())],
        [packet({"content": "Later"}), packet(finish="stop", usage=usage())],
    ])
    loop, messages = follow_up_loop(store)
    list(loop.run())
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["status"] == "completed"
    assert isinstance(requests[0]["messages"][0]["content"], list)
    assert requests[1]["messages"] == messages and requests[1]["cache_control"] == EPHEMERAL
    assert closed == [0, 1] and agent_client._CACHE_POINTS_REFUSED
    from app.services.llm.provider_runtime import AnalysisBudget, bind_analysis_budget
    with bind_analysis_budget(AnalysisBudget(seconds=30, max_calls=1)):
        list(AgentCompletion().stream(model=resolve_agent_model("claude-haiku-4-5"), messages=messages, api_key="test"))
    assert requests[2]["messages"] == messages


@pytest.mark.parametrize("second", [400, 429])
def test_a_request_that_fails_without_the_points_too_keeps_them(monkeypatch, second):
    # Another cause (a 400 for the request itself, a 429 on the second try):
    # the error stands and the points stay on for the next request.
    from app.services.llm.engines import _ProviderHTTPStatusError
    from app.services.llm.provider_runtime import AnalysisBudget, bind_analysis_budget
    monkeypatch.setattr(agent_client, "_CACHE_POINTS_REFUSED", False)
    requests, _, _ = transport(monkeypatch, [[_ProviderHTTPStatusError(400)], [_ProviderHTTPStatusError(second)]])
    messages = [{"role": "system", "content": "System"}, {"role": "user", "content": "Hi"}]
    with bind_analysis_budget(AnalysisBudget(seconds=30, max_calls=2)), pytest.raises(_ProviderHTTPStatusError) as raised:
        list(AgentCompletion().stream(model=resolve_agent_model("claude-haiku-4-5"), messages=messages, api_key="test"))
    assert raised.value.status_code == second and len(requests) == 2
    assert not agent_client._CACHE_POINTS_REFUSED


def test_other_provider_errors_never_resend_the_request(monkeypatch):
    from app.services.llm.engines import _ProviderHTTPStatusError
    from app.services.llm.provider_runtime import AnalysisBudget, bind_analysis_budget
    monkeypatch.setattr(agent_client, "_CACHE_POINTS_REFUSED", False)
    requests, _, _ = transport(monkeypatch, [[_ProviderHTTPStatusError(429)]])
    messages = [{"role": "system", "content": "System"}, {"role": "user", "content": "Hi"}]
    with bind_analysis_budget(AnalysisBudget(seconds=30, max_calls=2)), pytest.raises(_ProviderHTTPStatusError):
        list(AgentCompletion().stream(model=resolve_agent_model("claude-haiku-4-5"), messages=messages, api_key="test"))
    assert len(requests) == 1


@pytest.mark.real_prices
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
    assert request["provider"] == {"sort": "throughput", "data_collection": "deny"}
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


@pytest.mark.parametrize("fragment,error", [([{**call(), "index": -1}], RuntimeError),
                                            ([call(arguments="x" * 2049)], ValueError)])
def test_malformed_streamed_tool_calls_close_transport(store, monkeypatch, fragment, error):
    # Since 2026-10-27 a fragment no call of ours stands behind is skipped and
    # an oversized call reaches the registry, which refuses it with its limit;
    # neither executes, and the transport closes as before.
    _, _, closed = transport(monkeypatch, [[packet({"tool_calls": fragment}, finish="tool_calls", usage=usage())]])
    executed = []
    loop = loop_for(store, registry=client_registry(executed))
    with pytest.raises(error):
        list(loop.run())
    assert closed == [0] and totals(store)["calls"] == 1 and executed == []


def tool_fragments(*chunks, limit=4, argument_limit=2048):
    """The calls an AgentCompletion collects from streamed fragments."""
    value = AgentCompletion()
    value.tool_call_limit, value.tool_argument_limit = limit, argument_limit
    for chunk in chunks:
        value._tool_delta(chunk)
    return value


def test_a_call_after_the_providers_own_searches_keeps_its_stream_index():
    """2026-10-27: after five web searches inside its step DeepSeek's next
    call arrived as index 5, and the whole turn failed as a provider error."""
    value = tool_fragments([{"index": 5, "id": "call_a", "type": "function", "function": {"name": "double", "arguments": ""}}],
                           [{"index": 5, "function": {"arguments": '{"number":'}}], [{"function": {"arguments": "2}"}}])
    assert value._completed_tool_calls() == [{"id": "call_a", "type": "function",
                                              "function": {"name": "double", "arguments": '{"number":2}'}}]
    assert value.skipped_tool_parts == 0


def test_tool_fragments_that_name_no_call_of_ours_are_skipped_not_fatal():
    calls = [{"index": i, "id": f"c{i}", "type": "function", "function": {"name": "double", "arguments": "{}"}} for i in range(6)]
    value = tool_fragments(calls[:3], calls[3:],
                           [{"index": 9, "type": "web_search", "function": {"name": "search"}}, "noise", {"index": "7"}],
                           None)
    # At most the step's limit of calls, in stream order; the rest are counted.
    assert [c["id"] for c in value._completed_tool_calls()] == ["c0", "c1", "c2", "c3"]
    assert value.skipped_tool_parts == 2 + 4


def test_an_odd_id_or_an_oversized_call_still_completes_the_stream():
    value = tool_fragments([{"index": 0, "id": "functions.double:0", "type": "function",
                             "function": {"name": "double", "arguments": {"number": 2}}}],
                           [{"index": 1, "id": "", "function": {"name": "double", "arguments": "x" * 100}}],
                           argument_limit=50)
    first, second = value._completed_tool_calls()
    # Ids a provider takes back; arguments sent as an object are JSON text.
    assert first["id"] == "functions_double_0" and first["function"]["arguments"] == '{"number": 2}'
    assert second["id"].startswith("call_1_") and len(second["function"]["arguments"]) == 51
    # The registry refuses the oversized call with its limit: the model reads why.
    with pytest.raises(ValueError, match="at most 2048 characters"):
        client_registry([]).validate({"function": {"name": "double", "arguments": "x" * 2049}})


def test_calls_ended_with_stop_are_calls_and_a_writing_step_ignores_a_call(store, monkeypatch):
    transport(monkeypatch, [[packet({"tool_calls": [call()]}, finish="stop", usage=usage())],
                            [packet({"content": "Four."}), packet({"tool_calls": [call()]}, finish="tool_calls", usage=usage())]])
    value = AgentCompletion()
    value.tool_call_limit = 4
    list(value.stream(model=configured_model(resolve_agent_model("claude-haiku-4-5")),
                      messages=[{"role": "user", "content": "Hi"}], api_key="test",
                      tools=client_registry([]).schemas, allow_tool_calls=True))
    assert value.finish_reason == "tool_calls" and [c["id"] for c in value.tool_calls] == ["call_one"]
    answer = AgentCompletion()
    list(answer.stream(model=configured_model(resolve_agent_model("claude-haiku-4-5")),
                       messages=[{"role": "user", "content": "Hi"}], api_key="test",
                       tools=client_registry([]).schemas, allow_tool_calls=False))
    assert answer.finish_reason == "stop" and answer.text == "Four." and answer.tool_calls == []


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
    assert not any(e.get("kind") == "tool" for e in loop.completion.activity)


def test_missing_search_cost_keeps_only_cost_reservation(store, monkeypatch):
    raw = usage()
    raw.pop("server_tool_use")
    transport(monkeypatch, [[packet({"content": "Answer"}, finish="stop", usage=raw)]])
    loop = loop_for(store)
    events = list(loop.run())
    assert loop.completion.usage["complete"] is True
    assert loop.completion.usage["cost_complete"] is False
    assert loop.costs.tokens == 120
    assert totals(store).get("incomplete_calls", 0) == 0
    assert loop.remaining_tools == 0
    assert not any(e and e.get("kind") == "tool" for e in events)
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert not any(e.get("kind") == "tool" for e in saved["agent_activity"])


@pytest.mark.parametrize("selection_id", [m.selection_id for m, _ in agent_client.agent_models()])
@pytest.mark.parametrize("search_count", [None, 0])
def test_greetings_offer_optional_search_without_inventing_tool_activity(store, monkeypatch, selection_id, search_count):
    raw = {"prompt_tokens": 800, "completion_tokens": 62, "cost": 0.0004}
    if search_count is not None:
        raw["server_tool_use"] = {"web_search_requests": search_count}
    requests, _, _ = transport(monkeypatch, [[packet({"content": "Hey!", "reasoning": "A greeting. No tool needed."}, finish="stop", usage=raw)]])
    # This legacy-loop protocol test needs room for premium native-search
    # windows. Rejection limits are covered separately; chat uses its token ledger.
    loop = loop_for(store, policy=replace(AgentPolicy(), max_cost_nano_usd=50_000_000_000))
    loop.model = resolve_agent_model(selection_id)
    loop.messages[-1]["content"] = "was geht ab"
    events = list(loop.run())
    assert len(requests) == 1
    assert "tool_choice" not in requests[0] and "plugins" not in requests[0]
    assert requests[0]["tools"][0]["type"] == "openrouter:web_search"
    assert not any(e and e.get("kind") == "tool" for e in events)
    assert loop.completion.usage["complete"] is True
    assert loop.completion.usage["estimated_cost_nano_usd"] == 400_000
    assert totals(store)["calls"] == 1


@pytest.mark.parametrize("sources", [[], [{"type": "url_citation", "url_citation": {"url": "https://example.org/report", "title": "Report"}}]])
def test_interrupted_search_only_records_activity_if_use_is_confirmed(store, monkeypatch, sources):
    transport(monkeypatch, [[packet({"content": "Partial", "annotations": sources}), RuntimeError("Stream interrupted")]])
    loop = loop_for(store)
    with pytest.raises(RuntimeError, match="Stream interrupted"):
        list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    tools = [e for e in saved["agent_activity"] if e.get("kind") == "tool"]
    assert len(tools) == (1 if sources else 0)
    if sources:
        assert tools[0]["status"] == "unknown" and tools[0]["sources"][0]["url"] == "https://example.org/report"


@pytest.mark.parametrize("selection_id", [m.selection_id for m, _ in agent_client.agent_models()])
def test_every_offered_model_can_use_the_consensus_search_route(store, monkeypatch, selection_id):
    from app.services.agent_tools import search_family
    from app.services.llm.engines import build_provider_payload
    requests, _, _ = transport(monkeypatch, [[packet({"content": "Answer"}, finish="stop", usage=usage())]])
    loop = loop_for(store, policy=replace(AgentPolicy(), max_cost_nano_usd=50_000_000_000))
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
    requests, reviews = reviewed_transport(monkeypatch, "Found answer", searches=1)
    chat = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]
    payload = {"chat_id": chat["id"], "question": "Research, without a model comparison", "client_request_id": "native", "bookmark_id": "native",
               "model_id": "claude-haiku-4-5"}
    assert "event: final" in client.post("/agent", json=payload, headers=AUTH).text
    assert len(requests) == 1 and any(tool.get("type") == "openrouter:web_search" for tool in requests[0]["tools"])
    sent = len(requests) + len(reviews)
    replay = client.post("/agent", json={**payload, "recover_only": True}, headers=AUTH)
    assert replay.status_code == 200 and replay.json()["response"] == "Found answer"
    # The saved answer, from its receipt: no request, no search.
    assert len(requests) + len(reviews) == sent
    assert replay.json()["turn"]["agent_settings"]["tools"] == ["web_search"]
    assert client.post("/agent", json={**payload, "tools": ["shell"]}, headers=AUTH).status_code == 422


def search_usage(searches, field):
    """Both shapes OpenRouter has used to report native searches."""
    if field == "server_tool_use_details":
        # Live 2026-10-10: tool_calls_* count every server tool, not only searches.
        return {field: {"web_search_requests": searches, "tool_calls_requested": searches, "tool_calls_executed": searches}}
    return {field: {"web_search_requests": searches}}


SEARCH_FIELDS = ["server_tool_use_details", "server_tool_use"]


@pytest.mark.real_prices
@pytest.mark.parametrize("field", SEARCH_FIELDS)
def test_known_search_charge_survives_missing_tokens_without_inventing_zero_tokens(store, monkeypatch, field):
    transport(monkeypatch, [[packet({"content": "Answer"}, finish="stop", usage=search_usage(1, field))]])
    loop = loop_for(store)
    list(loop.run())
    assert loop.completion.usage["input_tokens"] is None
    assert loop.completion.usage["output_tokens"] is None
    assert loop.completion.usage["estimated_cost_nano_usd"] == 10_000_000
    assert loop.completion.usage["complete"] is False
    assert "input_tokens" not in totals(store)
    assert totals(store)["unmetered_calls"] == 1
    assert totals(store)["estimated_cost_nano_usd"] == 10_000_000


@pytest.mark.parametrize("field", SEARCH_FIELDS)
def test_known_search_count_returns_the_unused_search_budget(store, monkeypatch, field):
    transport(monkeypatch, [[packet({"content": "Answer"}, finish="stop",
                                    usage={"prompt_tokens": 100, "completion_tokens": 20, **search_usage(1, field)})]])
    loop = loop_for(store)
    events = list(loop.run())
    assert loop.completion.usage["web_search_requests"] == 1
    assert loop.remaining_tools == 1  # Two reserved, one used.
    tool = next(e for e in events if e and e.get("name") == "web_search")
    assert tool["status"] == "succeeded" and tool["count"] == 1


@pytest.mark.real_prices
@pytest.mark.parametrize("field", SEARCH_FIELDS)
def test_search_overrun_is_booked_and_never_fails_the_answer(store, monkeypatch, field):
    # OpenRouter does not enforce max_uses for every model (Haiku 4.5 searched
    # 2-3 times, Gemini 3.5 Flash-Lite 3 times at a limit of 1, 2026-10-10).
    metrics = []
    monkeypatch.setattr(agent_client, "record_metric", lambda *args, **kwargs: metrics.append((*args, kwargs)))
    requests, _, _ = transport(monkeypatch, [[packet({"content": "Answer"}, finish="stop",
        usage={"prompt_tokens": 100, "completion_tokens": 20, **search_usage(3, field)})]])
    loop = loop_for(store)
    events = list(loop.run())
    assert requests[0]["max_tool_calls"] == 2
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["status"] == "completed"
    assert loop.completion.text == "Answer"
    # All three searches are booked (catalog price, no provider cost here).
    assert loop.completion.usage["web_search_requests"] == 3
    assert totals(store)["estimated_cost_nano_usd"] == 30_200_000
    assert loop.remaining_tools == -1
    tool = next(e for e in events if e and e.get("name") == "web_search")
    assert tool["status"] == "succeeded" and tool["count"] == 3
    assert [metric for metric in metrics if metric[0] == "search_overrun"] == [
        ("search_overrun", loop.model.model, {"processed": 1})]


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


@pytest.mark.real_prices
@pytest.mark.parametrize("field", SEARCH_FIELDS)
def test_search_and_token_usage_in_separate_chunks_are_merged_once(store, monkeypatch, field):
    transport(monkeypatch, [[packet({"content": "Answer"}, finish="stop",
        usage=search_usage(1, field)),
        packet(usage={"prompt_tokens": 100, "completion_tokens": 20})]])
    loop = loop_for(store)
    list(loop.run())
    assert loop.completion.usage["complete"] is True
    assert totals(store)["estimated_cost_nano_usd"] == 10_200_000


def test_text_beyond_the_storage_limit_is_kept_as_truncated_instead_of_failing(monkeypatch):
    part = "x" * 60_000
    transport(monkeypatch, [[packet({"content": part}), packet({"content": part}),
                             packet({"content": "tail"}, finish="stop", usage=usage())]])
    completion = AgentCompletion()
    deltas = [e for e in completion.stream(model=resolve_agent_model(), messages=[{"role": "user", "content": "Q"}],
                                           api_key="key") if e.get("type") == "delta"]
    assert len(completion.text) == agent_client.TEXT_STORAGE_CHARS
    assert "".join(e["text"] for e in deltas) == completion.text
    # Ends like a token limit, and the usage after the cut still arrives.
    assert completion.finish_reason == "length"
    assert completion.usage["output_tokens"] == 20


def test_a_container_argument_sent_as_json_text_is_decoded():
    # Claude Sonnet sent compare_models' memory as "[]": strict validation
    # rejected every call and the turn ended (2026-10-07).
    from app.services.agent_comparison import CompareArgs
    from app.services.agent_memory import memory_field
    from pydantic import create_model
    args = create_model("MemoryCompareArgs", __base__=CompareArgs, memory=memory_field())
    registry = ToolRegistry([ReadOnlyTool("compare_models", "Compare", args, lambda a, **kw: {})], argument_limit=24_000)
    def call(memory):
        return {"function": {"name": "compare_models", "arguments": json.dumps(
            {"question": "Q", "context": "", "reason": "R", "next_step": "answer", "memory": memory})}}
    assert registry.validate(call("[]"))[1].memory == []
    change = '[{"op": "add", "text": "Lives in Berlin.", "evidence": "I live in Berlin"}]'
    assert registry.validate(call(change))[1].memory[0].text == "Lives in Berlin."
    # Text of another shape is left for validation to reject. (memory itself
    # takes any shape since 2026-10-12, test_agent_memory: a strict list here.)
    strict = create_model("ListCompareArgs", __base__=CompareArgs, items=(list[int], ...))
    registry = ToolRegistry([ReadOnlyTool("compare_models", "Compare", strict, lambda a, **kw: {})], argument_limit=24_000)
    def listed(items):
        return {"function": {"name": "compare_models", "arguments": json.dumps({"question": "Q", "items": items})}}
    assert registry.validate(listed("[1, 2]"))[1].items == [1, 2]
    for bad in ("nothing", '{"op": "add"}', "[1, 2"):
        with pytest.raises(ValueError):
            registry.validate(listed(bad))
    registry = ToolRegistry([ReadOnlyTool("compare_models", "Compare", args, lambda a, **kw: {})], argument_limit=24_000)
    # A text field keeps text that happens to look like JSON.
    plain = {"function": {"name": "compare_models", "arguments": json.dumps(
        {"question": "[]", "context": "", "reason": "R", "next_step": "answer", "memory": []})}}
    assert registry.validate(plain)[1].question == "[]"


def test_refused_tool_calls_say_what_to_change(caplog):
    # A bare "Tool is not authorized" and pydantic's input echo + docs URL
    # (cut after two errors) gave Claude nothing to correct: it repeated the
    # call until "repeated invalid tool requests" ended the turn (2026-10-09).
    from app.services.agent_comparison import CompareArgs
    from app.services.agent_delegation import DelegationLoop
    registry = ToolRegistry([ReadOnlyTool("compare_models", "Compare", CompareArgs, lambda a, **kw: {}),
                             ReadOnlyTool("judge_answer", "Judge", CompareArgs, lambda a, **kw: {})],
                            argument_limit=24_000)
    def call(name, arguments):
        return {"function": {"name": name, "arguments": arguments}}
    with pytest.raises(ValueError, match="Available tools: compare_models, judge_answer") as unknown:
        registry.validate(call("open_url", '{"url": "https://consens.io"}'))
    assert "web pages" in str(unknown.value)
    with pytest.raises(ValueError, match="not valid JSON"):
        registry.validate(call("compare_models", '{"question": '))
    # No arguments streamed is an empty object: the refusal names what is missing.
    with pytest.raises(ValueError, match="question: Field required"):
        registry.validate(call("compare_models", ""))
    secret = "private question text"
    with pytest.raises(ValueError) as invalid:
        registry.validate(call("compare_models", json.dumps({"context": secret, "url": "x", "depth": "deep"})))
    text = str(invalid.value)
    for problem in ("question: Field required", "url: Extra inputs", "depth: Input should be"):
        assert problem in text
    assert len(text) < 500 and "pydantic.dev" not in text and secret not in text
    with caplog.at_level("WARNING"):
        DelegationLoop._log_rejected_call(call("compare_models", json.dumps({"question": secret})), invalid.value)
    assert "tool=compare_models" in caplog.text and "question:missing" in caplog.text
    assert secret not in caplog.text


def test_cosmetic_compare_fields_are_shortened_not_refused():
    from app.services.agent_comparison import CompareArgs
    args = CompareArgs.model_validate({"question": "Q", "reason": "R" * 900, "next_step": "answer",
                                       "status_update": "S" * 900})
    # status_update is shortened; the retired fields are ignored, not refused.
    assert (args.context, len(args.status_update), args.reason, args.next_step) == ("", 400, "", "")
