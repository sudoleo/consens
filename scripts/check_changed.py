"""Pick the tests a change needs: `.\\dev.ps1 check changed`.

The full suite belongs to the CI: on the development machine it takes minutes
and slows every session working next to it. Picking "the one to three files
that fit" by feel is what turned main red, mostly through tests that list
things across modules. This script derives the selection from the changed
files (working tree plus the commits that are not on origin/main yet), the
same way every time and without stored state, so it also works in a worktree
that was created a second ago.

A test file is selected when

  1. it changed itself,
  2. it imports a changed file (Python imports, dotted names as monkeypatch
     and mock.patch take them, relative JavaScript imports), or the module
     that renders a changed template,
  3. it names a changed file, or a file that pulls the changed one in:
     bundles.json lists the scripts of /app, a sheet imports another, a
     template includes a partial. What the helper modules of a test under
     tests/ name counts as named by it,
  4. it walks a folder (glob, os.walk, readdirSync, ...) and names a folder
     on the changed file's path together with its suffix,
  5. it is in ALWAYS.

Rule 2 follows an import no further than IMPORT_HOPS modules, because the
app's imports form one knot: followed to the end, half of all modules reach
three quarters of the test files (docs/testing.md has the measurement). What
only the tests of a module's users would notice is left to the CI.

The whole suite runs instead when a file in WHOLE_SUITE changed, or when the
selection reaches WHOLE_SUITE_SHARE of a suite's files: a change that wide
is no longer a selection.

Browser tests (tests/e2e) and the rules test need the emulator queue of
dev.ps1, so they are only named here, with the call to start them. A browser
test is named by the same rules, and when it asks for an id, a class or a
visible text that the changed lines take away.

  python scripts/check_changed.py                    what would run, and why
  python scripts/check_changed.py --why              every file with its reason
  python scripts/check_changed.py --base HEAD~1      the last commit instead
  python scripts/check_changed.py --plan plan.json   for dev.ps1, which runs it

Exit code: 0 selection made, 2 no selection possible (git).
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from fnmatch import fnmatch
import json
import os
from pathlib import Path
import posixpath
import re
import subprocess
import sys
from typing import Iterable

try:
    from scripts.pre_commit import BUILD, touches
except ImportError:  # run as a script: scripts/ itself is the import root
    from pre_commit import BUILD, touches

# Tests whose subject is a list across modules, so no single changed file
# points at them. Rules 2 to 4 find them for most changes; they are fixed
# here because they are the tests that most often turn main red, and all of
# them together run in half a minute (docs/testing.md has the count).
ALWAYS = {
    "tests/test_i18n.py": "every visible English text has its German",
    "tests/test_agent_tool_budget.py": "the tools a message is offered, and their length",
    "tests/test_agent_turn_limits.py": "the tools a turn may repeat, by name",
    "tests/test_logging_redaction_contract.py": "no runtime module logs a raw exception",
    "tests/test_ui_copy.py": "one wording and one typography for every text of the app",
    "tests/test_forced_colors.py": "every masked icon of every sheet in contrast mode",
    "tests/test_public_design_system.py": "every sheet and text of the public pages",
}

# How many modules may stand between a changed file and a test importing it.
# 0: only the tests that import the changed file itself. One module more
# doubles the selection and sends a quarter of all commits to the whole
# suite, and it found none of the failures on main that 0 missed
# (docs/testing.md has the measurement).
IMPORT_HOPS = 0

# No selection sees through these: the test setup, the installed packages,
# the runners' configuration and the entry point that starts them.
WHOLE_SUITE = (
    "tests/conftest.py", "requirements*.txt", "package.json", "package-lock.json",
    ".python-version", "dev.ps1", "pytest.ini", "vitest.config.mjs",
)
WHOLE_SUITE_SHARE = 0.4

# The folders whose files are read. Any other changed file is only a name
# that tests can mention.
SCANNED = {
    "app": (".py",), "scripts": (".py", ".mjs"), "tests": (".py", ".mjs", ".js"),
    "templates": (".html",), "static/css": (".css",),
}
SCANNED_FILES = ("main.py", "static/style.css", "static/js/bundles.json")
SKIPPED_FOLDERS = {"__pycache__", "node_modules", "fixtures"}
# Where an absolute Python import can resolve besides the repository root:
# pytest puts the folder of a test file first on sys.path.
IMPORT_ROOTS = ("", "tests/", "tests/e2e/", "scripts/")
CODE = (".py", ".mjs", ".js")
# Build output: its file names carry a hash, so tests read it as a folder and
# name that. Vendored packages have a dist folder of their own, which is why
# the bare word does not count.
BUILT = "static/dist/"

SUITES = ("backend", "frontend", "browser", "rules")
RUN_HERE = ("backend", "frontend")

PY_IMPORT = re.compile(
    r"^[ \t]*(?:from[ \t]+[.\w]+[ \t]+import[ \t]+(?:\([^)]*\)|[^\n]*)|import[ \t]+[^\n]*)", re.M)
PY_DOTTED = re.compile(r"""["']((?:app|scripts|main)\.[A-Za-z_][\w.]*)["']""")
PY_TEMPLATE = re.compile(r"""["']([\w/-]+\.html)["']""")
JS_IMPORT = re.compile(r"""(?:\bfrom|\bimport|\brequire)\s*\(?\s*["'](\.{1,2}/[^"']+)["']""")
CSS_IMPORT = re.compile(r"""@import\s+(?:url\(\s*)?["']?([^"')\s;]+)""")
TEMPLATE_IMPORT = re.compile(r"""\{%-?\s*(?:include|extends|import|from)\s+["']([^"']+)["']""")
MANIFEST_ENTRY = re.compile(r'"(static/[^"]+)"')
WALKS = (".glob(", ".rglob(", "os.walk(", ".iterdir(", "os.listdir(", "os.scandir(", "ls-files",
         "walk_packages", "iter_modules", "readdirSync", "globSync", "readdir(")
STRING = re.compile(r'''"((?:[^"\\\n]|\\.)*)"|'((?:[^'\\\n]|\\.)*)\'''')
QUOTES = "\"'`"

ID_ATTRIBUTE = re.compile(r"""\bid=\\?["']([A-Za-z][\w-]*)|getElementById\(\s*["']([A-Za-z][\w-]*)""")
ID_SELECTOR = re.compile(r"#([A-Za-z][\w-]{2,})")
HEX_COLOUR = re.compile(r"[0-9a-fA-F]{3,8}")
CLASS_ATTRIBUTE = re.compile(r"""\bclass(?:Name)?\s*=\s*\\?["']([^"'<>{}$]+)""")
CLASS_LIST = re.compile(r"classList\.\w+\(([^)]*)\)")
CLASS_SELECTOR = re.compile(r"\.(-?[A-Za-z_][\w-]*)")
TEXT_NODE = re.compile(r">([^<>{}]+)<")
TEXT_ATTRIBUTE = re.compile(
    r"""\b(?:aria-label|title|placeholder|alt|data-tooltip|data-short|data-description)=\\?["']([^"'<>{}]+)""")
UI_SUFFIXES = (".html", ".js", ".css", ".json", ".py")


@dataclass
class Suite:
    total: int = 0
    files: dict[str, str] = field(default_factory=dict)  # test file -> why
    whole: str = ""  # why the whole suite runs instead of files


@dataclass
class Plan:
    changed: list[str]
    suites: dict[str, Suite]
    build_check: bool = False

    def not_started(self) -> list[str]:
        """The calls for the suites that need the emulator queue of dev.ps1."""
        calls = []
        browser = self.suites["browser"]
        if browser.files and not browser.whole:
            calls.append(".\\dev.ps1 check browser -TestPath " + ",".join(sorted(browser.files)))
        if self.suites["rules"].files:
            calls.append(".\\dev.ps1 check rules")
        return calls

    def as_json(self) -> dict:
        def runs(name):
            suite = self.suites[name]
            return {"whole": bool(suite.whole), "files": [] if suite.whole else sorted(suite.files)}
        return {
            "changed": self.changed,
            "backend": runs("backend"), "frontend": runs("frontend"), "build_check": self.build_check,
            "not_started": self.not_started(),
        }


def suite_of(path: str) -> str | None:
    name = posixpath.basename(path)
    if path.startswith("tests/e2e/"):
        return "browser" if name.startswith("test_") and name.endswith(".py") else None
    if path.startswith("tests/js/"):
        return "frontend" if name.endswith(".test.mjs") else None
    if path.startswith("tests/rules/"):
        return "rules" if name.endswith(".test.mjs") else None
    if path.startswith("tests/") and name.startswith("test_") and name.endswith(".py"):
        return "backend"
    return None


def is_documentation(path: str) -> bool:
    """What the CI workflow ignores (paths-ignore): it starts no run for it."""
    return path.startswith("docs/") or ("/" not in path and path.endswith(".md"))


def read_tree(root: Path) -> dict[str, str]:
    """The text of every scanned file, by repository path with forward slashes."""
    def read(relative):
        try:
            return (root / relative).read_bytes().decode("utf-8-sig", errors="replace")
        except OSError:
            return None

    paths = list(SCANNED_FILES)
    for folder, suffixes in SCANNED.items():
        for current, folders, names in os.walk(root / folder):
            folders[:] = [name for name in folders if name not in SKIPPED_FOLDERS]
            base = Path(current).relative_to(root).as_posix()
            paths += [f"{base}/{name}" for name in names if name.endswith(suffixes)]
    # Opening nine hundred files is most of the time when they are not in
    # the system's cache (a worktree that was just created): in parallel.
    with ThreadPoolExecutor(max_workers=8) as pool:
        return {path: text for path, text in zip(paths, pool.map(read, paths)) if text is not None}


def python_modules(text: str) -> list[tuple[int, str]]:
    """(level, dotted name) for everything the import statements of a file
    can load. Only the lines that look like an import go through ast: parsing
    every file whole took four seconds on the development machine."""
    found = []
    for match in PY_IMPORT.finditer(text):
        try:
            statement = ast.parse(match.group(0).strip()).body[0]
        except (SyntaxError, IndexError):
            continue  # prose in a docstring that starts like an import
        if isinstance(statement, ast.Import):
            found += [(0, alias.name) for alias in statement.names]
        elif isinstance(statement, ast.ImportFrom):
            module = statement.module or ""
            found.append((statement.level, module))
            # `from package import module` loads a file of its own.
            found += [(statement.level, f"{module}.{alias.name}" if module else alias.name)
                      for alias in statement.names]
    return found


class Imports:
    """Which files each scanned file pulls in when it is used."""

    def __init__(self, texts: dict[str, str], known: set[str]):
        self.known = known
        self.resolved: dict[tuple, tuple[str, ...]] = {}
        self.pulls = {path: self.pulled_in(path, text) for path, text in texts.items()}
        self.pulled_by: dict[str, set[str]] = {}
        for path, targets in self.pulls.items():
            for target in targets:
                self.pulled_by.setdefault(target, set()).add(path)

    def modules(self, dotted: str, roots: tuple[str, ...]) -> tuple[str, ...]:
        """The files a dotted name loads: the module and the packages above it."""
        key = (dotted, roots)
        if key not in self.resolved:
            parts = dotted.split(".")
            self.resolved[key] = tuple(
                candidate for root in roots for depth in range(1, len(parts) + 1)
                for candidate in (root + "/".join(parts[:depth]) + ".py", root + "/".join(parts[:depth]) + "/__init__.py")
                if candidate in self.known)
        return self.resolved[key]

    def pulled_in(self, path: str, text: str) -> set[str]:
        folder = posixpath.dirname(path)
        targets = set()
        if path.endswith(".py"):
            # A file outside the app package may import its neighbours by bare name.
            roots = IMPORT_ROOTS if path.startswith("app/") or not folder else (*IMPORT_ROOTS, f"{folder}/")
            for level, dotted in python_modules(text):
                if not level:
                    targets.update(self.modules(dotted, roots))
                    continue
                package = folder
                for _ in range(level - 1):
                    package = posixpath.dirname(package)
                if f"{package}/__init__.py" in self.known:
                    targets.add(f"{package}/__init__.py")
                if dotted:
                    targets.update(self.modules(dotted, (f"{package}/",)))
            for dotted in PY_DOTTED.findall(text):
                targets.update(self.modules(dotted, ("",)))
            if not path.startswith("tests/"):
                targets.update(template for template in (f"templates/{name}" for name in PY_TEMPLATE.findall(text))
                               if template in self.known)
        elif path.endswith((".mjs", ".js")):
            targets.update(posixpath.normpath(posixpath.join(folder, found)) for found in JS_IMPORT.findall(text))
        elif path.endswith(".css"):
            targets.update(posixpath.normpath(posixpath.join(folder, found)) for found in CSS_IMPORT.findall(text))
        elif path.endswith(".html"):
            targets.update(posixpath.normpath(posixpath.join("templates", found))
                           for found in TEMPLATE_IMPORT.findall(text))
        elif path.endswith(".json"):
            targets.update(MANIFEST_ENTRY.findall(text))
        targets.discard(path)
        return targets

    def users(self, path: str) -> dict[str, int]:
        """The files that pull ``path`` in, with at most IMPORT_HOPS modules
        between them and the changed file. The number says how many modules
        a file that uses this one is away from the change: the ones before
        it, plus itself if it is one. A sheet, a template or the bundle list
        is no module, and neither is the code file that reads one of them:
        the route that renders a template is where the template becomes
        behaviour, so the route's tests are the template's."""
        # (modules before this file, whether this file is one for its users)
        best = {path: (0, 0)}
        queue = deque([path])
        while queue:
            current = queue.popleft()
            before, counts = best[current]
            for user in self.pulled_by.get(current, ()):
                state = (before + counts, int(user.endswith(CODE) and current.endswith(CODE)))
                if state[0] <= IMPORT_HOPS and state < best.get(user, (IMPORT_HOPS + 1, 0)):
                    best[user] = state
                    queue.append(user)
        del best[path]
        return {user: before + counts for user, (before, counts) in best.items()}

    def helpers(self, test: str) -> set[str]:
        """The test and the helper modules under tests/ it loads: what they
        name or walk, the test names or walks. Other tests it imports from
        are not helpers; they name files for their own cases."""
        seen, queue = {test}, deque([test])
        while queue:
            for target in self.pulls.get(queue.popleft(), ()):
                if (target.startswith("tests/") and target in self.pulls and target not in seen
                        and not suite_of(target) and posixpath.basename(target) != "conftest.py"):
                    seen.add(target)
                    queue.append(target)
        return seen


def name_of(path: str) -> str:
    """How a test names the file: by file name; with its folder where every
    folder has a file of that name."""
    name = posixpath.basename(path)
    return "/".join(path.split("/")[-2:]) if name in ("__init__.py", "README.md") else name


def is_word(char: str) -> bool:
    return char.isalnum() or char in "_-"


def names(text: str, name: str, as_path: bool = False) -> bool:
    """Whether ``text`` has ``name`` as a word of its own. ``as_path``: only
    at the end of a string, the way a path to the file is written, so prose
    about a file that merely leads to the changed one does not count."""
    at = text.find(name)
    while at >= 0:
        end = at + len(name)
        after = text[end] if end < len(text) else " "
        if not (at and is_word(text[at - 1])) and (after in QUOTES if as_path else not is_word(after)):
            return True
        at = text.find(name, at + 1)
    return False


def is_distinct(token: str) -> bool:
    """A compound name such as agent-row or questionInput: found as a bare
    word it still means this element, unlike "hidden" or "open"."""
    return len(token) >= 5 and ("-" in token.strip("-") or "_" in token or re.search(r"[a-z][A-Z]", token) is not None)


def strings_of(text: str) -> list[str]:
    return [(double or single).replace("\\'", "'").replace('\\"', '"').strip()
            for double, single in STRING.findall(text)]


def reads_as_text(value: str) -> bool:
    return len(value) >= 4 and " " in value and any(char.isalpha() for char in value)


@dataclass
class UiTokens:
    """Ids, classes and visible texts that a change takes out of the interface."""
    ids: set[str] = field(default_factory=set)
    classes: set[str] = field(default_factory=set)
    texts: set[str] = field(default_factory=set)


def line_tokens(path: str, line: str) -> tuple[set[str], set[str], set[str]]:
    """The ids, classes and texts one line of an interface file has."""
    ids, classes = set(), set()
    literals = strings_of(line)
    texts = {value for value in literals if reads_as_text(value)}
    if path.endswith(".py"):
        return ids, classes, texts
    ids.update(first or second for first, second in ID_ATTRIBUTE.findall(line))
    if path.endswith(".css"):
        # Only the selector of a rule; a declaration has url(x.png) and 0.3s.
        selector = line.split("{")[0] if "{" in line or line.rstrip().endswith(",") else ""
        ids.update(found for found in ID_SELECTOR.findall(selector) if not HEX_COLOUR.fullmatch(found))
        classes.update(CLASS_SELECTOR.findall(selector))
        return ids, classes, texts
    ids.update(found for found in ID_SELECTOR.findall(line) if not HEX_COLOUR.fullmatch(found))
    for value in CLASS_ATTRIBUTE.findall(line):
        classes.update(value.split())
    for arguments in CLASS_LIST.findall(line):
        classes.update(strings_of(arguments))
    for literal in literals:
        classes.update(CLASS_SELECTOR.findall(literal))
    texts.update(value.strip() for value in TEXT_NODE.findall(line) + TEXT_ATTRIBUTE.findall(line)
                 if len(value.strip()) >= 4 and any(char.isalpha() for char in value))
    return ids, classes, texts


def ui_tokens(diff: str) -> UiTokens:
    """What the removed lines of a unified diff (git diff -U0) have and the
    added lines do not have as often: the id that was renamed, the text that
    was reworded. A browser test still asks for those. A line that only
    moved, or kept its id while something else on it changed, gives nothing,
    or every test using a common id would be named for every change near it."""
    gone = (Counter(), Counter(), Counter())
    path = ""
    header = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            header = True
        elif line.startswith("@@"):
            header = False
        elif header and line.startswith(("+++ ", "--- ")) and not line.endswith("/dev/null"):
            path = line[6:]
        if header or not line.startswith(("+", "-")) or not path.endswith(UI_SUFFIXES) or path.startswith(BUILT):
            continue
        for counter, found in zip(gone, line_tokens(path, line[1:])):
            counter.update({token: 1 if line[0] == "-" else -1 for token in found})
    ids, classes, texts = ({token for token, count in counter.items() if count > 0} for counter in gone)
    # Compound class names only: "hidden" or "open" as a bare word says nothing.
    return UiTokens(ids=ids, classes={token for token in classes if is_distinct(token)}, texts=texts)


def browser_tests_using(tokens: UiTokens, texts: dict[str, str]) -> dict[str, str]:
    """Browser test -> the id, class or text it asks for and the change took away."""
    distinct = {token for token in tokens.ids | tokens.classes if is_distinct(token)}
    plain_ids = sorted(tokens.ids - distinct)
    long_texts = sorted(value for value in tokens.texts if len(value) >= 12 and " " in value)
    every_text = "\n".join(sorted(tokens.texts))
    found = {}
    for test, text in texts.items():
        if suite_of(test) != "browser":
            continue
        used = next((token for token in sorted(distinct) if names(text, token)), None) or next(
            (f"#{token}" for token in plain_ids if names(text, f"#{token}")), None)
        if used:
            found[test] = f"uses {used}"
            continue
        literals = strings_of(text)
        together = "\n".join(literals)
        shown = (next((value for value in literals if value in tokens.texts), None)
                 or next((value for value in literals if len(value) >= 12 and " " in value and value in every_text), None)
                 or next((value for value in long_texts if value in together), None))
        if shown:
            found[test] = f'shows "{shown[:40]}"'
    return found


def select(root: Path, changes: Iterable[str], diff: str = "") -> Plan:
    """The plan for the changed paths against the files under ``root``. Reads
    no git: ``diff`` is the unified diff of the interface files, for the
    browser tests."""
    texts = read_tree(root)
    changed = sorted(set(changes))
    tests = {path: suite_of(path) for path in texts if suite_of(path)}
    suites = {name: Suite(total=sum(1 for suite in tests.values() if suite == name)) for name in SUITES}
    plan = Plan(changed=changed, suites=suites)
    if not changed:
        return plan
    # A removed module is still what the files importing it point at.
    imports = Imports(texts, set(texts) | set(changed))

    def choose(test, why):
        suites[tests[test]].files.setdefault(test, why)

    # Rule 1
    for path in changed:
        if path in tests:
            choose(path, "changed")

    # Rule 2, and for rule 3 the names that lead to a changed file.
    direct: dict[str, str] = {}  # name a test may mention -> what that means
    leading: dict[str, str] = {}
    for path in changed:
        if path.startswith(BUILT):
            for name in ("static/dist", '"dist"', "'dist'"):
                direct.setdefault(name, "names static/dist")
            continue
        # Other tests name a test file in their prose, not to read it.
        if not suite_of(path):
            direct.setdefault(name_of(path), f"names {path}")
        for user, away in imports.users(path).items():
            if user in tests:
                choose(user, f"imports {path}")
            elif away <= IMPORT_HOPS and (not user.endswith(".py") or user.startswith("scripts/")):
                leading.setdefault(name_of(user), f"names {user}, which pulls in {path}")

    # Rule 3. Browser tests are only named for someone to start: there, what
    # a shared helper names would list every file, so only their own text counts.
    reads = {test: imports.helpers(test) if suite in RUN_HERE else {test} for test, suite in tests.items()}
    naming: dict[str, str] = {}  # file under tests/ -> why
    for path, text in texts.items():
        if path.startswith("tests/"):
            why = next((why for name, why in direct.items() if names(text, name)), None) or next(
                (why for name, why in leading.items() if name not in direct and names(text, name, as_path=True)), None)
            if why:
                naming[path] = why
    for test in tests:
        why = next((naming[part] for part in sorted(reads[test]) if part in naming), None)
        if why:
            choose(test, why)

    # Rule 4
    walked = [(path.split("/")[:-1], posixpath.splitext(path)[1]) for path in changed
              if "/" in path and not path.startswith(BUILT)]
    walking = {path for path, text in texts.items() if path.startswith("tests/") and any(call in text for call in WALKS)}
    segments: dict[str, set[str]] = {}
    for test in tests:
        parts = reads[test]
        if not walked or not parts & walking:
            continue
        for part in parts:
            if part not in segments:
                segments[part] = {segment for literal in strings_of(texts[part]) for segment in re.split(r"[/\\]", literal)}
        for folders, suffix in walked:
            folder = next((name for name in folders if any(name in segments[part] for part in parts)), None)
            if folder and (not suffix or any(names(texts[part], suffix) for part in parts)):
                choose(test, f"walks {folder}/ for *{suffix}")
                break

    # Browser tests: the ids, classes and texts the changed lines take away.
    for test, why in browser_tests_using(ui_tokens(diff), texts).items():
        choose(test, why)

    # Rule 5: not for a change the CI starts no run for.
    if not all(is_documentation(path) for path in changed):
        for test, why in ALWAYS.items():
            if test in tests:
                choose(test, f"always: {why}")

    trigger = next((path for path in changed for pattern in WHOLE_SUITE if fnmatch(path, pattern)), None)
    for name in RUN_HERE:
        suite = suites[name]
        if trigger:
            suite.whole = f"{trigger} changed"
        elif suite.total and len(suite.files) >= WHOLE_SUITE_SHARE * suite.total:
            suite.whole = f"{len(suite.files)} of {suite.total} test files are affected"
    setup = next((path for path in ("tests/conftest.py", "tests/e2e/conftest.py") if path in changed), None)
    if setup:
        suites["browser"].whole = f"{setup} changed"
    plan.build_check = touches(BUILD, changed)
    return plan


GROUPS = (
    ("changed", "changed"), ("imports ", "import a changed file"), ("names ", "name a changed file"),
    ("walks ", "walk a changed folder"), ("uses ", "use an id or class that is gone"),
    ("shows ", "expect a text that is gone"),
    ("always", "always run"),
)


def report(plan: Plan, base: str, why: bool = False) -> str:
    """What runs and why, in a few lines; ``why`` lists every file."""
    def short(paths, limit=6):
        shown = [posixpath.basename(path) for path in paths]
        return ", ".join(shown[:limit]) + (f", +{len(shown) - limit}" if len(shown) > limit else "")

    if not plan.changed:
        return f"[changed] Nothing differs from {base}: nothing to run."
    lines = [f"[changed] {len(plan.changed)} changed file(s) against {base}: {short(plan.changed, 4)}"]
    for name in SUITES:
        suite = plan.suites[name]
        started = "" if name in RUN_HERE else ", not started here"
        extra = ", then build:check" if name == "frontend" and plan.build_check else ""
        if suite.whole:
            lines.append(f"[changed] {name}{started}: the whole suite ({suite.whole}){extra}")
            if name == "browser":
                lines.append("  It runs nightly in the CI; sooner by workflow_dispatch -> browser-and-rules.")
            continue
        if not suite.files:
            if name == "frontend" and plan.build_check:
                lines.append("[changed] frontend: no test file, only build:check")
            elif name in RUN_HERE:
                lines.append(f"[changed] {name}: no test file")
            continue
        lines.append(f"[changed] {name}{started}: {len(suite.files)} of {suite.total} test files{extra}")
        if why:
            lines += [f"  {test}: {reason}" for test, reason in sorted(suite.files.items())]
        else:
            for prefix, label in GROUPS:
                chosen = sorted(test for test, reason in suite.files.items() if reason.startswith(prefix))
                if chosen:
                    lines.append(f"  {len(chosen)} {label}: {short(chosen)}")
    lines += [f"[changed] start those with: {call}" for call in plan.not_started()]
    return "\n".join(lines)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=root,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {(result.stderr or result.stdout).strip()}")
    return result.stdout


def changes_since(root: Path, base: str) -> tuple[list[str], str]:
    """The files that differ from where this checkout left ``base`` (commits,
    index, working tree, new and removed files), and the diff of the
    interface files."""
    fork = git(root, "merge-base", base, "HEAD").strip()
    changed = git(root, "diff", "--name-only", "--no-renames", fork).splitlines()
    changed += git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    diff = git(root, "diff", "-U0", "--no-renames", fork, "--", "templates", "static", "app", "main.py",
               f":(exclude){BUILT}", ":(exclude)static/vendor")
    return changed, diff


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="origin/main", help="what the checkout is compared with")
    parser.add_argument("--plan", type=Path, help="write the selection as JSON, for dev.ps1")
    parser.add_argument("--why", action="store_true", help="list every selected file with its reason")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        changes, diff = changes_since(root, args.base)
    except (RuntimeError, OSError) as exc:
        print(f"[changed] {exc}", file=sys.stderr)
        print(f"[changed] No selection without {args.base}; `git fetch origin main` brings origin/main.", file=sys.stderr)
        return 2
    plan = select(root, changes, diff)
    print(report(plan, args.base, args.why))
    if args.plan:
        args.plan.write_text(json.dumps(plan.as_json(), indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
