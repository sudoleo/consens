"""Sharing an Agent answer (since 2026-10-21).

Agent Mode is the default for everyone; its answers had no way onto a public
page (the chat menu ended at "Saved consensus unavailable"). The snapshot is
built from the saved turn alone, keeps one link per answer, and the page
leaves out what a direct answer does not have.
"""
import hashlib
import html
import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import agent as agent_router
from app.api.routers import bookmarks as bookmarks_router
from app.api.routers import chat_history as chat_history_router
from app.api.routers import share as share_router
from app.core.rate_limit import limiter
from app.services import share_snapshots
from app.services.chat_store import ChatStore
from test_chat_history import FakeChatDatabase

UID = "uid-1"
QUESTION = "Is the James Webb telescope still working?"
ANSWER = "Yes. It sends science data every day. [S1]"
MODEL = "anthropic/claude-sonnet-5.5"
SOURCES = [{"id": "S1", "title": "NASA Webb", "url": "https://science.nasa.gov/webb"}]


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _answer(provider, label, text, **extra):
    return {"provider": provider.lower(), "provider_label": provider, "model": {"label": label, "model": label.lower()},
            "text": text, "sources": [], "hash": _digest(text), **extra}


def _review(*, text=ANSWER, check_status="succeeded", differences=None, answers=None):
    answers = answers if answers is not None else [
        _answer("OpenAI", "GPT-6 Luna", "It works."),
        _answer("Gemini", "Gemini 3.5 Flash", "It still works."),
        _answer("Grok", "Grok 4.3", "Late answer.", late=True),
    ]
    basis = _digest(json.dumps(answers, sort_keys=True, ensure_ascii=False))
    data = differences if differences is not None else {
        "claims": [{"anchor": "It sends science data every day.", "agree": ["OpenAI", "Gemini"], "dissent": []}],
        "differences": [{
            "claim": "How long it will last",
            "type": "contradiction", "severity": "major",
            "positions": [{"stance": "Until 2040", "models": ["OpenAI"]}, {"stance": "Until 2032", "models": ["Gemini"]}],
        }],
        "models_compared": ["OpenAI", "Gemini"],
        "agreement": {"score": 72, "level": "mostly", "model_count": 2,
                      "major_contradictions": 1, "minor_contradictions": 0, "emphases": 0},
    }
    return {
        "status": check_status, "answer_hash": _digest(text), "answer_version": 1,
        "comparisons": [{"id": "c1", "question": QUESTION, "status": "succeeded", "answers": answers, "basis_hash": basis}],
        "checks": [{"comparison_id": "c1", "basis_hash": basis, "answer_hash": _digest(text), "status": check_status,
                    "differences_data": None if check_status == "off" else data}],
    }


def _agent_turn(**overrides):
    turn = {
        "id": "2" * 32, "status": "completed", "execution_mode": "agent", "question": QUESTION,
        "consensus": ANSWER, "sources": SOURCES, "consensus_model": MODEL,
        "agent_settings": {"label": "Claude Sonnet 5.5", "model": MODEL},
        "completed_at": datetime(2026, 10, 21, 9, 30, tzinfo=timezone.utc),
    }
    turn.update(overrides)
    return turn


def test_a_direct_answer_shares_question_answer_and_sources_only():
    payload = share_snapshots.build_agent_pending_result(UID, _agent_turn())

    assert payload["question"] == QUESTION
    assert payload["consensus_md"] == ANSWER
    assert [source["url"] for source in payload["sources"]] == ["https://science.nasa.gov/webb"]
    assert payload["answer_mode"] == "agent"
    assert payload["answer_model_label"] == "Claude Sonnet 5.5"
    assert payload["consensus_model"] == MODEL
    assert payload["included_models"] == []
    assert payload["differences_data"] is None
    assert payload["answered_at"] == "2026-10-21T09:30:00+00:00"


def test_a_compared_answer_shares_its_models_and_their_check():
    payload = share_snapshots.build_agent_pending_result(UID, _agent_turn(agent_review=_review()))

    # The late answer was no part of the answer, nor of its check.
    assert payload["included_models"] == ["OpenAI: GPT-6 Luna", "Google Gemini: Gemini 3.5 Flash"]
    assert set(payload["model_responses"]) == {"OpenAI", "Gemini"}
    [difference] = payload["differences_data"]["differences"]
    assert difference["claim"] == "How long it will last"
    assert payload["differences_data"]["agreement"]["score"] == 72


@pytest.mark.parametrize("review", [
    # The check belongs to another version of the text.
    _review(text="An earlier draft."),
    # The answer check was switched off.
    _review(check_status="off"),
])
def test_a_check_that_is_not_of_this_text_is_left_out(review):
    payload = share_snapshots.build_agent_pending_result(UID, _agent_turn(agent_review=review))

    assert payload["differences_data"] is None
    # The models were still asked: the page names them.
    assert len(payload["included_models"]) == 2


@pytest.mark.parametrize("turn", [
    _agent_turn(status="failed"),
    _agent_turn(consensus=""),
    _agent_turn(execution_mode="consensus"),
])
def test_only_a_finished_agent_answer_has_a_snapshot(turn):
    assert share_snapshots.build_agent_pending_result(UID, turn) is None


def test_every_share_of_one_answer_has_the_same_pending_id():
    first = share_snapshots.agent_pending_result_id(UID, "c" * 32, "2" * 32)

    assert share_snapshots.is_valid_share_id(first)
    assert share_snapshots.agent_pending_result_id(UID, "c" * 32, "2" * 32) == first
    assert share_snapshots.agent_pending_result_id("uid-2", "c" * 32, "2" * 32) != first
    assert share_snapshots.agent_pending_result_id(UID, "c" * 32, "3" * 32) != first


# ---------------------------------------------------------------------------
# Through HTTP: chat turn -> pending result -> public link -> page
# ---------------------------------------------------------------------------

@pytest.fixture
def share_app():
    database = FakeChatDatabase()
    store = ChatStore(database)
    app = FastAPI()
    app.state.limiter = limiter
    limiter.reset()
    bookmarks_router.api_uid_limiter.reset()
    for router in (agent_router.router, bookmarks_router.router, share_router.router):
        app.include_router(router)
    share_snapshots.invalidate_share_cache()
    with (
        patch.object(chat_history_router, "verify_user_token", return_value=UID),
        patch.object(bookmarks_router, "verify_user_token", return_value=UID),
        patch.object(share_router, "verify_user_token", return_value=UID),
        patch.object(bookmarks_router, "db_firestore", database),
        patch.object(share_snapshots, "db_firestore", database),
        patch.object(share_snapshots, "schedule_share_cleanup"),
        patch.object(share_router.snapshots, "list_related_shares", return_value=[]),
        patch.object(share_router.snapshots, "list_watch_history", return_value=[]),
        patch.object(share_router.snapshots, "find_canonical_share", return_value=None),
        patch.object(share_router.watch_service, "get_public_watch_meta", return_value=None),
    ):
        yield TestClient(app), database, store
    share_snapshots.invalidate_share_cache()


def _saved_turn(database, store, *, chat_google=False, **fields):
    chat = store.create_chat(UID, execution_mode="agent")
    turn = store.create_turn(UID, chat["id"], question=QUESTION, mode="Agent", deep_search=False,
                             selected_models=[MODEL], consensus_model=MODEL,
                             client_request_id="share-one", execution_mode="agent")
    database.documents[("users", UID, "chats", chat["id"], "turns", turn["id"])].update({
        "status": "completed", "assistant_response": ANSWER, "sources": SOURCES,
        "agent_settings": {"label": "Claude Sonnet 5.5", "model": MODEL},
        "completed_at": datetime(2026, 10, 21, 9, 30, tzinfo=timezone.utc), **fields,
    })
    if chat_google:
        database.documents[("users", UID, "chats", chat["id"])]["google_data"] = True
    return chat["id"], turn["id"]


def _share(client, chat_id, turn_id):
    prepared = client.post(f"/agent/chats/{chat_id}/turns/{turn_id}/share-result",
                           headers={"Authorization": "Bearer token"})
    assert prepared.status_code == 200, prepared.text
    shared = client.post("/api/share", json={"id_token": "token", "result_id": prepared.json()["result_id"]})
    assert shared.status_code == 200, shared.text
    return prepared.json()["result_id"], shared.json()


def test_a_direct_agent_answer_gets_a_public_page_without_empty_parts(share_app):
    client, database, store = share_app
    chat_id, turn_id = _saved_turn(database, store)

    result_id, shared = _share(client, chat_id, turn_id)
    page = client.get(shared["path"])

    assert page.status_code == 200
    body = html.unescape(page.text)
    assert "Shared answer" in body and "Shared consensus" not in body
    assert "It sends science data every day." in body
    assert "science.nasa.gov" in body
    assert "Claude Sonnet 5.5" in body
    assert "Claude Sonnet 5.5 answered this question on 2026-10-21." in body
    assert 'Answer to "Is the James Webb telescope still working?". Answer model: Claude Sonnet 5.5.' in body
    # A direct answer compared nothing and checked nothing: nothing says so.
    for absent in ("Models compared", "Models consulted", 'id="toggleDifferencesView"', "contradiction",
                   "AI models answered", "AI models</li>", "<b>0</b>", "judge model", ">off<"):
        assert absent not in body, absent
    share = database.documents[(share_snapshots.SHARES_COLLECTION, shared["share_id"])]
    assert share["answer_mode"] == "agent" and share["indexed"] is False
    assert share["source_result_id"] == result_id


def test_a_compared_agent_answer_shows_its_models_and_differences(share_app):
    client, database, store = share_app
    chat_id, turn_id = _saved_turn(database, store, agent_review=_review())

    _, shared = _share(client, chat_id, turn_id)
    body = client.get(shared["path"]).text

    assert "Models compared" in body
    assert "GPT-6 Luna" in body and "Gemini 3.5 Flash" in body and "Grok 4.3" not in body
    assert 'id="toggleDifferencesView"' in body and "How long it will last" in body
    assert "<b>1</b> contradiction" in body
    assert "2 AI models answered this question" in body
    assert "A judge model then checked every sentence" in body


def test_a_checked_answer_without_findings_says_no_zero(share_app):
    client, database, store = share_app
    empty = {"claims": [], "differences": [], "models_compared": ["OpenAI", "Gemini"],
             "agreement": {"score": 96, "level": "very", "model_count": 2}}
    chat_id, turn_id = _saved_turn(database, store, agent_review=_review(differences=empty))

    _, shared = _share(client, chat_id, turn_id)
    body = client.get(shared["path"]).text

    assert "no notable differences found" in body
    assert "<b>0</b>" not in body


def test_an_answer_with_its_check_off_names_the_models_but_no_check(share_app):
    client, database, store = share_app
    chat_id, turn_id = _saved_turn(database, store, agent_review=_review(check_status="off"))

    _, shared = _share(client, chat_id, turn_id)
    body = client.get(shared["path"]).text

    assert "Models compared" in body
    for absent in ('id="toggleDifferencesView"', "judge model", "/100", ">off<", "<b>0</b>"):
        assert absent not in body, absent


def test_sharing_the_same_answer_again_keeps_its_one_link(share_app):
    client, database, store = share_app
    chat_id, turn_id = _saved_turn(database, store)

    first_result, first = _share(client, chat_id, turn_id)
    again_result, again = _share(client, chat_id, turn_id)

    assert again_result == first_result
    assert again["share_id"] == first["share_id"] and again["created"] is False
    shares = [path for path in database.documents if path[0] == share_snapshots.SHARES_COLLECTION]
    assert len(shares) == 1


@pytest.mark.parametrize("fields, chat_google, status, words", [
    ({"status": "failed"}, False, 409, "didn’t finish"),
    ({"agent_settings": {"label": "Claude Sonnet 5.5", "google_data": True}}, False, 409, "Google data"),
    # Gmail evidence fetched during the answer marks only the chat.
    ({}, True, 409, "Google data"),
])
def test_an_answer_that_cannot_be_shared_says_why(share_app, fields, chat_google, status, words):
    client, database, store = share_app
    chat_id, turn_id = _saved_turn(database, store, chat_google=chat_google, **fields)

    response = client.post(f"/agent/chats/{chat_id}/turns/{turn_id}/share-result",
                           headers={"Authorization": "Bearer token"})

    assert response.status_code == status
    assert words in response.json()["detail"]
    assert not [path for path in database.documents if path[0] == share_snapshots.PENDING_COLLECTION]


def test_another_account_cannot_prepare_someone_elses_answer(share_app):
    client, database, store = share_app
    chat_id, turn_id = _saved_turn(database, store)

    with patch.object(chat_history_router, "verify_user_token", return_value="uid-2"):
        response = client.post(f"/agent/chats/{chat_id}/turns/{turn_id}/share-result",
                               headers={"Authorization": "Bearer token"})

    assert response.status_code == 404


def test_the_chat_list_share_of_an_agent_chat_shares_its_latest_answer(share_app):
    """Pages opened before this change still ask the bookmark endpoint."""
    client, database, store = share_app
    chat_id, turn_id = _saved_turn(database, store)
    bookmark = {"query": QUESTION, "mode": "Agent", "execution_mode": "agent", "chat_id": chat_id,
                "turn_id": turn_id, "share_result_id": "", "responses": {"consensus": ANSWER}}
    database.documents[("users", UID, "bookmarks", "webb")] = dict(bookmark)

    response = client.post("/bookmark/consensus/share-result", json={
        "id_token": "token", "bookmarkId": "webb",
        "expectedVersion": bookmarks_router._bookmark_share_version(bookmark)})

    assert response.status_code == 200, response.text
    assert response.json()["result_id"] == share_snapshots.agent_pending_result_id(UID, chat_id, turn_id)
    # The entry now names another answer than its turn: no share of either.
    database.documents[("users", UID, "bookmarks", "webb")]["responses"] = {"consensus": "Another answer."}
    stale = client.post("/bookmark/consensus/share-result", json={"id_token": "token", "bookmarkId": "webb"})
    assert stale.status_code == 409
    assert "Open the chat again" in stale.json()["detail"]


def test_the_consensus_page_no_longer_counts_zero_contradictions():
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    template = (root / "templates" / "share.html").read_text(encoding="utf-8")
    assert "{% if has_differences_view and scoreboard.contradiction_count %}" in template
