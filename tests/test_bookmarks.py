import base64
import json
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import bookmarks as bookmarks_router
from app.core import config as cfg
from app.core.rate_limit import limiter
from app.core.security import CustomSecurityMiddleware
from app.services import persistence_guard, share_snapshots
from app.services.chat_store import ChatCursorUnavailable, InvalidChatCursor
from test_chat_history import FakeChatDatabase, FakeTransaction as ChatFakeTransaction


class FakeSnapshot:
    def __init__(self, bookmark_id, data):
        self.id = bookmark_id
        self._data = data

    def to_dict(self):
        return self._data.copy()

    @property
    def exists(self):
        return self._data is not None


class FakeBookmarkRef:
    def __init__(self, bookmark_id, data):
        self.id = bookmark_id
        self.data = data

    def set(self, incoming, merge=False):
        assert merge is True
        for key, value in incoming.items():
            if key in {"responses", "model_labels"}:
                self.data.setdefault(key, {}).update(value)
            elif value is bookmarks_router.firestore.SERVER_TIMESTAMP:
                # Production Firestore resolves transforms before the route's
                # post-write read. Keep this tiny fake faithful to that
                # response contract instead of leaking the SDK Sentinel.
                self.data[key] = "server-time"
            else:
                self.data[key] = value

    def get(self):
        return FakeSnapshot(self.id, self.data)


class FakeFirestore:
    def __init__(self, bookmark_ref):
        self.bookmark_ref = bookmark_ref

    def collection(self, name):
        if name == "users":
            return self
        assert name == "bookmarks"
        return self

    def document(self, document_id):
        if document_id == "uid-1":
            return self
        assert document_id == self.bookmark_ref.id
        return self.bookmark_ref


class FakeListSnapshot:
    def __init__(self, bookmark_id, data):
        self.id = bookmark_id
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return dict(self._data or {})


class FakeListRef:
    def __init__(self, collection, bookmark_id):
        self.collection = collection
        self.id = bookmark_id

    def get(self):
        return FakeListSnapshot(self.id, self.collection.items.get(self.id))


class FakeListCollection:
    def __init__(self, items):
        self.items = items

    def document(self, bookmark_id):
        return FakeListRef(self, bookmark_id)


class FakeOwnerDocument:
    def __init__(self, database, uid):
        self.database = database
        self.uid = uid

    def collection(self, name):
        assert name == "bookmarks"
        return FakeListCollection(self.database.by_uid.get(self.uid, {}))


class FakeUsersCollection:
    def __init__(self, database):
        self.database = database

    def document(self, uid):
        return FakeOwnerDocument(self.database, uid)


class FakeBookmarkDatabase:
    def __init__(self, by_uid):
        self.by_uid = by_uid

    def collection(self, name):
        assert name == "users"
        return FakeUsersCollection(self)


def test_bookmark_write_budget_is_scoped_to_the_authenticated_uid():
    with patch.object(bookmarks_router.api_uid_limiter, "check") as check:
        bookmarks_router._enforce_bookmark_uid_rate_limit("owner-1", "model_save")
        bookmarks_router._enforce_bookmark_uid_rate_limit("owner-2", "consensus_save")

    assert check.call_args_list[0].args == (
        "owner-1", "bookmark:model_save", 120,
    )
    assert check.call_args_list[1].args == (
        "owner-2", "bookmark:consensus_save", 60,
    )


def test_bookmark_uid_throttle_remains_a_429():
    with patch.object(
        bookmarks_router.api_uid_limiter,
        "check",
        side_effect=bookmarks_router.ApiUidRateLimitExceeded("full", retry_after=12),
    ):
        try:
            bookmarks_router._enforce_bookmark_uid_rate_limit("owner-1", "model_save")
        except bookmarks_router.HTTPException as exc:
            assert exc.status_code == 429
            assert exc.detail == "Too many bookmark saves. Please slow down."
            # Nachprüfung 2: the wait, as every throttle says it (main.error_body
            # adds code "rate_limited" and retry_after from it).
            assert exc.headers == {"Retry-After": "12"}
        else:
            raise AssertionError("Expected the bookmark UID budget to reject the write")


def test_last_grok_model_write_is_persisted_under_the_owner_budget():
    bookmark_id = "stable_grok_bookmark"
    bookmark_ref = FakeBookmarkRef(
        bookmark_id,
        {"query": "Why?", "responses": {}},
    )
    fake_db = FakeFirestore(bookmark_ref)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)

    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", fake_db),
        patch.object(bookmarks_router.firestore, "SERVER_TIMESTAMP", "server-time"),
        patch.object(bookmarks_router.api_uid_limiter, "check") as check_budget,
    ):
        response = TestClient(app).post(
            "/bookmark",
            json={
                "id_token": "token",
                "question": "Why?",
                "response": "Grok finished last.",
                "modelName": "Grok",
                "mode": "Standard",
                "bookmarkId": bookmark_id,
            },
        )

    assert response.status_code == 200
    assert response.json()["bookmark"]["responses"]["Grok"] == "Grok finished last."
    check_budget.assert_called_once_with("uid-1", "bookmark:model_save", 120)


def test_consensus_save_returns_complete_merged_bookmark():
    bookmark_id = "V2h5Pw__"
    bookmark_ref = FakeBookmarkRef(
        bookmark_id,
        {
            "query": "Why?",
            "mode": "Normal",
            "responses": {"OpenAI": "Existing model answer"},
        },
    )
    fake_db = FakeFirestore(bookmark_ref)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)

    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", fake_db),
        patch.object(bookmarks_router.firestore, "SERVER_TIMESTAMP", "server-time"),
        patch.object(
            bookmarks_router,
            "_authoritative_consensus_payload",
                return_value={
                    "question": "Why?",
                    "consensus": "Merged consensus",
                    "differences": "Merged differences",
                    "differences_data": None,
                    "sources": [],
                    "included_models": ["Gemini: Gemini-Pro"],
                    "consensus_model": "Gemini-Pro",
                    "model_responses": {"Gemini": "Authoritative answer"},
                    "vote_subject_id": "authoritative-run-1",
                    "result_id": "N" * 16,
                },
        ),
    ):
        response = TestClient(app).post(
            "/bookmark/consensus",
            json={
                "id_token": "token",
                "question": "Why?",
                "consensusText": "Merged consensus",
                "differencesText": "Merged differences",
                "resultId": "N" * 16,
                "consensusModel": "Gemini-Pro",
                "modelLabels": {"OpenAI": "GPT-5.4 mini"},
            },
        )

    assert response.status_code == 200
    bookmark = response.json()["bookmark"]
    assert bookmark["id"] == bookmark_id
    assert bookmark["query"] == "Why?"
    assert bookmark["responses"]["Gemini"] == "Authoritative answer"
    assert bookmark["responses"]["OpenAI"] == ""
    assert bookmark["responses"]["consensus"] == "Merged consensus"
    assert bookmark["responses"]["differences"] == "Merged differences"
    # Agent Mode no longer performs model bookmark writes. The consensus save
    # must therefore make a brand-new document eligible for the timestamp-
    # ordered sidebar query on its own.
    assert bookmark["timestamp"] == "server-time"
    assert bookmark["share_result_id"] == "N" * 16
    assert bookmark["consensus_model"] == "Gemini-Pro"
    assert bookmark["model_labels"] == {"Gemini": "Gemini-Pro"}


def test_consensus_save_ignores_large_legacy_client_snapshot():
    """Ignored browser copies must never veto an authoritative run.

    The evidence merger and authoritative snapshot both allow 50 sources. The
    former request schema allowed only 24, producing the observed intermittent
    422 before the handler could read the server-owned pending result.
    """
    bookmark_id = "source_heavy_run"
    bookmark_ref = FakeBookmarkRef(bookmark_id, {"responses": {}})
    fake_db = FakeFirestore(bookmark_ref)
    app = FastAPI()
    app.state.limiter = limiter
    limiter.reset()
    app.include_router(bookmarks_router.router)

    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", fake_db),
        patch.object(
            bookmarks_router,
            "_authoritative_consensus_payload",
            return_value={
                "question": "Who wins?",
                "consensus": "Authoritative consensus",
                "differences": "Authoritative differences",
                "differences_data": None,
                "sources": [
                    {"id": f"S{i}", "url": f"https://source-{i}.example"}
                    for i in range(1, 51)
                ],
                "included_models": ["OpenAI: GPT", "Gemini: Gemini"],
                "model_responses": {"OpenAI": "a", "Gemini": "b"},
                "result_id": "R" * 16,
            },
        ),
    ):
        response = TestClient(app).post(
            "/bookmark/consensus",
            json={
                "id_token": "token",
                "bookmarkId": bookmark_id,
                "question": "Who wins?",
                "resultId": "R" * 16,
                # Deliberately malformed/oversized legacy copies. None of them
                # is trusted or persisted by this endpoint.
                "consensusText": {"not": "text"},
                "differencesText": ["not", "text"],
                "differencesData": "not-an-object",
                "sources": [
                    {"id": f"S{i}", "url": f"https://client-{i}.example"}
                    for i in range(1, 51)
                ],
                "consensusModel": 123,
                "modelLabels": {"Mistral": None},
                "modelResponses": ["not", "a", "mapping"],
            },
        )

    assert response.status_code == 200
    bookmark = response.json()["bookmark"]
    assert bookmark["responses"]["consensus"] == "Authoritative consensus"
    assert len(bookmark["sources"]) == 50


def test_direct_comparison_model_save_accepts_full_evidence_budget():
    payload = {
        "id_token": "token",
        "question": "Compare",
        "response": "Answer",
        "modelName": "OpenAI",
        "mode": "Standard",
        "sources": [
            {"id": f"S{i}", "url": f"https://source-{i}.example"}
            for i in range(1, 101)
        ],
    }
    assert bookmarks_router.BookmarkModelRequest.model_validate(payload)
    assert len(bookmarks_router.BookmarkModelRequest.model_validate(payload).sources) == 100


def test_direct_comparison_model_name_contract_follows_provider_registry():
    base = {
        "id_token": "token",
        "question": "Compare",
        "response": "Answer",
        "mode": "Standard",
    }
    for model_name in cfg.PROVIDER_LABEL_BY_ID.values():
        validated = bookmarks_router.BookmarkModelRequest.model_validate({
            **base,
            "modelName": model_name,
        })
        assert validated.modelName == model_name


@pytest.mark.parametrize("label, expected", [
    ("Gemini 2.5 Pro", "Gemini 2.5 Pro"),
    ("Gemini 2.5 Flash · Pro", "Gemini 2.5 Flash"),
    (None, "Gemini"),
    ("<script>bad</script>", "Gemini"),
])
def test_direct_comparison_saves_model_version_with_answer(label, expected):
    bookmark_ref = FakeBookmarkRef("direct_models", {
        "responses": {"OpenAI": "Existing answer", "Gemini": "Old answer"},
        "model_labels": {"OpenAI": "GPT saved version", "Gemini": "Old Gemini version"},
    })
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)
    payload = {
        "id_token": "token", "question": "Compare", "response": "New Gemini answer",
        "modelName": "Gemini", "mode": "Standard", "bookmarkId": "direct_models",
    }
    if label is not None:
        payload["modelLabel"] = label
    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", FakeFirestore(bookmark_ref)),
        patch.object(bookmarks_router.api_uid_limiter, "check"),
    ):
        response = TestClient(app).post("/bookmark", json=payload)
    assert response.status_code == 200
    saved = response.json()["bookmark"]
    assert saved["model_labels"] == {"OpenAI": "GPT saved version", "Gemini": expected}
    assert saved["responses"] == {"OpenAI": "Existing answer", "Gemini": "New Gemini answer"}
    assert bookmark_ref.data["model_labels"] == saved["model_labels"]


def test_followup_bookmark_keeps_complete_previous_turn_for_restore():
    current = "What should I prioritize first?"
    previous = "How should I plan the migration?"
    bookmark_id = "V2hhdCBzaG91bGQgSSBwcmlvcml0aXplIGZpcnN0Pw__"
    bookmark_ref = FakeBookmarkRef(bookmark_id, {"query": current, "responses": {}})
    fake_db = FakeFirestore(bookmark_ref)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)

    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", fake_db),
        patch.object(
            bookmarks_router,
            "_authoritative_consensus_payload",
            return_value={
                "question": current,
                "consensus": "Follow-up consensus",
                "differences": "No material differences",
                "differences_data": None,
                "sources": [],
                "result_id": "",
            },
        ),
    ):
        response = TestClient(app).post(
            "/bookmark/consensus",
            json={
                "id_token": "token",
                "question": current,
                "previousQuestion": previous,
                "previousTurn": {
                    "question": previous,
                    "consensus": "Original consensus",
                    "differences": "Original differences",
                    "differences_data": {
                        "agreement": {"score": 82, "model_count": 6},
                        "claims": [],
                        "differences": [],
                        "best_model": None,
                        "models_compared": [],
                    },
                },
                "consensusText": "Follow-up consensus",
                "differencesText": "No material differences",
                "resultId": "R" * 16,
            },
        )

    assert response.status_code == 200
    bookmark = response.json()["bookmark"]
    assert bookmark["query"] == current
    assert bookmark["previous_question"] == previous
    assert bookmark["previous_turn"]["question"] == previous
    assert bookmark["previous_turn"]["consensus"] == "Original consensus"
    assert bookmark["previous_turn"]["differences_data"]["agreement"]["score"] == 82
    assert bookmark["share_result_id"] == ""
    meta = bookmarks_router._bookmark_meta(bookmark_id, bookmark)
    assert meta["query"] == current


def test_followup_consensus_updates_one_stable_chat_bookmark():
    bookmark_id = "stable_chat_bookmark"
    chat_id = "c" * 32
    turn_id = "2" * 32
    bookmark_ref = FakeBookmarkRef(
        bookmark_id,
        {
            "query": "First question",
            "responses": {"DeepSeek": "stale answer", "consensus": "First consensus"},
        },
    )
    fake_db = FakeFirestore(bookmark_ref)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)

    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", fake_db),
        patch.object(
            bookmarks_router,
            "_authoritative_consensus_payload",
            return_value={
                "question": "Second question",
                "consensus": "Second consensus",
                "differences": "Second differences",
                "differences_data": None,
                "sources": [],
                "model_responses": {"OpenAI": "new answer", "Gemini": "other answer"},
                "result_id": "",
            },
        ),
    ):
        response = TestClient(app).post(
            "/bookmark/consensus",
            json={
                "id_token": "token",
                "bookmarkId": bookmark_id,
                "chatId": chat_id,
                "turnId": turn_id,
                "question": "Second question",
                "previousQuestion": "First question",
                "consensusText": "Second consensus",
                "differencesText": "Second differences",
                "modelResponses": {
                    "OpenAI": "new answer",
                    "Gemini": "other answer",
                },
            },
        )

    assert response.status_code == 200
    bookmark = response.json()["bookmark"]
    assert bookmark["id"] == bookmark_id
    assert bookmark["query"] == "Second question"
    assert bookmark["chat_id"] == chat_id
    assert bookmark["turn_id"] == turn_id
    assert bookmark["responses"]["OpenAI"] == "new answer"
    assert bookmark["responses"]["Gemini"] == "other answer"
    assert bookmark["responses"]["DeepSeek"] == ""
    assert bookmark["responses"]["consensus"] == "Second consensus"


def test_bookmark_name_stays_the_first_question_of_the_conversation():
    """Der Sidebar-Name gehoert der ERSTEN Frage; `query` wandert weiter."""
    bookmark_id = "stable_chat_bookmark"
    chat_id = "c" * 32
    turn_id = "2" * 32
    bookmark_ref = FakeBookmarkRef(bookmark_id, {"responses": {}})
    fake_db = FakeFirestore(bookmark_ref)
    app = FastAPI()
    app.state.limiter = limiter
    limiter.reset()
    app.include_router(bookmarks_router.router)

    class FakeChatStore:
        def get_chat(self, uid, requested_chat_id):
            assert (uid, requested_chat_id) == ("uid-1", chat_id)
            return {"id": chat_id, "title": "First question"}

    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", fake_db),
        patch.object(bookmarks_router, "_chat_store", return_value=FakeChatStore()),
        patch.object(
            bookmarks_router,
            "_authoritative_consensus_payload",
            side_effect=[
                {
                    "question": "First question", "consensus": "First consensus",
                    "differences": "First differences", "differences_data": None,
                    "sources": [], "result_id": "",
                },
                {
                    "question": "Second question", "consensus": "Second consensus",
                    "differences": "Second differences", "differences_data": None,
                    "sources": [], "result_id": "",
                },
            ],
        ),
    ):
        client = TestClient(app)
        opening = client.post(
            "/bookmark/consensus",
            json={
                "id_token": "token",
                "bookmarkId": bookmark_id,
                "chatId": chat_id,
                "turnId": turn_id,
                "question": "First question",
                "consensusText": "First consensus",
                "differencesText": "First differences",
            },
        )
        followup = client.post(
            "/bookmark/consensus",
            json={
                "id_token": "token",
                "bookmarkId": bookmark_id,
                "chatId": chat_id,
                "turnId": turn_id,
                "question": "Second question",
                "previousQuestion": "First question",
                "consensusText": "Second consensus",
                "differencesText": "Second differences",
            },
        )

    assert opening.json()["bookmark"]["title"] == "First question"
    assert followup.status_code == 200
    bookmark = followup.json()["bookmark"]
    assert bookmark["title"] == "First question"
    assert bookmark["query"] == "Second question"
    assert bookmarks_router._bookmark_meta(bookmark_id, bookmark)["title"] == (
        "First question"
    )


def test_a_legacy_bookmark_without_a_title_falls_back_to_its_question():
    meta = bookmarks_router._bookmark_meta("legacy_id", {"query": "Only question"})
    assert meta["title"] == "Only question"


def test_a_follow_up_saves_although_the_turn_stored_a_normalized_question():
    """Der Chat-Turn speichert NFKC-normalisiert, der Browser schickt den Rohtext.

    Ein einziges geschuetztes Leerzeichen in einer Folgefrage liess den Lauf
    sichtbar durchlaufen, waehrend sein Bookmark mit 409 scheiterte.
    """
    raw_question = "Und was kostet das?"
    stored_question = unicodedata.normalize("NFKC", raw_question)
    assert raw_question != stored_question

    chat_id = "c" * 32
    turn_id = "2" * 32

    class FakeChatStore:
        def get_turn(self, uid, requested_chat_id, requested_turn_id):
            return {
                "status": "completed",
                "question": stored_question,
                "consensus": "Antwort",
                "differences": "",
                "differences_data": None,
                "sources": [],
                "model_answers": {"OpenAI": {"answer": "a", "model_label": "GPT"}},
                "included_models": ["OpenAI: GPT"],
                "consensus_model": "gpt-5",
                "result_id": "",
            }

        def get_chat(self, uid, requested_chat_id):
            return {"id": requested_chat_id, "title": "Erste Frage"}

    bookmark_ref = FakeBookmarkRef("stable_chat_bookmark", {"responses": {}})
    fake_db = FakeFirestore(bookmark_ref)
    app = FastAPI()
    app.state.limiter = limiter
    limiter.reset()
    app.include_router(bookmarks_router.router)

    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", fake_db),
        patch.object(bookmarks_router, "_chat_store", return_value=FakeChatStore()),
    ):
        response = TestClient(app).post(
            "/bookmark/consensus",
            json={
                "id_token": "token",
                "bookmarkId": "stable_chat_bookmark",
                "chatId": chat_id,
                "turnId": turn_id,
                "question": raw_question,
                "previousQuestion": "Erste Frage",
                "consensusText": "Antwort",
                "differencesText": "",
            },
        )

    assert response.status_code == 200
    assert response.json()["bookmark"]["query"] == raw_question


def test_a_follow_up_bookmark_may_rest_on_its_own_run_snapshot():
    """Ohne persistierten Chat-Turn ist die result_id der einzige Beleg.

    Der Browser schickt sie deshalb auch bei einer Folgefrage mit. Der
    Share-Verweis bleibt trotzdem leer -- ein Follow-up-Share wird spaeter
    serverseitig neu gebaut.
    """
    result_id = "R" * 16
    bookmark_ref = FakeBookmarkRef("followup_on_result", {"responses": {}})
    fake_db = FakeFirestore(bookmark_ref)
    app = FastAPI()
    app.state.limiter = limiter
    limiter.reset()
    app.include_router(bookmarks_router.router)

    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", fake_db),
        patch.object(
            bookmarks_router.share_snapshots,
            "get_pending_result",
            return_value={
                "question": "Zweite Frage",
                "consensus_md": "Zweiter Konsens",
                "differences_text": "",
                "differences_data": None,
                "sources": [],
                "included_models": ["OpenAI: GPT"],
                "consensus_model": "gpt-5",
                "model_responses": {"OpenAI": "a"},
                "vote_subject_id": result_id,
            },
        ),
    ):
        response = TestClient(app).post(
            "/bookmark/consensus",
            json={
                "id_token": "token",
                "bookmarkId": "followup_on_result",
                "resultId": result_id,
                "question": "Zweite Frage",
                "previousQuestion": "Erste Frage",
                "consensusText": "Zweiter Konsens",
                "differencesText": "",
            },
        )

    assert response.status_code == 200
    bookmark = response.json()["bookmark"]
    assert bookmark["responses"]["consensus"] == "Zweiter Konsens"
    assert bookmark["previous_question"] == "Erste Frage"
    assert bookmark["share_result_id"] == ""


def test_the_browser_sends_the_run_snapshot_with_every_consensus_bookmark():
    consensus_run = (
        Path(__file__).resolve().parents[1] / "static" / "js" / "consensus-run.js"
    ).read_text(encoding="utf-8")
    assert "context.consensus.resultId = data.result_id || null;" in consensus_run
    assert "resultId: context.consensus.resultId" in consensus_run
    assert "bookmarkPreviousQuestion ? null : data.result_id" not in consensus_run


def test_a_consensus_bookmark_without_a_completed_run_is_rejected():
    bookmark_id = "legacy_followup"
    bookmark_ref = FakeBookmarkRef(
        bookmark_id, {"query": "First", "title": "First", "responses": {}}
    )
    fake_db = FakeFirestore(bookmark_ref)
    app = FastAPI()
    app.state.limiter = limiter
    limiter.reset()
    app.include_router(bookmarks_router.router)

    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", fake_db),
    ):
        response = TestClient(app).post(
            "/bookmark/consensus",
            json={
                "id_token": "token",
                "bookmarkId": bookmark_id,
                "question": "Second",
                "previousQuestion": "First",
                "consensusText": "Second consensus",
                "differencesText": "Second differences",
            },
        )

    assert response.status_code == 409


def test_completed_turn_is_the_authoritative_source_for_model_provenance():
    chat_id = "c" * 32
    turn_id = "2" * 32

    class FakeChatStore:
        def get_turn(self, uid, requested_chat_id, requested_turn_id):
            assert (uid, requested_chat_id, requested_turn_id) == (
                "uid-1", chat_id, turn_id,
            )
            return {
                "status": "completed",
                "question": "Which source is authoritative?",
                "consensus": "The completed turn is authoritative.",
                "differences": "No material differences.",
                "differences_data": {"agreement": {"score": 81}},
                "sources": [],
                "included_models": ["OpenAI: Historical GPT"],
                "consensus_model": "Gemini-Pro",
                "model_answers": {
                    "OpenAI": {
                        "answer": "A server-owned answer.",
                        "model_label": "Historical GPT",
                        "model": "untrusted-wrong-field",
                    },
                },
                "result_id": "R" * 16,
            }

    with patch.object(bookmarks_router, "_chat_store", return_value=FakeChatStore()):
        payload = bookmarks_router._authoritative_consensus_payload(
            "uid-1", "", {"chat_id": chat_id, "turn_id": turn_id},
        )

    assert payload["model_responses"] == {"OpenAI": "A server-owned answer."}
    assert payload["model_labels"] == {"OpenAI": "Historical GPT"}
    assert payload["consensus_model"] == "Gemini-Pro"


def test_chat_bookmark_conversation_returns_complete_owner_bound_turns():
    bookmark_id = "stable_chat_bookmark"
    chat_id = "c" * 32
    fake_db = FakeBookmarkDatabase({
        "uid-1": {bookmark_id: {"query": "Latest", "chat_id": chat_id}},
    })

    class FakeChatStore:
        def list_turn_details(
            self, uid, requested_chat_id, *, cursor, limit, status=None
        ):
            # One owner-bound page call, filtered in the store: the failed turn
            # is never fetched in full, and the chat is verified only once.
            assert (uid, requested_chat_id, cursor, limit, status) == (
                "uid-1", chat_id, "", 50, "completed",
            )
            return {
                "turns": [
                    {
                        "id": "1" * 32,
                        "status": "completed",
                        "question": "First",
                        "consensus": "Answer",
                        "model_answers": {},
                    },
                    {
                        "id": "3" * 32,
                        "status": "completed",
                        "question": "Third",
                        "consensus": "Answer",
                        "model_answers": {},
                    },
                ],
                "next_cursor": None,
                "has_more": False,
            }

    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)
    app.add_middleware(CustomSecurityMiddleware)
    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", fake_db),
        patch.object(bookmarks_router, "_chat_store", return_value=FakeChatStore()),
    ):
        response = TestClient(app).get(
            f"/bookmarks/{bookmark_id}/conversation?limit=50",
            headers={"Authorization": "Bearer token"},
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert [turn["question"] for turn in response.json()["turns"]] == ["First", "Third"]


def test_agent_bookmark_returns_failed_turn_without_synthesis():
    bookmark_id, chat_id = "failed_agent", "c" * 32
    fake_db = FakeBookmarkDatabase({"uid-1": {bookmark_id: {
        "query": "Question", "chat_id": chat_id, "execution_mode": "agent"}}})
    turn = {"id": "1" * 32, "status": "failed", "execution_mode": "agent", "question": "Question",
            "agent_failure": {"code": "provider_timeout", "error": "The provider stopped responding."},
            "agent_review": {"status": "failed", "comparisons": [{"answers": [{"text": "Available evidence"}]}]}}
    class Store:
        def list_turn_details(self, uid, requested_chat_id, **kwargs):
            assert uid == "uid-1" and requested_chat_id == chat_id and kwargs['status'] is None
            return {"turns": [turn, {"status": "pending"}], "has_more": False}
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)
    with (patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
          patch.object(bookmarks_router, "db_firestore", fake_db),
          patch.object(bookmarks_router, "_chat_store", return_value=Store())):
        response = TestClient(app).get(f"/bookmarks/{bookmark_id}/conversation", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200 and response.json()['turns'] == [turn]


def test_chat_bookmark_conversation_falls_back_without_losing_middle_turns():
    bookmark_id = "stable_chat_bookmark"
    chat_id = "c" * 32
    fake_db = FakeBookmarkDatabase({
        "uid-1": {bookmark_id: {"query": "Fourth", "chat_id": chat_id}},
    })
    turn_ids = [str(index) * 32 for index in range(1, 5)]

    class FallbackChatStore:
        def list_turn_details(self, *_args, **_kwargs):
            raise RuntimeError("optimized collection read unavailable")

        def list_turns(self, uid, requested_chat_id, *, cursor, limit):
            assert (uid, requested_chat_id, cursor, limit) == (
                "uid-1", chat_id, "", 50,
            )
            return {
                "turns": [
                    {"id": turn_id, "status": "completed"}
                    for turn_id in turn_ids
                ],
                "next_cursor": None,
                "has_more": False,
            }

        def get_turn(self, uid, requested_chat_id, turn_id):
            index = turn_ids.index(turn_id) + 1
            return {
                "id": turn_id,
                "status": "completed",
                "position": index,
                "question": f"Question {index}",
                "consensus": f"Answer {index}",
                "model_answers": {},
            }

    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)
    app.add_middleware(CustomSecurityMiddleware)
    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", fake_db),
        patch.object(bookmarks_router, "_chat_store", return_value=FallbackChatStore()),
    ):
        response = TestClient(app).get(
            f"/bookmarks/{bookmark_id}/conversation?limit=50",
            headers={"Authorization": "Bearer token"},
        )

    assert response.status_code == 200
    assert [turn["question"] for turn in response.json()["turns"]] == [
        "Question 1", "Question 2", "Question 3", "Question 4",
    ]


def _prepare_share_result(bookmark_ref, chat_store, *, new_result_id="R" * 16):
    app = FastAPI()
    app.state.limiter = limiter
    limiter.reset()
    app.include_router(bookmarks_router.router)
    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", FakeFirestore(bookmark_ref)),
        patch.object(bookmarks_router, "_chat_store", return_value=chat_store),
        patch.object(
            bookmarks_router.share_snapshots,
            "pending_result_is_available",
            return_value=False,
        ),
        patch.object(
            bookmarks_router.share_snapshots,
            "save_pending_result",
            return_value=new_result_id,
        ) as save_pending,
    ):
        response = TestClient(app).post(
            "/bookmark/consensus/share-result",
            json={"id_token": "token", "bookmarkId": bookmark_ref.id},
        )
    payload = save_pending.call_args.args[0] if save_pending.called else None
    return response, payload


class OneTurnChatStore:
    def __init__(self, turn):
        self.turn = turn

    def get_turn(self, uid, chat_id, turn_id):
        assert uid == "uid-1"
        if (chat_id, turn_id) != ("c" * 32, "2" * 32):
            raise bookmarks_router.ChatNotFound("Chat not found")
        return self.turn


def _completed_turn(**overrides):
    return {
        "status": "completed",
        "question": "Why is the sky blue?",
        "consensus": "Rayleigh scattering. [S1]",
        "differences": "No material differences.",
        "differences_data": {"claims": [], "differences": [], "models_compared": ["OpenAI"]},
        "sources": [{"id": "S1", "title": "NASA", "url": "https://science.nasa.gov/sky"}],
        "included_models": ["OpenAI", "Gemini"],
        "consensus_model": "Gemini",
        "model_answers": {
            "OpenAI": {"answer": "Scattering.", "model_label": "GPT-6 Luna"},
            "Gemini": {"answer": "Scattering too.", "model_label": "Gemini 3 Flash"},
        },
        "result_id": "",
        **overrides,
    }


def test_legacy_bookmark_without_a_turn_gets_no_new_share_result():
    """Without a chat turn nothing proves where `query`/`sources` came from."""
    bookmark_ref = FakeBookmarkRef(
        "V2h5Pw__",
        {
            "query": "Why?",
            "responses": {
                "OpenAI": "Existing model answer",
                "consensus": "Stored consensus",
                "differences": "Stored differences",
            },
            "sources": [{"id": "S1", "url": "https://example.test/source"}],
        },
    )

    response, payload = _prepare_share_result(bookmark_ref, OneTurnChatStore(None))

    assert response.status_code == 409
    assert "Ask the question again" in response.json()["detail"]
    assert payload is None
    assert "share_result_id" not in bookmark_ref.data


def test_bookmark_share_is_rebuilt_from_its_completed_turn():
    bookmark_ref = FakeBookmarkRef(
        "sky_bookmark",
        {
            # The model save (POST /bookmark) may have written these three;
            # none of them may reach the share.
            "query": "Client claimed question",
            "sources": [{"id": "S1", "url": "https://phish.example/login"}],
            "model_labels": {"OpenAI": "Visit phish example"},
            "chat_id": "c" * 32,
            "turn_id": "2" * 32,
            "consensus_model": "Anthropic",
            "responses": {
                "consensus": "Rayleigh scattering. [S1]",
                "differences": "Stale bookmark differences",
                # The Resolve round writes its server result only here.
                "differences_data": {
                    "claims": [],
                    "differences": [{
                        "claim": "Main cause",
                        "type": "contradiction",
                        "severity": "major",
                        "positions": [
                            {"stance": "Rayleigh scattering.", "models": ["OpenAI"]},
                            {"stance": "Mie scattering.", "models": ["Gemini"]},
                        ],
                        "resolution": {
                            "outcome": "resolved",
                            "results": [{"model": "Gemini", "decision": "revise",
                                         "position": "Rayleigh", "reason": "Wavelength"}],
                        },
                    }],
                    "models_compared": ["OpenAI", "Gemini"],
                },
            },
        },
    )

    response, payload = _prepare_share_result(
        bookmark_ref, OneTurnChatStore(_completed_turn())
    )

    assert response.status_code == 200, response.text
    assert payload["question"] == "Why is the sky blue?"
    assert payload["consensus_md"] == "Rayleigh scattering. [S1]"
    assert payload["differences_text"] == "No material differences."
    assert [source["url"] for source in payload["sources"]] == ["https://science.nasa.gov/sky"]
    assert payload["included_models"] == [
        "OpenAI: GPT-6 Luna", "Google Gemini: Gemini 3 Flash",
    ]
    assert payload["consensus_model"] == "Anthropic"
    [difference] = payload["differences_data"]["differences"]
    assert difference["resolution"]["outcome"] == "resolved"
    assert bookmark_ref.data["share_result_id"] == "R" * 16


@pytest.mark.parametrize("turn", [
    None,
    _completed_turn(status="pending"),
    # The bookmark points at a turn whose answer is not its consensus.
    _completed_turn(consensus="A different answer."),
])
def test_bookmark_share_needs_the_completed_turn_of_its_consensus(turn):
    bookmark_ref = FakeBookmarkRef(
        "sky_bookmark",
        {
            "query": "Why is the sky blue?",
            "chat_id": "c" * 32,
            "turn_id": "2" * 32,
            "responses": {"consensus": "Rayleigh scattering. [S1]"},
        },
    )

    response, payload = _prepare_share_result(bookmark_ref, OneTurnChatStore(turn))

    assert response.status_code == 409
    assert payload is None


def _deep_merged(current, incoming):
    merged = dict(current)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merged(merged[key], value)
        else:
            merged[key] = value
    return merged


class _MergingTransaction(ChatFakeTransaction):
    def set(self, ref, data, merge=False):
        current = self.database.documents.get(ref.path)
        super().set(ref, _deep_merged(current, data) if merge and current is not None else data)


class FirestoreMergeDatabase(FakeChatDatabase):
    """Merges nested maps on set(merge=True) like Firestore does.

    The plain fake replaces the document instead. The share attack depends on
    the real behaviour: a model save merges its answer into `responses` and
    leaves the stored consensus where it is.
    """

    def run_transaction(self, operation):
        transaction = _MergingTransaction(self)
        result = operation(transaction)
        transaction.commit()
        return result

    def apply_set(self, ref, data, merge=False):
        current = self.documents.get(ref.path)
        if merge and current is not None:
            data, merge = _deep_merged(current, data), False
        super().apply_set(ref, data, merge=merge)


def test_a_model_save_cannot_put_a_forged_question_or_sources_on_a_share():
    """Audit S3: real consensus, forged question and sources, then share."""
    from app.api.routers import share as share_router
    from app.services.chat_store import ChatStore

    database = FirestoreMergeDatabase()
    store = ChatStore(database)
    chat = store.create_chat("uid-1")
    question = "Why is the sky blue?"
    turn = store.create_turn(
        "uid-1", chat["id"], question=question, mode="Standard",
        deep_search=False, selected_models=["OpenAI", "Gemini"],
        consensus_model="Gemini",
    )
    store.complete_turn(
        "uid-1", chat["id"], turn["id"],
        question=question,
        model_answers={
            "OpenAI": {"answer": "Scattering.", "model_label": "GPT-6 Luna"},
            "Gemini": {"answer": "Scattering too.", "model_label": "Gemini 3 Flash"},
        },
        consensus="Short wavelengths scatter most. [S1]",
        differences="No material differences.",
        differences_data=None,
        sources=[{"id": "S1", "title": "NASA", "url": "https://science.nasa.gov/sky"}],
    )

    app = FastAPI()
    app.state.limiter = limiter
    limiter.reset()
    bookmarks_router.api_uid_limiter.reset()
    app.include_router(bookmarks_router.router)
    app.include_router(share_router.router)
    client = TestClient(app)
    bookmark_id = "sky_bookmark"
    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(share_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", database),
        patch.object(share_snapshots, "db_firestore", database),
        patch.object(share_snapshots, "schedule_share_cleanup"),
    ):
        saved = client.post("/bookmark/consensus", json={
            "id_token": "token", "bookmarkId": bookmark_id, "question": question,
            "chatId": chat["id"], "turnId": turn["id"],
        })
        assert saved.status_code == 200, saved.text
        forged = client.post("/bookmark", json={
            "id_token": "token", "bookmarkId": bookmark_id,
            "question": "Which bank login do I need to verify my account?",
            "response": "Any text", "modelName": "OpenAI", "mode": "Standard",
            "sources": [{"id": "S1", "title": "Verify now",
                         "url": "https://phish.example/login"}],
        })
        assert forged.status_code == 200, forged.text
        # The forgery landed next to the real consensus on the private bookmark.
        bookmark = forged.json()["bookmark"]
        assert bookmark["query"].startswith("Which bank login")
        assert bookmark["sources"][0]["url"] == "https://phish.example/login"
        assert bookmark["responses"]["consensus"] == "Short wavelengths scatter most. [S1]"

        prepared = client.post("/bookmark/consensus/share-result", json={
            "id_token": "token", "bookmarkId": bookmark_id,
        })
        assert prepared.status_code == 200, prepared.text
        shared = client.post("/api/share", json={
            "id_token": "token", "result_id": prepared.json()["result_id"],
        })
        assert shared.status_code == 200, shared.text

    share = database.documents[(share_snapshots.SHARES_COLLECTION, shared.json()["share_id"])]
    assert share["question"] == question
    assert share["consensus_md"] == "Short wavelengths scatter most. [S1]"
    assert [source["url"] for source in share["sources"]] == ["https://science.nasa.gov/sky"]
    assert "phish.example" not in json.dumps(share, default=str)
    assert "bank login" not in json.dumps(share, default=str)


def test_consensus_bookmark_reuses_live_share_result():
    bookmark_id = "V2h5Pw__"
    existing_result_id = "E" * 16
    bookmark_ref = FakeBookmarkRef(
        bookmark_id,
        {
            "query": "Why?",
            "share_result_id": existing_result_id,
            "responses": {"consensus": "Stored consensus"},
        },
    )
    fake_db = FakeFirestore(bookmark_ref)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)

    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", fake_db),
        patch.object(
            bookmarks_router.share_snapshots,
            "pending_result_is_available",
            return_value=True,
        ),
        patch.object(bookmarks_router.share_snapshots, "save_pending_result") as save_pending,
    ):
        response = TestClient(app).post(
            "/bookmark/consensus/share-result",
            json={"id_token": "token", "bookmarkId": bookmark_id},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success", "result_id": existing_result_id, "created": False,
    }
    save_pending.assert_not_called()


def test_bookmark_share_result_rejects_a_different_visible_revision():
    bookmark_id = "V2h5Pw__"
    bookmark_ref = FakeBookmarkRef(
        bookmark_id,
        {
            "query": "Follow-up B",
            "chat_id": "a" * 32,
            "turn_id": "b" * 32,
            "share_result_id": "",
            "responses": {"consensus": "Newer consensus B"},
        },
    )
    old_visible_revision = {
        "query": "Original A",
        "chat_id": "a" * 32,
        "turn_id": "c" * 32,
        "share_result_id": "",
        "responses": {"consensus": "Visible consensus A"},
    }
    fake_db = FakeFirestore(bookmark_ref)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)

    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", fake_db),
        patch.object(bookmarks_router.share_snapshots, "save_pending_result") as save_pending,
    ):
        response = TestClient(app).post(
            "/bookmark/consensus/share-result",
            json={
                "id_token": "token",
                "bookmarkId": bookmark_id,
                "expectedVersion": bookmarks_router._bookmark_share_version(old_visible_revision),
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Bookmark changed. Reopen it before sharing."
    save_pending.assert_not_called()


def test_bookmark_frontend_prepares_share_and_watch_result():
    root = Path(__file__).resolve().parents[1]
    firebase = (root / "static" / "firebase.js").read_text(encoding="utf-8")
    share_dialog = (root / "static" / "js" / "share-dialog.js").read_text(encoding="utf-8")
    watch = (root / "static" / "js" / "watch.js").read_text(encoding="utf-8")
    assert 'fetch("/bookmark/consensus/share-result"' in firebase
    assert "prepareBookmarkShareResult(bookmark);" in firebase
    assert "resolveCurrentShareResultId" in share_dialog
    assert "resolveCurrentShareResultId" in watch


def test_consensus_frontend_uses_primary_write_and_small_retry_payload():
    root = Path(__file__).resolve().parents[1]
    firebase = (root / "static" / "firebase.js").read_text(encoding="utf-8")
    consensus_run = (root / "static" / "js" / "consensus-run.js").read_text(
        encoding="utf-8"
    )
    fallback = firebase.split("async function saveBookmarkConsensus(", 1)[1]
    fallback = fallback.split("window.saveBookmarkConsensus =", 1)[0]

    assert "bookmarkId: context.bookmark.id" in consensus_run
    assert "data.bookmark_persisted === true && data.bookmark_meta" in consensus_run
    assert "window.acceptPersistedConsensusBookmark" in firebase
    assert "keepalive: true" in fallback
    assert "attempt < 3" in fallback
    assert "sources:" not in fallback
    assert "differencesData:" not in fallback
    assert "modelResponses:" not in fallback


def test_bookmark_frontend_restores_every_turn_and_keeps_a_context_fallback():
    root = Path(__file__).resolve().parents[1]
    firebase = (root / "static" / "firebase.js").read_text(encoding="utf-8")
    query_send = (root / "static" / "js" / "query-send.js").read_text(encoding="utf-8")
    consensus_run = (root / "static" / "js" / "consensus-run.js").read_text(encoding="utf-8")

    assert "function bookmarkDisplayQuestion(bookmark)" in firebase
    # Auch ein Direktvergleich-Bookmark laedt mit seiner Frage zurueck.
    assert "window.App?.setThreadQuestion?.(displayQuestion);" in firebase
    # One step, never emptied first (Apple audit A1).
    assert "renderStoredTurns?.(materialized.historyTurns.length" in firebase
    assert '"/conversation?limit=50"' in firebase
    # By bookmark ID, beside the detail request (Apple audit D2).
    assert "function loadBookmarkConversationOnce(bookmarkId)" in firebase
    assert "This chat’s conversation was incomplete." in firebase
    assert "This chat’s conversation repeated a page." in firebase
    assert "function bookmarkFallbackTurn(bookmark)" in firebase
    assert "restoreCompletedChat?.(" in firebase
    assert "continuationTurn.turn_id" in firebase
    assert "followup?.offer?.(" in firebase
    assert "markContinuationUnavailable?.()" in firebase
    assert "Follow-ups still use the saved chat context" in firebase
    assert "window.App.bookmarkSession" in firebase
    assert "question: displayQuestion" in firebase
    assert "function conversationPayload(context, payload)" in query_send
    assert "context.previousExchange.question" in query_send
    assert "previousQuestion: context.previousExchange?.question" in consensus_run
    assert "previousTurn: context.previousExchange?.turn" in consensus_run
    assert "buildStoredAgreement(differencesData)" in consensus_run
    assert "Start a new chat — the saved context is unavailable" in consensus_run


def test_bookmark_restore_uses_historical_model_labels_without_mutating_picker_state():
    root = Path(__file__).resolve().parents[1]
    firebase = (root / "static" / "firebase.js").read_text(encoding="utf-8")
    query_send = (root / "static" / "js" / "query-send.js").read_text(encoding="utf-8")

    helper = firebase.split("function applyBookmarkModelPresentation(bookmark) {", 1)[1]
    helper = helper.split("// Diese Funktion füllt die UI", 1)[0]

    assert "bookmark?.model_labels" in helper
    assert "labelEl.textContent = visibleLabel" in helper
    assert "select.value" not in helper
    assert "localStorage.setItem" not in helper
    assert "localStorage.removeItem" not in helper
    assert "bookmarkCitationModels = applyBookmarkModelPresentation(bookmark);" in firebase
    assert 'consensusModel: bookmark.consensus_model || ""' in firebase
    run_view = (root / "static" / "js" / "run-view.js").read_text(encoding="utf-8")
    assert "config?.modelLabel" in run_view
    assert "modelText.textContent = config.modelLabel" in run_view
    # The Reasoning switch configures the next run: restoring a bookmark,
    # including an old "Deep Think" one, never touches it.
    assert "reasoningToggle" not in firebase
    assert "deepSearchToggle" not in firebase
    assert "sourceSelect.value" not in run_view
    assert "localStorage.setItem" not in run_view


def test_bookmark_restores_the_view_the_run_had_not_the_current_toggle():
    """Ein Direktvergleich (kein Consensus) laedt als Direktvergleich zurueck.

    Vorher entschied allein der heutige Agent-Mode-Schalter ueber die Ansicht:
    war er inzwischen wieder an, verschwanden die gespeicherten Modellantworten
    hinter "Compare answers" und das Bookmark zeigte nur noch die Frage.
    """
    root = Path(__file__).resolve().parents[1]
    firebase = (root / "static" / "firebase.js").read_text(encoding="utf-8")
    core = (root / "static" / "js" / "app-core.js").read_text(encoding="utf-8")
    agent = (root / "static" / "js" / "agent-mode.js").read_text(encoding="utf-8")
    consensus_css = (root / "static" / "css" / "components-consensus.css").read_text(encoding="utf-8")

    # Der Modus des Laufs steckt im Bookmark selbst, nicht im Schalter.
    assert "function isDirectComparisonBookmark(bookmark)" in firebase
    assert "const directComparison = isDirectComparisonBookmark(bookmark);" in firebase
    assert "window.enterDirectComparisonView?.();" in firebase

    # Eine Ansicht, ein Aufbau — geteilt mit dem frisch gesendeten Vergleich.
    assert 'document.body.classList.add("direct-comparison-active")' in core
    # Der Ausstieg in den Thread raeumt die Marke wieder ab.
    assert 'classList.remove("is-hero", "direct-comparison-active", "direct-comparison-preview")' in core

    # Auch das Umlegen behaelt jetzt den sichtbaren Direktvergleich. Die neue
    # Composer-Leiste erklaert dessen urspruenglichen Modus separat; erst die
    # naechste Frage ersetzt das Ergebnis (Browser-Test: test_composer_mode_bar).
    strip = 'document.body.classList.remove("direct-comparison-active");'
    assert strip not in agent

    # Das fruehere Modell-Panel ist samt Markup entfernt; es kann nicht mehr
    # ueber den wiederhergestellten Antworten auftauchen.
    assert "agent-mode-panel" not in consensus_css
    assert 'id="agentModePanel"' not in (root / "templates" / "index.html").read_text(encoding="utf-8")


LIST_START = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


def _seed_bookmarks(database, items, *, uid="uid-1"):
    """Store bookmarks newest first: the first item has the latest timestamp."""
    for index, (bookmark_id, data) in enumerate(items.items()):
        database.documents[("users", uid, "bookmarks", bookmark_id)] = {
            "timestamp": LIST_START - timedelta(minutes=index), **data,
        }


def _list_bookmarks(database, path):
    limiter._storage.reset()
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)
    with patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"), \
            patch.object(bookmarks_router, "db_firestore", database):
        return TestClient(app).get(path, headers={"Authorization": "Bearer token"})


def _ids(response):
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["bookmarks"]]


def test_bookmark_list_is_compact_and_cursor_paginated():
    database = FakeChatDatabase()
    _seed_bookmarks(database, {
        "first_id": {"query": "First", "mode": "Normal", "responses": {"OpenAI": "large", "consensus": "full"}},
        "second_id": {"query": "Second", "responses": {"Gemini": "large"}},
        "third_id": {"query": "Third", "responses": {"Grok": "large"}},
    })
    first = _list_bookmarks(database, "/bookmarks?limit=2")
    second = _list_bookmarks(database, "/bookmarks?limit=2&cursor=" + first.json()["next_cursor"])

    assert _ids(first) == ["first_id", "second_id"]
    assert "responses" not in first.json()["bookmarks"][0]
    assert first.json()["bookmarks"][0]["has_consensus"] is True
    [third] = second.json()["bookmarks"]
    assert third.pop("timestamp").startswith("2026-10-11T11:58:00")
    assert third == {
        "id": "third_id", "query": "Third", "title": "Third", "title_source": "", "mode": "",
        "pinned": False, "pinned_at": None,
        "has_consensus": False, "model_count": 1,
        "source_count": 0, "attachment_count": 0,
    }
    assert second.json()["has_more"] is False


def _write_bookmark(database, bookmark_id, patch_data, *, uid="uid-1"):
    ref = database.collection("users").document(uid).collection("bookmarks").document(bookmark_id)
    return persistence_guard.write_bookmark(uid=uid, doc_ref=ref, patch=patch_data, db=database)


def test_bookmark_list_reads_only_the_sidebar_fields_of_summarized_bookmarks():
    """Audit C4: the sidebar read every full bookmark (up to 750 kB with all
    answers) for a title and four counts. Written bookmarks carry those counts
    in list_summary, so listing them reads no full document anymore."""
    database = FakeChatDatabase()
    _write_bookmark(database, "big_id", {
        "query": "Big", "timestamp": LIST_START,
        "responses": {"OpenAI": "x" * 50_000, "Gemini": "y", "consensus": "z"},
        "sources": [{"url": "https://a.example"}], "attachments": [{"name": "a.pdf"}],
    })
    database.full_document_log.clear()

    response = _list_bookmarks(database, "/bookmarks")

    [row] = response.json()["bookmarks"]
    assert {key: row[key] for key in ("has_consensus", "model_count", "source_count", "attachment_count")} == {
        "has_consensus": True, "model_count": 2, "source_count": 1, "attachment_count": 1,
    }
    assert ("users", "uid-1", "bookmarks", "big_id") not in database.full_document_log


def test_bookmark_list_summary_follows_partial_merges():
    database = FakeChatDatabase()
    _write_bookmark(database, "b1", {
        "query": "Q", "timestamp": LIST_START, "responses": {"OpenAI": "a", "Grok": "b"},
    })
    # Later saves merge only part of the document; the counts still describe all of it.
    _write_bookmark(database, "b1", {"responses": {"consensus": "c"}, "title": "Named"})
    stored = database.documents[("users", "uid-1", "bookmarks", "b1")]

    assert persistence_guard.stored_bookmark_list_summary(stored) == {
        "has_consensus": True, "model_count": 2, "source_count": 0, "attachment_count": 0,
    }
    assert persistence_guard.bookmark_list_summary(stored) == persistence_guard.stored_bookmark_list_summary(stored)


def test_legacy_bookmarks_without_summary_are_read_in_full_once_per_list():
    database = FakeChatDatabase()
    _write_bookmark(database, "new_id", {"query": "New", "timestamp": LIST_START})
    database.documents[("users", "uid-1", "bookmarks", "old_id")] = {
        "query": "Old", "timestamp": LIST_START - timedelta(minutes=1),
        "responses": {"OpenAI": "a", "consensus": "c"},
        # A damaged summary counts as missing instead of showing wrong numbers.
        "list_summary": {"has_consensus": "yes"},
    }
    database.full_document_log.clear()

    response = _list_bookmarks(database, "/bookmarks")

    rows = {row["id"]: row for row in response.json()["bookmarks"]}
    assert rows["old_id"]["model_count"] == 1 and rows["old_id"]["has_consensus"] is True
    assert rows["new_id"]["model_count"] == 0
    assert database.full_document_log.count(("users", "uid-1", "bookmarks", "old_id")) == 1
    assert ("users", "uid-1", "bookmarks", "new_id") not in database.full_document_log


def test_backfill_gives_legacy_bookmarks_their_summary_only_with_apply():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "backfill_bookmark_list_summary",
        Path(__file__).resolve().parents[1] / "scripts" / "backfill_bookmark_list_summary.py",
    )
    backfill = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backfill)
    database = FakeChatDatabase()
    database.documents[("users", "uid-1")] = {}
    _write_bookmark(database, "new_id", {"query": "New", "timestamp": LIST_START})
    path = ("users", "uid-1", "bookmarks", "old_id")
    database.documents[path] = {"query": "Old", "timestamp": LIST_START, "responses": {"OpenAI": "a"}}

    backfill.main([], db=database)
    assert "list_summary" not in database.documents[path]

    backfill.main(["--apply"], db=database)
    assert persistence_guard.stored_bookmark_list_summary(database.documents[path])["model_count"] == 1
    assert database.documents[path]["query"] == "Old"
    assert list(backfill.missing_summaries(database)) == []


def test_next_bookmark_page_survives_its_boundary_row_being_deleted():
    """Lokaler Test 2026-10-11: "Load more" antwortete 400 "Bookmark cursor
    expired", weil der Cursor nur das Dokument der letzten Zeile nannte und
    genau dieses Bookmark inzwischen geloescht war."""
    database = FakeChatDatabase()
    _seed_bookmarks(database, {f"b{index}": {"query": f"Q{index}"} for index in range(1, 6)})
    first = _list_bookmarks(database, "/bookmarks?limit=2")
    assert _ids(first) == ["b1", "b2"]

    del database.documents[("users", "uid-1", "bookmarks", "b2")]
    after = _list_bookmarks(database, "/bookmarks?limit=2&cursor=" + first.json()["next_cursor"])

    assert _ids(after) == ["b3", "b4"]
    assert after.json()["has_more"] is True


def test_next_bookmark_page_continues_when_its_boundary_row_moves_up():
    # An Agent turn saves its bookmark with a new timestamp. The next page
    # still starts where the list stood instead of again at the top.
    database = FakeChatDatabase()
    _seed_bookmarks(database, {f"b{index}": {"query": f"Q{index}"} for index in range(1, 6)})
    first = _list_bookmarks(database, "/bookmarks?limit=2")

    database.documents[("users", "uid-1", "bookmarks", "b2")]["timestamp"] = LIST_START + timedelta(hours=1)
    after = _list_bookmarks(database, "/bookmarks?limit=2&cursor=" + first.json()["next_cursor"])

    assert _ids(after) == ["b3", "b4"]


def test_bookmark_pages_split_equal_timestamps_without_losing_a_row():
    database = FakeChatDatabase()
    for bookmark_id in ("b1", "b2", "b3", "b4"):
        database.documents[("users", "uid-1", "bookmarks", bookmark_id)] = {
            "query": bookmark_id, "timestamp": LIST_START,
        }
    first = _list_bookmarks(database, "/bookmarks?limit=2")
    second = _list_bookmarks(database, "/bookmarks?limit=2&cursor=" + first.json()["next_cursor"])

    assert _ids(first) + _ids(second) == ["b4", "b3", "b2", "b1"]


def _pin(database, bookmark_id, pinned, *, uid="uid-1"):
    limiter._storage.reset()
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)
    with patch.object(bookmarks_router, "verify_user_token", return_value=uid),             patch.object(bookmarks_router, "db_firestore", database):
        return TestClient(app).patch(f"/bookmarks/{bookmark_id}/pin", headers={"Authorization": "Bearer token"},
                                     json={"pinned": pinned})


def test_a_pinned_chat_comes_with_the_first_page_whatever_its_age():
    """The row menu pins a chat to the top of the sidebar. The first page
    brings every pinned chat along, the latest pin first, so one pinned long
    ago is not waiting on page five; later pages bring no pinned block."""
    database = FakeChatDatabase()
    _seed_bookmarks(database, {f"b{index}": {"query": f"Q{index}"} for index in range(1, 7)})

    old = _pin(database, "b6", True)
    _pin(database, "b5", True)
    first = _list_bookmarks(database, "/bookmarks?limit=2")
    second = _list_bookmarks(database, "/bookmarks?limit=2&cursor=" + first.json()["next_cursor"])

    assert old.status_code == 200, old.text
    assert old.json()["bookmark"]["pinned"] is True
    assert old.json()["bookmark"]["pinned_at"]
    assert [row["id"] for row in first.json()["pinned"]] == ["b5", "b6"]
    assert all(row["pinned"] is True for row in first.json()["pinned"])
    assert _ids(first) == ["b1", "b2"]
    assert all(row["pinned"] is False for row in first.json()["bookmarks"])
    assert second.json()["pinned"] == []


def test_a_pin_outlives_later_saves_and_unpinning_returns_the_chat_to_its_date():
    database = FakeChatDatabase()
    _seed_bookmarks(database, {"b1": {"query": "Q1"}, "b2": {"query": "Q2"}})

    _pin(database, "b2", True)
    _write_bookmark(database, "b2", {"responses": {"consensus": "A later answer"}})
    pinned = _list_bookmarks(database, "/bookmarks").json()
    unpinned = _pin(database, "b2", False)
    after = _list_bookmarks(database, "/bookmarks").json()

    assert [row["id"] for row in pinned["pinned"]] == ["b2"]
    assert unpinned.json()["bookmark"]["pinned"] is False
    assert unpinned.json()["bookmark"]["pinned_at"] is None
    assert after["pinned"] == []
    assert [row["id"] for row in after["bookmarks"]] == ["b1", "b2"]


def test_pinning_a_missing_chat_creates_nothing():
    database = FakeChatDatabase()

    response = _pin(database, "gone_bookmark", True)
    invalid = _pin(database, "gone_bookmark", "yes")

    assert response.status_code == 404
    assert invalid.status_code == 422
    assert ("users", "uid-1", "bookmarks", "gone_bookmark") not in database.documents


def _cursor(payload):
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


@pytest.mark.parametrize("cursor", [
    "garbage",
    # The previous format named only a document, which is no position.
    _cursor({"id": "b2"}),
    # A timestamp that does not round-trip would start at a shifted position.
    _cursor({"t": "2026-10-11T12:00:00Z", "id": "b2"}),
    _cursor({"t": "2026-10-11T12:00:00.000000Z", "id": "b2/../x"}),
])
def test_an_unusable_bookmark_cursor_is_a_client_error(cursor):
    database = FakeChatDatabase()
    _seed_bookmarks(database, {"b1": {"query": "Q1"}})

    response = _list_bookmarks(database, "/bookmarks?limit=2&cursor=" + cursor)

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid bookmark cursor"


def test_bookmark_detail_is_owner_scoped_and_frontend_loads_on_open():
    fake_db = FakeBookmarkDatabase({
        "owner": {"owned_id": {"query": "Owned", "responses": {"consensus": "Full answer"}}},
        "other": {},
    })
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)

    def verify(token):
        return "owner" if token == "owner-token" else "other"

    with patch.object(bookmarks_router, "verify_user_token", side_effect=verify), \
            patch.object(bookmarks_router, "db_firestore", fake_db):
        client = TestClient(app)
        owned = client.get("/bookmarks/owned_id", headers={"Authorization": "Bearer owner-token"})
        hidden = client.get("/bookmarks/owned_id", headers={"Authorization": "Bearer other-token"})
    assert owned.status_code == 200
    assert owned.json()["bookmark"]["responses"]["consensus"] == "Full answer"
    assert hidden.status_code == 404

    firebase = (Path(__file__).resolve().parents[1] / "static" / "firebase.js").read_text(encoding="utf-8")
    assert 'fetch("/bookmarks/" + encodeURIComponent(bookmarkId)' in firebase
    assert 'const path = "/bookmarks?limit=35"' in firebase
    assert "bookmarkDetailCache.clear()" in firebase
    # One delegated listener opens every saved row (Apple audit E2/E5).
    assert "window.openBookmark(row.dataset.id)" in firebase


# ---------------------------------------------------------------------------
# Ein Bookmark ist der einzige Griff an seinem Chat. Wird es geloescht, muss
# der Chat mitgehen — sonst bleibt das Transcript unerreichbar liegen.
# ---------------------------------------------------------------------------


class DeletableBookmarkRef(FakeBookmarkRef):
    def __init__(self, bookmark_id, data, events=None):
        super().__init__(bookmark_id, data)
        self.deleted = False
        self.events = events if events is not None else []

    def delete(self):
        self.deleted = True
        self.events.append("bookmark_deleted")


class RecordingChatStore:
    """Double for the durable deletion contract of ChatStore.

    ``request_chat_deletion`` commits tombstone + job, ``run_chat_deletion``
    runs the cascade and reports (never raises) a failure.
    """

    def __init__(self, error=None, queue_error=None, events=None):
        self.deleted = []
        self.queued = []
        self.error = error
        self.queue_error = queue_error
        self.events = events if events is not None else []

    def request_chat_deletion(self, uid, chat_id):
        if self.queue_error:
            raise self.queue_error
        self.queued.append((uid, chat_id))
        self.events.append("queued")

    def run_chat_deletion(self, uid, chat_id):
        self.deleted.append((uid, chat_id))
        self.events.append("cascade")
        return self.error is None


def _delete_bookmark(bookmark_ref, chat_store):
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)
    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", FakeFirestore(bookmark_ref)),
        patch.object(bookmarks_router, "_chat_store", return_value=chat_store),
    ):
        return TestClient(app).request(
            "DELETE",
            "/bookmark",
            json={"id_token": "token", "bookmarkId": bookmark_ref.id},
        )


def test_deleting_a_chat_bookmark_also_deletes_its_chat():
    chat_id = "c" * 32
    bookmark_ref = DeletableBookmarkRef("chat_bookmark", {"query": "Q", "chat_id": chat_id})
    chat_store = RecordingChatStore()

    response = _delete_bookmark(bookmark_ref, chat_store)

    assert response.status_code == 200
    assert bookmark_ref.deleted is True
    assert chat_store.deleted == [("uid-1", chat_id)]


def test_deleting_a_legacy_bookmark_touches_no_chat():
    bookmark_ref = DeletableBookmarkRef("legacy_bookmark", {"query": "Q"})
    chat_store = RecordingChatStore()

    response = _delete_bookmark(bookmark_ref, chat_store)

    assert response.status_code == 200
    assert bookmark_ref.deleted is True
    assert chat_store.deleted == []


def test_a_failing_chat_cascade_does_not_fail_the_bookmark_deletion():
    chat_id = "c" * 32
    bookmark_ref = DeletableBookmarkRef("chat_bookmark", {"query": "Q", "chat_id": chat_id})
    chat_store = RecordingChatStore(error=RuntimeError("firestore unavailable"))

    response = _delete_bookmark(bookmark_ref, chat_store)

    # The deletion is durably committed (tombstone + job) before the handle
    # goes away, so a failing cascade is a queued retry, not an error the user
    # has to act on.
    assert response.status_code == 200
    assert bookmark_ref.deleted is True
    assert chat_store.queued == [("uid-1", chat_id)]


def test_chat_deletion_job_is_committed_before_the_bookmark_handle_is_removed():
    chat_id = "c" * 32
    events = []
    bookmark_ref = DeletableBookmarkRef(
        "chat_bookmark", {"query": "Q", "chat_id": chat_id}, events=events
    )
    chat_store = RecordingChatStore(events=events)

    response = _delete_bookmark(bookmark_ref, chat_store)

    assert response.status_code == 200
    assert events == ["queued", "bookmark_deleted", "cascade"]


def test_bookmark_is_kept_when_the_chat_deletion_job_cannot_be_queued():
    chat_id = "c" * 32
    bookmark_ref = DeletableBookmarkRef("chat_bookmark", {"query": "Q", "chat_id": chat_id})
    chat_store = RecordingChatStore(queue_error=RuntimeError("firestore unavailable"))

    response = _delete_bookmark(bookmark_ref, chat_store)

    # Nothing was deleted, so the honest answer is an error the user can retry;
    # the handle survives and the transcript is not stranded.
    assert response.status_code == 500
    assert bookmark_ref.deleted is False
    assert chat_store.deleted == []


def test_unavailable_cursor_signing_is_reported_as_a_server_error():
    bookmark_id = "stable_chat_bookmark"
    chat_id = "c" * 32
    fake_db = FakeBookmarkDatabase({
        "uid-1": {bookmark_id: {"query": "Latest", "chat_id": chat_id}},
    })

    class UnavailableChatStore:
        def list_turn_details(self, *_args, **_kwargs):
            raise ChatCursorUnavailable("Chat cursor signing is not configured")

    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)
    app.add_middleware(CustomSecurityMiddleware)
    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", fake_db),
        patch.object(bookmarks_router, "_chat_store", return_value=UnavailableChatStore()),
    ):
        response = TestClient(app).get(
            f"/bookmarks/{bookmark_id}/conversation",
            headers={"Authorization": "Bearer token"},
        )

    # A missing signing secret is a deployment problem, not a bad request.
    assert response.status_code == 503


def test_a_malformed_cursor_is_still_a_client_error():
    bookmark_id = "stable_chat_bookmark"
    chat_id = "c" * 32
    fake_db = FakeBookmarkDatabase({
        "uid-1": {bookmark_id: {"query": "Latest", "chat_id": chat_id}},
    })

    class InvalidCursorChatStore:
        def list_turn_details(self, *_args, **_kwargs):
            raise InvalidChatCursor("Invalid chat cursor")

    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)
    app.add_middleware(CustomSecurityMiddleware)
    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", fake_db),
        patch.object(bookmarks_router, "_chat_store", return_value=InvalidCursorChatStore()),
    ):
        response = TestClient(app).get(
            f"/bookmarks/{bookmark_id}/conversation?cursor=garbage",
            headers={"Authorization": "Bearer token"},
        )

    assert response.status_code == 400
