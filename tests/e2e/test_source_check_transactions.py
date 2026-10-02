"""Real queued source jobs: claim takeover, deletion and versioned pagination."""
from datetime import timedelta
import pytest
from app.services.source_check_repository import (
    SourceCheckRepository,
    SourceCheckNotFound,
    SourceCheckRevisionChanged,
    LEASE_SECONDS,
    utcnow,
)
from test_source_check_repository import make_plan, package_result
from native_support import native_db, race_with_worker_retry, tree


def test_native_source_claim_takeover_and_exactly_once_package(native_db):
    db, uid = native_db, native_db.owner()
    repos = [SourceCheckRepository(db, environment="local") for _ in range(2)]
    plan = make_plan(2)
    job = repos[0].create(uid=uid, run_key="native", plan=plan)
    ref = db.tracked(repos[0].collection, job["job_id"])
    now = utcnow()
    claims = race_with_worker_retry(
        *(lambda repo=repo: repo.claim(job["job_id"], now=now) for repo in repos),
        snapshot=lambda: tree(ref)
    )
    old = next(claim for claim in claims if claim)
    assert sum(claim is not None for claim in claims) == 1
    current = repos[1].claim(
        job["job_id"], now=now + timedelta(seconds=LEASE_SECONDS + 1)
    )
    assert current["lease_token"] != old["lease_token"]
    before = tree(ref)
    assert repos[0].finish_package(old, package_result(plan, 0)) is False
    assert tree(ref) == before
    results = race_with_worker_retry(
        *(
            lambda repo=repo: repo.finish_package(current, package_result(plan, 0))
            for repo in repos
        ),
        snapshot=lambda: tree(ref)
    )
    assert sorted(results) == [False, True]
    assert ref.get().to_dict()["completed_packages"] == 1
    assert len(list(ref.collection("packages").stream())) == 1
    next_claim = repos[0].claim(job["job_id"], now=now + timedelta(hours=1))
    repos[1].delete(job["job_id"])
    assert repos[0].finish_package(next_claim, package_result(plan, 1)) is False
    assert tree(ref) == {}


def test_native_source_pagination_pins_revision_and_never_persists_credentials(
    native_db,
):
    db, uid = native_db, native_db.owner()
    repo, plan = SourceCheckRepository(db, environment="local"), make_plan(7)
    job = repo.create(uid=uid, run_key="pages", plan=plan)
    ref = db.tracked(repo.collection, job["job_id"])
    for index in range(7):
        claim = repo.claim(job["job_id"], now=utcnow() + timedelta(seconds=1))
        assert repo.finish_package(claim, package_result(plan, index))
    page = repo.page(job["job_id"], uid=uid)
    assert page["source_verification"]["status"] == "complete"
    findings = list(page["source_verification"]["findings"])
    revision = page["source_verification"]["revision"]
    while page["next_cursor"] is not None:
        page = repo.page(
            job["job_id"], uid=uid, cursor=int(page["next_cursor"]), revision=revision
        )
        findings.extend(page["source_verification"]["findings"])
    assert sorted(finding["sentence_id"] for finding in findings) == list(range(1, 8))
    with pytest.raises(SourceCheckNotFound):
        repo.page(job["job_id"], uid=db.owner())
    with pytest.raises(SourceCheckRevisionChanged):
        repo.page(job["job_id"], uid=uid, revision=-1)
    assert "api_key" not in repr(tree(ref)) and "sk-secret" not in repr(tree(ref))


def test_native_own_key_affinity_uses_only_the_bound_workers_memory(
    native_db, monkeypatch, caplog
):
    from dataclasses import asdict
    from unittest.mock import Mock
    from uuid import uuid4
    from app.services import (
        source_check_jobs as jobs,
        source_check_repository as repository_module,
    )
    from app.services import source_documents, source_verification
    from test_source_check_jobs import doc, judge

    db, uid, foreign_uid = native_db, native_db.owner(), native_db.owner()
    namespace = "audit-affinity-" + uuid4().hex
    for name in ("LOCAL_COLLECTION", "WORKER_COLLECTION", "CACHE_COLLECTION"):
        monkeypatch.setattr(repository_module, name, namespace + "-" + name.lower())
    repos = [SourceCheckRepository(db, environment="local") for _ in range(2)]
    worker_a, worker_b = uuid4().hex, uuid4().hex
    for worker in (worker_a, worker_b):
        db.tracked(repository_module.WORKER_COLLECTION, worker)
    monkeypatch.setattr(jobs, "_repository", repos[0])
    monkeypatch.setattr(jobs, "_keys", {})
    monkeypatch.setattr(jobs, "_scans", {})
    monkeypatch.setattr(jobs, "_heartbeats", {})
    monkeypatch.setattr(jobs, "_active_owners", set())
    monkeypatch.setattr(jobs, "WORKER_ID", worker_a)
    plan = make_plan(1)
    plan["limits"] = asdict(source_verification.Limits())
    repos[0].heartbeat_worker(worker_a)
    job = repos[0].create(
        uid=uid,
        run_key="native-own",
        plan=plan,
        credential_mode="own",
        credential_worker_id=worker_a,
    )
    ref = db.tracked(repos[0].collection, job["job_id"])
    secret = "dummy-private-own-key-" + uuid4().hex
    jobs.remember_key(job["job_id"], uid, secret)
    own_keys = jobs._keys
    assert own_keys[job["job_id"]][1] == secret
    fetch, provider = Mock(side_effect=doc), Mock(side_effect=judge)
    monkeypatch.setattr(source_documents, "fetch_document", fetch)
    monkeypatch.setattr(source_verification, "judge_sources", provider)
    monkeypatch.setattr(
        "app.services.llm.credentials.resolve_developer_api_keys",
        lambda *args: pytest.fail("Own-key work must never use developer credentials"),
    )
    before = tree(ref)
    monkeypatch.setattr(jobs, "WORKER_ID", worker_b)
    monkeypatch.setattr(jobs, "_repository", repos[1])
    monkeypatch.setattr(jobs, "_keys", {})
    assert not jobs.process_one(repos[1])
    assert tree(ref) == before
    with pytest.raises(SourceCheckNotFound):
        jobs.resume_source_check(job["job_id"], foreign_uid, "foreign-dummy-key")
    assert jobs._keys == {} and tree(ref) == before
    fetch.assert_not_called()
    provider.assert_not_called()
    monkeypatch.setattr(jobs, "WORKER_ID", worker_a)
    monkeypatch.setattr(jobs, "_keys", own_keys)
    try:
        assert jobs.process_one(repos[0])
        finished = repos[0].get(job["job_id"])
        assert finished["status"] == "complete"
        assert finished["completed_packages"] == 1 and finished["attempts"] == 0
        assert provider.call_count == 1
        assert provider.call_args.args[1] == {"OpenRouter": secret}
        assert job["job_id"] not in jobs._keys
        assert not jobs.process_one(repos[0])
        assert provider.call_count == 1
    finally:
        # Register only the cache in this test's private collection for cleanup.
        cache = list(db.collection(repository_module.CACHE_COLLECTION).stream())
        for snapshot in cache:
            db.tracked(repository_module.CACHE_COLLECTION, snapshot.id)
    saved = tree(ref)
    saved.update({snapshot.reference.path: snapshot.to_dict() for snapshot in cache})
    for worker in (worker_a, worker_b):
        saved.update(
            tree(db.collection(repository_module.WORKER_COLLECTION).document(worker))
        )
    for data in saved.values():
        if "payload" in data:
            assert secret not in repr(repository_module.unpack(data["payload"]))
    assert secret not in repr(saved) + caplog.text
    assert "foreign-dummy-key" not in repr(saved) + caplog.text
