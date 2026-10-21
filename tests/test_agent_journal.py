"""The run's session journal (agent_journal): order, merging, lines, waiting."""
import threading
import time
from types import SimpleNamespace

import pytest

from app.services.agent_journal import AgentJournal


class Recorder:
    """A write that takes ``seconds`` and records what it saved, in order."""

    def __init__(self, seconds=0.0, fail=None):
        self.seconds, self.fail = seconds, fail
        self.writes, self.failures = [], []
        self.lock = threading.Lock()

    def write(self, job):
        time.sleep(self.seconds)
        if self.fail and self.fail(job):
            raise RuntimeError("database unavailable")
        with self.lock:
            self.writes.append((job.worker.id, dict(job.patch), job.message))
            return {"id": job.key, "seq": len(self.writes), "agent": {"seq": len(self.writes)}}

    def failed(self, job, exc):
        self.failures.append((job.worker.id, str(exc)))


def worker(name):
    return SimpleNamespace(id=name)


def journal(recorder, gap=0.0):
    return AgentJournal(recorder.write, failed=recorder.failed, progress_gap=gap)


def test_a_sessions_updates_are_saved_in_order_and_unwritten_ones_merge():
    recorder = Recorder(seconds=0.05)
    log = journal(recorder)
    a = worker("a")
    log.submit(a, {"status": "waiting"}, wait=True)
    # Written while the first is still saving: these two become one write.
    log.submit(a, {"status": "working", "duration_ms": 1}, wait=False)
    log.submit(a, {"status": "completed", "duration_ms": 9}, {"kind": "result", "text": "Done."}, wait=False)
    log.close()
    assert [patch["status"] for _, patch, _ in recorder.writes] == ["waiting", "completed"]
    assert recorder.writes[-1][2] == {"kind": "result", "text": "Done."}


def test_two_messages_are_never_merged():
    recorder = Recorder(seconds=0.05)
    log = journal(recorder)
    a = worker("a")
    log.submit(a, {"status": "waiting"}, wait=False)
    log.submit(a, {}, {"kind": "partial", "text": "Half"}, wait=False)
    log.submit(a, {"status": "failed"}, {"kind": "failure", "text": "Stopped."}, wait=False)
    log.close()
    assert [message and message["kind"] for _, _, message in recorder.writes][-2:] == ["partial", "failure"]


def test_a_waiting_caller_goes_before_other_sessions_but_after_its_own():
    recorder = Recorder(seconds=0.05)
    log = journal(recorder)
    busy, mine = worker("busy"), worker("mine")
    # Something is being written; then other sessions queue, then this one.
    log.submit(busy, {"status": "working"}, wait=False)
    time.sleep(0.01)
    for name in "bcde":
        log.submit(worker(name), {"status": "working"}, wait=False)
    log.submit(mine, {"status": "working"}, wait=False)
    log.submit(mine, {}, {"kind": "result", "text": "x"}, wait=True)
    order = [name for name, _, _ in recorder.writes]
    # Only the write already running came before; then this session, in order.
    assert order[:2] == ["busy", "mine"]
    log.close()
    assert sorted(name for name, _, _ in recorder.writes) == ["b", "busy", "c", "d", "e", "mine"]


def test_a_waiting_caller_gets_the_saved_event_or_the_error():
    recorder = Recorder(fail=lambda job: job.worker.id == "bad")
    log = journal(recorder)
    event = log.submit(worker("good"), {"status": "waiting"}, wait=True)
    assert event["seq"] == 1
    with pytest.raises(RuntimeError, match="database unavailable"):
        log.submit(worker("bad"), {"status": "waiting"}, wait=True)
    # Raised to the one who waited, not reported a second time.
    assert recorder.failures == []
    log.close()


def test_an_update_nobody_waits_for_reports_its_failure():
    recorder = Recorder(fail=lambda job: True)
    log = journal(recorder)
    log.submit(worker("a"), {"status": "completed"}, wait=False)
    log.close()
    assert recorder.failures == [("a", "database unavailable")]


def test_the_newest_line_replaces_a_waiting_one_and_rides_with_the_next_status():
    recorder = Recorder(seconds=0.05)
    log = journal(recorder, gap=10)
    a, b = worker("a"), worker("b")
    log.submit(b, {"status": "working"}, wait=False)
    for i in range(5):
        log.submit(a, {"progress_text": f"line {i}"}, wait=False, progress=True)
    log.submit(a, {"status": "completed"}, wait=False)
    log.close()
    saved = [patch for name, patch, _ in recorder.writes if name == "a"]
    assert saved == [{"progress_text": "line 4", "status": "completed"}]


def test_a_line_never_overrides_the_status_it_joins():
    recorder = Recorder(seconds=0.05)
    log = journal(recorder, gap=10)
    a = worker("a")
    log.submit(worker("busy"), {"status": "working"}, wait=False)
    log.submit(a, {"status": "completed", "duration_ms": 9}, wait=False)
    log.submit(a, {"progress_text": "late line", "duration_ms": 3}, wait=False, progress=True)
    log.close()
    [patch] = [patch for name, patch, _ in recorder.writes if name == "a"]
    assert patch == {"status": "completed", "duration_ms": 9, "progress_text": "late line"}


def test_lines_of_all_sessions_are_written_at_most_once_per_gap():
    recorder = Recorder()
    times = []
    original = recorder.write

    def timed(job):
        times.append(time.monotonic())
        return original(job)

    recorder.write = timed
    log = journal(recorder, gap=0.1)
    started = time.monotonic()
    while time.monotonic() - started < 0.45:
        for name in "abc":
            log.submit(worker(name), {"progress_text": f"{name} {time.monotonic()}"}, wait=False, progress=True)
        time.sleep(0.005)
    log.close()
    line_times = times[:-3]  # close() writes what is still waiting at once
    assert 3 <= len(line_times) <= 6
    assert all(later - earlier >= 0.09 for earlier, later in zip(line_times, line_times[1:]))


def test_close_saves_everything_and_later_updates_are_dropped():
    recorder = Recorder()
    log = journal(recorder, gap=10)
    log.submit(worker("a"), {"progress_text": "last line"}, wait=False, progress=True)
    log.close()
    assert recorder.writes == [("a", {"progress_text": "last line"}, None)]
    assert log.submit(worker("a"), {"status": "stopped"}, wait=False) is None
    with pytest.raises(RuntimeError):
        log.submit(worker("a"), {"status": "stopped"}, wait=True)
