"""Agent turns run on their own thread, independent of any HTTP connection.

POST /agent prepares a turn, starts its producer here and answers with a tail
of the turn's frames (app.services.agent_live). A dropped connection, a tab in
the background or a closed laptop therefore only ends that tail; the turn
finishes and saves its answer, and the browser picks it up again. Only an
explicit Stop (``stop``) or a server shutdown ends a turn early.

Stop before start: a Stop can arrive before its POST was admitted (the user
cancels within the same moment). It then leaves a short-lived marker that
refuses the start, under the same lock that registers a run, so no turn
starts after its Stop.

Shutdown (Render deploys and the daily restart send SIGTERM and wait a fixed
delay before SIGKILL): ``begin_shutdown`` refuses new turns and lets running
ones finish for a grace period; afterwards each remaining turn is interrupted
with a clear reason, so it settles its usage and saves the available answer
before the process is killed. ``drain`` waits for that from the lifespan.

All of this is process memory. Production runs one worker; another worker
would not know these runs, and the browser then follows the saved turn.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import OrderedDict
from contextvars import copy_context
from dataclasses import dataclass, field
from typing import Callable

STOP_MARKER_SECONDS = 600.0
MAX_STOP_MARKERS = 1024
SHUTDOWN_SETTLE_SECONDS = 8.0
SHUTDOWN_REASON = ("The server restarted during this response. "
                   "Everything received up to that point has been saved; send the message again to continue.")


def shutdown_grace_seconds() -> float:
    """Time a running turn may still finish after SIGTERM.

    Render's default shutdown delay is 30 s (maximum 300 s); the default
    leaves room to settle and save before SIGKILL. Raise it together with
    the service's maxShutdownDelaySeconds.
    """
    try:
        value = float(os.getenv("AGENT_SHUTDOWN_GRACE_SECONDS", "20"))
    except ValueError:
        value = 20.0
    return min(max(value, 0.0), 900.0)


class AgentRunStopped(Exception):
    """A Stop for this request arrived before the turn started."""


class AgentShuttingDown(Exception):
    """The process is draining for a restart and starts no new turns."""


class AgentRunDuplicate(Exception):
    """The same request identity is already running in this process."""


@dataclass
class BackgroundRun:
    uid: str
    chat_id: str
    request_id: str
    turn_id: str
    cancel: Callable[[], None]
    interrupt: Callable[[Exception], None]
    finished: threading.Event = field(default_factory=threading.Event)
    stopped: bool = False

    @property
    def key(self):
        return (self.uid, self.chat_id, self.request_id)


class AgentBackgroundRuns:
    def __init__(self, *, clock=time.monotonic, stop_ttl=STOP_MARKER_SECONDS, max_stops=MAX_STOP_MARKERS):
        self._clock = clock
        self._stop_ttl, self._max_stops = stop_ttl, max_stops
        self._lock = threading.Condition()
        self._runs: dict[tuple, BackgroundRun] = {}
        self._stops: OrderedDict[tuple, float] = OrderedDict()
        self._shutdown_at: float | None = None
        self._grace = 0.0

    @staticmethod
    def key(uid, chat_id, request_id):
        return (str(uid), str(chat_id), str(request_id))

    @property
    def shutting_down(self) -> bool:
        return self._shutdown_at is not None

    def active(self) -> int:
        with self._lock:
            return len(self._runs)

    def running(self, uid, chat_id, request_id) -> bool:
        with self._lock:
            run = self._runs.get(self.key(uid, chat_id, request_id))
            return run is not None and not run.finished.is_set()

    def start(self, *, uid, chat_id, request_id, turn_id, target, cancel, interrupt) -> BackgroundRun:
        """Run ``target`` on its own thread; refused after a Stop or during shutdown."""
        run = BackgroundRun(uid=str(uid), chat_id=str(chat_id), request_id=str(request_id), turn_id=str(turn_id),
                            cancel=cancel, interrupt=interrupt)
        with self._lock:
            if self._shutdown_at is not None:
                raise AgentShuttingDown("The server is restarting. Please send your message again in a moment.")
            self._expire_stops()
            if self._stops.pop(run.key, None) is not None:
                raise AgentRunStopped("Response stopped before a model call started.")
            current = self._runs.get(run.key)
            if current is not None and not current.finished.is_set():
                raise AgentRunDuplicate("This request is still running.")
            self._runs[run.key] = run
        # The producer runs off the request; carry its ContextVars (the
        # correlation id for logs and alerts) along.
        context = copy_context()

        def main():
            try:
                context.run(target)
            except BaseException as exc:  # noqa: BLE001 - a thread must not die silently
                from app.core.observability import safe_exception, safe_traceback
                from app.services.error_alerts import report_server_exception
                logging.error("Agent background run crashed category=%s where=%s", safe_exception(exc), safe_traceback(exc))
                report_server_exception(exc, where="agent.background_run")
            finally:
                self._finished(run)

        thread = threading.Thread(target=main, name="agent-run", daemon=True)
        try:
            thread.start()
        except BaseException:
            self._finished(run)
            raise
        return run

    def stop(self, uid, chat_id, *, request_id=None, turn_id=None) -> bool:
        """Cancel a running turn of this account; True when this process runs it.

        A request that is not running yet is remembered so it cannot start.
        """
        with self._lock:
            run = None
            if request_id is not None:
                run = self._runs.get(self.key(uid, chat_id, request_id))
            if run is None and turn_id is not None:
                run = next((item for item in self._runs.values()
                            if (item.uid, item.chat_id, item.turn_id) == (str(uid), str(chat_id), str(turn_id))), None)
            if run is None:
                if request_id is not None:
                    self._expire_stops()
                    self._stops[self.key(uid, chat_id, request_id)] = self._clock() + self._stop_ttl
                    self._stops.move_to_end(self.key(uid, chat_id, request_id))
                    while len(self._stops) > self._max_stops:
                        self._stops.popitem(last=False)
                return False
            run.stopped = True
        run.cancel()
        return True

    def begin_shutdown(self, grace: float | None = None) -> None:
        """Refuse new turns; interrupt the remaining ones after ``grace`` seconds."""
        grace = shutdown_grace_seconds() if grace is None else max(float(grace), 0.0)
        with self._lock:
            if self._shutdown_at is not None:
                return
            self._shutdown_at, self._grace = self._clock(), grace
            count = len(self._runs)
        logging.info("Agent shutdown: %d running turn(s) may finish for %.0f s", count, grace)
        timer = threading.Timer(grace, self.interrupt_all)
        timer.daemon = True
        timer.name = "agent-shutdown"
        timer.start()

    def interrupt_all(self) -> int:
        from app.services.agent_provider_limits import AgentRunInterrupted
        with self._lock:
            runs = [run for run in self._runs.values() if not run.finished.is_set()]
        for run in runs:
            try:
                run.interrupt(AgentRunInterrupted(SHUTDOWN_REASON))
            except Exception as exc:  # noqa: BLE001 - one run must not keep the others alive
                from app.core.observability import safe_exception
                logging.warning("Agent shutdown interrupt failed category=%s", safe_exception(exc))
        if runs:
            logging.warning("Agent shutdown interrupted %d running turn(s)", len(runs))
        return len(runs)

    def drain(self, *, grace: float | None = None, settle: float = SHUTDOWN_SETTLE_SECONDS) -> int:
        """Block until every turn ended or the shutdown budget is spent; returns the rest."""
        self.begin_shutdown(grace)
        with self._lock:
            deadline = self._shutdown_at + self._grace + settle
            while self._runs:
                remaining = deadline - self._clock()
                if remaining <= 0:
                    break
                self._lock.wait(min(remaining, 1.0))
            left = len(self._runs)
        if left:
            logging.warning("Agent shutdown: %d turn(s) still running at the deadline", left)
        return left

    def _finished(self, run):
        run.finished.set()
        with self._lock:
            if self._runs.get(run.key) is run:
                del self._runs[run.key]
            self._lock.notify_all()

    def _expire_stops(self):
        now = self._clock()
        while self._stops:
            key, expires = next(iter(self._stops.items()))
            if expires > now:
                break
            self._stops.popitem(last=False)


agent_background = AgentBackgroundRuns()
