"""UTC-day admission ledger. Measured tokens are input + output, never details.

Reservations protect active calls only. Missing final usage remains auditable,
but a completed call cannot keep the account locked until the next UTC day.
A paid receipt is settled once; retries cannot release or charge it again.
"""
import time
from datetime import datetime, timezone

from app.services.llm.provider_runtime import AnalysisBudgetExceeded
from app.services import agent_budget_config


class AgentTokenBudgetExceeded(AnalysisBudgetExceeded):
    def __init__(self, remaining, required):
        self.remaining, self.required = remaining, required
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
    return {**public(data, day.split('_')[0], limit=config['daily_token_limit']),
            "observed_at": observed_at, "config_revision": config['revision']}


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


def measured_tokens(usage):
    # Cache reads/writes are subsets of input; reasoning is part of output.
    if usage and not usage.get("provisional") and all(type(usage.get(k)) is int and usage[k] >= 0 for k in ("input_tokens", "output_tokens")):
        return usage["input_tokens"] + usage["output_tokens"]
    return None


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
    remaining = max(0, (daily_limit() if limit is None else limit) - data.get("used", 0) - data.get("reserved", 0))
    if amount > remaining:
        raise AgentTokenBudgetExceeded(remaining, amount)
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
        data["unknown"] = data.get("unknown", 0) + reserved
        data['unknown_released'] = data.get('unknown_released', 0) + reserved
    data["revision"] = data.get("revision", 0) + 1
    return data


def public(data, day=None, *, limit=None):
    data = normalize(data)
    limit = daily_limit() if limit is None else limit
    return {"day": day or day_key(), "revision": data.get("revision", 0), "limit": limit, "used": data.get("used", 0),
            "reserved": data.get("reserved", 0), "unknown": data.get("unknown", 0),
            "remaining": max(0, limit - data.get("used", 0) - data.get("reserved", 0))}
