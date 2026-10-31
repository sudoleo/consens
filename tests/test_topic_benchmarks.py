"""Benchmark chart for model-family Topics (app/services/topic_benchmarks.py).

Data from Artificial Analysis, stored per check, drawn after the answer with
the attribution the free API requires.
"""

from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import topics as topics_router
from app.core.rate_limit import limiter
from app.services import topic_benchmarks, topic_runner, topics
from test_topics_feature import NOW, FakeFirestore, run_payload, topic_payload

DAY = date(2026, 10, 31)


def row(name, creator, score, creator_id=None):
    return {
        "id": name.lower().replace(" ", "-"), "name": name,
        "model_creator": {"id": creator_id or creator.lower(), "name": creator},
        "evaluations": {"artificial_analysis_intelligence_index": score},
    }


ROWS = [
    row("Gemini 4 Carbon (High)", "Google", 59.0),
    row("Gemini 4 Carbon (Low)", "Google", 54.2),
    row("Gemini 4 Argon", "Google", 55.4),
    row("Gemini 4.5 Pro", "Google", 70.0),  # another family, same lab
    row("Gemini 3.5 Flash", "Google", 48.0),
    row("GPT-6.1 (xhigh)", "OpenAI", 57.3),
    row("GPT-6.1 mini", "OpenAI", 50.0),
    row("Claude Opus 5.5", "Anthropic", 56.8),
    row("Grok 4.7", "xAI", 52.1),
    row("DeepSeek V4.1", "DeepSeek", 49.9),
    row("Kimi K3", "Moonshot", 48.7),
    row("Qwen 4 Max", "Alibaba", 47.0),  # sixth other lab: not shown
    row("Unscored", "Somebody", None),
    {"name": "broken"},
]


def test_the_family_stands_next_to_the_best_model_of_each_other_lab():
    snapshot = topic_benchmarks.select(ROWS, ["Gemini 4"], fetched_on=DAY.isoformat())

    names = [(item["name"], item["own"]) for item in snapshot["items"]]
    assert names == [
        ("Gemini 4 Carbon (High)", True),
        ("GPT-6.1 (xhigh)", False),
        ("Claude Opus 5.5", False),
        ("Gemini 4 Argon", True),
        ("Grok 4.7", False),
        ("DeepSeek V4.1", False),
        ("Kimi K3", False),
    ]
    # One bar per model (its best setting), one per other lab, none for the
    # own lab's other families.
    assert snapshot["fetched_on"] == "2026-10-31"
    assert snapshot["items"][0] == {"name": "Gemini 4 Carbon (High)", "creator": "Google", "score": 59.0, "own": True}


def test_no_chart_without_a_benchmarked_model_of_the_family():
    assert topic_benchmarks.select(ROWS, ["Gemini 5"], fetched_on="2026-10-31") is None
    assert topic_benchmarks.select([], ["Gemini 4"], fetched_on="2026-10-31") is None


def test_the_setting_takes_names_one_per_line():
    assert topic_benchmarks.normalize_config({"models": " Gemini 4 \n\ngemini 4\nGPT-6, Claude 5 ,a,b"}) == {
        "models": ["Gemini 4", "GPT-6", "Claude 5", "a"],
    }
    assert topic_benchmarks.normalize_config(None) == {"models": []}
    assert topic_benchmarks.normalize_config({"models": 3}) == {"models": []}


def test_build_never_costs_the_check(monkeypatch):
    def broken():
        raise RuntimeError("API down")

    assert topic_benchmarks.build({"models": ["Gemini 4"]}, today=DAY, fetch=broken) is None
    # No setting: nothing is asked.
    assert topic_benchmarks.build({}, today=DAY, fetch=broken) is None
    # Tests never call out, even with a key.
    monkeypatch.setenv(topic_benchmarks.API_KEY_ENV, "key")
    assert topic_benchmarks.build({"models": ["Gemini 4"]}, today=DAY) is None
    assert topic_benchmarks.build({"models": ["Gemini 4"]}, today=DAY, fetch=lambda: ROWS)["items"]


class Response:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def test_the_api_is_read_with_the_key_and_cached(monkeypatch):
    monkeypatch.setattr(topic_benchmarks, "_CACHE", {"at": 0.0, "rows": None})
    monkeypatch.delenv(topic_benchmarks.API_KEY_ENV, raising=False)
    calls = []

    def get(url, headers, timeout):
        calls.append((url, headers["x-api-key"]))
        return Response(200, {"status": 200, "data": ROWS[:2] + ["junk"]})

    try:
        topic_benchmarks.fetch_models(get=get)
        raise AssertionError("expected BenchmarkUnavailable")
    except topic_benchmarks.BenchmarkUnavailable:
        pass
    monkeypatch.setenv(topic_benchmarks.API_KEY_ENV, "secret")
    assert len(topic_benchmarks.fetch_models(get=get)) == 2
    assert len(topic_benchmarks.fetch_models(get=get)) == 2
    assert calls == [(topic_benchmarks.API_URL, "secret")]

    monkeypatch.setattr(topic_benchmarks, "_CACHE", {"at": 0.0, "rows": None})
    try:
        topic_benchmarks.fetch_models(get=lambda *a, **k: Response(429, {}))
        raise AssertionError("expected BenchmarkUnavailable")
    except topic_benchmarks.BenchmarkUnavailable as exc:
        assert "429" in str(exc)


def test_a_stored_snapshot_is_checked_before_it_is_drawn():
    assert topic_benchmarks.stored(None) is None
    assert topic_benchmarks.stored({"items": [{"name": "A", "score": 5, "own": False}] * 2}) is None
    kept = topic_benchmarks.stored({"fetched_on": 3, "items": [
        {"name": "A", "score": 5, "own": True},
        {"name": "B", "score": True, "own": False},
        {"name": "C", "score": 4.5, "creator": None},
    ]})
    assert [item["name"] for item in kept["items"]] == ["A", "C"]
    assert kept["fetched_on"] == "" and kept["items"][1]["creator"] == ""


def test_the_chart_is_escaped_dated_and_attributed():
    snapshot = topic_benchmarks.select(
        ROWS + [row("<b>Gemini 4</b> Nano", "Google", 30)], ["<b>Gemini 4</b>", "Gemini 4"],
        fetched_on="2026-10-31",
    )
    html = str(topic_benchmarks.figure_html(snapshot))
    assert '<figure class="af af-numbers af-benchmark">' in html
    assert "&lt;b&gt;Gemini 4&lt;/b&gt; Nano" in html and "<b>" not in html
    assert '<a href="https://artificialanalysis.ai/"' in html
    assert "as of Oct 31, 2026" in html
    assert html.count('class="af-row is-own"') == 3
    assert ">59</span>" in html and ">57.3</span>" in html
    # The top bar fills the row; the others are drawn to scale.
    assert 'style="width:100.0%"' in html


def test_the_topic_keeps_its_setting_through_an_admin_save():
    db = FakeFirestore()
    topic = topics.create_topic(
        topic_payload(benchmark={"models": ["GPT-6"]}), actor_uid="admin", db=db, now=NOW,
    )
    assert topic["benchmark"] == {"models": ["GPT-6"]}
    # An older admin form sends no benchmark field.
    payload = topic_payload()
    payload.pop("benchmark", None)
    updated = topics.update_topic(topic["id"], payload, actor_uid="admin", db=db, now=NOW)
    assert updated["benchmark"] == {"models": ["GPT-6"]}
    cleared = topics.update_topic(
        topic["id"], topic_payload(benchmark={"models": []}), actor_uid="admin", db=db, now=NOW,
    )
    assert cleared["benchmark"] == {"models": []}


def test_a_topic_check_stores_the_chart_and_the_page_draws_it_after_the_answer(monkeypatch):
    db = FakeFirestore()
    monkeypatch.setattr(topics, "db_firestore", db)
    # "GPT-6" alone would not match "GPT-6.1": a point release is named.
    topic = topics.create_topic(
        topic_payload(benchmark={"models": ["GPT-6", "GPT-6.1"]}), actor_uid="admin", db=db, now=NOW,
    )
    topics.create_run(topic["id"], run_payload(), actor_uid="admin", db=db, now=NOW)
    db.documents[("topics", topic["id"])].update({
        "current_run_id": "automatic-run", "claimed_until": NOW, "last_run_status": "running",
    })
    claimed = {**topics.get_topic(topic["id"], db=db)}
    asked = {}

    def build(config, *, today, fetch=None):
        asked.update(config=config, today=today)
        return topic_benchmarks.select([
            row("GPT-6.1 (xhigh)", "OpenAI", 57.3),
            row("Gemini 4 Carbon (High)", "Google", 59.0),
        ], config["models"], fetched_on=today.isoformat())

    monkeypatch.setattr(topic_benchmarks, "build", build)
    later = NOW + timedelta(days=1)

    def execute(question, previous_consensus, **kwargs):
        return {
            "consensus": "GPT-6.1 is out.\n\nIt came in October.", "agreement_score": 70,
            "changed": False, "opinion_map": {}, "differences_data": {},
            "sources": [{"url": "https://openai.com/index/gpt-6-1", "title": "GPT-6.1", "id": "S1"}],
            "consensus_model": "OpenAI",
            "included_models": ["OpenAI: gpt-6-luna", "Grok: grok-4.3"],
        }

    run = topic_runner.execute_claimed_topic(claimed, actor_uid="admin", db=db, now=later, executor=execute)

    assert asked == {"config": {"models": ["GPT-6", "GPT-6.1"]}, "today": later.date()}
    assert [item["name"] for item in run["benchmark"]["items"]] == ["Gemini 4 Carbon (High)", "GPT-6.1 (xhigh)"]

    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(topics_router.router)
    text = TestClient(app).get("/topics/gpt-6").text
    answer = text.split('id="wpAnswerHeading"', 1)[1]
    assert answer.index("It came in October.") < answer.index("af-benchmark") < answer.index("Sources</h3>")
    assert "Artificial Analysis Intelligence Index" in answer
