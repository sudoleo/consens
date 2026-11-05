"""Shared transport budgets and cooperative cancellation for LLM providers.

Provider calls deliberately have no automatic transport retry. A logical
operation claim authorizes one paid call; schema-level fallbacks and retries
remain explicit in the consensus layer and therefore auditable.
"""

from __future__ import annotations

from contextlib import contextmanager
import asyncio
import concurrent.futures
import functools
import inspect
import logging
import os
import threading
import time
from typing import Callable, Iterator, NamedTuple

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
    def __init__(self, seconds=None, max_calls=None, *, unlimited=False, run=None):
        self.started = time.monotonic()
        self.deadline = float("inf") if unlimited else self.started + (ANALYSIS_TIMEOUT_SECONDS if seconds is None else seconds)
        self.max_calls = float("inf") if unlimited else ANALYSIS_MAX_CALLS if max_calls is None else max_calls
        self.calls = 0
        self.lock = threading.Lock()
        # A run of phases (analysis_run_scope) gives each phase its own budget;
        # ``run`` is the run a phase belongs to, ``phased`` marks the run itself.
        self.run = run
        self.phased = False
        self.phase_calls = 0

    def check(self):
        if time.monotonic() >= self.deadline:
            raise AnalysisBudgetExceeded("analysis deadline exceeded")

    def consume(self):
        with self.lock:
            self.check()
            if self.calls >= self.max_calls:
                raise AnalysisBudgetExceeded("analysis call budget exhausted")
            self.calls += 1
        if self.run is not None:
            with self.run.lock:
                self.run.phase_calls += 1

    def snapshot(self):
        """Paid attempts and duration of the whole analysis, all phases included."""
        if self.run is not None:
            return self.run.snapshot()
        return {"attempts": self.calls + self.phase_calls,
                "duration_ms": int((time.monotonic() - self.started) * 1000)}


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
def _bound_analysis_scope(budget):
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
        if budget.run is None:
            snapshot = budget.snapshot()
            logging.info("Analysis completed attempts=%d duration_ms=%d", snapshot["attempts"], snapshot["duration_ms"])


@contextmanager
def analysis_budget_scope(seconds=None, max_calls=None):
    """One budget for an analysis step, shared across its threads.

    An existing budget is reused (an Agent's, or the step's caller's). Inside
    analysis_run_scope the step is a phase and opens its own budget instead."""
    existing = current_analysis_budget()
    if existing is not None and not existing.phased:
        yield existing
        return
    with _bound_analysis_scope(AnalysisBudget(seconds, max_calls, run=existing)) as budget:
        yield budget


@contextmanager
def analysis_run_scope():
    """A Consensus run of phases: synthesis, then both judges (audit C3).

    Each budgeted phase gets its own deadline and call count, so a slow
    synthesis never uses up the judges' time. The run carries the shared
    cancellation, totals every phase for ``analysis_runtime``, and bounds
    unbudgeted work inside it like a single default budget. An existing budget
    (an Agent's) keeps governing every phase instead."""
    existing = current_analysis_budget()
    if existing is not None:
        yield existing
        return
    run = AnalysisBudget()
    run.phased = True
    with _bound_analysis_scope(run):
        yield run


def _scoped(function, scope):
    # Generator scope must live across next() calls, not only their creation.
    if inspect.isgeneratorfunction(function):
        @functools.wraps(function)
        def stream(*args, **kwargs):
            with scope():
                yield from function(*args, **kwargs)
        return stream
    @functools.wraps(function)
    def call(*args, **kwargs):
        with scope():
            return function(*args, **kwargs)
    return call


def analysis_budgeted(function=None, *, seconds=None, max_calls=None):
    """Runs an analysis step in analysis_budget_scope; ``seconds``/``max_calls``
    size a budget it opens (default: ANALYSIS_TIMEOUT_SECONDS/ANALYSIS_MAX_CALLS)."""
    if function is None:
        return lambda inner: analysis_budgeted(inner, seconds=seconds, max_calls=max_calls)
    return _scoped(function, lambda: analysis_budget_scope(seconds, max_calls))


def analysis_run(function):
    """Runs a whole Consensus analysis in analysis_run_scope."""
    return _scoped(function, analysis_run_scope)


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


class ProviderProgressWatchdog:
    """Bound silence, not the total duration of a productive model call."""

    def __init__(self, seconds):
        self.seconds = seconds
        self.touch()

    def touch(self):
        self.deadline = time.monotonic() + self.seconds

    def check(self):
        if time.monotonic() >= self.deadline:
            raise TimeoutError("Provider stream made no progress")


def _check_provider_io(cancellation, budget, progress=None):
    if cancellation:
        cancellation.raise_if_cancelled()
    if budget:
        budget.check()
    if progress:
        progress.check()


async def _guard_provider_io(awaitable, cancellation, budget, progress=None, *, sends_request=False):
    """Await provider I/O while honouring cancellation, deadline and progress.

    With ``sends_request`` the awaitable is the one that opens the connection
    and sends the request: a stop raised before its task ever ran is marked
    as never dispatched, so the usage meter does not charge it.
    """
    from app.services.llm.provider_dispatch import mark_not_dispatched

    task = asyncio.ensure_future(awaitable)
    task_ran = False
    try:
        while True:
            try:
                _check_provider_io(cancellation, budget, progress)
            except BaseException as exc:
                # The task only runs once this coroutine yields to the loop.
                if sends_request and not task_ran:
                    mark_not_dispatched(exc)
                raise
            task_ran = True
            done, _ = await asyncio.wait({task}, timeout=0.05)
            if done:
                return task.result()
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


# Provider HTTP runs on one event loop per process with one pooled client.
# Until 2026-11-05 every call built its own loop and AsyncClient: DNS, TCP, TLS
# and the CA bundle again for each model step (prod: 50-560 ms from request
# start to the provider's first byte). No connection limit: each concurrent
# call gets its own connection as before, so a hung request never makes
# another wait for the pool. 60 s idle stays below common server idle limits;
# httpcore also drops a pooled connection the server already closed. HTTP/1.1
# although h2 is installed: HTTP/2 would carry all parallel model streams on
# one connection, so one stall or GOAWAY would hit all of them, and the pool
# already saves the handshakes.
PROVIDER_HTTP_LIMITS = httpx.Limits(max_connections=None, max_keepalive_connections=20, keepalive_expiry=60.0)
# After ``data: [DONE]`` only the end of the chunked body is left. Reading it
# (bounded, off the caller's path) returns the connection to the pool; a
# response closed before its end takes its connection with it.
_DRAIN_LIMIT_BYTES = 65_536
_DRAIN_SECONDS = 2.0
# How often a waiting caller checks that the loop thread still runs.
_LIVENESS_SECONDS = 1.0


class _HTTPSession(NamedTuple):
    pid: int
    loop: asyncio.AbstractEventLoop
    thread: threading.Thread
    client: httpx.AsyncClient


def _serve_provider_loop(loop):
    asyncio.set_event_loop(loop)
    try:
        loop.run_forever()
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            loop.close()


async def _close_stream(response, chunks):
    try:
        if chunks is not None:
            await chunks.aclose()
    finally:
        await response.aclose()


async def _drain_and_close(response, chunks):
    async def drain():
        received = 0
        async for chunk in chunks:
            received += len(chunk)
            if received > _DRAIN_LIMIT_BYTES:
                return
    try:
        await asyncio.wait_for(drain(), _DRAIN_SECONDS)
    except Exception:
        # Only the connection's reuse is at stake; closing below drops it.
        pass
    finally:
        await _close_stream(response, chunks)


class ProviderHTTP:
    """One event loop thread and one pooled ``httpx.AsyncClient`` per process.

    Synchronous provider workers hand awaitables to the loop (``call``) and
    block on the result. ``_guard_provider_io`` runs there as it did on the
    per-call loops, so cancellation, deadline and progress still end the
    socket task itself. Started on first use; a dead loop thread or a forked
    child gets a fresh one. ``transport`` is for tests (httpx.MockTransport).
    """

    def __init__(self, transport=None):
        self._transport = transport
        self._lock = threading.Lock()
        self._session = None
        # Background releases, referenced until done (the loop holds tasks weakly).
        self._releasing = set()

    def session(self) -> _HTTPSession:
        with self._lock:
            session = self._session
            if (session is None or session.pid != os.getpid() or not session.thread.is_alive()
                    or session.loop.is_closed()):
                session = self._session = self._start()
            return session

    def _start(self) -> _HTTPSession:
        loop = asyncio.new_event_loop()
        try:
            client = httpx.AsyncClient(
                transport=self._transport, limits=PROVIDER_HTTP_LIMITS,
                timeout=httpx.Timeout(PROVIDER_READ_TIMEOUT_SECONDS, connect=PROVIDER_CONNECT_TIMEOUT_SECONDS),
            )
            thread = threading.Thread(target=_serve_provider_loop, args=(loop,), name="provider-http", daemon=True)
            thread.start()
        except BaseException:
            loop.close()
            raise
        return _HTTPSession(os.getpid(), loop, thread, client)

    def call(self, session: _HTTPSession, make):
        """Await ``make()`` on the loop and return its result in this thread.

        ``make`` builds the awaitable on the loop thread itself. Waits as long
        as the awaitable runs; the guard inside bounds that."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            # Waiting here would stall that loop (FastAPI's) or deadlock this one.
            raise RuntimeError("provider HTTP called from a running event loop")

        async def run():
            return await make()
        coroutine = run()
        try:
            future = asyncio.run_coroutine_threadsafe(coroutine, session.loop)
        except BaseException:
            coroutine.close()
            raise
        while True:
            try:
                return future.result(timeout=_LIVENESS_SECONDS)
            except concurrent.futures.TimeoutError:
                if future.done():
                    return future.result()
                if not session.thread.is_alive():
                    try:
                        future.cancel()
                    except RuntimeError:
                        pass
                    raise RuntimeError("provider HTTP loop stopped")

    def release(self, session: _HTTPSession, response, chunks=None, *, drain=False):
        """Close a streamed response and its body iterator ``chunks``. After a
        complete stream (``drain``) the tail is read first, in the background,
        so the connection returns to the pool. Otherwise it is closed at once,
        which drops an unfinished connection: the provider sees the
        disconnect as before."""
        on_loop = threading.current_thread() is session.thread
        if drain or on_loop:
            closing = _drain_and_close(response, chunks) if drain else _close_stream(response, chunks)
            try:
                future = asyncio.run_coroutine_threadsafe(closing, session.loop)
            except RuntimeError:
                closing.close()
                if on_loop:
                    raise
            else:
                self._releasing.add(future)
                future.add_done_callback(self._releasing.discard)
                return
        self.call(session, lambda: _close_stream(response, chunks))

    def shutdown(self, timeout: float = 5.0) -> None:
        """Close the client and stop the loop thread (tests, scripts)."""
        with self._lock:
            session, self._session = self._session, None
        if session is None or session.pid != os.getpid() or not session.thread.is_alive():
            return
        for future in list(self._releasing):
            try:
                future.result(timeout)
            except Exception:
                pass
        try:
            asyncio.run_coroutine_threadsafe(session.client.aclose(), session.loop).result(timeout)
        except Exception:
            pass
        session.loop.call_soon_threadsafe(session.loop.stop)
        session.thread.join(timeout)

    def _after_fork(self) -> None:
        # The parent's loop thread does not exist here; its lock may be held.
        self._lock = threading.Lock()
        self._session = None
        self._releasing = set()


_provider_http = ProviderHTTP()
if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=lambda: _provider_http._after_fork())


def cancellable_post_json(url, *, json, headers):
    """Cancel the actual socket task even while waiting for response headers.

    Runs only in synchronous provider workers, never on FastAPI's event loop;
    the request itself runs on the shared provider loop (``ProviderHTTP``).
    No transport retries. Polling monitors cancellation, not provider results.
    """
    from app.services.llm import usage_meter
    from app.services.llm.engines import _ProviderHTTPStatusError, _raise_provider_http_status
    from app.services.llm.provider_dispatch import mark_not_dispatched

    cancellation = current_provider_cancellation()
    budget = current_analysis_budget()
    connect, read = analysis_http_timeout()
    metered = usage_meter.start_call(json)
    http = _provider_http
    try:
        try:
            session = http.session()
        except BaseException as exc:
            mark_not_dispatched(exc)
            raise
        timeout = httpx.Timeout(read, connect=connect)
        response = http.call(session, lambda: _guard_provider_io(
            session.client.post(url, json=json, headers=headers, timeout=timeout), cancellation, budget,
            sends_request=True))
        # Keep the existing content-free HTTP status contract.
        if response.status_code >= 400:
            _raise_provider_http_status(response)
        data = response.json()
    except _ProviderHTTPStatusError:
        metered.rejected()
        raise
    except BaseException as exc:
        from app.services.llm.provider_dispatch import never_reached_provider
        # Connect failure or a stop before dispatch: nothing reached the
        # provider. Timeout/cancellation after the request left: estimate.
        if never_reached_provider(exc):
            metered.rejected()
        else:
            metered.finish()
        raise
    metered.finish(data.get("usage") if isinstance(data, dict) else None)
    return data


async def _bounded_error_body(response, limit=16_384):
    body = b""
    async for chunk in response.aiter_bytes():
        body += chunk
        if len(body) >= limit:
            break
    return body[:limit]


def cancellable_sse_lines(url, *, json, headers, progress=None):
    """Read a provider's SSE lines one by one for a synchronous SSE worker.

    Each socket read runs guarded on the shared provider loop
    (``ProviderHTTP``); a deadline/disconnect cancels header reads and idle
    body reads alike. One read hands over a whole network chunk, split here as
    ``aiter_lines`` would: a round trip between threads per line would cost
    more than the lines. The guard's checks still run before every line. No
    extra producer thread, abandoned request or hidden retry is introduced.
    """
    from httpx._decoders import LineDecoder  # the decoder of Response.aiter_lines

    from app.services.llm.provider_dispatch import mark_not_dispatched

    cancellation = current_provider_cancellation()
    budget = current_analysis_budget()
    http = _provider_http
    try:
        # Runs on the first next(), after the caller started metering.
        connect, read = analysis_http_timeout()
        session = http.session()
        request = session.client.build_request("POST", url, json=json, headers=headers,
                                               timeout=httpx.Timeout(read, connect=connect))
    except BaseException as exc:
        mark_not_dispatched(exc)
        raise
    response = chunks = None
    complete = False

    def guarded(make, *, sends_request=False):
        return http.call(session, lambda: _guard_provider_io(make(), cancellation, budget, progress,
                                                             sends_request=sends_request))

    try:
        response = guarded(lambda: session.client.send(request, stream=True), sends_request=True)
        if response.status_code >= 400:
            from app.services.llm.engines import _raise_provider_http_status
            body = None
            try:
                # Small error bodies only feed a content-free diagnostic.
                body = guarded(lambda: _bounded_error_body(response))
            except (httpx.HTTPError, UnicodeError, ValueError):
                body = None
            _raise_provider_http_status(response, body=body)
        chunks = response.aiter_text()
        decoder = LineDecoder()
        ended = False
        while not ended:
            try:
                lines = decoder.decode(guarded(chunks.__anext__))
            except StopAsyncIteration:
                lines, ended = decoder.flush(), True
            for line in lines:
                # As before each guarded line read: a stop or an exhausted
                # deadline/progress budget ends the stream between lines too.
                _check_provider_io(cancellation, budget, progress)
                if line.startswith("data:") and line[5:].strip() == "[DONE]":
                    complete = True
                yield line
    finally:
        if response is not None:
            http.release(session, response, chunks, drain=complete)
