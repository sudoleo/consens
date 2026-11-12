"""Figures drawn from a Topic answer (app/services/topic_figures.py).

The figure may only show what the answer states; everything else is dropped
before it is stored or drawn.
"""

import re
from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import topics as topics_router
from app.core.rate_limit import limiter
from app.services import topic_figures, topic_runner, topics
from test_topics_feature import NOW, FakeFirestore, run_payload, topic_payload

ANSWER = """Google has officially announced Gemini 4.

## Release date

- 2026-09-30: public announcement of Gemini 4 Argon
- October 13, 2026: broader availability for Gemini app and API users

## Model variants

Gemini 4 Argon is confirmed. Gemini 4 Pro and Gemini 4 Flash are not confirmed.

## Pricing

$2 per 1M input tokens and $10 per 1M output tokens. Some sources say $4 later.

## Bottom line

Argon is out.
"""


def item(label, **fields):
    base = {"label": label, "date": "", "status": "none", "value": "", "unit": "", "note": "", "disputed": False}
    base.update(fields)
    return base


def figure(kind, items, title="A figure", after=""):
    return {"kind": kind, "title": title, "after_heading": after, "items": items}


def written_dates(html) -> list[str]:
    """The dates of a drawn chart, row by row."""
    return re.findall(r'<time class="af-when"[^>]*>([^<]+)</time>', str(html))


def marks(html) -> list[tuple[str, float]]:
    """Each mark on the time axis: its shape and where it starts (percent)."""
    return [(shape, float(left)) for shape, left in
            re.findall(r'<i class="af-(mark|range)" style="left:([0-9.]+)%', str(html))]


def tick_labels(html) -> list[tuple[float, str]]:
    return [(float(left), label) for left, label in
            re.findall(r'class="af-tick[^"]*" style="left:([0-9.]+)%">([^<]+)<', str(html))]


def test_only_what_the_answer_states_survives():
    raw = {"figures": [
        figure("timeline", [
            item("Broad availability", date="October 13, 2026"),
            item("Announcement", date="2026-09-30"),
            item("Invented launch", date="2026-12-01"),  # not in the answer
        ], after="Release date"),
        figure("status", [
            item("Gemini 4 Argon", status="confirmed", note="I could verify it myself"),
            item("Gemini 4 Pro", status="not_confirmed"),
            item("Gemini 4 Flash", status="not_confirmed"),
            item("Gemini 4 Ultra", status="not_confirmed"),  # name not in the answer
            item("68% on CWE-Bench", status="claimed"),  # a number, not a name
        ]),
        figure("numbers", [
            item("Input", value="$2", unit="per 1M tokens"),
            item("Output", value="$10", unit="per 1M tokens"),
            item("Output later", value="$20", unit="per 1M tokens", disputed=True),  # not stated
        ]),
    ]}

    figures = topic_figures.clean_figures(raw, ANSWER)

    # At most two; a status board of an earlier prompt is stored as a lineup.
    assert [f["kind"] for f in figures] == ["timeline", "lineup"]
    timeline, status = figures
    assert [entry["date"] for entry in timeline["items"]] == ["2026-09-30", "October 13, 2026"]
    assert timeline["after_heading"] == "Release date"
    assert [entry["label"] for entry in status["items"]] == ["Gemini 4 Argon", "Gemini 4 Pro", "Gemini 4 Flash"]
    # A note in the model's own voice explains nothing.
    assert status["items"][0]["note"] == ""


def test_a_figure_needs_two_items_and_one_template_appears_once():
    raw = {"figures": [
        figure("status", [item("Gemini 4 Argon", status="confirmed"), item("Gemini 4 Pro", status="not_confirmed")]),
        figure("status", [item("Gemini 4 Argon", status="confirmed"), item("Gemini 4 Pro", status="not_confirmed"),
                          item("Gemini 4 Flash", status="not_confirmed")], title="Fuller"),
        figure("numbers", [item("Input", value="$2", unit="per 1M tokens")]),
    ]}
    figures = topic_figures.clean_figures(raw, ANSWER)
    assert [(f["kind"], f["title"]) for f in figures] == [("lineup", "Fuller")]
    assert topic_figures.clean_figures({"figures": "nope"}, ANSWER) == []
    assert topic_figures.clean_figures(None, ANSWER) == []


def test_repeated_notes_are_dropped():
    raw = {"figures": [figure("status", [
        item("Gemini 4 Pro", status="not_confirmed", note="no official confirmation"),
        item("Gemini 4 Flash", status="not_confirmed", note="no official confirmation"),
        item("Gemini 4 Argon", status="confirmed", note="Gemini 4 Argon"),
    ])]}
    notes = [entry["note"] for entry in topic_figures.clean_figures(raw, ANSWER)[0]["items"]]
    assert notes == ["", "", ""]


def test_dates_are_read_the_way_answers_write_them():
    assert topic_figures.parse_date("2026-09-30") == (date(2026, 9, 30), "day")
    assert topic_figures.parse_date("Sept. 4, 2026") == (date(2026, 9, 4), "day")
    assert topic_figures.parse_date("13 October 2026") == (date(2026, 10, 13), "day")
    assert topic_figures.parse_date("October 2026") == (date(2026, 10, 1), "month")
    assert topic_figures.parse_date("in 2027") == (date(2027, 1, 1), "year")
    assert topic_figures.parse_date("soon") is None
    # A span of days sits at its first day (gpt-6-release-date:
    # "October 7–8, 2026" was read as the bare year and led the timeline).
    assert topic_figures.parse_date("October 7–8, 2026") == (date(2026, 10, 7), "days")
    assert topic_figures.parse_date("7-8 October 2026") == (date(2026, 10, 7), "days")
    assert topic_figures._date_label({"date": "October 7–8, 2026"}) == "Oct 7–8, 2026"
    # A named month no pattern reads is no date, never January 1st.
    assert topic_figures.parse_date("Q4 of October-ish") is None
    # "late 2026 or 2027" names two years: a span, drawn from the first to the last.
    assert topic_figures.parse_date("late 2026 or 2027") == (date(2026, 1, 1), "years")
    assert topic_figures._date_label({"date": "late 2026 or 2027"}) == "2026–2027"


def test_a_stored_timeline_is_ordered_by_its_written_dates_when_drawn():
    stored = {"kind": "timeline", "title": "", "after_heading": "", "items": [
        # Stored by the first version, which read the span as "2026".
        {"label": "Most users", "note": "", "disputed": False, "date": "October 7–8, 2026",
         "sort": "2026-01-01", "precision": "year"},
        {"label": "First introduction", "note": "", "disputed": False, "date": "early September 2026",
         "sort": "2026-09-01", "precision": "month"},
    ]}
    assert written_dates(topic_figures.figure_html(stored)) == ["Sep 2026", "Oct 7–8, 2026"]

    stored["items"].append({"label": "Rollout starts", "note": "", "disputed": False,
                            "date": "October 7, 2026"})
    # A single day comes before the span that starts on it.
    assert written_dates(topic_figures.figure_html(stored)) == ["Sep 2026", "Oct 7, 2026", "Oct 7–8, 2026"]


def test_figures_are_drawn_as_escaped_html_with_disagreement_marked():
    hostile = '<img src=x onerror="alert(1)">'
    html = str(topic_figures.figure_html({
        "kind": "numbers", "title": hostile, "after_heading": "",
        "items": [
            {"label": hostile, "note": "", "disputed": False, "value": "$2", "number": 2.0, "unit": "per 1M"},
            {"label": "Later", "note": "", "disputed": True, "value": "$4", "number": 4.0, "unit": "per 1M"},
        ],
    }, answered_on="Oct 14, 2026"))
    assert "<img" not in html and "&lt;img" in html
    assert 'class="af-row is-disputed"' in html
    assert "width:50.0%" in html and "width:100.0%" in html
    assert "Dashed: the sources or models disagree." in html
    # A head with symbol and kind marks it as a figure, not more answer text.
    assert '<p class="af-kind"><svg' in html and "In numbers</p>" in html
    assert "this answer of Oct 14, 2026" in html


def test_a_figure_sits_under_its_heading_but_never_after_the_closing_summary():
    figures = [figure("timeline", [], after="Release date"), figure("status", [], after="Bottom line")]
    marked, placed = topic_figures.place(ANSWER, figures)
    lines = marked.split("\n")
    assert lines[lines.index("## Release date") + 2] == "TOPICFIGURESLOT0"
    # "Bottom line" closes the answer: the figure moves up to the opening.
    assert lines[2] == "TOPICFIGURESLOT1"
    html = topic_figures.fill("<p>TOPICFIGURESLOT0</p><p>x</p>", [{
        "kind": "status", "title": "", "after_heading": "",
        "items": [{"label": "A", "note": "", "disputed": False, "status": "confirmed"},
                  {"label": "B", "note": "", "disputed": False, "status": "not_confirmed"}],
    }])
    assert str(html).startswith('<figure class="af af-lineup">') and "TOPICFIGURESLOT" not in str(html)


def test_build_never_costs_the_check():
    def broken(*args):
        raise RuntimeError("judge down")

    assert topic_figures.build("Q?", ANSWER, query=broken) == []
    # Tests and mock runs never call a model.
    assert topic_figures.build("Q?", ANSWER) == []


def test_a_topic_check_stores_its_figures_and_the_page_draws_them(monkeypatch):
    db = FakeFirestore()
    monkeypatch.setattr(topics, "db_firestore", db)
    topic = topics.create_topic(topic_payload(), actor_uid="admin", db=db, now=NOW)
    topics.create_run(topic["id"], run_payload(), actor_uid="admin", db=db, now=NOW)
    db.documents[("topics", topic["id"])].update({
        "current_run_id": "automatic-run", "claimed_until": NOW, "last_run_status": "running",
    })
    claimed = {**topics.get_topic(topic["id"], db=db)}
    asked = {}

    def build(question, answer, *, engine="OpenAI", **kwargs):
        asked.update(question=question, answer=answer, engine=engine)
        raw = {"figures": [figure("timeline", [
            item("Announcement", date="2026-09-30"),
            item("Broad availability", date="October 13, 2026"),
        ], title="How it rolled out", after="Release date")]}
        return topic_figures.clean_figures(raw, answer)

    monkeypatch.setattr(topic_figures, "build", build)
    later = NOW + timedelta(days=1)

    def execute(question, previous_consensus, **kwargs):
        return {
            "consensus": "Here's the current picture:\n\n" + ANSWER, "agreement_score": 70,
            "changed": False, "opinion_map": {}, "differences_data": {}, "sources": [],
            "consensus_model": "OpenAI",
            "included_models": ["OpenAI: gpt-6-luna", "Grok: grok-4.3"],
        }

    run = topic_runner.execute_claimed_topic(claimed, actor_uid="admin", db=db, now=later, executor=execute)

    assert asked["question"] == "What is the current evidence about GPT-6?"
    assert asked["answer"].startswith("Google has officially announced Gemini 4.")
    assert [f["title"] for f in run["figures"]] == ["How it rolled out"]

    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(topics_router.router)
    page = TestClient(app).get("/topics/gpt-6")
    assert page.status_code == 200
    text = page.text
    assert '<figure class="af af-timeline">' in text
    assert "How it rolled out" in text
    answer = text.split('id="wpAnswerHeading"', 1)[1]
    assert answer.index("Release date</h2>") < answer.index("af-timeline") < answer.index("broader availability")
    # Each event is a row on one time axis and says its date in words.
    assert 'class="af-chart is-npw"' in text
    assert '<time class="af-when" datetime="2026-09-30">Sep 30, 2026</time>' in text
    assert "TOPICFIGURESLOT" not in text


def test_figure_lists_do_not_inherit_the_answer_list_indent():
    """The figures sit inside the answer (.share-md), whose ol/ul rules are
    one step more specific than a bare class: the one figure list needs two,
    and the row chart is built without list elements."""
    css = open("static/css/public-pages.css", encoding="utf-8").read()
    assert ".af .af-rows {" in css
    chart = str(topic_figures.figure_html({"kind": "timeline", "title": "", "after_heading": "", "items": [
        {"label": "A", "note": "", "disputed": False, "date": "2026-09-30"},
        {"label": "B", "note": "", "disputed": False, "date": "2026-10-13"},
    ]}))
    assert "<ol" not in chart and "<ul" not in chart and chart.count('role="listitem"') == 2


LINEUP_ANSWER = """Grok 5 is not out yet.

- Grok 4.6: released 2026-08-12.
- Grok 4.7: released 2026-09-21, the latest shipped flagship.
- Grok 4.8: announced by Elon Musk, limited rollout expected.
- Grok 5: xAI said it is in training; no release date.
"""


def test_a_lineup_says_where_each_member_stands_and_when():
    raw = {"figures": [figure("lineup", [
        item("Grok 5", status="not_confirmed", note="in training"),
        item("Grok 4.8", status="announced", date="2026-11-30"),  # a date the answer never gives
        item("Grok 4.7", status="available", date="2026-09-21"),
        item("Grok 4.6", status="available", date="2026-08-12"),
        item("Grok 6", status="not_confirmed"),  # a name the answer never gives
        item("Grok 4.9", status="none"),  # neither a standing nor a date
    ], title="Grok models")]}

    lineup, = topic_figures.clean_figures(raw, LINEUP_ANSWER)

    assert lineup["kind"] == "lineup"
    # Dated rows in order, the rest after them as the answer lists them; an
    # unstated date is dropped, the row keeps its standing.
    assert [(e["label"], e["status"], e.get("date", "")) for e in lineup["items"]] == [
        ("Grok 4.6", "available", "2026-08-12"), ("Grok 4.7", "available", "2026-09-21"),
        ("Grok 5", "not_confirmed", ""), ("Grok 4.8", "announced", ""),
    ]
    html = str(topic_figures.figure_html(lineup, as_of=date(2026, 11, 12)))
    assert html.startswith('<figure class="af af-lineup">') and 'class="af-chart is-snpw"' in html
    assert html.count('class="af-glyph is-available"') == 2 and ">Announced</span>" in html
    assert written_dates(html) == ["Aug 12, 2026", "Sep 21, 2026"]
    # Two marks, in time order from left to right; undated rows have none.
    assert [shape for shape, _left in marks(html)] == ["mark", "mark"]
    assert marks(html)[0][1] < marks(html)[1][1]


def test_rows_that_all_stand_the_same_are_a_list_not_a_figure():
    """gpt-6-release-date: six models, all "Confirmed", right above
    the same six as bullets."""
    same = [item("Grok 4.6", status="available"), item("Grok 4.7", status="available")]
    assert topic_figures.clean_figures({"figures": [figure("lineup", same)]}, LINEUP_ANSWER) == []
    stored = [{"kind": "status", "title": "", "after_heading": "", "items": [
        {"label": "A", "note": "x", "disputed": False, "status": "confirmed"},
        {"label": "B", "note": "y", "disputed": False, "status": "confirmed"},
    ]}]
    assert topic_figures.stored_figures(stored) == []
    # Dates make it a figure again: the rows differ in when. A standing they
    # all share says nothing, so it is a timeline (when-will-agi-arrive: five
    # forecasters, each "Claimed, not settled").
    dated = [item("Grok 4.6", status="available", date="2026-08-12"),
             item("Grok 4.7", status="available", date="2026-09-21"),
             item("Grok 4.8", status="available")]
    timeline, = topic_figures.clean_figures({"figures": [figure("lineup", dated)]}, LINEUP_ANSWER)
    assert timeline["kind"] == "timeline"
    assert [(entry["label"], "status" in entry) for entry in timeline["items"]] == [
        ("Grok 4.6", False), ("Grok 4.7", False),
    ]


def test_a_lineup_without_any_standing_is_a_timeline():
    answer = "Dario Amodei expects it by 2027, Demis Hassabis around 2030, a survey says 2047."
    raw = {"figures": [figure("lineup", [
        item("Demis Hassabis", date="2030"), item("Dario Amodei", date="2027"), item("a survey", date="2047"),
    ])]}
    timeline, = topic_figures.clean_figures(raw, answer)
    assert timeline["kind"] == "timeline"
    assert [entry["label"] for entry in timeline["items"]] == ["Dario Amodei", "Demis Hassabis", "a survey"]


def test_the_time_axis_shows_the_day_of_the_check_only_when_it_is_near():
    timeline = {"kind": "timeline", "title": "", "after_heading": "", "items": [
        {"label": "Announced", "note": "", "disputed": False, "date": "30 September 2026"},
        {"label": "Available", "note": "", "disputed": True, "date": "13 October 2026"},
    ]}
    near = str(topic_figures.figure_html(timeline, as_of=date(2026, 11, 7)))
    assert 'class="af-asof"' in near and ">checked Nov 7<" in near
    # Round dates along the axis; it opens at one, left of the first mark.
    assert [label for _left, label in tick_labels(near)] == ["Sep 15", "Oct 1", "Oct 15", "Nov 1"]
    assert tick_labels(near)[0][0] < marks(near)[0][1]
    assert 'class="af-line is-disputed"' in near
    # A check long after the last event would squeeze the events into a corner.
    far = str(topic_figures.figure_html(timeline, as_of=date(2027, 6, 1)))
    assert "af-asof" not in far and "checked" not in far
    assert "af-asof" not in str(topic_figures.figure_html(timeline))


def test_a_date_is_drawn_as_wide_as_the_answer_was_precise():
    forecasts = {"kind": "timeline", "title": "", "after_heading": "", "items": [
        {"label": "Lab leaders", "note": "", "disputed": False, "date": "2026–2030"},
        {"label": "Forecasters", "note": "", "disputed": False, "date": "2033"},
        {"label": "Survey", "note": "", "disputed": False, "date": "2047"},
    ]}
    html = str(topic_figures.figure_html(forecasts, as_of=date(2026, 11, 12)))
    # A span of years is a bar from its first to its last year; the check
    # lies inside the forecasts and is marked.
    assert marks(html)[0][0] == "range" and "af-asof" in html
    assert [label for _left, label in tick_labels(html)] == ["2030", "2035", "2040", "2045"]
    october = (date(2026, 10, 1).toordinal(), date(2026, 10, 31).toordinal())
    assert topic_figures._day_span("October 2026") == october
    assert topic_figures._day_span("October 7–8, 2026") == (october[0] + 6, october[0] + 7)
    assert topic_figures._day_span("soon") is None


def test_a_status_board_of_an_earlier_run_is_drawn_as_a_lineup():
    stored = topic_figures.stored_figures([{"kind": "status", "title": "Availability", "after_heading": "", "items": [
        {"label": "Gemini 4 Argon", "note": "you can use it today", "disputed": False, "status": "confirmed"},
        {"label": "Gemini 4 Carbon", "note": "", "disputed": False, "status": "not_confirmed"},
        {"label": "Broken", "note": "", "disputed": False, "status": "shipped"},  # no such standing
    ]}])
    html = str(topic_figures.figure_html(stored[0]))
    assert 'class="af-chart is-sn"' in html and html.count('role="listitem"') == 2
    assert ">Confirmed</span>" in html and ">Not confirmed</span>" in html
    assert "af-plot" not in html and "af-when" not in html


def test_years_are_drawn_on_a_timeline_not_as_bars():
    """when-will-agi-arrive: the Judge filled the numbers template
    with forecast years; 2026, 2031 and 2047 as bars are three bars of almost
    the same length."""
    answer = ("Lab leaders say roughly 2026–2030. Metaculus: weakly general AI around 2027, "
              "general AI around 2031. Surveys put the 50% date at 2047.")
    raw = {"figures": [figure("numbers", [
        item("Some AI lab leaders", value="2026–2030", unit="year"),
        item("Weakly general AI", value="2027", unit="year"),
        item("Surveys, 50% date", value="2047", unit="year"),
    ], title="AGI forecast timing")]}

    cleaned = topic_figures.clean_figures(raw, answer)

    assert [f["kind"] for f in cleaned] == ["timeline"]
    assert [entry["date"] for entry in cleaned[0]["items"]] == ["2026–2030", "2027", "2047"]
    html = str(topic_figures.figure_html(cleaned[0]))
    assert "2026–2030" in html and "af-bar" not in html
    # A figure stored before the fix is drawn as a timeline too.
    stored = {"kind": "numbers", "title": "", "after_heading": "", "items": [
        {"label": "A", "note": "", "disputed": False, "value": "2027", "number": 2027.0, "unit": ""},
        {"label": "B", "note": "", "disputed": False, "value": "2047", "number": 2047.0, "unit": ""},
    ]}
    assert 'class="af af-timeline"' in str(topic_figures.figure_html(stored))
    # Real quantities stay bars.
    prices = {"kind": "numbers", "title": "", "after_heading": "", "items": [
        {"label": "Input", "note": "", "disputed": False, "value": "$2", "number": 2.0, "unit": "per 1M"},
        {"label": "Output", "note": "", "disputed": False, "value": "$10", "number": 10.0, "unit": "per 1M"},
    ]}
    assert "af-bar" in str(topic_figures.figure_html(prices))


def test_a_stalled_figures_judge_hands_over_without_its_retry(monkeypatch):
    """The Topic check waits for this call before it is stored: like the
    visual judge, a stalled attempt ends and the next family answers."""
    import json
    import time

    from app.services.llm import consensus_engine

    calls = []

    def fake(provider, *args, **kwargs):
        calls.append(provider)
        if provider == "openai":
            stop = consensus_engine.current_provider_cancellation()
            for _ in range(500):
                if stop is not None and stop.cancelled:
                    raise consensus_engine.ProviderCancelled("stopped")
                time.sleep(0.01)
            raise AssertionError("the stalled attempt was never stopped")
        return json.dumps({"figures": []})

    monkeypatch.setattr(consensus_engine, "JUDGE_ATTEMPT_SECONDS", 0.05)
    monkeypatch.setattr(consensus_engine, "_call_engine_text", fake)
    started = time.monotonic()
    result = consensus_engine.query_answer_figures("Q?", ANSWER, {"OpenRouter": "dummy"}, "OpenAI")
    assert time.monotonic() - started < 3.0
    assert result == {"figures": []}
    assert calls.count("openai") == 1 and len(calls) == 2


def test_a_rating_that_looks_like_a_year_stays_a_number():
    answer = "Model A scores 2048 Elo, model B 1999 Elo."
    raw = {"figures": [figure("numbers", [
        item("Model A", value="2048", unit="Elo"),
        item("Model B", value="1999", unit="Elo"),
    ])]}
    assert [f["kind"] for f in topic_figures.clean_figures(raw, answer)] == ["numbers"]


def test_malformed_judge_output_costs_the_figure_not_the_check():
    """A fallback judge that ignores the schema must not raise out of build()
    and end the paid Topic check (fail_topic_run)."""
    for raw in (
        {"figures": 5},
        {"figures": [{"kind": "numbers", "items": ["$2", "$5"]}]},
        {"figures": [{"kind": "timeline", "items": {"a": 1}}]},
        {"figures": [{"kind": "status", "items": [item("Gemini 4 Argon", status=["confirmed"])] * 2}]},
    ):
        assert topic_figures.clean_figures(raw, ANSWER) == []
        assert topic_figures.build("Q?", ANSWER, query=lambda *args, raw=raw: raw) == []


def test_a_stored_run_with_unreadable_items_never_breaks_the_page():
    """An imported run (admin) may lack fields the drawing reads."""
    stored = topic_figures.stored_figures([
        {"kind": "timeline", "items": [{"label": "A"}, {"label": "B", "date": "2027"}]},
        {"kind": "numbers", "items": [
            {"label": "Input", "value": "$2", "number": 2.0, "unit": "per 1M"},
            {"label": "Output", "value": "$10", "number": 10.0, "unit": "per 1M", "note": None},
        ]},
    ])
    assert [f["kind"] for f in stored] == ["numbers"]
    assert stored[0]["title"] == "" and stored[0]["after_heading"] == ""
    assert [entry["note"] for entry in stored[0]["items"]] == ["", ""]
    assert "af-bar" in str(topic_figures.figure_html(stored[0]))
