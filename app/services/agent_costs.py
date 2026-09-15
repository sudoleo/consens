"""Admission reservations and measured totals; never used to debit an account."""
import json
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


def search_cost_nanos(model):
    from app.services.agent_tools import uses_native_search
    return (provider_cost_nanos(model.web_search_usd_per_request)
            if uses_native_search(model) else 7_000_000)


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

    def reserve(self, model, messages, tools=(), *, native_searches=0):
        from app.services.agent_tools import uses_native_search
        inputs = input_bound(messages, tools)
        if inputs + model.max_output_tokens > model.context_length:
            raise AnalysisBudgetExceeded("The selected model's context limit was reached.")
        # Native search injects provider-owned context that we cannot count
        # before dispatch. Reserve its entire model window, then reconcile.
        if native_searches and uses_native_search(model):
            inputs = model.context_length - model.max_output_tokens
        elif native_searches:
            # Exa: five results with 2,000 characters each. Include worst-case
            # UTF-8, URL and argument overhead in every hidden continuation.
            inputs += native_searches * (5 * (2000 * 4 + 3000) + 4096)
            if inputs + model.max_output_tokens > model.context_length:
                raise AnalysisBudgetExceeded("The selected model's search context limit was reached.")
        # Account conservatively for native model continuations hidden behind
        # the provider API. Do not advertise max_results as a native input cap.
        segments = native_searches + 1 if native_searches else 1
        tokens = (inputs + model.max_output_tokens) * segments
        cost = int(((inputs * max(Decimal(model.input_usd_per_million), Decimal(model.cache_read_usd_per_million),
                                 Decimal(model.cache_write_usd_per_million or model.input_usd_per_million))
                     + model.max_output_tokens * Decimal(model.output_usd_per_million)) * 1000
                    ).quantize(Decimal("1"), rounding=ROUND_CEILING)) * segments
        if native_searches:
            cost += native_searches * (search_cost_nanos(model) or 10_000_000)
        if (self.calls >= self.policy.max_calls or self.tokens + tokens > self.policy.max_tokens
                or self.cost + cost > self.policy.max_cost_nano_usd):
            raise AnalysisBudgetExceeded("The agent's token or simulated cost budget was reached.")
        self.tokens += tokens
        self.cost += cost
        self.calls += 1
        return tokens, cost

    def reconcile(self, reservation, usage):
        self.usages.append(usage)
        if usage is not None and usage.get("complete", True):
            self.tokens += usage["input_tokens"] + usage["output_tokens"] - reservation[0]
            self.cost += usage["estimated_cost_nano_usd"] - reservation[1]
        # Missing usage keeps the full reservation. Never guess a zero cost.

    def check(self):
        if self.tokens > self.policy.max_tokens or self.cost > self.policy.max_cost_nano_usd:
            raise AnalysisBudgetExceeded("The provider reported usage beyond the agent's budget.")

    def total(self):
        known = [usage for usage in self.usages if usage is not None]
        measured = [usage for usage in known if usage.get("input_tokens") is not None]
        if not known:
            return None
        return {**{field: (sum(u[field] for u in known if u.get(field) is not None)
                          if any(u.get(field) is not None for u in known) else None) for field in USAGE_FIELDS},
                "web_search_requests": (sum(usage.get("web_search_requests") or 0 for usage in known)
                    if any(u.get("web_search_requests") is not None for u in known) else None),
                "complete": len(measured) == len(self.usages) and all(u.get("complete", True) for u in known),
                "measured_calls": len(measured), "unmetered_calls": len(self.usages) - len(measured),
                "cost_source": "provider" if all(u.get("cost_source") == "provider" for u in known)
                    else "catalog" if all(u.get("cost_source", "catalog") == "catalog" for u in known) else "mixed",
                "source": "provider", "billing_mode": "simulation", "currency": "USD"}
