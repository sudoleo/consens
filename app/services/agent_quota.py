"""UTC-day allowance in micro-euros (agent_budget_config.MICRO_EUR). Every
call is charged what it cost: the provider's dollar cost of the call (cache,
reasoning and web search included), else its catalog price, converted at
agent_budget_config.NANO_USD_PER_MICRO_EUR (measured_charge). Until
2026-10-31 the account counted tokens, cache reads and audit reviewers at
weights that stood in for their cost.

One ledger document per account and period serves Agent and the Consensus
pipeline alike; the limit comes from the account tier (agent_budget_config).
Agent reserves what a call is expected to cost before it starts
(agent_costs.RunCosts.estimate) and settles with measured usage. The pipeline
is admitted per run against the expected cost of a typical run, holds that
estimate while the run is young (``pipeline_holds``) and books the measured
cost of every finished operation afterwards. A run may therefore push the
account slightly below zero; the next admission then fails. The overdraft is
bounded because only runs with enough remaining budget are admitted and every
admitted run holds its estimate against concurrent admissions.

Reservations protect active calls only. A paid receipt is settled once;
retries cannot release or charge it again.

Bounded uncertainty (owner decision for R07): a started call whose final usage
is missing is neither fully released nor fully charged. Its reservation is
released and a bounded estimate is charged instead: the measured provisional
lower bound, but at least ``UNKNOWN_ESTIMATE_FRACTION`` of the reservation
and, for a run that lost its process, what such a call of the run measured.
Estimates live in their own ``estimated`` bucket, strictly separate from
the measured ``used`` amount, and count against ``remaining``. When the
provider later reports the generation's real cost, reconciliation swaps the
estimate for it exactly once. Calls that provably never started are
settled as a measured zero and release everything. There is no day-long lock.
"""
import math
import threading
import time
from datetime import datetime, timedelta, timezone

from app.services.llm.provider_runtime import AnalysisBudgetExceeded
from app.services import agent_budget_config


class AgentTokenBudgetExceeded(AnalysisBudgetExceeded):
    """``remaining``, ``required`` and ``reserved`` in micro-euros. The codes
    keep their names from the token account (browser and API contract)."""

    def __init__(self, remaining, required, *, reserved=0):
        self.remaining, self.required = remaining, required
        self.reserved = reserved
        self.code = "agent_token_reservation" if remaining else "agent_tokens_exhausted"
        message = ("The next model call needed more of today's allowance than was available at that point. "
                   "Some allowance may be reserved for active calls. Completed calls release their reservations."
                   if remaining else "Nothing was left in today's allowance for the next model call. Active calls temporarily reserve part of it. The daily allowance resets at 00:00 UTC.")
        super().__init__(message)


# Serialize short bookkeeping transactions per account inside each process.
# Agent and pipeline write the same ledger document; Firestore still fences
# concurrent processes, providers stay fully parallel.
_ACCOUNT_WRITES = tuple(threading.RLock() for _ in range(128))


def account_lock(uid):
    return _ACCOUNT_WRITES[hash(uid) % len(_ACCOUNT_WRITES)]


def _stored_tier(uid):
    from app.core import security
    return security.get_user_tier(uid)


def _admin_role(uid):
    from app.core import security
    return security.is_user_admin(uid)


def account_tier(uid, tier=None):
    """Ledger tier of an account: admin role first, then the stored tier.

    Routes that already resolved the tier pass it in. Both reads share the
    cached user document and raise TierStatusUnavailable on storage errors;
    callers map that to 503 instead of using another tier's limit.
    """
    tier = _stored_tier(uid) if tier is None else tier
    return agent_budget_config.tier_key(tier, admin=_admin_role(uid))


# Read throttles for snapshot(), which runs on every allowance poll and on
# every usage event of an Agent run. Both extra reads mostly find nothing:
# an owner with no running delegation is asked again after RECOVERY_QUIET_S,
# and a yesterday without estimates stays without them once the new day is
# PREVIOUS_DAY_GRACE old (a call reserved before midnight may still book its
# estimate there shortly after it).
RECOVERY_QUIET_S = 120
PREVIOUS_DAY_QUIET_S = 600
PREVIOUS_DAY_GRACE = timedelta(hours=2)
_quiet_lock = threading.Lock()
_quiet_until = {}


def _quiet(key):
    with _quiet_lock:
        return _quiet_until.get(key, 0) > time.monotonic()


def _mark_quiet(key, seconds):
    with _quiet_lock:
        if len(_quiet_until) > 4096:
            now = time.monotonic()
            for stale in [k for k, until in _quiet_until.items() if until <= now]:
                _quiet_until.pop(stale, None)
        _quiet_until[key] = time.monotonic() + seconds


def snapshot(db, uid, *, tier=None):
    from app.services.agent_runs import AgentRunStore
    store = AgentRunStore(db)
    recovery_key = ("recovery", id(db), uid)
    if not _quiet(recovery_key) and not store.recover_allowance(uid):
        _mark_quiet(recovery_key, RECOVERY_QUIET_S)
    # Timestamp the read's start so a slower HTTP response cannot overwrite a
    # newer terminal snapshot in the browser.
    observed_at = time.time_ns() // 1_000_000
    config = agent_budget_config.get_config(db)
    day = period_key(config)
    data = quota_ref(db, uid, day).get().to_dict() or {}
    if data.get('unknown', 0) > data.get('unknown_released', 0):
        data = store.repair_quota_period(uid, day)
    if awaits_measurement(data) or _previous_day_has_estimates(db, uid, day):
        # Provider usage lookups run off the request thread; a later snapshot
        # shows the measured result. This read never waits or fails for it.
        # Yesterday is checked too, so a call estimated just before midnight
        # is still measured instead of silently becoming final.
        from app.services import agent_usage_reconciliation
        agent_usage_reconciliation.schedule(db, uid)
    tier = account_tier(uid) if tier is None else agent_budget_config.tier_key(tier)
    return {**public_snapshot(data, day, config, tier), "observed_at": observed_at}


def public_snapshot(data, period, config, tier, *, now=None, limit=None):
    """The one browser shape of the account, shared by Agent and the pipeline."""
    tier = agent_budget_config.tier_key(tier)
    limit = agent_budget_config.limit_for(config, tier) if limit is None else limit
    return {**public(data, period.split('_')[0], limit=limit, now=now),
            "observed_at": time.time_ns() // 1_000_000, "config_revision": config['revision'],
            "tier": tier, "run_estimates": agent_budget_config.run_estimates_for(config, tier)}


def remaining_allowance(db, uid, *, tier=None):
    """Plain read of today's unreserved allowance (micro-euros), without snapshot repairs."""
    config = agent_budget_config.get_config(db)
    tier = account_tier(uid) if tier is None else tier
    data = quota_ref(db, uid, period_key(config)).get().to_dict() or {}
    return _remaining(data, agent_budget_config.limit_for(config, tier))


def shown_allowance(db, uid, *, tier=None):
    """``(left, limit)`` of today's allowance as the sidebar ring shows it
    (token-budget.js view): the limit less what was spent, not less what
    running calls hold for the moment (remaining_allowance)."""
    config = agent_budget_config.get_config(db)
    tier = account_tier(uid) if tier is None else tier
    data = quota_ref(db, uid, period_key(config)).get().to_dict() or {}
    limit = agent_budget_config.limit_for(config, tier)
    return max(0, limit - spent_amount(data)), limit


def _previous_day_has_estimates(db, uid, day):
    try:
        today = datetime.strptime(day.split('_')[0], "%Y-%m-%d")
    except ValueError:
        return False
    suffix = day[len(day.split('_')[0]):]
    previous = (today - timedelta(days=1)).strftime("%Y-%m-%d") + suffix
    quiet_key = ("previous-day", id(db), uid, previous)
    settled = datetime.now(timezone.utc).replace(tzinfo=None) - today >= PREVIOUS_DAY_GRACE
    if settled and _quiet(quiet_key):
        return False
    try:
        pending = awaits_measurement(quota_ref(db, uid, previous).get().to_dict())
    except Exception:
        return False
    if settled and not pending:
        _mark_quiet(quiet_key, PREVIOUS_DAY_QUIET_S)
    return pending


def daily_limit():
    """Fallback for pure ledger helpers called without a limit (tests, scripts)."""
    return agent_budget_config.DEFAULT_TIER_LIMITS["pro"]


def day_key():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# The unit of the period's ledger. Ledgers of the token account (until
# 2026-10-31) have no suffix: a call reserved in tokens before the switch
# settles into its own token ledger, never into the euro one.
LEDGER_UNIT = "_eur"


def period_key(config):
    # Receipts retain this key, so calls started before a reset settle into the
    # old ledger without consuming or releasing the freshly reset allowance.
    return day_key() + ("_" + config['reset_epoch'] if config.get('reset_epoch') else "") + LEDGER_UNIT


def quota_ref(db, uid, day):
    return db.collection("users").document(uid).collection("chat_state").document("agent_tokens_" + day)


# Share of an unknown call's reservation that is charged as an estimate.
UNKNOWN_ESTIMATE_FRACTION = 0.5


def measured_charge(usage):
    """What a measured call takes from the account in micro-euros, or None
    when its cost is not final: the provider's cost of the call, else its
    catalog price (agent_client.measured_usage), whatever kind of call it was."""
    if not usage or usage.get("provisional") or not usage.get("cost_complete", usage.get("complete", True)):
        return None
    cost = usage.get("estimated_cost_nano_usd")
    return agent_budget_config.micro_eur(cost) if type(cost) is int and cost >= 0 else None


def provisional_lower_bound(usage):
    """The cost of the counts seen before a lost final chunk: a lower bound only."""
    cost = (usage or {}).get("estimated_cost_nano_usd")
    return agent_budget_config.micro_eur(cost) if type(cost) is int and cost >= 0 else 0


def unknown_estimate(reserved, usage, *, expected=0):
    """Bounded charge for a started call without a final cost, else None.
    ``reserved`` is the ledger's reservation of the call; ``expected`` what
    such a call of its run measured (a run that lost its process,
    AgentSessionStore.reap_delegation)."""
    if measured_charge(usage) is not None:
        return None
    floor = math.ceil(max(0, reserved) * UNKNOWN_ESTIMATE_FRACTION)
    return max(provisional_lower_bound(usage), floor, max(0, int(expected or 0)))


# A pipeline run holds its expected cost against concurrent admissions for at
# most this long; measured bookings shrink the hold, expiry drops the rest.
# The admission lapses with it: a run's first operation after the window is
# admitted against the account again (usage_repository), so a run cannot bank
# its admission for the hours of its execution window. At most
# MAX_PIPELINE_HOLDS runs per account are therefore admitted and unchecked.
PIPELINE_HOLD_SECONDS = 10 * 60
MAX_PIPELINE_HOLDS = 32


class PipelineCapacityExceeded(Exception):
    """Too many young pipeline runs at once on one account."""


def _now(now=None):
    return time.time() if now is None else now


def active_holds(data, now=None):
    now = _now(now)
    holds = data.get("pipeline_holds") or {}
    return {key: dict(hold) for key, hold in holds.items()
            if isinstance(hold, dict) and type(hold.get("amount")) is int and hold["amount"] > 0
            and isinstance(hold.get("expires_at"), (int, float)) and hold["expires_at"] > now}


def held_amount(data, now=None):
    return sum(hold["amount"] for hold in active_holds(data, now).values())


def spent_amount(data):
    """Measured plus estimated consumption of both modes; holds excluded."""
    return data.get("used", 0) + data.get("estimated", 0) + data.get("pipeline_estimated", 0)


def _remaining(data, limit, now=None):
    return max(0, limit - spent_amount(data) - data.get("reserved", 0) - held_amount(data, now))


def admit_run(data, run_id, estimate, *, limit, now=None, readmission=False):
    """Admit one pipeline run if the remaining budget covers its expected cost.

    ``readmission`` admits an existing run whose admission lapsed; it is
    counted apart from new runs."""
    data = normalize(data)
    now = _now(now)
    holds = active_holds(data, now)
    if run_id in holds:
        return data
    remaining = _remaining(data, limit, now)
    if estimate > remaining:
        raise AgentTokenBudgetExceeded(remaining, estimate, reserved=data.get("reserved", 0) + held_amount(data, now))
    if len(holds) >= MAX_PIPELINE_HOLDS:
        raise PipelineCapacityExceeded("Too many runs are starting at once")
    holds[run_id] = {"amount": int(estimate), "expires_at": now + PIPELINE_HOLD_SECONDS}
    data["pipeline_holds"] = holds
    counter = "pipeline_readmissions" if readmission else "pipeline_runs"
    data[counter] = data.get(counter, 0) + 1
    data["revision"] = data.get("revision", 0) + 1
    return data


def book_run(data, run_id, *, measured, estimated, now=None):
    """Book one finished pipeline operation. It may overdraw the account."""
    data = normalize(data)
    measured, estimated = max(0, int(measured)), max(0, int(estimated))
    data["used"] = data.get("used", 0) + measured
    data["pipeline_used"] = data.get("pipeline_used", 0) + measured
    data["pipeline_estimated"] = data.get("pipeline_estimated", 0) + estimated
    holds = active_holds(data, now)
    if run_id in holds:
        left = holds[run_id]["amount"] - measured - estimated
        if left > 0:
            holds[run_id]["amount"] = left
        else:
            holds.pop(run_id)
    data["pipeline_holds"] = holds
    data["revision"] = data.get("revision", 0) + 1
    return data


def release_run(data, run_id, *, now=None):
    """Drop a run's remaining hold (released before work, or finished)."""
    data = normalize(data)
    holds = active_holds(data, now)
    if run_id not in holds:
        return data
    holds.pop(run_id)
    data["pipeline_holds"] = holds
    data["revision"] = data.get("revision", 0) + 1
    return data


def normalize(data):
    """Release legacy terminal holds, exactly once, without touching live holds.

    `unknown` was only incremented when a receipt became terminal. The cumulative
    marker also handles an old server settling another receipt during rollout.
    These are reservation bounds, never invented measured/billed token counts.
    """
    data = dict(data or {})
    pending = max(0, data.get('unknown', 0) - data.get('unknown_released', 0))
    if pending:
        data['reserved'] = max(0, data.get('reserved', 0) - pending)
        data['unknown_released'] = data['unknown']
        data['revision'] = data.get('revision', 0) + 1
    return data


def reserve(data, amount, *, limit=None, overdraft=False):
    """Hold ``amount`` for an active call. ``overdraft`` admits it even
    beyond the limit (finishing an Agent message that holds paid work); the
    next admission then fails, as after an overdrawn pipeline run."""
    data = normalize(data)
    remaining = _remaining(data, daily_limit() if limit is None else limit)
    if not overdraft and amount > remaining:
        raise AgentTokenBudgetExceeded(remaining, amount, reserved=data.get("reserved", 0))
    data["reserved"] = data.get("reserved", 0) + amount
    data["revision"] = data.get("revision", 0) + 1
    return data


def settle(data, reserved, usage, *, measurable=False, expected=0):
    """Swap a call's reservation for its charge (measured_charge).
    ``measurable``: an estimate charged instead can still be measured later
    (the call has a provider generation id, agent_usage_reconciliation);
    ``expected`` as for unknown_estimate."""
    data = normalize(data)
    actual = measured_charge(usage)
    data['reserved'] = max(0, data.get('reserved', 0) - reserved)
    data.setdefault("estimates_pending", 0)
    if actual is not None:
        data["used"] = data.get("used", 0) + actual
    else:
        # The reservation bound stays auditable as `unknown` and is released;
        # a bounded estimate is charged until reconciliation replaces it.
        data["unknown"] = data.get("unknown", 0) + reserved
        data['unknown_released'] = data.get('unknown_released', 0) + reserved
        data["estimated"] = data.get("estimated", 0) + unknown_estimate(reserved, usage, expected=expected)
        if measurable:
            data["estimates_pending"] += 1
    data["revision"] = data.get("revision", 0) + 1
    return data


# How many of a ledger's estimates still wait for their measurement, apart
# from the amount: an estimate that can never be measured stays charged for
# good, and until 2026-11-03 its ``estimated`` amount alone had snapshot()
# look for a measurement all day (a query a minute while a chat was open, and
# yesterday's ledger read on every snapshot of the next day).
def awaits_measurement(data):
    data = data or {}
    if "estimates_pending" in data:
        return data["estimates_pending"] > 0
    # A ledger no call has settled into since then only knows the amount.
    return data.get("estimated", 0) > 0


def estimate_closed(data):
    """One of the ledger's estimates no longer waits: measured, or kept as final."""
    data = dict(data or {})
    data["estimates_pending"] = max(0, data.get("estimates_pending", 0) - 1)
    return data


# What the account's model calls took in all (the admin's account lookup),
# counted in the day's ledger that a claim and a settlement write anyway.
# Until 2026-11-01 the user document carried these counters: two more writes
# and reads of the account's busiest document per model call, about a fifth
# of all Firestore writes of an Agent message.
USAGE_SUMS = ("input_tokens", "output_tokens", "cached_input_tokens", "cache_write_tokens", "reasoning_tokens",
              "estimated_cost_nano_usd")


def count_claim(data):
    """A call claimed against ``data`` (a day's ledger): counted, unsettled."""
    totals = dict(data.get("agent_usage") or {})
    totals["calls"] = totals.get("calls", 0) + 1
    totals["unsettled_calls"] = totals.get("unsettled_calls", 0) + 1
    data["agent_usage"] = totals
    return data


def count_settlement(data, usage):
    """The settled call's measurement in the ledger's sums (count_claim)."""
    totals = dict(data.get("agent_usage") or {})
    totals["unsettled_calls"] = max(0, totals.get("unsettled_calls", 0) - 1)
    key = "measured_calls" if usage is not None and usage.get("input_tokens") is not None else "unmetered_calls"
    totals[key] = totals.get(key, 0) + 1
    if usage is not None and not usage.get("complete", True):
        totals["incomplete_calls"] = totals.get("incomplete_calls", 0) + 1
    if usage is not None and usage.get("estimated_cost_nano_usd") is not None:
        cost_key = "provider_cost_nano_usd" if usage.get("cost_source") == "provider" else "catalog_cost_nano_usd"
        totals[cost_key] = totals.get(cost_key, 0) + usage["estimated_cost_nano_usd"]
    for field in USAGE_SUMS:
        if usage is not None and usage.get(field) is not None:
            totals[field] = totals.get(field, 0) + usage[field]
    data["agent_usage"] = totals
    return data


def usage_totals(db, uid, legacy=None):
    """The account's sums over all its day ledgers (count_claim and
    count_settlement), added to ``legacy``: what the user document counted
    until 2026-11-01. Reads every ledger of the account: for the admin's
    lookup only, never on a message's path."""
    totals = {key: value for key, value in (legacy or {}).items() if type(value) in (int, float)}
    ledgers = db.collection("users").document(uid).collection("chat_state").stream()
    for snapshot in ledgers:
        if not (snapshot.id.startswith("agent_tokens_") and snapshot.id.endswith(LEDGER_UNIT)):
            continue
        for key, value in ((snapshot.to_dict() or {}).get("agent_usage") or {}).items():
            if type(value) in (int, float):
                totals[key] = totals.get(key, 0) + value
    return totals


def reconcile(data, estimate, actual):
    """Replace one charged estimate with the measured charge. Callers fence once."""
    data = estimate_closed(normalize(data))
    data["estimated"] = max(0, data.get("estimated", 0) - estimate)
    data["used"] = data.get("used", 0) + actual
    data["reconciled"] = data.get("reconciled", 0) + 1
    data["revision"] = data.get("revision", 0) + 1
    return data


def public(data, day=None, *, limit=None, now=None):
    data = normalize(data)
    limit = daily_limit() if limit is None else limit
    # `estimated` is everything charged without a final measurement (both
    # modes), `reserved` everything held for running work (both modes).
    return {"day": day or day_key(), "unit": "micro_eur", "revision": data.get("revision", 0), "limit": limit,
            "used": data.get("used", 0),
            "reserved": data.get("reserved", 0) + held_amount(data, now), "unknown": data.get("unknown", 0),
            "estimated": data.get("estimated", 0) + data.get("pipeline_estimated", 0),
            "remaining": _remaining(data, limit, now)}
