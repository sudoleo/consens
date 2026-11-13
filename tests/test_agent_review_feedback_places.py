"""Which places of an answer the correction pass may rewrite
(agent_review_feedback.safe_place, kept_shape): Max's run of 2026-11-13 on a
comparison question left four of six findings with "no place it could safely
rewrite", three in table cells and one beside a price with "$". Only the
sentences quoted from that run are used here."""
import json

import pytest

from app.services import agent_review_feedback as fb
from test_agent_audit import Audit
from test_agent_review_feedback import agent_side, correction_request, feedback_loop
from test_agent_runs import UID, pending, store  # noqa: F401  (fixtures)

CELL = "Keine: kein Graph-Editor, keine eigenen Tools/MCP, kein Self-Hosting"
PRICE = "Die Konkurrenz kostet 17–20 $/Monat Einstieg plus Credits."
TABLE = ("Ein Vergleich der Werkzeuge folgt hier.\n\n"
         "| Werkzeug | Stärke | Lücke |\n"
         "|---|---|---|\n"
         f"| consens.io | Prüfer laufen mit. | {CELL} |\n"
         "| Andere | Großer Markt. | Teuer |\n\n"
         f"1. {PRICE}\n"
         "2. Ein zweiter Punkt der Liste steht hier.\n\n"
         "Schluss mit genug Wörtern.")


@pytest.fixture(autouse=True)
def _admin_allowance(monkeypatch):
    from app.services import agent_budget_config
    monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, "pro", 5_000_000)


def finding_on(answer, words, key="s1"):
    spans = fb.sentence_spans(answer)
    numbers = [i for i, (start, end) in enumerate(spans, 1) if words in answer[start:end]]
    assert numbers, words
    return {"id": key, "sentences": numbers}


def place(answer, words):
    return fb.correction_items(answer, [finding_on(answer, words)]).get("s1")


# --- Table cells ---------------------------------------------------------------

def test_a_body_cell_of_a_table_is_a_place_and_stays_a_cell():
    start, end, before = place(TABLE, "Keine: kein Graph-Editor")
    assert before == CELL and fb.table_cells(TABLE, {"s1": (start, end, before)}) == {"s1"}
    items = {"s1": (start, end, before)}
    fixed = "Teilweise: eigene Tools über MCP, kein Self-Hosting"
    results = fb.read_corrections(json.dumps({"findings": [{"id": "s1", "sentence": fixed}]}), items, cells={"s1"})
    out = fb.corrected_answer(TABLE, items, results)
    row = next(line for line in out.split("\n") if line.startswith("| consens.io"))
    assert row == f"| consens.io | Prüfer laufen mit. | {fixed} |"
    assert [line.count("|") for line in out.split("\n") if line.startswith("|")] == [4, 4, 4, 4]


@pytest.mark.parametrize("reply", [
    "Teilweise | eigene Tools",                       # a new cell
    "Teilweise:\neigene Tools",                       # a new row
    "Teilweise: " + "eigene Tools über MCP, " * 10,   # no longer a cell of its column
], ids=["border", "line-break", "too-long"])
def test_a_cell_that_would_break_the_table_stays(reply):
    items = {"s1": place(TABLE, "Keine: kein Graph-Editor")}
    assert fb.read_corrections(json.dumps({"findings": [{"id": "s1", "sentence": reply}]}), items, cells={"s1"}) == {}


def test_an_escaped_border_in_a_cell_is_text():
    items = {"s1": place(TABLE, "Keine: kein Graph-Editor")}
    fixed = r"Teilweise: eigene Tools \| MCP, kein Self-Hosting"
    assert fb.read_corrections(json.dumps({"findings": [{"id": "s1", "sentence": fixed}]}), items,
                               cells={"s1"})["s1"][0] == "corrected"


def test_header_and_separator_rows_stay_closed():
    answer = TABLE.replace("| Werkzeug | Stärke | Lücke |", "| Werkzeug ist hier. | Stärke | Lücke |")
    spans = fb.sentence_spans(answer)
    header = answer.index("Werkzeug ist hier.")
    assert not any(start <= header < end and fb.safe_place(answer, start, end) for start, end in spans)
    separator = answer.index("|---|")
    assert not fb.safe_place(answer, separator + 1, separator + 4)


def test_a_cell_never_widens_into_the_next_one():
    answer = TABLE.replace("| Prüfer laufen mit. |", "| **Prüfer laufen mit. |").replace(
        f"{CELL} |", f"{CELL}** |")
    assert place(answer, "Prüfer laufen mit.") is None


def test_the_agent_learns_that_a_place_is_a_table_cell():
    items = {"s1": place(TABLE, "Keine: kein Graph-Editor")}
    finding = {"id": "s1", "kind": "doubtful", "voices": {"Claude"}, "notes": [{"kind": "doubtful", "note": "n"}]}
    message = fb.correction_message([finding], items, cells={"s1"})
    sent = json.loads(message.split("\n", 1)[1].split("\n\nFor each finding", 1)[0])["findings"][0]
    assert sent["place"] == "table cell" and sent["sentence"] == CELL
    assert '"place": "table cell"' in fb.CORRECTION_REQUEST.replace("\\", "") or "table cell" in fb.CORRECTION_REQUEST
    plain = fb.correction_message([finding], {"s1": place(TABLE, "Ein zweiter Punkt")})
    assert "place" not in json.loads(plain.split("\n", 1)[1].split("\n\nFor each finding", 1)[0])["findings"][0]


# --- A price is no formula ------------------------------------------------------

def test_a_sentence_with_a_price_in_dollars_is_a_place():
    start, end, before = place(TABLE, "Die Konkurrenz kostet")
    assert before == PRICE
    fixed = "Die Konkurrenz kostet 19–25 $/Monat Einstieg plus Credits."
    items = {"s1": (start, end, before)}
    results = fb.read_corrections(json.dumps({"findings": [{"id": "s1", "sentence": fixed}]}), items)
    assert fixed in fb.corrected_answer(TABLE, items, results)


@pytest.mark.parametrize("sentence", [
    "Ein Monat kostet $20 im Abo.", "Das Paket kostet 20 US-$ im Monat.", "Es sind 6,7 Mrd. $ in Q1 gegenüber 6,1 Mrd. $ in Q2.",
], ids=["$20", "US-$", "two-amounts"])
def test_currency_signs_never_count_as_a_formula(sentence):
    answer = f"Eine Einleitung mit genug Wörtern.\n\n{sentence}\n\nSchluss mit genug Wörtern."
    assert place(answer, sentence[:12])[2] == sentence


def test_a_formula_the_page_renders_is_never_cut():
    """The sentence splitter keeps a formula whole; a place that began or
    ended inside one would rewrite half of it."""
    answer = "Eine Einleitung mit genug Wörtern.\n\nEs gilt $x^2 + y$ für alle Werte im Text.\n\nSchluss."
    line = answer.index("Es gilt")
    inside = answer.index("+ y$")
    assert fb._formulas(answer[line:]) and not fb.safe_place(answer, line, inside)
    assert fb.safe_place(answer, line, answer.index(" im Text.") + len(" im Text."))


def test_a_correction_that_would_make_a_formula_with_a_price_beside_it_stays():
    """A "$" of the new text may pair with a price's "$" beside the place
    into a formula the page would render: the sentence stays as it was."""
    answer = "Eine Einleitung mit genug Wörtern.\n\nKosten: $5 pro Stück. Die Formel lautet x^2 im Text.\n\nSchluss."
    start, end, before = place(answer, "Die Formel lautet")
    items = {"s1": (start, end, before)}
    reply = "Die Formel lautet x^2$ im Text."
    results = fb.read_corrections(json.dumps({"findings": [{"id": "s1", "sentence": reply}]}), items)
    assert results and fb.corrected_answer(answer, items, results) == answer and results == {}
    # Without such a pair the same kind of change goes through.
    fine = "Die Formel lautet x hoch 2 im Text."
    results = fb.read_corrections(json.dumps({"findings": [{"id": "s1", "sentence": fine}]}), items)
    assert fine in fb.corrected_answer(answer, items, results)


# --- The pass on Max's three places ------------------------------------------------

def test_the_three_places_of_the_run_reach_the_agent(store):
    """Two cells and the price sentence go to the agent; corrected, the
    table keeps its columns and the list its items."""
    asked = []

    def correct(findings):
        asked.append(findings)
        replies = []
        for item in findings:
            if item.get("place") == "table cell" and "Graph-Editor" in item["sentence"]:
                replies.append({"id": item["id"], "sentence": "Teilweise: eigene Tools über MCP, kein Self-Hosting"})
            elif "17–20" in item["sentence"]:
                replies.append({"id": item["id"], "sentence": PRICE.replace("17–20", "19–25")})
            else:
                replies.append({"id": item["id"], "stands": "Das steht so in der Quelle."})
        return json.dumps({"findings": replies})

    reviews = {"anthropic": json.dumps({"marks": [
        {"quote": "kein Graph-Editor", "kind": "doubtful", "note": "Es gibt eigene Tools über MCP."},
        {"quote": "Großer Markt.", "kind": "doubtful", "note": "Unbelegt."},
        {"quote": "17–20 $/Monat", "kind": "doubtful", "note": "Der Einstieg kostet heute 19–25 $."}]}),
        "openai": json.dumps({"marks": []})}
    script = Audit(reviews, answer=TABLE, live={"anthropic": agent_side(correct)})
    loop = feedback_loop(store, script)
    list(loop.run())
    assert len(asked) == 1 and len(asked[0]) == 3
    assert sum(1 for item in asked[0] if item.get("place") == "table cell") == 2
    text = store.get_turn(UID, loop.chat_id, loop.turn_id)["assistant_response"]
    assert "Teilweise: eigene Tools über MCP" in text and "19–25 $/Monat" in text
    assert [line.count("|") for line in text.split("\n") if line.startswith("|")] == [4, 4, 4, 4]
    assert "\n1. " in text and "\n2. " in text


def test_the_request_asks_for_the_sentences_language():
    """Max's run got an English sentence in a German answer: the request says
    to keep the sentence's language (no detection by word lists)."""
    assert "in the language it is written in" in fb.CORRECTION_REQUEST


def test_the_formula_rule_is_the_renderers():
    """_formulas copies math-render.js: the page and the pass must agree on
    what a formula is, or a correction could break one the page renders."""
    import re
    from pathlib import Path
    source = Path(__file__).resolve().parents[1].joinpath("static", "js", "math-render.js").read_text(encoding="utf-8")
    inline = re.search(r"const DOLLAR_INLINE_RE =\s*/(.+)/g;", source).group(1)
    signal = re.search(r"const LATEX_SIGNAL_RE = /(.+)/;", source).group(1)
    limit = int(re.search(r"const MAX_INLINE_MATH_CHARS = (\d+);", source).group(1))
    assert inline == fb._INLINE_FORMULA.pattern and signal == fb._LATEX_SIGNAL.pattern
    assert limit == fb.MAX_INLINE_FORMULA_CHARS


# --- A quote of a table row lands on its cells ------------------------------------

ROW_TABLE = ("Ein Vergleich folgt.\n\n| Kriterium | consens.io | Andere | Frameworks |\n|---|---|---|---|\n"
             f"| **Kontrolle / Erweiterbarkeit** | {CELL} | Keine: eigene Plattform, eigene Regeln | Voll: Graphen, State |\n"
             "| **Preis** | Kostenlos | Teuer | Frei |\n\nSchluss.")
ROW_QUOTE = "| **Kontrolle / Erweiterbarkeit** | Keine: eigene Plattform, eigene Regeln |"


def test_a_quote_of_a_row_with_its_label_lands_on_the_cell_it_means():
    """Max's run: the reviewer quoted the row's label and the third cell as
    Markdown, the cell between left out; the mark hung unplaced under the
    answer."""
    from app.services.agent_audit import place_marks
    claims, unplaced, _ = place_marks(ROW_TABLE, [("OpenAI", [{"quote": ROW_QUOTE, "kind": "wrong", "note": "x",
                                                               "source": "https://example.org"}], False)])
    assert unplaced == [] and [c["anchor"] for c in claims] == ["Keine: eigene Plattform, eigene Regeln"]
    assert claims[0]["dissent"][0]["target"] == "Keine: eigene Plattform, eigene Regeln"


@pytest.mark.parametrize("quote, cells", [
    ("| **Preis** | Kostenlos |", ["Kostenlos"]),
    ("| Kostenlos | Teuer |", ["Kostenlos", "Teuer"]),
    ("| **Preis** | Gratis |", []),              # no such cell
    ("| Keine | Voll |", []),                      # too short to name a cell
], ids=["label-and-cell", "two-cells", "not-in-the-table", "too-short"])
def test_a_row_quote_names_cells_of_one_row_only(quote, cells):
    from app.services.agent_audit import locate_cells
    assert [ROW_TABLE[s:e] for s, e in locate_cells(ROW_TABLE, quote)] == cells


def test_a_row_quote_two_rows_fit_names_none():
    from app.services.agent_audit import locate_cells
    twice = ROW_TABLE + "\n\n| Kriterium | A |\n|---|---|\n| **Preis** | Kostenlos |"
    assert locate_cells(twice, "| **Preis** | Kostenlos |") == []
