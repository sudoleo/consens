"""Which tests a change selects (scripts/check_changed.py, `dev.ps1 check changed`).

Each rule is shown on a small tree of its own, so a case names exactly the
files that make it true. The last cases ask the real repository for the
changes that turned main red when their tests were picked by feel.
"""
import json
from pathlib import Path
import subprocess

import pytest

from scripts import check_changed as cc

ROOT = Path(__file__).resolve().parents[1]


def tree(root, files):
    for path, text in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def selected(root, *paths, diff="", suite="backend"):
    return cc.select(root, paths, diff).suites[suite].files


@pytest.fixture(autouse=True)
def small_trees_keep_their_selection(monkeypatch):
    """One of two test files is already a large share of a suite."""
    monkeypatch.setattr(cc, "WHOLE_SUITE_SHARE", 2)


@pytest.fixture
def app(tmp_path):
    """core <- service <- router, and one test file per distance."""
    return tree(tmp_path, {
        "app/__init__.py": "",
        "app/core.py": "LIMIT = 3\n",
        "app/service.py": "from app.core import LIMIT\n",
        "app/router.py": "from app import service\n",
        "app/lonely.py": "",
        "tests/test_core.py": "from app.core import LIMIT\n",
        "tests/test_service.py": "import app.service\n",
        "tests/test_router.py": "from app.router import service\n",
        "tests/test_other.py": "import json\n",
    })


def test_a_changed_test_file_runs(app):
    assert selected(app, "tests/test_other.py") == {"tests/test_other.py": "changed"}


def test_a_module_selects_the_tests_importing_it(app, monkeypatch):
    assert selected(app, "app/core.py") == {"tests/test_core.py": "imports app/core.py"}
    assert selected(app, "app/service.py") == {"tests/test_service.py": "imports app/service.py"}
    assert selected(app, "app/lonely.py") == {}
    # IMPORT_HOPS is how far an import is followed: with one module in
    # between, the tests of a module's users come along.
    monkeypatch.setattr(cc, "IMPORT_HOPS", 1)
    assert selected(app, "app/core.py").keys() == {"tests/test_core.py", "tests/test_service.py"}
    monkeypatch.setattr(cc, "IMPORT_HOPS", 2)
    assert selected(app, "app/core.py").keys() == {"tests/test_core.py", "tests/test_service.py", "tests/test_router.py"}


@pytest.mark.parametrize("statement", [
    "from app import core",
    "import app.core as core",
    "def test_it():\n    from app.core import LIMIT\n",
    "from app.core import (\n    LIMIT,\n)\n",
    "def test_it(monkeypatch):\n    monkeypatch.setattr('app.core.LIMIT', 1)\n",
    "from unittest.mock import patch\n@patch(\"app.core.LIMIT\", 1)\ndef test_it(): pass\n",
])
def test_every_way_a_test_reaches_a_module_counts_as_an_import(app, statement):
    tree(app, {"tests/test_form.py": statement})
    assert selected(app, "app/core.py")["tests/test_form.py"] == "imports app/core.py"


def test_relative_imports_packages_and_neighbours_resolve(tmp_path):
    root = tree(tmp_path, {
        "app/services/__init__.py": "",
        "app/services/llm/__init__.py": "from .engines import run\n",
        "app/services/llm/engines.py": "from . import prices\nfrom ..quota import spend\nimport json\n",
        "app/services/llm/prices.py": "",
        "app/services/quota.py": "",
        "scripts/report.py": "import shared\nfrom scripts import shared as again\n",
        "scripts/shared.py": "",
        "tests/test_engines.py": "from app.services.llm import engines\n",
        "tests/test_quota.py": "from app.services import quota\n",
    })
    texts = cc.read_tree(root)
    pulls = cc.Imports(texts, set(texts)).pulls
    assert pulls["app/services/llm/__init__.py"] == {"app/services/llm/engines.py"}
    assert pulls["app/services/llm/engines.py"] == {
        "app/services/llm/__init__.py", "app/services/llm/prices.py", "app/services/__init__.py", "app/services/quota.py"}
    assert pulls["scripts/report.py"] == {"scripts/shared.py"}
    # Importing a module runs the packages above it.
    assert pulls["tests/test_engines.py"] == {
        "app/services/__init__.py", "app/services/llm/__init__.py", "app/services/llm/engines.py"}
    assert selected(root, "app/services/__init__.py").keys() == {"tests/test_engines.py", "tests/test_quota.py"}


def test_a_helper_or_a_test_file_that_others_import_from_selects_them(tmp_path):
    root = tree(tmp_path, {
        "app/store.py": "",
        "tests/store_support.py": "from app import store\n",
        "tests/test_store.py": "import app.store\n",
        "tests/test_with_helper.py": "from store_support import fake\n",
        "tests/test_with_fixture.py": "from test_store import fixture\n",
    })
    assert selected(root, "tests/store_support.py") == {"tests/test_with_helper.py": "imports tests/store_support.py"}
    assert selected(root, "tests/test_store.py") == {
        "tests/test_store.py": "changed", "tests/test_with_fixture.py": "imports tests/test_store.py"}
    assert selected(root, "app/store.py").keys() == {"tests/test_store.py"}


def test_a_template_selects_the_tests_of_the_module_that_renders_it(tmp_path):
    root = tree(tmp_path, {
        "main.py": "from app import pages\n",
        "app/pages.py": 'def home(request):\n    return templates.TemplateResponse(request=request, name="index.html")\n',
        "templates/index.html": '{% include "partials/head.html" %}\n',
        "templates/partials/head.html": "",
        "tests/test_pages.py": "from app import pages\n",
        "tests/test_main.py": "import main\n",
        "tests/test_reads.py": 'text = (ROOT / "templates" / "index.html").read_text()\n',
    })
    assert selected(root, "templates/index.html") == {
        "tests/test_pages.py": "imports templates/index.html", "tests/test_reads.py": "names templates/index.html"}
    assert selected(root, "templates/partials/head.html") == {
        "tests/test_pages.py": "imports templates/partials/head.html",
        "tests/test_reads.py": "names templates/index.html, which pulls in templates/partials/head.html"}


def test_a_removed_module_still_selects_the_tests_importing_it(app):
    (app / "app/core.py").unlink()
    assert selected(app, "app/core.py") == {"tests/test_core.py": "imports app/core.py"}


def test_a_test_naming_a_changed_file_runs(tmp_path):
    root = tree(tmp_path, {
        "tests/test_reads.py": 'SCRIPT = ROOT / "static" / "js" / "agent-mode.js"\n',
        "tests/test_path.py": 'text = read("static/js/agent-mode.js")\n',
        "tests/test_longer_name.py": 'text = read("static/js/my-agent-mode.js") + read("agent-mode.json")\n',
        "tests/js/loads.test.mjs": 'loadScripts(["static/js/agent-mode.js"]);\n',
        "tests/e2e/test_page.py": '"""Shows what static/js/agent-mode.js renders."""\n',
        "tests/rules/firestore.rules.test.mjs": 'readFileSync("firestore.rules");\n',
    })
    plan = cc.select(root, ["static/js/agent-mode.js"])
    assert plan.suites["backend"].files == {
        "tests/test_reads.py": "names static/js/agent-mode.js", "tests/test_path.py": "names static/js/agent-mode.js"}
    assert plan.suites["frontend"].files == {"tests/js/loads.test.mjs": "names static/js/agent-mode.js"}
    assert plan.suites["browser"].files == {"tests/e2e/test_page.py": "names static/js/agent-mode.js"}
    assert not plan.suites["rules"].files
    assert cc.select(root, ["firestore.rules"]).not_started() == [".\\dev.ps1 check rules"]


def test_what_a_helper_names_its_tests_name_but_not_what_another_test_names(tmp_path):
    root = tree(tmp_path, {
        "tests/js/helpers/boot.mjs": 'const TEMPLATE = read("templates/index.html");\n',
        "tests/js/dialog.test.mjs": 'import { boot } from "./helpers/boot.mjs";\n',
        "tests/js/plain.test.mjs": 'import { expect } from "vitest";\n',
        "tests/ui_text.py": 'TEMPLATE = ROOT / "templates" / "index.html"\n',
        "tests/test_copy.py": "from ui_text import texts\n",
        "tests/test_borrows.py": "from test_copy import helper\n",
    })
    plan = cc.select(root, ["templates/index.html"])
    assert plan.suites["frontend"].files.keys() == {"tests/js/dialog.test.mjs"}
    assert plan.suites["backend"].files.keys() == {"tests/test_copy.py"}


def test_a_file_name_every_folder_has_counts_only_with_its_folder(tmp_path):
    root = tree(tmp_path, {
        "tests/test_archive.py": 'ARCHIVE = tarball({"README.md": b"# App"})\n',
        "tests/test_setup.py": 'text = (ROOT / "tests/e2e/README.md").read_text()\n',
    })
    assert selected(root, "tests/e2e/README.md").keys() == {"tests/test_setup.py"}


def test_a_changed_test_file_is_not_a_name_other_tests_are_selected_by(tmp_path):
    root = tree(tmp_path, {
        "tests/test_first.py": "",
        "tests/test_second.py": '"""The cases for the dialog are in tests/test_first.py."""\n',
    })
    assert selected(root, "tests/test_first.py") == {"tests/test_first.py": "changed"}


def test_a_file_that_pulls_the_changed_one_in_carries_its_name_on(tmp_path, monkeypatch):
    root = tree(tmp_path, {
        "static/js/bundles.json": '{"groups": [{"files": ["static/js/run-view.js"]}]}',
        "static/style.css": "@import url('./css/base.css');\n",
        "static/css/base.css": '@import "./tokens.css";\n',
        "static/css/tokens.css": "",
        "templates/landing.html": '{% include "partials/nav.html" %}\n',
        "templates/partials/nav.html": "",
        "scripts/i18n.py": "from app import words\n",
        "app/words.py": "",
        "tests/test_order.py": 'BUNDLES = ROOT / "static" / "js" / "bundles.json"\n',
        # Prose about the bundle list does not read the scripts in it.
        "tests/test_prose.py": "# The order of /app is in bundles.json, not here.\n",
        "tests/test_sheet.py": 'css = (ROOT / "static" / "style.css").read_text()\n',
        "tests/test_landing.py": 'page = render("landing.html")\n',
        "tests/test_cli.py": 'subprocess.run([sys.executable, "scripts/i18n.py", "check"])\n',
    })
    assert selected(root, "static/js/run-view.js") == {
        "tests/test_order.py": "names static/js/bundles.json, which pulls in static/js/run-view.js"}
    assert selected(root, "static/css/tokens.css").keys() == {"tests/test_sheet.py"}
    assert selected(root, "templates/partials/nav.html").keys() == {"tests/test_landing.py"}
    # A script is a module like any other: the test that runs it is one
    # module away from what the script imports.
    assert selected(root, "scripts/i18n.py").keys() == {"tests/test_cli.py"}
    assert selected(root, "app/words.py") == {}
    monkeypatch.setattr(cc, "IMPORT_HOPS", 1)
    assert selected(root, "app/words.py").keys() == {"tests/test_cli.py"}


def test_build_output_is_named_as_a_folder(tmp_path):
    root = tree(tmp_path, {
        "tests/test_build.py": 'DIST = ROOT / "static" / "dist"\n',
        "tests/test_manifest.py": 'name = "manifest.json"\n',
    })
    plan = cc.select(root, ["static/dist/manifest.json", "static/dist/app.3f9a.js"])
    assert plan.suites["backend"].files == {"tests/test_build.py": "names static/dist"}
    assert plan.build_check


def test_a_test_that_walks_a_folder_runs_for_every_file_of_its_kind_there(tmp_path):
    # The calls are written in two parts: spelled out, this file would count
    # as walking those folders itself and run for every change in them.
    root = tree(tmp_path, {
        "tests/test_sheets.py": 'for sheet in (ROOT / "static" / "css").' + 'glob("*.css"):\n    pass\n',
        "tests/test_runtime.py": 'for module in Path("app").r' + 'glob("*.py"):\n    pass\n',
        "tests/test_no_walk.py": 'one = ROOT / "static" / "css" / "base.css"\n',
        "tests/js/syntax.test.mjs": 'for (const name of readdir' + 'Sync("static/js")) check(name, ".js");\n',
    })
    assert selected(root, "static/css/new.css") == {"tests/test_sheets.py": "walks static/ for *.css"}
    assert selected(root, "static/css/notes.txt") == {}
    assert selected(root, "app/services/new.py") == {"tests/test_runtime.py": "walks app/ for *.py"}
    assert selected(root, "static/js/new.js", suite="frontend") == {"tests/js/syntax.test.mjs": "walks static/ for *.js"}


def test_the_fixed_tests_run_for_every_change_the_ci_runs_for(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, "ALWAYS", {"tests/test_lists.py": "a list across modules", "tests/test_gone.py": "renamed"})
    root = tree(tmp_path, {"tests/test_lists.py": "", "app/x.py": ""})
    assert selected(root, "app/x.py") == {"tests/test_lists.py": "always: a list across modules"}
    assert selected(root, "docs/testing.md", "AGENTS.md") == {}
    assert selected(root, "docs/testing.md", "app/x.py").keys() == {"tests/test_lists.py"}


@pytest.mark.parametrize("path", [
    "tests/conftest.py", "requirements.txt", "requirements-test.txt", "package.json", "package-lock.json",
    ".python-version", "dev.ps1", "pytest.ini", "vitest.config.mjs",
])
def test_setup_and_runner_files_run_the_whole_suites(app, path):
    plan = cc.select(app, [path])
    assert plan.suites["backend"].whole == f"{path} changed"
    assert plan.suites["frontend"].whole == f"{path} changed"
    assert plan.as_json()["backend"] == {"whole": True, "files": []}


def test_a_selection_of_a_large_share_runs_the_whole_suite(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, "WHOLE_SUITE_SHARE", 0.5)
    files = {"app/hub.py": "", "tests/test_1.py": "import app.hub\n", "tests/test_2.py": "", "tests/test_3.py": ""}
    root = tree(tmp_path, files)
    assert not cc.select(root, ["app/hub.py"]).suites["backend"].whole
    tree(root, {"tests/test_2.py": "import app.hub\n"})
    plan = cc.select(root, ["app/hub.py"])
    assert plan.suites["backend"].whole == "2 of 3 test files are affected"
    assert not plan.suites["frontend"].whole


def test_build_check_runs_for_build_inputs_only(app):
    assert cc.select(app, ["static/css/base.css"]).build_check
    assert cc.select(app, ["scripts/build_frontend.mjs"]).build_check
    assert not cc.select(app, ["app/core.py", "templates/index.html"]).build_check


DIFF = """\
diff --git a/templates/index.html b/templates/index.html
--- a/templates/index.html
+++ b/templates/index.html
@@ -10 +10 @@
-<button id="sendButton" class="composer-send is-ready" aria-label="Send message">Send</button>
+<button id="sendQuestion" class="composer-send" aria-label="Send the question">Ask</button>
diff --git a/static/js/agent-mode.js b/static/js/agent-mode.js
--- a/static/js/agent-mode.js
+++ b/static/js/agent-mode.js
@@ -5,0 +6,3 @@
+  row.classList.toggle("agent-row-open", open);
+  if (event.key === "Enter") status.textContent = t("Reading the sources");
+  document.querySelector("#toast .toast-text").hidden = true;
diff --git a/static/css/shell.css b/static/css/shell.css
--- a/static/css/shell.css
+++ b/static/css/shell.css
@@ -3,2 +3,2 @@
-.side-panel > .panel-head {
-  color: #fafafa; background: url(icons/close.svg); transition: 0.3s;
+.side-panel > .panel-title {
+  color: #abcdef;
diff --git a/app/services/mail.py b/app/services/mail.py
--- a/app/services/mail.py
+++ b/app/services/mail.py
@@ -1 +1 @@
--- "Your watch is paused"
+++ "Your watch has been paused"
diff --git a/static/dist/app.1a2b.js b/static/dist/app.1a2b.js
--- a/static/dist/app.1a2b.js
+++ b/static/dist/app.1a2b.js
@@ -1 +1 @@
-const built = '<p id="builtOnly">Only in the bundle</p>';
+const built = "";
"""


def test_the_removed_lines_give_the_ids_classes_and_texts_that_are_gone():
    tokens = cc.ui_tokens(DIFF)
    # composer-send and side-panel stay on the line, the script only adds.
    assert tokens.ids == {"sendButton"}
    assert tokens.classes == {"is-ready", "panel-head"}
    # A removed line that itself starts with "-- " is no file header.
    assert {"Send message", "Send", "Your watch is paused"} <= tokens.texts
    added = {"Send the question", "Reading the sources", "Your watch has been paused", "Only in the bundle"}
    assert not added & tokens.texts

    moved = DIFF.replace('+<button id="sendQuestion" class="composer-send" aria-label="Send the question">Ask</button>',
                         '+<button id="sendButton" class="composer-send is-ready" aria-label="Send message">Send</button>')
    assert not cc.ui_tokens(moved).ids and "Send" not in cc.ui_tokens(moved).texts


def test_browser_tests_are_named_by_what_they_ask_the_page_for_and_never_started(tmp_path):
    root = tree(tmp_path, {
        "tests/e2e/test_send.py": 'page.click("#sendButton")\n',
        "tests/e2e/test_mail.py": 'expect(page.locator("main")).to_contain_text("Your watch is paused")\n',
        "tests/e2e/test_panel.py": 'page.locator(".side-panel .panel-head")\n',
        "tests/e2e/test_role.py": "page.get_by_role('button', name='Send')\n",
        # What the change adds or leaves in place is no reason to name a test.
        "tests/e2e/test_unrelated.py": 'page.locator("#toast .toast-text")\npage.locator(".composer-send")\n'
                                       'expect(status).to_have_text("Reading the sources")\npage.click("#send")\n',
        "tests/e2e/native_support.py": 'SEND = "#sendButton"\n',
    })
    plan = cc.select(root, ["templates/index.html", "static/js/agent-mode.js"], DIFF)
    assert plan.suites["browser"].files == {
        "tests/e2e/test_send.py": "uses sendButton",
        "tests/e2e/test_mail.py": 'shows "Your watch is paused"',
        "tests/e2e/test_panel.py": "uses panel-head",
        "tests/e2e/test_role.py": 'shows "Send"',
    }
    assert plan.not_started() == [
        ".\\dev.ps1 check browser -TestPath tests/e2e/test_mail.py,tests/e2e/test_panel.py,tests/e2e/test_role.py,"
        "tests/e2e/test_send.py"]
    assert "browser" not in plan.as_json() and plan.as_json()["not_started"] == plan.not_started()
    whole = cc.select(root, ["tests/e2e/conftest.py"])
    assert whole.suites["browser"].whole and not whole.not_started()


def test_the_report_says_what_runs_and_why_in_a_few_lines(tmp_path):
    root = tree(tmp_path, {
        "app/x.py": "",
        "tests/test_x.py": "import app.x\n",
        "tests/test_reads.py": 'open("static/css/base.css")\n',
        "tests/js/x.test.mjs": "",
        "tests/e2e/test_page.py": 'open("static/css/base.css")\n',
    })
    plan = cc.select(root, ["app/x.py", "static/css/base.css"])
    assert cc.report(plan, "origin/main").splitlines() == [
        "[changed] 2 changed file(s) against origin/main: x.py, base.css",
        "[changed] backend: 2 of 2 test files",
        "  1 import a changed file: test_x.py",
        "  1 name a changed file: test_reads.py",
        "[changed] frontend: no test file, only build:check",
        "[changed] browser, not started here: 1 of 1 test files",
        "  1 name a changed file: test_page.py",
        "[changed] start those with: .\\dev.ps1 check browser -TestPath tests/e2e/test_page.py",
    ]
    assert "  tests/test_x.py: imports app/x.py" in cc.report(plan, "origin/main", why=True)
    assert cc.report(cc.select(root, []), "origin/main") == "[changed] Nothing differs from origin/main: nothing to run."


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
    root = tree(tmp_path / "repo", {
        "app/kept.py": "", "app/committed.py": "", "app/staged.py": "", "app/edited.py": "", "app/removed.py": "",
        "templates/index.html": '<h1 id="oldHeading">Old</h1>\n', "static/dist/app.js": "old\n",
    })
    _git(root, "init", "-b", "main")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base")
    _git(root, "branch", "published")
    return root


def test_changes_are_the_commits_the_index_the_working_tree_and_new_files(repo):
    (repo / "app/committed.py").write_text("x = 1\n")
    _git(repo, "commit", "-am", "work")
    (repo / "app/staged.py").write_text("x = 1\n")
    _git(repo, "add", "app/staged.py")
    (repo / "app/edited.py").write_text("x = 1\n")
    (repo / "app/removed.py").unlink()
    (repo / "app/new.py").write_text("")
    (repo / "templates/index.html").write_text('<h1 id="newHeading">New</h1>\n')
    (repo / "static/dist/app.js").write_text('new id="builtOnly"\n')
    changes, diff = cc.changes_since(repo, "published")
    assert sorted(changes) == [
        "app/committed.py", "app/edited.py", "app/new.py", "app/removed.py", "app/staged.py", "static/dist/app.js",
        "templates/index.html",
    ]
    # The diff for the browser tests leaves the build output out.
    assert cc.ui_tokens(diff).ids == {"oldHeading"} and "builtOnly" not in diff


def test_main_writes_the_plan_dev_ps1_runs_and_fails_without_the_base(repo, tmp_path, monkeypatch, capsys):
    tree(repo, {"scripts/check_changed.py": "", "tests/test_kept.py": "import app.kept\n", "tests/js/a.test.mjs": ""})
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "tests")
    _git(repo, "branch", "--force", "published")
    monkeypatch.setattr(cc, "__file__", str(repo / "scripts" / "check_changed.py"))
    (repo / "app/kept.py").write_text("x = 1\n")
    plan = tmp_path / "plan.json"
    assert cc.main(["--base", "published", "--plan", str(plan)]) == 0
    assert json.loads(plan.read_text(encoding="utf-8")) == {
        "changed": ["app/kept.py"],
        "backend": {"whole": False, "files": ["tests/test_kept.py"]},
        "frontend": {"whole": False, "files": []},
        "build_check": False,
        "not_started": [],
    }
    assert "[changed] backend: 1 of 1 test files" in capsys.readouterr().out

    plan.unlink()
    assert cc.main(["--base", "origin/main", "--plan", str(plan)]) == 2
    assert "git fetch origin main" in capsys.readouterr().err
    assert not plan.exists()


def test_the_fixed_lists_point_at_files_that_exist():
    assert all((ROOT / test).is_file() and cc.suite_of(test) == "backend" for test in cc.ALWAYS), cc.ALWAYS
    literal = [pattern for pattern in cc.WHOLE_SUITE if "*" not in pattern]
    assert all((ROOT / path).is_file() for path in literal), literal
    assert all((ROOT / folder).is_dir() for folder in cc.SCANNED)
    assert all((ROOT / path).is_file() for path in cc.SCANNED_FILES)


@pytest.fixture(scope="module")
def repository():
    """The real tree and its imports, read once: every case here changes a
    file that exists, so what the files import stays the same."""
    texts = cc.read_tree(ROOT)
    imports = cc.Imports(texts, set(texts))
    patch = pytest.MonkeyPatch()
    patch.setattr(cc, "read_tree", lambda root: texts)
    patch.setattr(cc, "Imports", lambda texts, known: imports)
    yield ROOT
    patch.undo()


@pytest.mark.parametrize("changed,test", [
    # A tool more in REPEATABLE_TOOLS breaks the test that names them all.
    ("app/services/agent_delegation.py", "tests/test_agent_turn_limits.py"),
    # The tests that walk a tree are the ones most often red on main.
    ("app/services/agent_tools.py", "tests/test_logging_redaction_contract.py"),
    ("static/css/shell.css", "tests/test_forced_colors.py"),
    ("static/css/landing.css", "tests/test_public_design_system.py"),
    ("static/js/agent-mode.js", "tests/test_ui_copy.py"),
    ("templates/index.html", "tests/test_ui_copy.py"),
    # Renders /app through the route and never names the template.
    ("templates/index.html", "tests/test_og_cards.py"),
    ("static/dist/manifest.json", "tests/test_frontend_build.py"),
    ("app/i18n/de/app-shell.json", "tests/test_i18n.py"),
])
def test_the_changes_that_turned_main_red_select_their_test(repository, changed, test, monkeypatch):
    # Found by a rule, not only because the test is on the fixed list.
    monkeypatch.setattr(cc, "ALWAYS", {})
    assert (ROOT / changed).exists() or changed.startswith("static/dist/"), changed
    assert test in selected(repository, changed)


def test_a_script_of_the_app_selects_the_javascript_tests_that_load_it(repository):
    files = selected(repository, "static/js/app-state.js", suite="frontend")
    assert files["tests/js/app-state.test.mjs"] == "names static/js/app-state.js"
