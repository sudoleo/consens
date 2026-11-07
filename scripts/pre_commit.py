"""Run the CI checks that most often turn main red, before git commits.

Git calls this through .githooks/pre-commit once a clone has
`git config core.hooksPath .githooks` (`dev.ps1 update` sets it). A red main
holds up every session and scheduled task working on it, and the two checks
here are the ones people forget: static/dist out of step with the sources
(`npm run build`) and English text without a German entry. Each runs only when
a staged file can change its result, and both run at once because each takes
about 20 seconds on the development machine.

The checks read the working tree, not the commit. When a file they read has
unstaged changes, often another session's work in the same checkout, their
verdict is not about this commit, so a failure then only warns.

Exit code: 0 commit may go ahead, 1 a check failed for this commit.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys


@dataclass(frozen=True)
class Check:
    name: str
    inputs: tuple[str, ...]
    fix: str


BUILD = Check(
    name="build",
    inputs=(
        "static/",
        "scripts/build_frontend.mjs",
        "scripts/frontend-output.mjs",
        "scripts/frontend-sourcemaps.mjs",
        "scripts/vendor_frontend.mjs",
        "package.json",
        "package-lock.json",
    ),
    fix="static/dist does not match the sources. Run `npm run build` once and stage static/dist.",
)
I18N = Check(
    name="i18n",
    inputs=("templates/", "static/", "app/", "main.py", "scripts/i18n.py"),
    fix=(
        "Visible English text has no German entry. `venv/Scripts/python.exe scripts/i18n.py missing` "
        "lists it; add it to app/i18n/de/*.json (docs/i18n.md)."
    ),
)
CHECKS = (BUILD, I18N)


def touches(check: Check, paths: list[str]) -> bool:
    return any(path == item or (item.endswith("/") and path.startswith(item)) for path in paths for item in check.inputs)


def git_lines(*args: str, cwd: Path) -> list[str]:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True)
    return [line for line in result.stdout.splitlines() if line]


def staged_paths(root: Path) -> list[str]:
    return git_lines("diff", "--cached", "--name-only", "--no-renames", cwd=root)


def unstaged_paths(check: Check, root: Path) -> list[str]:
    """Files the check reads whose working copy differs from what is being committed."""
    specs = list(check.inputs)
    return git_lines("diff", "--name-only", "--", *specs, cwd=root) + git_lines(
        "ls-files", "--others", "--exclude-standard", "--", *specs, cwd=root
    )


def command(check: Check, root: Path) -> list[str] | str:
    """The command to run, or why the check cannot run here."""
    if check is BUILD:
        node = shutil.which("node")
        if not node:
            return "node is not on PATH"
        if not (root / "node_modules").is_dir():
            return "node_modules is missing (npm ci)"
        return [node, "scripts/build_frontend.mjs", "--check"]
    return [sys.executable, "scripts/i18n.py", "check"]


def tail(text: str, lines: int = 15) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def main(root: Path | None = None) -> int:
    root = root or Path(git_lines("rev-parse", "--show-toplevel", cwd=Path.cwd())[0])
    staged = staged_paths(root)
    running = {}
    for check in CHECKS:
        if not touches(check, staged):
            continue
        cmd = command(check, root)
        if isinstance(cmd, str):
            print(f"[pre-commit] {check.name} check skipped: {cmd}; CI still runs it.", file=sys.stderr)
            continue
        running[check] = subprocess.Popen(
            cmd, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace"
        )

    blocked = False
    for check, process in running.items():
        output, _ = process.communicate()
        if process.returncode == 0:
            continue
        unreliable = unstaged_paths(check, root)
        print(f"[pre-commit] {check.fix}", file=sys.stderr)
        print(tail(output), file=sys.stderr)
        if unreliable:
            shown = ", ".join(unreliable[:3]) + (" …" if len(unreliable) > 3 else "")
            print(
                f"[pre-commit] Warning only: {len(unreliable)} file(s) this check reads have unstaged changes "
                f"({shown}), so the result may not be about this commit.",
                file=sys.stderr,
            )
        else:
            blocked = True
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
