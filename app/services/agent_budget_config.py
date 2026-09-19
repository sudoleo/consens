"""Admin-owned Agent allowance, cached per database; reset without a user scan."""
from copy import deepcopy
from datetime import datetime, timezone
import os
import threading
import time
from uuid import uuid4
from weakref import WeakKeyDictionary, ref as weakref

from app.services import persistence_guard

CACHE_SECONDS = 30
MAX_DAILY_TOKENS = 100_000_000


class BudgetConfigConflict(ValueError):
    pass


def default_limit():
    value = int(os.getenv("AGENT_DAILY_TOKEN_LIMIT", "250000"))
    if not 1 <= value <= MAX_DAILY_TOKENS:
        raise ValueError("Agent daily token limit is outside the supported range")
    return value


def snapshot(data):
    data = data or {}
    limit = data.get("daily_token_limit", default_limit())
    revision = data.get("revision", 0)
    epoch = data.get("reset_epoch", "")
    if type(limit) is not int or not 1 <= limit <= MAX_DAILY_TOKENS:
        raise ValueError("Invalid Agent daily token limit")
    if type(revision) is not int or revision < 0:
        raise ValueError("Invalid Agent budget revision")
    if epoch and (not isinstance(epoch, str) or len(epoch) != 32 or any(c not in '0123456789abcdef' for c in epoch)):
        raise ValueError("Invalid Agent budget reset")
    return {"daily_token_limit": limit, "revision": revision, "reset_epoch": epoch,
            "updated_at": data.get("updated_at"), "updated_by": data.get("updated_by"),
            "reset_at": data.get("reset_at")}


class BudgetConfigStore:
    def __init__(self, db, *, clock=time.monotonic):
        self._db = weakref(db)
        self.clock = clock
        self.lock = threading.RLock()
        self.cached, self.expires = None, 0

    def document(self):
        return self._db().collection("app_config").document("agent_budget")

    def read(self, *, force=False):
        with self.lock:
            if not force and self.cached is not None and self.clock() < self.expires:
                return deepcopy(self.cached)
            # Fail closed on DB errors: don't silently revive the old allowance
            # or an old reset generation. Only a missing document uses defaults.
            current = snapshot(self.document().get().to_dict())
            self.cached, self.expires = current, self.clock() + CACHE_SECONDS
            return deepcopy(current)

    def save(self, *, expected_revision, updated_by, daily_token_limit=None, reset=False):
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("A valid revision is required")
        if not reset:
            snapshot({"daily_token_limit": daily_token_limit})
        def operation(tx):
            document = self.document()
            current = snapshot(document.get(transaction=tx).to_dict())
            if current['revision'] != expected_revision:
                raise BudgetConfigConflict("Agent budget changed in another session. Reload before trying again.")
            now = datetime.now(timezone.utc)
            saved = {**current, "revision": current['revision'] + 1, "updated_by": updated_by, "updated_at": now}
            if reset:
                saved.update(reset_epoch=uuid4().hex, reset_at=now)
            else:
                saved['daily_token_limit'] = daily_token_limit
            persistence_guard._set(tx, document, saved)
            persistence_guard._set(tx, document.collection('revisions').document(f"{saved['revision']:012d}"), saved)
            return saved
        with self.lock:
            saved = persistence_guard._run_transaction(self._db(), operation)
            self.cached, self.expires = saved, self.clock() + CACHE_SECONDS
            return deepcopy(saved)


_stores = WeakKeyDictionary()
_lock = threading.Lock()


def store(db):
    with _lock:
        if db not in _stores:
            _stores[db] = BudgetConfigStore(db)
        return _stores[db]


def get_config(db):
    return store(db).read()
