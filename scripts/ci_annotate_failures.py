"""Print failed JUnit tests as GitHub Actions error annotations.

Job logs need a GitHub login; annotations do not. The failure mail links to
the run, and its annotations name each failed test with the end of its
message, so a red run can be read (and fixed) without signing in.

Usage: python scripts/ci_annotate_failures.py test-results/<suite>.xml
"""
import sys
import xml.etree.ElementTree as ET

# GitHub keeps at most 10 error annotations per step: nine tests in detail,
# the tenth lists the names of the rest.
LIMIT = 9


def escape(text):
    return text.replace("%", "%25").replace("\r", "").replace("\n", "%0A")


def main(path):
    try:
        cases = list(ET.parse(path).iter("testcase"))
    except (OSError, ET.ParseError) as exc:
        print(f"::error title=No test report::{escape(f'{path}: {exc}')}")
        return
    failed = [(case, problem) for case in cases
              for problem in [*case.iter("failure"), *case.iter("error")]]
    for case, problem in failed[:LIMIT]:
        text = (problem.get("message") or "") + "\n" + (problem.text or "")[-1500:]
        print(f"::error title={case.get('classname')}::{case.get('name')}%0A{escape(text)}")
    if len(failed) > LIMIT:
        names = "\n".join(f"{case.get('classname')}::{case.get('name')}" for case, _ in failed[LIMIT:])
        print(f"::error title={len(failed) - LIMIT} more failed tests::{escape(names)}")


if __name__ == "__main__":
    main(sys.argv[1])
