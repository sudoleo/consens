import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


def _load():
    path = Path(__file__).resolve().parents[1] / "scripts" / "pre_commit.py"
    spec = importlib.util.spec_from_file_location("pre_commit", path)
    module = importlib.util.module_from_spec(spec)
    # dataclass resolves the string annotations through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pc = _load()
FAIL = [sys.executable, "-c", "import sys; print('out of date'); sys.exit(1)"]
PASS = [sys.executable, "-c", "pass"]


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    config = tmp_path / "gitconfig"
    config.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "test@example.com")
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    for name in ("static/js/app.js", "templates/index.html", "docs/notes.md"):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("start\n")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "init")
    return root


def _commands(monkeypatch, build, i18n):
    ran = []

    def command(check, root):
        ran.append(check.name)
        return build if check is pc.BUILD else i18n

    monkeypatch.setattr(pc, "command", command)
    return ran


@pytest.mark.parametrize(
    "path, expected",
    [
        ("static/js/app.js", {"build", "i18n"}),
        ("static/css/shell.css", {"build", "i18n"}),
        ("package-lock.json", {"build"}),
        ("scripts/vendor_frontend.mjs", {"build"}),
        ("app/api/routers/chat.py", {"i18n"}),
        ("app/i18n/de/app.json", {"i18n"}),
        ("main.py", {"i18n"}),
        ("docs/notes.md", set()),
        ("tests/static/x.js", set()),
    ],
)
def test_each_check_runs_only_for_files_it_reads(path, expected):
    assert {check.name for check in pc.CHECKS if pc.touches(check, [path])} == expected


def test_a_failing_check_blocks_the_commit_it_is_about(repo, monkeypatch, capsys):
    ran = _commands(monkeypatch, build=FAIL, i18n=PASS)
    (repo / "static/js/app.js").write_text("changed\n")
    _git(repo, "add", "static/js/app.js")

    assert pc.main(repo) == 1
    assert sorted(ran) == ["build", "i18n"]
    assert "npm run build" in capsys.readouterr().err


def test_a_failure_from_unstaged_work_only_warns(repo, monkeypatch, capsys):
    _commands(monkeypatch, build=PASS, i18n=FAIL)
    (repo / "templates/index.html").write_text("mine\n")
    _git(repo, "add", "templates/index.html")
    (repo / "static/js/app.js").write_text("another session's work\n")

    assert pc.main(repo) == 0
    err = capsys.readouterr().err
    assert "Warning only" in err and "static/js/app.js" in err


def test_untracked_files_the_check_reads_also_make_it_a_warning(repo, monkeypatch):
    _commands(monkeypatch, build=FAIL, i18n=PASS)
    (repo / "static/js/app.js").write_text("changed\n")
    _git(repo, "add", "static/js/app.js")
    (repo / "static/js/draft.js").write_text("not mine\n")

    assert pc.main(repo) == 0


def test_commits_outside_the_checked_files_run_nothing(repo, monkeypatch):
    ran = _commands(monkeypatch, build=FAIL, i18n=FAIL)
    (repo / "docs/notes.md").write_text("changed\n")
    _git(repo, "add", "docs/notes.md")

    assert pc.main(repo) == 0
    assert ran == []


def test_a_check_that_cannot_run_here_is_skipped(repo, monkeypatch, capsys):
    _commands(monkeypatch, build="node_modules is missing (npm ci)", i18n=PASS)
    (repo / "static/js/app.js").write_text("changed\n")
    _git(repo, "add", "static/js/app.js")

    assert pc.main(repo) == 0
    assert "build check skipped" in capsys.readouterr().err
