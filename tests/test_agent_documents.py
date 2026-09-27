import io
from types import SimpleNamespace
import pytest
from docx import Document
from pypdf import PdfReader
from app.services.agent_documents import CreateDocument, DocumentTools, ReadDocument, ReviseDocument
from app.services.agent_files import FileContext, FileUnavailable
from app.services.llm.provider_runtime import ProviderCancellation
from test_agent_files import setup, upload


def sample():
    return {"document": {"title": "Decision brief", "summary": "Evaluate the two vendor offers.",
        "sections": [{"heading": "Comparison", "paragraphs": ["Vendor A is cheaper; vendor B ships sooner."],
            "table": {"headers": ["Vendor", "Price", "Delivery"], "rows": [["A", "42 EUR", "2 weeks"], ["B", "55 EUR", "1 week"]]}},
            {"heading": "Action plan", "paragraphs": ["Confirm delivery with procurement."]}],
        "uncertainties": ["Tax treatment is unconfirmed."], "differing_views": ["Model B prioritizes delivery over price."]}}


def service(files, chat, turn="first", uid="owner"):
    return DocumentTools(SimpleNamespace(file_context=FileContext(files, uid, chat, []), uid=uid, chat_id=chat, turn_id=turn))


def test_real_docx_pdf_version_and_saved_provenance(setup):
    files, chat = setup
    source = upload(files, chat)
    args = sample(); args["document"]["sources"] = [{"label": "Vendor quote", "file_id": source["id"], "locator": "lines 1-2"}]
    docs = service(files, chat)
    created = docs.create(CreateDocument.model_validate(args), cancellation=ProviderCancellation())
    assert len(created["files"]) == 2
    for f in created["files"]:
        meta, raw = files.download("owner", chat, f["id"])
        assert meta["turn_id"] == "first" and meta["source_file_ids"] == [source["id"]]
        if f["mime"] == "application/pdf":
            pdf = PdfReader(io.BytesIO(raw), strict=True)
            text = "\n".join(p.extract_text() for p in pdf.pages)
            assert "Tax treatment" in text and "Model B prioritizes" in text and "42 EUR" in text
        else:
            document = Document(io.BytesIO(raw))
            assert document.tables[0].cell(1, 1).text == "42 EUR"
    saved = docs.read(ReadDocument(document_id=created["document_id"]), cancellation=ProviderCancellation())
    assert saved["sources"][0]["sha256"] == source["sha256"]
    assert saved["content_hash"] == created["content_hash"]
    repeat = docs.create(CreateDocument.model_validate(args), cancellation=ProviderCancellation())
    assert repeat["files"] == created["files"] and len(files.list("owner", chat)) == 3
    revision = service(files, chat, "followup").revise(ReviseDocument(document_id=created["document_id"], version=1,
        section_number=2, replacement={"heading": "Revised plan", "paragraphs": ["Contact vendor B on Monday."]}, change_summary="Revised section two"), cancellation=ProviderCancellation())
    assert revision["version"] == 2 and revision["parent_version"] == 1
    latest = docs.read(ReadDocument(document_id=created["document_id"]), cancellation=ProviderCancellation())
    original = docs.read(ReadDocument(document_id=created["document_id"], version=1), cancellation=ProviderCancellation())
    assert original["content"]["sections"][1]["heading"] == "Action plan"
    assert latest["content"]["sections"][1]["heading"] == "Revised plan"
    assert latest["content"]["sections"][0] == original["content"]["sections"][0]
    assert latest["content"]["uncertainties"] == original["content"]["uncertainties"]
    with pytest.raises(FileUnavailable, match="newer"):
        docs.revise(ReviseDocument(document_id=created["document_id"], version=1, section_number=2,
            replacement={"heading": "Stale", "paragraphs": []}, change_summary="stale edit"), cancellation=ProviderCancellation())


def test_ownership_invalid_sources_and_storage_failure(setup, monkeypatch):
    from app.services.chat_store import ChatNotFound
    files, chat = setup
    docs = service(files, chat)
    created = docs.create(CreateDocument.model_validate(sample()), cancellation=ProviderCancellation())
    with pytest.raises(ChatNotFound):
        service(files, chat, uid="other").read(ReadDocument(document_id=created["document_id"]), cancellation=ProviderCancellation())
    other_chat = files.chats.create_chat("owner", execution_mode="agent")["id"]
    with pytest.raises(FileUnavailable):
        service(files, other_chat).read(ReadDocument(document_id=created["document_id"]), cancellation=ProviderCancellation())
    args = sample(); args["document"]["sources"] = [{"label": "Missing", "file_id": "a" * 32}]
    with pytest.raises(FileUnavailable):
        docs.create(CreateDocument.model_validate(args), cancellation=ProviderCancellation())
    real_put = files.objects.put; calls = []
    def fail_second(key, raw, mime):
        calls.append(key)
        if len(calls) == 2:
            raise OSError("Storage unavailable")
        real_put(key, raw, mime)
    monkeypatch.setattr(files.objects, "put", fail_second)
    before = files.list("owner", chat)
    with pytest.raises(OSError):
        service(files, chat, "failed").create(CreateDocument.model_validate(sample()), cancellation=ProviderCancellation())
    assert files.list("owner", chat) == before
    with pytest.raises(FileUnavailable):
        files.objects.get(calls[0])


def test_limits_unsupported_glyphs_and_cancellation(setup):
    from pydantic import ValidationError
    from app.services.llm.provider_runtime import ProviderCancelled
    files, chat = setup
    args = sample(); args["document"]["sections"][0]["paragraphs"] = ["a" * 40_000]
    with pytest.raises(ValidationError): CreateDocument.model_validate(args)
    args = sample(); args["document"]["sources"] = [{"label": "Bad", "url": "javascript:alert(1)"}]
    with pytest.raises(ValidationError): CreateDocument.model_validate(args)
    args = sample(); args["document"]["title"] = "Unsupported \U0001f999"
    with pytest.raises(FileUnavailable, match="rendering"):
        service(files, chat).create(CreateDocument.model_validate(args), cancellation=ProviderCancellation())
    cancelled = ProviderCancellation(); cancelled.cancel()
    with pytest.raises(ProviderCancelled):
        service(files, chat).create(CreateDocument.model_validate(sample()), cancellation=cancelled)
    assert not files.list("owner", chat)


def test_synthesis_keeps_actual_document_results(setup):
    from test_agent_comparison import Script, make_loop
    from app.services.agent_runs import AgentRunStore
    files, _ = setup
    loop = make_loop(AgentRunStore(files.db), Script())
    loop.documents = SimpleNamespace(results=[{"title": "Decision", "files": [{"id": "a" * 32}]}])
    messages = loop.comparison.synthesis_messages(loop.answer_conversation)
    assert '"saved_documents"' in messages[-1]["content"] and '"Decision"' in messages[-1]["content"]
