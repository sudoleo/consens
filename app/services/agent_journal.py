"""The run's agent-session journal, written on one thread.

Every status of every model call of a run is saved by ``publish_agents`` in a Firestore transaction.
Written by the calling thread under the run's lock, a comparison answer stopped reading its stream
for every saved line and the transactions queued up faster than Firestore took them, until finished
answers were cancelled. So a call hands its status here and goes on; one writer saves them in order
per session: everything due goes into one transaction, a caller that needs the saved event waits and
goes first, waiting statuses of one session merge, and live reasoning lines replace the waiting one
and are written at most every ``progress_gap`` across the run, so they never queue ahead of a call's
receipt."""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from uuid import uuid4

# A few documents per update, far below Firestore's 500 writes per commit; a batch never waits to be
# full.
BATCH_LIMIT = 32


class JournalJob:

    __slots__ = ("worker", "patch", "message", "progress", "urgent", "started", "order", "key", "event", "error",
                 "done")

    def __init__(self, worker, patch, message, *, progress, urgent, order):
        self.worker, self.patch, self.message = worker, patch, message
        # A retried write finds its own first commit by this id.
        self.key = uuid4().hex
        self.progress, self.urgent, self.order = progress, urgent, order
        self.started = False
        self.event = self.error = None
        self.done = threading.Event()

    def absorb(self, patch, message):
        self.patch = {**self.patch, **patch}
        if message is not None:
            self.message = message

    def result(self):
        self.done.wait()
        if self.error is not None:
            raise self.error
        return self.event


class AgentJournal:
    """Saves session updates in order per session, on one writer thread. ``write(jobs)`` returns per
    job its event or the exception that refused it alone; one it raises refuses them all.
    ``failed(job, exc)`` hears about a job nobody waited for that could not be saved."""

    def __init__(self, write, *, failed, progress_gap, clock=time.monotonic):
        self._write, self._failed = write, failed
        self._gap, self._clock = progress_gap, clock
        self._condition = threading.Condition()
        self._queues = {}
        self._order = 0
        self._last_progress = float("-inf")
        self._thread = None
        self._closing = False

    def submit(self, worker, patch, message=None, *, wait, progress=False):
        """Queue an update of ``worker``'s session; with ``wait`` return the saved event (or raise
        its error) once written."""
        with self._condition:
            if self._closing:
                # The run has ended (a straggler reporting late): the turn accepts no session
                # updates.
                if wait:
                    raise RuntimeError("The run's journal is closed")
                return None
            queue = self._queues.setdefault(worker.id, deque())
            tail = queue[-1] if queue else None
            mergeable = tail is not None and not tail.started and (tail.message is None or message is None)
            if mergeable and (tail.progress or not progress):
                if tail.progress and not progress:
                    # The waiting line rides along with this status.
                    tail.progress = False
                tail.absorb(patch, message)
                job = tail
            elif progress and tail is not None and not tail.started and not tail.progress:
                # A status is still waiting: the line goes with it.
                tail.patch = {**patch, **tail.patch}
                return tail
            else:
                self._order += 1
                job = JournalJob(worker, patch, message, progress=progress, urgent=False, order=self._order)
                queue.append(job)
            if wait:
                # Everything this session queued before goes first, so all of it is urgent now.
                for queued in queue:
                    queued.urgent = True
            self._start()
            self._condition.notify_all()
        return job.result() if wait else job

    def close(self, timeout=None):
        """Write everything still queued and stop, waiting at most ``timeout``: a hung write must
        not hold the run's end until its lease expires."""
        with self._condition:
            self._closing = True
            self._condition.notify_all()
            thread = self._thread
        if thread is not None:
            thread.join(timeout)
            if thread.is_alive():
                logging.warning("Agent journal still saving at the run's end thread=%s", thread.name)

    def _start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="agent-journal", daemon=True)
            self._thread.start()

    def _next(self):
        """The heads of each session's queue that are due and, without any, how long to wait."""
        heads = [queue[0] for queue in self._queues.values()]
        if not heads:
            return [], None
        lines_due = self._closing or self._clock() >= self._last_progress + self._gap
        due = [job for job in heads if lines_due or job.urgent or not job.progress]
        if not due:
            return [], self._last_progress + self._gap - self._clock()
        # A full batch leaves the rest for the next one: waiting callers first.
        return sorted(due, key=lambda job: (not job.urgent, job.order))[:BATCH_LIMIT], None

    def _run(self):
        while True:
            with self._condition:
                while True:
                    jobs, wait = self._next()
                    if jobs:
                        break
                    if self._closing and not self._queues:
                        return
                    self._condition.wait(wait)
                for job in jobs:
                    job.started = True
            try:
                results = self._write(jobs)
            except BaseException as exc:
                results = [exc] * len(jobs)
            for job, result in zip(jobs, results):
                if isinstance(result, BaseException):
                    job.error = result
                else:
                    job.event = result
            with self._condition:
                for job in jobs:
                    queue = self._queues[job.worker.id]
                    queue.popleft()
                    if not queue:
                        del self._queues[job.worker.id]
                if any(job.progress for job in jobs):
                    self._last_progress = self._clock()
                self._condition.notify_all()
            for job in jobs:
                job.done.set()
            for job in jobs:
                if job.error is not None and not job.urgent:
                    self._failed(job, job.error)
