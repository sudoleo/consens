"""Check this documentation snapshot without executing the application or tests.

Run from any directory: python /path/to/repo/docs/test-coverage/check_inventory.py
This does not update hashes or infer that old review descriptions remain correct.
"""

from collections import Counter
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CATALOG = Path(__file__).with_name("inventory.json")


def read_inventory():
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def python_definitions(source):
    """Source anchors, not semantic assertions or newly collected runner cases."""
    definitions = []

    def visit(node, classes=()):
        if isinstance(node, ast.ClassDef):
            classes += (node.name,)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            evidence = set()
            for child in ast.walk(node):
                if isinstance(child, ast.Assert):
                    evidence.add((child.lineno, "assert"))
                if isinstance(child, ast.Call):
                    function = ast.unparse(child.func)
                    last = function.rsplit(".", 1)[-1]
                    if function == "expect":
                        evidence.add((child.lineno, "playwright_expect"))
                    elif last == "wait_for_function":
                        evidence.add((child.lineno, "wait_for_function"))
                    elif last == "fail":
                        evidence.add((child.lineno, "explicit_failure"))
                    elif last.startswith("assert") or function == "pytest.raises":
                        evidence.add((child.lineno, "assertion_or_helper_call"))
            definitions.append({"name": "::".join(classes + (node.name,)),
                                "line": node.lineno, "end_line": node.end_lineno,
                                "anchors": evidence})
        for child in ast.iter_child_nodes(node):
            visit(child, classes)

    visit(ast.parse(source))
    return definitions


def check_definition_anchors(item, actual, problems):
    expected = {(d["name"], d["line"], d["end_line"]) for d in actual}
    recorded = {(d["name"], d["line"], d["end_line"]) for d in item["definitions"]}
    if expected != recorded or len(recorded) != len(item["definitions"]):
        problems.append(f"Definition identity/location differs from parsed source: {item['path']}")
    by_key = {(d["name"], d["line"], d["end_line"]): d for d in actual}
    for definition in item["definitions"]:
        parsed = by_key.get((definition["name"], definition["line"], definition["end_line"]))
        if not parsed:
            continue
        recorded_assertions = {(a["line"], a["kind"]) for a in definition["assertion_evidence"]}
        if "registration" in parsed:
            anchors = {(line, "expect") for line in parsed["assertion_lines"]}
            if definition.get("registration") != parsed["registration"]:
                problems.append(f"JavaScript registration differs: {item['path']}:{definition['line']}")
        else:
            anchors = parsed["anchors"]
        if recorded_assertions != anchors:
            problems.append(f"Assertion anchors differ from parsed source: {item['path']}:{definition['line']}")


def main():
    data = read_inventory()
    problems = []
    files = data["files"]
    paths = [item["path"] for item in files]
    javascript = [p for p in paths if p.endswith(".mjs")]
    try:
        js_definitions = json.loads(subprocess.check_output(
            ["node", str(CATALOG.with_name("javascript_evidence.mjs")), *javascript],
            cwd=ROOT, text=True, stderr=subprocess.PIPE))
    except (OSError, subprocess.CalledProcessError, ValueError):
        js_definitions = {}
        problems.append("Cannot parse JavaScript evidence; node and locked npm dependencies required (npm ci)")
    if len(paths) != len(set(paths)):
        problems.append("Duplicate test paths in inventory")
    actual = {
        str(path.relative_to(ROOT))
        for pattern in ("test_*.py", "*_test.py", "*.test.mjs")
        for path in (ROOT / "tests").rglob(pattern)
    }
    missing = actual - set(paths)
    removed = set(paths) - actual
    problems.extend(f"New/unreviewed test file: {path}" for path in sorted(missing))
    problems.extend(f"Removed test file: {path}" for path in sorted(removed))

    for item in files + data["support_files"] + data.get("reference_files", []):
        path = ROOT / item["path"]
        if not path.is_file():
            problems.append(f"Missing source: {item['path']}")
            continue
        source = path.read_bytes()
        if hashlib.sha256(source).hexdigest() != item["sha256"]:
            problems.append(f"Changed; review required: {item['path']}")
        if "definitions" not in item:
            continue
        length = len(source.decode("utf-8").splitlines())
        if path.suffix == ".py":
            check_definition_anchors(item, python_definitions(source.decode("utf-8-sig")), problems)
        elif item["path"] in js_definitions:
            check_definition_anchors(item, js_definitions[item["path"]], problems)
        if length != item["source_lines"]:
            problems.append(f"Line count changed: {item['path']}")
        for definition in item["definitions"]:
            if not 1 <= definition["line"] <= definition["end_line"] <= length:
                problems.append(f"Invalid definition location: {item['path']}::{definition['name']}")
            for evidence in definition["assertion_evidence"]:
                if not definition["line"] <= evidence["line"] <= definition["end_line"]:
                    problems.append(f"Invalid assertion location: {item['path']}:{evidence['line']}")
        for field, observed in (
            ("definition_count", len(item["definitions"])),
            ("runner_case_count", len(item["cases"])),
        ):
            if item[field] != observed:
                problems.append(f"Inconsistent {field}: {item['path']}")
        if dict(Counter(case["status"] for case in item["cases"])) != item["execution"]:
            problems.append(f"Inconsistent execution counts: {item['path']}")
        if [case["report_ordinal"] for case in item["cases"]] != list(range(1, len(item["cases"]) + 1)):
            problems.append(f"Invalid report ordinals: {item['path']}")
        for key in ("level", "covers", "limits", "questions"):
            if not item.get(key):
                problems.append(f"Missing {key}: {item['path']}")

    observed_totals = {
        "files": len(files),
        "static_definitions": sum(item["definition_count"] for item in files),
        "runner_cases": sum(item["runner_case_count"] for item in files),
        "source_lines": sum(item["source_lines"] for item in files),
    }
    if observed_totals != data["totals"]:
        problems.append("Inventory totals do not match entries")

    try:
        diff = subprocess.run(
            ["git", "diff", "--name-only", data["base_commit"], "--",
             "app", "static", "templates", "scripts", "benchmark", "main.py"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        for changed in diff.stdout.splitlines():
            problems.append(f"Production source changed since review: {changed}")
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "--",
             "app", "static", "templates", "scripts", "benchmark", "main.py"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        for changed in untracked.stdout.splitlines():
            problems.append(f"New production source; review mapping: {changed}")
    except (OSError, subprocess.CalledProcessError):
        problems.append("Cannot compare production source with base commit; git history required")

    if problems:
        for problem in sorted(set(problems)):
            print(problem)
        return 1
    print(f"OK: {len(files)} files, {observed_totals['static_definitions']} definitions, "
          f"{observed_totals['runner_cases']} historical runner cases; hashes and parsed definition/assertion anchors match.")
    print("Historical execution evidence only; semantic coverage is not revalidated by this check.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
