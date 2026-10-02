"""Shared token admission, debit and release through native Firestore retries."""
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

import pytest
from app.services import agent_budget_config, agent_quota
from app.services.usage_repository import (
    FirestoreUsageRepository, TokenAdmission, RunKind, UsageLimitExceeded,
    UsageTransitionError, RunStatus,
)
from native_support import native_db, race, race_with_worker_retry, tree


def admission(now, *, limit=100, estimate=60):
    return TokenAdmission(tier="free", mode="consensus", limit=limit, estimate=estimate,
        period=now.date().isoformat(), config=agent_budget_config.snapshot({}))


@pytest.fixture(autouse=True)
def separate_workers(monkeypatch):
    # Remove only the optional process-local optimization; SDK retries and every
    # production read/guard/write remain real, like independent server processes.
    monkeypatch.setattr(agent_quota, "account_lock", lambda uid: nullcontext())


def test_native_identical_key_and_booking_are_exactly_once(native_db):
    db, now = native_db, datetime.now(timezone.utc)
    uid, other = db.owner(), db.owner()
    def reserve():
        return FirestoreUsageRepository(db).reserve(uid, "same", RunKind.REGULAR, admission(now), now=now)
    results = race(reserve, reserve)
    assert sorted(result.idempotent for result in results) == [False, True]
    repository = FirestoreUsageRepository(db)
    repository.consume(uid, "same")
    def book():
        return FirestoreUsageRepository(db).book_operation(uid, "same", "consensus", measured=25, estimated=5, final=True, now=now)
    race(book, book)
    ledger = agent_quota.quota_ref(db, uid, admission(now).period).get().to_dict()
    assert ledger["used"] == 25 and ledger["pipeline_estimated"] == 5 and ledger["pipeline_holds"] == {}
    assert not agent_quota.quota_ref(db, other, admission(now).period).get().exists


def test_native_last_allowance_release_and_utc_period(native_db):
    db, now = native_db, datetime.now(timezone.utc)
    uid = db.owner()
    def reserve(key):
        try:
            FirestoreUsageRepository(db).reserve(uid, key, RunKind.REGULAR, admission(now), now=now)
            return key
        except UsageLimitExceeded:
            return None
    winners = [key for key in race(lambda: reserve("first"), lambda: reserve("second")) if key]
    assert len(winners) == 1
    repository = FirestoreUsageRepository(db)
    repository.release(uid, winners[0])
    assert reserve("third") == "third"
    # UTC rollover creates a separate allowance; an old run still books its own day.
    tomorrow = now + timedelta(days=1)
    repository.reserve(uid, "tomorrow", RunKind.REGULAR, admission(tomorrow), now=tomorrow)
    repository.consume(uid, "third")
    repository.book_operation(uid, "third", "consensus", measured=11, estimated=0, final=True, now=tomorrow)
    assert agent_quota.quota_ref(db, uid, admission(now).period).get().to_dict()["used"] == 11
    assert agent_quota.quota_ref(db, uid, admission(tomorrow).period).get().to_dict().get("used", 0) == 0


def test_native_distinct_bookings_preserve_both_charges(native_db):
    db, now, uid = native_db, datetime.now(timezone.utc), native_db.owner()
    repository = FirestoreUsageRepository(db)
    repository.reserve(uid, "shared", RunKind.REGULAR, admission(now), now=now)
    repository.consume(uid, "shared")
    race_with_worker_retry(
        lambda: FirestoreUsageRepository(db).book_operation(uid, "shared", "ask_openai", measured=11, estimated=0, final=False, now=now),
        lambda: FirestoreUsageRepository(db).book_operation(uid, "shared", "ask_anthropic", measured=17, estimated=0, final=False, now=now),
        snapshot=lambda: tree(db.collection("users").document(uid)),
    )
    ledger = agent_quota.quota_ref(db, uid, admission(now).period).get().to_dict()
    assert ledger["used"] == 28
    from app.services.usage_repository import _idempotency_hash
    saved = repository._run_ref(uid, _idempotency_hash("shared")).get().to_dict()
    assert set(saved["booked_operations"]) == {"ask_openai", "ask_anthropic"}
    assert sum(item["measured"] for item in saved["booked_operations"].values()) == 28


def test_native_release_consume_have_one_terminal_winner(native_db):
    db, now = native_db, datetime.now(timezone.utc)
    uid = db.owner()
    FirestoreUsageRepository(db).reserve(uid, "race", RunKind.REGULAR, admission(now), now=now)
    def finish(method):
        try:
            return getattr(FirestoreUsageRepository(db), method)(uid, "race").status
        except UsageTransitionError:
            return None
    results = race(lambda: finish("release"), lambda: finish("consume"))
    assert sum(value is not None for value in results) == 1
    saved = FirestoreUsageRepository(db).get_run(uid, "race", now=now)
    assert saved.status in {RunStatus.RELEASED, RunStatus.CONSUMED}
    holds = agent_quota.quota_ref(db, uid, admission(now).period).get().to_dict()["pipeline_holds"]
    assert bool(holds) == (saved.status is RunStatus.CONSUMED)
