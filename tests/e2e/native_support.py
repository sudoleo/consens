"""Native SDK fixtures: fail closed, unique owners, no live credentials/cleanup."""
from concurrent.futures import ThreadPoolExecutor
import os
import threading
import uuid
import warnings

from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore
from google.api_core.exceptions import Aborted
import pytest

from app.core.e2e_profile import E2E_PROJECT_ID, assert_safe_e2e_environment


def race(*operations):
    gate = threading.Barrier(len(operations))
    def run(operation):
        gate.wait(timeout=15)
        return operation()
    with ThreadPoolExecutor(max_workers=len(operations)) as pool:
        return list(pool.map(run, operations))


def race_with_worker_retry(*operations, snapshot):
    """Observe a transient SDK loser, then one explicit next-tick replay.

    Emulator pessimistic lock upgrades can exhaust SDK retries. Preserve that
    outcome instead of changing production retry budgets; only replay after a
    competing worker has completed, exactly as a durable worker's next tick.
    Any other exception remains a test failure. If all attempts abort, their
    persisted state must be unchanged before the explicit next-tick replay.
    """
    def attempt(operation):
        def run():
            try:
                return (False, operation())
            except ValueError as exc:
                if not isinstance(exc.__cause__, Aborted):
                    raise
                return (True, None)
        return run
    before = snapshot()
    outcomes = race(*(attempt(operation) for operation in operations))
    aborted_count = sum(aborted for aborted, value in outcomes)
    if aborted_count:
        warnings.warn(f"Native SDK contention: {aborted_count} aborted worker(s); one explicit settled-state replay", RuntimeWarning)
    if all(aborted for aborted, value in outcomes):
        assert snapshot() == before, "Aborted native transactions left partial writes"
    return [operation() if aborted else value for operation, (aborted, value) in zip(operations, outcomes)]


def tree(ref):
    """Include descendants of missing parent documents, as real Firestore does."""
    result = {}
    snapshot = ref.get()
    if snapshot.exists:
        result[ref.path] = snapshot.to_dict()
    for collection in ref.collections():
        for child in collection.list_documents():
            result.update(tree(child))
    return result


@pytest.fixture
def native_db():
    assert os.environ.get("E2E_TEST_MODE") == "1", "Native tests require the explicit demo profile"
    assert_safe_e2e_environment()
    db = firestore.Client(project=E2E_PROJECT_ID, credentials=AnonymousCredentials())
    roots = []
    def tracked(collection, identifier=None):
        ref = db.collection(collection).document(identifier or uuid.uuid4().hex)
        roots.append(ref)
        return ref
    db.tracked = tracked
    db.owner = lambda: tracked("users", "native-" + uuid.uuid4().hex).id
    try:
        yield db
    finally:
        for ref in reversed(roots):
            for path in sorted(tree(ref), key=lambda value: value.count("/"), reverse=True):
                db.document(path).delete()
        db.close()
