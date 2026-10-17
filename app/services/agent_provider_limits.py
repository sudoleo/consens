"""Bounded, process-local backpressure for a rate-limited model/API key.

No automatic replay of a possibly paid generation. Routing fallbacks are owned
by OpenRouter, as in Consensus. This gate prevents immediate repeated requests
while honoring Retry-After; other models remain usable.
"""
from collections import OrderedDict
from hashlib import sha256
import json
import math
from threading import Lock
from time import monotonic


class AgentProviderCooldown(Exception):
    def __init__(self, seconds):
        self.retry_after = seconds
        super().__init__(f"This model is busy at its provider right now. It is available again in about {seconds} seconds, or you can choose another model.")


class ProviderCooldowns:
    def __init__(self, *, clock=monotonic):
        self.clock = clock
        self.lock = Lock()
        self.entries = OrderedDict()

    def key(self, model, api_key):
        # The route is part of the key: a chat with Google data runs the same
        # model only on zero-retention endpoints, so its 429 says nothing about
        # the fastest route every other chat takes (openrouter_contract).
        provider = (getattr(model, "request_config", None) or {}).get("provider") or {}
        return sha256(api_key.encode()).digest(), model.model, json.dumps(provider, sort_keys=True)

    def check(self, model, api_key):
        with self.lock:
            key = self.key(model, api_key)
            remaining = math.ceil(self.entries.get(key, 0) - self.clock())
            if remaining > 0:
                raise AgentProviderCooldown(remaining)
            self.entries.pop(key, None)

    def record(self, model, api_key, error):
        if getattr(error, "status_code", None) != 429:
            return
        seconds = getattr(error, "retry_after", None) or 30
        with self.lock:
            key = self.key(model, api_key)
            self.entries[key] = max(self.entries.get(key, 0), self.clock() + seconds)
            self.entries.move_to_end(key)
            while len(self.entries) > 256:
                self.entries.popitem(last=False)


provider_cooldowns = ProviderCooldowns()


class ModelOutputLimit(RuntimeError):
    """The model used its whole output allowance before any usable answer.

    A turn that ends this way says what to do instead (TURN_OUTPUT_LIMIT); a
    comparison answer keeps the plain cause (COMPARISON_FAILURES)."""
    def __init__(self, message=None):
        super().__init__(message or "This model used its whole output allowance before it finished an answer.")


class ModelEmptyAnswer(ModelOutputLimit):
    """The model reasoned (and maybe searched), then stopped without a word.

    Unlike a real output limit this is chance: gpt-oss-120b did it once in
    thirteen identical comparison calls (2026-10-15). A comparison answer
    tries once more (AgentComparison.call); everything else treats it as an
    output limit."""
    def __init__(self, message=None):
        super().__init__(message or "The model ended without writing an answer.")


# The chat model reasoned through its allowance, also on its lighter retry:
# the user can change the reasoning level, the app cannot do more by itself.
TURN_OUTPUT_LIMIT = ("The chat model used its whole output allowance on reasoning before it could finish. "
                     "Choose a lower reasoning level or another chat model and send the message again.")


class AgentRunInterrupted(RuntimeError):
    """Content-free infrastructure failure, distinct from a user cancellation."""


def agent_failure(error):
    """The same safe failure is saved in history and sent over the live stream."""
    from app.services.agent_files import FileUnavailable
    from app.services.agent_quota import AgentTokenBudgetExceeded
    from app.services.agent_runs import ConversationTooLong
    from app.services.agent_runtime import AgentCapacityExceeded
    from app.services.chat_store import TurnStatusConflict
    from app.services.google_connections import GoogleError
    from app.services.llm.provider_runtime import AnalysisBudgetExceeded
    import httpx
    # Our own messages, written for the user: sending the same message again
    # would fail the same way, so none of them says "try again".
    if isinstance(error, ConversationTooLong):
        return {"code": "conversation_too_long", "error": str(error)}
    if isinstance(error, FileUnavailable):
        return {"code": "file_unavailable", "error": str(error)}
    if isinstance(error, GoogleError):
        return {"code": "google_error", "error": str(error)}
    if isinstance(error, AgentTokenBudgetExceeded):
        return {"code": error.code, "error": str(error),
                "required_tokens": error.required, "available_tokens": error.remaining}
    if isinstance(error, AgentRunInterrupted):
        return {"code": "run_interrupted", "error": str(error)}
    if isinstance(error, (AgentCapacityExceeded, TurnStatusConflict)):
        return {"code": "run_state_conflict", "error": str(error)}
    if isinstance(error, ModelEmptyAnswer):
        return {"code": "empty_answer", "error": str(error)}
    if isinstance(error, ModelOutputLimit):
        return {"code": "output_limit", "error": str(error)}
    if isinstance(error, AgentProviderCooldown):
        return {"code": "provider_rate_limited", "error": str(error), "retry_after": error.retry_after}
    if isinstance(error, AnalysisBudgetExceeded):
        return {"code": "model_context_limit" if "context" in str(error).lower() else "run_limit", "error": str(error)}
    if isinstance(error, (httpx.TimeoutException, TimeoutError)):
        return {"code": "provider_timeout", "error": "The model provider stopped responding. Everything received up to that point has been saved."}
    return provider_failure(error)


def provider_failure(error):
    """Safe user-facing error codes/messages, never the provider's raw body."""
    status = getattr(error, "status_code", None)
    if status == 429:
        seconds = getattr(error, "retry_after", None) or 30
        return {"code": "provider_rate_limited", "retry_after": seconds,
                "error": str(AgentProviderCooldown(seconds))}
    if status in {404, 503}:
        return {"code": "provider_unavailable", "error": "This model is currently unavailable at its provider. Choose another model or try again later."}
    if status in {401, 402, 403}:
        return {"code": "provider_access", "error": "The model provider declined the request. This needs a check of the provider settings on our side."}
    if status in {400, 413, 422}:
        # The request itself was refused (too large, an unsupported file or
        # parameter): the same request again fails the same way.
        return {"code": "provider_rejected", "error": "The model provider rejected this request. Try another chat model, or start a new chat if this one is long or has large files."}
    return {"code": "provider_error", "error": "The model provider could not finish this request. Trying again in a moment usually works."}
