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
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
CATALOG = Path(__file__).with_name("inventory.json")

def file_sha256(path):
    """Git text checkouts may use CRLF; binary assets must stay byte-exact."""
    path = Path(path)
    value = path.read_bytes()
    if path.name == '.gitattributes' or path.suffix.lower() in {'.py', '.js', '.mjs', '.css', '.html', '.json', '.yml', '.yaml', '.ps1', '.rules', '.txt', '.md', '.ini', '.xml'}:
        value = value.replace(b'\r\n', b'\n')
    return hashlib.sha256(value).hexdigest()


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
            anchors = {(a["line"], a["kind"]) for a in parsed["assertion_evidence"]}
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
            cwd=ROOT, text=True, encoding="utf-8", stderr=subprocess.PIPE))
    except (OSError, subprocess.CalledProcessError, ValueError):
        js_definitions = {}
        problems.append("Cannot parse JavaScript evidence; node and locked npm dependencies required (npm ci)")
    if len(paths) != len(set(paths)):
        problems.append("Duplicate test paths in inventory")
    actual = {
        path.relative_to(ROOT).as_posix()
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
        if file_sha256(path) != item["sha256"]:
            problems.append(f"Changed; review required: {item['path']}")
        if "definitions" not in item:
            continue
        decoded = source.decode("utf-8")
        length = len(decoded.split("\n")) - decoded.endswith("\n")
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

    if data.get("schema_version", 1) >= 2:
        execution = json.loads(CATALOG.with_name("execution.json").read_text(encoding="utf-8"))
        if execution["source_commit"] != data["base_commit"] or execution["review_date"] != data["review_date"]:
            problems.append("Current execution source/date differs from inventory")
        for artifact in execution["artifacts"]:
            path = ROOT / artifact["path"]
            if not path.is_file() or file_sha256(path) != artifact["sha256"]:
                problems.append(f"Execution artifact changed: {artifact['path']}")
        for suite, recorded in execution["suites"].items():
            group = [item for item in files if item["suite"] == suite]
            statuses = Counter(c["status"] for item in group for c in item["cases"])
            expected = dict(files=len(group), definitions=sum(f["definition_count"] for f in group),
                            collected=sum(f["runner_case_count"] for f in group), result=dict(statuses))
            if expected != recorded:
                problems.append(f"Execution totals differ: {suite}")
        for label, suite in (("backend", "backend"), ("browser", "e2e")):
            path = ROOT / execution.get("runner_artifacts", {}).get(
                suite, f"docs/test-coverage/evidence/{label}-{data['review_date']}.xml")
            reported = Counter()
            for case in ET.parse(path).findall(".//testcase"):
                parts = case.get("classname").split(".")
                end = next(i for i, name in enumerate(parts) if name.startswith("test_"))
                file = "/".join(parts[:end+1]) + ".py"
                name = file + "::" + "::".join(parts[end+1:] + [case.get("name")])
                status = next((status for tag, status in (("error", "error"), ("failure", "failed"), ("skipped", "skipped")) if case.find(tag) is not None), "passed")
                reported[(name, status)] += 1
            inventoried = Counter((c["id"], c["status"]) for f in files if f["suite"] == suite for c in f["cases"] if c["status"] != "not_run")
            if inventoried != reported:
                problems.append(f"JUnit identities/statuses differ: {suite}")
        frontend_path = ROOT / execution.get("runner_artifacts", {}).get(
            "frontend", f"docs/test-coverage/evidence/frontend-{data['review_date']}.json")
        frontend = json.loads(frontend_path.read_text(encoding="utf-8"))
        reported = Counter((f["path"], c["id"], c["status"]) for f in frontend["files"] for c in f["cases"])
        inventoried = Counter((f["path"], c["id"], c["status"]) for f in files if f["suite"] == "frontend" for c in f["cases"])
        if reported != inventoried:
            problems.append("Vitest identities/statuses differ")
        if "rules" in execution["suites"]:
            rules_path = ROOT / execution["runner_artifacts"]["rules"]
            reported = Counter()
            for case in ET.parse(rules_path).findall(".//testcase"):
                status = next((status for tag, status in (("error", "error"), ("failure", "failed"), ("skipped", "skipped")) if case.find(tag) is not None), "passed")
                reported[(case.get("name"), status)] += 1
            inventoried = Counter((c["id"], c["status"]) for f in files if f["suite"] == "rules" for c in f["cases"])
            if reported != inventoried:
                problems.append("Node rules identities/statuses differ")

    try:
        diff = subprocess.run(
            ["git", "diff", "--name-only", data["base_commit"], "--",
             "app", "static", "templates", "scripts", "benchmark", "main.py", ":(exclude)static/dist"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
        )
        for changed in diff.stdout.splitlines():
            problems.append(f"Production source changed since review: {changed}")
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "--",
             "app", "static", "templates", "scripts", "benchmark", "main.py", ":(exclude)static/dist"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
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
          f"{observed_totals['runner_cases']} runner cases; hashes and parsed definition/assertion anchors match.")
    print("Execution dates and exclusions are recorded in execution.json; semantic coverage is not revalidated by this check.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
