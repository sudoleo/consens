"""Admission reservations and measured totals; never used to debit an account."""
import json
import threading
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP

from app.services.llm.provider_runtime import AnalysisBudgetExceeded


USAGE_FIELDS = ("input_tokens", "output_tokens", "cached_input_tokens", "cache_write_tokens", "reasoning_tokens", "estimated_cost_nano_usd")


def token_cost_nanos(model, prompt, completion, cached, written=0):
    nanos = ((prompt - cached - written) * Decimal(model.input_usd_per_million)
             + cached * Decimal(model.cache_read_usd_per_million)
             + written * Decimal(model.cache_write_usd_per_million or model.input_usd_per_million)
             + completion * Decimal(model.output_usd_per_million)) * 1000
    return int(nanos.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def provider_cost_nanos(raw):
    """Total OpenRouter cost includes routing, cache, reasoning and tools."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None
    try:
        value = Decimal(str(raw))
        if value.is_finite() and 0 <= value <= 1_000_000:
            return int((value * 1_000_000_000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        pass
    return None


# Input one search round may add, reserved for every model alike. Measured
# 2026-10-01 per round: OpenAI's own search up to ~11k tokens, Exa (5 x 2,000
# characters) ~2.5k, Anthropic ~2k, Google grounding ~0 (billed per request).
# About three times the largest observation. A soft bound: settlement charges
# the actual usage, so a rare larger round can exceed the daily allowance a little.
SEARCH_INPUT_TOKENS = 32_000


def search_cost_nanos(model):
    # The catalog prices the publishers' own search; Exa otherwise.
    return provider_cost_nanos(model.web_search_usd_per_request) or 7_000_000


def input_bound(messages, tools=()):
    # UTF-8 bytes plus generous protocol/schema overhead, not a tokenizer.
    return len(json.dumps([messages, tools], ensure_ascii=False).encode("utf-8")) + 1024


class RunCosts:
    def __init__(self, policy):
        self.policy = policy
        self.tokens = 0
        self.cost = 0
        self.calls = 0
        self.usages = []
        self._lock = threading.RLock()

    def release(self, reservation):
        """Roll back admission only when no durable provider claim was made."""
        with self._lock:
            self.tokens -= reservation[0]
            self.cost -= reservation[1]
            self.calls -= 1

    def reserve(self, model, messages, tools=(), *, native_searches=0):
        with self._lock:
            return self._reserve(model, messages, tools, native_searches=native_searches)

    def _reserve(self, model, messages, tools=(), *, native_searches=0):
        tokens, cost = self.estimate(model, messages, tools, native_searches=native_searches)
        if not self.policy.account_budget_only and (self.calls >= self.policy.max_calls or self.tokens + tokens > self.policy.max_tokens
                or self.cost + cost > self.policy.max_cost_nano_usd):
            raise AnalysisBudgetExceeded("The agent's token or simulated cost budget was reached.")
        self.tokens += tokens
        self.cost += cost
        self.calls += 1
        return tokens, cost

    def estimate(self, model, messages, tools=(), *, native_searches=0):
        from app.services.agent_tokens import input_estimate
        inputs = (input_estimate(messages, tools, model.request_config) if self.policy.account_budget_only
                  else input_bound(messages, tools))
        initial_inputs = inputs
        if inputs + model.max_output_tokens > model.context_length:
            raise AnalysisBudgetExceeded("The selected model's context limit was reached.")
        if native_searches:
            # A provider can never add more than the window still holds.
            room = model.context_length - model.max_output_tokens - inputs
            if room <= 0:
                raise AnalysisBudgetExceeded("The selected model's search context limit was reached.")
            inputs += min(native_searches * SEARCH_INPUT_TOKENS, room)
        # Account conservatively for native model continuations hidden behind
        # the provider API. Do not advertise max_results as a native input cap.
        segments = native_searches + 1 if native_searches else 1
        total_inputs = inputs * segments
        if self.policy.account_budget_only and native_searches:
            # Search results do not exist in the pre-search generation. Each
            # result enters only its subsequent continuations.
            total_inputs = initial_inputs * segments + (inputs - initial_inputs) * segments // 2
        outputs = model.max_output_tokens * segments
        tokens = total_inputs + outputs
        cost = int(((total_inputs * max(Decimal(model.input_usd_per_million), Decimal(model.cache_read_usd_per_million),
                                 Decimal(model.cache_write_usd_per_million or model.input_usd_per_million))
                     + outputs * Decimal(model.output_usd_per_million)) * 1000
                    ).quantize(Decimal("1"), rounding=ROUND_CEILING))
        if native_searches:
            cost += native_searches * (search_cost_nanos(model) or 10_000_000)
        return tokens, cost

    def reconcile(self, reservation, usage):
        with self._lock:
            self.usages.append(usage)
            tokens, cost = remaining_reservation(reservation, usage)
            self.tokens += tokens - reservation[0]
            self.cost += cost - reservation[1]
        # Missing usage keeps the full reservation. Never guess a zero cost.

    def check(self):
        if not self.policy.account_budget_only and (self.tokens > self.policy.max_tokens or self.cost > self.policy.max_cost_nano_usd):
            raise AnalysisBudgetExceeded("The provider reported usage beyond the agent's budget.")

    def total(self):
        with self._lock:
            return aggregate_usage(self.usages)


def remaining_reservation(reservation, usage):
    tokens, cost = reservation
    if usage is not None:
        if usage.get("complete", True) and usage.get("input_tokens") is not None:
            tokens = usage["input_tokens"] + usage["output_tokens"]
        if usage.get("cost_complete", usage.get("complete", True)) and usage.get("estimated_cost_nano_usd") is not None:
            cost = usage["estimated_cost_nano_usd"]
    return tokens, cost


def _call_counts(usage):
    """(calls, measured calls) of one receipt or of an earlier aggregate."""
    if usage is None:
        return 1, 0
    if "measured_calls" in usage:
        measured = int(usage.get("measured_calls") or 0)
        return measured + int(usage.get("unmetered_calls") or 0), measured
    return 1, int(usage.get("input_tokens") is not None)


def aggregate_usage(usages):
    """Sum receipts. Earlier aggregates compose: they count as all their calls."""
    usages = list(usages)
    known = [usage for usage in usages if usage is not None]
    if not known:
        return None
    counts = [_call_counts(usage) for usage in usages]
    calls = sum(total for total, _ in counts)
    measured = sum(count for _, count in counts)
    return {**{field: (sum(u[field] for u in known if u.get(field) is not None)
                      if any(u.get(field) is not None for u in known) else None) for field in USAGE_FIELDS},
            "web_search_requests": (sum(usage.get("web_search_requests") or 0 for usage in known)
                if any(u.get("web_search_requests") is not None for u in known) else None),
            "complete": measured == calls and all(u.get("complete", True) for u in known),
            "cost_complete": len(known) == len(usages) and all(u.get("cost_complete", u.get("complete", True)) for u in known),
            "measured_calls": measured, "unmetered_calls": calls - measured,
            "cost_source": "provider" if all(u.get("cost_source") == "provider" for u in known)
                else "catalog" if all(u.get("cost_source", "catalog") == "catalog" for u in known) else "mixed",
            "source": "provider", "billing_mode": "simulation", "currency": "USD"}
