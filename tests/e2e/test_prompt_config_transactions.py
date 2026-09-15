"""Prompt revisions are atomic across independent workers in real Firestore."""
from concurrent.futures import ThreadPoolExecutor
import threading
import uuid

from google.cloud import firestore

from app.core.e2e_profile import E2E_PROJECT_ID, assert_safe_e2e_environment
from app.services.prompt_config import PromptConfigConflict, PromptConfigStore, defaults


def test_prompt_configuration_conflict_and_history_are_atomic():
    assert_safe_e2e_environment()
    db = firestore.Client(project=E2E_PROJECT_ID)
    ref = db.collection("app_config").document("prompt-test-" + uuid.uuid4().hex)

    class IsolatedStore(PromptConfigStore):
        def document(self):
            return ref

    gate = threading.Barrier(2)

    def save(editor):
        store = IsolatedStore(db)
        assert store.read()["revision"] == 0
        config = defaults()
        config["prompts"]["agent"] = editor
        gate.wait(timeout=10)
        try:
            return store.save(config, expected_revision=0, updated_by=editor)
        except PromptConfigConflict:
            return None

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, ["editor-a", "editor-b"]))
        winners = [result for result in results if result]
        assert len(winners) == 1
        saved = ref.get().to_dict()
        assert saved == winners[0]
        assert saved["prompts"]["agent"] == saved["updated_by"]
        history = list(ref.collection("revisions").stream())
        assert len(history) == 1
        assert history[0].id == "000000000001" and history[0].to_dict() == saved
        other_worker = IsolatedStore(db)
        assert other_worker.read() == saved
        restored = other_worker.save(defaults(), expected_revision=1, updated_by="editor-c")
        assert restored["revision"] == 2
        assert ref.collection("revisions").document("000000000001").get().to_dict() == saved
        assert ref.collection("revisions").document("000000000002").get().to_dict() == restored
        assert IsolatedStore(db).read() == restored
    finally:
        for revision in ref.collection("revisions").stream():
            revision.reference.delete()
        ref.delete()
        db.close()
