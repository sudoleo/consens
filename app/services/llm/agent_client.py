"""One provider step. Tool execution, run budgets and persistence live outside."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from decimal import Decimal
import json
import os
import re
from urllib.parse import urlsplit

from app.core import config as cfg
from app.services.agent_costs import provider_cost_nanos, search_cost_nanos, token_cost_nanos
from app.services.llm import agent_model_metadata

from app.services.llm.engines import OPENROUTER_CHAT_COMPLETIONS_URL, _ProviderHTTPStatusError, _ProviderResponseError, openrouter_headers
from app.services.llm.provider_runtime import (
    AnalysisBudget, bind_analysis_budget, cancellable_sse_lines, current_analysis_budget,
)
from app.services.llm.streaming import _sse_pairs


@dataclass(frozen=True)
class AgentModel:
    model: str = "deepseek/deepseek-v4.1-flash"
    label: str = "DeepSeek V4.1 Flash"
    max_output_tokens: int = 4096
    # USD / million tokens. A versioned simulation, not an invoice.
    input_usd_per_million: str = "0.15"
    output_usd_per_million: str = "0.60"
    cache_read_usd_per_million: str = "0.003"
    cache_write_usd_per_million: str = ""
    web_search_usd_per_request: str | None = None
    pricing_version: str = "openrouter-2026-09-14"
    selection_id: str = "deepseek/deepseek-v4.1-flash"
    reasoning_effort: str = "default"
    request_config: dict = field(default_factory=dict)
    context_length: int = 1_048_576

    def snapshot(self):
        return asdict(self)

    def settings(self):
        from app.services.agent_policy import tools_for_model
        return {"model_id": self.selection_id, "model": self.model, "label": self.label,
                "reasoning_effort": self.reasoning_effort,
                "reasoning": self.request_config.get("reasoning", {}),
                "tools": list(tools_for_model(self))}


def agent_model(*, _metadata=None) -> AgentModel:
    """Operator configuration is explicit; never silently substitute a model."""
    defaults = AgentModel()
    model_id = os.environ.get("AGENT_MODEL", defaults.model).strip()
    metadata = (_metadata if _metadata is not None else agent_model_metadata.snapshot()).get(model_id)
    if not metadata:
        raise ValueError("The configured agent model needs a catalog entry with prices and context limits.")
    entry = next((entry for entry in cfg.MODEL_CONFIGS.values() if entry.api_model == model_id), None)
    pricing = metadata["pricing"]
    defaults = replace(defaults, model=model_id, label=entry.label if entry else defaults.label if model_id == defaults.model else model_id,
        input_usd_per_million=str(Decimal(pricing["prompt"]) * 1_000_000),
        output_usd_per_million=str(Decimal(pricing["completion"]) * 1_000_000),
        cache_read_usd_per_million=str(Decimal(pricing.get("input_cache_read", pricing["prompt"])) * 1_000_000),
        cache_write_usd_per_million=str(Decimal(pricing.get("input_cache_write", pricing["prompt"])) * 1_000_000),
        web_search_usd_per_request=pricing.get("web_search"), pricing_version=metadata.get('_version', _CATALOG['version']))
    values = {}
    for name in ("model", "label", "input_usd_per_million", "output_usd_per_million",
                 "cache_read_usd_per_million", "cache_write_usd_per_million", "pricing_version"):
        values[name] = os.environ.get("AGENT_" + name.upper(), getattr(defaults, name)).strip()
        if not values[name]:
            raise ValueError("Empty agent configuration")
    values["max_output_tokens"] = int(os.environ.get("AGENT_MAX_OUTPUT_TOKENS", "4096"))
    if not 256 <= values["max_output_tokens"] <= 16384:
        raise ValueError("Invalid agent output limit")
    for name in ("input_usd_per_million", "output_usd_per_million", "cache_read_usd_per_million", "cache_write_usd_per_million"):
        price = Decimal(values[name])
        if not price.is_finite() or price < 0 or price > 1000:
            raise ValueError("Invalid agent price")
    values["max_output_tokens"] = min(values["max_output_tokens"], metadata["top_provider"].get("max_completion_tokens") or values["max_output_tokens"])
    return AgentModel(**values, selection_id=values["model"], context_length=metadata["context_length"],
                      web_search_usd_per_request=defaults.web_search_usd_per_request,
                      request_config=dict(entry.request_config or {}) if entry else {})


_CATALOG = agent_model_metadata.BASELINE
_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")


def _choices(model, metadata):
    reasoning = metadata.get("reasoning") or {}
    efforts = reasoning.get("supported_efforts", [])
    if efforts is None:
        efforts = _EFFORTS
    # These registry entries explicitly name a no-reasoning variant.
    fixed = model.selection_id.endswith(("-no-reasoning", "-non-reasoning"))
    allowed = [x for x in _EFFORTS if x in efforts and not (x == "none" and reasoning.get("mandatory"))]
    return ["default", *(allowed if not fixed else [])]


def _ordered_entries():
    return [entry for provider in cfg.PROVIDERS
            for model_id in cfg.get_ordered_models(provider)
            if (entry := cfg.get_model_config(model_id, provider)) is not None]


def agent_models(*, _metadata=None):
    """Use the DB-backed admin model lists and order, without a second allowlist."""
    catalog = _metadata if _metadata is not None else agent_model_metadata.snapshot()
    default = agent_model(_metadata=catalog)
    result = [(default, catalog[default.model])]
    for entry in _ordered_entries():
        metadata = catalog.get(entry.api_model)
        if not metadata or entry.internal_id == default.selection_id:
            continue
        pricing = metadata["pricing"]
        per_million = lambda key, fallback: str(Decimal(pricing.get(key, fallback)) * 1_000_000)
        result.append((AgentModel(
            model=entry.api_model, label=entry.label, selection_id=entry.internal_id,
            max_output_tokens=min(default.max_output_tokens, metadata["top_provider"].get("max_completion_tokens") or default.max_output_tokens),
            input_usd_per_million=per_million("prompt", "0"),
            output_usd_per_million=per_million("completion", "0"),
            cache_read_usd_per_million=per_million("input_cache_read", pricing["prompt"]),
            cache_write_usd_per_million=per_million("input_cache_write", pricing["prompt"]),
            web_search_usd_per_request=pricing.get("web_search"),
            pricing_version=metadata.get('_version', _CATALOG['version']), request_config=dict(entry.request_config or {}),
            context_length=metadata["context_length"],
        ), metadata))
    return result


def _provider_options(model):
    provider = next((p for p in cfg.PROVIDERS.values()
                     if model.model.startswith(p.openrouter_prefix)), None)
    return {"provider": provider.key if provider else "other",
            "provider_label": provider.label if provider else "Other models"}


def agent_model_options():
    from app.services.agent_policy import tools_for_model, supports_delegation
    catalog = agent_model_metadata.snapshot()
    options = [
        {"id": model.selection_id, "label": model.label, **_provider_options(model),
         "available": True,
         "reasoning_efforts": _choices(model, metadata),
         "default_reasoning": model.request_config.get("reasoning", metadata.get("reasoning") or {}),
         "reasoning_available": bool(metadata.get("reasoning")),
         "delegation_by_effort": {effort: supports_delegation(_resolve_effort(model, metadata, effort))
                                  for effort in _choices(model, metadata)},
         "tools_by_effort": {effort: list(tools_for_model(model))
                             for effort in _choices(model, metadata)}}
        for model, metadata in agent_models(_metadata=catalog)
    ]
    available = {item['id']: item for item in options}
    default = options[0]
    # An invalid or temporarily unresolved admin entry stays visible, with a
    # reason, instead of silently disappearing or inheriting made-up prices.
    models = [default]
    for entry in _ordered_entries():
        if entry.internal_id == default['id']:
            continue
        models.append(available.get(entry.internal_id) or {
            'id': entry.internal_id, 'label': entry.label, 'provider': entry.provider,
            'provider_label': cfg.PROVIDERS[entry.provider].label,
            'available': False, 'unavailable_reason': 'Model information unavailable · check the model ID or retry later',
            'reasoning_efforts': ['default'], 'reasoning_available': False,
        })
    return {'default_model_id': default['id'], 'models': models}


def metered_model(model_id, *, max_tokens=2048):
    """Resolve any existing answer/judge model through the shared registry."""
    entry = cfg.get_model_config(model_id)
    if entry is None:
        raise ValueError("Unknown comparison or judge model")
    metadata = agent_model_metadata.snapshot().get(entry.api_model)
    if not metadata:
        raise ValueError("This model has no metering catalog entry")
    pricing = metadata["pricing"]
    million = lambda key, fallback: str(Decimal(pricing.get(key, fallback)) * 1_000_000)
    return AgentModel(model=entry.api_model, label=entry.label, selection_id=entry.internal_id,
        max_output_tokens=min(max_tokens, metadata["top_provider"].get("max_completion_tokens") or max_tokens),
        input_usd_per_million=million("prompt", "0"), output_usd_per_million=million("completion", "0"),
        cache_read_usd_per_million=million("input_cache_read", pricing["prompt"]),
        cache_write_usd_per_million=million("input_cache_write", pricing["prompt"]),
        context_length=metadata["context_length"], pricing_version=metadata.get('_version', _CATALOG['version']),
        request_config=dict(entry.request_config or {}))


def resolve_agent_model(model_id=None, reasoning_effort="default"):
    models = agent_models()
    for model, metadata in models:
        if model.selection_id != (model_id or models[0][0].selection_id):
            continue
        return _resolve_effort(model, metadata, reasoning_effort)
    if model_id in cfg.MODEL_CONFIGS:
        raise ValueError('Model information is temporarily unavailable. Check the model ID or try again later.')
    raise ValueError("This model is not available in Agent Beta.")


def _resolve_effort(model, metadata, reasoning_effort):
    if reasoning_effort not in _choices(model, metadata):
        raise ValueError("This reasoning level is not supported by the selected model.")
    config = dict(model.request_config)
    reasoning = dict(config.get("reasoning") or {})
    if reasoning_effort != "default":
        reasoning = {"effort": reasoning_effort}
    if metadata.get("reasoning"):
        reasoning["exclude"] = False
        if model.model.startswith("openai/") and reasoning.get("effort") != "none":
            reasoning["summary"] = "auto"
    if reasoning:
        config["reasoning"] = reasoning
    return replace(model, request_config=config, reasoning_effort=reasoning_effort)


def measured_usage(raw: object, model: AgentModel, *, searches_enabled=False) -> dict | None:
    """Missing counts are unknown, never estimated or silently set to zero."""
    if not isinstance(raw, dict):
        return None
    prompt = raw.get("prompt_tokens", raw.get("input_tokens"))
    completion = raw.get("completion_tokens", raw.get("output_tokens"))
    valid = lambda value: type(value) is int and 0 <= value <= 10_000_000
    tokens_known = valid(prompt) and valid(completion)
    cost = provider_cost_nanos(raw.get("cost"))
    if not tokens_known and cost is None:
        return None
    prompt_details = raw.get("prompt_tokens_details", raw.get("input_tokens_details")) or {}
    output_details = raw.get("completion_tokens_details", raw.get("output_tokens_details")) or {}
    cached = prompt_details.get("cached_tokens", 0) if isinstance(prompt_details, dict) else 0
    reasoning = output_details.get("reasoning_tokens", 0) if isinstance(output_details, dict) else 0
    written = prompt_details.get("cache_write_tokens", 0) if isinstance(prompt_details, dict) else 0
    cached = cached if tokens_known and valid(cached) and cached <= prompt else 0
    written = written if tokens_known and valid(written) and written <= prompt - cached else 0
    reasoning = reasoning if tokens_known and valid(reasoning) and reasoning <= completion else 0
    server_use = raw.get("server_tool_use")
    searches = server_use.get("web_search_requests") if isinstance(server_use, dict) else None
    searches_known = valid(searches)
    source = "provider" if cost is not None else "catalog"
    cost_complete = tokens_known
    if cost is None:
        cost = token_cost_nanos(model, prompt, completion, cached, written)
        if searches_enabled:
            price = search_cost_nanos(model)
            cost_complete = searches_known and (searches == 0 or price is not None)
            if searches_known and price is not None:
                cost += searches * price
    # Integer nanodollars avoid cumulative float/rounding drift. Reasoning is
    # already included in completion_tokens and must not be charged twice.
    return {
        "input_tokens": prompt if tokens_known else None, "output_tokens": completion if tokens_known else None,
        "cached_input_tokens": cached if tokens_known else None, "cache_write_tokens": written if tokens_known else None,
        "reasoning_tokens": reasoning if tokens_known else None,
        "web_search_requests": searches if searches_known else None,
        "estimated_cost_nano_usd": cost, "cost_source": source, "complete": tokens_known,
        "cost_complete": source == "provider" or cost_complete,
        "pricing_version": model.pricing_version,
        "source": "provider", "billing_mode": "simulation", "currency": "USD",
    }


class AgentCompletion:
    """Mutable receipt survives cancellation/errors after any streamed event."""
    def __init__(self):
        self.text = ""
        self.usage = None
        self.generation_id = ""
        self.finish_reason = ""
        self.activity = []
        self.reasoning_chars = 0
        self.reasoning_truncated = False
        self.step_id = "completion:0"
        self.tool_calls = []
        self.sources = []
        self._tool_parts = {}
        self._raw_usage = {}
        self._final_usage_fields = set()
        self.tool_argument_limit = 2048
        self.tool_call_limit = 1
        self._reasoning_parts = {}
        self._reasoning_text = ""

    def record_rejection(self, error, model):
        # An HTTP admission rejection never opened an SSE generation. Timeouts,
        # 5xx and errors inside an accepted stream can still have incurred usage.
        if (isinstance(error, _ProviderHTTPStatusError)
                and error.status_code in {400, 401, 402, 403, 404, 413, 422, 429}
                and self.usage is None and not self.generation_id and not self.text
                and not self.reasoning_chars and not self._tool_parts):
            self.record_unstarted(model)
            self.usage["source"] = "provider_rejection"

    def record_unstarted(self, model):
        self.usage = measured_usage({"prompt_tokens": 0, "completion_tokens": 0, "cost": 0,
                                    "server_tool_use": {"web_search_requests": 0}}, model)
        self.usage["source"] = "not_started"

    def assistant_message(self):
        """Exact provider continuation data; never a public message or stored trace."""
        message = {"role": "assistant", "content": self.text}
        if self.tool_calls:
            message["tool_calls"] = self.tool_calls
        if self._reasoning_parts:
            message["reasoning_details"] = list(self._reasoning_parts.values())
        elif self._reasoning_text:
            message["reasoning"] = self._reasoning_text
        return message

    def _preserve_reasoning(self, delta):
        for detail in delta.get("reasoning_details") or []:
            if not isinstance(detail, dict) or type(detail.get("index", 0)) is not int:
                raise ValueError("Invalid reasoning continuation")
            key = detail.get("index", 0)
            target = self._reasoning_parts.setdefault(key, {})
            for field, value in detail.items():
                if field in {"text", "summary", "data", "signature"} and isinstance(value, str):
                    target[field] = target.get(field, "") + value
                elif field in target and target[field] != value:
                    raise ValueError("Reasoning identity changed during a stream")
                else:
                    target[field] = value
        text = delta.get("reasoning") or delta.get("reasoning_content")
        if isinstance(text, str):
            self._reasoning_text += text
        if len(json.dumps(self._reasoning_parts)) + len(self._reasoning_text) > 128_000:
            raise ValueError("Reasoning continuation exceeds context limit")

    def event(self, kind, event_id, **data):
        event = {"version": 1, "step_id": self.step_id, "kind": kind, "id": event_id, **data}
        existing = next((item for item in self.activity if item["id"] == event_id), None)
        if existing is None:
            if kind == "reasoning" and len(self.activity) >= 32:
                self.reasoning_truncated = True
                return None
            self.activity.append({k: v for k, v in event.items() if k != "append"})
        elif data.get("append"):
            existing["text"] += data["text"]
        else:
            existing.update(event)
        return {"type": "activity", **event}

    def reasoning_events(self, delta):
        details = delta.get("reasoning_details")
        if not isinstance(details, list) or not details:
            text = delta.get("reasoning") or delta.get("reasoning_content")
            details = [{"type": "reasoning.text", "text": text, "index": 0}] if isinstance(text, str) and text else []
        for index, detail in enumerate(details):
            if not isinstance(detail, dict):
                continue
            kind = detail.get("type")
            text = detail.get("summary" if kind == "reasoning.summary" else "text")
            if kind not in {"reasoning.text", "reasoning.summary"} or not isinstance(text, str) or not text:
                # Encrypted reasoning is not display text and is never persisted.
                continue
            available = max(0, 32_000 - self.reasoning_chars)
            self.reasoning_truncated |= len(text) > available
            text = text[:available]
            if not text:
                continue
            self.reasoning_chars += len(text)
            block_id = str(detail.get("index", index))[:40]
            event = self.event("reasoning", f"{kind}:{block_id}", format=kind.split(".")[1], text=text, append=True)
            if event:
                yield event

    def _tool_delta(self, raw):
        if not isinstance(raw, list) or len(raw) > self.tool_call_limit:
            raise ValueError("Tool call batch exceeds the allowed limit")
        for part in raw:
            if not isinstance(part, dict) or type(part.get("index")) is not int or not 0 <= part["index"] < self.tool_call_limit:
                raise ValueError("Invalid tool call index")
            target = self._tool_parts.setdefault(part["index"], {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
            if part.get("type", "function") != "function":
                raise ValueError("Invalid tool call type")
            function = part.get("function") or {}
            if not isinstance(function, dict):
                raise ValueError("Invalid tool call")
            for key, source, output, limit in (("id", part, target, 160), ("name", function, target["function"], 64),
                                                ("arguments", function, target["function"], self.tool_argument_limit)):
                fragment = source.get(key, "")
                if not isinstance(fragment, str) or len(output[key]) + len(fragment) > limit:
                    raise ValueError("Tool call exceeds argument limit")
                output[key] += fragment

    def _annotations(self, raw):
        if not isinstance(raw, list):
            return
        for annotation in raw[:20]:
            value = annotation.get("url_citation") if isinstance(annotation, dict) else None
            if not isinstance(value, dict):
                continue
            url = value.get("url")
            if not isinstance(url, str) or len(url) > 2048 or any(c.isspace() or ord(c) < 32 for c in url):
                continue
            try:
                parsed = urlsplit(url)
                valid = parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username and not parsed.password
            except ValueError:
                valid = False
            if valid and len(self.sources) < 5 and not any(s["url"] == url for s in self.sources):
                title = value.get("title")
                self.sources.append({"url": url, "title": title[:200] if isinstance(title, str) else parsed.hostname})

    def stream(self, *, model: AgentModel, messages: list[dict], api_key: str, tools=None,
               native_searches=0, allow_tool_calls=False):
        payload = {
            "model": model.model, "messages": messages,
            "max_tokens": model.max_output_tokens,
            "stream": True, "stream_options": {"include_usage": True},
            "provider": {"zdr": True},
        }
        payload.update({k: v for k, v in model.request_config.items() if k != "provider" and not k.startswith("_agent_")})
        payload.update(model=model.model, messages=messages, max_tokens=model.max_output_tokens,
                       stream=True, stream_options={"include_usage": True})
        payload["provider"].update(model.request_config.get("provider") or {})
        payload["provider"]["zdr"] = True
        # All execution-affecting fields are owned by this adapter, never model
        # arguments, user settings or arbitrary registry configuration.
        for field in ("tools", "tool_choice", "plugins", "parallel_tool_calls", "max_tool_calls", "stop_server_tools_when"):
            payload.pop(field, None)
        if tools:
            payload["tools"] = tools
            if any(tool.get("type") == "function" for tool in tools):
                payload["tool_choice"] = "auto" if allow_tool_calls or native_searches else "none"
                payload["parallel_tool_calls"] = False
        if native_searches:
            payload["max_tool_calls"] = native_searches
        with bind_analysis_budget(current_analysis_budget() or AnalysisBudget(seconds=180, max_calls=1)):
            lines = cancellable_sse_lines(
                OPENROUTER_CHAT_COMPLETIONS_URL, json=payload,
                headers=openrouter_headers(api_key),
            )
            try:
                for _, encoded in _sse_pairs(lines):
                    if len(encoded) > 256_000:
                        raise ValueError("Provider event exceeds limit")
                    if encoded.strip() == "[DONE]":
                        break
                    data = json.loads(encoded)
                    if not isinstance(data, dict):
                        raise ValueError("Invalid provider event")
                    self.generation_id = str(data.get("id") or self.generation_id)[:200]
                    terminal = self.finish_reason or any(choice.get("finish_reason") for choice in data.get("choices") or [])
                    reported = data.get("usage")
                    if isinstance(reported, dict):
                        if terminal:
                            self._final_usage_fields.update(reported)
                        for field in ("prompt_tokens", "completion_tokens", "prompt_tokens_details", "completion_tokens_details",
                                      "input_tokens", "output_tokens", "input_tokens_details", "output_tokens_details", "cost"):
                            if field in reported:
                                if field.endswith("_details") and isinstance(reported[field], dict):
                                    previous = self._raw_usage.get(field)
                                    self._raw_usage[field] = {**(previous if isinstance(previous, dict) else {}), **reported[field]}
                                else:
                                    self._raw_usage[field] = reported[field]
                        server_use = reported.get("server_tool_use")
                        if isinstance(server_use, dict) and "web_search_requests" in server_use:
                            self._raw_usage["server_tool_use"] = {"web_search_requests": server_use["web_search_requests"]}
                    usage = measured_usage(self._raw_usage, model, searches_enabled=bool(native_searches)) if isinstance(reported, dict) else None
                    known = False
                    if native_searches and isinstance(reported, dict):
                        server_use = self._raw_usage.get("server_tool_use")
                        count = server_use.get("web_search_requests") if isinstance(server_use, dict) else None
                        known = type(count) is int and 0 <= count <= 10_000
                        if usage is None and known:
                            # Search cost can be known even if token usage is not.
                            price = search_cost_nanos(model)
                            usage = {"input_tokens": None, "output_tokens": None, "cached_input_tokens": None,
                                     "reasoning_tokens": None, "estimated_cost_nano_usd": count * price if price is not None else None,
                                     "web_search_requests": count, "complete": False, "cost_source": "catalog",
                                     "pricing_version": model.pricing_version, "source": "provider",
                                     "billing_mode": "simulation", "currency": "USD"}
                    if usage is not None:
                        # Cumulative telemetry before the terminal choice is a
                        # lower bound, not a final receipt after a disconnect.
                        final_tokens = (bool(self._final_usage_fields & {"prompt_tokens", "input_tokens"})
                                        and bool(self._final_usage_fields & {"completion_tokens", "output_tokens"}))
                        if not final_tokens:
                            usage.update(provisional=True, complete=False)
                        if (not terminal or (usage.get("cost_source") == "provider" and "cost" not in self._final_usage_fields)
                                or (usage.get("cost_source") == "catalog" and not final_tokens)):
                            usage["cost_complete"] = False
                        self.usage = usage
                        yield self.event("usage", "usage", usage=usage)
                        if native_searches and known and count > native_searches:
                            raise RuntimeError("Provider exceeded the native search limit")
                    if data.get("error"):
                        raise _ProviderResponseError(data["error"])
                    for choice in data.get("choices") or []:
                        if choice.get("index", 0) != 0:
                            raise ValueError("Unexpected parallel completion")
                        delta = choice.get("delta") or {}
                        if allow_tool_calls:
                            self._preserve_reasoning(delta)
                        if delta.get("tool_calls"):
                            if not allow_tool_calls:
                                raise RuntimeError("Unexpected tool call")
                            self._tool_delta(delta["tool_calls"])
                        self._annotations(delta.get("annotations"))
                        self._annotations((choice.get("message") or {}).get("annotations"))
                        yield from self.reasoning_events(delta)
                        chunk = delta.get("content")
                        if isinstance(chunk, str) and chunk:
                            if not self.text:
                                yield self.event("status", "responding", status="responding")
                            self.text += chunk
                            if len(self.text) > 100_000:
                                raise ValueError("Agent response exceeds storage limit")
                            yield {"type": "delta", "text": chunk}
                        if choice.get("finish_reason"):
                            self.finish_reason = str(choice["finish_reason"])
                if self.finish_reason == "tool_calls" and allow_tool_calls:
                    self.tool_calls = [self._tool_parts[i] for i in sorted(self._tool_parts)]
                    if not self.tool_calls or any(not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", call["id"]) for call in self.tool_calls):
                        raise ValueError("Invalid completed tool call")
                elif self._tool_parts or self.finish_reason not in {"stop", "length"} or not self.text.strip():
                    raise RuntimeError("Agent stream ended without a completed answer")
            finally:
                lines.close()
