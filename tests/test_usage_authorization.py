"""Atomic authorization preserves billing safeguards with three document reads."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from app.services import persistence_guard
from app.services.usage_repository import (
    RunKind, RunStatus, UsageDataError, UsageLimitExceeded, UsageLimits,
    UsageOperationConflict, UsageRunConflict, UsageRunExpired, UsageRunReleased,
    canonical_request_fingerprint,
)
from usage_test_support import make_usage_repository


NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
LIMITS = UsageLimits(total=3, deep_think=1)
RUN_FP = canonical_request_fingerprint({"question": "question"})
OP_FP = canonical_request_fingerprint({"model": "model"})


def authorize(repo, *, uid="owner", key="run", operation="ask:openai",
              kind=RunKind.REGULAR, limits=LIMITS, now=NOW,
              run_fp=RUN_FP, op_fp=OP_FP):
    return repo.authorize_operation(
        uid, key, kind, limits, operation, op_fp,
        request_fingerprint=run_fp, now=now,
    )


@pytest.mark.parametrize("prepared", ["missing", "reserved", "consumed"])
@pytest.mark.parametrize("kind", [RunKind.REGULAR, RunKind.DEEP_THINK])
def test_three_reads_for_direct_reserved_and_prepared_runs(prepared, kind):
    repo, db = make_usage_repository()
    if prepared != "missing":
        repo.reserve("owner", "run", kind, LIMITS, request_fingerprint=RUN_FP, now=NOW)
    if prepared == "consumed":
        repo.consume("owner", "run")
    db.reads.clear()

    result, claim = authorize(repo, kind=kind)

    assert len(db.reads) == len(set(db.reads)) == 3
    assert db.reads[0] == ("account_deletion_jobs", "owner")
    assert result.status is RunStatus.CONSUMED
    assert result.snapshot.total.consumed == 1
    assert result.snapshot.total.reserved == 0
    assert result.snapshot.deep_think.consumed == int(kind is RunKind.DEEP_THINK)
    assert claim.idempotent is False


def test_six_provider_fanout_uses_18_reads_and_one_charge():
    repo, db = make_usage_repository()
    repo.reserve("owner", "run", RunKind.REGULAR, LIMITS, request_fingerprint=RUN_FP, now=NOW)
    repo.consume("owner", "run")
    db.reads.clear()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(
            lambda index: authorize(repo, operation=f"ask:provider{index}"), range(6)
        ))
    assert len(db.reads) == 18
    assert all(not claim.idempotent for _, claim in results)
    assert repo.snapshot("owner", LIMITS, now=NOW).total.consumed == 1


def test_same_operation_race_has_exactly_one_authorization():
    repo, db = make_usage_repository()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: authorize(repo), range(6)))
    assert sum(not claim.idempotent for _, claim in results) == 1
    assert repo.snapshot("owner", LIMITS, now=NOW).total.consumed == 1
    before = deepcopy(db.documents)
    _, repeated = authorize(repo)
    assert repeated.idempotent
    assert db.documents == before


def test_distinct_run_race_cannot_exceed_daily_limit():
    repo, _ = make_usage_repository()
    def attempt(index):
        try:
            authorize(repo, key=f"run-{index}")
            return True
        except UsageLimitExceeded:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        accepted = list(pool.map(attempt, range(12)))
    assert sum(accepted) == LIMITS.total
    assert repo.snapshot("owner", LIMITS, now=NOW).total.consumed == LIMITS.total


@pytest.mark.parametrize("changes,error", [
    ({"run_fp": canonical_request_fingerprint("other")}, UsageRunConflict),
    ({"kind": RunKind.DEEP_THINK}, UsageRunConflict),
    ({"op_fp": canonical_request_fingerprint("other")}, UsageOperationConflict),
    ({"now": NOW + timedelta(days=1)}, UsageRunExpired),
])
def test_conflicts_and_expiry_leave_all_documents_unchanged(changes, error):
    repo, db = make_usage_repository()
    authorize(repo)
    before = deepcopy(db.documents)
    with pytest.raises(error):
        authorize(repo, **changes)
    assert db.documents == before


def test_released_reservation_cannot_authorize_work():
    repo, db = make_usage_repository()
    repo.reserve("owner", "run", RunKind.REGULAR, LIMITS, request_fingerprint=RUN_FP, now=NOW)
    repo.release("owner", "run")
    before = deepcopy(db.documents)
    with pytest.raises(UsageRunReleased):
        authorize(repo)
    assert db.documents == before


def test_deep_quota_failure_does_not_consume_total_or_claim():
    repo, db = make_usage_repository()
    authorize(repo, kind=RunKind.DEEP_THINK)
    before = deepcopy(db.documents)
    with pytest.raises(UsageLimitExceeded) as error:
        authorize(repo, key="another", kind=RunKind.DEEP_THINK)
    assert error.value.limiting_bucket == "deep_think"
    assert db.documents == before


def test_changed_limits_preserve_previously_reserved_limits_and_fresh_counters():
    repo, _ = make_usage_repository()
    repo.reserve("owner", "run", RunKind.REGULAR, LIMITS, request_fingerprint=RUN_FP, now=NOW)
    authorize(repo, key="other")
    result, _ = authorize(repo, limits=UsageLimits(total=0, deep_think=0))
    assert result.snapshot.total.limit == LIMITS.total
    assert result.snapshot.total.consumed == 2
    assert result.snapshot.total.remaining == 1


def test_owner_isolation_and_utc_rollover():
    repo, _ = make_usage_repository()
    authorize(repo)
    other, _ = authorize(repo, uid="other-owner")
    tomorrow, _ = authorize(repo, key="tomorrow", now=NOW + timedelta(days=1))
    assert other.snapshot.total.consumed == 1
    assert tomorrow.snapshot.total.consumed == 1
    assert tomorrow.utc_date == "2026-09-10"


def test_account_deletion_fence_blocks_even_a_prepared_run():
    repo, db = make_usage_repository()
    authorize(repo)
    db.documents[("account_deletion_jobs", "owner")] = {"status": "pending"}
    before = deepcopy(db.documents)
    db.reads.clear()
    with pytest.raises(persistence_guard.AccountDeletionInProgress):
        authorize(repo, operation="consensus")
    assert db.documents == before
    assert db.reads == [("account_deletion_jobs", "owner")]


def test_corrupt_reserved_counter_fails_without_claim():
    repo, db = make_usage_repository()
    repo.reserve("owner", "run", RunKind.REGULAR, LIMITS, request_fingerprint=RUN_FP, now=NOW)
    db.documents[("users", "owner", "usage_days", "2026-09-09")]["total_reserved"] = 0
    before = deepcopy(db.documents)
    with pytest.raises(UsageDataError):
        authorize(repo)
    assert db.documents == before
