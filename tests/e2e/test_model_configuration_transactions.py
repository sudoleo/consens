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


@pytest.mark.parametrize("existing", [False, True])
def test_native_activation_and_rollback_rpc_failure_is_not_reported_as_restored(native_db, monkeypatch, caplog, existing):
    from google.api_core.exceptions import PermissionDenied
    from app.core import config as cfg, security

    db, ref = native_db, native_db.tracked("app_config")
    if existing:
        ref.set({"revision": 4, "label": "initial"})
    revision = 4 if existing else 0
    before_runtime = cfg._capture_runtime_config()

    # Only redirect the configuration document to this test's unique native ref.
    class ConfigurationDatabase:
        def collection(self, name):
            assert name == "app_config"
            return self
        def document(self, name):
            assert name == "models"
            return ref

    monkeypatch.setattr(admin, "db_firestore", db)
    monkeypatch.setattr(security, "db_firestore", ConfigurationDatabase())
    def fail_activation(*args, **kwargs):
        raise RuntimeError("synthetic activation failure")
    monkeypatch.setattr(cfg, "apply_watch_models", fail_activation)
    original_commit, commits = db._firestore_api.commit, []
    def commit(*args, **kwargs):
        commits.append(kwargs.get("request"))
        if len(commits) == 2:
            raise PermissionDenied("synthetic rollback RPC failure")
        return original_commit(*args, **kwargs)
    monkeypatch.setattr(db._firestore_api, "commit", commit)

    with pytest.raises(RuntimeError, match="synthetic activation failure"):
        admin._persist_and_activate_models(ref, {"openai": ["gpt-5.6"]}, expected_revision=revision)
    assert len(commits) == 2  # Native save succeeded; native rollback RPC failed.
    assert ref.get().to_dict() == {"openai": ["gpt-5.6"], "revision": revision + 1}
    assert cfg._capture_runtime_config() == before_runtime
    assert "activation and persistence rollback both failed" in caplog.text
    assert "synthetic rollback RPC failure" not in caplog.text
