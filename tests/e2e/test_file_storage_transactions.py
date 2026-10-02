"""Cloud object wire + native file quotas, download guard and deletion retry."""
from types import SimpleNamespace
import pytest
from app.services import agent_files
from app.services.chat_store import ChatNotFound
from native_support import native_db, race_with_worker_retry, tree


class Bucket:
    def __init__(self):
        self.data, self.calls = {}, []
        self.fail_put = self.fail_delete = False

    def blob(self, key):
        bucket = self
        class Blob:
            def upload_from_string(self, raw, **kwargs):
                assert kwargs["if_generation_match"] == 0 and kwargs["retry"] is None
                bucket.calls.append(("put", key))
                if bucket.fail_put:
                    raise OSError("Original upload failure")
                assert key not in bucket.data
                bucket.data[key] = raw
            def download_as_bytes(self, **kwargs):
                bucket.calls.append(("get", key))
                return bucket.data[key]
            def delete(self, **kwargs):
                if bucket.fail_delete:
                    raise OSError("Retryable object delete failure")
                bucket.calls.append(("delete", key))
                bucket.data.pop(key, None)
        # No public ACL or URL API is offered: such calls fail this contract.
        return Blob()


def cloud_files(db, monkeypatch):
    bucket = Bucket()
    from google.cloud import storage
    monkeypatch.delenv("AGENT_FILES_LOCAL_DIR", raising=False)
    monkeypatch.setenv("AGENT_FILES_BUCKET", "demo-private-bucket")
    monkeypatch.setattr(storage, "Client", lambda: SimpleNamespace(bucket=lambda name: bucket))
    return agent_files.AgentFiles(db), bucket


def save(files, uid, chat):
    return files.save(uid, chat, raw=b"private fixture", name="../../fixture.txt", mime="text/plain",
        extraction={"status": "ready", "warnings": [], "parts": [{"locator": "line 1", "text": "private fixture"}]})


def test_native_cloud_upload_quota_foreign_download_and_delete_retry(native_db, monkeypatch):
    db, uid = native_db, native_db.owner()
    files, bucket = cloud_files(db, monkeypatch)
    chat = files.chats.create_chat(uid, execution_mode="agent")["id"]
    monkeypatch.setattr(agent_files, "MAX_FILES", 1)
    def upload_worker():
        worker_files = agent_files.AgentFiles(db)
        object_attempts = []
        actual_put = worker_files.objects.put
        def observed_put(*args, **kwargs):
            object_attempts.append(args[0])
            return actual_put(*args, **kwargs)
        monkeypatch.setattr(worker_files.objects, "put", observed_put)
        def upload():
            # A replay is safe only if this worker never reached object I/O.
            # A failed finalization after upload must remain a test failure.
            assert not object_attempts, "Cannot replay an upload after object I/O"
            try:
                return save(worker_files, uid, chat)
            except agent_files.FileUnavailable:
                return None
        return upload
    outcomes = race_with_worker_retry(
        upload_worker(), upload_worker(),
        snapshot=lambda: {"owner": tree(db.collection("users").document(uid)),
                          "objects": dict(bucket.data), "calls": list(bucket.calls)},
    )
    saved = next(value for value in outcomes if value)
    assert sum(value is not None for value in outcomes) == 1
    assert len([call for call in bucket.calls if call[0] == "put"]) == 1
    assert len(bucket.data) == 1
    assert files.quota_ref(uid).get().to_dict() == {"count": 1, "bytes": 15}
    assert files.download(uid, chat, saved["id"])[1] == b"private fixture"
    before_calls = list(bucket.calls)
    with pytest.raises(ChatNotFound):
        files.download(db.owner(), chat, saved["id"])
    assert bucket.calls == before_calls
    bucket.fail_delete = True
    with pytest.raises(OSError, match="Retryable"):
        files.delete(uid, chat, saved["id"])
    assert files.ref(uid, chat, saved["id"]).get().to_dict()["status"] == "deleting"
    assert files.quota_ref(uid).get().to_dict()["count"] == 1
    bucket.fail_delete = False
    agent_files.AgentFiles(db).delete(uid, chat, saved["id"], cleanup=True)
    assert files.quota_ref(uid).get().to_dict() == {"count": 0, "bytes": 0}
    assert not files.ref(uid, chat, saved["id"]).get().exists and bucket.data == {}


def test_native_failed_cloud_upload_preserves_original_error_and_retry_cleans(native_db, monkeypatch):
    db, uid = native_db, native_db.owner()
    files, bucket = cloud_files(db, monkeypatch)
    chat = files.chats.create_chat(uid, execution_mode="agent")["id"]
    bucket.fail_put = bucket.fail_delete = True
    with pytest.raises(OSError, match="Original upload failure"):
        save(files, uid, chat)
    refs = list(files.chats._chat_ref(uid, chat).collection("files").stream())
    assert len(refs) == 1 and refs[0].to_dict()["status"] == "deleting"
    bucket.fail_put = bucket.fail_delete = False
    agent_files.AgentFiles(db).cleanup_chat(uid, chat)
    assert list(files.chats._chat_ref(uid, chat).collection("files").stream()) == []
    assert files.quota_ref(uid).get().to_dict() == {"count": 0, "bytes": 0}


def test_native_cloud_document_versions_are_immutable_and_cascade_retries(native_db, monkeypatch):
    from app.services.agent_documents import CreateDocument, ReadDocument, ReviseDocument
    from app.services.llm.provider_runtime import ProviderCancellation
    from test_agent_documents import service, sample
    db, uid = native_db, native_db.owner()
    files, bucket = cloud_files(db, monkeypatch)
    chat = files.chats.create_chat(uid, execution_mode="agent")["id"]
    documents = service(files, chat, uid=uid)
    created = documents.create(CreateDocument.model_validate(sample()), cancellation=ProviderCancellation())
    assert created["version"] == 1 and len(created["files"]) == 2
    before = tree(documents.ref(created["document_id"]))
    revised = service(files, chat, turn="second", uid=uid).revise(ReviseDocument(
        document_id=created["document_id"], version=1, section_number=2,
        replacement={"heading": "Revised plan", "paragraphs": ["Review on Monday."]}, change_summary="Update plan"),
        cancellation=ProviderCancellation())
    assert revised["version"] == 2
    old_path = documents.ref(created["document_id"]).collection("versions").document("1").path
    assert tree(documents.ref(created["document_id"]))[old_path] == before[old_path]
    assert files.quota_ref(uid).get().to_dict()["count"] == 4
    bucket.fail_delete = True
    assert files.chats.delete_chat(uid, chat) is False
    assert documents.ref(created["document_id"]).collection("versions").document("1").get().exists
    bucket.fail_delete = False
    assert agent_files.ChatStore(db).run_chat_deletion(uid, chat)
    assert bucket.data == {} and tree(files.chats._chat_ref(uid, chat)) == {}
    assert files.quota_ref(uid).get().to_dict() == {"count": 0, "bytes": 0}
