"""Native turn/terminal-write/deletion ordering, including missing-parent children."""
from concurrent.futures import ThreadPoolExecutor
import threading
import pytest
from app.services.chat_store import ChatStore, ChatNotFound, TurnStatusConflict
from native_support import native_db, tree


def create_turn(store, uid, chat, request="first"):
    return store.create_turn(uid, chat, question="A durable question?", mode="consensus", deep_search=False,
        selected_models=["OpenAI"], consensus_model="OpenAI", client_request_id=request)["id"]


def finish(store, uid, chat, turn, error_code="consensus_failed"):
    # The terminal write a stored turn still takes (the Consensus completion
    # left with the browser's Consensus run on 2026-10-25).
    return store.fail_turn(uid, chat, turn, error_code=error_code)


@pytest.mark.parametrize("delete_first", [False, True])
def test_native_turn_write_and_delete_never_resurrect_children(native_db, delete_first):
    db, uid, control_uid = native_db, native_db.owner(), native_db.owner()
    store = ChatStore(db)
    chat = store.create_chat(uid)["id"]
    turn = create_turn(store, uid, chat)
    control = store.create_chat(control_uid)["id"]
    control_before = tree(store._chat_ref(control_uid, control))
    store._chat_ref(uid, chat).collection("context_versions").document("a" * 32).set({"summary": "Private context"})
    ready = threading.Event()
    def first():
        try:
            if delete_first:
                assert ChatStore(db).delete_chat(uid, chat)
            else:
                finish(ChatStore(db), uid, chat, turn)
        finally:
            ready.set()
    def second():
        assert ready.wait(20)
        if delete_first:
            with pytest.raises(ChatNotFound):
                finish(ChatStore(db), uid, chat, turn)
        else:
            assert ChatStore(db).delete_chat(uid, chat)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(first), pool.submit(second)]
        for job in jobs:
            job.result(timeout=30)
    with pytest.raises(ChatNotFound):
        create_turn(ChatStore(db), uid, chat, "late")
    assert tree(store._chat_ref(uid, chat)) == {}
    assert tree(store._chat_ref(control_uid, control)) == control_before


def test_native_terminal_failure_rejects_another_outcome_and_remains_failed(native_db):
    db, uid = native_db, native_db.owner()
    store = ChatStore(db)
    chat = store.create_chat(uid)["id"]
    turn = create_turn(store, uid, chat)
    store.fail_turn(uid, chat, turn, error_code="consensus_failed")
    before = tree(store._chat_ref(uid, chat))
    with pytest.raises(TurnStatusConflict):
        finish(ChatStore(db), uid, chat, turn, error_code="abandoned")
    assert tree(store._chat_ref(uid, chat)) == before


def test_native_deleting_tombstone_fences_writes_before_physical_purge(native_db, monkeypatch):
    db, uid, control_uid = native_db, native_db.owner(), native_db.owner()
    store = ChatStore(db)
    chat, control = store.create_chat(uid)["id"], store.create_chat(control_uid)["id"]
    turn = create_turn(store, uid, chat)
    chat_ref = store._chat_ref(uid, chat)
    chat_ref.collection("context_versions").document("a" * 32).set({"summary": "Private context"})
    control_before = tree(store._chat_ref(control_uid, control))
    tombstone_committed, allow_purge = threading.Event(), threading.Event()
    original_purge = ChatStore._delete_chat_tree

    def paused_purge(self, ref):
        # This hook is after the real deletion-job/tombstone transaction and
        # before physical deletion. No transaction callback or guard is mocked.
        if ref.path == chat_ref.path:
            assert ref.get().to_dict()["status"] == "deleting"
            assert self._deletion_job_ref(uid, chat).get().exists
            tombstone_committed.set()
            assert allow_purge.wait(20)
        return original_purge(self, ref)

    monkeypatch.setattr(ChatStore, "_delete_chat_tree", paused_purge)
    with ThreadPoolExecutor(max_workers=1) as pool:
        deletion = pool.submit(ChatStore(db).delete_chat, uid, chat)
        try:
            assert tombstone_committed.wait(20)
            before = tree(chat_ref)
            job_before = store._deletion_job_ref(uid, chat).get().to_dict()
            assert before and any("/turns/" in path for path in before)
            with pytest.raises(ChatNotFound):
                finish(ChatStore(db), uid, chat, turn)
            assert tree(chat_ref) == before
            with pytest.raises(ChatNotFound):
                create_turn(ChatStore(db), uid, chat, "during-purge")
            assert tree(chat_ref) == before
            assert store._deletion_job_ref(uid, chat).get().to_dict() == job_before
            assert tree(store._chat_ref(control_uid, control)) == control_before
        finally:
            allow_purge.set()
        assert deletion.result(timeout=30)
    assert tree(chat_ref) == {}
    assert not store._deletion_job_ref(uid, chat).get().exists
    assert tree(store._chat_ref(control_uid, control)) == control_before
