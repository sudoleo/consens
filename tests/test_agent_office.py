"""The converter VM all accounts share (app/services/agent_office.py, since
2026-11-01): LibreOffice once for every account instead of on each
workbench. The VM's scripts are checked as text here and sheet.py with
Pillow; on a Sprite they have not run yet (docs/smoke-checklist.md)."""
import io
import os
import subprocess
import sys
import tarfile

import pytest

os.environ.setdefault("UNIT_TEST_MODE", "1")

from app.services import agent_office, agent_vm
from app.services.agent_vm import ExecOutcome, VMBackend, VMFileMissing, VMUnavailable
from app.services.llm.provider_runtime import ProviderCancellation, ProviderCancelled

PNG = b"\x89PNG\r\n\x1a\n" + b"overview"


def converted(pdf=b"%PDF-1.7 deck", pages=b"8\n", overview=PNG):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w") as archive:
        for name, data in (("in.pdf", pdf), ("pages.png", overview), ("pages.txt", pages)):
            if data is None:
                continue
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return out.getvalue()


class Converter(VMBackend):
    """The converter VM as the server sees it: files, the setup and convert.sh."""

    def __init__(self, *, marker=None, setup_exit=0, answer=None, exit_code=0, stderr=b"", fail=()):
        self.files = {} if marker is None else {agent_office.MARKER: marker}
        self.calls, self.setups, self.runs, self.policy, self.setup_cancellations = [], [], [], None, []
        self.setup_exit, self.answer, self.exit_code, self.stderr, self.fail = (
            setup_exit, converted() if answer is None else answer, exit_code, stderr, set(fail))
        self.closed = False

    def ensure(self, name, rules=None):
        self.calls.append(("ensure", name))
        self.policy = rules
        return False

    def read_file(self, name, path, *, limit, agent=True):
        assert name == agent_office.NAME and agent is False
        if path not in self.files:
            raise VMFileMissing(path)
        return self.files[path][:limit], True

    def write_file(self, name, path, data, *, agent=True):
        assert agent is False
        self.files[path] = data
        return len(data)

    def exec(self, name, command, *, cwd, timeout, on_output, cancellation, agent=True):
        assert agent is False and command.startswith("sudo -n bash ")
        self.setups.append(command)
        self.setup_cancellations.append(cancellation)
        if self.setup_exit == 0:
            self.files[agent_office.MARKER] = command.rsplit(" ", 1)[1].encode() + b"\n"
        return ExecOutcome(exit_code=self.setup_exit, timed_out=False, seconds=60)

    def run(self, name, argv, *, cwd, timeout, on_output, cancellation, input=None):
        if "run" in self.fail:
            raise VMUnavailable("run")
        self.runs.append((name, argv, input))
        on_output("stdout", self.answer)
        if self.stderr:
            on_output("stderr", self.stderr)
        return ExecOutcome(exit_code=self.exit_code, timed_out=False, seconds=3)

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    monkeypatch.setattr(agent_office, "_ready", None)
    monkeypatch.setattr(agent_office, "_failed_at", None)
    # No sweep thread outlives a test (the one that checks it records them).
    monkeypatch.setattr(agent_office, "_sweep_later", lambda backend=None: None)


def test_the_converter_is_set_up_once_per_version_and_reaches_only_ubuntus_mirrors():
    vm = Converter()
    stop = ProviderCancellation()
    rendered = agent_office.render(b"PK deck", "pptx", cancellation=stop, backend=vm)
    assert rendered == agent_office.Rendered(pdf=b"%PDF-1.7 deck", overview=PNG, pages=8)
    # Its tools where only the server writes, then the setup with this version.
    for name in agent_office.FILES:
        assert vm.files[f"{agent_office.DIR}/{name}"] == agent_office.tool_files()[name]
    assert vm.setups == [f"sudo -n bash {agent_office.DIR}/setup.sh {agent_office.VERSION}"]
    # The setup runs to its end whatever the message does: a Stop halfway
    # through apt would leave dpkg broken for every account (review 2026-11-01).
    assert vm.setup_cancellations[0] is not stop
    assert vm.policy == agent_office.RULES and all(rule["action"] == "allow" and "ubuntu.com" in rule["domain"]
                                                   for rule in vm.policy)
    # The file goes in on stdin and the answer comes back on stdout.
    [(name, argv, data)] = vm.runs
    assert name == agent_office.NAME == "consens-office" and data == b"PK deck"
    assert argv == ["sudo", "-n", "/bin/bash", agent_office.CONVERT, "pptx", str(agent_office.CONVERT_SECONDS),
                    str(agent_office.OVERVIEW_PAGES)]
    # The next conversion in this process neither checks nor sets up again.
    agent_office.render(b"PK sheet", "XLSX", cancellation=ProviderCancellation(), backend=vm)
    assert len(vm.setups) == 1 and vm.calls == [("ensure", "consens-office")] and vm.runs[1][1][4] == "xlsx"
    # Another process finds the version in place: no setup.
    agent_office._ready = None
    other = Converter(marker=agent_office.VERSION.encode() + b"\n")
    agent_office.render(b"PK", "docx", cancellation=ProviderCancellation(), backend=other)
    assert other.setups == [] and agent_office.VERSION == agent_office._version()


def test_a_file_libreoffice_cannot_read_is_the_agents_and_a_failure_the_converters(monkeypatch):
    refused = Converter(exit_code=3, answer=b"", stderr=b"LibreOffice could not turn the file into a PDF.\n")
    with pytest.raises(agent_office.OfficeRefused, match="could not turn the file into a PDF"):
        agent_office.render(b"junk", "pptx", cancellation=ProviderCancellation(), backend=refused)
    # Too slow is the file's as well, said as such (exit 5), not "damaged".
    slow = Converter(exit_code=5, answer=b"", stderr=b"LibreOffice took longer than 90 seconds for this file.\n")
    with pytest.raises(agent_office.OfficeRefused, match="took longer than 90 seconds"):
        agent_office.render(b"huge", "pptx", cancellation=ProviderCancellation(), backend=slow)
    for broken in (Converter(exit_code=1, answer=b""), Converter(answer=b"no tar"), Converter(fail={"run"}),
                   Converter(answer=converted(overview=None)), Converter(answer=converted(pages=b"many"))):
        with pytest.raises(agent_office.OfficeUnavailable):
            agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation(), backend=broken)
    # A provider failure or a missing convert.sh (exit 127: the Sprite was
    # recreated) makes the next call check the converter again.
    agent_office._ready = agent_office.VERSION
    with pytest.raises(agent_office.OfficeUnavailable):
        agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation(), backend=Converter(fail={"run"}))
    assert agent_office._ready is None
    agent_office._ready = agent_office.VERSION
    with pytest.raises(agent_office.OfficeUnavailable):
        agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation(),
                            backend=Converter(exit_code=127, answer=b""))
    assert agent_office._ready is None
    # A failed setup is no ready converter, and for SETUP_RETRY_SECONDS no
    # call sets it up again (each would wait minutes); then one does.
    now = [1000.0]
    monkeypatch.setattr(agent_office.time, "monotonic", lambda: now[0])
    failed = Converter(setup_exit=1)
    for _ in range(3):
        with pytest.raises(agent_office.OfficeUnavailable):
            agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation(), backend=failed)
    assert agent_office._ready is None and failed.runs == [] and len(failed.setups) == 1
    now[0] += agent_office.SETUP_RETRY_SECONDS + 1
    failed.setup_exit = 0
    agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation(), backend=failed)
    assert len(failed.setups) == 2 and agent_office._ready == agent_office.VERSION and agent_office._failed_at is None
    # Nothing goes out for a type it does not take or a file too large.
    vm = Converter()
    with pytest.raises(agent_office.OfficeRefused):
        agent_office.render(b"%PDF", "pdf", cancellation=ProviderCancellation(), backend=vm)
    with pytest.raises(agent_office.OfficeRefused):
        agent_office.render(b"x" * (agent_office.MAX_BYTES + 1), "docx", cancellation=ProviderCancellation(),
                            backend=vm)
    assert vm.calls == [] and vm.runs == []


def test_a_stop_ends_the_wait_for_a_place(monkeypatch):
    """All places taken: the wait looks at Stop every WAIT_STEP_SECONDS
    instead of sitting out CONVERT_SECONDS (review 2026-11-01)."""
    import threading
    import time
    monkeypatch.setattr(agent_office, "_slots", threading.BoundedSemaphore(1))
    monkeypatch.setattr(agent_office, "WAIT_STEP_SECONDS", 0.05)
    agent_office._slots.acquire()
    stop = ProviderCancellation()
    threading.Timer(0.2, stop.cancel).start()
    started = time.monotonic()
    with pytest.raises(ProviderCancelled):
        agent_office.render(b"PK", "pptx", cancellation=stop, backend=Converter())
    assert time.monotonic() - started < 5


def test_what_a_conversion_the_server_ended_left_goes_right_after(monkeypatch):
    """Stop or the server's timeout end convert.sh with SIGKILL, and its own
    clean-up never runs (review 2026-11-01): a sweep (convert.sh clean)
    follows in the background, and runs as root without the file."""
    later = []
    monkeypatch.setattr(agent_office, "_sweep_later", lambda backend=None: later.append(backend))
    ready = agent_office.VERSION.encode() + b"\n"

    class Slow(Converter):
        def run(self, name, argv, *, cwd, timeout, on_output, cancellation, input=None):
            self.runs.append((name, argv, input))
            return ExecOutcome(exit_code=137, timed_out=True, seconds=timeout)

    slow = Slow(marker=ready)
    with pytest.raises(agent_office.OfficeUnavailable):
        agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation(), backend=slow)
    assert later == [slow]

    class Stopped(Converter):
        def run(self, name, argv, *, cwd, timeout, on_output, cancellation, input=None):
            raise ProviderCancelled("stopped")

    with pytest.raises(ProviderCancelled):
        agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation(), backend=Stopped(marker=ready))
    # A connection lost mid-conversion leaves LibreOffice running as well.
    with pytest.raises(agent_office.OfficeUnavailable):
        agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation(),
                            backend=Converter(marker=ready, fail={"run"}))
    assert len(later) == 3
    # A finished conversion cleans up after itself: no sweep.
    agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation(), backend=Converter(marker=ready))
    assert len(later) == 3
    # The sweep itself: convert.sh clean; a failure is only logged.
    vm = Converter()
    agent_office.sweep(vm)
    assert vm.runs == [(agent_office.NAME, ["sudo", "-n", "/bin/bash", agent_office.CONVERT, "clean"], None)]
    agent_office.sweep(Converter(fail={"run"}))


def test_a_conversion_takes_no_longer_than_the_answer_has_left():
    """A file shared late in a long run: the conversion ate the answer's
    reserve and the hard stop took the share down with it (review
    2026-11-01). ``seconds`` cuts the run and LibreOffice's own limit; a
    converter still to set up is left to a later call, one set up is used."""
    class Timed(Converter):
        def run(self, name, argv, *, timeout, **kwargs):
            self.timeout = timeout
            return super().run(name, argv, timeout=timeout, **kwargs)
    cold = Timed()
    with pytest.raises(agent_office.OfficeUnavailable, match="no time"):
        agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation(), backend=cold, seconds=60)
    assert cold.setups == [] and cold.runs == [] and agent_office._failed_at is None
    warm = Timed(marker=agent_office.VERSION.encode() + b"\n")
    agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation(), backend=warm, seconds=100)
    [(_, argv, _)] = warm.runs
    assert warm.setups == [] and warm.timeout <= 100
    assert int(argv[5]) == warm.timeout - (agent_office.RUN_SECONDS - agent_office.CONVERT_SECONDS)
    # Without a limit, as before.
    agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation(), backend=warm)
    assert warm.timeout == agent_office.RUN_SECONDS and warm.runs[1][1][5] == str(agent_office.CONVERT_SECONDS)


def test_without_a_provider_the_converter_is_unavailable_and_its_own_backend_closes(monkeypatch):
    monkeypatch.setattr(agent_vm, "backend", lambda: None)
    with pytest.raises(agent_office.OfficeUnavailable):
        agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation())
    vm = Converter()
    monkeypatch.setattr(agent_vm, "backend", lambda: vm)
    agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation())
    assert vm.closed


def test_each_conversion_runs_alone_without_rights_and_leaves_nothing():
    """convert.sh: LibreOffice as its place's own user (no sudo, no home, no
    shell) in a folder of its own with a profile of its own; afterwards that
    user's processes and files go. One user per place: on the live probe of
    2026-11-01 three conversions shared one user, and the first to finish
    ended the other two."""
    files = agent_office.tool_files()
    convert, setup = files["convert.sh"].decode(), files["setup.sh"].decode()
    assert all(b"\r\n" not in data for data in files.values())
    assert "for user in office0 office1 office2; do" in setup
    assert 'useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin "$user"' in setup
    assert 'gpasswd -d "$user" sudo' in setup
    # As many places as the server lets conversions run at once.
    assert f"slots={agent_office.PARALLEL}" in convert
    assert 'exec 9>"/run/consens-office/slot$candidate.lock"' in convert and "flock -n 9" in convert
    assert "user=office$slot" in convert and "exit 4" in convert
    # The locks stay with the script, never with LibreOffice.
    assert '"$@" 8>&- 9>&-' in convert
    # What a conversion killed with SIGKILL left goes before the next file:
    # on every free place (their lock held for the moment, 2026-11-01: the
    # places beyond the first are seldom used) and on its own, then again
    # at the end. Every process of the user goes, also one that keeps forking.
    assert convert.index("user=office$slot") < convert.index("\nclean_free\ncleanup\ntrap cleanup EXIT") \
        < convert.index("dir=$(mktemp")
    assert 'exec 8>"/run/consens-office/slot$other.lock"' in convert
    assert 'if flock -n 8; then clean "office$other"; fi' in convert
    assert 'as_user "$1" kill -s KILL -- -1' in convert
    # convert.sh clean: only that, for the server's sweep after a Stop or timeout.
    assert 'if [ "$ext" = clean ]; then\n  clean_free\n  exit 0\nfi' in convert
    # Each process of a place has at most 2 GB of address space (a conversion
    # takes 0.6 GB, live probe 2026-11-01): one file never takes the memory
    # of all three places.
    assert "memory=2147483648" in convert and 'prlimit --as="$memory" -- setpriv' in convert
    # The page count is written by the place's user, never by root into its folder.
    assert "as_office sh -c 'timeout 10 pdfinfo" in convert and '> "$dir/pages.txt"' not in convert
    # A timeout is said as such (exit 5), and every step together stays
    # below what the server waits, so the script ends a slow file itself.
    assert 'if [ "$status" = 124 ] || [ "$status" = 137 ]; then' in convert and "exit 5" in convert
    assert "timeout 20 pdftoppm" in convert and "timeout 20 /usr/bin/python3" in convert
    assert agent_office.CONVERT_SECONDS + 5 + 10 + 20 + 20 < agent_office.RUN_SECONDS
    for package in ("libreoffice-impress", "libreoffice-writer", "libreoffice-calc", "fonts-crosextra-carlito",
                    "fonts-crosextra-caladea", "fonts-liberation", "poppler-utils", "python3-pil"):
        assert package in setup
    assert "--no-install-recommends" in setup
    # The version last: a setup that broke off is set up again; dpkg left
    # half done by one is finished first, and no package stays on the disk.
    assert setup.rstrip().endswith('> /usr/local/lib/consens/office/VERSION')
    assert setup.index("dpkg --configure -a") < setup.index("apt_get update") < setup.index("apt-get clean")
    assert "install -D -m 0755" in setup and agent_office.CONVERT in setup
    assert 'setpriv --reuid="$who" --regid="$who" --init-groups --no-new-privs' in convert
    assert 'dir=$(mktemp -d /tmp/office.XXXXXXXXXX)' in convert and 'chmod 700 "$dir"' in convert
    assert '"-env:UserInstallation=file://$dir/profile"' in convert
    assert "trap cleanup EXIT" in convert and 'pkill -KILL -u "$1"' in convert
    assert 'find /tmp /var/tmp /dev/shm -xdev -user "$1"' in convert
    # Only the types the server lets through; the rest is the agent's error (exit 2).
    accepted = convert[convert.index('case "$ext" in'):convert.index("esac")]
    assert set(accepted.split("\n")[1].strip().rstrip(") ;").split("|")) == agent_office.EXTENSIONS | {"clean"}
    assert 'timeout --kill-after=5 "$seconds" soffice --headless' in convert
    assert 'tar -C "$dir" -cf - in.pdf pages.png pages.txt' in convert


def test_the_overview_stays_within_what_the_providers_take(tmp_path):
    """sheet.py: a poster or many large pages never make an overview over
    LONGEST pixels (review 2026-11-01: 12 pages of a big custom size passed
    8000 px)."""
    Image = pytest.importorskip("PIL.Image")
    script = agent_office._FILES / "sheet.py"
    for number in range(1, 13):
        Image.new("RGB", (1600, 2400), "white").save(tmp_path / f"page-{number:02d}.png")
    subprocess.run([sys.executable, str(script), str(tmp_path)], check=True)
    sheet = Image.open(tmp_path / "pages.png")
    assert max(sheet.size) == 1568 and sheet.width < sheet.height


def test_the_overview_puts_slides_in_two_columns_and_pages_in_three(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    script = agent_office._FILES / "sheet.py"
    for size, columns in (((533, 300), 2), ((330, 467), 3)):
        folder = tmp_path / f"{size[0]}"
        folder.mkdir()
        for number in range(1, 6):
            Image.new("RGB", size, "white").save(folder / f"page-{number:02d}.png")
        subprocess.run([sys.executable, str(script), str(folder)], check=True)
        sheet = Image.open(folder / "pages.png")
        gap = 12
        assert sheet.width == columns * size[0] + (columns + 1) * gap
        rows = -(-5 // columns)
        assert sheet.height == rows * (size[1] + 16 + gap) + gap
