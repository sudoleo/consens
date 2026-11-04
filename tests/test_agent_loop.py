"""Provider protocol of the agent's requests. No real paid model calls."""
from dataclasses import replace
import json
import re

from pydantic import BaseModel, ConfigDict, Field
import pytest

from app.core.openrouter_contract import provider_session_id
from agent_reviewers import without_reviewers
from app.services.agent_comparison import comparison_selection
from app.services.agent_delegation import DelegationLoop
from app.services.agent_tools import ReadOnlyTool, ToolRegistry, configured_model
from app.services.llm import agent_client
from app.services.llm.agent_client import AgentCompletion, resolve_agent_model
from app.services.llm.provider_runtime import ProviderCancellation, current_analysis_budget
from test_agent_runs import AUTH, UID, answered, api, pending, store, totals


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
        # A copy: the run goes on appending to the conversation it sent.
        requests.append(json.loads(json.dumps(kwargs["json"])))
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


def chat_loop(store, chat_id, turn, model, messages=None):
    """The agent's run of ``turn``, without reviewers."""
    return without_reviewers(DelegationLoop(
        store=store, uid=UID, chat_id=chat_id, turn_id=turn["id"], model=model,
        messages=messages or store.messages(UID, chat_id, turn, model=model), api_key="test",
        cancellation=ProviderCancellation(),
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"})))


def loop_for(store):
    chat_id, turn = pending(store)
    return chat_loop(store, chat_id, turn, configured_model(resolve_agent_model("claude-haiku-4-5")))


def test_a_service_tier_of_the_model_config_reaches_the_request(store, monkeypatch):
    # The way judges ask for OpenAI's priority lane (ComparisonTools.judge_transport).
    requests, _, _ = transport(monkeypatch, [[packet({"content": "Answer"}), packet(finish="stop", usage=usage())]])
    chat_id, turn = pending(store)
    model = configured_model(resolve_agent_model("claude-haiku-4-5"))
    model = replace(model, request_config={**model.request_config, "service_tier": "priority"})
    loop = chat_loop(store, chat_id, turn, model)
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
    loop = chat_loop(store, chat_id, turn, model)
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


def follow_up_loop(store, model="claude-haiku-4-5"):
    """The run of a chat's second message: system prompt, one earlier
    question and answer, then the new question. Returns the loop and its
    conversation as the run begins (its system prompt with the run's blocks)."""
    chat_id, first = pending(store)
    assert answered(store, chat_id, first["id"], model=resolve_agent_model(model))
    _, second = pending(store, chat_id=chat_id, request_id="two", question="What next?")
    model = configured_model(resolve_agent_model(model))
    loop = chat_loop(store, chat_id, second, model)
    return loop, [dict(message) for message in loop.messages]


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
    loop, messages = follow_up_loop(store)
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


def test_a_writing_step_with_tool_choice_auto_keeps_the_request_and_drops_its_calls(store, monkeypatch):
    """The agent's steps send tool_choice "auto" also where they may only
    write (prompt cache): a reply of calls alone ends without text instead
    of failing, so the loop can ask once more; "none" may still be asked."""
    from app.services.llm.agent_client import AgentStreamIncomplete
    requests, _, _ = transport(monkeypatch, [[packet({"tool_calls": [call()]}, finish="tool_calls", usage=usage())],
                                             [packet({"tool_calls": [call()]}, finish="tool_calls", usage=usage())],
                                             [packet({"content": "Four."}, finish="stop", usage=usage())]])
    model = configured_model(resolve_agent_model("claude-haiku-4-5"))
    tools = client_registry([]).schemas
    calls_only = AgentCompletion()
    list(calls_only.stream(model=model, messages=[{"role": "user", "content": "Hi"}], api_key="test", tools=tools,
                           allow_tool_calls=False, tool_choice="auto"))
    assert requests[0]["tool_choice"] == "auto" and requests[0]["tools"] == tools
    assert calls_only.finish_reason == "tool_calls" and calls_only.text == "" and calls_only.tool_calls == []
    assert calls_only.skipped_tool_parts
    # Without the explicit choice a writing step's calls alone still fail it.
    with pytest.raises(AgentStreamIncomplete):
        list(AgentCompletion().stream(model=model, messages=[{"role": "user", "content": "Hi"}], api_key="test",
                                      tools=tools, allow_tool_calls=False))
    assert requests[1]["tool_choice"] == "none"
    retry = AgentCompletion()
    list(retry.stream(model=model, messages=[{"role": "user", "content": "Hi"}], api_key="test", tools=tools,
                      allow_tool_calls=False, tool_choice="none"))
    assert requests[2]["tool_choice"] == "none" and retry.text == "Four."


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


@pytest.mark.real_prices
@pytest.mark.parametrize("field", SEARCH_FIELDS)
def test_search_overrun_is_booked_and_never_fails_the_answer(store, monkeypatch, field):
    # OpenRouter does not enforce max_uses for every model (Haiku 4.5 searched
    # 2-3 times, Gemini 3.5 Flash-Lite 3 times at a limit of 1, 2026-10-10).
    metrics = []
    monkeypatch.setattr(agent_client, "record_metric", lambda *args, **kwargs: metrics.append((*args, kwargs)))
    monkeypatch.setattr("app.services.agent_audit.AGENT_SEARCH_ROUNDS", 2)
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
    tool = next(e for e in events if e and e.get("name") == "web_search")
    assert tool["status"] == "succeeded" and tool["count"] == 3
    assert [metric for metric in metrics if metric[0] == "search_overrun"] == [
        ("search_overrun", loop.model.model, {"processed": 1})]


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
    # Claude Sonnet sent compare_models' memory as "[]" (a field until
    # 2026-10-31): strict validation rejected every call and the turn ended
    # (2026-10-07). Every list or object argument is decoded alike.
    from pydantic import BaseModel, ConfigDict
    from app.services.agent_comparison import AuditCompareArgs
    from app.services.agent_memory import AuditUpdateMemoryArgs
    registry = ToolRegistry([ReadOnlyTool("compare_models", "Compare", AuditCompareArgs, lambda a, **kw: {}),
                             ReadOnlyTool("update_memory", "Remember", AuditUpdateMemoryArgs, lambda a, **kw: {})],
                            argument_limit=24_000)
    def call(name, args):
        return {"function": {"name": name, "arguments": json.dumps(args)}}
    assert registry.validate(call("compare_models", {"question": "Q", "file_ids": "[]"}))[1].file_ids == []
    change = '[{"op": "add", "text": "Lives in Berlin."}]'
    assert registry.validate(call("update_memory", {"changes": change}))[1].changes[0].text == "Lives in Berlin."

    # Text of another shape is left for validation to reject.
    class Listed(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        question: str
        items: list[int]
    registry = ToolRegistry([ReadOnlyTool("compare_models", "Compare", Listed, lambda a, **kw: {})], argument_limit=24_000)
    def listed(items):
        return {"function": {"name": "compare_models", "arguments": json.dumps({"question": "Q", "items": items})}}
    assert registry.validate(listed("[1, 2]"))[1].items == [1, 2]
    for bad in ("nothing", '{"op": "add"}', "[1, 2"):
        with pytest.raises(ValueError):
            registry.validate(listed(bad))
    registry = ToolRegistry([ReadOnlyTool("compare_models", "Compare", AuditCompareArgs, lambda a, **kw: {})],
                            argument_limit=24_000)
    # A text field keeps text that happens to look like JSON.
    plain = {"function": {"name": "compare_models", "arguments": json.dumps({"question": "[]", "file_ids": []})}}
    assert registry.validate(plain)[1].question == "[]"


def test_refused_tool_calls_say_what_to_change(caplog):
    # A bare "Tool is not authorized" and pydantic's input echo + docs URL
    # (cut after two errors) gave Claude nothing to correct: it repeated the
    # call until "repeated invalid tool requests" ended the turn (2026-10-09).
    from app.services.agent_comparison import AuditCompareArgs
    from app.services.agent_delegation import DelegationLoop
    registry = ToolRegistry([ReadOnlyTool("compare_models", "Compare", AuditCompareArgs, lambda a, **kw: {}),
                             ReadOnlyTool("audit_answer", "Review", AuditCompareArgs, lambda a, **kw: {})],
                            argument_limit=24_000)
    def call(name, arguments):
        return {"function": {"name": name, "arguments": arguments}}
    with pytest.raises(ValueError, match="Available tools: compare_models, audit_answer") as unknown:
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


def test_a_recursive_argument_model_is_refused_at_registration():
    # Flat schemas (argument_schema) cannot write out a model that holds itself.
    from pydantic import BaseModel, ConfigDict
    class Node(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        children: list["Node"] = []
    with pytest.raises(ValueError, match="recursive"):
        ToolRegistry([ReadOnlyTool("tree", "Tree", Node, lambda a, **kw: {})])
