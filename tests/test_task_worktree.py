import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
import subprocess

import pytest


def _load():
    path = Path(__file__).resolve().parents[1] / "scripts" / "task_worktree.py"
    spec = importlib.util.spec_from_file_location("task_worktree", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tw = _load()
T0 = datetime(2026, 10, 25, 4, 30, 0)


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def root(tmp_path, monkeypatch):
    """A main checkout with an origin and a real venv, like the project's."""
    config = tmp_path / "gitconfig"
    config.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "test@example.com")
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", "-b", "main", str(origin))
    main = tmp_path / "main"
    _git(tmp_path, "clone", str(origin), str(main))
    (main / ".gitignore").write_text("venv/\nnode_modules/\n")
    _git(main, "add", ".gitignore")
    _git(main, "commit", "-m", "init")
    _git(main, "push", "origin", "HEAD:main")
    (main / "venv").mkdir()
    (main / "venv" / "python.txt").write_text("real venv")
    return main


def test_each_run_gets_its_own_worktree_at_origin_main(root):
    first = tw.new("bug-hunt", root=root, npm=False, now=T0)
    second = tw.new("bug-hunt", root=root, npm=False, now=T0)

    assert first != second
    assert first.parent == second.parent == root / ".claude" / "worktrees"
    for path in (first, second):
        assert _git(path, "rev-parse", "HEAD") == _git(root, "rev-parse", "origin/main")
        assert (path / "venv" / "python.txt").read_text() == "real venv"
        assert tw.uncommitted(path) == []


def test_remove_takes_the_link_out_and_keeps_the_real_venv(root):
    path = tw.new("visual-polish", root=root, npm=False, now=T0)

    tw.remove(path, root=root)

    assert not path.exists()
    assert (root / "venv" / "python.txt").read_text() == "real venv"
    assert tw.task_worktrees(root) == []


def test_remove_refuses_uncommitted_work_unless_discarded(root):
    path = tw.new("daily-improvement", root=root, npm=False, now=T0)
    (path / "fix.py").write_text("x = 1\n")

    with pytest.raises(tw.Refused, match="uncommitted"):
        tw.remove(path, root=root)
    assert (path / "fix.py").exists()

    tw.remove(path, root=root, discard=True)
    assert not path.exists()
    assert (root / "venv" / "python.txt").exists()


def test_remove_refuses_unpushed_commits_until_they_are_on_origin(root):
    path = tw.new("ci-watch", root=root, npm=False, now=T0)
    (path / "fix.py").write_text("x = 1\n")
    _git(path, "add", "fix.py")
    _git(path, "commit", "-m", "fix")

    with pytest.raises(tw.Refused, match="no remote branch"):
        tw.remove(path, root=root)

    _git(path, "push", "origin", "HEAD:main")
    tw.remove(path, root=root)
    assert not path.exists()


def test_remove_refuses_anything_but_a_task_worktree(root):
    with pytest.raises(tw.Refused, match="not a task worktree"):
        tw.remove(root, root=root, discard=True)
    assert (root / ".gitignore").exists()


def test_new_prunes_only_stale_worktrees_that_are_clean_and_pushed(root):
    stale_clean = tw.new("bug-hunt", root=root, npm=False, now=T0)
    stale_dirty = tw.new("bug-hunt", root=root, npm=False, now=T0)
    (stale_dirty / "half.py").write_text("")
    recent = tw.new("bug-hunt", root=root, npm=False, now=T0 + timedelta(hours=20))

    latest = tw.new("bug-hunt", root=root, npm=False, now=T0 + timedelta(hours=25))

    assert not stale_clean.exists()
    assert (stale_dirty / "half.py").exists()
    assert recent.exists() and latest.exists()
    assert (root / "venv" / "python.txt").read_text() == "real venv"


def test_task_names_stay_inside_the_worktrees_folder(root):
    with pytest.raises(tw.Refused, match="task name"):
        tw.new("../escape", root=root, npm=False, now=T0)
