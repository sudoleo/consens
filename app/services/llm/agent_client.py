"""One provider step. Tool execution, run budgets and persistence live outside."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from decimal import Decimal
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from app.core import config as cfg
from app.services.agent_costs import NATIVE_SEARCH_NANO_USD, token_cost_nanos

from app.services.llm.engines import OPENROUTER_CHAT_COMPLETIONS_URL, openrouter_headers
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


def agent_model() -> AgentModel:
    """Operator configuration is explicit; never silently substitute a model."""
    defaults = AgentModel()
    model_id = os.environ.get("AGENT_MODEL", defaults.model).strip()
    metadata = _CATALOG["models"].get(model_id)
    if not metadata:
        raise ValueError("The configured agent model needs a catalog entry with prices and context limits.")
    entry = next((entry for entry in cfg.MODEL_CONFIGS.values() if entry.api_model == model_id), None)
    if model_id != defaults.model:
        pricing = metadata["pricing"]
        defaults = replace(defaults, model=model_id, label=entry.label if entry else model_id,
            input_usd_per_million=str(Decimal(pricing["prompt"]) * 1_000_000),
            output_usd_per_million=str(Decimal(pricing["completion"]) * 1_000_000),
            cache_read_usd_per_million=str(Decimal(pricing.get("input_cache_read", pricing["prompt"])) * 1_000_000),
            pricing_version=_CATALOG["version"])
    values = {}
    for name in ("model", "label", "input_usd_per_million", "output_usd_per_million",
                 "cache_read_usd_per_million", "pricing_version"):
        values[name] = os.environ.get("AGENT_" + name.upper(), getattr(defaults, name)).strip()
        if not values[name]:
            raise ValueError("Empty agent configuration")
    values["max_output_tokens"] = int(os.environ.get("AGENT_MAX_OUTPUT_TOKENS", "4096"))
    if not 256 <= values["max_output_tokens"] <= 16384:
        raise ValueError("Invalid agent output limit")
    for name in ("input_usd_per_million", "output_usd_per_million", "cache_read_usd_per_million"):
        price = Decimal(values[name])
        if not price.is_finite() or price < 0 or price > 1000:
            raise ValueError("Invalid agent price")
    values["max_output_tokens"] = min(values["max_output_tokens"], metadata["top_provider"].get("max_completion_tokens") or values["max_output_tokens"])
    return AgentModel(**values, selection_id=values["model"], context_length=metadata["context_length"],
                      request_config=dict(entry.request_config or {}) if entry else {})


_CATALOG = json.loads(Path(__file__).with_name("agent_model_catalog.json").read_text(encoding="utf-8"))
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


def agent_models():
    """Reuse the active product allowlist; only priced, known text models qualify.

    The checked-in public catalog is a versioned simulation baseline, not a
    live provider quote. No user-controlled prices or provider URLs are used.
    """
    default = agent_model()
    result = [(default, _CATALOG["models"].get(default.model, {}))]
    for entry in sorted(cfg.MODEL_CONFIGS.values(), key=lambda x: (x.provider, x.label)):
        metadata = _CATALOG["models"].get(entry.api_model)
        if not metadata or entry.api_model == default.model:
            continue
        pricing = metadata["pricing"]
        per_million = lambda key, fallback: str(Decimal(pricing.get(key, fallback)) * 1_000_000)
        result.append((AgentModel(
            model=entry.api_model, label=entry.label, selection_id=entry.internal_id,
            max_output_tokens=min(default.max_output_tokens, metadata["top_provider"].get("max_completion_tokens") or default.max_output_tokens),
            input_usd_per_million=per_million("prompt", "0"),
            output_usd_per_million=per_million("completion", "0"),
            cache_read_usd_per_million=per_million("input_cache_read", pricing["prompt"]),
            pricing_version=_CATALOG["version"], request_config=dict(entry.request_config or {}),
            context_length=metadata["context_length"],
        ), metadata))
    return result


def agent_model_options():
    from app.services.agent_policy import tools_for_model
    return {"default_model_id": agent_model().selection_id, "models": [
        {"id": model.selection_id, "label": model.label, "reasoning_efforts": _choices(model, metadata),
         "default_reasoning": model.request_config.get("reasoning", metadata.get("reasoning") or {}),
         "reasoning_available": bool(metadata.get("reasoning")),
         "tools_by_effort": {effort: list(tools_for_model(model))
                             for effort in _choices(model, metadata)}}
        for model, metadata in agent_models()
    ]}


def resolve_agent_model(model_id=None, reasoning_effort="default"):
    for model, metadata in agent_models():
        if model.selection_id != (model_id or agent_model().selection_id):
            continue
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
    raise ValueError("This model is not available in Agent Beta.")


def measured_usage(raw: object, model: AgentModel) -> dict | None:
    """Missing counts are unknown, never estimated or silently set to zero."""
    if not isinstance(raw, dict):
        return None
    prompt = raw.get("prompt_tokens", raw.get("input_tokens"))
    completion = raw.get("completion_tokens", raw.get("output_tokens"))
    valid = lambda value: type(value) is int and 0 <= value <= 10_000_000
    if not valid(prompt) or not valid(completion):
        return None
    prompt_details = raw.get("prompt_tokens_details", raw.get("input_tokens_details")) or {}
    output_details = raw.get("completion_tokens_details", raw.get("output_tokens_details")) or {}
    cached = prompt_details.get("cached_tokens", 0) if isinstance(prompt_details, dict) else 0
    reasoning = output_details.get("reasoning_tokens", 0) if isinstance(output_details, dict) else 0
    cached = cached if valid(cached) and cached <= prompt else 0
    reasoning = reasoning if valid(reasoning) and reasoning <= completion else 0
    # Integer nanodollars avoid cumulative float/rounding drift. Reasoning is
    # already included in completion_tokens and must not be charged twice.
    return {
        "input_tokens": prompt, "output_tokens": completion,
        "cached_input_tokens": cached, "reasoning_tokens": reasoning,
        "estimated_cost_nano_usd": token_cost_nanos(model, prompt, completion, cached),
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
        if not isinstance(raw, list) or len(raw) > 1:
            raise ValueError("Only one tool call per model step is allowed")
        for part in raw:
            if not isinstance(part, dict) or type(part.get("index")) is not int or part["index"] != 0:
                raise ValueError("Invalid tool call index")
            target = self._tool_parts.setdefault(0, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
            if part.get("type", "function") != "function":
                raise ValueError("Invalid tool call type")
            function = part.get("function") or {}
            if not isinstance(function, dict):
                raise ValueError("Invalid tool call")
            for key, source, output, limit in (("id", part, target, 160), ("name", function, target["function"], 64),
                                                ("arguments", function, target["function"], 2048)):
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
            "provider": {"zdr": True, "allow_fallbacks": False},
        }
        payload.update({k: v for k, v in model.request_config.items() if k != "provider"})
        payload.update(model=model.model, messages=messages, max_tokens=model.max_output_tokens,
                       stream=True, stream_options={"include_usage": True})
        payload["provider"].update(model.request_config.get("provider") or {})
        payload["provider"].update(zdr=True, allow_fallbacks=False)
        # All execution-affecting fields are owned by this adapter, never model
        # arguments, user settings or arbitrary registry configuration.
        for field in ("tools", "tool_choice", "plugins", "parallel_tool_calls", "max_tool_calls", "stop_server_tools_when"):
            payload.pop(field, None)
        if tools:
            # Anthropic's checked endpoint does not advertise parallel_tool_calls.
            # Enforce client-call cardinality in the parser instead of sending
            # an unsupported parameter with require_parameters=True.
            payload.update(tools=tools, tool_choice="auto" if allow_tool_calls or native_searches else "none")
            payload["provider"]["require_parameters"] = True
        if native_searches:
            payload["max_tool_calls"] = native_searches
            # Bedrock does not support this native search. Explicitly pin the
            # checked first integration, including the existing ZDR constraint.
            payload["provider"]["only"] = ["anthropic"]
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
                    reported = data.get("usage")
                    if isinstance(reported, dict):
                        for field in ("prompt_tokens", "completion_tokens", "prompt_tokens_details", "completion_tokens_details",
                                      "input_tokens", "output_tokens", "input_tokens_details", "output_tokens_details"):
                            if field in reported:
                                self._raw_usage[field] = reported[field]
                        server_use = reported.get("server_tool_use")
                        if isinstance(server_use, dict) and "web_search_requests" in server_use:
                            self._raw_usage["server_tool_use"] = {"web_search_requests": server_use["web_search_requests"]}
                    usage = measured_usage(self._raw_usage, model) if isinstance(reported, dict) else None
                    known = False
                    if native_searches and isinstance(reported, dict):
                        server_use = self._raw_usage.get("server_tool_use")
                        count = server_use.get("web_search_requests") if isinstance(server_use, dict) else None
                        known = type(count) is int and 0 <= count <= 10_000
                        if usage is None and known:
                            # Search cost can be known even if token usage is not.
                            usage = {"input_tokens": None, "output_tokens": None, "cached_input_tokens": None,
                                     "reasoning_tokens": None, "estimated_cost_nano_usd": 0,
                                     "pricing_version": model.pricing_version, "source": "provider",
                                     "billing_mode": "simulation", "currency": "USD"}
                        if usage is not None:
                            usage.update(web_search_requests=count if known else None,
                                         complete=known and usage["input_tokens"] is not None)
                            if known:
                                usage["estimated_cost_nano_usd"] += count * NATIVE_SEARCH_NANO_USD
                    if usage is not None:
                        self.usage = usage
                        yield self.event("usage", "usage", usage=usage)
                        if native_searches and known and count > native_searches:
                            raise RuntimeError("Provider exceeded the native search limit")
                    if data.get("error"):
                        raise RuntimeError("Agent provider failed")
                    for choice in data.get("choices") or []:
                        if choice.get("index", 0) != 0:
                            raise ValueError("Unexpected parallel completion")
                        delta = choice.get("delta") or {}
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
                    self.tool_calls = list(self._tool_parts.values())
                    if not self.tool_calls or any(not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", call["id"]) for call in self.tool_calls):
                        raise ValueError("Invalid completed tool call")
                elif self._tool_parts or self.finish_reason not in {"stop", "length"} or not self.text.strip():
                    raise RuntimeError("Agent stream ended without a completed answer")
            finally:
                lines.close()
