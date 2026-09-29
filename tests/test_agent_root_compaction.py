"""R29: the per-turn root receipt stays bounded however many steps run.

Settled steps are folded out of step_states/step_usage/reservations once they
leave a fixed window; each step keeps its own immutable llm_calls receipt, so
no usage or history is lost and running leases are never compacted.
"""
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services import agent_quota, agent_sessions
from app.services.agent_costs import aggregate_usage
from app.services.agent_sessions import ROOT_MAX_BYTES, ROOT_SETTLED_STEP_WINDOW, root_usage
from app.services.llm.agent_client import AgentCompletion, measured_usage
from app.services.llm.provider_runtime import AnalysisBudgetExceeded
from test_agent_runs import UID, store, totals
from test_agent_continuation import chat_loop


def measured(model, prompt=100, completion=20):
    value = AgentCompletion()
    value.text, value.finish_reason = "ok", "stop"
    value.usage = measured_usage({"prompt_tokens": prompt, "completion_tokens": completion, "cost": .001}, model)
    return value


def root_of(store, loop):
    return store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()


def size(value):
    return len(json.dumps(value, default=str).encode("utf-8"))


def test_hundreds_of_sequential_steps_keep_the_root_bounded_without_losing_usage(store):
    loop = chat_loop(store, AgentCompletion)
    args = (UID, loop.chat_id, loop.turn_id)
    steps = 10 * ROOT_SETTLED_STEP_WINDOW + 7
    sizes = []
    for index in range(steps):
        step = f"completion:{index}"
        assert store.claim(*args, loop.model, step=step, run_token=loop.run_token,
                           policy=loop.policy.snapshot(), reservation=(500, 100))
        store.settle(*args, completion=measured(loop.model), status="succeeded", step=step, final=False)
        if index % 50 == 49:
            sizes.append(size(root_of(store, loop)))

    root = root_of(store, loop)
    assert len(root["step_states"]) == len(root["step_usage"]) == ROOT_SETTLED_STEP_WINDOW
    assert len(root["reservations"]) == ROOT_SETTLED_STEP_WINDOW
    assert root["compacted_steps"] == steps - ROOT_SETTLED_STEP_WINDOW
    assert max(sizes) < ROOT_MAX_BYTES and max(sizes) - min(sizes) < 1024  # flat, not growing
    assert root["step_states"][f"completion:{steps - 1}"] == "succeeded"
    assert root["reserved_tokens"] == steps * 120  # exact reconciled total

    usage = root_usage(root)
    assert usage["input_tokens"] == steps * 100 and usage["output_tokens"] == steps * 20
    assert usage["measured_calls"] == steps and usage["unmetered_calls"] == 0 and usage["complete"]
    assert store.delegation_view(*args)["usage"]["input_tokens"] == steps * 100
    # Ledger and per-step receipts are untouched by compaction.
    assert agent_quota.snapshot(store.db, UID)["used"] == steps * 120
    assert totals(store)["calls"] == steps and totals(store)["unsettled_calls"] == 0
    for index in (0, steps // 2, steps - 1):
        receipt = store.receipt_ref(*args, step=f"completion:{index}").get().to_dict()
        assert receipt["status"] == "succeeded" and receipt["usage"]["input_tokens"] == 100


def test_compacted_previous_step_still_authorizes_the_next_step_and_replays_are_refused(store):
    loop = chat_loop(store, AgentCompletion)
    args = (UID, loop.chat_id, loop.turn_id)
    for index in range(ROOT_SETTLED_STEP_WINDOW + 3):
        step = f"completion:{index}"
        store.claim(*args, loop.model, step=step, run_token=loop.run_token,
                    policy=loop.policy.snapshot(), reservation=(10, 1))
        store.settle(*args, completion=measured(loop.model), status="succeeded", step=step, final=False)
    root = root_of(store, loop)
    assert "completion:0" not in root["step_states"]
    # A compacted step can never be claimed (and paid) a second time.
    assert store.claim(*args, loop.model, step="completion:0", run_token=loop.run_token,
                       policy=loop.policy.snapshot(), reservation=(10, 1)) is False
    assert not store.settle(*args, completion=measured(loop.model), status="succeeded",
                            step="completion:0", final=False)
    assert agent_quota.snapshot(store.db, UID)["used"] == (ROOT_SETTLED_STEP_WINDOW + 3) * 120


def test_parallel_worker_settlements_keep_running_leases_and_exact_usage(store):
    loop = chat_loop(store, AgentCompletion)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, step="completion:0", run_token=loop.run_token,
                policy=loop.policy.snapshot(), reservation=(10, 1))
    workers = [f"{index:032x}" for index in range(1, 5)]
    for aid in workers:
        store.publish_agent(*args, run_token=loop.run_token, agent_id=aid,
                            patch={"assignment": {"goal": "Verify"}, "status": "working", "kind": "comparison"})
    per_worker = 40

    def run_worker(aid):
        for index in range(per_worker):
            step = f"agent:{aid}:{index}"
            assert store.claim(*args, loop.model, step=step, run_token=loop.run_token,
                               policy=loop.policy.snapshot(), reservation=(50, 1))
            store.settle(*args, completion=measured(loop.model), status="succeeded", step=step, final=False)

    with ThreadPoolExecutor(max_workers=len(workers)) as pool:
        list(pool.map(run_worker, workers))

    root = root_of(store, loop)
    # The orchestrator's live step was never compacted, whatever settled around it.
    assert root["step_states"]["completion:0"] == "running"
    assert "completion:0" in root["reservations"]
    assert len(root["step_states"]) <= ROOT_SETTLED_STEP_WINDOW + 1
    total = len(workers) * per_worker
    assert root["compacted_steps"] + len(root["step_usage"]) == total
    usage = root_usage(root)
    assert usage["measured_calls"] == total and usage["input_tokens"] == total * 100
    assert agent_quota.snapshot(store.db, UID)["reserved"] == 10
    assert agent_quota.snapshot(store.db, UID)["used"] == total * 120


def test_oversized_root_is_a_saved_resumable_stop_not_a_write_failure(store, monkeypatch):
    loop = chat_loop(store, AgentCompletion)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, step="completion:0", run_token=loop.run_token,
                policy=loop.policy.snapshot(), reservation=(10, 1))
    store.settle(*args, completion=measured(loop.model), status="succeeded", step="completion:0", final=False)
    monkeypatch.setattr(agent_sessions, "ROOT_MAX_BYTES", 10)
    before = agent_quota.snapshot(store.db, UID)
    with pytest.raises(AnalysisBudgetExceeded, match="technical limit"):
        store.claim(*args, loop.model, step="completion:1", run_token=loop.run_token,
                    policy=loop.policy.snapshot(), reservation=(10, 1))
    # Nothing was reserved or started; the turn can still be finished and saved.
    assert not store.receipt_ref(*args, step="completion:1").get().exists
    assert agent_quota.snapshot(store.db, UID)["reserved"] == before["reserved"]
    from app.services.agent_provider_limits import agent_failure
    failure = agent_failure(AnalysisBudgetExceeded(agent_sessions.TECHNICAL_STEP_LIMIT))
    assert failure["code"] == "run_limit" and "follow-up message" in failure["error"]


def test_aggregates_compose_with_earlier_aggregates_and_unknown_calls():
    model_usage = measured_usage({"prompt_tokens": 10, "completion_tokens": 5}, __import__(
        "app.services.llm.agent_client", fromlist=["AgentModel"]).AgentModel())
    first = aggregate_usage([model_usage, None])
    combined = aggregate_usage([first, model_usage])
    assert combined["measured_calls"] == 2 and combined["unmetered_calls"] == 1
    assert combined["input_tokens"] == 20 and not combined["complete"]
    assert aggregate_usage([first])["measured_calls"] == 1


def test_reaping_after_compaction_keeps_every_worker_step_usage(store):
    from datetime import datetime, timedelta, timezone
    loop = chat_loop(store, AgentCompletion)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, step="completion:0", run_token=loop.run_token,
                policy=loop.policy.snapshot(), reservation=(10, 1))
    aid = "a" * 32
    store.publish_agent(*args, run_token=loop.run_token, agent_id=aid,
                        patch={"assignment": {"goal": "Verify"}, "status": "working", "kind": "comparison"})
    steps = ROOT_SETTLED_STEP_WINDOW + 5
    for index in range(steps):
        step = f"agent:{aid}:{index}"
        store.claim(*args, loop.model, step=step, run_token=loop.run_token,
                    policy=loop.policy.snapshot(), reservation=(50, 1))
        store.settle(*args, completion=measured(loop.model), status="succeeded", step=step, final=False)
    root_ref = store.receipt_ref(*args)
    store._transaction(lambda tx: tx.update(root_ref, {"lease_until": datetime.now(timezone.utc) - timedelta(seconds=1)}))
    store.reap_delegation(*args)
    session = store.agent_ref(*args, aid).get().to_dict()
    assert session["status"] == "stopped"
    assert session["usage"]["measured_calls"] == steps
    assert session["usage"]["input_tokens"] == steps * 100
    turn = store.get_turn(*args)
    assert turn["status"] == "failed"
    # All worker steps plus the reaped, unmeasured orchestrator step.
    assert turn["agent_usage"]["measured_calls"] == steps and turn["agent_usage"]["unmetered_calls"] == 1


def test_unmetered_first_fold_keeps_its_call_count():
    from app.services.agent_sessions import ROOT_SETTLED_STEP_WINDOW, compact_root, root_usage
    total = ROOT_SETTLED_STEP_WINDOW + 3
    data = {"step_states": {f"completion:{i}": "succeeded" for i in range(total)},
            "step_usage": {f"completion:{i}": None for i in range(total)}, "reservations": {}}
    first = compact_root({}, data)
    assert first["compacted_usage"]["unmetered_calls"] == 3
    # A later fold with a measured step must still count the unmetered ones.
    data = {**first, "step_states": {**first["step_states"], **{f"completion:{i}": "succeeded" for i in range(total, total + 2)}},
            "step_usage": {**first["step_usage"], f"completion:{total}": {"input_tokens": 10, "output_tokens": 2},
                           f"completion:{total + 1}": None}}
    second = compact_root({}, data)
    usage = root_usage(second)
    assert usage["complete"] is False
    assert usage["measured_calls"] + usage["unmetered_calls"] == total + 2
