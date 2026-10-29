"""Anonymous daily counters of audit turns (spec A-M1, agent_audit_metrics):
counted once at the turn's end, off its thread, without account or text."""
import json
import threading
from datetime import datetime, timedelta, timezone

import pytest
from google.cloud import firestore

from app.services import agent_audit_metrics as metrics, agent_budget_config
from test_agent_audit import Audit, audit_loop
from test_agent_runs import UID, store  # noqa: F401  (fixture)

START = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _admin_allowance(monkeypatch):
    monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, "pro", 5_000_000)


def at(seconds):
    return (START + timedelta(seconds=seconds)).isoformat()


def test_a_turn_is_counted_by_status_times_halts_and_failures():
    turn = {"status": "completed", "created_at": START, "agent_review": {"mode": "audit", "status": "partial", "audit": {
        "reviewers": [
            {"model": {"model": "openai/gpt-6-luna"}, "status": "completed", "final_ms": 13_400,
             "backlog": {"entries": 4, "steps": 1}},
            {"model": {"model": "xiaomi/mimo-v2.6-flash"}, "status": "failed", "failure": {"code": "review_unreadable"}},
            # Fields of later packages may be missing: their buckets stay empty.
            {"model": {"model": "qwen/qwen3.7"}, "status": "completed"}],
        "issues": [{"code": "reviewers_unavailable", "count": 1}]}}}
    captured = {"ended_at": START + timedelta(seconds=40), "reviewers": 3, "entries": [
        {"at": at(3), "actor": "agent", "kind": "step"},
        {"at": at(7.5), "actor": "app", "kind": "app", "name": "checked", "gate_ms": None},
        {"at": at(9), "actor": "agent", "kind": "step"},
        {"at": at(30), "actor": "app", "kind": "app", "name": "paused", "gate_ms": 11_000},
        {"at": at(32), "actor": "app", "kind": "app", "name": "answer_fixed"}],
        "holds": [{"halt": "injection", "gate": True, "state": "continue"},
                  {"halt": "safety", "state": "steer"}, {"halt": "", "ask": "browser", "state": "handed_back"},
                  {"halt": "domain", "gate": True, "domain": "example.org", "state": "waiting"}]}
    assert metrics.turn_counters(turn, captured) == {
        "turns": {"completed": 1}, "reviewers": {"n3": 1}, "reviews": {"partial": 1},
        "total_s": {"le45": 1}, "answer_s": {"le45": 1}, "marks_s": {"le10": 1},
        # The go after 4.5 s from its step's entry, the halt's own wait.
        "gate_s": {"le5": 1, "le15": 1},
        "reviewer_status": {"completed": 2, "failed": 1},
        "final_s": {"openai_gpt-6-luna": {"le15": 1}}, "backlog_entries": {"le5": 1},
        "failures": {"reviewer": {"review_unreadable": 1}, "review": {"reviewers_unavailable": 1}},
        "halts": {"gate_injection": {"continue": 1}, "safety": {"steer": 1}, "ask_browser": {"handed_back": 1},
                  "domain": {"open": 1}}}
    # The turn's own hold history wins over the activity once it is saved.
    failed = {"status": "failed", "error_code": "cancelled", "created_at": START,
              "agent_failure": {"code": "cancelled"}, "agent_holds": [{"kind": "harm", "decision": "stop"}]}
    counters = metrics.turn_counters(failed, captured)
    assert counters["turns"] == {"cancelled": 1} and counters["failures"] == {"turn": {"cancelled": 1}}
    assert counters["halts"] == {"harm": {"stop": 1}} and "marks_s" not in counters
    # A turn whose chat went meanwhile still counts.
    assert metrics.turn_counters(None, {**captured, "entries": []})["turns"] == {"deleted": 1}


def test_buckets_and_labels_are_plain_field_names():
    assert [metrics.bucket(value) for value in (0, 2, 2.1, 20, 7200, 7201)] == [
        "le2", "le2", "le5", "le20", "le7200", "over7200"]
    assert metrics.label("anthropic/claude-haiku-4.5") == "anthropic_claude-haiku-4_5"
    assert metrics.label(None) == "unknown"


class Recorder:
    """A Firestore stand-in that keeps the one merge it is given."""

    def __init__(self, turn):
        self.turn, self.writes = turn, []

    def get(self):
        return type("Snapshot", (), {"exists": self.turn is not None, "to_dict": lambda _self: self.turn})()

    def collection(self, name):
        return self

    def document(self, name):
        self.document_id = name
        return self

    def set(self, data, merge=False):
        self.writes.append((self.document_id, data, merge))


def test_one_merge_of_increments_per_turn_without_account_or_text():
    turn = {"status": "completed", "created_at": START, "agent_review": {"mode": "audit", "status": "succeeded"}}
    db = Recorder(turn)
    captured = {"ended_at": START + timedelta(seconds=20), "reviewers": 1, "entries": [], "holds": []}
    metrics.write(db, db, captured)
    [(document, data, merge)] = db.writes
    assert document == "agent-audit-2026-10-29" and merge is True and data["day"] == "2026-10-29"
    assert isinstance(data["turns"]["completed"], firestore.Increment)
    assert set(data) == {"turns", "reviewers", "reviews", "total_s", "day", "updated_at"}


def test_an_audit_turn_is_counted_at_its_end_off_its_thread(store, monkeypatch):
    done, seen = threading.Event(), []

    def write(db, turn_ref, captured):
        seen.append((threading.current_thread().name, turn_ref.get().to_dict(), captured))
        done.set()
    monkeypatch.setattr(metrics, "_enabled", lambda: True)
    monkeypatch.setattr(metrics, "write", write)
    script = Audit(tool_steps=1)
    loop = audit_loop(store, script)
    list(loop.run())
    assert done.wait(5)
    [(thread, turn, captured)] = seen
    assert thread == "agent-audit-metrics"
    counters = metrics.turn_counters(turn, captured)
    assert counters["turns"] == {"completed": 1} and counters["reviewers"] == {"n2": 1}
    assert counters["reviews"] == {"succeeded": 1} and counters["reviewer_status"] == {"completed": 2}
    assert {"total_s", "answer_s", "marks_s"} <= set(counters)
    # What the run's thread copied holds no account, chat, turn or text.
    text = json.dumps(captured, default=str)
    assert UID not in text and loop.chat_id not in text and loop.turn_id not in text
    assert "Eiffel" not in text and "lookup" not in text and "claude" not in text
    # Without the setting nothing is counted, and tests never write.
    monkeypatch.undo()
    assert metrics.record(loop) is False
