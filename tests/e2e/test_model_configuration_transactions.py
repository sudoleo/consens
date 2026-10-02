"""Model rollback CAS through native SDK; independent process state is explicit."""
from concurrent.futures import ThreadPoolExecutor
import threading
import pytest
from google.cloud import firestore
from app.api.routers import admin
from native_support import native_db


@pytest.mark.parametrize("existing", [False, True])
def test_native_failed_model_activation_preserves_other_writer(native_db, monkeypatch, existing):
    db, ref = native_db, native_db.tracked("app_config")
    if existing:
        ref.set({"revision": 4, "label": "initial"})
    initial_revision = 4 if existing else 0
    monkeypatch.setattr(admin, "db_firestore", db)
    entered, finished = threading.Event(), threading.Event()
    def activate(**kwargs):
        entered.set()
        assert finished.wait(20)
        raise RuntimeError("Synthetic runtime activation failure")
    monkeypatch.setattr(admin, "load_models_from_db", activate)
    def first_writer():
        with pytest.raises(RuntimeError, match="activation failure"):
            admin._persist_and_activate_models(ref, {"label": "A"}, expected_revision=initial_revision)
    def independent_writer():
        assert entered.wait(20)
        try:
            # Separate native transaction, representing a server with independent
            # runtime/lock state; this writes a valid newer config revision.
            @firestore.transactional
            def save(tx):
                current = ref.get(transaction=tx).to_dict()
                assert current["revision"] == initial_revision + 1
                tx.set(ref, {"revision": current["revision"] + 1, "label": "B"})
            save(db.transaction())
        finally:
            finished.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(first_writer), pool.submit(independent_writer)]
        for job in jobs:
            job.result(timeout=30)
    assert ref.get().to_dict() == {"revision": initial_revision + 2, "label": "B"}
    with pytest.raises(admin.ModelConfigConflict):
        admin._persist_and_activate_models(ref, {"label": "stale"}, expected_revision=initial_revision)
