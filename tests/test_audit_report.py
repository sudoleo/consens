"""scripts/audit_report.py: the spec's tables and targets from fake turns,
receipts and daily counters, offline (A-M8)."""
from datetime import datetime, timedelta, timezone

from scripts.audit_report import quantiles, render, report

T0 = datetime(2026, 10, 29, 10, tzinfo=timezone.utc)
OWN, GUEST = "mWKgPUowner", "guestaccount"
LUNA, FLASH, TERRA = "openai/gpt-6-luna", "xiaomi/mimo-v2.6-flash", "openai/gpt-6.1-terra"


def at(seconds):
    return T0 + timedelta(seconds=seconds)


def receipt(account, turn, step, model, start, end, *, agent_id=None, status="succeeded", quota=100, cost=1_000_000,
            **extra):
    return {"account": account, "own": account.startswith("mWKgPU"), "chat": "c1", "turn": turn, "step": step,
            "agent_id": agent_id, "model": model, "created_at": at(start), "settled_at": at(end), "status": status,
            "input": 1000, "cached": 800, "output": 50, "cost": cost, "quota_charged": quota, **extra}


def log(*entries):
    return [{"seq": n + 1, "at": at(seconds).isoformat(), **entry} for n, (seconds, entry) in enumerate(entries)]


def turn(*, status="completed", reviewers, holds=(), entries=(), agents=(), vm=False, error_code=None):
    return {"audit": True, "status": status, "error_code": error_code, "failure": None, "created_at": T0,
            "completed_at": None, "failed_at": None, "updated_at": None, "model": TERRA,
            "preferences": {"audit": "on"}, "comparison_models": len(reviewers), "vm": vm, "holds": list(holds),
            "review": {"mode": "audit", "status": "succeeded" if status == "completed" else "cancelled",
                       "reviewers": [{"model": m, "status": "completed", "failure": None} for m in reviewers],
                       "issues": []},
            "agents": list(agents), "log": log(*entries)}


def data():
    reviewer, flash = "a" * 32, "b" * 32
    turns = {
        # A turn with a gate, a halt and a step that searched without a hit.
        (OWN, "c1", "t1"): turn(reviewers=[LUNA, FLASH], holds=[
            {"kind": "injection", "gate": True, "decision": "continue"}], entries=[
            (2, {"actor": "agent", "kind": "step", "model": TERRA, "searches": 2, "hits": 0}),
            (6, {"actor": "app", "kind": "app", "name": "checked", "gate_ms": None}),
            (8, {"actor": "agent", "kind": "step", "model": TERRA, "searches": 1, "hits": 3}),
            (9, {"actor": "app", "kind": "app", "name": "paused", "gate_ms": 12_000}),
            (20, {"actor": "app", "kind": "app", "name": "decision"}),
            (30, {"actor": "app", "kind": "app", "name": "answer_fixed"})],
            agents=[{"id": reviewer, "kind": "audit", "status": "completed", "created_at": at(1).isoformat()},
                    {"id": flash, "kind": "audit", "status": "completed", "created_at": at(1).isoformat()}]),
        # A turn stopped before its answer, with a live round that failed.
        (GUEST, "c1", "t2"): turn(status="failed", error_code="cancelled", reviewers=[LUNA], agents=[
            {"id": "c" * 32, "kind": "audit", "status": "failed", "created_at": at(3).isoformat()}]),
        # A chat deleted since: only its receipts are left.
        (GUEST, "c1", "t3"): None,
    }
    receipts = [
        {**receipt(OWN, "t1", "completion:0", TERRA, 0, 3, quota=300, cost=3_000_000), "finished_at": at(42)},
        receipt(OWN, "t1", "completion:1", TERRA, 7, 29, quota=300, cost=3_000_000),
        receipt(OWN, "t1", f"agent:{reviewer}:0", LUNA, 3, 7, agent_id=reviewer),
        receipt(OWN, "t1", f"agent:{flash}:0", FLASH, 3, 5, agent_id=flash),
        # Their final rounds, after the answer was fixed (at 30 s); one by its round.
        receipt(OWN, "t1", f"agent:{reviewer}:1", LUNA, 30.5, 41, agent_id=reviewer),
        receipt(OWN, "t1", f"agent:{flash}:1", FLASH, 31, 33, agent_id=flash, round="final"),
        {**receipt(GUEST, "t2", "completion:0", TERRA, 0, 4), "finished_at": at(5)},
        receipt(GUEST, "t3", "agent:" + "d" * 32 + ":0", LUNA, 3, 6, agent_id="d" * 32, session_kind="audit"),
        receipt(GUEST, "t3", "completion:0", TERRA, 0, 2, searches=1, search_hits=0),
    ]
    counters = [{"day": "2026-10-29", "turns": {"completed": 4}, "marks_s": {"le10": 3, "le30": 1}},
                {"day": "2026-10-30", "turns": {"completed": 1, "failed": 1}}]
    return {"receipts": receipts, "turns": turns, "counters": counters, "since": T0 - timedelta(days=5)}


def test_the_spec_tables_and_targets_from_turns_receipts_and_counters():
    result = report(data())
    assert result["data"] == {"audit_turns": 2, "own": 1, "other": 1, "deleted": {"audit": 1},
                              "reviewers_per_turn": {1: 1, 2: 1}}
    assert result["status"]["turns"] == {"completed": 1, "cancelled": 1}
    assert result["status"]["live_rounds"] == {"total": 2, "failed": 1}
    times = result["times"]
    assert times["total"]["p50"] == 42 and times["to_answer"]["p50"] == 30
    assert times["marks_after_last_word"] == {"n": 1, "p50": 12, "p90": 12, "max": 12}
    # 11 s of the turn waited for the user: not part of the work.
    assert times["total_without_pauses"]["p50"] == 31
    assert times["final_round_by_model"] == {FLASH: {"n": 1, "p50": 2, "p90": 2, "max": 2},
                                             LUNA: {"n": 1, "p50": 10.5, "p90": 10.5, "max": 10.5}}
    assert times["live_request_by_model"][LUNA]["p50"] == 4
    # The go 4 s after its step, the gate halt by its own wait.
    assert result["gate"] == {"rounds": 2, "results": {"go": 1, "injection": 1},
                              "wait": {"n": 2, "p50": 8, "p90": 12, "max": 12}}
    assert result["halts"]["by_kind_and_decision"] == {"gate:injection -> continue": 1}
    tokens = result["tokens"]
    assert tokens["agent"]["calls"] == 3 and tokens["reviewer"]["calls"] == 4
    assert tokens["reviewer_final"]["calls"] == 2 and tokens["reviewer"]["cached_share"] == .8
    # Reviewers: 400 of 1,100 allowance tokens, 4 of 11 dollars spent.
    assert result["quota"]["reviewer_share"] == result["quota"]["reviewer_cost_share"] == .364
    assert {(s["model"], s["source"]): (s["without_hits"], s["steps"]) for s in result["search"]} == {
        (TERRA, "receipts"): (1, 1), (TERRA, "work_log"): (1, 2)}
    assert result["counters"] == {"days": ["2026-10-29", "2026-10-30"], "turns": {"completed": 5, "failed": 1},
                                  "marks_s": {"le10": 3, "le30": 1}}
    targets = {t["id"]: t for t in result["targets"]}
    # 12 s of marks after the last word miss Z1's median; a gate at p90 12 s misses Z5.
    assert targets["Z1"]["ok"] is False and targets["Z5"]["ok"] is False
    assert targets["Z2"]["value"]["share"] == 1.0 and targets["Z3"]["ok"] and targets["Z6"]["ok"]
    assert targets["Z7"]["ok"] is None and targets["Z8"]["value"] == .364
    assert result["release"]["turns"] == 2 and result["release"]["three_reviewers"] == 0
    text = render(result)
    assert "Z5 MISSED" in text and "Z3 ok" in text and "Z7 -" in text
    # The report never names an account or a chat.
    assert OWN not in text and GUEST not in text and "c1" not in text


def test_quantiles_by_nearest_rank():
    assert quantiles([]) == {"n": 0, "p50": None, "p90": None, "max": None}
    assert quantiles([5, 1, None, 3, 2, 4, 10, 9, 8, 7, 6]) == {"n": 10, "p50": 5.5, "p90": 9, "max": 10}
