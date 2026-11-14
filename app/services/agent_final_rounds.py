"""What the reviewers' final rounds took, by model and endpoint, kept across
deploys.

The marks of an answer wait for its slowest reviewer's final round
(agent_audit). Two decisions there rest on what earlier final rounds took:
when a round gets its hedge (agent_audit.final_hedge_seconds) and which
endpoints of its model a reviewer stays away from (slow_endpoints). Counted
in the process alone, neither has enough rounds to go by: a deploy starts
the count over, and a model has a handful of final rounds a day.

One document, ``ops_metrics/agent-final-rounds``: per model its last ROUNDS
final rounds, each the time it ended, its seconds and the endpoint that
served it. Never an account, a chat or any text. The document is read once
per process and written after a review's final rounds, both off the run's
thread; a read or write that fails costs only what it would have told. Not
in tests or with MOCK_LLM, which share the real database locally.

A round older than MAX_AGE_SECONDS no longer counts. That is also how an
endpoint a reviewer stays away from gets its next chance: it gets no new
rounds while it is avoided, so its old ones run out.
"""
from __future__ import annotations

import logging
import os
import statistics
import threading
import time
from collections import deque
from datetime import datetime, timezone

from app.core.observability import safe_exception

COLLECTION, DOCUMENT = "ops_metrics", "agent-final-rounds"
ROUNDS = 50
MAX_AGE_SECONDS = 14 * 86400
# An endpoint is slow for a model when the median of its final rounds, from
# ENDPOINT_MIN_ROUNDS on, is SLOW_FACTOR times that of the model's fastest
# endpoint and at least SLOW_MIN_SECONDS more. A round's time is mostly its
# reviewer's thinking, which varies with the answer: the factor and the
# seconds keep a few long answers from condemning an endpoint. (Prod, six
# days to 2026-11-14, median seconds: DeepSeek V4.1 Flash 8 on Together, 29
# and 60 on two others, which were a fifth of its rounds and all of its p90;
# Claude Haiku 5.5 7, 9 and 13.5.)
ENDPOINT_MIN_ROUNDS = 3
SLOW_FACTOR = 1.75
SLOW_MIN_SECONDS = 4.
# A reviewer stays away from at most this many endpoints of its model.
MAX_AVOIDED = 3
ENDPOINT_CHARS = 80

_lock = threading.Lock()
# {model: deque of (ended at, seconds, endpoint)}, oldest first.
_rounds = {}
_loading = None
_saving = threading.Lock()


def record(model, seconds, endpoint="", *, now=None):
    """A final round's first request on ``model`` took ``seconds`` (or had
    run that long when its hedge overtook it), on ``endpoint`` where its
    stream named one."""
    entry = (float(now if now is not None else time.time()), float(seconds), str(endpoint or "")[:ENDPOINT_CHARS])
    with _lock:
        _rounds.setdefault(model, deque(maxlen=ROUNDS)).append(entry)


def rounds(model, *, now=None):
    """``model``'s rounds that still count, oldest first: [(ended at, seconds, endpoint)]."""
    since = (now if now is not None else time.time()) - MAX_AGE_SECONDS
    with _lock:
        return [entry for entry in _rounds.get(model, ()) if entry[0] >= since]


def _slow(entries):
    by_endpoint = {}
    for _, seconds, endpoint in entries:
        if endpoint:
            by_endpoint.setdefault(endpoint, []).append(seconds)
    medians = {endpoint: statistics.median(values) for endpoint, values in by_endpoint.items()
               if len(values) >= ENDPOINT_MIN_ROUNDS}
    if len(medians) < 2:
        return ()
    best = min(medians.values())
    slow = [endpoint for endpoint, median in medians.items()
            if median >= best * SLOW_FACTOR and median - best >= SLOW_MIN_SECONDS]
    return tuple(sorted(slow, key=lambda endpoint: (-medians[endpoint], endpoint))[:MAX_AVOIDED])


def slow_endpoints(model, *, now=None):
    """The endpoints of ``model`` a reviewer stays away from, slowest first;
    none before two of its endpoints have enough rounds to compare."""
    return _slow(rounds(model, now=now))


def seconds(model, *, now=None):
    """What ``model``'s final rounds took, sorted, without those on an
    endpoint its reviewers stay away from now: they say nothing about the
    next round, which runs elsewhere."""
    entries = rounds(model, now=now)
    slow = set(_slow(entries))
    return sorted(seconds for _, seconds, endpoint in entries if endpoint not in slow)


def _enabled():
    return not any(os.getenv(key) == "1" for key in ("UNIT_TEST_MODE", "E2E_TEST_MODE", "MOCK_LLM"))


def _document():
    from app.core.security import db_firestore
    return db_firestore.collection(COLLECTION).document(DOCUMENT)


def _stored(data):
    """{model: [(ended at, seconds, endpoint)]} of a saved document; what does not read as a round is left out."""
    found = {}
    for item in (data or {}).get("models") or []:
        if not isinstance(item, dict) or not isinstance(item.get("model"), str):
            continue
        entries = []
        for entry in item.get("rounds") or []:
            at, taken = (entry.get("at"), entry.get("s")) if isinstance(entry, dict) else (None, None)
            if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in (at, taken)):
                entries.append((float(at), float(taken), str(entry.get("e") or "")[:ENDPOINT_CHARS]))
        if entries:
            found[item["model"]] = entries
    return found


def _merge(stored, *, now=None):
    """The saved rounds join those of this process: each once, the newest ROUNDS that still count."""
    since = (now if now is not None else time.time()) - MAX_AGE_SECONDS
    with _lock:
        for model in set(stored) | set(_rounds):
            merged = sorted({*stored.get(model, ()), *_rounds.get(model, ())})
            kept = [entry for entry in merged if entry[0] >= since][-ROUNDS:]
            if kept:
                _rounds[model] = deque(kept, maxlen=ROUNDS)
            else:
                _rounds.pop(model, None)


def _read():
    try:
        snapshot = _document().get()
        _merge(_stored(snapshot.to_dict() if snapshot.exists else {}))
    except Exception as exc:
        logging.warning("Agent final rounds not read category=%s", safe_exception(exc))


def load():
    """The saved rounds, once per process, off the caller's thread
    (AnswerAudit.follow: the run's start, long before its final rounds)."""
    global _loading
    if not _enabled():
        return
    with _lock:
        if _loading is not None:
            return
        _loading = threading.Thread(target=_read, name="agent-final-rounds-load", daemon=True)
    _loading.start()


def _write():
    with _saving:
        try:
            reference = _document()
            # Another instance may have saved since (a deploy overlaps): its
            # rounds stay.
            snapshot = reference.get()
            _merge(_stored(snapshot.to_dict() if snapshot.exists else {}))
            with _lock:
                models = [{"model": model, "rounds": [{"at": at, "s": round(taken, 2), "e": endpoint}
                                                      for at, taken, endpoint in entries]}
                          for model, entries in sorted(_rounds.items())]
            reference.set({"models": models, "updated_at": datetime.now(timezone.utc)})
        except Exception as exc:
            logging.warning("Agent final rounds not saved category=%s", safe_exception(exc))


def save():
    """After a review's final rounds: the rounds are saved off the caller's thread."""
    if not _enabled():
        return
    try:
        threading.Thread(target=_write, name="agent-final-rounds-save", daemon=True).start()
    except Exception as exc:
        logging.warning("Agent final rounds save not started category=%s", safe_exception(exc))
