"""Admission reservations and measured totals; never used to debit an account."""
import threading
from dataclasses import replace
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


# Expected input per search round: about the mean of the families (measured: OpenAI's own search up
# to ~11k tokens, Exa ~2.5k, Anthropic ~2k, Google grounding ~0, billed per request).
SEARCH_ROUND_TOKENS = 6_000
# Until the run has measured calls of its kind on its model: about one routing step with reasoning
# (measured on Sonnet 5.5: about 3,900 tokens).
OUTPUT_START_TOKENS = 4_096


def search_cost_nanos(model):
    # The catalog prices the publishers' own search; Exa otherwise.
    return provider_cost_nanos(model.web_search_usd_per_request) or 7_000_000


# A page read adds at most its max_content_tokens to the reading continuation's input; the cap is
# approximate, hence the margin. Exa's $0.001 per page is outside the cost OpenRouter reports.
FETCH_TOKEN_MARGIN = 1.25
FETCH_COST_NANOS = 1_000_000


def fetch_bounds(tools):
    """(pages, input tokens) the page-reading tools of one call may add."""
    pages = tokens = 0
    for tool in tools or ():
        if isinstance(tool, dict) and tool.get("type") == "openrouter:web_fetch":
            parameters = tool.get("parameters") or {}
            uses = int(parameters.get("max_uses") or 1)
            pages += uses
            tokens += int(uses * int(parameters.get("max_content_tokens") or 0) * FETCH_TOKEN_MARGIN)
    return pages, tokens


def _nanos(value):
    return int((value * 1000).quantize(Decimal("1"), rounding=ROUND_CEILING))


def _mean(values):
    return -(-sum(values) // len(values))


class RunCosts:
    """What one run's calls are expected to cost, and what they cost. A call is admitted at its
    ``estimate``; the expectation learns from the run's receipts: the prefix the provider cached
    after the session's last call is priced as a cache read, output and search rounds are the means
    its kind measured on that model. A call dearer than expected may leave the account a little
    below zero; the next admission then fails."""

    def __init__(self):
        from app.services.agent_tokens import TokenMemo
        self.tokens = 0
        self.cost = 0
        self.calls = 0
        self.usages = []
        self.memo = TokenMemo()
        # session -> input tokens its last measured call read from or wrote to the cache.
        self._cached = {}
        # (kind, model) -> measured output tokens and search rounds.
        self._outputs, self._rounds = {}, {}
        self._lock = threading.RLock()

    def inputs(self, messages, tools=(), request_config=None):
        """Estimated input tokens of a request, each message counted once per run."""
        from app.services.agent_tokens import input_estimate
        return input_estimate(messages, tools, request_config, memo=self.memo)

    def fit(self, model, messages, tools=()):
        """``model`` with its output limit within the context window the input leaves: a hard limit
        whatever the allowance."""
        from app.services.agent_tokens import minimum_output
        room = model.context_length - self.inputs(messages, tools, model.request_config)
        if room < minimum_output(model):
            raise AnalysisBudgetExceeded("The selected model's context limit was reached.")
        return model if room >= model.max_output_tokens else replace(model, max_output_tokens=room)

    def rewritten(self, session):
        """The session's conversation changed before its end (summary, compaction, new tools): its
        next call finds no cached prefix."""
        with self._lock:
            self._cached.pop(session, None)

    def release(self, reservation):
        """Roll back admission only when no durable provider claim was made."""
        with self._lock:
            self.tokens -= reservation[0]
            self.cost -= reservation[1]
            self.calls -= 1

    def reserve(self, model, messages, tools=(), *, native_searches=0, session=None, kind="agent"):
        with self._lock:
            tokens, cost = self.estimate(model, messages, tools, native_searches=native_searches, session=session,
                                         kind=kind)
            self.tokens += tokens
            self.cost += cost
            self.calls += 1
            return tokens, cost

    def estimate(self, model, messages, tools=(), *, native_searches=0, session=None, kind="agent"):
        """Expected tokens and cost (nano-USD) of one call. ``session``: the conversation the call
        continues; ``kind``: its sort, for the measured means."""
        from app.services.agent_tokens import minimum_output
        inputs = self.inputs(messages, tools, model.request_config)
        if inputs + minimum_output(model) > model.context_length:
            raise AnalysisBudgetExceeded("The selected model's context limit was reached.")
        with self._lock:
            cached = min(inputs, self._cached.get(session, 0)) if session is not None else 0
            outputs, searched = self._outputs.get((kind, model.model)), self._rounds.get((kind, model.model))
        output = min(model.max_output_tokens, _mean(outputs) if outputs else OUTPUT_START_TOKENS)
        rounds = min(native_searches, _mean(searched) if searched else 1) if native_searches else 0
        pages, fetched = fetch_bounds(tools)
        added = rounds * SEARCH_ROUND_TOKENS + fetched
        # Fresh input at the cache write price where that is dearer (Anthropic).
        fresh = max(Decimal(model.input_usd_per_million), Decimal(model.cache_write_usd_per_million or 0))
        cost = _nanos(cached * Decimal(model.cache_read_usd_per_million) + (inputs - cached + added) * fresh
                      + output * Decimal(model.output_usd_per_million))
        cost += rounds * search_cost_nanos(model) + pages * FETCH_COST_NANOS
        return inputs + added + output, cost

    def reconcile(self, reservation, usage, *, model=None, session=None, kind="agent", searches=0):
        with self._lock:
            self.usages.append(usage)
            tokens, cost = remaining_reservation(reservation, usage)
            self.tokens += tokens - reservation[0]
            self.cost += cost - reservation[1]
            # Missing usage keeps the full reservation, never a guessed zero; nor learn from a call
            # that never reached the model.
            if model is None or not usage or not usage.get("complete", True) or not usage.get("input_tokens"):
                return
            if session is not None:
                self._cached[session] = (usage.get("cached_input_tokens") or 0) + (usage.get("cache_write_tokens") or 0)
            if usage.get("output_tokens") is not None:
                self._outputs.setdefault((kind, model.model), []).append(usage["output_tokens"])
            if searches and type(usage.get("web_search_requests")) is int:
                self._rounds.setdefault((kind, model.model), []).append(min(searches, usage["web_search_requests"]))

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
