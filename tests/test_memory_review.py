"""The daily memory review (app/services/memory_review.py)."""
from datetime import datetime, timedelta, timezone
import json
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.routers import users as users_router
from app.core.rate_limit import limiter
from app.services import agent_memory, memory_review, user_memory
from app.services.agent_memory import FirestoreAgentMemoryRepository
from app.services.chat_store import ChatStore
from test_chat_history import FakeChatDatabase

UID = "review-user"
# Real time: the Undo log keeps 30 days counted from now (agent_memory._clean_changes).
NOW = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
AUTH = {"Authorization": "Bearer verified"}


class Database(FakeChatDatabase):
    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()

    def run_transaction(self, operation):
        with self.lock:
            return super().run_transaction(operation)


@pytest.fixture
def db():
    return Database()


def set_profile(db, **fields):
    db.collection("users").document(UID).collection("memory").document("profile").set(
        {**user_memory.empty_profile(), **fields})


def add_items(db, *texts):
    items = [{"id": f"m00000{index}", "text": text, "origin": "agent",
              "created_at": NOW - timedelta(days=30), "updated_at": NOW - timedelta(days=30)}
             for index, text in enumerate(texts)]
    FirestoreAgentMemoryRepository(db).entries_ref(UID).set({"items": items, "revision": 1, "changes": []})
    return items


def chat(db, chat_id, *, updated=NOW - timedelta(hours=5), **fields):
    db.collection("users").document(UID).collection("chats").document(chat_id).set(
        {"status": "active", "execution_mode": "agent", "title": f"Chat {chat_id}", "updated_at": updated, **fields})


def turn(db, chat_id, turn_id, question, *, at, answer="Here you go.", status="completed", **settings):
    (db.collection("users").document(UID).collection("chats").document(chat_id)
     .collection("turns").document(turn_id).set({
         "question": question, "assistant_response": answer, "status": status, "created_at": at,
         "agent_settings": settings}))


def review(db, replies, *, clock=lambda: NOW):
    prompts = []

    def query(model, keys, *, system, prompt, max_tokens, json_schema):
        prompts.append(prompt)
        assert json_schema == memory_review.SCHEMA and max_tokens == memory_review.MAX_TOKENS
        return json.dumps(replies.pop(0)) if replies else '{"changes": []}'

    service = memory_review.MemoryReview(db, store=ChatStore(db), clock=clock, query_fn=query,
                                         api_keys={"openrouter": "key"})
    return service, prompts


@pytest.fixture(autouse=True)
def openrouter_key(monkeypatch):
    from app.services.llm import credentials
    monkeypatch.setattr(credentials, "openrouter_api_key", lambda keys: "key")


# --- Due accounts -------------------------------------------------------------

def test_a_message_marks_the_account_and_the_review_waits_for_quiet(db):
    memory_review.mark_due(db, UID, now=NOW)
    service, _ = review(db, [])
    assert service.due(NOW) == []
    assert service.due(NOW + memory_review.IDLE) == [UID]
    stored = db.collection(memory_review.COLLECTION).document(UID).get().to_dict()
    # Times only: nothing of the chats or the memory.
    assert set(stored) == {"last_turn_at", "review_after"}


def test_a_failed_mark_never_fails_the_message():
    class Broken:
        def collection(self, name):
            raise RuntimeError("firestore down")

    memory_review.mark_due(Broken(), UID, now=NOW)


# --- One review ---------------------------------------------------------------

def test_the_review_reads_the_days_chats_and_saves_one_change_with_undo(db):
    set_profile(db, auto_memory=True, role="Builds consens.io")
    add_items(db, "Plans a marathon training camp in October 2026.", "Prefers short answers.")
    memory_review.mark_due(db, UID, now=NOW - memory_review.IDLE)
    chat(db, "c1")
    turn(db, "c1", "t1", "Ich möchte neben der Arbeit promovieren, KI und Wirtschaft. Komme aus Hannover.",
         at=NOW - timedelta(hours=9), answer="Gute Idee. Soll ich dir nächstes Mal Lehrstühle raussuchen?")
    turn(db, "c1", "t2", "ja gerne" + agent_memory.QUOTE_TYPED_MARKER + "Soll ich dir Lehrstühle raussuchen?”",
         at=NOW - timedelta(hours=8))
    turn(db, "c1", "t3", "still running", at=NOW - timedelta(hours=7), status="pending")
    turn(db, "c1", "t4", "Watch task: check the weather", at=NOW - timedelta(hours=6), watch_run={"id": "w"})
    turn(db, "c1", "t0", "a question from last month", at=NOW - timedelta(days=30))
    chat(db, "google", google_data=True)
    turn(db, "google", "g1", "What is in my inbox from my doctor?", at=NOW - timedelta(hours=8))
    chat(db, "temp", temporary=True)
    turn(db, "temp", "x1", "Something private", at=NOW - timedelta(hours=8))
    chat(db, "gone", status="deleting")
    turn(db, "gone", "d1", "Deleted chat question", at=NOW - timedelta(hours=8))
    chat(db, "compare", execution_mode="consensus")
    turn(db, "compare", "k1", "A Compare question", at=NOW - timedelta(hours=8))

    service, prompts = review(db, [{"changes": [
        {"op": "add", "id": "", "text": "Will neben der Arbeit in KI/Wirtschaft promovieren; kommt aus Hannover."},
        {"op": "delete", "id": "m000000", "text": ""},
        {"op": "update", "id": "m999999", "text": "An unknown memory"},
        {"op": "add", "id": "", "text": "Password: hunter22"},
    ]}])
    assert service.run() == {"reviewed": 0, "changed": 1, "skipped": 0, "failed": 0}

    prompt = prompts[0]
    assert "promovieren" in prompt and "Hannover" in prompt and "Lehrstühle" in prompt
    # The user's words, not the answer passage they quoted, and the end of each answer.
    assert ("User: ja gerne\n(The user quoted the assistant's earlier answer: “Soll ich dir Lehrstühle"
            in prompt)
    assert "Assistant (end of the answer): Gute Idee." in prompt
    for left_out in ("still running", "Watch task", "last month", "inbox", "Something private", "Deleted chat",
                     "Compare question"):
        assert left_out not in prompt
    assert "m000001" in prompt and "Builds consens.io" in prompt and f"Today is {NOW.date().isoformat()}." in prompt

    repository = FirestoreAgentMemoryRepository(db)
    items, revision, last = repository.get_with_review(UID)
    assert [item["text"] for item in items] == [
        "Prefers short answers.", "Will neben der Arbeit in KI/Wirtschaft promovieren; kommt aus Hannover."]
    assert all(item["origin"] == "agent" for item in items)
    assert last == {"change_id": last["change_id"], "at": NOW.isoformat(), "added": 1, "updated": 0,
                    "deleted": 1, "undone": False}

    queued = db.collection(memory_review.COLLECTION).document(UID).get().to_dict()
    assert queued["reviewed_at"] == NOW and queued["review_after"] is None and queued["lease_id"] is None
    assert queued["last_result"] == {"status": "applied", "added": 1, "updated": 0, "deleted": 1, "messages": 2}

    repository.undo(UID, last["change_id"])
    items, _, last = repository.get_with_review(UID)
    assert [item["text"] for item in items] == [
        "Prefers short answers.", "Plans a marathon training camp in October 2026."]
    assert last["undone"] is True


def test_the_review_needs_the_opt_in_and_runs_at_most_once_a_day(db):
    set_profile(db, auto_memory=False)
    memory_review.mark_due(db, UID, now=NOW - memory_review.IDLE)
    chat(db, "c1")
    turn(db, "c1", "t1", "I live in Hannover.", at=NOW - timedelta(hours=5))
    service, prompts = review(db, [])
    assert service.run()["reviewed"] == 1 and prompts == []
    assert db.collection(memory_review.COLLECTION).document(UID).get().to_dict()["last_result"]["status"] == \
        "auto_memory_off"

    set_profile(db, auto_memory=True)
    later = NOW + timedelta(hours=5)
    memory_review.mark_due(db, UID, now=later - memory_review.IDLE)
    service, prompts = review(db, [], clock=lambda: later)
    assert service.run()["skipped"] == 1 and prompts == []
    # Reviewed five hours ago: the next one waits for its day.
    assert db.collection(memory_review.COLLECTION).document(UID).get().to_dict()["review_after"] == \
        NOW + memory_review.INTERVAL


def test_a_message_during_the_review_keeps_its_own_due_time(db):
    set_profile(db, auto_memory=True)
    memory_review.mark_due(db, UID, now=NOW - memory_review.IDLE)
    chat(db, "c1")
    turn(db, "c1", "t1", "I live in Hannover.", at=NOW - timedelta(hours=5))
    service, _ = review(db, [])

    def query(model, keys, **kwargs):
        memory_review.mark_due(db, UID, now=NOW + timedelta(minutes=1))
        return '{"changes": []}'

    service.query_fn = query
    service.run()
    queued = db.collection(memory_review.COLLECTION).document(UID).get().to_dict()
    assert queued["review_after"] == NOW + timedelta(minutes=1) + memory_review.IDLE
    assert queued["reviewed_at"] == NOW


def test_a_held_lease_keeps_a_second_process_out(db):
    set_profile(db, auto_memory=True)
    memory_review.mark_due(db, UID, now=NOW - memory_review.IDLE)
    db.collection(memory_review.COLLECTION).document(UID).set(
        {"lease_until": NOW + timedelta(minutes=5), "lease_id": "other"}, merge=True)
    service, prompts = review(db, [])
    assert service.run()["skipped"] == 1 and prompts == []


def test_a_failed_model_call_saves_nothing_and_frees_the_account(db):
    set_profile(db, auto_memory=True)
    add_items(db, "Prefers short answers.")
    memory_review.mark_due(db, UID, now=NOW - memory_review.IDLE)
    chat(db, "c1")
    turn(db, "c1", "t1", "I live in Hannover.", at=NOW - timedelta(hours=5))
    service, _ = review(db, [])

    def broken(*args, **kwargs):
        raise RuntimeError("provider down")

    service.query_fn = broken
    assert service.run()["reviewed"] == 1
    queued = db.collection(memory_review.COLLECTION).document(UID).get().to_dict()
    assert queued["last_result"]["status"] == "failed" and queued["lease_id"] is None
    assert [item["text"] for item in FirestoreAgentMemoryRepository(db).get(UID)[0]] == ["Prefers short answers."]


def test_a_reply_cut_off_mid_json_is_a_failure_not_a_quiet_day(db):
    set_profile(db, auto_memory=True)
    memory_review.mark_due(db, UID, now=NOW - memory_review.IDLE)
    chat(db, "c1")
    turn(db, "c1", "t1", "I live in Hannover.", at=NOW - timedelta(hours=5))
    service, _ = review(db, [])
    service.query_fn = lambda *args, **kwargs: '{"changes": [{"op": "add", "id": "", "text": "Lives in Hann'
    service.run()
    result = db.collection(memory_review.COLLECTION).document(UID).get().to_dict()["last_result"]
    assert result == {"status": "unreadable", "added": 0, "updated": 0, "deleted": 0, "messages": 1}


def test_never_further_back_than_the_lookback_and_the_newest_messages_first(db, monkeypatch):
    set_profile(db, auto_memory=True)
    chat(db, "c1")
    turn(db, "c1", "old", "a question from three weeks ago", at=NOW - timedelta(days=21))
    for hour in range(6):
        turn(db, "c1", f"t{hour}", f"question {hour} " + "x" * 300, at=NOW - timedelta(hours=10 - hour))
    monkeypatch.setattr(memory_review, "CHATS_CHARS", 1_200)
    chats = memory_review.collect_chats(ChatStore(db), UID, NOW - memory_review.LOOKBACK)
    questions = [turn["question"][:10] for turn in chats[0]["turns"]]
    assert questions == ["question 3", "question 4", "question 5"]


# --- The reply ----------------------------------------------------------------

def test_unusable_changes_are_dropped_and_a_full_memory_makes_room_first(monkeypatch):
    monkeypatch.setattr(memory_review, "MAX_ITEMS", 2)
    items = [{"id": "m000001", "text": "A"}, {"id": "m000002", "text": "B"}]
    reply = json.dumps({"changes": [
        {"op": "add", "id": "x", "text": "New one"},
        {"op": "add", "id": "", "text": "Second new one"},
        {"op": "delete", "id": "m000001", "text": "ignored"},
        {"op": "update", "id": "m000001", "text": "A twice"},
        {"op": "update", "id": "m000002", "text": "B, sharper"},
        {"op": "launch", "id": "", "text": "?"},
        "not a change",
    ]})
    assert memory_review.changes(reply, items) == [
        {"op": "delete", "id": "m000001", "text": ""},
        {"op": "update", "id": "m000002", "text": "B, sharper"},
        {"op": "add", "id": "", "text": "New one"},
    ]
    assert memory_review.changes("not json", items) == []
    assert memory_review.changes('{"changes": "none"}', items) == []


# --- Settings -----------------------------------------------------------------

@pytest.fixture
def items_api(monkeypatch, db):
    limiter.reset()
    monkeypatch.setattr(users_router, "agent_memory_repository", FirestoreAgentMemoryRepository(db))
    monkeypatch.setattr(users_router, "user_memory_repository", user_memory.FirestoreUserMemoryRepository(db))
    monkeypatch.setattr(users_router, "verify_user_token", lambda token, **kw: UID)
    monkeypatch.setattr(users_router, "get_user_tier", lambda uid: "free")
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(users_router.router)
    return TestClient(app)


def test_settings_name_the_latest_review_and_undo_it(items_api, db):
    assert items_api.get("/api/my/memory", headers=AUTH).json()["last_review"] is None
    set_profile(db, auto_memory=True)
    repository = FirestoreAgentMemoryRepository(db)
    repository.apply(UID, [{"op": "add", "id": "", "text": "Prefers tea."}], origin="user")
    applied = repository.apply(UID, [{"op": "add", "id": "", "text": "Lives in Hannover."},
                                     {"op": "add", "id": "", "text": "Runs marathons."}],
                               origin="agent", source=memory_review.SOURCE)
    listing = items_api.get("/api/my/memory", headers=AUTH).json()
    assert listing["last_review"]["change_id"] == applied["change_id"]
    assert listing["last_review"]["added"] == 2 and listing["last_review"]["undone"] is False
    # Counts only: the review's texts stay in the list itself.
    assert "Hannover" not in json.dumps(listing["last_review"])
    undone = items_api.post(f"/api/my/memory/changes/{applied['change_id']}/undo", headers=AUTH).json()
    assert [item["text"] for item in undone["items"]] == ["Prefers tea."]
    assert undone["last_review"]["undone"] is True


def test_the_agent_is_told_what_memory_is_for_not_what_to_leave_out():
    prompt = agent_memory.AUDIT_MEMORY_WRITE_PROMPT
    assert "personal" in prompt and "working on" in prompt and "same step as your answer" in prompt
    assert "merely ask" not in prompt and "need not mention it" in prompt
    # Apply silently, name rarely (Max 2026-10-04); lost with comparison mode
    # on 2026-10-31, back with the review that fills the memory.
    use = " ".join(agent_memory.AUDIT_MEMORY_USE_PROMPT.split())
    assert "apply it without saying why" in use and "never build a bridge" in use
    assert "one short clause" in use and "the question and the evidence decide" in use
