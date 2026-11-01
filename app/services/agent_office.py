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
VERSION, the setup runs as root, LibreOffice as one of the users
``office0``–``office2`` (one per place, without sudo, at most 2 GB of
address space per process) in a folder of one conversion alone, which goes
with every process and file of that user afterwards (convert.sh). What a
conversion the server ended left goes with the next one on any free place
and, right after the end, with sweep. The VM reaches Ubuntu's package
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
from app.services.llm.provider_runtime import ProviderCancellation, ProviderCancelled

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
# A conversion the server ended (Stop, its timeout) may still hold its place
# for a moment: the clean-up after it (sweep) waits this long first.
SWEEP_DELAY_SECONDS = 5
SWEEP_SECONDS = 30


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


def prepare(backend, cancellation, seconds=None):
    """The converter at this VERSION: created where missing, its rules set,
    the tools written and set up when its marker names another version.
    Once per process. The setup runs to its end whatever the message does:
    a Stop halfway through apt would leave dpkg broken for every account
    (setup.sh repairs that too). After a failure the converter counts as
    down for SETUP_RETRY_SECONDS. ``seconds``: what the caller has (render):
    a setup needs SETUP_SECONDS and its conversion RUN_SECONDS more, so with
    less it is left to a later call (OfficeUnavailable)."""
    global _ready, _failed_at
    if _ready == VERSION:
        return
    wait = SETUP_SECONDS + 30 if seconds is None else max(1, min(SETUP_SECONDS + 30, seconds))
    if not _take(_setup_lock, cancellation, wait):
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
            if seconds is not None and seconds < SETUP_SECONDS + RUN_SECONDS:
                raise OfficeUnavailable("no time to set up")
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


def render(data, extension, *, cancellation, backend=None, seconds=None):
    """``data`` of an Office file with ``extension`` as a Rendered: its PDF,
    the overview of its first OVERVIEW_PAGES pages (PNG) and its page count.
    OfficeRefused when LibreOffice makes nothing of it, OfficeUnavailable
    when the converter fails; ProviderCancelled on Stop. ``seconds``: all
    it may take (the answer's time left, agent_vm_tools): the wait for a
    slot and the run are cut to it, LibreOffice's own limit with them, and
    a converter not yet set up at this VERSION is not set up in less time
    than that takes (OfficeUnavailable)."""
    extension = str(extension or "").lower()
    if extension not in EXTENSIONS:
        raise OfficeRefused(f"Not an Office file the converter takes: .{extension}")
    if len(data) > MAX_BYTES:
        raise OfficeRefused(f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    end = None if seconds is None else time.monotonic() + seconds

    def left(most):
        return most if end is None else max(1, min(most, int(end - time.monotonic())))
    # A free slot, or the converter counts as busy (never a wait without end).
    if not _take(_slots, cancellation, left(CONVERT_SECONDS)):
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
        prepare(backend, cancellation, seconds=None if end is None else end - time.monotonic())
        timeout = left(RUN_SECONDS)
        outcome = backend.run(NAME, ["sudo", "-n", "/bin/bash", CONVERT, extension,
                                     str(max(1, min(CONVERT_SECONDS, timeout - (RUN_SECONDS - CONVERT_SECONDS)))),
                                     str(OVERVIEW_PAGES)],
                              cwd="/", timeout=timeout, on_output=keep, cancellation=cancellation,
                              input=bytes(data))
    except agent_vm.VMUnavailable as exc:
        # A connection lost mid-conversion leaves LibreOffice running with
        # the file, as a Stop does (live probe 2026-11-01).
        _forget()
        _sweep_later(None if own else backend)
        raise OfficeUnavailable(str(exc)) from None
    except ProviderCancelled:
        _sweep_later(None if own else backend)
        raise
    finally:
        if own and backend is not None:
            backend.close()
        _slots.release()
    if outcome.exit_code in (2, 3, 5):
        # The file's, not the converter's; still worth a line, for a pattern.
        logging.info("Office conversion refused exit=%s", outcome.exit_code)
        raise OfficeRefused(err.decode("utf-8", "replace").strip()[:300] or "LibreOffice could not convert the file.")
    if outcome.timed_out:
        _sweep_later(None if own else backend)
    if outcome.exit_code != 0 or outcome.timed_out or len(out) > MAX_OUTPUT:
        logging.warning("Office conversion failed exit=%s timed_out=%s", outcome.exit_code, outcome.timed_out)
        if outcome.exit_code == 127:
            _forget()
        raise OfficeUnavailable("conversion failed")
    return _unpack(bytes(out))


def sweep(backend=None):
    """``convert.sh clean``: what a conversion the server ended left on the
    converter goes now. Live probe 2026-11-01: the provider ends convert.sh,
    LibreOffice runs on as the place's user with the file in its folder,
    and the script's own clean-up never runs; the next conversion on that
    place could be days away (privacy policy: the file is deleted there
    right after its conversion). The sweep took 0.6 s. Best effort."""
    own = backend is None
    try:
        backend = backend or agent_vm.backend()
        if backend is None:
            return
        outcome = backend.run(NAME, ["sudo", "-n", "/bin/bash", CONVERT, "clean"], cwd="/", timeout=SWEEP_SECONDS,
                              on_output=lambda stream, chunk: None, cancellation=ProviderCancellation())
        if outcome.exit_code != 0:
            logging.warning("Office converter clean-up failed exit=%s", outcome.exit_code)
    except Exception as exc:
        logging.warning("Office converter clean-up failed category=%s", safe_exception(exc))
    finally:
        if own and backend is not None:
            backend.close()


def _sweep_later(backend=None):
    """sweep in the background, once the ended conversion let go of its place."""
    def later():
        time.sleep(SWEEP_DELAY_SECONDS)
        sweep(backend)
    threading.Thread(target=later, name="office-sweep", daemon=True).start()


def _forget():
    """A converter that failed this way may be gone or reset (its Sprite
    recreated, convert.sh missing): the next call checks it again."""
    global _ready
    _ready = None
