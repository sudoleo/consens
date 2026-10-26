"""Print failed JUnit tests as GitHub Actions error annotations.

Job logs need a GitHub login; annotations do not. The failure mail links to
the run, and its annotations name each failed test with the end of its
message, so a red run can be read (and fixed) without signing in.

A suite cut off by the job's time limit leaves no JUnit report. Given the
progress log tests/e2e/conftest.py writes as the suite goes, the annotation
then names the test that was still running and the slowest ones before it.

Usage: python scripts/ci_annotate_failures.py test-results/<suite>.xml [<progress log>]
"""
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

# GitHub keeps at most 10 error annotations per step: nine tests in detail,
# the tenth lists the names of the rest.
LIMIT = 9
# The test's own lines in the traceback. The end of a Playwright or Firestore
# error is the library's frames, not the wait in the test that ran out (a
# timed-out wait_for_function named no line, nightly run 2026-10-24).
TEST_FRAME = re.compile(r"^(tests/[\w./-]+\.py:\d+)", re.M)
SLOWEST = 8


def escape(text):
    return text.replace("%", "%25").replace("\r", "").replace("\n", "%0A")


def cut_off(path, now=None):
    """Name what the time limit cut off, from the progress log of the suite."""
    started, took = {}, []
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        stamp, event, nodeid = line.split(" ", 2)
        if event == "start":
            started[nodeid] = float(stamp)
        elif nodeid in started:
            took.append((float(stamp) - started.pop(nodeid), nodeid))
    if not lines:
        print(f"::error title=No test report::{escape(f'{path}: no browser test started (setup or the rules tests failed or ran out of time)')}")
        return
    now = time.time() if now is None else now
    running = "\n".join(f"{nodeid} (running for {now - start:.0f} s)" for nodeid, start in started.items())
    print(f"::error title=Suite cut off after {len(took)} tests::"
          + escape("Still running when the time ran out:\n" + (running or "none, between two tests")))
    slowest = "\n".join(f"{seconds:.0f} s  {nodeid}" for seconds, nodeid in sorted(took, reverse=True)[:SLOWEST])
    if slowest:
        print(f"::error title=Slowest finished tests::{escape(slowest)}")


def main(path, progress=None):
    try:
        cases = list(ET.parse(path).iter("testcase"))
    except (OSError, ET.ParseError) as exc:
        if progress:
            return cut_off(progress)
        print(f"::error title=No test report::{escape(f'{path}: {exc}')}")
        return
    failed = [(case, problem) for case in cases
              for problem in [*case.iter("failure"), *case.iter("error")]]
    for case, problem in failed[:LIMIT]:
        frames = list(dict.fromkeys(TEST_FRAME.findall(problem.text or "")))
        where = "at " + ", ".join(frames[-3:]) + "\n" if frames else ""
        text = where + (problem.get("message") or "") + "\n" + (problem.text or "")[-1500:]
        print(f"::error title={case.get('classname')}::{case.get('name')}%0A{escape(text)}")
    if len(failed) > LIMIT:
        names = "\n".join(f"{case.get('classname')}::{case.get('name')}" for case, _ in failed[LIMIT:])
        print(f"::error title={len(failed) - LIMIT} more failed tests::{escape(names)}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
