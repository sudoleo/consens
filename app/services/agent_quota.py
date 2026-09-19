"""UTC-day admission ledger. Measured tokens are input + output, never details.

Unknown provider usage keeps its reservation until the day ends. A paid receipt
is settled once; retries/replay cannot release or charge it again.
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
                   "The daily budget was not empty. Unused reservations are released when the run ends."
                   if remaining else "No Agent tokens were available for the next model call. Running calls and pending usage also reserve tokens. The daily budget resets at 00:00 UTC.")
        super().__init__(message)


def snapshot(db, uid):
    # Timestamp the read's start so a slower HTTP response cannot overwrite a
    # newer terminal snapshot in the browser.
    observed_at = time.time_ns() // 1_000_000
    config = agent_budget_config.get_config(db)
    day = period_key(config)
    return {**public(quota_ref(db, uid, day).get().to_dict(), day.split('_')[0], limit=config['daily_token_limit']),
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
    if usage and all(type(usage.get(k)) is int and usage[k] >= 0 for k in ("input_tokens", "output_tokens")):
        return usage["input_tokens"] + usage["output_tokens"]
    return None


def reserve(data, amount, *, limit=None):
    data = dict(data or {})
    remaining = max(0, (daily_limit() if limit is None else limit) - data.get("used", 0) - data.get("reserved", 0))
    if amount > remaining:
        raise AgentTokenBudgetExceeded(remaining, amount)
    data["reserved"] = data.get("reserved", 0) + amount
    return data


def settle(data, reserved, usage):
    data = dict(data or {})
    actual = measured_tokens(usage)
    if actual is not None:
        data["reserved"] = max(0, data.get("reserved", 0) - reserved)
        data["used"] = data.get("used", 0) + actual
    else:
        data["unknown"] = data.get("unknown", 0) + reserved
    return data


def public(data, day=None, *, limit=None):
    data = data or {}
    limit = daily_limit() if limit is None else limit
    return {"day": day or day_key(), "limit": limit, "used": data.get("used", 0),
            "reserved": data.get("reserved", 0), "unknown": data.get("unknown", 0),
            "remaining": max(0, limit - data.get("used", 0) - data.get("reserved", 0))}
