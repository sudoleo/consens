"""Real queued source jobs: claim takeover, deletion and versioned pagination."""
from datetime import timedelta
import pytest
from app.services.source_check_repository import (
    SourceCheckRepository, SourceCheckNotFound, SourceCheckRevisionChanged, LEASE_SECONDS, utcnow,
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
    claims = race_with_worker_retry(*(lambda repo=repo: repo.claim(job["job_id"], now=now) for repo in repos), snapshot=lambda: tree(ref))
    old = next(claim for claim in claims if claim)
    assert sum(claim is not None for claim in claims) == 1
    current = repos[1].claim(job["job_id"], now=now + timedelta(seconds=LEASE_SECONDS + 1))
    assert current["lease_token"] != old["lease_token"]
    before = tree(ref)
    assert repos[0].finish_package(old, package_result(plan, 0)) is False
    assert tree(ref) == before
    results = race_with_worker_retry(*(lambda repo=repo: repo.finish_package(current, package_result(plan, 0)) for repo in repos), snapshot=lambda: tree(ref))
    assert sorted(results) == [False, True]
    assert ref.get().to_dict()["completed_packages"] == 1
    assert len(list(ref.collection("packages").stream())) == 1
    next_claim = repos[0].claim(job["job_id"], now=now + timedelta(hours=1))
    repos[1].delete(job["job_id"])
    assert repos[0].finish_package(next_claim, package_result(plan, 1)) is False
    assert tree(ref) == {}


def test_native_source_pagination_pins_revision_and_never_persists_credentials(native_db):
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
        page = repo.page(job["job_id"], uid=uid, cursor=int(page["next_cursor"]), revision=revision)
        findings.extend(page["source_verification"]["findings"])
    assert sorted(finding["sentence_id"] for finding in findings) == list(range(1, 8))
    with pytest.raises(SourceCheckNotFound):
        repo.page(job["job_id"], uid=db.owner())
    with pytest.raises(SourceCheckRevisionChanged):
        repo.page(job["job_id"], uid=uid, revision=-1)
    assert "api_key" not in repr(tree(ref)) and "sk-secret" not in repr(tree(ref))
