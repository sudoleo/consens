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
from app.services.llm.provider_runtime import ProviderCancellation

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
        self.calls, self.setups, self.runs, self.policy = [], [], [], None
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


def test_the_converter_is_set_up_once_per_version_and_reaches_only_ubuntus_mirrors():
    vm = Converter()
    rendered = agent_office.render(b"PK deck", "pptx", cancellation=ProviderCancellation(), backend=vm)
    assert rendered == agent_office.Rendered(pdf=b"%PDF-1.7 deck", overview=PNG, pages=8)
    # Its tools where only the server writes, then the setup with this version.
    for name in agent_office.FILES:
        assert vm.files[f"{agent_office.DIR}/{name}"] == agent_office.tool_files()[name]
    assert vm.setups == [f"sudo -n bash {agent_office.DIR}/setup.sh {agent_office.VERSION}"]
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


def test_a_file_libreoffice_cannot_read_is_the_agents_and_a_failure_the_converters():
    refused = Converter(exit_code=3, answer=b"", stderr=b"LibreOffice could not turn the file into a PDF.\n")
    with pytest.raises(agent_office.OfficeRefused, match="could not turn the file into a PDF"):
        agent_office.render(b"junk", "pptx", cancellation=ProviderCancellation(), backend=refused)
    for broken in (Converter(exit_code=1, answer=b""), Converter(answer=b"no tar"), Converter(fail={"run"}),
                   Converter(answer=converted(overview=None)), Converter(answer=converted(pages=b"many"))):
        with pytest.raises(agent_office.OfficeUnavailable):
            agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation(), backend=broken)
    # A failed setup is no ready converter: the next call tries again.
    agent_office._ready = None
    failed = Converter(setup_exit=1)
    with pytest.raises(agent_office.OfficeUnavailable):
        agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation(), backend=failed)
    assert agent_office._ready is None and failed.runs == []
    # Nothing goes out for a type it does not take or a file too large.
    vm = Converter()
    with pytest.raises(agent_office.OfficeRefused):
        agent_office.render(b"%PDF", "pdf", cancellation=ProviderCancellation(), backend=vm)
    with pytest.raises(agent_office.OfficeRefused):
        agent_office.render(b"x" * (agent_office.MAX_BYTES + 1), "docx", cancellation=ProviderCancellation(),
                            backend=vm)
    assert vm.calls == [] and vm.runs == []


def test_without_a_provider_the_converter_is_unavailable_and_its_own_backend_closes(monkeypatch):
    monkeypatch.setattr(agent_vm, "backend", lambda: None)
    with pytest.raises(agent_office.OfficeUnavailable):
        agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation())
    vm = Converter()
    monkeypatch.setattr(agent_vm, "backend", lambda: vm)
    agent_office.render(b"PK", "pptx", cancellation=ProviderCancellation())
    assert vm.closed


def test_each_conversion_runs_alone_without_rights_and_leaves_nothing():
    """convert.sh: LibreOffice as `office` (no sudo, no home, no shell) in a
    folder of its own with a profile of its own, so conversions run side by
    side; afterwards that user's processes and files go."""
    files = agent_office.tool_files()
    convert, setup = files["convert.sh"].decode(), files["setup.sh"].decode()
    assert all(b"\r\n" not in data for data in files.values())
    assert "useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin office" in setup
    assert "gpasswd -d office sudo" in setup
    for package in ("libreoffice-impress", "libreoffice-writer", "libreoffice-calc", "fonts-crosextra-carlito",
                    "fonts-crosextra-caladea", "fonts-liberation", "poppler-utils", "python3-pil"):
        assert package in setup
    assert "--no-install-recommends" in setup
    # The version last: a setup that broke off is set up again.
    assert setup.rstrip().endswith('> /usr/local/lib/consens/office/VERSION')
    assert "install -D -m 0755" in setup and agent_office.CONVERT in setup
    assert "setpriv --reuid=office --regid=office --init-groups --no-new-privs" in convert
    assert 'dir=$(mktemp -d /tmp/office.XXXXXXXXXX)' in convert and 'chmod 700 "$dir"' in convert
    assert '"-env:UserInstallation=file://$dir/profile"' in convert
    assert "trap cleanup EXIT" in convert and "pkill -KILL -u office" in convert
    assert "find /tmp /var/tmp /dev/shm -xdev -user office" in convert
    # Only the types the server lets through; the rest is the agent's error (exit 2).
    accepted = convert[convert.index('case "$ext" in'):convert.index("esac")]
    assert set(accepted.split("\n")[1].strip().rstrip(") ;").split("|")) == agent_office.EXTENSIONS
    assert 'timeout --kill-after=5 "$seconds" soffice --headless' in convert
    assert 'tar -C "$dir" -cf - in.pdf pages.png pages.txt' in convert


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
