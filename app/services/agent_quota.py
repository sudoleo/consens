"""UTC-day allowance in micro-euros, shared by Agent and the Consensus pipeline in one ledger
document per account and period; the limit comes from the tier. Every call is charged what it cost:
the provider's dollar cost (cache, reasoning and search included), else its catalog price
(measured_charge).

Agent reserves a call's expected cost before it starts and settles with measured usage. The pipeline
is admitted per run against a typical run's cost, holds that estimate while young and books every
finished operation. A run may push the account slightly below zero and the next admission then
fails; the overdraft stays bounded because only runs with enough budget are admitted and each holds
its estimate against concurrent admissions. A paid receipt is settled once.

A started call whose final usage is missing is neither fully released nor fully charged: a bounded
estimate is charged in its own ``estimated`` bucket, counted against ``remaining``, until the
provider's real cost replaces it exactly once. Calls that provably never started settle as a
measured zero."""
import math
import threading
import time
from datetime import datetime, timedelta, timezone

from app.services.llm.provider_runtime import AnalysisBudgetExceeded
from app.services import agent_budget_config


class AgentTokenBudgetExceeded(AnalysisBudgetExceeded):
    """``remaining``, ``required`` and ``reserved`` in micro-euros. The codes keep their
    token-account names (browser and API contract)."""

    def __init__(self, remaining, required, *, reserved=0):
        self.remaining, self.required = remaining, required
        self.reserved = reserved
        self.code = "agent_token_reservation" if remaining else "agent_tokens_exhausted"
        message = ("The next model call needed more of today's allowance than was available at that point. "
                   "Some allowance may be reserved for active calls. Completed calls release their reservations."
                   if remaining else "Nothing was left in today's allowance for the next model call. Active calls temporarily reserve part of it. The daily allowance resets at 00:00 UTC.")
        super().__init__(message)


# Serialize short bookkeeping transactions per account inside each process; Firestore still fences
# concurrent processes.
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
    """Ledger tier of an account: admin role first, then the stored tier. Raises
    TierStatusUnavailable on storage errors, which callers map to 503 instead of using another
    tier's limit."""
    tier = _stored_tier(uid) if tier is None else tier
    return agent_budget_config.tier_key(tier, admin=_admin_role(uid))


# snapshot() runs on every allowance poll and usage event, and both extra reads mostly find nothing:
# an owner without running runs is asked again after RECOVERY_QUIET_S, and yesterday is no longer
# read for estimates after PREVIOUS_DAY_GRACE.
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
    # So a slower HTTP response cannot overwrite a newer snapshot in the browser.
    observed_at = time.time_ns() // 1_000_000
    config = agent_budget_config.get_config(db)
    day = period_key(config)
    data = quota_ref(db, uid, day).get().to_dict() or {}
    if data.get('unknown', 0) > data.get('unknown_released', 0):
        data = store.repair_quota_period(uid, day)
    if awaits_measurement(data) or _previous_day_has_estimates(db, uid, day):
        # Provider usage lookups run off the request thread; a later snapshot shows the result.
        # Yesterday too, so a call estimated just before midnight is still measured.
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


def shown_allowance(db, uid, *, tier=None):
    """``(left, limit)`` as the sidebar ring shows it: the limit less what was spent, not less what
    running calls hold."""
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


# Token-account ledgers have no suffix: a call reserved in tokens settles into its own ledger, never
# into the euro one.
LEDGER_UNIT = "_eur"


def period_key(config):
    # Receipts retain this key, so calls started before a reset settle into the old ledger.
    return day_key() + ("_" + config['reset_epoch'] if config.get('reset_epoch') else "") + LEDGER_UNIT


def quota_ref(db, uid, day):
    return db.collection("users").document(uid).collection("chat_state").document("agent_tokens_" + day)


UNKNOWN_ESTIMATE_FRACTION = 0.5


def measured_charge(usage):
    """What a measured call takes from the account in micro-euros, or None when its cost is not
    final."""
    if not usage or usage.get("provisional") or not usage.get("cost_complete", usage.get("complete", True)):
        return None
    cost = usage.get("estimated_cost_nano_usd")
    return agent_budget_config.micro_eur(cost) if type(cost) is int and cost >= 0 else None


def provisional_lower_bound(usage):
    """The cost of the counts seen before a lost final chunk: a lower bound only."""
    cost = (usage or {}).get("estimated_cost_nano_usd")
    return agent_budget_config.micro_eur(cost) if type(cost) is int and cost >= 0 else 0


def unknown_estimate(reserved, usage, *, expected=0):
    """Bounded charge for a started call without a final cost, else None: the lower bound, at least
    UNKNOWN_ESTIMATE_FRACTION of ``reserved``, and ``expected`` for a run that lost its process."""
    if measured_charge(usage) is not None:
        return None
    floor = math.ceil(max(0, reserved) * UNKNOWN_ESTIMATE_FRACTION)
    return max(provisional_lower_bound(usage), floor, max(0, int(expected or 0)))


# A pipeline run holds its expected cost at most this long; measured bookings shrink the hold. The
# admission lapses with it, so a run cannot bank its admission for hours, and at most
# MAX_PIPELINE_HOLDS runs per account are admitted and unchecked.
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
    """Admit one pipeline run if the remaining budget covers its expected cost; ``readmission`` (a
    lapsed admission) is counted apart."""
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
    """Release legacy terminal holds exactly once without touching live holds. These are reservation
    bounds, never invented measured counts."""
    data = dict(data or {})
    pending = max(0, data.get('unknown', 0) - data.get('unknown_released', 0))
    if pending:
        data['reserved'] = max(0, data.get('reserved', 0) - pending)
        data['unknown_released'] = data['unknown']
        data['revision'] = data.get('revision', 0) + 1
    return data


def reserve(data, amount, *, limit=None, overdraft=False):
    """Hold ``amount`` for an active call. ``overdraft`` admits it beyond the limit (finishing an
    Agent message with paid work); the next admission then fails."""
    data = normalize(data)
    remaining = _remaining(data, daily_limit() if limit is None else limit)
    if not overdraft and amount > remaining:
        raise AgentTokenBudgetExceeded(remaining, amount, reserved=data.get("reserved", 0))
    data["reserved"] = data.get("reserved", 0) + amount
    data["revision"] = data.get("revision", 0) + 1
    return data


def settle(data, reserved, usage, *, measurable=False, expected=0):
    """Swap a call's reservation for its charge. ``measurable``: an estimate charged instead can
    still be measured later; ``expected`` as for unknown_estimate."""
    data = normalize(data)
    actual = measured_charge(usage)
    data['reserved'] = max(0, data.get('reserved', 0) - reserved)
    data.setdefault("estimates_pending", 0)
    if actual is not None:
        data["used"] = data.get("used", 0) + actual
    else:
        # The reservation bound stays auditable as `unknown`; a bounded estimate is charged until
        # reconciliation replaces it.
        data["unknown"] = data.get("unknown", 0) + reserved
        data['unknown_released'] = data.get('unknown_released', 0) + reserved
        data["estimated"] = data.get("estimated", 0) + unknown_estimate(reserved, usage, expected=expected)
        if measurable:
            data["estimates_pending"] += 1
    data["revision"] = data.get("revision", 0) + 1
    return data


# How many estimates still wait for their measurement: one that can never be measured stays charged
# for good, and the amount alone kept snapshot() looking all day.
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


# What the account's model calls took in all (the admin's lookup), counted in the ledger that claims
# and settlements write anyway: on the user document it cost two more writes per call.
USAGE_SUMS = ("input_tokens", "output_tokens", "cached_input_tokens", "cache_write_tokens", "reasoning_tokens",
              "estimated_cost_nano_usd")


def count_claim(data):
    """A call claimed against a day's ledger: counted, unsettled."""
    totals = dict(data.get("agent_usage") or {})
    totals["calls"] = totals.get("calls", 0) + 1
    totals["unsettled_calls"] = totals.get("unsettled_calls", 0) + 1
    data["agent_usage"] = totals
    return data


def count_settlement(data, usage):
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
    """The account's sums over all its day ledgers, added to ``legacy`` (the user document's former
    counters). Reads every ledger: for the admin's lookup only."""
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
    # `estimated`: charged without a final measurement; `reserved`: held for running work (both
    # modes).
    return {"day": day or day_key(), "unit": "micro_eur", "revision": data.get("revision", 0), "limit": limit,
            "used": data.get("used", 0),
            "reserved": data.get("reserved", 0) + held_amount(data, now), "unknown": data.get("unknown", 0),
            "estimated": data.get("estimated", 0) + data.get("pipeline_estimated", 0),
            "remaining": _remaining(data, limit, now)}
