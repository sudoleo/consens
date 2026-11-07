"""The links of a fixed agent answer that lead nowhere.

Models write addresses they never retrieved: one answer of 2026-10-26 linked
three articles that do not exist, none of them among its search results. Most
links the app did not see retrieved are real all the same (an answer's own
knowledge, a provider's search that sends no hits to the app), so a link is
never judged by where it came from. The app opens each link of the answer once,
as a reader's click would, and keeps only those the site itself answers with
"no such page" (404, 410) or whose host does not exist. Anything else (403 to
bots, a sign-in wall, a timeout) is no finding.

Runs beside the hand-over and the reviewers' final round
(DelegationLoop._finish_merged); the result is part of the turn's review
(ComparisonTools.links), marked in the answer by sources.js
markMissingAnswerLinks. Never in chats with Google data: an address written
from a mail would be fetched without anyone's click."""
from __future__ import annotations

import asyncio
import logging
import socket
import threading
import time
from urllib.parse import urljoin

import httpx

from app.core.observability import record_metric, safe_exception
from app.services.agent_read_source import text_urls, url_key
from app.services.source_catalog import _prose_parts
from app.services.source_documents import pinned_target

LINKS_MAX = 12
CHECK_SECONDS = 6.0
LINK_SECONDS = 4.0
# source_documents.pinned_target allows four DNS lookups at once in the
# process; read_source and the comparison answers share them.
PARALLEL = 3
REDIRECTS = 4
GONE = frozenset({404, 410})
USER_AGENT = "consens.io link check/1"


def answer_links(text):
    """The answer's links (text_urls) outside code, each once, at most LINKS_MAX."""
    found, seen = [], set()
    for prose, part in _prose_parts(text or ""):
        if not prose:
            continue
        for url in text_urls(part):
            key = url_key(url)
            if key not in seen:
                seen.add(key)
                found.append(url)
                if len(found) >= LINKS_MAX:
                    return found
    return found


async def link_gone(url, *, transport=None):
    """404 or 410 when the site says the page does not exist, "no_host" when
    the host does not exist, else None. Every hop's address is checked
    (pinned_target: public, no rebinding)."""
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=LINK_SECONDS,
                                 transport=transport) as client:
        for _ in range(REDIRECTS + 1):
            try:
                target, host, hostname = await pinned_target(url)
            except socket.gaierror as exc:
                return "no_host" if exc.errno == socket.EAI_NONAME else None
            async with client.stream("GET", target, headers={"Host": host, "User-Agent": USER_AGENT},
                                     extensions={"sni_hostname": hostname}) as response:
                location = response.headers.get("location")
                if response.status_code in (301, 302, 303, 307, 308) and location:
                    url = urljoin(url, location)
                    continue
                return response.status_code if response.status_code in GONE else None
    return None


class LinkCheck:
    """One answer's links, checked on a thread of their own from ``start``.

    ``retrieved(url)``: whether the app saw the page during the message
    (search results, pages read, the chat's sources, the user's links); kept
    with each finding, so the saved reviews tell an invented address from a
    page that went away."""

    def __init__(self, text, retrieved=None, *, gone=None, clock=time.monotonic):
        self.links = answer_links(text)
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
