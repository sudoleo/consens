"""Model-independent search accounting and upstream backpressure regressions."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.api.routers import agent
from app.services import agent_loop
from app.services.agent_costs import RunCosts, provider_cost_nanos
from app.services.agent_policy import AgentPolicy
from app.services.agent_provider_limits import ProviderCooldowns, AgentProviderCooldown
from app.services.llm.agent_client import AgentCompletion, agent_models, measured_usage, resolve_agent_model
from app.services.llm.engines import _ProviderHTTPStatusError, _raise_provider_http_status
from test_agent_runs import api, store, AUTH, UID, receipt, totals
from test_agent_loop import loop_for, packet, transport, usage


@pytest.mark.parametrize("model_id", [m.selection_id for m, _ in agent_models()])
def test_provider_total_wins_over_catalog_including_search_cache_and_reasoning(model_id):
    model = resolve_agent_model(model_id)
    raw = {"prompt_tokens": 1000, "completion_tokens": 100,
           "prompt_tokens_details": {"cached_tokens": 200, "cache_write_tokens": 300},
           "completion_tokens_details": {"reasoning_tokens": 80},
           "server_tool_use": {"web_search_requests": 2}, "cost": "0.012345678"}
    measured = measured_usage(raw, model, searches_enabled=True)
    assert measured["estimated_cost_nano_usd"] == 12_345_678
    assert measured["cost_source"] == "provider" and measured["complete"]
    assert measured["cache_write_tokens"] == 300
    # The provider total is independent of our catalog snapshot, even with
    # different providers, context tiers, tool charges and discounted tokens.
    expensive = replace(model, input_usd_per_million="100", output_usd_per_million="200")
    assert measured_usage(raw, expensive, searches_enabled=True) == measured


@pytest.mark.parametrize("value", [True, False, -1, "NaN", "Infinity", 1e100, "no", {}, None])
def test_invalid_provider_cost_never_becomes_a_known_zero(value):
    assert provider_cost_nanos(value) is None


def test_provider_zero_is_valid_and_cost_without_tokens_remains_partial():
    model = resolve_agent_model()
    assert measured_usage({"cost": 0}, model)["estimated_cost_nano_usd"] == 0
    result = measured_usage({"cost": .01}, model)
    assert result["input_tokens"] is None and not result["complete"]
    assert result["estimated_cost_nano_usd"] == 10_000_000
    assert measured_usage({"prompt_tokens": 12}, model) is None


def test_catalog_fallback_accounts_for_cache_writes_once_and_is_labeled():
    result = measured_usage({"prompt_tokens": 1000, "completion_tokens": 100,
        "prompt_tokens_details": {"cached_tokens": 200, "cache_write_tokens": 300}}, resolve_agent_model("claude-haiku-4-5"))
    assert result["estimated_cost_nano_usd"] == 1_395_000  # 500 + 20 + 375 + 500 microdollars
    assert result["cost_source"] == "catalog"


def test_default_prices_match_catalog_instead_of_stale_dataclass_defaults():
    from decimal import Decimal
    from app.services.llm import agent_client
    model = resolve_agent_model()
    pricing = agent_client._CATALOG["models"][model.model]["pricing"]
    assert Decimal(model.input_usd_per_million) == Decimal(pricing["prompt"]) * 1_000_000
    assert Decimal(model.output_usd_per_million) == Decimal(pricing["completion"]) * 1_000_000


def test_stream_merges_split_usage_and_records_actual_cost_idempotently(store, monkeypatch):
    transport(monkeypatch, [[
        packet({"content": "Answer"}, finish="stop", usage={"cost": .0123}),
        packet(usage={"prompt_tokens": 100, "completion_tokens": 20, "prompt_tokens_details": {"cached_tokens": 30}}),
        packet(usage={"prompt_tokens_details": {"cache_write_tokens": 40}}),
    ]])
    loop = loop_for(store)
    list(loop.run())
    result = loop.completion.usage
    assert result["complete"] and result["cost_source"] == "provider"
    assert result["cached_input_tokens"] == 30 and result["cache_write_tokens"] == 40
    assert result["web_search_requests"] is None
    assert totals(store)["provider_cost_nano_usd"] == 12_300_000
    assert totals(store)["estimated_cost_nano_usd"] == 12_300_000
    assert not store.settle(UID, loop.chat_id, loop.turn_id, completion=receipt(), status="succeeded")
    assert totals(store)["provider_cost_nano_usd"] == 12_300_000


def test_unknown_usage_does_not_release_a_reservation_with_known_cost_only():
    model = resolve_agent_model()
    costs = RunCosts(AgentPolicy())
    reserved = costs.reserve(model, [])
    costs.reconcile(reserved, measured_usage({"cost": .01}, model))
    assert (costs.tokens, costs.cost) == reserved
    assert costs.total()["input_tokens"] is None
    assert not costs.total()["complete"]


@pytest.mark.parametrize("header,expected", [("60", 60), ("0", 1), ("NaN", None), ("invalid", None), ("-5", None)])
def test_http_errors_preserve_only_retry_timing(header, expected):
    with pytest.raises(_ProviderHTTPStatusError) as caught:
        _raise_provider_http_status(SimpleNamespace(status_code=429, headers={"Retry-After": header}, text="private provider body"))
    assert caught.value.retry_after == expected
    assert "private" not in str(caught.value)


def test_cooldown_is_bounded_and_isolated_by_key_and_model():
    time = [100]
    gate = ProviderCooldowns(clock=lambda: time[0])
    model = resolve_agent_model()
    gate.record(model, "one", _ProviderHTTPStatusError(429, retry_after=60))
    with pytest.raises(AgentProviderCooldown) as caught:
        gate.check(model, "one")
    assert caught.value.retry_after == 60
    gate.check(model, "two")
    gate.check(resolve_agent_model("claude-haiku-4-5"), "one")
    time[0] += 60
    gate.check(model, "one")
    for i in range(300):
        gate.record(model, str(i), _ProviderHTTPStatusError(429))
    assert len(gate.entries) == 256


@pytest.mark.parametrize("streamed", [False, True])
def test_rate_limit_blocks_immediate_resubmission_without_another_paid_claim(api, monkeypatch, streamed):
    client, store, calls = api
    gate = ProviderCooldowns()
    monkeypatch.setattr(agent, "provider_cooldowns", gate)
    monkeypatch.setattr(agent_loop, "provider_cooldowns", gate)
    from app.services.llm.engines import _ProviderResponseError
    def fail(self, **kwargs):
        calls.append(kwargs)
        if streamed:
            raise _ProviderResponseError({"code": 429, "message": "private content"})
        raise _ProviderHTTPStatusError(429, retry_after=60)
        yield  # generator contract
    monkeypatch.setattr(AgentCompletion, "stream", fail)
    chat = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat, "question": "Hi", "client_request_id": "limited", "bookmark_id": "limited"}
    first = client.post("/agent", headers=AUTH, json=payload)
    assert "provider_rate_limited" in first.text and "private content" not in first.text
    second = client.post("/agent", headers=AUTH, json={**payload, "client_request_id": "new"})
    assert second.status_code == 429 and int(second.headers["retry-after"]) > 0
    assert len(calls) == totals(store)["calls"] == 1
    assert store.get_chat(UID, chat)["turn_count"] == 1


def test_provider_404_has_an_actionable_message_and_releases_the_chat(api, monkeypatch):
    client, store, calls = api
    def fail(self, **kwargs):
        raise _ProviderHTTPStatusError(404)
        yield
    monkeypatch.setattr(AgentCompletion, "stream", fail)
    chat = store.create_chat(UID, execution_mode="agent")["id"]
    response = client.post("/agent", headers=AUTH, json={"chat_id": chat, "question": "Hi",
        "client_request_id": "missing", "bookmark_id": "missing", "model_id": "claude-haiku-4-5"})
    assert "provider_unavailable" in response.text and "Choose another model" in response.text
    assert not store.active_ref(UID).get().to_dict()["leases"]
