"""scripts/cache_hit_rate.py: prompt-cache reads and writes from Agent receipts, offline."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from scripts.cache_hit_rate import aggregate, collect, described, totals

NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)


def receipt(step, model, tokens, read=0, write=0, *, agent_id=None, turn="t1", created=NOW):
    usage = {"input_tokens": tokens, "cached_input_tokens": read, "cache_write_tokens": write}
    return {"purpose": "agent", "step": step, "agent_id": agent_id, "chat_id": "c1", "turn_id": turn,
            "model": {"model": model}, "usage": usage, "created_at": created}


def test_counts_reads_and_writes_per_day_family_and_kind():
    receipts = [
        receipt("completion:0", "anthropic/claude-sonnet-5.5", 1000, write=900),
        receipt("completion:1", "anthropic/claude-sonnet-5.5", 1200, read=900, write=250),
        receipt("agent:" + "a" * 32 + ":0", "anthropic/claude-haiku-4.5", 400, write=380, agent_id="a" * 32),
        receipt("agent:" + "b" * 32 + ":0", "openai/gpt-6-luna", 300, read=100, agent_id="b" * 32),
        # A call that failed before the provider answered has no tokens.
        {**receipt("completion:2", "anthropic/claude-sonnet-5.5", 0), "usage": None},
    ]
    agents = {("c1", "t1"): {"a" * 32: {"kind": "judge"}, "b" * 32: {"kind": "comparison"}}}
    rows = aggregate(receipts, agents)
    chat = rows[("2026-10-21", "anthropic", "chat")]
    assert chat == {"calls": 2, "input": 2200, "read": 900, "write": 1150, "writing": 2, "reading": 1}
    assert rows[("2026-10-21", "anthropic", "judge")]["write"] == 380
    assert rows[("2026-10-21", "openai", "comparison")]["reading"] == 1
    # A read saves nine tenths of the input price, a write costs a quarter more.
    assert described("anthropic", chat) == {**chat, "hit": 0.409, "net": round(0.9 * 900 - 0.25 * 1150)}
    assert "net" not in described("openai", rows[("2026-10-21", "openai", "comparison")])
    assert totals(rows)[("anthropic", "chat")]["calls"] == 2


class Query:
    def __init__(self, docs):
        self.docs = docs

    def where(self, *, filter):
        assert filter.op_string == ">="
        return Query([d for d in self.docs if d.get(filter.field_path) and d[filter.field_path] >= filter.value])

    def stream(self):
        return [SimpleNamespace(id=d.get("id", ""), to_dict=lambda d=d: dict(d)) for d in self.docs]


class Ref:
    def __init__(self, data, path=()):
        self.data, self.path = data, path
        self.id = path[-1] if path else ""

    def collection(self, name):
        return Ref(self.data, self.path + (name,))

    def document(self, name):
        return Ref(self.data, self.path + (name,))

    def list_documents(self):
        return [Ref(self.data, self.path + (uid,)) for uid in self.data["users"]]

    def where(self, **kwargs):
        return Query(self.data["docs"].get(self.path, [])).where(**kwargs)

    def stream(self):
        return Query(self.data["docs"].get(self.path, [])).stream()


def test_reads_only_recent_agent_receipts_and_may_leave_out_own_accounts():
    old = NOW - timedelta(days=30)
    worker = "c" * 32
    data = {"users": ["mWKgPUown", "guest"], "docs": {
        ("users", "mWKgPUown", "llm_calls"): [receipt("completion:0", "anthropic/claude-sonnet-5.5", 10)],
        ("users", "guest", "llm_calls"): [
            receipt("completion:0", "anthropic/claude-sonnet-5.5", 10),
            receipt(f"agent:{worker}:0", "anthropic/claude-sonnet-5.5", 20, agent_id=worker),
            receipt("completion:0", "anthropic/claude-sonnet-5.5", 30, created=old),
            {**receipt("completion:0", "openai/gpt-6-luna", 40), "purpose": "consensus"}],
        ("users", "guest", "chats", "c1", "turns", "t1", "agents"): [{"id": worker, "kind": "comparison"}],
    }}
    since = NOW - timedelta(days=7)
    receipts, agents = collect(Ref(data), since)
    assert sorted(r["usage"]["input_tokens"] for r in receipts) == [10, 10, 20]
    assert agents == {("c1", "t1"): {worker: {"id": worker, "kind": "comparison"}}}
    receipts, _ = collect(Ref(data), since, exclude_own=True)
    assert sorted(r["usage"]["input_tokens"] for r in receipts) == [10, 20]
    receipts, _ = collect(Ref(data), since, family_filter="openai")
    assert receipts == []
