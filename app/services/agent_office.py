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
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.observability import safe_exception
from app.services import agent_vm
from app.services.llm.provider_runtime import ProviderCancellation

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
# After a failed setup the converter counts as down this long: every call
# would otherwise run the whole setup again and wait minutes for it.
SETUP_RETRY_SECONDS = 600
# LibreOffice's own limit; convert.sh's other steps take at most 50 s more,
# and the server waits RUN_SECONDS, so the script ends a slow file itself.
CONVERT_SECONDS = 90
RUN_SECONDS = CONVERT_SECONDS + 75
# A wait for a slot or for the setup looks at Stop this often.
WAIT_STEP_SECONDS = 1
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
_failed_at = None
_setup_lock = threading.Lock()
_slots = threading.BoundedSemaphore(PARALLEL)


def _take(lock, cancellation, seconds):
    """``lock`` within ``seconds``, looking at Stop meanwhile; False when it
    stayed taken."""
    deadline = time.monotonic() + seconds
    while True:
        cancellation.raise_if_cancelled()
        left = deadline - time.monotonic()
        if left <= 0:
            return False
        if lock.acquire(timeout=min(WAIT_STEP_SECONDS, left)):
            return True


def prepare(backend, cancellation):
    """The converter at this VERSION: created where missing, its rules set,
    the tools written and set up when its marker names another version.
    Once per process. The setup runs to its end whatever the message does:
    a Stop halfway through apt would leave dpkg broken for every account
    (setup.sh repairs that too). After a failure the converter counts as
    down for SETUP_RETRY_SECONDS."""
    global _ready, _failed_at
    if _ready == VERSION:
        return
    if not _take(_setup_lock, cancellation, SETUP_SECONDS + 30):
        raise OfficeUnavailable("setup busy")
    try:
        if _ready == VERSION:
            return
        if _failed_at is not None and time.monotonic() - _failed_at < SETUP_RETRY_SECONDS:
            raise OfficeUnavailable("setup failed recently")
        backend.ensure(NAME, RULES)
        try:
            raw, _ = backend.read_file(NAME, MARKER, limit=64, agent=False)
        except agent_vm.VMFileMissing:
            raw = b""
        if raw.decode("utf-8", "replace").strip() != VERSION:
            for name, data in tool_files().items():
                backend.write_file(NAME, f"{DIR}/{name}", data, agent=False)
            said = []
            try:
                outcome = backend.exec(NAME, f"sudo -n bash {DIR}/setup.sh {VERSION}", cwd=agent_vm.SERVER_HOME,
                                       timeout=SETUP_SECONDS, on_output=lambda stream, chunk: said.append(chunk),
                                       cancellation=ProviderCancellation(), agent=False)
            except agent_vm.VMUnavailable:
                _failed_at = time.monotonic()
                raise
            if outcome.exit_code != 0:
                _failed_at = time.monotonic()
                logging.warning("Office converter setup failed exit=%s", outcome.exit_code)
                raise OfficeUnavailable("setup failed")
        _ready, _failed_at = VERSION, None
    finally:
        _setup_lock.release()


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
    if not _take(_slots, cancellation, CONVERT_SECONDS):
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
                              cwd="/", timeout=RUN_SECONDS, on_output=keep, cancellation=cancellation,
                              input=bytes(data))
    except agent_vm.VMUnavailable as exc:
        _forget()
        raise OfficeUnavailable(str(exc)) from None
    finally:
        if own and backend is not None:
            backend.close()
        _slots.release()
    if outcome.exit_code in (2, 3, 5):
        # The file's, not the converter's; still worth a line, for a pattern.
        logging.info("Office conversion refused exit=%s", outcome.exit_code)
        raise OfficeRefused(err.decode("utf-8", "replace").strip()[:300] or "LibreOffice could not convert the file.")
    if outcome.exit_code != 0 or outcome.timed_out or len(out) > MAX_OUTPUT:
        logging.warning("Office conversion failed exit=%s timed_out=%s", outcome.exit_code, outcome.timed_out)
        if outcome.exit_code == 127:
            _forget()
        raise OfficeUnavailable("conversion failed")
    return _unpack(bytes(out))


def _forget():
    """A converter that failed this way may be gone or reset (its Sprite
    recreated, convert.sh missing): the next call checks it again."""
    global _ready
    _ready = None
