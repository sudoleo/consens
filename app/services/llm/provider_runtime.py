"""Shared transport budgets and cooperative cancellation for LLM providers.

Provider calls deliberately have no automatic transport retry. A logical
operation claim authorizes one paid call; schema-level fallbacks and retries
remain explicit in the consensus layer and therefore auditable.
"""

from __future__ import annotations

from contextlib import contextmanager
import asyncio
import functools
import inspect
import logging
import os
import threading
import time
from typing import Callable, Iterator

import httpx
import openai


def _bounded_env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


PROVIDER_CONNECT_TIMEOUT_SECONDS = _bounded_env_float(
    "PROVIDER_CONNECT_TIMEOUT_SECONDS", 10.0, 1.0, 30.0
)
PROVIDER_READ_TIMEOUT_SECONDS = _bounded_env_float(
    "PROVIDER_READ_TIMEOUT_SECONDS", 120.0, 10.0, 300.0
)
PROVIDER_KEY_CHECK_TIMEOUT_SECONDS = 15.0
ANALYSIS_TIMEOUT_SECONDS = _bounded_env_float("ANALYSIS_TIMEOUT_SECONDS", 180.0, 10.0, 600.0)
ANALYSIS_MAX_CALLS = int(_bounded_env_float("ANALYSIS_MAX_CALLS", 8, 3, 12))


def provider_http_timeout(read_seconds: float | None = None) -> tuple[float, float]:
    read_budget = float(read_seconds or PROVIDER_READ_TIMEOUT_SECONDS)
    return (min(PROVIDER_CONNECT_TIMEOUT_SECONDS, read_budget), read_budget)


PROVIDER_HTTP_TIMEOUT = provider_http_timeout()
PROVIDER_SDK_MAX_RETRIES = 0


def openai_client(
    *,
    api_key: str,
    base_url: str | None = None,
    timeout_seconds: float | None = None,
) -> openai.OpenAI:
    """Build an OpenAI-compatible client with explicit, shared budgets."""
    read_budget = float(timeout_seconds or PROVIDER_READ_TIMEOUT_SECONDS)
    kwargs = {
        "api_key": api_key,
        "timeout": httpx.Timeout(
            read_budget,
            connect=min(PROVIDER_CONNECT_TIMEOUT_SECONDS, read_budget),
        ),
        "max_retries": PROVIDER_SDK_MAX_RETRIES,
    }
    if base_url:
        kwargs["base_url"] = base_url
    return openai.OpenAI(**kwargs)


class ProviderCancelled(Exception):
    """Raised inside a provider producer after its downstream client left."""


class ProviderCancellation:
    """Thread-safe cancellation signal that closes active streaming resources."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._closers: set[Callable[[], None]] = set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise ProviderCancelled("provider stream cancelled")

    def register(self, resource) -> Callable[[], None]:
        close = getattr(resource, "close", None)
        if not callable(close):
            return lambda: None
        with self._lock:
            if self.cancelled:
                close_now = True
            else:
                self._closers.add(close)
                close_now = False
        if close_now:
            _close_safely(close)

        def unregister() -> None:
            with self._lock:
                self._closers.discard(close)

        return unregister

    def cancel(self) -> None:
        self._event.set()
        with self._lock:
            closers = tuple(self._closers)
            self._closers.clear()
        for close in closers:
            _close_safely(close)

    def close(self) -> None:
        """Allow a child cancellation scope to register with its parent."""
        self.cancel()


def _close_safely(close: Callable[[], None]) -> None:
    try:
        close()
    except Exception:
        # Cancellation is best effort. The producer still observes the event.
        pass


_thread_context = threading.local()


@contextmanager
def bind_provider_cancellation(
    cancellation: ProviderCancellation,
) -> Iterator[ProviderCancellation]:
    """Bindet die Cancellation an DIESEN Thread.

    Invariante: Ein Producer, der hier gebunden wird, muss vollstaendig auf
    einem Thread laufen. Ein Generator, den Starlette ueber
    iterate_in_threadpool zieht, erfuellt das nicht (jedes next() kann auf
    einem anderen Worker landen) und wuerde fremde Cancellations sehen --
    solche Producer gehoeren in den Pump-Thread von iter_sse_with_keepalive.
    """
    previous = getattr(_thread_context, "cancellation", None)
    _thread_context.cancellation = cancellation
    try:
        yield cancellation
    finally:
        _thread_context.cancellation = previous


def current_provider_cancellation() -> ProviderCancellation | None:
    return getattr(_thread_context, "cancellation", None)


def raise_if_provider_cancelled() -> None:
    cancellation = current_provider_cancellation()
    if cancellation:
        cancellation.raise_if_cancelled()
    budget = current_analysis_budget()
    if budget:
        budget.check()


@contextmanager
def managed_provider_resource(resource):
    """Register a response/SDK stream for cancellation and always close it."""
    cancellation = current_provider_cancellation()
    unregister = cancellation.register(resource) if cancellation else (lambda: None)
    try:
        if cancellation:
            cancellation.raise_if_cancelled()
        yield resource
    finally:
        unregister()
        close = getattr(resource, "close", None)
        if callable(close):
            _close_safely(close)


class AnalysisBudgetExceeded(TimeoutError):
    """Content-free terminal limit; never a reason to retry a paid call."""


class AnalysisBudget:
    def __init__(self, seconds=None, max_calls=None):
        self.started = time.monotonic()
        self.deadline = self.started + (ANALYSIS_TIMEOUT_SECONDS if seconds is None else seconds)
        self.max_calls = ANALYSIS_MAX_CALLS if max_calls is None else max_calls
        self.calls = 0
        self.lock = threading.Lock()

    def check(self):
        if time.monotonic() >= self.deadline:
            raise AnalysisBudgetExceeded("analysis deadline exceeded")

    def consume(self):
        with self.lock:
            self.check()
            if self.calls >= self.max_calls:
                raise AnalysisBudgetExceeded("analysis call budget exhausted")
            self.calls += 1

    def snapshot(self):
        return {"attempts": self.calls, "duration_ms": int((time.monotonic() - self.started) * 1000)}


def current_analysis_budget():
    return getattr(_thread_context, "analysis_budget", None)


@contextmanager
def bind_analysis_budget(budget):
    previous = current_analysis_budget()
    _thread_context.analysis_budget = budget
    try:
        yield budget
    finally:
        _thread_context.analysis_budget = previous


@contextmanager
def analysis_budget_scope():
    """One budget from synthesis through both judges, shared across threads."""
    existing = current_analysis_budget()
    if existing is not None:
        yield existing
        return
    budget = AnalysisBudget()
    cancellation = ProviderCancellation()
    # Parent disconnect propagates to both roles. Async socket guards enforce
    # the deadline without allocating a timer thread per analysis.
    parent = current_provider_cancellation()
    unregister = parent.register(cancellation) if parent else lambda: None
    try:
        with bind_analysis_budget(budget), bind_provider_cancellation(cancellation):
            yield budget
    finally:
        unregister()
        cancellation.cancel()
        logging.info("Analysis completed attempts=%d duration_ms=%d", budget.calls, budget.snapshot()["duration_ms"])


def analysis_budgeted(function):
    # Generator scope must live across next() calls, not only their creation.
    if inspect.isgeneratorfunction(function):
        @functools.wraps(function)
        def stream(*args, **kwargs):
            with analysis_budget_scope():
                yield from function(*args, **kwargs)
        return stream
    @functools.wraps(function)
    def call(*args, **kwargs):
        with analysis_budget_scope():
            return function(*args, **kwargs)
    return call


def analysis_http_timeout():
    budget = current_analysis_budget()
    if budget is None:
        return PROVIDER_HTTP_TIMEOUT
    budget.check()
    return provider_http_timeout(min(PROVIDER_READ_TIMEOUT_SECONDS, max(0.01, budget.deadline - time.monotonic())))


def claim_analysis_call():
    raise_if_provider_cancelled()
    budget = current_analysis_budget()
    if budget:
        budget.consume()


async def _guard_provider_io(awaitable, cancellation, budget):
    task = asyncio.ensure_future(awaitable)
    try:
        while True:
            if cancellation:
                cancellation.raise_if_cancelled()
            if budget:
                budget.check()
            done, _ = await asyncio.wait({task}, timeout=0.05)
            if done:
                return task.result()
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def cancellable_post_json(url, *, json, headers):
    """Cancel the actual socket task even while waiting for response headers.

    Runs only in synchronous provider workers, never on FastAPI's event loop.
    No transport retries. Polling monitors cancellation, not provider results.
    """
    cancellation = current_provider_cancellation()
    budget = current_analysis_budget()
    connect, read = analysis_http_timeout()

    async def request():
        async with httpx.AsyncClient(timeout=httpx.Timeout(read, connect=connect)) as client:
            response = await _guard_provider_io(client.post(url, json=json, headers=headers), cancellation, budget)
            # Keep the existing content-free HTTP status contract.
            if response.status_code >= 400:
                from app.services.llm.engines import _raise_provider_http_status
                _raise_provider_http_status(response)
            return response.json()
    return asyncio.run(request())


def cancellable_sse_lines(url, *, json, headers):
    """Drive async socket reads on the existing synchronous SSE worker.

    A deadline/disconnect cancels header reads and idle body reads alike; no
    extra producer thread, abandoned request or hidden retry is introduced.
    """
    cancellation = current_provider_cancellation()
    budget = current_analysis_budget()
    connect, read = analysis_http_timeout()
    loop = asyncio.new_event_loop()
    client = httpx.AsyncClient(timeout=httpx.Timeout(read, connect=connect))
    response = None

    def guarded(awaitable):
        return _guard_provider_io(awaitable, cancellation, budget)

    try:
        request = client.build_request("POST", url, json=json, headers=headers)
        response = loop.run_until_complete(guarded(client.send(request, stream=True)))
        if response.status_code >= 400:
            from app.services.llm.engines import _raise_provider_http_status
            _raise_provider_http_status(response)
        lines = response.aiter_lines()
        while True:
            try:
                line = loop.run_until_complete(guarded(lines.__anext__()))
            except StopAsyncIteration:
                return
            yield line
    finally:
        try:
            if response is not None:
                loop.run_until_complete(response.aclose())
        finally:
            loop.run_until_complete(client.aclose())
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
