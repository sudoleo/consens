"""Isolated, bounded extraction. Invoked in a disposable subprocess, never a model."""
import io
import json
import sys
import zipfile
import xml.etree.ElementTree as ET

MAX_CHARS = 120_000
MAX_PARTS = 120


def extract(raw, mime):
    parts, warnings = [], []
    remaining = MAX_CHARS

    def add(locator, text):
        nonlocal remaining
        if not text.strip():
            return
        if remaining <= 0 or len(parts) >= MAX_PARTS:
            if "Extraction limit reached; remaining content was not read." not in warnings:
                warnings.append("Extraction limit reached; remaining content was not read.")
            return
        if len(text) > remaining:
            warnings.append("Text was truncated at the extraction limit.")
        text = text[:remaining]
        # Locators survive splitting, so every excerpt identifies its origin.
        for offset in range(0, len(text), 4000):
            if len(parts) >= MAX_PARTS:
                warnings.append("Extraction limit reached; remaining content was not read.")
                break
            parts.append({"locator": locator, "text": text[offset:offset + 4000]})
        remaining -= len(text)

    if mime == "application/pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw), strict=True)
        if reader.is_encrypted:
            raise ValueError("Password-protected PDFs are not supported.")
        pages = len(reader.pages)
        if pages > 80:
            warnings.append("Only the first 80 PDF pages were processed.")
        empty = []
        for index in range(min(80, pages)):
            if remaining <= 0 or len(parts) >= MAX_PARTS:
                warnings.append("Extraction limit reached; remaining pages were not read.")
                break
            page = reader.pages[index]
            text = (page.extract_text(extraction_mode="layout") or "") if page.get_contents() is not None else ""
            if not text.strip():
                empty.append(index + 1)
            add(f"page {index + 1}", text)
        if empty:
            warnings.append("No extractable text on pages " + ", ".join(map(str, empty)) + ". Scans require visual reading; OCR is not available.")
    elif mime.endswith("wordprocessingml.document"):
        from app.services.llm.attachments import _validate_docx_archive
        _validate_docx_archive(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            xml = archive.read("word/document.xml")
        if b"<!doctype" in xml.lower() or b"<!entity" in xml.lower():
            raise ValueError("XML entities are not allowed.")
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        body = ET.fromstring(xml).find(f"{ns}body")
        if body is None:
            raise ValueError("Word document has no body.")
        for number, node in enumerate(body, 1):
            if node.tag == ns + "tbl":
                rows = [" | ".join("".join(t.text or "" for t in cell.iter(ns + "t"))
                                  for cell in row.findall(ns + "tc")) for row in node.findall(ns + "tr")]
                add(f"table at block {number}", "\n".join(rows))
            else:
                add(f"paragraph {number}", "".join(t.text or "" for t in node.iter(ns + "t")))
        warnings.append("Word headers, footnotes, drawings and embedded images are not extracted; tables retain cell order.")
    elif mime.startswith("image/"):
        from PIL import Image
        with Image.open(io.BytesIO(raw)) as picture:
            picture.verify()
        warnings.append("Visual content is sent only to models with declared image support; no OCR text is available.")
    else:
        lines = raw.decode("utf-8").splitlines()
        for offset in range(0, len(lines), 40):
            add(f"lines {offset + 1}-{min(offset + 40, len(lines))}", "\n".join(lines[offset:offset + 40]))
    return {"parts": parts, "warnings": list(dict.fromkeys(warnings)),
            "status": "partial" if warnings else "ready"}


def main():
    # Apply after imports needed to start Python, before parsing untrusted bytes.
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024,) * 2)
    except ImportError:  # Windows still has the parent's hard wall timeout.
        pass
    raw = sys.stdin.buffer.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError("File exceeds the extraction limit.")
    try:
        result = extract(raw, sys.argv[1])
    except Exception:
        result = {"parts": [], "warnings": ["File could not be safely read. Export it again or provide text."], "status": "failed"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
