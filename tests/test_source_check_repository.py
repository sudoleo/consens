"""Durable source-check races and complete paginated evidence, without Firestore."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import threading

import pytest

from app.services import persistence_guard
from app.services.source_check_repository import (
    CACHE_COLLECTION, COLLECTION, LEASE_SECONDS, PAGE_PACKAGES,
    SourceCheckNotFound, SourceCheckRepository, SourceCheckResourceGone, SourceCheckRevisionChanged,
    unpack, utcnow,
)


class Snapshot:
    def __init__(self, reference, data):
        self.reference, self.id = reference, reference.id
        self.exists = data is not None
        self._data = deepcopy(data)

    def to_dict(self):
        return deepcopy(self._data)


class Document:
    def __init__(self, db, path):
        self.db, self.path = db, tuple(path)
        self.id = self.path[-1]

    def collection(self, name):
        return Query(self.db, self.path + (name,))

    def get(self, transaction=None, **kwargs):
        if transaction:
            return transaction.get(self)
        with self.db.lock:
            return Snapshot(self, self.db.documents.get(self.path))

    def delete(self, **kwargs):
        with self.db.lock:
            self.db.documents.pop(self.path, None)

    def set(self, data, merge=False, **kwargs):
        with self.db.lock:
            self.db.documents[self.path] = {**(self.db.documents.get(self.path, {}) if merge else {}), **deepcopy(data)}


class Query:
    def __init__(self, db, path, filters=(), order=None, count=None, cursor=None):
        self.db, self.path = db, tuple(path)
        self.filters, self.order, self.count = filters, order, count
        self.cursor = cursor

    def document(self, doc_id):
        return Document(self.db, self.path + (doc_id,))

    def where(self, *, filter):
        return Query(self.db, self.path, self.filters + (filter,), self.order, self.count, self.cursor)

    def order_by(self, field, **kwargs):
        return Query(self.db, self.path, self.filters, field, self.count, self.cursor)

    def limit(self, count):
        return Query(self.db, self.path, self.filters, self.order, count, self.cursor)

    def start_after(self, snapshot):
        return Query(self.db, self.path, self.filters, self.order, self.count, snapshot)

    def stream(self, **kwargs):
        def match(data, condition):
            field, op, right = condition.field_path, condition.op_string, condition.value
            if field not in data:
                return False
            left = data[field]
            if op == "==":
                return left == right
            if op == "!=":
                return left != right
            # Firestore orders null before timestamp values. The due queue
            # must explicitly exclude terminal nulls before applying its limit.
            if left is None or right is None:
                comparison = (left is not None) - (right is not None)
            else:
                comparison = (left > right) - (left < right)
            return {"<": comparison < 0, "<=": comparison <= 0,
                    ">": comparison > 0, ">=": comparison >= 0}[op]

        with self.db.lock:
            rows = [(path, data) for path, data in self.db.documents.items()
                    if path[:-1] == self.path and all(match(data, f) for f in self.filters)]
            if self.order:
                rows.sort(key=lambda row: (row[1].get(self.order) is not None, row[1].get(self.order), row[0]))
            if self.cursor is not None:
                cursor_data = self.cursor.to_dict()
                boundary = (cursor_data.get(self.order), self.cursor.reference.path)
                rows = [row for row in rows if (row[1].get(self.order), row[0]) > boundary]
            if self.count is not None:
                rows = rows[:self.count]
            return iter([Snapshot(Document(self.db, path), data) for path, data in rows])


class Transaction:
    def __init__(self, db):
        self.db, self.writes = db, []

    def get(self, ref):
        assert not self.writes, "Firestore transaction read after write"
        return Snapshot(ref, self.db.documents.get(ref.path))

    def set(self, ref, data, merge=False):
        self.writes.append((ref.path, deepcopy(data), merge))

    def update(self, ref, data):
        assert ref.path in self.db.documents
        self.set(ref, data, True)

    def commit(self):
        for path, data, merge in self.writes:
            self.db.documents[path] = {**(self.db.documents.get(path, {}) if merge else {}), **data}


class FakeDb:
    def __init__(self):
        self.documents, self.lock = {}, threading.RLock()

    def collection(self, name):
        return Query(self, (name,))

    def document(self, path):
        return Document(self, path.split("/"))

    def run_transaction(self, operation):
        with self.lock:
            transaction = Transaction(self)
            result = operation(transaction)
            transaction.commit()
            return result


def make_plan(packages=7):
    parts = []
    for index in range(packages):
        sid = f"S{index % 2 + 1}"
        parts.append({"id": f"package-{index}",
                      "pairs": [{"sentence_id": index + 1, "source_id": sid, "claim": f"Claim {index + 1}."}],
                      "sources": [{"id": sid, "url": f"https://example.test/{sid}", "title": sid}]})
    sources = [{"id": sid, "url": f"https://example.test/{sid}", "title": sid} for sid in ("S1", "S2")]
    return {"question": "Question", "answer_version": "a" * 64, "packages": parts,
            "snapshot": {"schema_version": 3, "answer_version": "a" * 64, "prompt_version": "v3",
                         "sources": sources, "findings": [], "documents": [], "runtime": {"calls": 0},
                         "scope": {"pairs": packages, "checked_pairs": 0, "processed_pairs": 0, "sources": min(2, packages)}}}


def create(repo, *, uid="owner", run_key="run", packages=7, **kwargs):
    return repo.create(uid=uid, run_key=run_key, plan=make_plan(packages), **kwargs)


def package_result(plan, index, *, checked=True):
    package = plan["packages"][index]
    return {"answer_version": plan["answer_version"], "package_id": package["id"],
            "findings": [{**pair, "checked": checked, "support": "supported" if checked else "unknown",
                          "topical": "relevant" if checked else "unknown", "temporal": "not_relevant",
                          "state": "checked" if checked else "unavailable", "reason_code": None if checked else "fetch_timeout",
                          "quotes": ["Exact evidence."] if checked else []} for pair in package["pairs"]],
            "documents": [{"source_id": source["id"], "source_url": source["url"]} for source in package["sources"]] if checked else [],
            "runtime": {"calls": int(checked), "cost": .001 if checked else 0}}


@pytest.fixture
def store():
    db = FakeDb()
    return SourceCheckRepository(db), db


def test_create_is_atomic_idempotent_and_persists_every_package_without_credentials(store):
    repo, db = store
    first = create(repo, packages=40, credential_mode="own")
    second = create(repo, packages=40, credential_mode="own")
    assert first == second
    assert len(db.documents) == 2
    assert len(repo.get_plan(first["job_id"])["packages"]) == 40
    assert first["source_totals"] == {"S1": 20, "S2": 20}
    assert first["snapshot"]["credential_mode"] == "own"
    assert "run" not in first
    assert "findings" not in first["snapshot"]
    assert "sources" not in first["snapshot"]
    for data in db.documents.values():
        content = unpack(data["payload"]) if "payload" in data else data
        assert not any(key in repr(content) for key in ("openrouter_key", "api_keys", "sk-secret"))
    with pytest.raises(TypeError):
        create(repo, api_keys={"openrouter_key": "sk-secret"})


def test_only_one_parallel_worker_claims_and_terminal_packages_are_not_replayed(store):
    repo, _ = store
    job = create(repo, packages=1)
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = list(pool.map(lambda _: repo.claim(job["job_id"]), range(8)))
    assert sum(claim is not None for claim in claims) == 1
    claimed = next(claim for claim in claims if claim)
    result = package_result(repo.get_plan(job["job_id"]), 0)
    assert repo.finish_package(claimed, result)
    assert not repo.finish_package(claimed, result)
    assert repo.claim(job["job_id"]) is None
    assert repo.get(job["job_id"])["snapshot"]["runtime"]["calls"] == 1


def test_expired_lease_reclaims_unfinished_package_and_rejects_stale_worker(store):
    repo, _ = store
    job = create(repo, packages=2)
    now = job["next_attempt_at"]
    first = repo.claim(job["job_id"], now=now)
    assert repo.claim(job["job_id"], now=now + timedelta(seconds=LEASE_SECONDS - 1)) is None
    second = repo.claim(job["job_id"], now=now + timedelta(seconds=LEASE_SECONDS + 1))
    assert second["lease_token"] != first["lease_token"]
    assert second["completed_packages"] == 0
    result = package_result(repo.get_plan(job["job_id"]), 0)
    assert not repo.finish_package(first, result)
    assert not repo.retry(first)
    assert repo.finish_package(second, result)
    assert repo.get(job["job_id"])["completed_packages"] == 1


def test_owner_scope_and_invalid_job_ids_are_not_disclosed(store):
    repo, _ = store
    job = create(repo)
    for call in (lambda: repo.get(job["job_id"], "intruder"),
                 lambda: repo.page(job["job_id"], uid="intruder"),
                 lambda: repo.resume(job["job_id"], "intruder"),
                 lambda: repo.get("../owner")):
        with pytest.raises(SourceCheckNotFound):
            call()
    assert create(repo, uid="other-owner")["job_id"] != job["job_id"]


def test_account_tombstone_fences_creation_claim_finish_and_cache(store):
    repo, db = store
    job = create(repo)
    claimed = repo.claim(job["job_id"])
    db.documents[(persistence_guard.ACCOUNT_DELETION_JOBS_COLLECTION, "owner")] = {"status": "pending"}
    before = deepcopy(db.documents)
    for call in (lambda: create(repo, run_key="another"), lambda: repo.claim(job["job_id"]),
                 lambda: repo.finish_package(claimed, package_result(repo.get_plan(job["job_id"]), 0)),
                 lambda: repo.cache_put("owner", "key", {"value": "evidence"})):
        with pytest.raises(persistence_guard.AccountDeletionInProgress):
            call()
    assert db.documents == before


def test_pagination_covers_every_pending_pair_and_rejects_revision_changes(store):
    repo, _ = store
    job = create(repo, packages=PAGE_PACKAGES * 2 + 1)
    first = repo.page(job["job_id"], uid="owner")
    assert len(first["source_verification"]["findings"]) == PAGE_PACKAGES
    assert all(row["pending"] for row in first["source_verification"]["findings"])
    claimed = repo.claim(job["job_id"])
    repo.finish_package(claimed, package_result(repo.get_plan(job["job_id"]), 0))
    with pytest.raises(SourceCheckRevisionChanged):
        repo.page(job["job_id"], uid="owner", cursor=int(first["next_cursor"]), revision=0)
    findings, cursor = [], 0
    while cursor is not None:
        page = repo.page(job["job_id"], uid="owner", cursor=cursor, revision=2)
        findings += page["source_verification"]["findings"]
        cursor = int(page["next_cursor"]) if page["next_cursor"] is not None else None
    assert [row["sentence_id"] for row in findings] == list(range(1, PAGE_PACKAGES * 2 + 2))
    assert findings[0]["checked"]
    with pytest.raises(ValueError):
        repo.page(job["job_id"], cursor=-1)


def test_progress_counts_sources_only_after_all_their_packages_finish(store):
    repo, _ = store
    job = create(repo, packages=3)
    plan = repo.get_plan(job["job_id"])
    for index in range(3):
        claimed = repo.claim(job["job_id"])
        assert claimed["completed_packages"] == index
        assert repo.finish_package(claimed, package_result(plan, index, checked=index != 2))
        scope = repo.get(job["job_id"])["snapshot"]["scope"]
        if index == 0:
            assert scope["processed_sources"] == 0
        if index == 1:
            assert scope["processed_sources"] == 1
    final = repo.get(job["job_id"])
    assert final["status"] == "partial"
    assert final["snapshot"]["scope"]["processed_pairs"] == 3
    assert final["snapshot"]["scope"]["checked_pairs"] == 2
    assert final["snapshot"]["scope"]["processed_sources"] == 2
    assert final["snapshot"]["scope"]["checked_sources"] == 1
    assert final["snapshot"]["scope"]["unavailable_pairs"] == 1
    assert final["snapshot"]["scope"]["checked_statements"] == 2
    assert final["snapshot"]["scope"]["fetched_sources"] == 2
    assert final["snapshot"]["runtime"]["calls"] == 2


def test_credentials_pause_preserves_work_and_only_owner_can_resume(store):
    repo, _ = store
    job = create(repo, credential_mode="own")
    claimed = repo.claim(job["job_id"])
    assert repo.pause_credentials(claimed)
    assert repo.claim(job["job_id"]) is None
    page = repo.page(job["job_id"], uid="owner")
    assert all(not row["pending"] and row["reason_code"] == "awaiting_credentials"
               for row in page["source_verification"]["findings"])
    assert repo.resume(job["job_id"], "owner")["status"] == "queued"
    assert repo.claim(job["job_id"])["completed_packages"] == 0


def test_due_excludes_terminal_null_timestamps_before_limit(store):
    repo, _ = store
    for index in range(5):
        create(repo, run_key=f"skipped-{index}", packages=0)
    active = create(repo, run_key="active")
    assert [job["job_id"] for job in repo.due(limit=1)] == [active["job_id"]]


def test_owner_deletion_cascades_plans_results_and_cache_and_stale_workers_cannot_resurrect(store):
    repo, db = store
    job = create(repo)
    other = create(repo, uid="other-owner")
    plan = repo.get_plan(job["job_id"])
    first = repo.claim(job["job_id"])
    repo.finish_package(first, package_result(plan, 0))
    second = repo.claim(job["job_id"])
    repo.cache_put("owner", "key", {"text": "private"})
    repo.cache_put("other-owner", "key", {"text": "retained"})
    repo.delete_owner("owner")
    assert not repo.finish_package(second, package_result(plan, 1))
    assert not any(path[:2] == (COLLECTION, job["job_id"]) for path in db.documents)
    assert repo.cache_get("owner", "key") is None
    assert repo.cache_get("other-owner", "key") == {"text": "retained"}
    assert repo.get(other["job_id"])["uid"] == "other-owner"


def test_page_detects_commit_during_assembly(store, monkeypatch):
    repo, db = store
    job = create(repo)
    original = repo.get_plan

    def change_revision(job_id):
        plan = original(job_id)
        db.documents[(COLLECTION, job_id)]["revision"] += 1
        return plan

    monkeypatch.setattr(repo, "get_plan", change_revision)
    with pytest.raises(SourceCheckRevisionChanged):
        repo.page(job["job_id"], uid="owner")


def test_cache_is_owner_partitioned_and_expired_items_are_ignored(store):
    repo, db = store
    repo.cache_put("owner", "document-key", {"text": "private"})
    assert repo.cache_get("intruder", "document-key") is None
    for path, data in db.documents.items():
        if path[0] == CACHE_COLLECTION:
            data["expires_at"] = utcnow() - timedelta(seconds=1)
    assert repo.cache_get("owner", "document-key") is None


def test_deleted_chat_parent_fences_inflight_results_but_retained_bookmark_can_continue(store):
    repo, db = store
    path = "users/owner/chats/chat-1"
    db.document(path).set({"status": "active"})
    job = create(repo, references=[path])
    claimed = repo.claim(job["job_id"])
    plan = repo.get_plan(job["job_id"])
    db.document(path).set({"status": "deleting"})
    with pytest.raises(SourceCheckResourceGone):
        repo.finish_package(claimed, package_result(plan, 0))
    assert repo.get(job["job_id"])["completed_packages"] == 0
    bookmark_path = "users/owner/bookmarks/bookmark-1"
    db.document(bookmark_path).set({"title": "Saved run"})
    repo.retain(job["job_id"], "owner", bookmark_path)
    assert repo.finish_package(claimed, package_result(plan, 0))


def test_cleanup_retains_live_references_and_deletes_unreferenced_results(store):
    repo, db = store
    bookmark_path = "users/owner/bookmarks/bookmark-1"
    db.document(bookmark_path).set({"title": "Saved"})
    retained = create(repo, run_key="saved", references=[bookmark_path])
    expired = create(repo, run_key="orphan")
    old = utcnow() - timedelta(days=1)
    for job in (retained, expired):
        db.documents[(COLLECTION, job["job_id"])]["cleanup_at"] = old
    assert repo.cleanup() == 1
    assert repo.get(retained["job_id"])["cleanup_at"] > old
    with pytest.raises(SourceCheckNotFound):
        repo.get(expired["job_id"])
    assert not any(path[:2] == (COLLECTION, expired["job_id"]) for path in db.documents)


def test_claim_exposes_running_status_and_advances_snapshot_revision(store):
    repo, _ = store
    job = create(repo)
    assert job["snapshot"]["credential_mode"] == "server"
    claimed = repo.claim(job["job_id"])
    assert claimed["status"] == claimed["snapshot"]["status"] == "running"
    assert claimed["revision"] == claimed["snapshot"]["revision"] == 1


def test_repeated_missing_credentials_do_not_consume_worker_crash_attempts(store):
    repo, _ = store
    job = create(repo, credential_mode="own")
    for _ in range(6):
        claimed = repo.claim(job["job_id"])
        assert claimed["attempts"] == 1
        assert repo.pause_credentials(claimed)
        assert repo.get(job["job_id"])["attempts"] == 0
        repo.resume(job["job_id"], "owner")


def test_incomplete_duplicate_or_wrong_package_results_never_lose_planned_pairs(store):
    repo, _ = store
    plan = make_plan(1)
    plan["packages"][0]["pairs"].append({"sentence_id": 2, "source_id": "S1", "claim": "Second claim"})
    plan["snapshot"]["scope"]["pairs"] = 2
    job = repo.create(uid="owner", run_key="multi-pair", plan=plan)
    result = package_result(plan, 0)
    # Duplicate the first finding and omit the second. Both planned rows must
    # be unavailable rather than duplicated, omitted or counted as reviewed.
    result["findings"] = [result["findings"][0], result["findings"][0],
                          {"sentence_id": 99, "source_id": "S99", "checked": True}]
    assert repo.finish_package(repo.claim(job["job_id"]), result)
    page = repo.page(job["job_id"])["source_verification"]
    assert [(row["sentence_id"], row["source_id"]) for row in page["findings"]] == [(1, "S1"), (2, "S1")]
    assert all(row["reason_code"] == "invalid_output" and row["state"] == "unavailable" for row in page["findings"])
    assert page["scope"]["processed_pairs"] == 2
    assert page["scope"]["checked_pairs"] == 0
    assert page["status"] == "partial"


@pytest.mark.parametrize("field,value", [("answer_version", "wrong"), ("package_id", "other-package")])
def test_mismatched_result_identity_cannot_validate_a_source(store, field, value):
    repo, _ = store
    job = create(repo, packages=1)
    result = package_result(repo.get_plan(job["job_id"]), 0)
    result[field] = value
    assert repo.finish_package(repo.claim(job["job_id"]), result)
    page = repo.page(job["job_id"])["source_verification"]
    assert page["scope"]["checked_pairs"] == 0
    assert page["findings"][0]["reason_code"] == "invalid_output"
    assert page["documents"] == []


def test_checked_statement_waits_for_all_its_source_pairs_and_content_version_ignores_fetch_time(store):
    repo, _ = store
    plan = make_plan(2)
    plan["packages"][1]["pairs"][0]["sentence_id"] = 1
    # Both source IDs point at one document, so a second access time must not
    # change its content version or overcount fetched documents.
    plan["packages"][1]["sources"][0]["url"] = "https://example.test/S1"
    job = repo.create(uid="owner", run_key="same-statement", plan=plan)
    versions = []
    for index in range(2):
        result = package_result(plan, index)
        result["documents"][0].update(content_hash="b" * 64, retrieved_at=f"2026-09-0{index + 1}T12:00:00Z")
        assert repo.finish_package(repo.claim(job["job_id"]), result)
        snapshot = repo.get(job["job_id"])["snapshot"]
        assert snapshot["scope"]["checked_statements"] == index
        assert snapshot["scope"]["fetched_sources"] == 1
        versions.append(snapshot["source_version"])
    assert versions[0] == versions[1]


def test_retained_private_share_allows_work_after_chat_deletion_but_revoked_share_does_not(store):
    repo, db = store
    chat = "users/owner/chats/chat-1"
    share = "shares/share-1"
    db.document(chat).set({"status": "active"})
    db.document(share).set({"status": "private", "owner_uid": "owner"})
    job = create(repo, references=[chat, share])
    db.document(chat).delete()
    claimed = repo.claim(job["job_id"])
    assert claimed is not None
    db.document(share).set({"status": "revoked", "owner_uid": "owner"})
    with pytest.raises(SourceCheckResourceGone):
        repo.finish_package(claimed, package_result(repo.get_plan(job["job_id"]), 0))


def test_legacy_bookmark_does_not_need_to_exist_at_enqueue(store):
    repo, _ = store
    job = create(repo, references=["users/owner/bookmarks/to-be-created"])
    assert repo.claim(job["job_id"]) is not None


def test_retain_refuses_deleting_job_and_deleted_resource_and_nested_turn_cannot_bypass_parent(store):
    repo, db = store
    chat = "users/owner/chats/chat-1"
    turn = chat + "/turns/turn-1"
    db.document(chat).set({"status": "active"})
    db.document(turn).set({"status": "pending"})
    job = create(repo, references=[turn])
    db.document(chat).set({"status": "deleting"})
    with pytest.raises(SourceCheckResourceGone):
        repo.claim(job["job_id"])
    with pytest.raises(SourceCheckResourceGone):
        repo.retain(job["job_id"], "owner", turn)
    share = "shares/live"
    db.document(share).set({"status": "private"})
    db.documents[(COLLECTION, job["job_id"])]["status"] = "deleting"
    with pytest.raises(SourceCheckResourceGone):
        repo.retain(job["job_id"], "owner", share)


def test_cleanup_deletion_rechecks_concurrent_retention_and_revoked_references(store):
    repo, db = store
    job = create(repo)
    now = utcnow()
    db.documents[(COLLECTION, job["job_id"])]["cleanup_at"] = now - timedelta(seconds=1)
    share = "shares/live"
    db.document(share).set({"status": "private"})
    repo.retain(job["job_id"], "owner", share)
    assert not repo.delete(job["job_id"], only_if_expired_at=now)
    db.document(share).set({"status": "revoked"})
    db.documents[(COLLECTION, job["job_id"])]["cleanup_at"] = now - timedelta(seconds=1)
    assert repo.cleanup(now=now) == 1



def test_due_snapshot_cursor_covers_ties_after_cursor_document_deleted(store):
    repo, _ = store
    common = utcnow() - timedelta(seconds=1)
    jobs = [create(repo, run_key=f'cursor-{index}', packages=1) for index in range(30)]
    for job in jobs:
        repo.ref(job['job_id']).set({'next_attempt_at': common}, merge=True)
    first, cursor = repo.due_page(limit=24)
    assert len(first) == 24 and cursor is not None
    repo.delete(cursor.id)
    second, end = repo.due_page(limit=24, cursor=cursor)
    assert len(second) == 6 and end is None
    assert len({job['job_id'] for job in first + second}) == 30
