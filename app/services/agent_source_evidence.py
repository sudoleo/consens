"""What the cited sources say, for the Agent answer step.

Comparison models cite URLs from their web search. OpenRouter sends source
text with each URL citation (``url_citation.content``): Exa highlights for the
families without their own search; for native search often nothing usable.
Before this module the answer step saw only URL and title, so it could weigh
what the answers claimed, but not what their sources say.

Per turn this module keeps the cited source text in memory, binds each source
to the answer sentences it supports, fetches the page for sources without
usable text (the bounded, cached retrieval of the source checks, started as
soon as an answer arrives) and gives the answer step one deduplicated source
list with relevant original excerpts under a fixed character budget.

No model call, no search, nothing persisted or streamed. See
docs/agent-mode.md, "Quellenauszüge für die Antwort".
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
import re
import threading
import time

from app.core.observability import record_metric
from app.services.llm.citations import citation_end
from app.services.source_catalog import canonical_source_url
from app.services.source_documents import fetch_document, select_passages

# Excerpts and supported claims of all sources of one answer step together:
# about 4000 input tokens, roughly one cent at 3 $ per million input tokens.
EXCERPT_BUDGET_CHARS = 16_000
# The most cited sources get room for context and qualifications, the rest a
# focused passage; below MIN_EXCERPT_CHARS an excerpt no longer carries a claim.
LEAD_SOURCES, LEAD_EXCERPT_CHARS = 4, 1200
EXCERPT_CHARS = 500
MIN_EXCERPT_CHARS = 200
# Search text shorter than this is a teaser, not evidence: the page is
# fetched instead.
MIN_SEARCH_TEXT_CHARS = 200
CLAIMS_PER_SOURCE, CLAIM_CHARS = 2, 240
# Page fetches cost no tokens, only time and outbound requests: the first
# sources of each answer, bounded per turn.
PAGE_FETCHES_PER_ANSWER, PAGE_FETCHES_PER_TURN = 4, 12
# Fetches start while slower models still answer; the answer step waits at
# most this long for the rest.
PAGE_WAIT_SECONDS = 4.0
# The source documents' DNS gate admits four lookups at once (dns_busy beyond).
_pages = ThreadPoolExecutor(max_workers=3, thread_name_prefix="agent-source-page")

_SENTENCE_END = re.compile(r"[.!?…](?:[\"'”’)\]}]+)?\s+|\n")
_MARKDOWN_LINK = re.compile(r"!?\[([^\]\n]*)\]\(\s*<?https?://[^\s)>]*>?\s*\)")
_BARE_URL = re.compile(r"<?https?://[^\s<>()\[\]]+>?")
_EMPTY_BRACKETS = re.compile(r"\(\s*[,;]?\s*\)|\[\s*\]")
_LEADING_MARKER = re.compile(r"^(?:#{1,6}\s+|[-*+]\s+|\d{1,3}[.)]\s+|>\s*)+")


def _anchored(text, citation):
    """Whether the citation marks a position inside the answer text."""
    start, end = citation.get("start_index"), citation.get("end_index")
    if type(end) is int and 0 < end <= len(text) and (start is None or (type(start) is int and 0 <= start < end)):
        return True
    hint = citation.get("fallback_end_index")
    # The stream position helps only inside the text: at its end it would
    # bind the source to the last sentence, whatever that says.
    return type(hint) is int and 0 < hint < len(text)


def cited_claim(text, citation):
    """The answer sentence a citation supports, as plain text, or ""."""
    text = text or ""
    if not _anchored(text, citation):
        return ""
    end = citation_end(text, citation)
    head = text[:end]
    stop = len(head.rstrip()) - 1  # the sentence's own end is not its start
    start = 0
    for match in _SENTENCE_END.finditer(head, 0, max(0, stop)):
        start = match.end()
    claim = _MARKDOWN_LINK.sub(r"\1", head[start:])
    claim = _EMPTY_BRACKETS.sub("", _BARE_URL.sub("", claim))
    claim = _LEADING_MARKER.sub("", " ".join(claim.split())).strip()
    if len(claim) > CLAIM_CHARS:
        # The citation marks the sentence's end; keep the part next to it.
        tail = claim[-CLAIM_CHARS:]
        space = tail.find(" ")
        claim = "…" + (tail[space + 1:] if 0 <= space < CLAIM_CHARS // 5 else tail)
    return claim


def answer_citations(text, citations):
    """Per canonical URL of one answer: its longest source text and its claims."""
    cited = {}
    for citation in citations or []:
        if not isinstance(citation, dict):
            continue
        url = canonical_source_url(citation.get("url"))
        if not url:
            continue
        entry = cited.setdefault(url, {"content": "", "claims": []})
        content = citation.get("content")
        if isinstance(content, str) and len(content.strip()) > len(entry["content"]):
            entry["content"] = content.strip()
        claim = cited_claim(text, citation)
        if claim and claim not in entry["claims"]:
            entry["claims"].append(claim)
    return cited


@dataclass
class PooledSource:
    """One cited source of the turn, across all answers that cite it."""
    url: str
    title: str
    question: str
    order: int
    families: set = field(default_factory=set)
    claims: list = field(default_factory=list)
    content: str = ""
    page: dict | None = None

    def text(self):
        """The text excerpts come from, its origin, and a publication date."""
        if len(self.content) >= MIN_SEARCH_TEXT_CHARS:
            return self.content, "search", ""
        body = str((self.page or {}).get("text") or "").strip()
        if body:
            return body, "page", _published(self.page)
        return self.content, "search" if self.content else "none", ""


def _published(document):
    for item in (document or {}).get("dates") or []:
        if "published" in str(item.get("origin") or "").lower() and item.get("value"):
            return str(item["value"])[:40]
    return ""


def source_entries(pooled, budget=EXCERPT_BUDGET_CHARS):
    """The answer step's source list: most cited first, excerpts within budget.

    Every source stays listed and citable; one without text or beyond the
    budget is listed without excerpt. Excerpts are original spans selected
    for the claims the answers make with the source (select_passages), never
    model-written summaries."""
    entries, remaining, lead = [], budget, 0
    for source in sorted(pooled, key=lambda item: (-len(item.families), item.order)):
        entry = {"url": source.url, "title": source.title, "cited_by": len(source.families)}
        body, _, published = source.text()
        claims = source.claims[:CLAIMS_PER_SOURCE]
        claim_chars = sum(len(claim) for claim in claims)
        allowance = min(LEAD_EXCERPT_CHARS if lead < LEAD_SOURCES else EXCERPT_CHARS, remaining - claim_chars)
        if body and allowance >= MIN_EXCERPT_CHARS:
            excerpt = select_passages({"text": body}, [{"claim": claim} for claim in source.claims],
                                      source.question, allowance)["text"].strip()
            if excerpt:
                if claims:
                    entry["supports"] = claims
                entry["excerpt"] = excerpt
                if published:
                    entry["published"] = published
                remaining -= len(excerpt) + claim_chars
                lead += 1
        entries.append(entry)
    return entries


class SourceEvidence:
    """One turn's cited source texts and page fetches (thread-safe)."""

    def __init__(self, *, fetch=None, limits=None):
        self._fetch = fetch or fetch_document
        self._limits = limits
        self._lock = threading.Lock()
        self._answers = {}
        self._pages = {}
        self._closed = False

    def record(self, comparison_id, provider, text, citations):
        """Keep one completed answer's citations and start its page fetches.

        Called before the answer joins the comparison, so the answer step
        never sees an answer without its sources' text."""
        cited = answer_citations(text, citations)
        for entry in cited.values():
            found = len(entry["content"]) >= MIN_SEARCH_TEXT_CHARS
            # Per family: how often search delivers usable source text.
            record_metric("agent_source_evidence", f"{provider}:{'search_text' if found else 'no_search_text'}",
                          processed=1)
        with self._lock:
            self._answers[(comparison_id, provider)] = cited
        self._start_pages([url for url, entry in cited.items()
                           if len(entry["content"]) < MIN_SEARCH_TEXT_CHARS][:PAGE_FETCHES_PER_ANSWER])

    def _start_pages(self, urls):
        with self._lock:
            for url in urls:
                if self._closed or url in self._pages or len(self._pages) >= PAGE_FETCHES_PER_TURN:
                    continue
                if self._limits is None:
                    from app.services.source_verification import Limits
                    self._limits = Limits.configured()
                self._pages[url] = _pages.submit(self._fetch, url, self._limits)

    def collect(self, comparisons, *, wait_seconds=PAGE_WAIT_SECONDS, check=None):
        """Pool the sources of the answers in the synthesis, with their text.

        Waits up to ``wait_seconds`` for page fetches still running; ``check``
        raises when the turn stops."""
        with self._lock:
            answers = dict(self._answers)
        pooled = {}
        for comparison in comparisons:
            for answer in comparison.get("answers") or []:
                if answer.get("late"):
                    continue
                cited = answers.get((comparison.get("id"), answer.get("provider")), {})
                for source in answer.get("sources") or []:
                    key = canonical_source_url(source.get("url")) if isinstance(source, dict) else ""
                    if not key:
                        continue
                    item = pooled.get(key)
                    if item is None:
                        item = pooled[key] = PooledSource(
                            url=str(source["url"]), title=str(source.get("title") or ""),
                            question=str(comparison.get("question") or ""), order=len(pooled))
                    item.families.add(answer.get("provider"))
                    entry = cited.get(key) or {}
                    item.claims.extend(c for c in entry.get("claims", []) if c not in item.claims)
                    if len(entry.get("content", "")) > len(item.content):
                        item.content = entry["content"]
        missing = sorted((key for key, item in pooled.items() if len(item.content) < MIN_SEARCH_TEXT_CHARS),
                         key=lambda key: (-len(pooled[key].families), pooled[key].order))
        # Sources past each answer's first few were not fetched on arrival:
        # the most cited of them now, within the turn's bound.
        self._start_pages(missing)
        with self._lock:
            futures = {key: self._pages[key] for key in missing if key in self._pages}
        self._wait(list(futures.values()), wait_seconds, check)
        for key, future in futures.items():
            if future.done() and not future.cancelled() and future.exception() is None:
                pooled[key].page = future.result()
        for item in pooled.values():
            record_metric("agent_source_evidence", f"text:{item.text()[1]}", processed=1)
        return list(pooled.values())

    @staticmethod
    def _wait(futures, seconds, check):
        deadline = time.monotonic() + max(0.0, seconds)
        pending = [future for future in futures if not future.done()]
        while pending:
            if check:
                check()
            left = deadline - time.monotonic()
            if left <= 0:
                record_metric("agent_source_evidence", "page_wait", outcome="timeout", processed=len(pending))
                return
            pending = list(wait(pending, timeout=min(.2, left)).not_done)

    def close(self):
        """Turn end: page fetches that have not started never start."""
        with self._lock:
            self._closed = True
            for future in self._pages.values():
                future.cancel()
