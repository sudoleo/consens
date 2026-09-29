"""Isolated, bounded extraction. Invoked in a disposable subprocess, never a model."""
import io
import json
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_CHARS = 120_000
MAX_PARTS = 120
MAX_INPUT_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 80
# Mode for regular (non-agent) consensus attachments: plain page text up to
# a character budget, read page by page and stopped as soon as it is reached.
PDF_TEXT_MODE = "pdf-text"
PROCESS_TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 800_000
SAFETY_LIMIT_WARNING = "Processing exceeded its safety limits. Provide a smaller file or extracted text."


def run_isolated(raw, mode, *args, timeout=PROCESS_TIMEOUT_SECONDS):
    """Run one extraction in a disposable, resource-limited subprocess.

    CPU time and address space are capped inside the child (see ``main``) and
    the parent enforces a wall-clock timeout, so a hostile or pathological
    file can only exhaust its own process. The child reads the bytes from
    stdin and never writes temporary files.
    """
    try:
        process = subprocess.run([sys.executable, "-m", "app.services.agent_file_extract", mode, *map(str, args)],
            input=raw, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout,
            cwd=str(Path(__file__).resolve().parents[2]), check=True)
        if len(process.stdout) > MAX_RESPONSE_BYTES:
            raise ValueError("Extraction response too large")
        return json.loads(process.stdout)
    except (subprocess.SubprocessError, ValueError):
        return {"status": "failed", "parts": [], "warnings": [SAFETY_LIMIT_WARNING]}


def extract_pdf_text(raw, max_chars):
    """Plain text of the first pages, stopping once ``max_chars`` is reached."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted:
        raise ValueError("Password-protected PDFs are not supported.")
    chunks, total, warnings = [], 0, []
    pages = len(reader.pages)
    if pages > MAX_PDF_PAGES:
        warnings.append(f"Only the first {MAX_PDF_PAGES} PDF pages were processed.")
    for index in range(min(MAX_PDF_PAGES, pages)):
        text = reader.pages[index].extract_text() or ""
        if not text.strip():
            continue
        chunks.append(text)
        total += len(text)
        if total >= max_chars:
            break
    combined = "\n".join(chunks).strip()[:max_chars]
    return {"status": "ready" if combined else "empty", "text": combined, "warnings": warnings}


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
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("File exceeds the extraction limit.")
    mode = sys.argv[1]
    try:
        if mode == PDF_TEXT_MODE:
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 24_000
            result = extract_pdf_text(raw, max(1, min(limit, MAX_CHARS)))
        else:
            result = extract(raw, mode)
    except Exception:
        result = {"parts": [], "warnings": ["File could not be safely read. Export it again or provide text."], "status": "failed"}
    # Write UTF-8 bytes: text-mode stdout uses the console code page on
    # Windows (e.g. cp1252) and would corrupt or crash on non-ASCII text.
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
