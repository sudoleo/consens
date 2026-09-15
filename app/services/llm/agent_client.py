"""One text completion, with provider-reported usage and no implicit tools.

The transport has no chat, billing or consensus responsibilities. Future tool
steps can use the same event/receipt contract without changing their callers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from decimal import Decimal, ROUND_HALF_UP
import json
import os
from pathlib import Path

from app.core import config as cfg

from app.services.llm.engines import OPENROUTER_CHAT_COMPLETIONS_URL, openrouter_headers
from app.services.llm.provider_runtime import (
    AnalysisBudget, bind_analysis_budget, cancellable_sse_lines,
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
        return {"model_id": self.selection_id, "model": self.model, "label": self.label,
                "reasoning_effort": self.reasoning_effort,
                "reasoning": self.request_config.get("reasoning", {})}


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
    return {"default_model_id": agent_model().selection_id, "models": [
        {"id": model.selection_id, "label": model.label, "reasoning_efforts": _choices(model, metadata),
         "default_reasoning": model.request_config.get("reasoning", metadata.get("reasoning") or {}),
         "reasoning_available": bool(metadata.get("reasoning"))}
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
    prompt, completion = raw.get("prompt_tokens"), raw.get("completion_tokens")
    valid = lambda value: type(value) is int and 0 <= value <= 10_000_000
    if not valid(prompt) or not valid(completion):
        return None
    prompt_details = raw.get("prompt_tokens_details") or {}
    output_details = raw.get("completion_tokens_details") or {}
    cached = prompt_details.get("cached_tokens", 0) if isinstance(prompt_details, dict) else 0
    reasoning = output_details.get("reasoning_tokens", 0) if isinstance(output_details, dict) else 0
    cached = cached if valid(cached) and cached <= prompt else 0
    reasoning = reasoning if valid(reasoning) and reasoning <= completion else 0
    # Integer nanodollars avoid cumulative float/rounding drift. Reasoning is
    # already included in completion_tokens and must not be charged twice.
    nanos = ((prompt - cached) * Decimal(model.input_usd_per_million)
             + cached * Decimal(model.cache_read_usd_per_million)
             + completion * Decimal(model.output_usd_per_million)) * 1000
    return {
        "input_tokens": prompt, "output_tokens": completion,
        "cached_input_tokens": cached, "reasoning_tokens": reasoning,
        "estimated_cost_nano_usd": int(nanos.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
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

    def event(self, kind, event_id, **data):
        event = {"version": 1, "step_id": "completion:0", "kind": kind, "id": event_id, **data}
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

    def stream(self, *, model: AgentModel, messages: list[dict], api_key: str):
        payload = {
            "model": model.model, "messages": messages,
            "max_tokens": model.max_output_tokens,
            "stream": True, "stream_options": {"include_usage": True},
            "provider": {"zdr": True, "allow_fallbacks": False},
        }
        payload.update({k: v for k, v in model.request_config.items() if k != "provider"})
        payload["provider"].update(model.request_config.get("provider") or {})
        payload["provider"].update(zdr=True, allow_fallbacks=False)
        # No web-search plugin, tools, judge, memory compressor or retries.
        with bind_analysis_budget(AnalysisBudget(seconds=180, max_calls=1)):
            lines = cancellable_sse_lines(
                OPENROUTER_CHAT_COMPLETIONS_URL, json=payload,
                headers=openrouter_headers(api_key),
            )
            try:
                for _, encoded in _sse_pairs(lines):
                    if encoded.strip() == "[DONE]":
                        break
                    data = json.loads(encoded)
                    if not isinstance(data, dict):
                        raise ValueError("Invalid provider event")
                    self.generation_id = str(data.get("id") or self.generation_id)[:200]
                    usage = measured_usage(data.get("usage"), model)
                    if usage is not None:
                        self.usage = usage
                        yield self.event("usage", "usage", usage=usage)
                    if data.get("error"):
                        raise RuntimeError("Agent provider failed")
                    for choice in data.get("choices") or []:
                        delta = choice.get("delta") or {}
                        if delta.get("tool_calls"):
                            raise RuntimeError("Unexpected tool call")
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
                if self.finish_reason not in {"stop", "length"} or not self.text.strip():
                    raise RuntimeError("Agent stream ended without a completed answer")
            finally:
                lines.close()
