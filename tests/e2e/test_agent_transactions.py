"""Agent admission and accounting races against the isolated Firestore emulator."""
from concurrent.futures import ThreadPoolExecutor
import threading
import uuid

from google.cloud import firestore

from app.core.e2e_profile import E2E_PROJECT_ID, assert_safe_e2e_environment
from app.services.account_deletion import FirestoreAccountDeletion
from app.services.agent_runs import AgentRunStore
from app.services.agent_policy import AgentPolicy
from app.services.agent_runtime import AgentCapacityExceeded
from app.services.llm.agent_client import AgentModel, AgentCompletion, measured_usage
from app.services.agent_delegation_config import defaults
from app.services.llm.provider_runtime import AnalysisBudgetExceeded
from app.services import agent_quota


def test_daily_token_admission_and_idempotent_settlement_in_firestore(monkeypatch):
    assert_safe_e2e_environment()
    monkeypatch.setenv("AGENT_DAILY_TOKEN_LIMIT", "100")
    db = firestore.Client(project=E2E_PROJECT_ID)
    uid = "agent-token-race-" + uuid.uuid4().hex
    store, model = AgentRunStore(db), AgentModel()
    config = defaults()
    config["enabled"] = True
    policy = AgentPolicy.from_config(config)
    try:
        identities = []
        for i in range(2):
            chat = store.create_chat(uid, execution_mode="agent")["id"]
            turn = store.create_turn(uid, chat, question="Budget race", mode="Agent", deep_search=False,
                selected_models=[model.model], consensus_model=model.model, client_request_id=str(i), execution_mode="agent")["id"]
            identities.append((uid, chat, turn))
        def claim(args):
            try:
                return AgentRunStore(db).claim(*args, model, run_token=args[1], policy=policy.snapshot(), reservation=(60, 100))
            except AnalysisBudgetExceeded:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            admitted = list(pool.map(claim, identities))
        assert sum(admitted) == 1
        args = identities[admitted.index(True)]
        value = AgentCompletion()
        value.usage = measured_usage({"prompt_tokens": 10, "completion_tokens": 5,
            "prompt_tokens_details": {"cached_tokens": 5}, "completion_tokens_details": {"reasoning_tokens": 4}}, model)
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sum(pool.map(lambda _: AgentRunStore(db).settle(*args, completion=value,
                status="cancelled", final=False), range(2))) == 1
        quota = agent_quota.quota_ref(db, uid, agent_quota.day_key()).get().to_dict()
        assert quota["used"] == 15 and quota["reserved"] == 0
        assert quota['revision'] == 2  # one admitted call, one settlement despite retries
        store.finish_run(*args, completion=value, status="cancelled", run_token=args[1])
        store.delete_chat(uid, args[1])
        assert agent_quota.quota_ref(db, uid, agent_quota.day_key()).get().to_dict()["used"] == 15
    finally:
        FirestoreAccountDeletion(db)._delete_user_subcollections(uid)
        db.collection("users").document(uid).delete()
        db.close()


def test_delegation_budget_journal_and_receipts_are_atomic_in_firestore():
    assert_safe_e2e_environment()
    db = firestore.Client(project=E2E_PROJECT_ID)
    uid = "delegation-race-" + uuid.uuid4().hex
    store, model = AgentRunStore(db), AgentModel()
    try:
        chat = store.create_chat(uid, execution_mode="agent")["id"]
        turn = store.create_turn(uid, chat, question="Two workers", mode="Agent", deep_search=False,
            selected_models=[model.model], consensus_model=model.model, client_request_id="delegation", execution_mode="agent")["id"]
        config = defaults()
        config["enabled"] = True
        config["max_cost_nano_usd"] = 100
        policy = AgentPolicy.from_config(config)
        args = (uid, chat, turn)
        assert store.claim(*args, model, run_token=uid, policy=policy.snapshot(), reservation=(1, 10))
        completion = AgentCompletion()
        store.settle(*args, completion=completion, status="succeeded", final=False)
        ids = [uuid.uuid4().hex, uuid.uuid4().hex]
        def publish(aid):
            return AgentRunStore(db).publish_agent(*args, run_token=uid, agent_id=aid,
                patch={"assignment": {"goal": "Independent check"}, "status": "waiting"}, event_id=aid)
        with ThreadPoolExecutor(max_workers=2) as pool:
            events = list(pool.map(publish, ids))
        assert sorted(e["seq"] for e in events) == [1, 2]
        assert publish(ids[0]) in events
        def claim(aid):
            try:
                return AgentRunStore(db).claim(*args, model, step=f"agent:{aid}:0", run_token=uid, reservation=(1, 80))
            except AnalysisBudgetExceeded:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            admitted = list(pool.map(claim, ids))
        assert sum(admitted) == 1
        winner = ids[admitted.index(True)]
        completion.usage = measured_usage({"prompt_tokens": 1, "completion_tokens": 1, "cost": .00000005}, model)
        with ThreadPoolExecutor(max_workers=3) as pool:
            assert sum(pool.map(lambda _: AgentRunStore(db).settle(*args, completion=completion, status="succeeded",
                step=f"agent:{winner}:0", final=False), range(3))) == 1
        root = store.receipt_ref(*args).get().to_dict()
        assert root["reserved_cost"] == 60
        assert store.delegation_view(*args)["usage"]["estimated_cost_nano_usd"] == 50
        assert store.delegation_view(*args)["usage"]["cost_complete"] is False
        store.publish_agent(*args, run_token=uid, agent_id=winner,
            message={"sender": winner, "recipient": "orchestrator", "kind": "question", "text": "Which period?"})
        assert store.delegation_view(*args, agent_id=winner)["messages"][0]["text"] == "Which period?"
        store.finish_run(*args, completion=completion, status="succeeded", run_token=uid)
        assert db.collection("users").document(uid).get().to_dict()["agent_usage"]["calls"] == 2
        store.delete_chat(uid, chat)
        assert not list(store._turn_ref(*args).collection("agents").stream())
    finally:
        FirestoreAccountDeletion(db)._delete_user_subcollections(uid)
        db.collection("users").document(uid).delete()
        db.close()


def test_parallel_workers_share_admission_and_settle_each_receipt_once():
    assert_safe_e2e_environment()
    db = firestore.Client(project=E2E_PROJECT_ID)
    uid = "agent-race-" + uuid.uuid4().hex
    store = AgentRunStore(db)
    model = AgentModel()
    turns = []
    try:
        for i in range(6):
            chat = store.create_chat(uid, execution_mode="agent")
            turn = store.create_turn(uid, chat["id"], question=f"Question {i}", mode="Agent", deep_search=False,
                selected_models=[model.model], consensus_model=model.model,
                client_request_id=f"run-{i}", execution_mode="agent")
            turns.append((chat["id"], turn["id"]))
        gate = threading.Barrier(len(turns))

        def claim(item):
            gate.wait(timeout=5)
            try:
                return AgentRunStore(db).claim(uid, *item, model, run_token=uid, policy=AgentPolicy().snapshot())
            except AgentCapacityExceeded:
                return False

        with ThreadPoolExecutor(max_workers=len(turns)) as pool:
            admitted = list(pool.map(claim, turns))
        assert sum(admitted) == 2
        assert db.collection("users").document(uid).get().to_dict()["agent_usage"]["calls"] == 2
        winners = [item for item, allowed in zip(turns, admitted) if allowed]
        # A duplicate paid step remains a read-only result even at full capacity.
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert not any(pool.map(lambda _: AgentRunStore(db).claim(uid, *winners[0], model), range(4)))
        completion = AgentCompletion()
        completion.text, completion.finish_reason = "Saved answer", "stop"
        completion.usage = measured_usage({"prompt_tokens": 100, "completion_tokens": 10,
            "prompt_tokens_details": {"cache_write_tokens": 40}, "cost": .0123}, model)

        def settle(_):
            return AgentRunStore(db).settle(uid, *winners[0], completion=completion, status="succeeded", final=False)

        with ThreadPoolExecutor(max_workers=4) as pool:
            assert sum(pool.map(settle, range(4))) == 1
        totals = db.collection("users").document(uid).get().to_dict()["agent_usage"]
        assert totals["measured_calls"] == 1 and totals["unsettled_calls"] == 1
        assert totals["estimated_cost_nano_usd"] == completion.usage["estimated_cost_nano_usd"]
        assert len(store.active_ref(uid).get().to_dict()["leases"]) == 2
        # A paid continuation keeps the SAME owner slot and has its own receipt.
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert sum(pool.map(lambda _: AgentRunStore(db).claim(uid, *winners[0], model,
                step="completion:1", run_token=uid), range(4))) == 1
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert sum(pool.map(lambda _: AgentRunStore(db).settle(uid, *winners[0], completion=completion,
                status="succeeded", step="completion:1", final=False), range(4))) == 1
        assert len(store.active_ref(uid).get().to_dict()["leases"]) == 2
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert sum(pool.map(lambda _: AgentRunStore(db).finish_run(uid, *winners[0], completion=completion,
                status="succeeded", run_token=uid), range(4))) == 1
        totals = db.collection("users").document(uid).get().to_dict()["agent_usage"]
        assert totals["measured_calls"] == 2 and totals["unsettled_calls"] == 1
        assert totals["estimated_cost_nano_usd"] == 2 * completion.usage["estimated_cost_nano_usd"]
        assert totals["provider_cost_nano_usd"] == 24_600_000
        assert totals["cache_write_tokens"] == 80
        replacement = next(item for item, allowed in zip(turns, admitted) if not allowed)
        assert store.claim(uid, *replacement, model)
        # Chat deletion does not prevent the receipt from freeing its owner slot.
        store.delete_chat(uid, winners[1][0])
        assert store.settle(uid, *winners[1], completion=completion, status="cancelled")
        assert len(store.active_ref(uid).get().to_dict()["leases"]) == 1
        assert not store._chat_ref(uid, winners[1][0]).get().exists
    finally:
        FirestoreAccountDeletion(db)._delete_user_subcollections(uid)
        db.collection("users").document(uid).delete()
        db.close()
