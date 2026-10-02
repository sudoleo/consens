"""Admin-owned daily token account, cached per database; reset without a user scan.

One account serves every mode: Agent books each call (reserve, then settle with
measured usage), the Consensus pipeline is admitted against the expected cost
of a typical run and books the measured tokens afterwards. Both read their
limit from the account tier (Free, Plus, Pro, Admin). Opening Agent to another
tier is therefore an access decision only; the ledger needs no change.

The defaults keep a typical user's daily capacity from the run quotas they
replace: limit ~ old daily run limit x tokens of a typical run. The derivation
lives in docs/codebase-map.md ("Ein Tokenkonto für alle Modi").
"""
from copy import deepcopy
from datetime import datetime, timezone
import threading
import time
from uuid import uuid4
from weakref import WeakKeyDictionary, ref as weakref

from app.services import persistence_guard

CACHE_SECONDS = 30
MAX_DAILY_TOKENS = 100_000_000
MAX_RUN_ESTIMATE = 10_000_000

TIER_KEYS = ("free", "plus", "pro", "admin")
RUN_MODES = ("compare", "consensus", "deep_think")

# Old run quotas in production (12 / 30 / 50 runs, 5 of them Deep Think) times
# the typical run below. Pro and Admin additionally keep the separate
# 750,000-token Agent allowance they had before both modes shared one account.
DEFAULT_TIER_LIMITS = {
    "free": 660_000,
    "plus": 1_650_000,
    "pro": 5_000_000,
    "admin": 5_000_000,
}

# Expected tokens of one typical run (input + output, reasoning included), the
# admission threshold of the pipeline. Free/Plus answer with the 4,096-token
# cap, Pro with 8,192, Deep Think with 16,384 and five search rounds.
_STANDARD_RUN = {"compare": 32_000, "consensus": 55_000, "deep_think": 150_000}
_PRO_RUN = {"compare": 40_000, "consensus": 75_000, "deep_think": 150_000}
DEFAULT_RUN_ESTIMATES = {
    "free": dict(_STANDARD_RUN),
    "plus": dict(_STANDARD_RUN),
    "pro": dict(_PRO_RUN),
    "admin": dict(_PRO_RUN),
}


class BudgetConfigConflict(ValueError):
    pass


def _positive_int(value, maximum, message):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(message)
    return value


def normalize_tier_limits(value):
    """Missing tiers take their default; a present but invalid value fails closed."""
    value = value if value is not None else {}
    if not isinstance(value, dict) or any(key not in TIER_KEYS for key in value):
        raise ValueError("Invalid daily token limits")
    return {tier: _positive_int(value.get(tier, DEFAULT_TIER_LIMITS[tier]), MAX_DAILY_TOKENS,
                                 "Invalid daily token limit")
            for tier in TIER_KEYS}


def normalize_run_estimates(value):
    value = value if value is not None else {}
    if not isinstance(value, dict) or any(key not in TIER_KEYS for key in value):
        raise ValueError("Invalid run estimates")
    result = {}
    for tier in TIER_KEYS:
        modes = value.get(tier) or {}
        if not isinstance(modes, dict) or any(key not in RUN_MODES for key in modes):
            raise ValueError("Invalid run estimates")
        result[tier] = {mode: _positive_int(modes.get(mode, DEFAULT_RUN_ESTIMATES[tier][mode]), MAX_RUN_ESTIMATE,
                                            "Invalid run estimate")
                        for mode in RUN_MODES}
    return result


def snapshot(data):
    data = data or {}
    revision = data.get("revision", 0)
    epoch = data.get("reset_epoch", "")
    if type(revision) is not int or revision < 0:
        raise ValueError("Invalid token budget revision")
    if epoch and (not isinstance(epoch, str) or len(epoch) != 32 or any(c not in '0123456789abcdef' for c in epoch)):
        raise ValueError("Invalid token budget reset")
    # The single pre-2026-10 `daily_token_limit` (Agent only) is not read any
    # more: its value is part of the Pro/Admin default above.
    return {"tier_limits": normalize_tier_limits(data.get("tier_limits")),
            "run_estimates": normalize_run_estimates(data.get("run_estimates")),
            "revision": revision, "reset_epoch": epoch,
            "updated_at": data.get("updated_at"), "updated_by": data.get("updated_by"),
            "reset_at": data.get("reset_at")}


def tier_key(tier, *, admin=False):
    """Account tier as the ledger sees it. Unknown values fall back to Free."""
    if admin:
        return "admin"
    tier = str(tier or "").strip().lower()
    return tier if tier in TIER_KEYS else "free"


def limit_for(config, tier):
    return config["tier_limits"][tier_key(tier)]


def run_estimates_for(config, tier):
    return dict(config["run_estimates"][tier_key(tier)])


def run_mode(mode, *, deep_think=False):
    """Admission mode of a pipeline run. Unknown means the larger Consensus run."""
    if deep_think:
        return "deep_think"
    return "compare" if mode == "compare" else "consensus"


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

    def save(self, *, expected_revision, updated_by, tier_limits=None, run_estimates=None, reset=False):
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("A valid revision is required")
        if not reset:
            if tier_limits is None and run_estimates is None:
                raise ValueError("Nothing to save")
            if tier_limits is not None:
                normalize_tier_limits(tier_limits)
            if run_estimates is not None:
                normalize_run_estimates(run_estimates)

        def operation(tx):
            document = self.document()
            current = snapshot(document.get(transaction=tx).to_dict())
            if current['revision'] != expected_revision:
                raise BudgetConfigConflict("The token budget changed in another session. Reload before trying again.")
            now = datetime.now(timezone.utc)
            saved = {**current, "revision": current['revision'] + 1, "updated_by": updated_by, "updated_at": now}
            if reset:
                saved.update(reset_epoch=uuid4().hex, reset_at=now)
            else:
                if tier_limits is not None:
                    saved['tier_limits'] = normalize_tier_limits({**current['tier_limits'], **tier_limits})
                if run_estimates is not None:
                    merged = {tier: {**current['run_estimates'][tier], **(run_estimates.get(tier) or {})}
                              for tier in TIER_KEYS}
                    saved['run_estimates'] = normalize_run_estimates(merged)
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
