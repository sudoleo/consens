"""New-answer sanitation and structured dispute checkability contracts."""
import json
from unittest import mock

import pytest

from app.services.llm.consensus_citations import ConsensusCitationFilter, strip_consensus_source_markers
from app.services.llm.consensus_engine import (
    _build_consensus_prompt, _build_differences_prompt, parse_differences_payload, query_consensus, stream_consensus,
)


@pytest.mark.parametrize("text,expected", [
    ("Fact.[S1] Next.[S2, S3]", "Fact. Next."),
    ("Fact [s21](https://example.org).", "Fact ."),
    ("[12] and S12 are ordinary text.", "[12] and S12 are ordinary text."),
    ("Code `[S1]` and ``x`[S2]``. Fact.[S3]", "Code `[S1]` and ``x`[S2]``. Fact."),
    ("Code ``x```[S1]``. Fact.[S2]", "Code ``x```[S1]``. Fact."),
    ("```python\nx = '[S1]'\n```\nFact.[S2]", "```python\nx = '[S1]'\n```\nFact."),
    ("~~~\n[S1]\n~~~\n    [S2]\nFact.[S3]", "~~~\n[S1]\n~~~\n    [S2]\nFact."),
    (r"Math \([S1]\) and \[[S2]\]. Fact.[S3]", r"Math \([S1]\) and \[[S2]\]. Fact."),
    ("$$\n[S1]\n$$\nFact.[S2]", "$$\n[S1]\n$$\nFact."),
    ("Math $f_{[S1]}$; fact.[S2]", "Math $f_{[S1]}$; fact."),
    (r"Math $\sum_{i\in[S1]} i$; fact.[S2]", r"Math $\sum_{i\in[S1]} i$; fact."),
    ("Currency $5[S1] and $6[S2].", "Currency $5 and $6."),
    (r"\begin{align}[S1]\end{align} Fact.[S2]", r"\begin{align}[S1]\end{align} Fact."),
    (r"\begin{equation*}[S1]\end{equation*} Fact.[S2]", r"\begin{equation*}[S1]\end{equation*} Fact."),
    ("Cost $5.[S1] Revenue 10 $. [S2]", "Cost $5. Revenue 10 $. "),
    (r"Literal \[S1]. Fact.[S2]", r"Literal \[S1]. Fact."),
    ("Unclosed code ```[S1]", "Unclosed code ```[S1]"),
])
def test_complete_and_every_chunk_boundary_agree(text, expected):
    assert strip_consensus_source_markers(text) == expected
    for split in range(len(text) + 1):
        scanner = ConsensusCitationFilter()
        actual = scanner.feed(text[:split]) + scanner.feed(text[split:]) + scanner.feed("", final=True)
        assert actual == expected
    scanner = ConsensusCitationFilter()
    assert "".join(scanner.feed(char) for char in text) + scanner.feed("", final=True) == expected


def test_synthesis_keeps_source_information_but_prohibits_tags():
    prompt = _build_consensus_prompt("Q", {"openai": "A.[S1]"}, [], model_sources={
        "OpenAI": [{"id": "S1", "url": "https://example.org", "title": "Original evidence"}],
    })
    assert "Original evidence" in prompt
    assert "A.[S1]" in prompt
    assert "Do not output S-source references" in prompt
    assert "include the existing source tag" not in prompt


def test_differences_prompt_keeps_source_eligibility_separate_from_detection():
    prompt = _build_differences_prompt(
        {"openai": "Choose PostgreSQL.", "gemini": "Choose MongoDB."},
        "Choose PostgreSQL.", [],
    )[0]
    assert "never a filter for reporting differences" in prompt
    assert "competing preferences or recommendations" in prompt
    assert "must not remove a difference or change its type or severity" in prompt


def test_prose_streams_immediately_and_partial_markers_never_leak():
    scanner = ConsensusCitationFilter()
    assert scanner.feed("A useful answer.") == "A useful answer."
    assert scanner.feed("[S") == ""
    assert scanner.feed("12") == ""
    assert scanner.feed("]") == ""
    assert scanner.feed(" More") == " More"
    assert scanner.feed("", final=True) == ""


def test_query_and_stream_remove_tags_before_final_or_delta():
    raw = "Fact.[S1]\nCode `[S2]`. Next.[S3]"
    kwargs = dict(question="Q", answers={"openai": "A"}, excluded_models=[],
                  consensus_model="OpenAI", api_keys={"OpenRouter": "test"})
    with mock.patch("app.services.llm.consensus_engine._call_engine_text", return_value=raw):
        answer = query_consensus(**kwargs)
    with mock.patch("app.services.llm.consensus_engine._stream_consensus_engine", return_value=(
        {"type": "delta", "text": char} for char in raw
    )):
        events = list(stream_consensus(**kwargs))
    assert answer == "Fact.\nCode `[S2]`. Next."
    assert events[-1] == {"type": "final", "text": answer}
    assert "".join(event["text"] for event in events if event["type"] == "delta") == answer


def _parsed(factual=None, anchor="The rate is 5%."):
    diff = {"claim": "Which rate applies?", "type": "contradiction", "severity": "major",
            "consensus_anchor": anchor, "positions": [
                {"stance": "Five percent", "models": ["Model A", "Model C"], "quote": "The rate is 5%."},
                {"stance": "Ten percent", "models": ["Model B"], "quote": "The rate is 10%."},
            ]}
    if factual is not None:
        diff["factual_check"] = factual
    data, _ = parse_differences_payload(json.dumps({"differences": [diff], "best_model": "Model A"}),
        {"Model A": "OpenAI", "Model B": "Gemini", "Model C": "Grok"},
        consensus_answer="The rate is 5%.", model_answers={
            "OpenAI": "The rate is 5%.", "Gemini": "The rate is 10%.", "Grok": "No number given.",
        })
    return data["differences"][0]


def test_checkability_and_original_quote_provenance_are_preserved():
    diff = _parsed({"checkable": True, "question": "Which rate applies in 2026?", "reason": "A documented rate."})
    assert diff["factual_check"]["checkable"] is True
    assert diff["consensus_anchor_validated"] is True
    assert diff["positions"][0]["quote_models"] == ["OpenAI"]
    assert diff["positions"][0]["models"] == ["OpenAI", "Grok"]
    assert diff["positions"][1]["quote_models"] == ["Gemini"]


@pytest.mark.parametrize("factual", [None, {}, "yes", {"checkable": "true", "question": "Rate?"},
                                     {"checkable": True}, {"checkable": False, "question": "Best choice?"}])
def test_legacy_or_uncertain_classification_fails_closed(factual):
    assert _parsed(factual)["factual_check"]["checkable"] is False


def test_unmatched_anchor_cannot_be_marked_validated():
    diff = _parsed({"checkable": True, "question": "Rate?"}, anchor="The rate is 91%.")
    assert diff["consensus_anchor"] == ""
    assert diff["consensus_anchor_validated"] is False


@pytest.mark.parametrize("factual", [None, {"checkable": False, "question": "Which option is preferable?"},
                                     {"checkable": True, "question": "Which documented limit applies?"}])
def test_source_check_eligibility_never_filters_differences_or_claims(factual):
    """Regression: the new field is metadata, not a display or scoring gate.

    The non-checkable recommendation case was also exercised with a live
    Differences judge: it remains a major contradiction in the returned data.
    """
    consensus = "Choose PostgreSQL. Both products store data."
    positions = [
        {"stance": "Choose PostgreSQL", "models": ["Model A"], "quote": "Choose PostgreSQL."},
        {"stance": "Choose MongoDB", "models": ["Model B"], "quote": "Choose MongoDB."},
    ]
    raw_differences = [
        {"claim": "Opposite recommendations", "consensus_anchor": "Choose PostgreSQL.",
         "type": "contradiction", "severity": "major", "positions": positions},
        {"claim": "A side-detail disagreement", "type": "contradiction", "severity": "minor", "positions": positions},
        {"claim": "Different priorities", "type": "emphasis", "positions": positions},
    ]
    if factual is not None:
        for diff in raw_differences:
            diff["factual_check"] = factual
    payload = {"differences": raw_differences, "best_model": "Model A", "claims": [
        {"anchor": "Both products store data.", "agree": ["Model A", "Model B"], "dissent": []},
    ]}
    data, _ = parse_differences_payload(json.dumps(payload), {"Model A": "OpenAI", "Model B": "Gemini"},
        consensus_answer=consensus, model_answers={
            "OpenAI": "Choose PostgreSQL. Both products store data.",
            "Gemini": "Choose MongoDB. Both products store data.",
        })
    assert [(diff["type"], diff["severity"]) for diff in data["differences"]] == [
        ("contradiction", "major"), ("contradiction", "minor"), ("emphasis", ""),
    ]
    assert len(data["claims"]) == 1
    assert data["claims"][0]["agree"] == ["OpenAI", "Gemini"]
    assert data["agreement"]["major_contradictions"] == 1
    assert data["agreement"]["minor_contradictions"] == 1
    assert data["agreement"]["emphases"] == 1
    assert all(len(diff["positions"]) == 2 for diff in data["differences"])
