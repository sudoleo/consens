import json
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import bookmarks as bookmarks_router
from app.core.rate_limit import limiter
from app.services import chat_titles
from tests.test_bookmarks import FakeBookmarkRef, FakeFirestore

QUESTION = (
    "Our house is from 1978 and still has the original radiators. "
    "Can a heat pump heat it properly, or do we need new radiators?"
)


def test_clean_title_strips_quotes_punctuation_and_overlong_tails():
    assert chat_titles.clean_title('  "Heat pump for a 1978 house."  ') == "Heat pump for a 1978 house"
    assert chat_titles.clean_title("**Wärmepumpe im Altbau**") == "Wärmepumpe im Altbau"
    assert chat_titles.clean_title("Line\nbreaks\tand  spaces") == "Line breaks and spaces"
    long = "Very " * 20 + "long"
    cleaned = chat_titles.clean_title(long)
    assert len(cleaned) <= chat_titles.TITLE_MAX_LENGTH
    assert not cleaned.endswith(" ")
    assert chat_titles.clean_title(None) == ""


def test_generate_title_sends_the_question_as_data_and_parses_the_title():
    calls = []

    def fake_query(model, keys, **kwargs):
        calls.append((model, keys, kwargs))
        return json.dumps({"title": "Heat pump for a 1978 house."})

    title = chat_titles.generate_title(QUESTION, query_fn=fake_query, api_keys={"OpenRouter": "key"})

    assert title == "Heat pump for a 1978 house"
    (model, _keys, kwargs), = calls
    assert model == chat_titles.title_model()
    assert "<CHAT_TITLE_QUESTION>\n" + QUESTION in kwargs["prompt"]
    assert kwargs["json_schema"]["required"] == ["title"]


def test_generate_title_never_raises_and_rejects_non_titles():
    keys = {"OpenRouter": "key"}

    def broken(*_args, **_kwargs):
        raise RuntimeError("provider down")

    assert chat_titles.generate_title(QUESTION, query_fn=broken, api_keys=keys) == ""
    assert chat_titles.generate_title(QUESTION, query_fn=lambda *a, **k: "not json", api_keys=keys) == ""
    assert chat_titles.generate_title(QUESTION, query_fn=lambda *a, **k: '{"title": "?"}', api_keys=keys) == ""
    echo = json.dumps({"title": QUESTION})
    assert chat_titles.generate_title(QUESTION, query_fn=lambda *a, **k: echo, api_keys=keys) == ""
    assert chat_titles.generate_title("   ", query_fn=broken, api_keys=keys) == ""
    # Without an operator key there is nothing to call.
    with patch.object(chat_titles, "mock_llm_enabled", return_value=False):
        assert chat_titles.generate_title(QUESTION, query_fn=broken, api_keys={}) == ""


def test_mock_engine_names_a_conversation_deterministically():
    from app.services.llm.mock_llm import _mock_engine_output

    prompt = chat_titles.TITLE_PROMPT.format(question="How do heat pumps work?")
    assert json.loads(_mock_engine_output(prompt, True)) == {"title": "Topic: How do heat pumps"}


class FakeChatRef:
    def __init__(self):
        self.updates = []

    def update(self, data):
        self.updates.append(data)


class FakeChatStore:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.ref = FakeChatRef()

    def _chat_ref(self, uid, chat_id):
        assert (uid, chat_id) == ("uid-1", self.chat_id)
        return self.ref

    def get_chat(self, uid, chat_id):
        assert (uid, chat_id) == ("uid-1", self.chat_id)
        titles = [update["title"] for update in self.ref.updates]
        return {"id": chat_id, "title": titles[-1] if titles else QUESTION}


def _client():
    app = FastAPI()
    app.state.limiter = limiter
    limiter.reset()
    app.include_router(bookmarks_router.router)
    return TestClient(app)


def test_a_conversation_is_named_once_on_the_chat_and_its_bookmark():
    chat_id = "c" * 32
    bookmark_ref = FakeBookmarkRef("named_bookmark", {
        "query": QUESTION, "title": QUESTION, "chat_id": chat_id, "responses": {},
    })
    store = FakeChatStore(chat_id)
    generate = []

    def fake_generate(question):
        generate.append(question)
        return "Heat pump for a 1978 house"

    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", FakeFirestore(bookmark_ref)),
        patch.object(bookmarks_router, "_chat_store", return_value=store),
        patch.object(bookmarks_router, "generate_title", side_effect=fake_generate),
    ):
        client = _client()
        headers = {"Authorization": "Bearer token"}
        first = client.post("/bookmarks/named_bookmark/title", headers=headers)
        again = client.post("/bookmarks/named_bookmark/title", headers=headers)

    assert first.status_code == 200
    assert first.json()["status"] == "success"
    assert first.json()["bookmark"]["title"] == "Heat pump for a 1978 house"
    assert first.json()["bookmark"]["title_source"] == "generated"
    assert first.json()["bookmark"]["query"] == QUESTION
    assert store.ref.updates == [{"title": "Heat pump for a 1978 house"}]
    assert bookmark_ref.data["title_source"] == "generated"
    # The second request finds the name and calls no model.
    assert again.json()["bookmark"]["title"] == "Heat pump for a 1978 house"
    assert generate == [QUESTION]


def test_a_failed_title_keeps_the_question_and_never_errors():
    bookmark_ref = FakeBookmarkRef("plain_bookmark", {"query": QUESTION, "title": QUESTION, "responses": {}})
    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", FakeFirestore(bookmark_ref)),
        patch.object(bookmarks_router, "generate_title", return_value=""),
    ):
        response = _client().post("/bookmarks/plain_bookmark/title", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert response.json()["status"] == "skipped"
    assert response.json()["bookmark"]["title"] == QUESTION
    assert "title_source" not in bookmark_ref.data


def test_a_missing_bookmark_is_not_created_by_a_title_request():
    bookmark_ref = FakeBookmarkRef("gone_bookmark", None)
    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", FakeFirestore(bookmark_ref)),
        patch.object(bookmarks_router, "generate_title", side_effect=AssertionError("no call")),
    ):
        response = _client().post("/bookmarks/gone_bookmark/title", headers={"Authorization": "Bearer token"})

    assert response.status_code == 404
    assert bookmark_ref.data is None


def test_later_saves_of_the_run_keep_the_generated_name():
    """Model and consensus saves merge the question as title again; the
    generated name must survive them (persistence_guard checks it)."""
    chat_id = "c" * 32
    bookmark_ref = FakeBookmarkRef("run_bookmark", {
        "query": "First question", "title": "Opening topic", "title_source": "generated",
        "chat_id": chat_id, "responses": {},
    })
    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", FakeFirestore(bookmark_ref)),
        patch.object(
            bookmarks_router,
            "_authoritative_consensus_payload",
            return_value={
                "question": "First question", "consensus": "Consensus", "differences": "",
                "differences_data": None, "sources": [], "result_id": "",
            },
        ),
    ):
        response = _client().post("/bookmark/consensus", json={
            "id_token": "token", "bookmarkId": "run_bookmark", "question": "First question",
            "consensusText": "Consensus", "differencesText": "",
        })

    assert response.status_code == 200
    assert response.json()["bookmark"]["title"] == "Opening topic"
    assert bookmark_ref.data["title"] == "Opening topic"
