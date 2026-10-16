"""Example questions under an empty new chat (app/services/starter_questions.py).

Three curated questions per page load; with a few saved chats, three
predicted from the newest ones (POST /api/my/starter-questions).
"""
import json
import os
import random
import re
from unittest.mock import patch

os.environ.setdefault("UNIT_TEST_MODE", "1")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import bookmarks as bookmarks_router
from app.api.routers import pages as pages_router
from app.core.rate_limit import api_uid_limiter, limiter
from app.services import starter_questions

HISTORY = [
    {"title": "Heat pump for a 1978 house", "question": "Do we need bigger radiators?"},
    {"title": "EU AI Act for support bots", "question": "EU AI Act for support bots"},
    {"title": "Creatine and sleep", "question": "Does creatine affect sleep quality?"},
]
PREDICTED = {"questions": [
    {"label": "Heat pump running costs?", "question": "What will a heat pump cost to run in a 1978 house per year?"},
    {"label": "AI Act deadlines?", "question": "Which EU AI Act deadlines apply to a support chatbot in 2027?"},
    {"label": "Creatine timing?", "question": "Does the time of day I take creatine change how I sleep?"},
]}


def test_the_curated_pool_fits_one_row_and_asks_real_questions():
    keys = [item["key"] for item in starter_questions.CURATED_STARTERS]
    assert len(set(keys)) == len(keys) >= 6
    assert "check" not in keys
    for item in starter_questions.CURATED_STARTERS:
        assert re.fullmatch(r"[a-z0-9_]+", item["key"])
        # Three labels and "Check an AI answer" in one row under the composer.
        assert len(item["label"]) <= 22 and item["label"].endswith("?")
        assert item["question"].endswith("?") and len(item["question"]) <= 160
        assert '"' not in item["question"]

    picked = starter_questions.pick_curated(random.Random(1))
    assert len(picked) == starter_questions.CURATED_PER_PAGE
    assert len({item["key"] for item in picked}) == len(picked)


def test_prediction_sends_the_chats_as_data_and_returns_clean_questions():
    calls = []

    def fake_query(model, keys, **kwargs):
        calls.append((model, kwargs))
        return json.dumps(PREDICTED)

    questions = starter_questions.predict_questions(
        HISTORY, query_fn=fake_query, api_keys={"OpenRouter": "key"}, today="2026-10-16"
    )

    assert questions == PREDICTED["questions"]
    (model, kwargs), = calls
    assert model == starter_questions.title_model()
    assert kwargs["json_schema"]["required"] == ["questions"]
    prompt = kwargs["prompt"]
    assert "Today is 2026-10-16." in prompt
    conversations = prompt.split("<RECENT_CONVERSATIONS>\n", 1)[1].split("\n</RECENT_CONVERSATIONS>", 1)[0]
    assert conversations.splitlines() == [
        "1. Heat pump for a 1978 house (latest question: Do we need bigger radiators?)",
        # A chat that was never renamed is named by its question once.
        "2. EU AI Act for support bots",
        "3. Creatine and sleep (latest question: Does creatine affect sleep quality?)",
    ]


def test_prediction_drops_repeats_junk_and_too_little():
    keys = {"OpenRouter": "key"}

    def answer(payload):
        return lambda *_a, **_k: json.dumps(payload)

    mixed = {"questions": [
        # Already asked, only differently punctuated.
        {"label": "Creatine and sleep?", "question": "Does creatine affect sleep quality"},
        {"label": "**Heat pump costs.**", "question": " \"What will a heat pump cost to run per year?\" "},
        {"label": "A label far too long to ever fit on one button?", "question": "Is this a fine question?"},
        {"label": "Short?", "question": "Too?"},
        {"label": "AI Act deadlines", "question": "Which EU AI Act deadlines apply to a support chatbot?"},
        {"label": "AI Act deadlines again?", "question": "Which EU AI Act deadlines apply to a support chatbot?"},
        "not an object",
    ]}
    assert starter_questions.predict_questions(HISTORY, query_fn=answer(mixed), api_keys=keys) == [
        {"label": "Heat pump costs?", "question": "What will a heat pump cost to run per year?"},
        {"label": "AI Act deadlines?", "question": "Which EU AI Act deadlines apply to a support chatbot?"},
    ]
    # One usable question is no row of suggestions.
    one = {"questions": PREDICTED["questions"][:1]}
    assert starter_questions.predict_questions(HISTORY, query_fn=answer(one), api_keys=keys) == []

    def broken(*_args, **_kwargs):
        raise RuntimeError("provider down")

    assert starter_questions.predict_questions(HISTORY, query_fn=broken, api_keys=keys) == []
    assert starter_questions.predict_questions(HISTORY, query_fn=lambda *a, **k: "not json", api_keys=keys) == []
    # Fewer than three chats: nothing to read a pattern from, no call.
    assert starter_questions.predict_questions(HISTORY[:2], query_fn=broken, api_keys=keys) == []
    with patch.object(starter_questions, "mock_llm_enabled", return_value=False):
        assert starter_questions.predict_questions(HISTORY, query_fn=broken, api_keys={}) == []


def test_mock_engine_predicts_deterministically():
    from app.services.llm.mock_llm import _mock_engine_output

    prompt = starter_questions.PREDICT_PROMPT.format(
        today="2026-10-16", count=3,
        conversations=starter_questions._conversation_lines(HISTORY),
    )
    raw = json.loads(_mock_engine_output(prompt, True))
    assert starter_questions.clean_predictions(raw, HISTORY) == [
        {"label": "More on Heat pump?", "question": "What should I know next about Heat pump for a 1978 house?"},
        {"label": "More on EU AI?", "question": "What should I know next about EU AI Act for support bots?"},
        {"label": "More on Creatine and?", "question": "What should I know next about Creatine and sleep?"},
    ]


# ---- The route ----------------------------------------------------------------

class FakeDoc:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class FakeBookmarksQuery:
    def __init__(self, database):
        self.database = database

    def select(self, fields):
        self.database.calls.append(("select", list(fields)))
        return self

    def order_by(self, field, direction=None):
        self.database.calls.append(("order_by", field, direction))
        return self

    def limit(self, count):
        self.database.calls.append(("limit", count))
        return self

    def stream(self):
        self.database.reads += 1
        return [FakeDoc(item) for item in self.database.bookmarks]


class FakeDatabase:
    def __init__(self, bookmarks):
        self.bookmarks = bookmarks
        self.calls = []
        self.reads = 0

    def collection(self, name):
        return self

    def document(self, uid):
        assert uid == "uid-1"
        return self

    def select(self, fields):
        return FakeBookmarksQuery(self).select(fields)


def _client():
    app = FastAPI()
    app.state.limiter = limiter
    limiter.reset()
    api_uid_limiter.reset()
    app.include_router(bookmarks_router.router)
    return TestClient(app)


def _bookmarks(count):
    return [{"title": item["title"], "query": item["question"]} for item in (HISTORY * 4)[:count]]


def test_the_route_predicts_from_the_newest_chat_names_only():
    database = FakeDatabase(_bookmarks(3))
    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", database),
        patch.object(starter_questions, "predict_questions", return_value=PREDICTED["questions"]) as predict,
    ):
        response = _client().post("/api/my/starter-questions", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert response.json() == {"status": "success", "questions": PREDICTED["questions"]}
    # Never the answers: a bookmark document carries every model's text.
    assert database.calls[0] == ("select", ["title", "query"])
    assert ("limit", starter_questions.HISTORY_SIZE) in database.calls
    assert predict.call_args.args[0] == HISTORY


def test_the_route_skips_quietly():
    headers = {"Authorization": "Bearer token"}
    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", FakeDatabase(_bookmarks(2))),
        patch.object(starter_questions, "predict_questions", side_effect=AssertionError("no call")),
    ):
        too_few = _client().post("/api/my/starter-questions", headers=headers)
    assert too_few.json() == {"status": "skipped", "questions": []}

    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", FakeDatabase(_bookmarks(5))),
        patch.object(starter_questions, "predict_questions", return_value=[]),
    ):
        failed = _client().post("/api/my/starter-questions", headers=headers)
    assert failed.status_code == 200
    assert failed.json() == {"status": "skipped", "questions": []}

    assert _client().post("/api/my/starter-questions").status_code == 401


def test_predictions_are_capped_per_account_before_any_read():
    database = FakeDatabase(_bookmarks(5))
    cap = bookmarks_router.STARTER_PREDICTIONS_PER_HOUR
    with (
        patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"),
        patch.object(bookmarks_router, "db_firestore", database),
        patch.object(starter_questions, "predict_questions", return_value=PREDICTED["questions"]) as predict,
    ):
        client = _client()
        responses = [
            client.post(
                "/api/my/starter-questions",
                headers={"Authorization": "Bearer token", "CF-Connecting-IP": f"198.51.100.{index + 1}"},
            )
            for index in range(cap + 1)
        ]
    api_uid_limiter.reset()

    assert [r.json()["status"] for r in responses] == ["success"] * cap + ["skipped"]
    assert predict.call_count == cap
    assert database.reads == cap


def test_the_app_shell_shows_three_curated_questions_and_the_check():
    app = FastAPI()
    app.include_router(pages_router.router)
    html = TestClient(app).get("/app").text

    row = html.split('id="composerStarters"', 1)[1].split("</div>", 1)[0]
    starters = re.findall(r'data-starter="([a-z0-9_]+)"', row)
    pool = {item["key"] for item in starter_questions.CURATED_STARTERS}
    assert len(starters) == 4 and starters[-1] == "check"
    assert set(starters[:3]) <= pool and len(set(starters[:3])) == 3
