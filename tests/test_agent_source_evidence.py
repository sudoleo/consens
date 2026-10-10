"""Source excerpts for the Agent answer step: capture, binding, budget, pages."""
from concurrent.futures import wait
import json
import threading

import pytest

from app.services import agent_source_evidence as evidence
from app.services.agent_source_evidence import (
    EXCERPT_BUDGET_CHARS, LEAD_EXCERPT_CHARS, MIN_SEARCH_TEXT_CHARS, PooledSource, SourceEvidence,
    answer_citations, cited_claim, source_entries)


ANSWER = "Prices rose sharply. The tariff is 4.5% since [March 2026](https://example.org/a). It ends in May."
# End of the second sentence, where a provider puts the citation.
CLAIM_END = ANSWER.index(" It ends")


def citation(url="https://example.org/a", content="", end=None, start=None, hint=None):
    return {"url": url, "content": content, "start_index": start, "end_index": end, "fallback_end_index": hint}


def long_text(marker, lines=12):
    return "\n".join(f"Line {i} about {marker} with enough words to form a real paragraph of source text."
                     for i in range(lines))


def test_claim_is_the_cited_sentence_without_link_syntax():
    assert cited_claim(ANSWER, citation(start=21, end=CLAIM_END)) == "The tariff is 4.5% since March 2026."
    # Decimal points and the citation's own full stop are no sentence start.
    assert cited_claim("A: costs 4.5 EUR. B: costs 3 EUR.", citation(end=17)) == "A: costs 4.5 EUR."


def test_claim_uses_the_stream_position_only_inside_the_answer():
    # Native search adapters send 0/0: the text seen so far anchors the claim.
    assert cited_claim(ANSWER, citation(start=0, end=0, hint=25)).startswith("The tariff is 4.5%")
    # Without a position inside the text there is no claim, never the last sentence.
    assert cited_claim(ANSWER, citation(start=0, end=0, hint=len(ANSWER))) == ""
    assert cited_claim(ANSWER, citation(start=0, end=0)) == ""
    assert cited_claim("", citation(end=3)) == ""


def test_claim_drops_list_markers_bare_urls_and_keeps_the_end_of_long_sentences():
    text = "- **Rate**: 4.5% (https://example.org/a)\n- Next"
    assert cited_claim(text, citation(end=text.index("\n"))) == "Rate: 4.5%"
    sentence = "Word " * 100 + "the decisive figure is 7%."
    claim = cited_claim(sentence, citation(end=len(sentence)))
    assert claim.startswith("…") and claim.endswith("the decisive figure is 7%.")
    assert len(claim) <= evidence.CLAIM_CHARS + 1


def marker(text, link):
    start = text.index(link)
    return citation(start=start, end=start + len(link))


def test_claim_before_a_source_marker_is_the_cited_statement_not_the_marker():
    # Recorded shape of OpenAI's own search (2026-10-10): one marker after a
    # paragraph, its span covering only "([site](url))".
    link = "([ecb.europa.eu](https://www.ecb.europa.eu/press/pr/2026.html))"
    text = ("Der Einlagesatz beträgt 2,50 %.\n\n- **Seit wann:** Er gilt seit dem **16. September 2026**. "
            f"Die EZB hatte ihn um 25 Basispunkte angehoben. {link}  \n- Next")
    assert cited_claim(text, marker(text, link)) == ("Seit wann: Er gilt seit dem 16. September 2026. "
                                                     "Die EZB hatte ihn um 25 Basispunkte angehoben.")
    # The claim reaches back on its line only to an earlier marker.
    first, second = "([a.org](https://a.org/1))", "([b.org](https://b.org/2))"
    text = f"A holds. {first} B holds. C holds too. {second}"
    assert cited_claim(text, marker(text, second)) == "C holds too."
    # Inside a sentence the marker leaves the whole sentence; a link that
    # names the claim keeps its text, one that names the source goes.
    link = "[bundesbank.de](https://www.bundesbank.de/x)"
    text = f"Prices rose. The rate is 2.5 % {link} and applies since March. Next."
    assert cited_claim(text, marker(text, link)) == "The rate is 2.5 % and applies since March."
    link = "[4.5 percent](https://example.org/a)"
    text = f"Prices rose. The tariff is {link} since March. Next."
    assert cited_claim(text, marker(text, link)) == "The tariff is 4.5 percent since March."
    assert cited_claim(f"{first} Rest.", marker(f"{first} Rest.", first)) == ""


def test_positions_follow_the_provider_not_the_stream():
    # Google grounding counts UTF-8 bytes: an end past the characters converts.
    text = "* Der Einlagesatz für Banken: 2,50 %\n* Nächste Zinsentscheidung: 29. Oktober 2026"
    size = len(text.encode())
    cited = answer_citations(text, [citation("https://g.example/2", end=size, start=size - 30)])
    assert cited["https://g.example/2"]["claims"] == ["Nächste Zinsentscheidung: 29. Oktober 2026"]
    # Sources that arrived together came with the search results, before the
    # claims (Anthropic's own search): their stream position binds none.
    batch = answer_citations(ANSWER, [citation(f"https://example.org/{i}", "text", 0, 0, hint=25) for i in range(3)])
    assert all(entry["claims"] == [] and entry["content"] == "text" for entry in batch.values())
    single = answer_citations(ANSWER, [citation("https://example.org/a", "text", 0, 0, hint=25)])
    assert single["https://example.org/a"]["claims"] == ["The tariff is 4.5% since March 2026."]


def test_answer_citations_merge_repeated_urls_by_canonical_form():
    cited = answer_citations(ANSWER, [
        citation("https://Example.org/a#part", "short", end=CLAIM_END),
        citation("https://example.org/a", "the longer source text", end=CLAIM_END),
        citation("javascript:alert(1)", "x", end=5),
        "not a citation"])
    assert list(cited) == ["https://example.org/a"]
    assert cited["https://example.org/a"]["content"] == "the longer source text"
    assert len(cited["https://example.org/a"]["claims"]) == 1


def pooled(url, families, order, content="", claims=(), page=None, question="What is the tariff?"):
    return PooledSource(url=url, title=url.rsplit("/", 1)[-1], question=question, order=order,
                        families=set(families), claims=list(claims), content=content, page=page)


def test_entries_rank_by_families_keep_every_source_and_stay_in_budget():
    body = long_text("the tariff of 4.5 percent", 40)
    sources = [pooled(f"https://example.org/{i}", ["openai"], i, content=body, claims=["The tariff is 4.5%."])
               for i in range(30)]
    sources.append(pooled("https://example.org/shared", ["openai", "anthropic", "gemini"], 30, content=body))
    sources.append(pooled("https://example.org/empty", ["openai"], 31))
    entries = source_entries(sources)
    assert entries[0]["url"] == "https://example.org/shared" and entries[0]["cited_by"] == 3
    assert {e["url"] for e in entries} == {s.url for s in sources}
    with_excerpt = [e for e in entries if "excerpt" in e]
    assert 10 <= len(with_excerpt) < len(entries)
    used = sum(len(e["excerpt"]) + sum(len(c) for c in e.get("supports", [])) for e in with_excerpt)
    assert used <= EXCERPT_BUDGET_CHARS
    # Lead sources get more room than the rest; excerpts are original lines.
    assert len(with_excerpt[0]["excerpt"]) > len(with_excerpt[-1]["excerpt"])
    assert len(with_excerpt[0]["excerpt"]) <= LEAD_EXCERPT_CHARS
    assert all(line in body for e in with_excerpt for line in e["excerpt"].splitlines())
    assert "excerpt" not in next(e for e in entries if e["url"] == "https://example.org/empty")
    assert source_entries(sources, budget=0) == [{k: v for k, v in e.items() if k in {"url", "title", "cited_by"}}
                                                 for e in entries]


def test_excerpt_follows_the_supported_claim_not_the_page_start():
    body = "\n".join([long_text("history"), "The 2026 tariff is 4.5 percent for imports.", long_text("weather")])
    entry = source_entries([pooled("https://example.org/a", ["openai"], 0, content=body,
                                   claims=["The 2026 tariff is 4.5 percent."])], budget=600)[0]
    assert "The 2026 tariff is 4.5 percent for imports." in entry["excerpt"]
    assert entry["supports"] == ["The 2026 tariff is 4.5 percent."]


def comparison(cid, answers):
    return {"id": cid, "question": "What is the tariff?", "answers": answers}


def answer(provider, urls, late=False):
    return {"provider": provider, "sources": [{"id": f"S{i + 1}", "url": url, "title": f"T{i}"} for i, url in enumerate(urls)],
            **({"late": True} if late else {})}


class Pages:
    def __init__(self, documents=None, block=None):
        self.documents, self.block, self.calls = documents or {}, block, []

    def __call__(self, url, limits):
        self.calls.append(url)
        if self.block is not None:
            assert self.block.wait(5)
        if url not in self.documents:
            raise ValueError("not_found")
        return self.documents[url]


def settle(sources):
    wait(list(sources._pages.values()), timeout=5)


def test_pages_are_fetched_only_for_sources_without_search_text_and_within_bounds():
    pages = Pages()
    sources = SourceEvidence(fetch=pages, limits=object())
    rich = "x" * MIN_SEARCH_TEXT_CHARS
    sources.record("c1", "openai", ANSWER, [citation(f"https://example.org/{i}", rich if i == 0 else "", end=20)
                                            for i in range(8)])
    settle(sources)
    assert sorted(pages.calls) == [f"https://example.org/{i}" for i in range(1, 1 + evidence.PAGE_FETCHES_PER_ANSWER)]
    for family in ("anthropic", "gemini", "grok", "kimi"):
        sources.record("c1", family, ANSWER, [citation(f"https://{family}.org/{i}", end=20) for i in range(5)])
    settle(sources)
    assert len(pages.calls) == evidence.PAGE_FETCHES_PER_TURN


def test_collect_pools_answers_uses_page_text_and_skips_late_answers():
    page_text = long_text("the official tariff table")
    pages = Pages({"https://example.org/page": {"text": page_text, "dates": [
        {"value": "2026-09-30T08:00:00Z", "origin": "meta:article:published_time"}]}})
    sources = SourceEvidence(fetch=pages, limits=object())
    search_text = long_text("an Exa highlight")
    sources.record("c1", "deepseek", ANSWER, [citation("https://example.org/search", search_text, end=CLAIM_END),
                                            citation("https://example.org/page", "", end=CLAIM_END)])
    sources.record("c1", "openai", ANSWER, [citation("https://example.org/page", "teaser", start=0, end=0, hint=25)])
    sources.record("c1", "gemini", ANSWER, [citation("https://example.org/late", search_text, end=CLAIM_END)])
    comparisons = [comparison("c1", [
        answer("deepseek", ["https://example.org/search", "https://example.org/page"]),
        answer("openai", ["https://example.org/page"]),
        answer("gemini", ["https://example.org/late"], late=True)])]
    entries = source_entries(sources.collect(comparisons, wait_seconds=2))
    by_url = {e["url"]: e for e in entries}
    assert set(by_url) == {"https://example.org/search", "https://example.org/page"}
    page = by_url["https://example.org/page"]
    assert entries[0] is page and page["cited_by"] == 2
    assert page["published"] == "2026-09-30T08:00:00Z"
    assert "official tariff table" in page["excerpt"] and page["supports"] == ["The tariff is 4.5% since March 2026."]
    assert "Exa highlight" in by_url["https://example.org/search"]["excerpt"]


def test_failed_or_slow_pages_leave_the_source_listed_without_excerpt():
    gate = threading.Event()
    sources = SourceEvidence(fetch=Pages(block=gate), limits=object())
    try:
        sources.record("c1", "openai", ANSWER, [citation("https://example.org/slow", "", end=20)])
        checks = []
        entries = source_entries(sources.collect([comparison("c1", [answer("openai", ["https://example.org/slow"])])],
                                                 wait_seconds=.3, check=lambda: checks.append(1)))
        assert entries == [{"url": "https://example.org/slow", "title": "T0", "cited_by": 1}]
        assert checks
    finally:
        gate.set()
    sources = SourceEvidence(fetch=Pages(), limits=object())
    sources.record("c1", "openai", ANSWER, [citation("https://example.org/missing", "", end=20)])
    settle(sources)
    entries = source_entries(sources.collect([comparison("c1", [answer("openai", ["https://example.org/missing"])])]))
    assert entries == [{"url": "https://example.org/missing", "title": "T0", "cited_by": 1}]


def test_a_stopped_turn_ends_the_wait_for_pages():
    gate = threading.Event()
    sources = SourceEvidence(fetch=Pages(block=gate), limits=object())
    def stop():
        raise RuntimeError("stopped")
    try:
        sources.record("c1", "openai", ANSWER, [citation("https://example.org/slow", "", end=20)])
        with pytest.raises(RuntimeError):
            sources.collect([comparison("c1", [answer("openai", ["https://example.org/slow"])])],
                            wait_seconds=5, check=stop)
    finally:
        gate.set()


def test_close_stops_fetches_that_have_not_started():
    gate = threading.Event()
    pages = Pages(block=gate)
    sources = SourceEvidence(fetch=pages, limits=object())
    try:
        sources.record("c1", "openai", ANSWER, [citation(f"https://example.org/{i}", "", end=20) for i in range(4)])
        sources.close()
        sources.record("c2", "gemini", ANSWER, [citation("https://example.org/after", "", end=20)])
    finally:
        gate.set()
    settle(sources)
    assert "https://example.org/after" not in pages.calls
    assert len(pages.calls) <= 3  # only the pool's running fetches


# The real client: citations keep text and position, sources stay small.

def test_client_keeps_citation_text_and_offsets_in_memory_only(monkeypatch):
    from app.services.llm.agent_client import AgentCompletion, resolve_agent_model
    from test_agent_loop import packet, transport, usage
    annotation = lambda url, content, start, end: {"type": "url_citation", "url_citation": {
        "url": url, "title": "T", "content": content, "start_index": start, "end_index": end}}
    many = [annotation(f"https://example.org/{i}", "text", 0, 6) for i in range(12)]
    snapshot = [annotation("https://example.org/0", "first", 0, 6), annotation("javascript:alert(1)", "x", 0, 6)]
    transport(monkeypatch, [[packet({"content": "Answer.", "annotations": many}),
                             packet({"annotations": snapshot + [{"type": "url_citation", "url_citation": {
                                 "url": "https://example.org/0", "content": "x" * 9000, "start_index": True}}]}),
                             packet(finish="stop", usage=usage(1))]])
    completion = AgentCompletion()
    events = list(completion.stream(model=resolve_agent_model("claude-haiku-4-5"),
                                    messages=[{"role": "user", "content": "Question"}], api_key="test"))
    assert completion.text == "Answer."
    assert [s["url"] for s in completion.sources] == [f"https://example.org/{i}" for i in range(10)]
    assert all(set(s) == {"url", "title"} for s in completion.sources)
    citations = completion.citations
    assert [c["url"] for c in citations[:10]] == [s["url"] for s in completion.sources]
    # The stream position includes the text of the chunk the citation came with.
    assert citations[0] == {"url": "https://example.org/0", "content": "text", "start_index": 0, "end_index": 6,
                            "fallback_end_index": len("Answer.")}
    # Repeated snapshots are dropped; an invalid offset becomes no offset.
    assert len(citations) == 11
    assert citations[-1]["start_index"] is None and len(citations[-1]["content"]) == 4000
    # Source text is evidence for the answer step, never an event or stored activity.
    assert "x" * 100 not in json.dumps(events) + json.dumps(completion.activity)
