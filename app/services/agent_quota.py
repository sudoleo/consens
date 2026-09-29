"""UTC-day admission ledger. Measured tokens are input + output, never details.

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
                   if remaining else "No Agent tokens were available for the next model call. Active calls temporarily reserve tokens. The daily budget resets at 00:00 UTC.")
        super().__init__(message)


def snapshot(db, uid):
    from app.services.agent_runs import AgentRunStore
    store = AgentRunStore(db)
    store.recover_allowance(uid)
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
    return {**public(data, day.split('_')[0], limit=config['daily_token_limit']),
            "observed_at": observed_at, "config_revision": config['revision']}


def _previous_day_has_estimates(db, uid, day):
    try:
        today = datetime.strptime(day.split('_')[0], "%Y-%m-%d")
    except ValueError:
        return False
    suffix = day[len(day.split('_')[0]):]
    previous = (today - timedelta(days=1)).strftime("%Y-%m-%d") + suffix
    try:
        return (quota_ref(db, uid, previous).get().to_dict() or {}).get('estimated', 0) > 0
    except Exception:
        return False


def daily_limit():
    return agent_budget_config.default_limit()


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


def _remaining(data, limit):
    return max(0, limit - data.get("used", 0) - data.get("reserved", 0) - data.get("estimated", 0))


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


def public(data, day=None, *, limit=None):
    data = normalize(data)
    limit = daily_limit() if limit is None else limit
    return {"day": day or day_key(), "revision": data.get("revision", 0), "limit": limit, "used": data.get("used", 0),
            "reserved": data.get("reserved", 0), "unknown": data.get("unknown", 0),
            "estimated": data.get("estimated", 0),
            "remaining": _remaining(data, limit)}
