"""Transport-level token metering for the Consensus pipeline.

Every OpenRouter request that leaves the shared transport (streamed answers,
streamed and non-streamed synthesis, judges, repairs) reports its provider
usage to the meter bound to the current context. Callers above the transport
never see usage; they only bind a meter around one logical operation and read
its totals afterwards (``app.services.run_metering`` books them).

Counting follows the token ledger: ``prompt_tokens + completion_tokens``;
reasoning is part of the completion, cache reads are part of the prompt.

A started call without final usage (stream cut, timeout, client gone) is
charged the same bounded estimate as an Agent call: the provisional lower
bound, but at least half of the call's bound (input estimate + output cap).
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

# Same share as agent_quota.UNKNOWN_ESTIMATE_FRACTION (kept local so the
# transport does not import the ledger).
UNKNOWN_ESTIMATE_FRACTION = 0.5

_current = ContextVar("consensio_usage_meter", default=None)


def normalize_usage(raw) -> dict | None:
    """OpenRouter/OpenAI usage -> {input_tokens, output_tokens, reasoning_tokens}."""
    if not isinstance(raw, dict):
        return None
    prompt = raw.get("prompt_tokens", raw.get("input_tokens"))
    completion = raw.get("completion_tokens", raw.get("output_tokens"))
    if type(prompt) is not int or type(completion) is not int or prompt < 0 or completion < 0:
        return None
    details = raw.get("completion_tokens_details") or raw.get("output_tokens_details") or {}
    reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else None
    return {"input_tokens": prompt, "output_tokens": completion,
            "reasoning_tokens": reasoning if type(reasoning) is int and reasoning >= 0 else 0}


def call_bound(payload) -> int:
    """Upper bound of one request: estimated input plus the output cap."""
    if not isinstance(payload, dict):
        return 0
    try:
        from app.services.agent_tokens import input_estimate
        prompt = input_estimate(payload.get("messages") or [],
                                request_config={"response_format": payload.get("response_format")})
    except Exception:
        # The tokenizer is an estimate aid only; never fail a paid call for it.
        prompt = len(json.dumps(payload.get("messages") or [], default=str)) // 3
    output = payload.get("max_tokens") or payload.get("max_output_tokens") or 0
    return int(prompt) + (int(output) if type(output) is int and output > 0 else 0)


class MeteredCall:
    def __init__(self, meter: "UsageMeter", bound: int):
        self._meter = meter
        self.bound = max(0, int(bound))
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
    usage = None

    def observe(self, raw_usage) -> None:
        pass

    def finish(self, raw_usage=None) -> None:
        pass

    def rejected(self) -> None:
        pass


NULL_CALL = _NullCall()


class UsageMeter:
    """Thread-safe token totals of one logical operation."""

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

    def start(self, payload) -> MeteredCall | _NullCall:
        with self._lock:
            if self.closed:
                # Late work (e.g. an advisory check after booking) is not part
                # of this operation's bill.
                return NULL_CALL
            call = MeteredCall(self, call_bound(payload))
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
            elif started:
                self.missing_calls += 1
                self.estimated_tokens += math.ceil(call.bound * UNKNOWN_ESTIMATE_FRACTION)

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
        return {"measured": self.input_tokens + self.output_tokens,
                "estimated": self.estimated_tokens,
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
        meter.record({"prompt_tokens": max(1, len(str(prompt_text or "")) // 4) + 400,
                      "completion_tokens": max(1, len(str(output_text or "")) // 4)})


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
