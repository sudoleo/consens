"""Run snapshots reduce parallel profile reads without caching settings reads."""

from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from app.services import user_memory


class Repository:
    def __init__(self, role="Original"):
        self.role = role
        self.calls = 0

    def get(self, uid, **kwargs):
        self.calls += 1
        return {"role": self.role, "notes": "n" * 100}


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    monkeypatch.setattr(user_memory, "_profile_run_cache", user_memory._RunProfileSnapshotCache())


def load(repo, uid="owner", run_key="run-1", **kwargs):
    return user_memory.load_profile_text(repo, uid, run_key=run_key, **kwargs)


def test_run_snapshot_is_stable_but_new_run_and_standalone_reads_are_fresh():
    repo = Repository()
    first = load(repo)
    repo.role = "Edited"
    assert load(repo) == first
    assert "Edited" in load(repo, run_key="run-2")
    assert "Edited" in load(repo, run_key=None)
    assert repo.calls == 3


@pytest.mark.parametrize("key", [None, "", " ", 123, "x" * 201])
def test_no_usable_run_key_never_caches(key):
    repo = Repository()
    load(repo, run_key=key)
    load(repo, run_key=key)
    assert repo.calls == 2


def test_owners_repositories_and_tier_budgets_never_share_snapshots():
    repo = Repository()
    other = Repository("Other database")
    load(repo)
    load(repo, uid="other-owner")
    assert "Other database" in load(other)
    short = load(repo, max_notes_chars=50)
    assert "n" * 51 not in short
    assert repo.calls == 3
    assert other.calls == 1


def test_expired_snapshot_reads_again(monkeypatch):
    now = [1.0]
    monkeypatch.setattr(user_memory.time, "monotonic", lambda: now[0])
    repo = Repository()
    load(repo)
    now[0] += user_memory.PROFILE_RUN_CACHE_TTL_SECONDS + 1
    repo.role = "Fresh"
    assert "Fresh" in load(repo)
    assert repo.calls == 2


def test_read_failures_are_not_cached():
    class RecoveringRepository(Repository):
        def get(self, uid, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("unavailable")
            return {"role": "Recovered"}

    repo = RecoveringRepository()
    assert load(repo) == ""
    assert "Recovered" in load(repo)
    assert repo.calls == 2


def test_six_parallel_model_requests_share_one_read():
    started = threading.Event()
    release = threading.Event()
    callers = threading.Barrier(6)

    class SlowRepository(Repository):
        def get(self, uid, **kwargs):
            self.calls += 1
            started.set()
            assert release.wait(2)
            return {"role": "Shared"}

    repo = SlowRepository()

    def ask():
        callers.wait(timeout=2)
        return load(repo)

    with ThreadPoolExecutor(max_workers=6) as pool:
        requests = [pool.submit(ask) for _ in range(6)]
        assert started.wait(2)
        release.set()
        results = [request.result(timeout=2) for request in requests]
    assert repo.calls == 1
    assert len(set(results)) == 1
    assert "Shared" in results[0]


def test_invalidation_during_read_discards_personal_text():
    started = threading.Event()
    release = threading.Event()

    class SlowRepository(Repository):
        def get(self, uid, **kwargs):
            self.calls += 1
            started.set()
            assert release.wait(2)
            return {"role": "Deleted personal text"}

    repo = SlowRepository()
    with ThreadPoolExecutor(max_workers=1) as pool:
        request = pool.submit(load, repo)
        assert started.wait(2)
        user_memory.invalidate_profile_snapshots("owner")
        release.set()
        assert request.result(timeout=2) == ""
    assert not user_memory._profile_run_cache._entries


def test_waiting_model_fails_open_when_another_profile_read_is_stuck(monkeypatch):
    monkeypatch.setattr(user_memory, "PROFILE_READ_TIMEOUT_SECONDS", 0)
    started = threading.Event()
    release = threading.Event()

    class SlowRepository(Repository):
        def get(self, uid, **kwargs):
            self.calls += 1
            started.set()
            assert release.wait(2)
            return {"role": "Eventually available"}

    repo = SlowRepository()
    with ThreadPoolExecutor(max_workers=1) as pool:
        request = pool.submit(load, repo)
        assert started.wait(2)
        assert load(repo) == ""
        release.set()
        assert "Eventually available" in request.result(timeout=2)
    assert "Eventually available" in load(repo)
    assert repo.calls == 1


def test_invalidation_only_removes_target_owner():
    repo = Repository()
    load(repo)
    load(repo, uid="other-owner")
    user_memory.invalidate_profile_snapshots("owner")
    load(repo, uid="other-owner")
    load(repo)
    assert repo.calls == 3


def test_cache_storage_is_bounded(monkeypatch):
    monkeypatch.setattr(user_memory, "PROFILE_RUN_CACHE_MAX_ENTRIES", 2)
    repo = Repository()
    for i in range(8):
        load(repo, run_key=f"run-{i}")
    assert len(user_memory._profile_run_cache._entries) == 2
    load(repo, run_key="run-7")
    assert repo.calls == 8
    load(repo, run_key="run-0")
    assert repo.calls == 9


def test_pending_entries_are_bounded_and_overflow_reads_without_caching(monkeypatch):
    monkeypatch.setattr(user_memory, "PROFILE_RUN_CACHE_MAX_ENTRIES", 1)
    started = threading.Event()
    release = threading.Event()

    class SlowRepository(Repository):
        def get(self, uid, **kwargs):
            started.set()
            assert release.wait(2)
            return {"role": "Slow"}

    with ThreadPoolExecutor(max_workers=1) as pool:
        request = pool.submit(load, SlowRepository())
        assert started.wait(2)
        repo = Repository()
        assert "Original" in load(repo, run_key="overflow")
        assert "Original" in load(repo, run_key="overflow")
        assert repo.calls == 2
        assert len(user_memory._profile_run_cache._entries) == 1
        release.set()
        request.result(timeout=2)
