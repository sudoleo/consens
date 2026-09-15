"""Bounded, process-local backpressure for a rate-limited model/API key.

No automatic replay of a possibly paid generation. Routing fallbacks are owned
by OpenRouter, as in Consensus. This gate prevents immediate repeated requests
while honoring Retry-After; other models remain usable.
"""
from collections import OrderedDict
from hashlib import sha256
import math
from threading import Lock
from time import monotonic


class AgentProviderCooldown(Exception):
    def __init__(self, seconds):
        self.retry_after = seconds
        super().__init__(f"This model is temporarily rate limited. Wait {seconds} seconds or choose another model.")


class ProviderCooldowns:
    def __init__(self, *, clock=monotonic):
        self.clock = clock
        self.lock = Lock()
        self.entries = OrderedDict()

    def key(self, model, api_key):
        return sha256(api_key.encode()).digest(), model.model

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


def provider_failure(error):
    """Safe user-facing error codes/messages, never the provider's raw body."""
    status = getattr(error, "status_code", None)
    if status == 429:
        seconds = getattr(error, "retry_after", None) or 30
        return {"code": "provider_rate_limited", "retry_after": seconds,
                "error": str(AgentProviderCooldown(seconds))}
    if status in {404, 503}:
        return {"code": "provider_unavailable", "error": "No provider is currently available for this model. Choose another model or try again later."}
    if status in {401, 402, 403}:
        return {"code": "provider_access", "error": "The model provider rejected access. The server API key, credits or provider permissions need to be checked."}
    return {"code": "provider_error", "error": "The model provider could not complete the response. Try a new message later."}
