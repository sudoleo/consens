"""Atomic authorization: admission, consume and claim in one transaction."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from app.services import agent_budget_config, agent_quota, persistence_guard
from app.services.usage_repository import (
    RunKind, RunStatus, TokenAdmission, UsageLimitExceeded,
    UsageOperationConflict, UsageRunConflict, UsageRunExpired, UsageRunReleased,
    canonical_request_fingerprint,
)
from usage_test_support import make_usage_repository


NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
ADMISSION = TokenAdmission(tier="free", mode="consensus", limit=100_000, estimate=30_000,
                           period="2026-09-09", config=agent_budget_config.snapshot({}))
RUN_FP = canonical_request_fingerprint({"question": "question"})
OP_FP = canonical_request_fingerprint({"model": "model"})
LEDGER = ("users", "owner", "chat_state", "agent_tokens_2026-09-09")


def authorize(repo, *, uid="owner", key="run", operation="ask:openai",
              kind=RunKind.REGULAR, admission=ADMISSION, now=NOW,
              run_fp=RUN_FP, op_fp=OP_FP):
    return repo.authorize_operation(
        uid, key, kind, admission, operation, op_fp,
        request_fingerprint=run_fp, now=now,
    )


@pytest.mark.parametrize("kind", [RunKind.REGULAR, RunKind.DEEP_THINK])
def test_direct_run_is_admitted_in_three_reads(kind):
    repo, db = make_usage_repository()
    result, claim = authorize(repo, kind=kind)
    assert db.reads[0] == ("account_deletion_jobs", "owner")
    assert len(db.reads) == len(set(db.reads)) == 3
    assert LEDGER in db.reads
    assert result.status is RunStatus.CONSUMED
    assert result.token_budget["reserved"] == 30_000
    assert claim.idempotent is False


@pytest.mark.parametrize("prepared", ["reserved", "consumed"])
def test_prepared_runs_authorize_in_two_reads_without_the_account(prepared):
    repo, db = make_usage_repository()
    repo.reserve("owner", "run", RunKind.REGULAR, ADMISSION, request_fingerprint=RUN_FP, now=NOW)
    if prepared == "consumed":
        repo.consume("owner", "run")
    before = deepcopy(db.documents[LEDGER])
    db.reads.clear()

    result, claim = authorize(repo)

    assert len(db.reads) == 2 and LEDGER not in db.reads
    assert result.status is RunStatus.CONSUMED and result.token_budget is None
    assert db.documents[LEDGER] == before
    assert claim.idempotent is False


def test_six_provider_fanout_admits_once():
    repo, db = make_usage_repository()
    repo.reserve("owner", "run", RunKind.REGULAR, ADMISSION, request_fingerprint=RUN_FP, now=NOW)
    repo.consume("owner", "run")
    db.reads.clear()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(
            lambda index: authorize(repo, operation=f"ask:provider{index}"), range(6)
        ))
    assert len(db.reads) == 12
    assert all(not claim.idempotent for _, claim in results)
    assert db.documents[LEDGER]["pipeline_runs"] == 1


def test_same_operation_race_has_exactly_one_authorization():
    repo, db = make_usage_repository()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: authorize(repo), range(6)))
    assert sum(not claim.idempotent for _, claim in results) == 1
    assert db.documents[LEDGER]["pipeline_runs"] == 1
    before = deepcopy(db.documents)
    _, repeated = authorize(repo)
    assert repeated.idempotent
    assert db.documents == before


def test_distinct_run_race_cannot_exceed_the_account():
    repo, db = make_usage_repository()

    def attempt(index):
        try:
            authorize(repo, key=f"run-{index}")
            return True
        except UsageLimitExceeded:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        accepted = list(pool.map(attempt, range(12)))
    assert sum(accepted) == 3
    assert agent_quota.held_tokens(db.documents[LEDGER], NOW.timestamp()) == 90_000


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
    repo.reserve("owner", "run", RunKind.REGULAR, ADMISSION, request_fingerprint=RUN_FP, now=NOW)
    repo.release("owner", "run")
    before = deepcopy(db.documents)
    with pytest.raises(UsageRunReleased):
        authorize(repo)
    assert db.documents == before


def test_refused_admission_writes_nothing():
    repo, db = make_usage_repository()
    db.documents[LEDGER] = {"used": 90_000, "revision": 4}
    before = deepcopy(db.documents)
    with pytest.raises(UsageLimitExceeded) as error:
        authorize(repo, kind=RunKind.DEEP_THINK)
    assert error.value.token_budget["remaining"] == 10_000
    assert db.documents == before


def test_owner_isolation_and_utc_rollover():
    repo, db = make_usage_repository()
    authorize(repo)
    other, _ = authorize(repo, uid="other-owner")
    tomorrow_admission = TokenAdmission(tier="free", mode="consensus", limit=100_000, estimate=30_000,
                                        period="2026-09-10", config=ADMISSION.config)
    tomorrow, _ = authorize(repo, key="tomorrow", now=NOW + timedelta(days=1), admission=tomorrow_admission)
    assert other.token_budget["reserved"] == 30_000
    assert tomorrow.token_budget["reserved"] == 30_000
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
