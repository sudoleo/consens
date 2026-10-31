"""Transport-level cost metering for the Consensus pipeline.

Every OpenRouter request that leaves the shared transport (streamed answers,
streamed and non-streamed synthesis, judges, repairs) reports its provider
usage to the meter bound to the current context. Callers above the transport
never see usage; they only bind a meter around one logical operation and read
its totals afterwards (``app.services.run_metering`` books them).

Charging follows the allowance (agent_quota, micro-euros since 2026-10-31):
the call's dollar cost as OpenRouter reports it in ``usage.cost`` (cache,
reasoning and web search included), else its tokens at the model's catalog
price (``agent_model_metadata.pricing``, FALLBACK_PRICES for a model the
catalog does not know). Tokens are still counted for the logs.

A started call without final usage (stream cut, timeout, client gone) is
charged the same bounded estimate as an Agent call: half of the cost of the
call's bound (input estimate + output cap) at the model's price.
A request the provider rejected with an HTTP status never started and costs
nothing; so does one that provably never reached the provider (connect
failure, cancellation before dispatch; see ``provider_dispatch``). Without a bound meter (Watch, Topics, Agent's own client) every hook
is a no-op.

Meters propagate like other contextvars: threads started through
``contextvars.copy_context().run`` (coverage judge, provider fan-out) report
into the same meter.
"""

from __future__ import annotations

import json
import math
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal, InvalidOperation, ROUND_CEILING

# Same share as agent_quota.UNKNOWN_ESTIMATE_FRACTION (kept local so the
# transport does not import the ledger).
UNKNOWN_ESTIMATE_FRACTION = 0.5
# Dollars per token for a model the catalog does not know: about the dearest
# of the pipeline's models, so an unknown one is never charged too little.
FALLBACK_PRICES = {"prompt": "0.000005", "completion": "0.000025"}

_current = ContextVar("consensio_usage_meter", default=None)


def _nanos(value) -> int | None:
    """A dollar amount (``usage.cost``) as whole nano-USD, or None."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or not 0 <= amount <= 1_000_000:
        return None
    return int((amount * 1_000_000_000).to_integral_value(rounding=ROUND_CEILING))


def normalize_usage(raw) -> dict | None:
    """OpenRouter/OpenAI usage -> {input_tokens, output_tokens,
    reasoning_tokens, cached_input_tokens, cost_nano_usd (None if unnamed)}."""
    if not isinstance(raw, dict):
        return None
    prompt = raw.get("prompt_tokens", raw.get("input_tokens"))
    completion = raw.get("completion_tokens", raw.get("output_tokens"))
    if type(prompt) is not int or type(completion) is not int or prompt < 0 or completion < 0:
        return None
    details = raw.get("completion_tokens_details") or raw.get("output_tokens_details") or {}
    reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else None
    prompt_details = raw.get("prompt_tokens_details") or raw.get("input_tokens_details") or {}
    cached = prompt_details.get("cached_tokens") if isinstance(prompt_details, dict) else None
    return {"input_tokens": prompt, "output_tokens": completion,
            "reasoning_tokens": reasoning if type(reasoning) is int and reasoning >= 0 else 0,
            "cached_input_tokens": cached if type(cached) is int and 0 <= cached <= prompt else 0,
            "cost_nano_usd": _nanos(raw.get("cost"))}


def _prices(model) -> tuple[Decimal, Decimal, Decimal]:
    """(input, cached input, output) in nano-USD per token of ``model``."""
    pricing = None
    if isinstance(model, str) and model:
        try:
            from app.services.llm.agent_model_metadata import pricing as catalog_pricing
            pricing = catalog_pricing(model)
        except Exception:
            # Metadata is a pricing aid only; never fail a paid call for it.
            pricing = None
    pricing = pricing or FALLBACK_PRICES

    def price(key, default):
        try:
            value = Decimal(str(pricing.get(key, default)))
            return value * 1_000_000_000 if value.is_finite() and value >= 0 else None
        except (InvalidOperation, ValueError):
            return None

    prompt = price("prompt", FALLBACK_PRICES["prompt"])
    completion = price("completion", FALLBACK_PRICES["completion"])
    if prompt is None or completion is None:
        prompt, completion = (Decimal(FALLBACK_PRICES[key]) * 1_000_000_000 for key in ("prompt", "completion"))
    cached = price("input_cache_read", pricing.get("prompt", FALLBACK_PRICES["prompt"]))
    return prompt, prompt if cached is None else cached, completion


def usage_cost(usage: dict, model=None) -> int:
    """Nano-USD of a measured call: its reported cost, else catalog price."""
    if usage.get("cost_nano_usd") is not None:
        return usage["cost_nano_usd"]
    prompt, cached, completion = _prices(model)
    hits = usage.get("cached_input_tokens") or 0
    total = (usage["input_tokens"] - hits) * prompt + hits * cached + usage["output_tokens"] * completion
    return int(total.to_integral_value(rounding=ROUND_CEILING))


def call_bound(payload) -> int:
    """Upper bound of one request: estimated input plus the output cap."""
    return sum(_bound_parts(payload))


def _bound_parts(payload) -> tuple[int, int]:
    if not isinstance(payload, dict):
        return 0, 0
    try:
        from app.services.agent_tokens import input_estimate
        prompt = input_estimate(payload.get("messages") or [],
                                request_config={"response_format": payload.get("response_format")})
    except Exception:
        # The tokenizer is an estimate aid only; never fail a paid call for it.
        prompt = len(json.dumps(payload.get("messages") or [], default=str)) // 3
    output = payload.get("max_tokens") or payload.get("max_output_tokens") or 0
    return int(prompt), (int(output) if type(output) is int and output > 0 else 0)


def call_bound_cost(payload) -> int:
    """Nano-USD of the call's bound at its model's price (fresh input)."""
    prompt_tokens, output_tokens = _bound_parts(payload)
    prompt, _, completion = _prices(payload.get("model") if isinstance(payload, dict) else None)
    return int((prompt_tokens * prompt + output_tokens * completion).to_integral_value(rounding=ROUND_CEILING))


class MeteredCall:
    def __init__(self, meter: "UsageMeter", bound: int, bound_cost: int = 0, model=None):
        self._meter = meter
        self.bound = max(0, int(bound))
        self.bound_cost = max(0, int(bound_cost))
        self.model = model
        self.usage: dict | None = None
        self.closed = False

    def observe(self, raw_usage) -> None:
        usage = normalize_usage(raw_usage)
        if usage is not None:
            self.usage = usage

    def finish(self, raw_usage=None) -> None:
        if raw_usage is not None:
            self.observe(raw_usage)
        self._meter._settle(self, started=True)

    def rejected(self) -> None:
        """No provider work: an HTTP status rejection or a request that
        provably never reached the provider (``provider_dispatch``)."""
        self._meter._settle(self, started=False)


class _NullCall:
    bound = 0
    bound_cost = 0
    usage = None

    def observe(self, raw_usage) -> None:
        pass

    def finish(self, raw_usage=None) -> None:
        pass

    def rejected(self) -> None:
        pass


NULL_CALL = _NullCall()


class UsageMeter:
    """Thread-safe cost and token totals of one logical operation."""

    def __init__(self):
        self._lock = threading.Lock()
        self._open: set[MeteredCall] = set()
        self.closed = False
        self.calls = 0
        self.missing_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.reasoning_tokens = 0
        self.estimated_tokens = 0
        # Nano-USD: measured (reported cost or catalog price) and estimated.
        self.cost_nano_usd = 0
        self.estimated_nano_usd = 0

    def start(self, payload) -> MeteredCall | _NullCall:
        with self._lock:
            if self.closed:
                # Late work (e.g. an advisory check after booking) is not part
                # of this operation's bill.
                return NULL_CALL
            model = payload.get("model") if isinstance(payload, dict) else None
            call = MeteredCall(self, call_bound(payload), call_bound_cost(payload), model)
            self._open.add(call)
            self.calls += 1
            return call

    def record(self, usage: dict) -> None:
        """Book a synthetic, already measured call (MOCK_LLM fixtures)."""
        call = self.start({})
        if isinstance(call, MeteredCall):
            call.finish(usage)

    def _settle(self, call: MeteredCall, *, started: bool) -> None:
        with self._lock:
            if call.closed:
                return
            call.closed = True
            self._open.discard(call)
            if call.usage is not None:
                self.input_tokens += call.usage["input_tokens"]
                self.output_tokens += call.usage["output_tokens"]
                self.reasoning_tokens += call.usage["reasoning_tokens"]
                self.cost_nano_usd += usage_cost(call.usage, call.model)
            elif started:
                self.missing_calls += 1
                self.estimated_tokens += math.ceil(call.bound * UNKNOWN_ESTIMATE_FRACTION)
                self.estimated_nano_usd += math.ceil(call.bound_cost * UNKNOWN_ESTIMATE_FRACTION)

    @property
    def measured_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def close(self) -> dict:
        """Settle calls that never reported and freeze the totals."""
        with self._lock:
            pending = list(self._open)
        for call in pending:
            self._settle(call, started=True)
        with self._lock:
            self.closed = True
            return self.totals()

    def totals(self) -> dict:
        """``measured`` and ``estimated`` in the allowance's micro-euros."""
        from app.services.agent_budget_config import micro_eur
        return {"measured": micro_eur(self.cost_nano_usd),
                "estimated": micro_eur(self.estimated_nano_usd),
                "cost_nano_usd": self.cost_nano_usd, "estimated_nano_usd": self.estimated_nano_usd,
                "tokens": self.input_tokens + self.output_tokens, "estimated_tokens": self.estimated_tokens,
                "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "reasoning_tokens": self.reasoning_tokens,
                "calls": self.calls, "missing_calls": self.missing_calls}


def current_meter() -> UsageMeter | None:
    return _current.get()


def start_call(payload) -> MeteredCall | _NullCall:
    meter = _current.get()
    return meter.start(payload) if meter is not None else NULL_CALL


def record_mock_call(prompt_text: str, output_text: str) -> None:
    """MOCK_LLM: a plausible measured call so local runs move the account."""
    meter = _current.get()
    if meter is not None:
        prompt = max(1, len(str(prompt_text or "")) // 4) + 400
        completion = max(1, len(str(output_text or "")) // 4)
        # At a dollar per million tokens, so local runs move the account.
        meter.record({"prompt_tokens": prompt, "completion_tokens": completion,
                      "cost": (prompt + completion) / 1_000_000})


@contextmanager
def bind_usage_meter(meter: UsageMeter | None):
    token = _current.set(meter)
    try:
        yield meter
    finally:
        try:
            _current.reset(token)
        except ValueError:
            # A generator finalized from another context: that context never
            # saw the binding, so there is nothing left to undo.
            pass
