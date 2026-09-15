"""Agent admission and accounting races against the isolated Firestore emulator."""
from concurrent.futures import ThreadPoolExecutor
import threading
import uuid

from google.cloud import firestore

from app.core.e2e_profile import E2E_PROJECT_ID, assert_safe_e2e_environment
from app.services.account_deletion import FirestoreAccountDeletion
from app.services.agent_runs import AgentRunStore
from app.services.agent_runtime import AgentCapacityExceeded
from app.services.llm.agent_client import AgentModel, AgentCompletion, measured_usage


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
                return AgentRunStore(db).claim(uid, *item, model)
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
        completion.usage = measured_usage({"prompt_tokens": 100, "completion_tokens": 10}, model)

        def settle(_):
            return AgentRunStore(db).settle(uid, *winners[0], completion=completion, status="succeeded")

        with ThreadPoolExecutor(max_workers=4) as pool:
            assert sum(pool.map(settle, range(4))) == 1
        totals = db.collection("users").document(uid).get().to_dict()["agent_usage"]
        assert totals["measured_calls"] == 1 and totals["unsettled_calls"] == 1
        assert totals["estimated_cost_nano_usd"] == completion.usage["estimated_cost_nano_usd"]
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
