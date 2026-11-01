"""LibreOffice for every account in one place: a converter VM of the
operator's (since 2026-11-01).

An Office file of the agent's, such as a deck it built with python-pptx,
becomes a PDF and an overview of its first pages, which the agent looks at
to check its work (vm_render_office, agent_vm_tools.py). Before, the agent
installed LibreOffice into its own workbench for that: 73 of the 160
seconds of the first deck in production, and half a gigabyte on every
workbench that ever did, which Sprites bill as storage for as long as it
lies there. Here it lies once. The VM sleeps between conversions, so its
compute costs only while it converts, and no account carries anything.

One Sprite (NAME) for all accounts, the server's own: its tools
(workspace_vm/office: setup.sh, convert.sh, sheet.py) come with a new
VERSION, the setup runs as root, LibreOffice as the user ``office`` without
sudo in a folder of one conversion alone, which goes with every process and
file of that user afterwards (convert.sh). The VM reaches Ubuntu's package
mirrors and nothing else (RULES). A conversion sends the file's bytes on
stdin and reads a tar from stdout; nothing of a file stays on the VM.
"""
from __future__ import annotations

import hashlib
import io
import logging
import tarfile
import threading
from dataclasses import dataclass
from pathlib import Path

from app.core.observability import safe_exception
from app.services import agent_vm

NAME = "consens-office"
DIR = agent_vm.SERVER_HOME + "/.consens/office"
INSTALLED = "/usr/local/lib/consens/office"
CONVERT = INSTALLED + "/convert.sh"
MARKER = INSTALLED + "/VERSION"
FILES = ("setup.sh", "convert.sh", "sheet.py")
_FILES = Path(__file__).resolve().parent / "workspace_vm" / "office"
RULES = [{"domain": domain, "action": "allow"}
         for domain in ("archive.ubuntu.com", "*.archive.ubuntu.com", "security.ubuntu.com", "ports.ubuntu.com")]
# What convert.sh takes; the agent's tool refuses anything else before it reads the file.
EXTENSIONS = frozenset({"pptx", "ppt", "odp", "docx", "doc", "odt", "rtf", "xlsx", "xls", "ods"})
MAX_BYTES = 20 * 1024 * 1024
# The tar back: the PDF, the overview (a few MB) and the page count.
MAX_OUTPUT = 60 * 1024 * 1024
# The overview shows this many pages; the PDF has them all.
OVERVIEW_PAGES = 12
SETUP_SECONDS = 300
CONVERT_SECONDS = 90
# Conversions at once on the one VM (8 cores; LibreOffice takes one or two each).
PARALLEL = 3
# Per account, the operator's cost (agent_vm_tools.render).
RENDERS_PER_HOUR = 30


class OfficeUnavailable(Exception):
    """The converter failed; nothing about the file."""


class OfficeRefused(ValueError):
    """The file is not one LibreOffice turns into a PDF: the agent's to fix."""


@dataclass(frozen=True)
class Rendered:
    pdf: bytes
    overview: bytes
    pages: int


def tool_files():
    """The converter's tools as written there (LF line ends whatever the checkout)."""
    return {name: (_FILES / name).read_bytes().replace(b"\r\n", b"\n") for name in FILES}


def _version():
    digest = hashlib.sha256(b"office\0")
    for name, data in sorted(tool_files().items()):
        digest.update(name.encode() + b"\0" + data + b"\0")
    return digest.hexdigest()[:16]


VERSION = _version()
_ready = None
_setup_lock = threading.Lock()
_slots = threading.BoundedSemaphore(PARALLEL)


def _quiet(stream, chunk):
    pass


def prepare(backend, cancellation):
    """The converter at this VERSION: created where missing, its rules set,
    the tools written and set up when its marker names another version.
    Once per process; a failed setup is tried again by the next call."""
    global _ready
    if _ready == VERSION:
        return
    with _setup_lock:
        if _ready == VERSION:
            return
        backend.ensure(NAME, RULES)
        try:
            raw, _ = backend.read_file(NAME, MARKER, limit=64, agent=False)
        except agent_vm.VMFileMissing:
            raw = b""
        if raw.decode("utf-8", "replace").strip() != VERSION:
            for name, data in tool_files().items():
                backend.write_file(NAME, f"{DIR}/{name}", data, agent=False)
            said = []
            outcome = backend.exec(NAME, f"sudo -n bash {DIR}/setup.sh {VERSION}", cwd=agent_vm.SERVER_HOME,
                                   timeout=SETUP_SECONDS, on_output=lambda stream, chunk: said.append(chunk),
                                   cancellation=cancellation, agent=False)
            if outcome.exit_code != 0:
                logging.warning("Office converter setup failed exit=%s", outcome.exit_code)
                raise OfficeUnavailable("setup failed")
        _ready = VERSION


def _unpack(raw):
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
            parts = {member.name: archive.extractfile(member).read()
                     for member in archive.getmembers() if member.isfile()}
        pages = int(parts.get("pages.txt", b"0").strip() or 0)
        return Rendered(pdf=parts["in.pdf"], overview=parts["pages.png"], pages=pages)
    except (tarfile.TarError, KeyError, ValueError, AttributeError) as exc:
        logging.warning("Office converter answer unreadable category=%s", safe_exception(exc))
        raise OfficeUnavailable("unreadable answer") from None


def render(data, extension, *, cancellation, backend=None):
    """``data`` of an Office file with ``extension`` as a Rendered: its PDF,
    the overview of its first OVERVIEW_PAGES pages (PNG) and its page count.
    OfficeRefused when LibreOffice makes nothing of it, OfficeUnavailable
    when the converter fails; ProviderCancelled on Stop."""
    extension = str(extension or "").lower()
    if extension not in EXTENSIONS:
        raise OfficeRefused(f"Not an Office file the converter takes: .{extension}")
    if len(data) > MAX_BYTES:
        raise OfficeRefused(f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    # A free slot, or the converter counts as busy (never a wait without end).
    if not _slots.acquire(timeout=CONVERT_SECONDS):
        raise OfficeUnavailable("busy")
    own = backend is None
    out, err = bytearray(), bytearray()

    def keep(stream, chunk):
        target = out if stream == "stdout" else err
        if len(target) <= MAX_OUTPUT:
            target.extend(chunk)
    try:
        backend = backend or agent_vm.backend()
        if backend is None:
            raise OfficeUnavailable("no provider")
        prepare(backend, cancellation)
        outcome = backend.run(NAME, ["sudo", "-n", "/bin/bash", CONVERT, extension, str(CONVERT_SECONDS),
                                     str(OVERVIEW_PAGES)],
                              cwd="/", timeout=CONVERT_SECONDS + 60, on_output=keep, cancellation=cancellation,
                              input=bytes(data))
    except agent_vm.VMUnavailable as exc:
        raise OfficeUnavailable(str(exc)) from None
    finally:
        if own and backend is not None:
            backend.close()
        _slots.release()
    if outcome.exit_code in (2, 3):
        raise OfficeRefused(err.decode("utf-8", "replace").strip()[:300] or "LibreOffice could not convert the file.")
    if outcome.exit_code != 0 or outcome.timed_out or len(out) > MAX_OUTPUT:
        logging.warning("Office conversion failed exit=%s timed_out=%s", outcome.exit_code, outcome.timed_out)
        raise OfficeUnavailable("conversion failed")
    return _unpack(bytes(out))
