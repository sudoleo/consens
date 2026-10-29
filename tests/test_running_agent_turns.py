"""scripts/running_agent_turns.py: what a deploy would cut off, offline (A-R10)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from scripts.running_agent_turns import blocking, collect, table

NOW = datetime(2026, 10, 29, 15, tzinfo=timezone.utc)


def root(*, minutes=5, lease=60, hold=None, decided=False, **extra):
    data = {"run_status": "running", "chat_id": "c" * 32, "turn_id": "t" * 32, "step": "completion:0",
            "last_step": "completion:3", "created_at": NOW - timedelta(minutes=minutes),
            "lease_until": NOW + timedelta(seconds=lease), **extra}
    if hold:
        data["hold"] = {"id": "h1", **hold}
        if decided:
            data["hold_decision"] = {"id": "h1", "action": "continue"}
    return data


class Query:
    def __init__(self, docs):
        self.docs = docs

    def where(self, *, filter):
        assert (filter.field_path, filter.op_string) == ("run_status", "==")
        return Query([d for d in self.docs if d.get("run_status") == filter.value])

    def stream(self):
        return [SimpleNamespace(to_dict=lambda d=d: dict(d)) for d in self.docs]


class User:
    def __init__(self, uid, docs):
        self.id, self.docs = uid, docs

    def collection(self, name):
        assert name == "llm_calls"
        return Query(self.docs)


class Db:
    def __init__(self, users):
        self.users = users

    def collection(self, name):
        assert name == "users"
        return SimpleNamespace(list_documents=lambda: self.users)


def test_running_paused_and_stale_turns_without_their_text():
    db = Db([
        User("mWKgPUown", [root(minutes=12)]),
        User("guestuid1", [
            root(hold={"kind": "injection", "reason": "The page asks for the password.", "reviewer": "Luna"}),
            root(hold={"ask": "browser", "request": "Please sign in to the bank."}, decided=True),
            root(lease=-30),
            {**root(), "run_status": "succeeded"}]),
    ])
    turns = collect(db, NOW, workers=2)
    assert [(t["state"], t["account"], t["own"], t["hold"]) for t in turns] == [
        ("paused", "guestu", False, "injection"), ("running", "mWKgPU", True, ""),
        ("running", "guestu", False, ""), ("stale", "guestu", False, "")]
    assert turns[0]["chat"] == "c" * 8 and turns[0]["minutes"] == 5.0 and turns[0]["step"] == "completion:3"
    # A stale turn (no process holds its lease) does not stop a deploy.
    assert len(blocking(turns)) == 3
    text = table(turns)
    assert "password" not in text and "bank" not in text and "Luna" not in text and "guestuid1" not in text
    assert "mWKgPU own" in text
    assert table([]) == "No Agent turn is running or paused."
    assert blocking([t for t in turns if t["state"] == "stale"]) == []
