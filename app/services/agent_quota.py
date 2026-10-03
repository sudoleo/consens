"""UTC-day token account. Measured tokens are input + output, never details.

One ledger document per account and period serves Agent and the Consensus
pipeline alike; the limit comes from the account tier (agent_budget_config).
Agent reserves before every call and settles with measured usage. The pipeline
is admitted per run against the expected cost of a typical run, holds that
estimate while the run is young (``pipeline_holds``) and books the measured
tokens of every finished operation afterwards. A run may therefore push the
account slightly below zero; the next admission then fails. The overdraft is
bounded because only runs with enough remaining budget are admitted and every
admitted run holds its estimate against concurrent admissions.

Reservations protect active calls only. A paid receipt is settled once;
retries cannot release or charge it again.

Bounded uncertainty (owner decision for R07): a started call whose final usage
is missing is neither fully released nor fully charged. Its reservation is
released and a bounded estimate is charged instead: the measured provisional
lower bound, but at least ``UNKNOWN_ESTIMATE_FRACTION`` of the reservation.
Estimates live in their own ``estimated`` bucket, strictly separate from
measured ``used`` tokens, and count against ``remaining``. When the provider
later reports the generation's real usage, reconciliation swaps the estimate
for the measured tokens exactly once. Calls that provably never started are
settled as a measured zero and release everything. There is no day-long lock.
"""
import math
import threading
import time
from datetime import datetime, timedelta, timezone

from app.services.llm.provider_runtime import AnalysisBudgetExceeded
from app.services import agent_budget_config


class AgentTokenBudgetExceeded(AnalysisBudgetExceeded):
    def __init__(self, remaining, required, *, reserved=0):
        self.remaining, self.required = remaining, required
        self.reserved = reserved
        self.code = "agent_token_reservation" if remaining else "agent_tokens_exhausted"
        message = (f"The next model call needed a reservation of {required:,} tokens; {remaining:,} were available at that point. "
                   "Some allowance may be reserved for active calls. Completed calls release their reservations."
                   if remaining else "No tokens were left in today's allowance for the next model call. Active calls temporarily reserve tokens. The daily allowance resets at 00:00 UTC.")
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
    if data.get('estimated', 0) > 0 or _previous_day_has_estimates(db, uid, day):
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


def remaining_tokens(db, uid, *, tier=None):
    """Plain read of today's unreserved allowance, without snapshot repairs."""
    config = agent_budget_config.get_config(db)
    tier = account_tier(uid) if tier is None else tier
    data = quota_ref(db, uid, period_key(config)).get().to_dict() or {}
    return _remaining(data, agent_budget_config.limit_for(config, tier))


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
        pending = (quota_ref(db, uid, previous).get().to_dict() or {}).get('estimated', 0) > 0
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


def period_key(config):
    # Receipts retain this key, so calls started before a reset settle into the
    # old ledger without consuming or releasing the freshly reset allowance.
    return day_key() + ("_" + config['reset_epoch'] if config.get('reset_epoch') else "")


def quota_ref(db, uid, day):
    return db.collection("users").document(uid).collection("chat_state").document("agent_tokens_" + day)


# Share of an unknown call's reservation that is charged as an estimate.
UNKNOWN_ESTIMATE_FRACTION = 0.5


def measured_tokens(usage):
    # Cache reads/writes are subsets of input; reasoning is part of output.
    if usage and not usage.get("provisional") and all(type(usage.get(k)) is int and usage[k] >= 0 for k in ("input_tokens", "output_tokens")):
        return usage["input_tokens"] + usage["output_tokens"]
    return None


def provisional_lower_bound(usage):
    """Cumulative counts seen before a lost final chunk: a lower bound only."""
    if usage and all(type(usage.get(k)) is int and usage[k] >= 0 for k in ("input_tokens", "output_tokens")):
        return usage["input_tokens"] + usage["output_tokens"]
    return 0


def unknown_estimate(reserved, usage):
    """Bounded charge for a started call without final usage, else None."""
    if measured_tokens(usage) is not None:
        return None
    floor = math.ceil(max(0, reserved) * UNKNOWN_ESTIMATE_FRACTION)
    return max(provisional_lower_bound(usage), floor)


# A pipeline run holds its expected cost against concurrent admissions for at
# most this long; measured bookings shrink the hold, expiry drops the rest.
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
            if isinstance(hold, dict) and type(hold.get("tokens")) is int and hold["tokens"] > 0
            and isinstance(hold.get("expires_at"), (int, float)) and hold["expires_at"] > now}


def held_tokens(data, now=None):
    return sum(hold["tokens"] for hold in active_holds(data, now).values())


def spent_tokens(data):
    """Measured plus estimated consumption of both modes; holds excluded."""
    return data.get("used", 0) + data.get("estimated", 0) + data.get("pipeline_estimated", 0)


def _remaining(data, limit, now=None):
    return max(0, limit - spent_tokens(data) - data.get("reserved", 0) - held_tokens(data, now))


def admit_run(data, run_id, estimate, *, limit, now=None):
    """Admit one pipeline run if the remaining budget covers its expected cost."""
    data = normalize(data)
    now = _now(now)
    holds = active_holds(data, now)
    if run_id in holds:
        return data
    remaining = _remaining(data, limit, now)
    if estimate > remaining:
        raise AgentTokenBudgetExceeded(remaining, estimate, reserved=data.get("reserved", 0) + held_tokens(data, now))
    if len(holds) >= MAX_PIPELINE_HOLDS:
        raise PipelineCapacityExceeded("Too many runs are starting at once")
    holds[run_id] = {"tokens": int(estimate), "expires_at": now + PIPELINE_HOLD_SECONDS}
    data["pipeline_holds"] = holds
    data["pipeline_runs"] = data.get("pipeline_runs", 0) + 1
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
        left = holds[run_id]["tokens"] - measured - estimated
        if left > 0:
            holds[run_id]["tokens"] = left
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


def reserve(data, amount, *, limit=None):
    data = normalize(data)
    remaining = _remaining(data, daily_limit() if limit is None else limit)
    if amount > remaining:
        raise AgentTokenBudgetExceeded(remaining, amount, reserved=data.get("reserved", 0))
    data["reserved"] = data.get("reserved", 0) + amount
    data["revision"] = data.get("revision", 0) + 1
    return data


def release(data, amount):
    data = normalize(data)
    data["reserved"] = max(0, data.get("reserved", 0) - amount)
    data["revision"] = data.get("revision", 0) + 1
    return data


def settle(data, reserved, usage):
    data = normalize(data)
    actual = measured_tokens(usage)
    data['reserved'] = max(0, data.get('reserved', 0) - reserved)
    if actual is not None:
        data["used"] = data.get("used", 0) + actual
    else:
        # The reservation bound stays auditable as `unknown` and is released;
        # a bounded estimate is charged until reconciliation replaces it.
        data["unknown"] = data.get("unknown", 0) + reserved
        data['unknown_released'] = data.get('unknown_released', 0) + reserved
        data["estimated"] = data.get("estimated", 0) + unknown_estimate(reserved, usage)
    data["revision"] = data.get("revision", 0) + 1
    return data


def reconcile(data, estimate, actual):
    """Replace one charged estimate with measured tokens. Callers fence once."""
    data = normalize(data)
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
    return {"day": day or day_key(), "revision": data.get("revision", 0), "limit": limit, "used": data.get("used", 0),
            "reserved": data.get("reserved", 0) + held_tokens(data, now), "unknown": data.get("unknown", 0),
            "estimated": data.get("estimated", 0) + data.get("pipeline_estimated", 0),
            "remaining": _remaining(data, limit, now)}
