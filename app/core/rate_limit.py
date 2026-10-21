import hashlib
import math
import os
import threading
import time
from collections import defaultdict, deque

from slowapi import Limiter
from slowapi.util import get_remote_address


def client_ip_key(request):
    """Client-IP hinter Render/Cloudflare für IP-basierte Rate-Limits.

    www.consens.io ist ein CNAME auf typeonai.onrender.com; davor sitzt
    Renders Cloudflare. Cloudflare setzt ``CF-Connecting-IP`` selbst auf die
    Adresse, die die Verbindung geöffnet hat, und überschreibt einen vom
    Client mitgeschickten Wert. Das ist der einzige Header, dem wir trauen.

    ``X-Forwarded-For`` dagegen hängt Render nur an: ein vom Client gesetzter
    Eintrag bleibt vorn stehen. Live belegt am 2026-10-15: 36 Abrufe mit
    wechselnder gefälschter XFF-Adresse liefen alle durch ein 30/min-Limit,
    ohne Fälschung kam ab dem 31. ein 429. Deshalb gilt XFF nur noch als
    Rückfall ohne Cloudflare (lokale Server, E2E-Proxys); lokal ohne Header
    zählt ``request.client.host``.
    """
    connecting = request.headers.get("cf-connecting-ip", "").strip()
    if connecting:
        return connecting
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        client_ip = forwarded.split(",", 1)[0].strip()
        if client_ip:
            return client_ip
    return get_remote_address(request)


def api_key_rate_key(request):
    """Stable non-secret limiter key for one public API credential.

    Invalid or missing credentials fall back to the client IP so random-key
    attacks cannot manufacture an unlimited number of limiter buckets.
    """
    raw = request.headers.get("x-api-key", "").strip()
    if not raw.startswith("cns_live_"):
        return "ip:" + client_ip_key(request)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return "api-key:" + digest


class ApiUidRateLimitExceeded(Exception):
    pass


class ApiUidRateLimiter:
    """Small in-process UID limiter applied after API-key authentication."""

    # Above this many buckets a check sweeps out the empty ones, at most once
    # per SWEEP_INTERVAL_SECONDS so a crowd of fresh buckets is no full scan
    # on every call.
    MAX_KEYS = 4096
    SWEEP_INTERVAL_SECONDS = 5.0

    def __init__(self, *, enabled: bool = True):
        self._enabled = enabled
        self._events = defaultdict(deque)
        # Each bucket's own window: a sweep must never shorten an hourly
        # limit to the minute of whoever triggered it.
        self._windows = {}
        self._next_sweep = 0.0
        self._lock = threading.Lock()

    def reset(self):
        """Alle Zaehler verwerfen. Fuer Tests: der Limiter ist ein
        Prozess-Singleton, sonst schleppt jeder Testfall die Requests des
        vorherigen mit und die Suite wird reihenfolgeabhaengig."""
        with self._lock:
            self._events.clear()
            self._windows.clear()
            self._next_sweep = 0.0

    def _sweep(self, now: float) -> None:
        for stored_key, stored_events in list(self._events.items()):
            cutoff = now - self._windows.get(stored_key, 0)
            while stored_events and stored_events[0] <= cutoff:
                stored_events.popleft()
            if not stored_events:
                self._events.pop(stored_key, None)
                self._windows.pop(stored_key, None)

    def check(self, uid: str, operation: str, limit: int, *, window_seconds: int = 60):
        if not self._enabled:
            return
        now = time.monotonic()
        key = (str(uid), str(operation))
        cutoff = now - window_seconds
        with self._lock:
            if len(self._events) > self.MAX_KEYS and now >= self._next_sweep:
                self._sweep(now)
                self._next_sweep = now + self.SWEEP_INTERVAL_SECONDS
            self._windows[key] = max(window_seconds, self._windows.get(key, 0))
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                raise ApiUidRateLimitExceeded("API UID rate limit exceeded")
            events.append(now)


_rate_limits_enabled = os.environ.get("DISABLE_RATE_LIMIT") != "1"
api_uid_limiter = ApiUidRateLimiter(enabled=_rate_limits_enabled)


# DISABLE_RATE_LIMIT=1 nur fuer die lokale E2E-Suite: die Tests feuern
# mehrere /ask_*- und /consensus-Requests pro Minute von derselben IP und
# wuerden sonst in 429er laufen. In Produktion nie setzen.
limiter = Limiter(key_func=client_ip_key, enabled=_rate_limits_enabled)


# What a person reads when a limit holds them back (Audit H6): no "10 per 1
# minute", no status code, and never an upgrade offer -- the clients tell a
# throttle (code "rate_limited") apart from a plan limit ("limit_reached").
RATE_LIMITED_CODE = "rate_limited"


def retry_after_seconds(request, exc) -> int:
    """Seconds until the limit that was hit lets this caller through again."""
    try:
        item, keys = request.state.view_rate_limit
        reset_at, _remaining = limiter.limiter.get_window_stats(item, *keys)
        return max(1, min(int(math.ceil(reset_at - time.time())), int(item.get_expiry())))
    except Exception:
        try:
            return max(1, int(exc.limit.limit.get_expiry()))
        except Exception:
            return 60


def rate_limit_message(retry_after: int) -> str:
    if retry_after <= 90:
        wait = "Please wait a moment and try again."
    elif retry_after <= 90 * 60:
        wait = f"Please try again in {max(2, round(retry_after / 60))} minutes."
    else:
        wait = "Please try again later."
    return "Too many requests in a short time. " + wait
