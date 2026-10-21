"""The run's agent-session journal, written on one thread (since 2026-10-21).

Every status of every model call of a run (waiting, working, the live
reasoning line, completed, its result) is saved by ``publish_agents`` in a
Firestore transaction. Until 2026-10-21 the calling thread wrote it itself,
holding the run's lock: a comparison answer stopped reading its stream for
every line it saved, and every other call waited behind it. With six
comparison models, two Differences passes, Coverage windows and their hedges
the transactions queued up faster than Firestore (0.4-1 s each) could take
them; in prod a request left 77 s after the decision and finished judge
answers were cancelled after 90 s (docs/agent-mode.md "Wartezeit im Server").

Now a call hands its status to this journal and goes on. One writer thread
saves them in order per session:

- Everything due when the writer is free goes into one transaction (since
  2026-10-22): six answers starting together are one write, not six writes
  in a row, each ahead of a model call's receipt behind the account lock.
- A caller that needs the saved event (a new session must exist before its
  receipt is claimed, a worker's message carries its event id) waits; its
  session goes first when a batch is full.
- Statuses of the same session that are still waiting merge into one update
  (``completed`` and the result become one).
- A live reasoning line replaces the line still waiting; lines are written at
  most every ``progress_gap`` seconds across the whole run (all sessions'
  lines together), so they never fill the database queue ahead of a model
  call's receipt.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from uuid import uuid4

# Updates per transaction: a few documents each, far below Firestore's 500
# writes per commit, and a batch never waits for a full one.
BATCH_LIMIT = 32


class JournalJob:
    """One session update: ``patch`` for the session, optional ``message``."""

    __slots__ = ("worker", "patch", "message", "progress", "urgent", "started", "order", "key", "event", "error",
                 "done")

    def __init__(self, worker, patch, message, *, progress, urgent, order):
        self.worker, self.patch, self.message = worker, patch, message
        # The saved event's id: a retried write finds its own first commit.
        self.key = uuid4().hex
        self.progress, self.urgent, self.order = progress, urgent, order
        self.started = False
        self.event = self.error = None
        self.done = threading.Event()

    def absorb(self, patch, message):
        """A newer update of the same session, still unwritten: one write."""
        self.patch = {**self.patch, **patch}
        if message is not None:
            self.message = message

    def result(self):
        self.done.wait()
        if self.error is not None:
            raise self.error
        return self.event


class AgentJournal:
    """Saves session updates in order per session, on one writer thread.

    ``write(jobs)`` saves jobs of different sessions together and returns one
    entry per job, its event or the exception that refused it alone; an
    exception it raises refuses them all. It runs on the writer thread,
    never under a caller's lock. ``failed(job, exc)`` hears about a job
    nobody waited for that could not be saved."""

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
        """Queue an update of ``worker``'s session. ``wait``: return the saved
        event (or raise its error) once written; otherwise return at once."""
        with self._condition:
            if self._closing:
                # The run has ended (a straggler thread reporting late): the
                # turn is being finalized and accepts no session updates.
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
                # Everything this session queued before goes first, so all of
                # it is urgent now.
                for queued in queue:
                    queued.urgent = True
            self._start()
            self._condition.notify_all()
        return job.result() if wait else job

    def close(self):
        """Write everything still queued, lines included, and stop."""
        with self._condition:
            self._closing = True
            self._condition.notify_all()
            thread = self._thread
        if thread is not None:
            thread.join()

    def _start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="agent-journal", daemon=True)
            self._thread.start()

    def _next(self):
        """The jobs to write together next (the head of each session's queue
        that is due) and, without any, how long to wait."""
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
