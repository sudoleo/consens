"""Give every run of a scheduled Claude task its own worktree.

Scheduled tasks (C:\\Users\\maxlp\\.claude\\scheduled-tasks) are started several
times a day and often in parallel. In the main checkout, or in one fixed
worktree per task, two runs overwrite or reset each other's work. A run that
changes the repo therefore takes a fresh worktree from origin/main and hands it
back at the end, both from the main checkout:

  venv/Scripts/python.exe scripts/task_worktree.py new bug-hunt
  venv/Scripts/python.exe scripts/task_worktree.py remove <path>

`new` prints the path as its last line (.claude/worktrees/<task>-<timestamp>).
The worktree gets node_modules (npm ci, skip with --no-npm) and `venv` as a
junction to the main checkout's venv. `remove` takes the junction out first:
`git worktree remove` once walked through it and deleted the real venv
(2026-10-22). It refuses a worktree with uncommitted changes or with commits
that are on no remote branch, unless --discard says the run throws them away.
`new` and `prune` also remove task worktrees older than a day that are clean
and pushed, so runs that were stopped halfway do not pile up.

Exit code: 0 done, 1 refused or failed (reason on stderr).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

STALE_AFTER = timedelta(hours=24)
STAMP = "%Y%m%d-%H%M%S"
TASK = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
NAME = re.compile(rf"(?P<task>{TASK.pattern})-(?P<stamp>\d{{8}}-\d{{6}})")


class Refused(Exception):
    pass


def git(*args: str, cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise Refused(f"git {' '.join(args)}: {(result.stderr or result.stdout).strip()}")
    return result.stdout.strip()


def main_checkout(start: Path) -> Path:
    """The main checkout, also when the script runs from inside a worktree."""
    return Path(git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=start)).parent


def worktrees_dir(root: Path) -> Path:
    return root / ".claude" / "worktrees"


def _is_link(path: Path) -> bool:
    return os.path.islink(path) or os.path.isjunction(path)


def link_venv(worktree: Path, target: Path) -> None:
    link = worktree / "venv"
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)


def unlink_venv(worktree: Path) -> None:
    """Remove only the link. Anything that recurses through it empties the real venv."""
    link = worktree / "venv"
    if not _is_link(link):
        return
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "rmdir", str(link)], check=True, capture_output=True)
    else:
        link.unlink()
    if _is_link(link) or link.exists():
        raise Refused(f"could not remove the venv link in {worktree}")


def fetch_main(root: Path) -> str:
    # Runs that start together (the app catches up missed ones at once) race
    # for the lock on refs/remotes/origin/main.
    for attempt in range(4):
        try:
            git("fetch", "origin", "main", cwd=root)
            break
        except Refused:
            if attempt == 3:
                raise
            time.sleep(2 + attempt * 3)
    return git("rev-parse", "origin/main", cwd=root)


def install_node_modules(worktree: Path) -> None:
    npm = shutil.which("npm")
    if not npm:
        raise Refused("npm not found; install Node.js or pass --no-npm")
    result = subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=worktree, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise Refused(f"npm ci failed in {worktree}:\n{(result.stderr or result.stdout).strip()[-2000:]}")


def new(task: str, *, root: Path, npm: bool = True, now: datetime | None = None) -> Path:
    if not TASK.fullmatch(task):
        raise Refused(f"task name {task!r}: use lowercase letters, digits and hyphens")
    now = now or datetime.now()
    prune(root, now=now)
    commit = fetch_main(root)
    base = worktrees_dir(root)
    base.mkdir(parents=True, exist_ok=True)
    stamp = now
    while (path := base / f"{task}-{stamp:{STAMP}}").exists():
        stamp += timedelta(seconds=1)
    git("worktree", "add", "--detach", str(path), commit, cwd=root)
    try:
        link_venv(path, root / "venv")
        if npm:
            install_node_modules(path)
    except BaseException:
        remove(path, root=root, discard=True)
        raise
    return path


def uncommitted(worktree: Path) -> list[str]:
    lines = git("status", "--porcelain", cwd=worktree).splitlines()
    return [line for line in lines if line.strip() not in ("?? venv", "?? venv/")]


def remove(path: Path, *, root: Path, discard: bool = False) -> None:
    base = worktrees_dir(root).resolve()
    path = Path(path).resolve()
    if path.parent != base or not NAME.fullmatch(path.name):
        raise Refused(f"{path} is not a task worktree under {base}")
    if not path.exists():
        git("worktree", "prune", cwd=root)
        return
    if not discard:
        dirty = uncommitted(path)
        if dirty:
            raise Refused(f"uncommitted changes in {path} (commit and push them, or pass --discard):\n" + "\n".join(dirty))
        head = git("rev-parse", "HEAD", cwd=path)
        if not git("branch", "-r", "--contains", head, cwd=path):
            raise Refused(f"{path} has commits on no remote branch (push them, or pass --discard)")
    unlink_venv(path)
    git("worktree", "remove", "--force", str(path), cwd=root)


def task_worktrees(root: Path) -> list[Path]:
    base = worktrees_dir(root).resolve()
    found = []
    for line in git("worktree", "list", "--porcelain", cwd=root).splitlines():
        if line.startswith("worktree "):
            path = Path(line[len("worktree "):]).resolve()
            if path.parent == base and NAME.fullmatch(path.name):
                found.append(path)
    return found


def prune(root: Path, *, now: datetime | None = None) -> list[str]:
    """Remove stale task worktrees that are clean and pushed; report the rest."""
    now = now or datetime.now()
    kept = []
    for path in task_worktrees(root):
        started = datetime.strptime(NAME.fullmatch(path.name)["stamp"], STAMP)
        if now - started < STALE_AFTER:
            continue
        try:
            remove(path, root=root)
            print(f"[task-worktree] removed stale {path.name}")
        except Refused as error:
            kept.append(path.name)
            print(f"[task-worktree] kept stale {path.name}: {str(error).splitlines()[0]}", file=sys.stderr)
    return kept


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Worktrees for scheduled task runs.")
    actions = parser.add_subparsers(dest="action", required=True)
    make = actions.add_parser("new", help="fresh worktree from origin/main; prints its path last")
    make.add_argument("task")
    make.add_argument("--no-npm", action="store_true", help="skip npm ci (no frontend checks or builds in this run)")
    drop = actions.add_parser("remove", help="remove a task worktree once its work is committed and pushed")
    drop.add_argument("path")
    drop.add_argument("--discard", action="store_true", help="throw away uncommitted changes and unpushed commits")
    actions.add_parser("prune", help="remove task worktrees older than a day that are clean and pushed")
    args = parser.parse_args(argv)
    try:
        root = main_checkout(Path(__file__).resolve().parent)
        if args.action == "new":
            print(new(args.task, root=root, npm=not args.no_npm))
        elif args.action == "remove":
            remove(Path(args.path), root=root, discard=args.discard)
            print(f"[task-worktree] removed {Path(args.path).name}")
        else:
            prune(root)
    except (Refused, subprocess.CalledProcessError) as error:
        print(f"[task-worktree] {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
