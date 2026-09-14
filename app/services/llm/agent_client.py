"""One text completion, with provider-reported usage and no implicit tools.

The transport has no chat, billing or consensus responsibilities. Future tool
steps can use the same event/receipt contract without changing their callers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
import json
import os

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

    def snapshot(self):
        return asdict(self)


def agent_model() -> AgentModel:
    """Operator configuration is explicit; never silently substitute a model."""
    defaults = AgentModel()
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
    return AgentModel(**values)


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

    def stream(self, *, model: AgentModel, messages: list[dict], api_key: str):
        payload = {
            "model": model.model, "messages": messages,
            "max_tokens": model.max_output_tokens,
            "stream": True, "stream_options": {"include_usage": True},
            "provider": {"zdr": True, "allow_fallbacks": False},
        }
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
                    if data.get("error"):
                        raise RuntimeError("Agent provider failed")
                    for choice in data.get("choices") or []:
                        delta = choice.get("delta") or {}
                        if delta.get("tool_calls"):
                            raise RuntimeError("Unexpected tool call")
                        chunk = delta.get("content")
                        if isinstance(chunk, str) and chunk:
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
