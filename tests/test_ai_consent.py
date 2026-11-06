"""The account's consent before its first question goes to the AI providers
(app/services/ai_consent.py, security.has_ai_consent/require_ai_consent)."""

import pytest

import app.core.config as cfg
from app.api.routers import agent, agent_watches as watches_router, bookmarks, chat, users
from app.core import security
from app.services.agent_runs import AgentRunStore
from app.services.usage_repository import FirestoreUsageRepository
from adapter_test_support import http_adapter, login  # noqa: F401  (fixture)
from test_chat_history import FakeDocumentRef

pytestmark = pytest.mark.real_ai_consent

REQUIRED = security.AI_CONSENT_REQUIRED


def must_not_run(*args, **kwargs):
    raise AssertionError("reached a model without the account's consent")


@pytest.fixture
def h(http_adapter, monkeypatch):
    h = http_adapter
    for module in (agent, bookmarks):
        monkeypatch.setattr(module, "db_firestore", h.db)
    monkeypatch.setattr(users, "run_usage_repository", FirestoreUsageRepository(h.db))
    h.db.collection("users").document("owner").set({"tier": "pro"})
    return h


def agree(h):
    response = h.client.post("/api/my/ai-consent", headers=login("owner"))
    assert response.status_code == 200, response.text
    assert response.json() == {"ai_consent": True}


def refused(response):
    assert response.status_code == 403, response.text
    assert response.json()["code"] == REQUIRED
    return True


# --- the record ------------------------------------------------------------------

def test_only_the_current_version_counts():
    flags = security._compute_tier_flags
    assert flags({})["ai_consent"] is False
    assert flags({"ai_consent": {"version": security.AI_CONSENT_VERSION}})["ai_consent"] is True
    assert flags({"ai_consent": {"version": "2020-01-01"}})["ai_consent"] is False
    assert flags({"ai_consent": True})["ai_consent"] is False


def test_the_status_says_it_and_agreeing_keeps_the_rest_of_the_account(h):
    assert h.client.get("/user_status", headers=login("owner")).json()["ai_consent"] is False
    agree(h)
    assert h.client.get("/user_status", headers=login("owner")).json()["ai_consent"] is True
    stored = h.db.collection("users").document("owner").get().to_dict()
    assert stored["tier"] == "pro"
    assert stored["ai_consent"]["version"] == security.AI_CONSENT_VERSION
    assert stored["ai_consent"]["at"] is not None


def test_agreeing_needs_a_signed_in_account(h):
    assert h.client.post("/api/my/ai-consent").status_code == 401
    assert "ai_consent" not in h.db.collection("users").document("owner").get().to_dict()


def test_a_consent_given_in_another_process_counts_at_once(h):
    assert security.has_ai_consent("owner") is False
    # Written elsewhere: this process's cache still holds the "no".
    h.db.collection("users").document("owner").set(
        {"tier": "pro", "ai_consent": {"version": security.AI_CONSENT_VERSION}})
    assert security.has_ai_consent("owner") is True


# --- the gates -------------------------------------------------------------------

def test_no_question_leaves_without_the_consent(h, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-server-key")
    original = FakeDocumentRef.get
    monkeypatch.setattr(FakeDocumentRef, "get", lambda self, transaction=None, **kwargs: original(
        self, transaction=transaction))
    monkeypatch.setattr(chat, "_run_ask", must_not_run)
    monkeypatch.setattr(users.memory_edit_service, "edit", must_not_run)
    monkeypatch.setattr(watches_router.agent_watches, "create", must_not_run)
    chat_id = AgentRunStore(h.db).create_chat("owner", execution_mode="agent")["id"]
    question = {"chat_id": chat_id, "question": "Hello", "client_request_id": "request", "bookmark_id": "bookmark"}
    openai = cfg.PROVIDERS["openai"]

    def ask_all():
        return [
            h.client.post("/agent", headers=login("owner"), json=question),
            h.client.post("/prepare", headers=login("owner"), json={"question": "Hello"}),
            # An own key skips /prepare: the provider route asks again.
            h.client.post(openai.ask_endpoint, headers=login("owner"), json={
                "question": "Hello", "useOwnKeys": True, "openrouter_key": "sk-or-test",
                "model": openai.base_model}),
            h.client.post("/api/my/memory/edit", headers=login("owner"), json={
                "client_request_id": "request-1", "source_kind": "answer",
                "selected_text": "Paris", "correction": "Lyon"}),
            h.client.post("/agent/watches", headers=login("owner"), json={"task": "Check the price daily."}),
        ]

    assert all(refused(response) for response in ask_all())
    assert AgentRunStore(h.db).get_chat("owner", chat_id)["turn_count"] == 0
    agree(h)
    # With it the gate is open; every other suite runs these routes past it
    # (conftest: the test accounts agreed).
    security.require_ai_consent("owner")


def test_following_a_run_and_a_watch_run_are_not_asked(h, monkeypatch):
    original = FakeDocumentRef.get
    monkeypatch.setattr(FakeDocumentRef, "get", lambda self, transaction=None, **kwargs: original(
        self, transaction=transaction))
    chat_id = AgentRunStore(h.db).create_chat("owner", execution_mode="agent")["id"]
    question = {"chat_id": chat_id, "question": "Hello", "client_request_id": "request", "bookmark_id": "bookmark"}
    # Recovering a saved answer sends nothing anywhere.
    response = h.client.post("/agent", headers=login("owner"), json={**question, "recover_only": True})
    assert response.status_code == 404 and response.json()["code"] == "answer_unavailable"
    # A Watch's scheduled run passes the gate; the shutdown right after it stops this one.
    monkeypatch.setattr(type(agent.agent_background), "shutting_down", property(lambda self: True))
    payload = agent.AgentRequest(**question)
    with pytest.raises(agent.HTTPException) as watch_run:
        agent.start_agent_turn("owner", payload, watch_run={"watch_id": "w1"})
    assert watch_run.value.status_code == 503, watch_run.value.detail
    with pytest.raises(agent.HTTPException) as caught:
        agent.start_agent_turn("owner", payload)
    assert caught.value.detail["code"] == REQUIRED


def test_titles_and_example_questions_skip_the_model_without_it(h, monkeypatch):
    monkeypatch.setattr(bookmarks, "generate_title", must_not_run)
    monkeypatch.setattr(bookmarks.starter_questions, "predict_questions", must_not_run)
    h.db.collection("users").document("owner").collection("bookmarks").document("b1").set(
        {"query": "What is the price of gold?", "title": "What is the price of gold?"})
    title = h.client.post("/bookmarks/b1/title", headers=login("owner"))
    assert title.status_code == 200 and title.json()["status"] == "skipped"
    starters = h.client.post("/api/my/starter-questions", headers=login("owner"))
    assert starters.status_code == 200 and starters.json() == {"status": "skipped", "questions": []}
