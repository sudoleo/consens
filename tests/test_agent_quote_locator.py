"""Where a reviewer's quote stands in the answer (agent_audit.locate_quote).

Every mark of every turn goes through it: a quote it cannot find leaves its
mark unplaced (agent_audit.place_marks). Until 2026-10-31 the same search
form located a pasted text for check_text (tests/test_agent_passage_check.py,
removed with it); these are its cases on the quote locator.
"""
import pytest

from app.services.agent_audit import locate_quote
from app.services.llm.consensus_engine import _enumerate_consensus_sentences


def found(answer, quote):
    span = locate_quote(answer, quote)
    assert span is not None, quote
    return answer[span[0]:span[1]]


def test_case_quotation_marks_and_whitespace_do_not_count():
    answer = "Is this true?\n\nChatGPT said: „Heat  pumps\nwork fine.“ Also they are cheap to run here."
    assert found(answer, '"heat pumps work fine.') == "Heat  pumps\nwork fine.“"
    # Shortened with "...": from its first to its last part.
    assert found(answer, "heat pumps work ... cheap to run here") == (
        "Heat  pumps\nwork fine.“ Also they are cheap to run here.")


def test_a_closing_quote_and_ellipsis_after_the_quote_belong_to_it():
    assert found("Check: „It costs 100 dollars here…“ Is that so?", "It costs 100 dollars here") == (
        "It costs 100 dollars here…“")


def test_a_repeated_phrase_ends_the_passage_at_its_first_occurrence_after_the_start():
    answer = "Note: the price rises. Later the price rises again. And the price rises."
    assert found(answer, "the price rises. ... price rises again.") == "the price rises. Later the price rises again."


def test_markdown_bullets_and_invisible_characters_do_not_hide_the_quote():
    zwsp = chr(0x200b)
    answer = (f"Is that so?\n\n**Yes**, heat pumps work in old buildings.\n- They save{zwsp} money over time.\n"
              "- Radiators often suffice.")
    passage = found(answer, "Yes, heat pumps work ... They save money over time. Radiators often suffice.")
    assert passage.startswith("**Yes**") and passage.endswith("Radiators often suffice.")
    assert found(answer, "They save money over time.") == f"They save{zwsp} money over time."


def test_of_two_places_the_one_where_a_passage_begins_wins():
    answer = ("Do heat pumps work in old buildings? Many ask this:\n\n"
              "Heat pumps work in old buildings if they are insulated.")
    assert found(answer, "heat pumps work in old buildings ... if they are insulated.") == (
        "Heat pumps work in old buildings if they are insulated.")


def test_a_quote_cut_inside_a_word_takes_the_whole_word():
    assert found("Note: Heat pumps are efficient machines. Thanks", "eat pumps are efficient mach") == (
        "Heat pumps are efficient machines.")


@pytest.mark.parametrize("quote", [
    "Eine Wärmepumpe senkt den CO2-Ausstoß ... für 150 m2 Wohnfläche.",
    "Eine Wärmepumpe senkt den CO₂-Ausstoß ... für 150 m² Wohnfläche.",
    "Eine Wärmepumpe senkt den CO₂-Ausstoß ... reicht… für 150 m² Wohnfläche.",
])
def test_subscripts_superscripts_and_ellipses_do_not_hide_the_quote(quote):
    answer = "Eine Wärmepumpe senkt den CO₂-Ausstoß deutlich. Eine Anlage mit 8 kW reicht… für 150 m² Wohnfläche."
    assert found("Stimmt das?\n\n" + answer, quote) == answer


def test_a_decomposed_accent_keeps_the_quote_whole():
    answer = "Heat pumps work in old buildings. Ask the café"
    assert found("Check: " + answer, "Heat pumps work ... ask the café") == answer


@pytest.mark.parametrize("text,sentence", [
    ("## Heat pumps are efficient machines.\nHeat pumps are efficient machines.", "Heat pumps are efficient machines."),
    ("| Option | Cost |\n|---|---|\n| Air pump | Cost |\n", "Cost"),
    ("```\nThis sentence is inside a fence.\n```\nThis sentence is inside a fence.", "This sentence is inside a fence."),
])
def test_sentence_offsets_point_at_the_sentence_not_an_earlier_copy(text, sentence):
    """place_marks puts a mark on the sentences its quote overlaps: their
    offsets in the answer (``spans``) must be those of the counted sentences."""
    spans = []
    _, sentences = _enumerate_consensus_sentences(text, limit=None, spans=spans)
    assert [text[start:end] for start, end in spans] == sentences
    assert spans[-1][0] == text.rindex(sentence)
