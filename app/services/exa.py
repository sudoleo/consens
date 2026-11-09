"""Exa for the agent's own research: its web search (agent_web_search.py) and
the text of a page (agent_read_source.py), asked by the server.

A provider's own search runs inside the model's request and hands its hits
to the model alone: of 101 search steps of GPT-6.1 Terra in prod (2026-10-31
to 11-09) 62 left the app nothing, so neither the reviewers nor read_source
nor the timeline knew what was found, and every search round was another
pass of the model (6.2 s at the median). Asked directly, a search takes 1.3
to 2.9 s, five of them side by side 1.7 s, and every hit is the app's to
show, to review and to read on from (probed 2026-11-09).

What leaves: the search words and the addresses of the pages to read, from
the server, with consens.io's key; nothing of the user's account or browser
(privacy.html). Never in chats with Google data (agent_delegation.py).

One process-wide client: its pool keeps the connection open (a TLS handshake
per search otherwise), ``_SEARCH_PACE`` keeps the searches of all runs within
Exa's limit per team, and after failures that are the service's and not a
request's, ``available`` is False for a while: the messages that start
meanwhile search inside the model's request again (DelegationLoop).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from contextvars import copy_context
import logging
import os
import random
import threading
import time
from urllib.parse import urlsplit

import httpx

from app.services.agent_costs import provider_cost_nanos

KEY_ENV = "EXA_API_KEY"
# Off with AGENT_EXA=0 although a key is set.
ENABLED_ENV = "AGENT_EXA"
SEARCH_URL = "https://api.exa.ai/search"
CONTENTS_URL = "https://api.exa.ai/contents"
# Exa's limit for /search is 10 requests a second per team, over all keys
# (docs.exa.ai/reference/rate-limits, 2026-11-09). Half of it as a burst and
# half as the steady rate never passes it within any second; EXA_SEARCH_QPS
# says so when the team's limit is another.
SEARCH_QPS_ENV = "EXA_SEARCH_QPS"
SEARCH_QPS = 10
# A search answered within 2.9 s in the probe; a page Exa has to fetch first
# takes up to its own fetch timeout (10 s) and a little.
SEARCH_SECONDS = 12.0
PAGE_SECONDS = 20.0
ATTEMPTS = 3
RETRY_SECONDS = .5
RETRY_AFTER_MAX_SECONDS = 3.0
# What a call costs when the answer does not say (``costDollars``): Exa's
# list prices of a search with excerpts and of a page's text.
SEARCH_COST_NANOS = 7_000_000
PAGE_COST_NANOS = 1_000_000
TITLE_CHARS = 200
# The most text of a page Exa gives (``text.maxCharacters``).
PAGE_CHARACTERS_MAX = 5_000_000
# After this many failed calls in a row, or at once when Exa refuses the key
# or the credit is used up, the agent does without Exa for BREAK_SECONDS.
BREAK_FAILURES = 3
BREAK_SECONDS = 300.0

# Failures by what they are: only the service's own count towards the break.
SERVICE_FAILURES = frozenset({"unreachable", "server", "busy", "account"})


class ExaError(Exception):
    """A call Exa did not answer: ``code`` is one of rejected (the request
    itself, HTTP 400), busy (rate limit), account (key refused or credit used
    up), server, unreachable (no answer in time) or unreadable (an answer
    that is no JSON object). ``retry``: another attempt may succeed, after
    ``wait`` seconds."""

    def __init__(self, code, detail="", *, retry=False, wait=RETRY_SECONDS):
        super().__init__(f"{code}{': ' + detail if detail else ''}")
        self.code, self.detail, self.retry, self.wait = code, detail, retry, wait


def configured():
    """A key is set, unless AGENT_EXA=0."""
    return bool(os.environ.get(KEY_ENV, "").strip()) and os.environ.get(ENABLED_ENV, "1").strip() != "0"


class _Pace:
    """A token bucket: ``burst`` requests at once, ``rate`` more per second."""

    def __init__(self, rate, burst):
        self.rate, self.burst = float(rate), float(burst)
        self.tokens, self.at = float(burst), time.monotonic()
        self.lock = threading.Lock()

    def wait(self, deadline):
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(self.burst, self.tokens + (now - self.at) * self.rate)
                self.at = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                pause = (1 - self.tokens) / self.rate
            if now + pause >= deadline:
                raise ExaError("busy", "no free slot in time")
            time.sleep(pause)


def _search_pace():
    try:
        qps = max(2.0, float(os.environ.get(SEARCH_QPS_ENV, "") or SEARCH_QPS))
    except ValueError:
        qps = float(SEARCH_QPS)
    return _Pace(qps / 2, qps / 2)


_lock = threading.Lock()
_client_instance = None
_SEARCH_PACE = None
_failures = 0
_open_until = 0.0


def _client():
    global _client_instance
    with _lock:
        if _client_instance is None:
            _client_instance = httpx.Client(
                trust_env=False, follow_redirects=False,
                limits=httpx.Limits(max_connections=40, max_keepalive_connections=20, keepalive_expiry=60))
        return _client_instance


def _pace():
    global _SEARCH_PACE
    with _lock:
        if _SEARCH_PACE is None:
            _SEARCH_PACE = _search_pace()
        return _SEARCH_PACE


def available():
    """Configured, and not set aside after failures of the service itself."""
    with _lock:
        return configured() and time.monotonic() >= _open_until


def reset():
    """Forget the failures counted so far (tests)."""
    global _failures, _open_until, _SEARCH_PACE
    with _lock:
        _failures, _open_until, _SEARCH_PACE = 0, 0.0, None


def _note(failure=None):
    """Count a call's end towards the break (SERVICE_FAILURES), or reset it."""
    global _failures, _open_until
    with _lock:
        if failure is None:
            _failures = 0
            return
        if failure.code not in SERVICE_FAILURES:
            return
        _failures += 1
        opened = failure.code == "account" or _failures >= BREAK_FAILURES
        if opened:
            _open_until = time.monotonic() + BREAK_SECONDS
    if opened:
        # An error for the key or the credit: nothing heals it but the operator.
        logging.log(logging.ERROR if failure.code == "account" else logging.WARNING,
                    "Exa set aside for %ss code=%s detail=%s", int(BREAK_SECONDS), failure.code, failure.detail[:120])


def _failure(response):
    """The ExaError of an answer that is not 200. Exa's error body is
    {error, tag, requestId}; only the tag and the status are kept."""
    try:
        tag = str((response.json() or {}).get("tag") or "")[:60]
    except (ValueError, AttributeError):
        tag = ""
    status, detail = response.status_code, f"HTTP {response.status_code}{' ' + tag if tag else ''}"
    if status == 429:
        try:
            wait = min(RETRY_AFTER_MAX_SECONDS, max(0.0, float(response.headers.get("retry-after") or 1)))
        except ValueError:
            wait = 1.0
        # Runs that were refused together do not come back together.
        return ExaError("busy", detail, retry=True, wait=wait + random.uniform(0, .3))
    if status in (401, 402, 403):
        return ExaError("account", detail)
    if status >= 500:
        return ExaError("server", detail, retry=True)
    return ExaError("rejected", detail)


def _post(url, body, *, seconds, pace=None):
    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        raise ExaError("account", "no key")
    deadline = time.monotonic() + seconds
    for attempt in range(1, ATTEMPTS + 1):
        try:
            if pace is not None:
                pace.wait(deadline)
            try:
                response = _client().post(url, json=body, headers={"x-api-key": key},
                                          timeout=max(1.0, deadline - time.monotonic()))
            except httpx.HTTPError as exc:
                raise ExaError("unreachable", type(exc).__name__, retry=True) from exc
            if response.status_code != 200:
                raise _failure(response)
            try:
                data = response.json()
            except ValueError as exc:
                raise ExaError("unreadable", "no JSON") from exc
            if not isinstance(data, dict):
                raise ExaError("unreadable", "no object")
        except ExaError as failure:
            if failure.retry and attempt < ATTEMPTS and time.monotonic() + failure.wait < deadline - 1:
                time.sleep(failure.wait)
                continue
            _note(failure)
            raise
        _note()
        return data


def together(calls, check):
    """Run ``calls`` side by side and return, in their order, what each
    returned or the exception it raised. ``check`` is called about ten times
    a second while any of them runs and may raise (the user's Stop, the
    turn's end): the caller then goes on at once, and a request under way
    ends on its own."""
    pool = ThreadPoolExecutor(max(1, len(calls)), thread_name_prefix="agent-exa")

    def run(call):
        try:
            return call()
        except Exception as exc:
            return exc
    try:
        pending = [pool.submit(copy_context().run, run, call) for call in calls]
        while wait(pending, timeout=.1)[1]:
            check()
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return [future.result() for future in pending]


def _web(value):
    """``value`` when it is an http(s) address without credentials, else ""."""
    if not isinstance(value, str) or not 0 < len(value) <= 2048 or any(c.isspace() or ord(c) < 32 for c in value):
        return ""
    try:
        parts = urlsplit(value)
    except ValueError:
        return ""
    return value if parts.scheme in ("http", "https") and parts.hostname and not parts.username and not parts.password else ""


def _line(value, limit):
    return " ".join(str(value or "").split())[:limit]


def _day(value):
    """The date of Exa's ``publishedDate`` (YYYY-MM-DD), or ""."""
    text = str(value or "")[:10]
    return text if len(text) == 10 and text[4] == text[7] == "-" and text.replace("-", "").isdigit() else ""


def _cost(data, fallback):
    cost = provider_cost_nanos((data.get("costDollars") or {}).get("total")
                               if isinstance(data.get("costDollars"), dict) else None)
    return fallback if cost is None else cost


def _notes(data):
    """Exa's ``notices``: what it wants the model to know about the answer."""
    return [_line(note, 300) for note in (data.get("notices") if isinstance(data.get("notices"), list) else [])
            if isinstance(note, str) and note.strip()][:3]


def search(query, *, results, characters, domains=(), without=(), since=""):
    """One web search: {"hits": [{url, title, published?, excerpts}],
    "cost_nanos", "notes"}. ``characters``: of excerpts per hit, chosen by
    Exa for the query. ``domains``: only these sites; ``without``: none of
    these. ``since`` (YYYY-MM-DD): only pages published from that day on.
    Raises ExaError."""
    body = {"query": query, "type": "auto", "numResults": results,
            "contents": {"highlights": {"maxCharacters": characters}}}
    if domains:
        body["includeDomains"] = list(domains)
    if without:
        body["excludeDomains"] = list(without)
    if since:
        body["startPublishedDate"] = f"{since}T00:00:00.000Z"
    data = _post(SEARCH_URL, body, seconds=SEARCH_SECONDS, pace=_pace())
    hits, seen = [], set()
    for item in data.get("results") if isinstance(data.get("results"), list) else []:
        url = _web(item.get("url")) if isinstance(item, dict) else ""
        if not url or url in seen:
            continue
        seen.add(url)
        excerpts = [text.strip() for text in (item.get("highlights") if isinstance(item.get("highlights"), list) else [])
                    if isinstance(text, str) and text.strip()]
        hit = {"url": url, "title": _line(item.get("title"), TITLE_CHARS)}
        if _day(item.get("publishedDate")):
            hit["published"] = _day(item.get("publishedDate"))
        hit["excerpts"] = excerpts
        hits.append(hit)
    return {"hits": hits[:results], "cost_nanos": _cost(data, SEARCH_COST_NANOS), "notes": _notes(data)}


# Exa's reasons for a page it could not give (``statuses[].error.tag``), in
# words for the model; any other tag reads as its HTTP status.
PAGE_FAILURES = {
    "CRAWL_NOT_FOUND": "the page does not exist (HTTP 404)",
    "CRAWL_TIMEOUT": "the page did not answer in time",
    "CRAWL_LIVECRAWL_TIMEOUT": "the page did not answer in time",
    "SOURCE_NOT_AVAILABLE": "the site does not let a reader in",
    "UNSUPPORTED_URL": "this kind of address cannot be read",
}


def page(url, *, characters, fresh=False):
    """The text of one public page, PDFs too: {"status": "completed", "url",
    "title", "text", "published", "stored", "cost_nanos"} or {"status":
    "failed", "error", "cost_nanos"}. Exa answers with its stored copy where
    it has one and fetches the page otherwise; ``fresh`` has it fetched now.
    ``stored``: the answer is the stored copy. Raises ExaError when Exa
    itself does not answer."""
    body = {"urls": [url], "text": {"maxCharacters": min(characters, PAGE_CHARACTERS_MAX)}}
    if fresh:
        body["maxAgeHours"] = 0
    data = _post(CONTENTS_URL, body, seconds=PAGE_SECONDS)
    status = next((item for item in (data.get("statuses") if isinstance(data.get("statuses"), list) else [])
                   if isinstance(item, dict)), {})
    found = next((item for item in (data.get("results") if isinstance(data.get("results"), list) else [])
                  if isinstance(item, dict)), None)
    text = found.get("text") if found else None
    if status.get("status") == "error" or not isinstance(text, str) or not text.strip():
        error = status.get("error") if isinstance(status.get("error"), dict) else {}
        tag, code = str(error.get("tag") or ""), error.get("httpStatusCode")
        reason = PAGE_FAILURES.get(tag) or (f"HTTP {code}" if type(code) is int else "the page gave no text")
        return {"status": "failed", "error": reason, "cost_nanos": _cost(data, 0)}
    return {"status": "completed", "url": _web(found.get("url")) or url, "title": _line(found.get("title"), TITLE_CHARS),
            "text": text, "published": _day(found.get("publishedDate")), "stored": status.get("source") == "cached",
            "cost_nanos": _cost(data, PAGE_COST_NANOS)}
