"""Admin-owned daily allowance in euros, cached per database; reset without a user scan.

One account serves every mode: Agent books each call (reserve, then settle with
its measured cost), the Consensus pipeline is admitted against the expected
cost of a typical run and books the measured cost afterwards. Both read their
limit from the account tier (Free, Plus, Pro, Admin). Opening Agent to another
tier is therefore an access decision only; the ledger needs no change.

Since 2026-10-31 (Max) the account counts money, not tokens: whole
micro-euros (1 EUR = 1,000,000), converted from the provider's dollar cost at
the fixed NANO_USD_PER_MICRO_EUR. A cached prompt, a web search and an audit
reviewer then count what they cost, without weights. The derivation of the
limits lives in docs/codebase-map.md ("Ein Konto in Euro für alle Modi").
"""
from copy import deepcopy
from datetime import datetime, timezone
import threading
import time
from uuid import uuid4
from weakref import WeakKeyDictionary, ref as weakref

from app.services import persistence_guard

CACHE_SECONDS = 30
# Amounts are whole micro-euros: 1 EUR = 1,000,000.
MICRO_EUR = 1_000_000
# Written with every save since 2026-10-31: a document without it holds tokens.
UNIT = "micro_eur"
MAX_DAILY_LIMIT = 1_000 * MICRO_EUR
MAX_RUN_ESTIMATE = 10 * MICRO_EUR
# A fixed exchange rate, 1 EUR = 1.15 USD (late October 2026: about 1.12 to
# 1.15). OpenRouter bills in dollars; a few percent of drift do not matter for
# a daily allowance, and a fixed rate keeps every booking reproducible.
NANO_USD_PER_MICRO_EUR = 1_150

TIER_KEYS = ("free", "plus", "pro", "admin")
# "deep_think" is the kept storage key (app_config, admin API) of a run with
# the Reasoning switch on; Deep Think itself was removed on 2026-10-02.
RUN_MODES = ("compare", "consensus", "deep_think")

# Euros per day (Max, 2026-10-31). Measured 21.-30.10. in Prod, one million
# tokens of the former account cost 0.24 to 2.18 USD, about 1.46 USD at Free:
# 660,000 tokens were about 0.85 EUR a day, 5 million at Pro typically 4 EUR.
# The limits keep that capacity in round figures; Plus stays 2.5 x Free.
DEFAULT_TIER_LIMITS = {
    "free": 1 * MICRO_EUR,
    "plus": 2_500_000,
    "pro": 5 * MICRO_EUR,
    "admin": 5 * MICRO_EUR,
}

# Expected cost of one typical run, the admission threshold of the pipeline:
# the former token estimates (Free/Plus 32k Compare, 55k Consensus, 150k with
# Reasoning; Pro 40k/75k/150k) at the price of the tier's models, searches
# included, rounded up. Derived, not measured: Compare and Consensus ran on a
# single account-day in the ten days before the switch. Admin tunes them in
# the Limits tab; bookings charge the measured cost either way.
_STANDARD_RUN = {"compare": 60_000, "consensus": 100_000, "deep_think": 200_000}
_PRO_RUN = {"compare": 150_000, "consensus": 250_000, "deep_think": 400_000}
DEFAULT_RUN_ESTIMATES = {
    "free": dict(_STANDARD_RUN),
    "plus": dict(_STANDARD_RUN),
    "pro": dict(_PRO_RUN),
    "admin": dict(_PRO_RUN),
}


def micro_eur(nano_usd):
    """A dollar cost in nano-USD as whole micro-euros, rounded up; None stays None."""
    if nano_usd is None:
        return None
    return -(-max(0, int(nano_usd)) // NANO_USD_PER_MICRO_EUR)


def nano_usd(micro_eur):
    """Micro-euros as nano-USD (the unit of model prices and receipts)."""
    return int(micro_eur) * NANO_USD_PER_MICRO_EUR


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
        raise ValueError("Invalid daily limits")
    return {tier: _positive_int(value.get(tier, DEFAULT_TIER_LIMITS[tier]), MAX_DAILY_LIMIT,
                                 "Invalid daily limit")
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
    # Every save and reset before 2026-10-31 wrote the whole table in tokens;
    # read as micro-euros they would be other limits (Free 0.66 EUR), so a
    # document without the unit keeps the euro defaults until its next save.
    euros = data.get("unit") == UNIT
    return {"tier_limits": normalize_tier_limits(data.get("tier_limits") if euros else None),
            "run_estimates": normalize_run_estimates(data.get("run_estimates") if euros else None),
            "unit": UNIT, "revision": revision, "reset_epoch": epoch,
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
    """Admission mode of a pipeline run. Unknown means the larger Consensus run.

    ``deep_think`` means "Reasoning on" (compatibility name)."""
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
