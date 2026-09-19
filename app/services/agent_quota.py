"""UTC-day admission ledger. Measured tokens are input + output, never details.

Unknown provider usage keeps its reservation until the day ends. A paid receipt
is settled once; retries/replay cannot release or charge it again.
"""
import os
from datetime import datetime, timezone

from app.services.llm.provider_runtime import AnalysisBudgetExceeded


def daily_limit():
    value = int(os.getenv("AGENT_DAILY_TOKEN_LIMIT", "250000"))
    if value < 1:
        raise ValueError("AGENT_DAILY_TOKEN_LIMIT must be positive")
    return value


def day_key():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def quota_ref(db, uid, day):
    return db.collection("users").document(uid).collection("chat_state").document("agent_tokens_" + day)


def measured_tokens(usage):
    # Cache reads/writes are subsets of input; reasoning is part of output.
    if usage and all(type(usage.get(k)) is int and usage[k] >= 0 for k in ("input_tokens", "output_tokens")):
        return usage["input_tokens"] + usage["output_tokens"]
    return None


def reserve(data, amount):
    data = dict(data or {})
    if data.get("used", 0) + data.get("reserved", 0) + amount > daily_limit():
        raise AnalysisBudgetExceeded("Agent daily token budget reached. It resets at 00:00 UTC.")
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


def public(data, day=None):
    data = data or {}
    return {"day": day or day_key(), "limit": daily_limit(), "used": data.get("used", 0),
            "reserved": data.get("reserved", 0), "unknown": data.get("unknown", 0),
            "remaining": max(0, daily_limit() - data.get("used", 0) - data.get("reserved", 0))}
