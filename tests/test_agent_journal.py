"""The run's session journal (agent_journal): order, merging, lines, waiting."""
import threading
import time
from types import SimpleNamespace

import pytest

from app.services.agent_journal import BATCH_LIMIT, AgentJournal


class Recorder:
    """A write that takes ``seconds`` and records what it saved, in order.
    ``fail(job)``: that job alone is refused; ``down``: the whole write raises."""

    def __init__(self, seconds=0.0, fail=None):
        self.seconds, self.fail = seconds, fail
        self.down = False
        self.writes, self.failures, self.batches = [], [], []
        self.lock = threading.Lock()

    def write(self, jobs):
        down = self.down
        time.sleep(self.seconds)
        if down:
            raise RuntimeError("database unavailable")
        results = []
        with self.lock:
            self.batches.append([job.worker.id for job in jobs])
            for job in jobs:
                if self.fail and self.fail(job):
                    results.append(RuntimeError("update refused"))
                    continue
                self.writes.append((job.worker.id, dict(job.patch), job.message))
                results.append({"id": job.key, "seq": len(self.writes), "agent": {"seq": len(self.writes)}})
        return results

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


def test_updates_of_several_sessions_that_queue_during_a_write_are_saved_together():
    """Six comparison answers start at once: their sessions are one write
    after the one already running, not six in a row (since 2026-10-22)."""
    recorder = Recorder(seconds=0.05)
    log = journal(recorder)
    log.submit(worker("busy"), {"status": "working"}, wait=False)
    time.sleep(0.01)
    waiters = [threading.Thread(target=log.submit, args=(worker(name), {"status": "waiting"}), kwargs={"wait": True})
               for name in "abcdef"]
    for thread in waiters:
        thread.start()
    for thread in waiters:
        thread.join()
    log.close()
    assert recorder.batches == [["busy"], list("abcdef")]


def test_a_waiting_caller_goes_into_the_next_batch_before_other_sessions():
    recorder = Recorder(seconds=0.05)
    log = journal(recorder)
    log.submit(worker("busy"), {"status": "working"}, wait=False)
    time.sleep(0.01)
    others = [f"s{i:02d}" for i in range(40)]
    for name in others:
        log.submit(worker(name), {"status": "working"}, wait=False)
    mine = worker("mine")
    log.submit(mine, {"status": "working"}, wait=False)
    log.submit(mine, {}, {"kind": "result", "text": "x"}, wait=True)
    # Only the write already running came before; a full batch still takes
    # this session first, its two updates as one.
    assert recorder.batches[0] == ["busy"]
    assert recorder.batches[1][0] == "mine" and len(recorder.batches[1]) == BATCH_LIMIT
    log.close()
    assert sorted(name for name, _, _ in recorder.writes) == sorted(["busy", "mine", *others])
    assert [patch for name, patch, _ in recorder.writes if name == "mine"] == [{"status": "working"}]


def test_one_refused_update_leaves_the_others_of_its_batch_saved():
    recorder = Recorder(seconds=0.05, fail=lambda job: job.worker.id == "bad")
    log = journal(recorder)
    log.submit(worker("busy"), {"status": "working"}, wait=False)
    time.sleep(0.01)
    for name in ("good", "bad", "fine"):
        log.submit(worker(name), {"status": "completed"}, wait=False)
    log.close()
    assert [name for name, _, _ in recorder.writes] == ["busy", "good", "fine"]
    assert recorder.failures == [("bad", "update refused")]


def test_a_failed_write_refuses_its_whole_batch():
    recorder = Recorder(seconds=0.05)
    log = journal(recorder)
    log.submit(worker("busy"), {"status": "working"}, wait=False)
    time.sleep(0.01)
    recorder.down = True
    log.submit(worker("a"), {"status": "completed"}, wait=False)
    with pytest.raises(RuntimeError, match="database unavailable"):
        log.submit(worker("mine"), {"status": "waiting"}, wait=True)
    log.close()
    # Raised to the one who waited; the other is reported.
    assert recorder.failures == [("a", "database unavailable")]


def test_a_waiting_caller_gets_the_saved_event_or_the_error():
    recorder = Recorder(fail=lambda job: job.worker.id == "bad")
    log = journal(recorder)
    event = log.submit(worker("good"), {"status": "waiting"}, wait=True)
    assert event["seq"] == 1
    with pytest.raises(RuntimeError, match="update refused"):
        log.submit(worker("bad"), {"status": "waiting"}, wait=True)
    # Raised to the one who waited, not reported a second time.
    assert recorder.failures == []
    log.close()


def test_an_update_nobody_waits_for_reports_its_failure():
    recorder = Recorder(fail=lambda job: True)
    log = journal(recorder)
    log.submit(worker("a"), {"status": "completed"}, wait=False)
    log.close()
    assert recorder.failures == [("a", "update refused")]


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


def test_lines_of_all_sessions_are_written_together_at_most_once_per_gap():
    recorder = Recorder()
    times = []
    original = recorder.write

    def timed(jobs):
        times.append(time.monotonic())
        return original(jobs)

    recorder.write = timed
    log = journal(recorder, gap=0.1)
    started = time.monotonic()
    while time.monotonic() - started < 0.45:
        for name in "abc":
            log.submit(worker(name), {"progress_text": f"{name} {time.monotonic()}"}, wait=False, progress=True)
        time.sleep(0.005)
    log.close()
    line_times = times[:-1]  # close() writes what is still waiting at once
    assert 3 <= len(line_times) <= 6
    assert all(later - earlier >= 0.09 for earlier, later in zip(line_times, line_times[1:]))
    # Each model's newest line, every gap: after the first write (only "a"
    # had a line yet) every write carries all three.
    assert all(sorted(batch) == ["a", "b", "c"] for batch in recorder.batches[1:])


def test_close_saves_everything_and_later_updates_are_dropped():
    recorder = Recorder()
    log = journal(recorder, gap=10)
    log.submit(worker("a"), {"progress_text": "last line"}, wait=False, progress=True)
    log.close()
    assert recorder.writes == [("a", {"progress_text": "last line"}, None)]
    assert log.submit(worker("a"), {"status": "stopped"}, wait=False) is None
    with pytest.raises(RuntimeError):
        log.submit(worker("a"), {"status": "stopped"}, wait=True)
