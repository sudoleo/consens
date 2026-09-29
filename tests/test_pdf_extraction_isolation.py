"""R26: regular consensus PDF extraction runs under the Agent file budget.

pypdf never runs in the web process for chat attachments; it runs in the same
disposable, CPU/memory/wall-clock limited subprocess the Agent uses.
"""

import io
import subprocess
import threading

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.services import agent_file_extract
from app.services.llm import attachments


def _pdf_with_text(pages):
    """Tiny valid PDF whose pages carry the given text (Helvetica, one line)."""
    writer = PdfWriter()
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_ref = writer._add_object(font)
    for text in pages:
        page = writer.add_blank_page(600, 800)
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref}),
        })
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def test_normal_pdf_text_is_extracted_in_a_subprocess(monkeypatch):
    calls = []
    real_run = subprocess.run

    def spy(args, **kwargs):
        calls.append((args, kwargs))
        return real_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    text = attachments.extract_pdf_text(_pdf_with_text(["Clause seven applies"]))
    assert text and "Clause seven applies" in text
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[1:4] == ["-m", "app.services.agent_file_extract", agent_file_extract.PDF_TEXT_MODE]
    assert args[4] == str(attachments.MAX_PDF_EXTRACT_CHARS)
    assert kwargs["timeout"] == agent_file_extract.PROCESS_TIMEOUT_SECONDS


def test_blank_or_scanned_pdf_reports_no_text():
    assert attachments.extract_pdf_text(_pdf_with_text([])) is None
    writer = PdfWriter()
    writer.add_blank_page(600, 800)
    out = io.BytesIO()
    writer.write(out)
    assert attachments.extract_pdf_text(out.getvalue()) is None
    assert attachments.extract_pdf_text(b"") is None


def test_malformed_pdf_fails_safely():
    assert attachments.extract_pdf_text(b"%PDF-1.7\nnot really a pdf") is None


def test_char_budget_stops_the_page_loop():
    pages = ["A" * 60 + f" page {index}" for index in range(10)]
    result = agent_file_extract.extract_pdf_text(_pdf_with_text(pages), 100)
    assert result["status"] == "ready"
    assert len(result["text"]) == 100


def test_page_cap_bounds_work_for_many_page_documents():
    pages = [f"p{index}" for index in range(agent_file_extract.MAX_PDF_PAGES + 5)]
    result = agent_file_extract.extract_pdf_text(_pdf_with_text(pages), 1_000_000)
    assert f"p{agent_file_extract.MAX_PDF_PAGES - 1}" in result["text"]
    assert f"p{agent_file_extract.MAX_PDF_PAGES}" not in result["text"].split()
    assert any("first 80" in warning for warning in result["warnings"])


def test_slow_extraction_is_stopped_at_the_wall_clock_budget_and_others_stay_served(monkeypatch):
    """Instrumented slow extraction: the child is killed at its timeout and a
    concurrent extraction in another thread completes normally."""
    real_run = subprocess.run
    slow_started = threading.Event()

    def instrumented(args, **kwargs):
        if kwargs.get("input") == b"%PDF-slow":
            slow_started.set()
            # Stand-in for a pathological page: a child that never finishes.
            return real_run(
                [args[0], "-c", "import time; time.sleep(30)"],
                **{**kwargs, "timeout": 1},
            )
        return real_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", instrumented)
    results = {}
    worker = threading.Thread(
        target=lambda: results.setdefault("slow", attachments.extract_pdf_text(b"%PDF-slow")),
    )
    worker.start()
    assert slow_started.wait(5)
    results["normal"] = attachments.extract_pdf_text(_pdf_with_text(["Still served"]))
    worker.join(10)
    assert not worker.is_alive()
    assert results["slow"] is None
    assert "Still served" in results["normal"]


def test_oversized_child_response_is_rejected(monkeypatch):
    class Done:
        stdout = b"x" * (agent_file_extract.MAX_RESPONSE_BYTES + 1)

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Done())
    result = agent_file_extract.run_isolated(b"%PDF", agent_file_extract.PDF_TEXT_MODE, 10)
    assert result["status"] == "failed"
    assert attachments.extract_pdf_text(b"%PDF") is None


@pytest.mark.parametrize("status", [{"status": "failed", "parts": [], "warnings": ["x"]},
                                    {"status": "empty", "text": ""}])
def test_attachment_fallback_explains_unreadable_pdfs(monkeypatch, status):
    monkeypatch.setattr(agent_file_extract, "run_isolated", lambda *a, **k: status)
    attachment = {"name": "scan.pdf", "mime": "application/pdf", "raw": b"%PDF-1.7"}
    text = attachments.attachment_fallback_text(attachment)
    assert "could not be extracted" in text
