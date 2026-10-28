"""Word attachments (audit 2026-10-28): a parser that refuses every DTD, run in
the disposable subprocess like PDF, once per file content.

Before, a byte search for "<!doctype"/"<!entity" guarded ElementTree in the
web process: a UTF-16 document.xml passed it, expat expanded its entities, and
every family request of a Compare run parsed the file again.
"""

import io
import subprocess
import threading
import uuid
import xml.etree.ElementTree as ET
import zipfile

import pytest

from app.services import agent_file_extract
from app.services.llm import attachments

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def document(body, *, prolog="", encoding="utf-8"):
    declaration = f'<?xml version="1.0" encoding="{encoding.upper()}"?>'
    return (declaration + prolog + f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>').encode(encoding)


def docx(xml):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


ENTITY_BODY = "<w:p><w:r><w:t>&lol;</w:t></w:r></w:p>"
UTF16_ENTITIES = document(ENTITY_BODY, prolog='<!DOCTYPE w:document [<!ENTITY lol "EXPANDED">]>', encoding="utf-16")


def test_a_utf16_dtd_passed_the_old_byte_search():
    # The old guard saw no "<!doctype" bytes, and ElementTree expanded the entity.
    assert b"<!doctype" not in UTF16_ENTITIES.lower() and b"<!entity" not in UTF16_ENTITIES.lower()
    assert "EXPANDED" in ET.tostring(ET.fromstring(UTF16_ENTITIES), encoding="unicode")


@pytest.mark.parametrize("xml", [
    UTF16_ENTITIES,
    document(ENTITY_BODY, prolog='<!DOCTYPE w:document [<!ENTITY lol "EXPANDED">]>'),
    document("<w:p/>", prolog="<!DOCTYPE w:document>"),
    document("<w:p><w:r><w:t>&ext;</w:t></w:r></w:p>",
             prolog='<!DOCTYPE w:document [<!ENTITY ext SYSTEM "file:///etc/passwd">]>'),
    document("<w:p/>", prolog='<!DOCTYPE w:document SYSTEM "http://example.org/word.dtd">'),
])
def test_the_parser_refuses_every_dtd(xml):
    with pytest.raises(ValueError):
        agent_file_extract.parse_xml(xml)
    with pytest.raises(ValueError):
        agent_file_extract.extract(docx(xml), attachments.DOCX_MIME)
    with pytest.raises(ValueError):
        agent_file_extract.extract_docx_text(docx(xml), 1_000)


def test_the_parser_reads_ordinary_word_xml_with_namespaces():
    xml = document('<w:p w:rsidR="00A1"><w:r><w:t xml:space="preserve">Fees &amp; terms</w:t></w:r></w:p>',
                   encoding="utf-16")
    root = agent_file_extract.parse_xml(xml)
    assert root.tag == f"{{{W}}}document"
    paragraph = root.find(f"{{{W}}}body/{{{W}}}p")
    assert paragraph.get(f"{{{W}}}rsidR") == "00A1"
    assert agent_file_extract.extract_docx_text(docx(xml), 1_000)["text"] == "Fees & terms"


def test_a_word_attachment_with_entities_reads_as_unreadable():
    attachment = {"name": "lol.docx", "mime": attachments.DOCX_MIME, "raw": docx(UTF16_ENTITIES)}
    assert attachments.extract_docx_text(attachment["raw"]) is None
    assert "could not be extracted" in attachments.attachment_fallback_text(attachment)


def test_word_text_is_extracted_once_per_file_in_a_subprocess(monkeypatch):
    calls = []
    real_run = subprocess.run

    def spy(args, **kwargs):
        calls.append(args)
        return real_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    marker = uuid.uuid4().hex
    raw = docx(document(f"<w:p><w:r><w:t>Clause {marker}</w:t></w:r></w:p>"))
    results = []
    # Six family requests of one Compare run arrive together.
    threads = [threading.Thread(target=lambda: results.append(attachments.extract_docx_text(raw)))
               for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert results == [f"Clause {marker}"] * 6
    assert len(calls) == 1
    assert calls[0][1:5] == ["-m", "app.services.agent_file_extract", agent_file_extract.DOCX_TEXT_MODE,
                             str(attachments.MAX_TEXT_EXTRACT_CHARS)]


def test_a_failed_extraction_is_not_cached(monkeypatch):
    raw = docx(document(f"<w:p><w:r><w:t>{uuid.uuid4().hex}</w:t></w:r></w:p>"))
    answers = iter([{"status": "failed", "parts": [], "warnings": ["x"]}, {"status": "ready", "text": "Later"}])
    monkeypatch.setattr(agent_file_extract, "run_isolated", lambda *args, **kwargs: next(answers))
    assert attachments.extract_docx_text(raw) is None
    assert attachments.extract_docx_text(raw) == "Later"
    assert attachments.extract_docx_text(raw) == "Later"
