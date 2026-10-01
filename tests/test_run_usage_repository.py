"""Run-Belege auf dem gemeinsamen Tokenkonto: Admission, Buchung, Idempotenz."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

import app.core.config as cfg
from usage_test_support import FakeFirestore, make_usage_repository
from app.services import agent_budget_config, agent_quota, persistence_guard
from app.services.usage_repository import (
    FirestoreUsageRepository,
    RunKind,
    RunStatus,
    TokenAdmission,
    UsageLimitExceeded,
    UsageRunConflict,
    UsageRunExpired,
    UsageRunNotFound,
    UsageTransitionError,
    canonical_request_fingerprint,
    token_admission,
)


@pytest.fixture
def usage_repo():
    return make_usage_repository()


UTC_NOON = datetime(2026, 7, 18, 12, tzinfo=timezone.utc)
CONFIG = agent_budget_config.snapshot({})
PERIOD = "2026-07-18"


def admission(limit=100_000, estimate=30_000, *, tier="free", mode="consensus", period=PERIOD):
    return TokenAdmission(tier=tier, mode=mode, limit=limit, estimate=estimate, period=period, config=CONFIG)


ADMISSION = admission()


def ledger(db, uid, period=PERIOD):
    return db.documents.get(("users", uid, "chat_state", "agent_tokens_" + period)) or {}


def consumed(repo, uid, key, adm=ADMISSION, kind=RunKind.REGULAR):
    repo.reserve(uid, key, kind, adm, now=UTC_NOON)
    repo.consume(uid, key)


def test_run_quotas_are_gone_from_the_limits_config():
    for key in ("free_consensus_run_limit", "plus_consensus_run_limit", "pro_consensus_run_limit",
                "free_deep_think_run_limit", "pro_deep_think_run_limit"):
        assert key not in cfg.DEFAULT_LIMITS
    assert not hasattr(cfg, "get_consensus_run_limit")
    assert not hasattr(cfg, "get_deep_think_run_limit")
    # A stored legacy value is dropped by the next normalization/backfill.
    assert "free_consensus_run_limit" not in cfg.normalize_limits_config({"free_consensus_run_limit": 12})


def test_token_admission_follows_tier_and_mode():
    db = FakeFirestore()
    free = token_admission(db, "free", mode="compare")
    pro_deep = token_admission(db, "pro", mode="consensus", deep_think=True)
    admin = token_admission(db, "admin", mode=None)
    assert (free.tier, free.mode, free.limit) == ("free", "compare", agent_budget_config.DEFAULT_TIER_LIMITS["free"])
    assert free.estimate == agent_budget_config.DEFAULT_RUN_ESTIMATES["free"]["compare"]
    assert (pro_deep.mode, pro_deep.estimate) == ("deep_think", agent_budget_config.DEFAULT_RUN_ESTIMATES["pro"]["deep_think"])
    # Unknown mode = the larger Consensus run; unknown tier falls back to Free.
    assert admin.mode == "consensus" and admin.limit == agent_budget_config.DEFAULT_TIER_LIMITS["admin"]
    assert token_admission(db, "premium-typo").tier == "free"
    with pytest.raises(ValueError):
        admission(limit=0)
    with pytest.raises(ValueError):
        admission(estimate=True)


def test_production_path_wraps_reserve_in_firestore_transaction(monkeypatch):
    db = FakeFirestore()
    calls = []
    transaction_options = []
    original_transaction = db.transaction

    def capture_transaction(**kwargs):
        transaction_options.append(kwargs)
        return original_transaction(**kwargs)

    db.transaction = capture_transaction

    def fake_transactional(function):
        calls.append("decorated")

        def execute(transaction):
            with db.lock:
                result = function(transaction)
                transaction.commit()
                return result

        return execute

    monkeypatch.setattr(
        "app.services.usage_repository.firestore.transactional", fake_transactional
    )
    repo = FirestoreUsageRepository(db)

    result = repo.reserve("firestore-user", "tx-key", RunKind.REGULAR, ADMISSION, now=UTC_NOON)

    assert calls == ["decorated"]
    assert transaction_options == [{"max_attempts": 12}]
    assert result.token_budget["reserved"] == 30_000
    assert result.token_budget["used"] == 0


def test_admission_needs_the_expected_run_cost_and_holds_it(usage_repo):
    repo, db = usage_repo
    for index in range(3):
        result = repo.reserve("user-1", f"run-{index}", RunKind.REGULAR, ADMISSION, now=UTC_NOON)
        assert result.status is RunStatus.RESERVED

    # 100k limit, 3 x 30k held: 10k left is less than one more typical run.
    with pytest.raises(UsageLimitExceeded) as exc_info:
        repo.reserve("user-1", "run-3", RunKind.REGULAR, ADMISSION, now=UTC_NOON)

    assert exc_info.value.limiting_bucket == "tokens"
    assert exc_info.value.required == 30_000
    assert exc_info.value.token_budget["remaining"] == 10_000
    assert exc_info.value.token_budget["used"] == 0
    assert ledger(db, "user-1")["pipeline_runs"] == 3


def test_parallel_admissions_cannot_oversubscribe_the_account(usage_repo):
    repo, _ = usage_repo

    def reserve(index):
        try:
            repo.reserve("parallel-user", f"parallel-{index}", RunKind.REGULAR, ADMISSION, now=UTC_NOON)
            return "reserved"
        except UsageLimitExceeded:
            return "limited"

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(reserve, range(24)))

    assert results.count("reserved") == 3
    assert results.count("limited") == 21


def test_parallel_same_idempotency_key_admits_only_once(usage_repo):
    repo, db = usage_repo

    def reserve(_):
        return repo.reserve("same-key-user", "one-logical-run", RunKind.REGULAR, ADMISSION, now=UTC_NOON)

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(reserve, range(20)))

    assert sum(not result.idempotent for result in results) == 1
    assert all(result.status is RunStatus.RESERVED for result in results)
    assert agent_quota.held_tokens(ledger(db, "same-key-user"), UTC_NOON.timestamp()) == 30_000


def test_idempotency_is_scoped_by_uid_and_bound_to_run_kind(usage_repo):
    repo, _ = usage_repo
    first = repo.reserve("user-a", "shared-key", RunKind.REGULAR, ADMISSION, now=UTC_NOON)
    repeated = repo.reserve("user-a", "shared-key", RunKind.REGULAR, ADMISSION, now=UTC_NOON)
    other_user = repo.reserve("user-b", "shared-key", RunKind.REGULAR, ADMISSION, now=UTC_NOON)

    assert first.idempotent is False
    assert repeated.idempotent is True
    assert other_user.idempotent is False
    with pytest.raises(UsageRunConflict):
        repo.reserve("user-a", "shared-key", RunKind.DEEP_THINK, ADMISSION, now=UTC_NOON)


def test_consume_is_idempotent_and_changes_no_tokens(usage_repo):
    repo, db = usage_repo
    repo.reserve("consumer", "consume-me", RunKind.REGULAR, ADMISSION, now=UTC_NOON)
    before = deepcopy(ledger(db, "consumer"))

    consumed_run = repo.consume("consumer", "consume-me")
    repeated = repo.consume("consumer", "consume-me")

    assert consumed_run.status is RunStatus.CONSUMED and consumed_run.idempotent is False
    assert repeated.status is RunStatus.CONSUMED and repeated.idempotent is True
    assert ledger(db, "consumer") == before
    with pytest.raises(UsageTransitionError):
        repo.release("consumer", "consume-me")


def test_booking_debits_measured_tokens_once_and_may_overdraw(usage_repo):
    repo, db = usage_repo
    # Bookings report against the tier's current limit from the admin config.
    db.documents[("app_config", "agent_budget")] = {"tier_limits": {"free": 100_000}}
    consumed(repo, "booker", "run")

    first = repo.book_operation("booker", "run", "ask:openai", measured=60_000, estimated=0, now=UTC_NOON)
    repeated = repo.book_operation("booker", "run", "ask:openai", measured=60_000, estimated=0, now=UTC_NOON)
    second = repo.book_operation("booker", "run", "consensus", measured=55_000, estimated=1_000,
                                 final=True, now=UTC_NOON)

    assert first["used"] == repeated["used"] == 60_000
    # Measured beyond the estimate: the account may end below zero.
    assert second["used"] == 115_000 and second["estimated"] == 1_000
    assert second["remaining"] == 0 and second["reserved"] == 0
    data = ledger(db, "booker")
    assert data["pipeline_used"] == 115_000 and data["pipeline_estimated"] == 1_000
    assert agent_quota.spent_tokens(data) > ADMISSION.limit
    run = next(doc for path, doc in db.documents.items() if path[2:3] == ("usage_runs",))
    assert set(run["booked_operations"]) == {"ask:openai", "consensus"}
    # The overdraft blocks the next admission instead of another run.
    with pytest.raises(UsageLimitExceeded):
        repo.reserve("booker", "next", RunKind.REGULAR, admission(estimate=1), now=UTC_NOON)


def test_bookings_shrink_the_hold_and_final_drops_the_rest(usage_repo):
    repo, db = usage_repo
    consumed(repo, "holder", "run")
    epoch = UTC_NOON.timestamp()

    repo.book_operation("holder", "run", "ask:openai", measured=10_000, estimated=0, now=UTC_NOON)
    assert agent_quota.held_tokens(ledger(db, "holder"), epoch) == 20_000
    repo.book_operation("holder", "run", "consensus", measured=5_000, estimated=0, final=True, now=UTC_NOON)
    assert agent_quota.held_tokens(ledger(db, "holder"), epoch) == 0
    assert ledger(db, "holder")["used"] == 15_000


def test_expired_holds_stop_blocking_admissions(usage_repo):
    repo, _ = usage_repo
    for index in range(3):
        repo.reserve("expiry", f"run-{index}", RunKind.REGULAR, ADMISSION, now=UTC_NOON)
    later = UTC_NOON + timedelta(seconds=agent_quota.PIPELINE_HOLD_SECONDS + 1)
    assert repo.reserve("expiry", "run-3", RunKind.REGULAR, ADMISSION, now=later).status is RunStatus.RESERVED


def test_booking_requires_a_consumed_run(usage_repo):
    repo, _ = usage_repo
    with pytest.raises(UsageRunNotFound):
        repo.book_operation("nobody", "missing", "ask:openai", measured=1, estimated=0)
    repo.reserve("reserved-only", "run", RunKind.REGULAR, ADMISSION, now=UTC_NOON)
    with pytest.raises(UsageTransitionError):
        repo.book_operation("reserved-only", "run", "ask:openai", measured=1, estimated=0)
    with pytest.raises(ValueError):
        repo.book_operation("reserved-only", "run", "ask:openai", measured=-1, estimated=0)


def test_release_drops_the_hold_and_is_idempotent(usage_repo):
    repo, db = usage_repo
    repo.reserve("releaser", "release-me", RunKind.REGULAR, ADMISSION, now=UTC_NOON)

    released = repo.release("releaser", "release-me")
    repeated = repo.release("releaser", "release-me")

    assert released.status is RunStatus.RELEASED and released.idempotent is False
    assert repeated.status is RunStatus.RELEASED and repeated.idempotent is True
    assert agent_quota.held_tokens(ledger(db, "releaser")) == 0
    with pytest.raises(UsageTransitionError):
        repo.consume("releaser", "release-me")


def test_agent_and_pipeline_share_one_account(usage_repo):
    repo, db = usage_repo
    key = ("users", "shared", "chat_state", "agent_tokens_" + PERIOD)
    # Agent reserved 80k for a running call: a 30k run no longer fits.
    db.documents[key] = agent_quota.reserve({}, 80_000, limit=100_000)
    with pytest.raises(UsageLimitExceeded):
        repo.reserve("shared", "run", RunKind.REGULAR, ADMISSION, now=UTC_NOON)
    # Agent settled at 20k measured; the run fits and books on the same document.
    db.documents[key] = agent_quota.settle(db.documents[key], 80_000,
                                           {"input_tokens": 15_000, "output_tokens": 5_000})
    consumed(repo, "shared", "run")
    budget = repo.book_operation("shared", "run", "ask:openai", measured=30_000, estimated=0, now=UTC_NOON)
    assert budget["used"] == 50_000
    # Agent's next reservation sees the pipeline's tokens.
    with pytest.raises(agent_quota.AgentTokenBudgetExceeded):
        agent_quota.reserve(db.documents[key], 60_000, limit=100_000)


def test_get_run_is_read_only_and_reports_consumed_status(usage_repo):
    repo, db = usage_repo
    consumed(repo, "reader", "read-me")
    before = {path: dict(data) for path, data in db.documents.items()}

    result = repo.get_run("reader", "read-me", now=UTC_NOON)

    assert result.status is RunStatus.CONSUMED
    assert result.idempotent is True
    assert db.documents == before


def test_consumed_run_context_binding_is_idempotent_and_target_specific(usage_repo):
    repo, db = usage_repo
    consumed(repo, "binder", "bind-me")
    before_ledger = deepcopy(ledger(db, "binder"))

    repo.bind_context_target("binder", "bind-me", "chat-context\0chat-a\0turn-a", now=UTC_NOON)
    first_documents = {path: dict(data) for path, data in db.documents.items()}
    repo.bind_context_target("binder", "bind-me", "chat-context\0chat-a\0turn-a", now=UTC_NOON)

    assert db.documents == first_documents
    assert ledger(db, "binder") == before_ledger
    with pytest.raises(UsageRunConflict):
        repo.bind_context_target("binder", "bind-me", "chat-context\0chat-b\0turn-b", now=UTC_NOON)


@pytest.mark.parametrize("operation", ["reserve", "consume", "claim", "bind", "book"])
def test_pending_account_deletion_fences_every_usage_mutation(usage_repo, operation):
    repo, db = usage_repo
    uid = "deleting-usage-owner"
    key = "logical-run"
    run_fingerprint = canonical_request_fingerprint({"question": "same"})

    if operation != "reserve":
        repo.reserve(uid, key, RunKind.REGULAR, ADMISSION, request_fingerprint=run_fingerprint, now=UTC_NOON)
    if operation in {"claim", "bind", "book"}:
        repo.consume(uid, key)

    db.documents[(persistence_guard.ACCOUNT_DELETION_JOBS_COLLECTION, uid)] = {"status": "pending"}
    before = deepcopy(db.documents)

    with pytest.raises(persistence_guard.AccountDeletionInProgress):
        if operation == "reserve":
            repo.reserve(uid, key, RunKind.REGULAR, ADMISSION, request_fingerprint=run_fingerprint, now=UTC_NOON)
        elif operation == "consume":
            repo.consume(uid, key)
        elif operation == "claim":
            repo.claim_operation(uid, key, "ask:openai", canonical_request_fingerprint({"model": "gpt"}), now=UTC_NOON)
        elif operation == "book":
            repo.book_operation(uid, key, "ask:openai", measured=1, estimated=0, now=UTC_NOON)
        else:
            repo.bind_context_target(uid, key, "chat-context\0chat-a\0turn-a", now=UTC_NOON)

    assert db.documents == before


def test_expired_run_cannot_be_read_or_bound_to_new_context(usage_repo):
    repo, db = usage_repo
    consumed(repo, "expired", "old-run")
    expired_at = UTC_NOON + timedelta(days=1)
    before = {path: dict(data) for path, data in db.documents.items()}

    with pytest.raises(UsageRunExpired):
        repo.get_run("expired", "old-run", now=expired_at)
    with pytest.raises(UsageRunExpired):
        repo.bind_context_target("expired", "old-run", "chat-context\0chat-a\0turn-a", now=expired_at)

    assert db.documents == before


def test_run_records_its_admission_day_and_account_period(usage_repo):
    repo, db = usage_repo
    berlin = timezone(timedelta(hours=2))
    local_after_midnight = datetime(2026, 7, 19, 1, 30, tzinfo=berlin)

    result = repo.reserve("utc-user", "utc-run", RunKind.REGULAR, ADMISSION, now=local_after_midnight)

    assert result.utc_date == "2026-07-18"
    run = next(doc for path, doc in db.documents.items() if path[2:3] == ("usage_runs",))
    assert run["quota_day"] == PERIOD and run["admission_estimate"] == 30_000
    assert run["token_tier"] == "free" and run["admission_mode"] == "consensus"


def test_missing_reservation_cannot_be_consumed_or_released(usage_repo):
    repo, _ = usage_repo
    with pytest.raises(UsageRunNotFound):
        repo.consume("missing-user", "missing")
    with pytest.raises(UsageRunNotFound):
        repo.release("missing-user", "missing")


def test_request_fingerprint_binds_reused_key(usage_repo):
    repo, _ = usage_repo
    first = canonical_request_fingerprint({"question": "first"})
    second = canonical_request_fingerprint({"question": "second"})
    repo.reserve("bound-user", "bound-key", RunKind.REGULAR, ADMISSION, request_fingerprint=first, now=UTC_NOON)

    with pytest.raises(UsageRunConflict):
        repo.reserve("bound-user", "bound-key", RunKind.REGULAR, ADMISSION, request_fingerprint=second, now=UTC_NOON)


def test_authorize_admits_a_legacy_run_and_reads_no_account_for_prepared_runs(usage_repo):
    repo, db = usage_repo
    run_fp = canonical_request_fingerprint({"question": "legacy"})
    op_fp = canonical_request_fingerprint({"provider": "openai"})

    result, claim = repo.authorize_operation("legacy", "direct", RunKind.REGULAR, ADMISSION, "ask:openai", op_fp,
                                             request_fingerprint=run_fp, now=UTC_NOON)
    assert result.status is RunStatus.CONSUMED and claim.idempotent is False
    assert result.token_budget["reserved"] == 30_000

    repo.reserve("prepared", "key", RunKind.REGULAR, ADMISSION, request_fingerprint=run_fp, now=UTC_NOON)
    repo.consume("prepared", "key")
    db.reads.clear()
    result, _ = repo.authorize_operation("prepared", "key", RunKind.REGULAR, ADMISSION, "ask:openai", op_fp,
                                         request_fingerprint=run_fp, now=UTC_NOON)
    assert result.token_budget is None
    assert not any(path[-1].startswith("agent_tokens_") for path in db.reads)


def test_parallel_operation_claim_allows_exactly_one_winner(usage_repo):
    repo, _ = usage_repo
    fingerprint = canonical_request_fingerprint({"question": "same"})
    repo.reserve("claim-user", "claim-key", RunKind.REGULAR, ADMISSION, request_fingerprint=fingerprint, now=UTC_NOON)
    repo.consume("claim-user", "claim-key")
    operation_fingerprint = canonical_request_fingerprint({"model": "gpt"})

    def claim(_):
        return repo.claim_operation("claim-user", "claim-key", "ask:openai", operation_fingerprint, now=UTC_NOON)

    with ThreadPoolExecutor(max_workers=12) as pool:
        claims = list(pool.map(claim, range(24)))

    assert sum(not item.idempotent for item in claims) == 1
    assert sum(item.idempotent for item in claims) == 23


def test_cross_operation_claims_are_independent_and_payload_bound(usage_repo):
    repo, _ = usage_repo
    run_fingerprint = canonical_request_fingerprint({"question": "same"})
    repo.reserve("cross-operation", "claim-key", RunKind.REGULAR, ADMISSION,
                 request_fingerprint=run_fingerprint, now=UTC_NOON)
    repo.consume("cross-operation", "claim-key")
    ask = canonical_request_fingerprint({"provider": "openai"})
    consensus = canonical_request_fingerprint({"engine": "gemini"})

    assert repo.claim_operation("cross-operation", "claim-key", "ask:openai", ask, now=UTC_NOON).idempotent is False
    assert repo.claim_operation("cross-operation", "claim-key", "consensus", consensus, now=UTC_NOON).idempotent is False
    with pytest.raises(UsageRunConflict):
        repo.claim_operation("cross-operation", "claim-key", "ask:openai",
                             canonical_request_fingerprint({"provider": "openai", "changed": True}), now=UTC_NOON)


def test_cross_day_replay_cannot_claim_provider_work(usage_repo):
    repo, _ = usage_repo
    run_fingerprint = canonical_request_fingerprint({"question": "today"})
    repo.reserve("expired-user", "expired-key", RunKind.REGULAR, ADMISSION,
                 request_fingerprint=run_fingerprint, now=UTC_NOON)
    repo.consume("expired-user", "expired-key")
    tomorrow = UTC_NOON + timedelta(days=1)

    with pytest.raises(UsageRunExpired):
        repo.claim_operation("expired-user", "expired-key", "ask:openai",
                             canonical_request_fingerprint({"model": "gpt"}), now=tomorrow)
