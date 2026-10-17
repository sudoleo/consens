"""Coverage windows of the Agent's answer while it is still being written.

The Coverage judge checks every sentence of the answer against the model
answers. It used to start only once the answer was finished: for real users
it then took 25 s (median) and up to 99 s after the last word (14 days to
2026-10-17), and a check that arrives that late is rarely seen. Now every
window of AGENT_COVERAGE_WINDOW sentences starts as soon as those sentences
are settled (consensus_engine.settled_sentence_count). The check of the
finished answer collects these windows and asks only the rest
(consensus_engine._run_coverage_with_prefetch).

The windows run through the same judge transport as the check itself
(ComparisonTools.judge_transport): metered, stopped with the turn, and in a
chat with Google data routed like every other call of that chat.

Since 2026-10-18 the page also sees them early: once the answer is fixed,
every collected or finished window becomes provisional marks
(ComparisonTools.preview_coverage, event ``coverage_preview``) while the
Differences judge still runs; the final review replaces them.
"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait as wait_for
from contextvars import copy_context
from functools import partial
import hashlib
import json
import logging
import threading

from app.core import config as cfg
from app.core.observability import safe_exception
from app.services.llm.provider_runtime import ProviderCancellation, bind_provider_cancellation
from app.services.llm.task_transport import bind_task_transport


def judge_basis(answers: dict, question: str, read_sources) -> str:
    """What a window's verdicts rest on; a check with another basis cannot use them."""
    pages = [(str(item.get("url") or ""), str(item.get("text") or "")) for item in read_sources or ()]
    encoded = json.dumps([sorted(answers.items()), question or "", pages], ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class _ComparisonWindows:
    """The windows one comparison's check can collect (engine protocol)."""

    def __init__(self, windows):
        self._windows = windows

    def launched(self) -> dict:
        """Sentence id -> the exact sentence a window is checking."""
        sentences = {}
        for launched, _ in self._windows:
            sentences.update(launched)
        return sentences

    def results(self):
        """Each window's result as it finishes, the first done first (its
        marks reach the page at once); a failed window yields nothing.

        Waits only as long as the check that collects them may run: once its
        own stop fires (the check's deadline, a user stop), it takes what is
        there and leaves the rest to ComparisonTools.judge's cleanup."""
        from app.services.llm.provider_runtime import current_provider_cancellation
        stop = current_provider_cancellation()
        order = [future for _, future in self._windows]
        pending = set(order)
        while pending:
            if stop is not None and stop.cancelled:
                return
            done, pending = wait_for(pending, timeout=.25, return_when=FIRST_COMPLETED)
            for future in (f for f in order if f in done):
                try:
                    result = future.result()
                except Exception as exc:
                    logging.info("Early coverage window ended without a result category=%s", safe_exception(exc))
                    continue
                if result:
                    yield result


class CoveragePrefetch:
    """Starts Coverage windows of the visible answer while it streams."""

    def __init__(self, tools):
        self.tools = tools
        self.lock = threading.Lock()
        self.pool = None
        self.stop = None
        self._unlink = lambda: None
        # Comparison id -> (basis, [(launched sentences, future), ...]).
        self.windows = {}
        self.started = 0
        # How much of the text has been looked at: a sentence can only settle
        # with a new line break, so most deltas cost nothing.
        self.scanned = 0

    def _enabled(self):
        tools = self.tools
        # Chat turns only: a bounded run caps its judge calls
        # (ComparisonTools.judge_transport), and early windows must not use them up.
        return (bool(tools.comparisons) and not tools.text and tools.preferences.judges != "off"
                and getattr(tools.loop.policy, "account_budget_only", False))

    def update(self, text: str) -> None:
        """The answer as far as it is visible; starts every window that is complete."""
        from app.services.llm import coverage_judge as coverage
        from app.services.llm.consensus_engine import (AGENT_COVERAGE_WINDOW, CHAT_MAX_CONSENSUS_SENTENCES,
                                                       _enumerate_consensus_sentences, settled_sentence_count)
        with self.lock:
            fresh = "\n" in text[self.scanned:] if len(text) >= self.scanned else True
            self.scanned = len(text)
            if not fresh or not self._enabled():
                return
            settled = settled_sentence_count(text)
            if settled - self.started < AGENT_COVERAGE_WINDOW:
                return
            _, sentences = _enumerate_consensus_sentences(text, limit=CHAT_MAX_CONSENSUS_SENTENCES)
            while settled - self.started >= AGENT_COVERAGE_WINDOW:
                numbers = range(self.started + 1, self.started + AGENT_COVERAGE_WINDOW + 1)
                launched = {coverage.sentence_id(n): sentences[n - 1] for n in numbers}
                for comparison in list(self.tools.comparisons):
                    self._launch(comparison, text, launched)
                self.started += AGENT_COVERAGE_WINDOW

    def _launch(self, comparison, text, launched):
        tools = self.tools
        with tools.lock:
            checked = [a for a in comparison["answers"] if not a.get("late")]
        if len(checked) < 2:
            return
        answers = {cfg.provider_label(a["provider"]): a["text"] for a in checked}
        read_sources = tools.reader.judge_sources() if tools.reader is not None else None
        basis = judge_basis(answers, comparison["question"], read_sources)
        known, windows = self.windows.setdefault(comparison["id"], (basis, []))
        if known != basis:
            # The comparison changed under the answer: the final check asks again.
            return
        if self.pool is None:
            from app.services.agent_comparison import JUDGE_PARALLEL
            self.pool = ThreadPoolExecutor(max_workers=JUDGE_PARALLEL, thread_name_prefix="coverage-prefetch")
        if self.stop is None:
            self.stop = ProviderCancellation()
            self._unlink = tools.loop.cancellation.register(self.stop) or (lambda: None)
        transport = (partial(tools.judge_transport, subject="passage_answer")
                     if tools.passage is not None else tools.judge_transport)
        stop, reference, api_key = self.stop, tools._judge_reference(), tools.loop.api_key
        ids = list(launched)

        def work():
            from app.services.llm.consensus_engine import prefetch_coverage_window
            with bind_task_transport(transport), bind_provider_cancellation(stop):
                return prefetch_coverage_window(answers, text, ids, {"OpenRouter": api_key}, reference,
                                                resolved_question=comparison["question"], read_sources=read_sources)

        windows.append((launched, self.pool.submit(copy_context().run, work)))

    def for_comparison(self, comparison, answers: dict, read_sources):
        """The windows the check of ``comparison`` may collect, or None."""
        with self.lock:
            basis, windows = self.windows.get(comparison["id"], (None, []))
        if not windows or basis != judge_basis(answers, comparison["question"], read_sources):
            return None
        return _ComparisonWindows(list(windows))

    def discard(self) -> None:
        """The visible text was no answer after all: stop its windows.
        Windows still queued never start (no empty judge row)."""
        with self.lock:
            self._stop()
            for _, windows in self.windows.values():
                for _, future in windows:
                    future.cancel()
            self.windows, self.started, self.scanned = {}, 0, 0

    def close(self, *, wait: bool = False) -> None:
        """Stop what still runs; queued windows never start. ``wait`` (run
        end, ComparisonTools.close): until every started window's paid step
        has ended, so the run settles it before it finishes (DelegationLoop.run)."""
        with self.lock:
            self._stop()
            pool, self.pool = self.pool, None
        if pool is not None:
            pool.shutdown(wait=wait, cancel_futures=True)

    def _stop(self):
        if self.stop is not None:
            self.stop.cancel()
            self._unlink()
            self.stop, self._unlink = None, (lambda: None)
