"""The links of a fixed agent answer that lead nowhere.

Models write addresses they never retrieved: one answer of 2026-10-26 linked
three articles that do not exist, none of them among its search results. Most
links the app did not see retrieved are real all the same (an answer's own
knowledge, a provider's search that sends no hits to the app), so a link is
never judged by where it came from. The app opens each link of the answer once,
as a reader's click would, and keeps only those the site itself answers with
"no such page" (404, 410). Anything else (403 to bots, a sign-in wall, a
timeout, a name public DNS does not know, which may be the user's router or
intranet) is no finding.

The request is anonymous and from the server, so what is private looks
missing there: code hosts answer 404 for a private repository
(REPO_HOSTS), which counts only inside a repository that is public. Links
the user wrote are never opened: a pasted link may act when opened
(unsubscribe, sign-in, a tracker) and is the user's own anyway.

Runs beside the hand-over and the reviewers' final round
(DelegationLoop._finish_merged); the result is part of the turn's review
(ComparisonTools.links), marked in the answer by sources.js
markMissingAnswerLinks. Never in chats with Google data: an address written
from a mail would be opened without anyone's click."""
from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore
from urllib.parse import urljoin, urlsplit

import httpx

from app.core.observability import record_metric, safe_exception
from app.services.agent_read_source import _safe_url, text_urls, url_key
from app.services.source_catalog import _prose_parts
from app.services.source_documents import pinned_target

LINKS_MAX = 12
CHECK_SECONDS = 6.0
LINK_SECONDS = 4.0
PARALLEL = 3
REDIRECTS = 4
GONE = frozenset({404, 410})
# Host of a link -> host of its repository page.
REPO_HOSTS = {"github.com": "github.com", "raw.githubusercontent.com": "github.com", "gitlab.com": "gitlab.com"}
USER_AGENT = "consens.io link check/1"
# DNS lookups of their own: the four that source pages and pictures share
# (source_documents) refuse a fifth at once, and a slow lookup holds its slot
# past every timeout. A busy lookup here is a link left unchecked.
_lookups = (ThreadPoolExecutor(max_workers=6, thread_name_prefix="link-dns"), BoundedSemaphore(6))
_DESTINATION = re.compile(r"\]\(\s*<?(?=https?://)", re.IGNORECASE)


def _destinations(text):
    """Markdown link destinations ("[label](url)") as written, parentheses
    balanced, and the text without them for the bare URLs (text_urls ends a
    URL at a quote, which a destination may hold: "Hitchhiker's_Guide")."""
    found, rest, cursor = [], [], 0
    for match in _DESTINATION.finditer(text):
        if match.start() < cursor:
            continue
        start = end = match.end()
        depth = 0
        while end < len(text) and not text[end].isspace() and text[end] != ">":
            if text[end] == "(":
                depth += 1
            elif text[end] == ")":
                if not depth:
                    break
                depth -= 1
            end += 1
        found.append(text[start:end])
        rest.append(text[cursor:start])
        cursor = end
    rest.append(text[cursor:])
    return found, "".join(rest)


def answer_links(text, skip=()):
    """The answer's links outside code, each once, at most LINKS_MAX; none
    whose url_key is in ``skip``."""
    found, seen = [], set(skip)
    for prose, part in _prose_parts(text or ""):
        if not prose:
            continue
        destinations, rest = _destinations(part)
        for url in [*(d for d in destinations if _safe_url(d)), *text_urls(rest)]:
            key = url_key(url)
            if key and key not in seen:
                seen.add(key)
                found.append(url)
                if len(found) >= LINKS_MAX:
                    return found
    return found


def _repository(url):
    """The page of the repository a code-host link lies in; None for another
    host, "" when the link is no page inside a repository (the repository
    itself, its owner: private or invented look the same there)."""
    parts = urlsplit(url)
    host = REPO_HOSTS.get((parts.hostname or "").removeprefix("www."))
    if host is None:
        return None
    segments = [s for s in parts.path.split("/") if s]
    if host == "gitlab.com":
        # Groups nest on GitLab: only "/-/" tells where the project ends.
        root = segments[:segments.index("-")] if "-" in segments else []
    else:
        root = segments[:2] if len(segments) > 2 else []
    return f"https://{host}/" + "/".join(root) if len(root) >= 2 else ""


async def _status(client, url):
    """The status where ``url`` ends after its redirects, every hop's address
    checked (pinned_target: public, no rebinding); None after too many."""
    for _ in range(REDIRECTS + 1):
        target, host, hostname = await pinned_target(url, lookups=_lookups)
        async with client.stream("GET", target, headers={"Host": host, "User-Agent": USER_AGENT},
                                 extensions={"sni_hostname": hostname}) as response:
            location = response.headers.get("location")
            if response.status_code in (301, 302, 303, 307, 308) and location:
                url = urljoin(url, location)
                continue
            return response.status_code
    return None


async def link_gone(url, *, transport=None):
    """404 or 410 when the site says the page does not exist, else None."""
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=LINK_SECONDS,
                                 transport=transport) as client:
        status = await _status(client, url)
        if status not in GONE:
            return None
        repository = _repository(url)
        if repository == "" or (repository and await _status(client, repository) != 200):
            return None
        return status


class LinkCheck:
    """One answer's links, checked on a thread of their own from ``start``.

    ``retrieved(url)``: whether the app saw the page during the message
    (search results, pages read, the chat's sources); kept with each finding,
    so the saved reviews tell an invented address from a page that went
    away. ``skip``: url_keys never opened (the user's links)."""

    def __init__(self, text, retrieved=None, *, skip=(), gone=None, clock=time.monotonic):
        self.links = answer_links(text, skip)
        self.retrieved = retrieved or (lambda url: False)
        self.gone = gone or link_gone
        self.clock = clock
        self.found = None
        self.thread = None
        self.deadline = None

    def start(self):
        if not self.links:
            return self
        self.deadline = self.clock() + CHECK_SECONDS
        self.thread = threading.Thread(target=self._run, name="agent-answer-links", daemon=True)
        self.thread.start()
        return self

    def result(self, wait=True):
        """{"checked", "missing": [{url, status, retrieved}]} once done, None
        before or without links. ``wait``: until the check's own deadline."""
        if self.thread is None:
            return None
        if wait:
            self.thread.join(max(0., self.deadline - self.clock()) + 0.5)
        return self.found

    def _run(self):
        started = self.clock()
        try:
            results = asyncio.run(self._check_all())
        except Exception as exc:
            logging.info("Agent answer links not checked category=%s", safe_exception(exc))
            return
        missing = [{"url": url, "status": status, "retrieved": bool(self.retrieved(url))}
                   for url, status in results if status is not None]
        self.found = {"checked": len(results), "missing": missing}
        invented = sum(not item["retrieved"] for item in missing)
        record_metric("agent_answer_links", "check", duration_ms=(self.clock() - started) * 1000,
                      processed=len(results))
        if missing:
            record_metric("agent_answer_links", "missing", processed=len(missing))
            logging.info("Agent answer links missing=%d of %d not_retrieved=%d", len(missing), len(results), invented)

    async def _check_all(self):
        slots = asyncio.Semaphore(PARALLEL)

        async def one(url):
            async with slots:
                try:
                    return url, await asyncio.wait_for(self.gone(url), LINK_SECONDS)
                except Exception:
                    return url, None

        tasks = [asyncio.ensure_future(one(url)) for url in self.links]
        done, pending = await asyncio.wait(tasks, timeout=CHECK_SECONDS)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        # In the answer's order.
        return [task.result() for task in tasks if task in done]
