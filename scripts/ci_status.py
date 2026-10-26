"""Read the CI result of main from GitHub, without a login.

Red runs are not read from the inbox: whoever pushes checks their own run,
and the daily CI watcher reads the last day. Failed tests come from the
annotations that scripts/ci_annotate_failures.py writes, so no login (and
no token) is needed; the public API allows 60 requests per hour and IP.

  python scripts/ci_status.py              runs on main in the last 26 hours
  python scripts/ci_status.py --hours 72   a longer window
  python scripts/ci_status.py --wait       wait for the run of the local HEAD
  python scripts/ci_status.py --wait --sha <commit>

Exit code: 0 all green, 1 failed tests, 2 unknown (no run, timeout, API).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = "sudoleo/consens"
WORKFLOW = "Regression tests"
API = f"https://api.github.com/repos/{REPO}"
POLL_SECONDS = 60
WAIT_MINUTES = 40
# Annotations GitHub adds to every failed or cancelled step; the test names
# say more.
NOISE = ("Process completed with exit code", "The operation was canceled.")
# A job over its time limit ends cancelled, like one a newer run or a person
# cancelled, but it failed: the nightly browser suite ran into it unseen
# (2026-10-25).
TIMED_OUT = "exceeded the maximum execution time"


class ApiError(Exception):
    pass


def get(path):
    request = urllib.request.Request(API + path, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "consens-ci-status"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 403 and exc.headers.get("X-RateLimit-Remaining") == "0":
            reset = datetime.fromtimestamp(int(exc.headers.get("X-RateLimit-Reset", "0")), timezone.utc)
            raise ApiError(f"GitHub rate limit reached until {reset:%H:%M} UTC; try again then.") from exc
        raise ApiError(f"GitHub API {exc.code} for {path}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ApiError(f"GitHub API unreachable: {exc}") from exc


def runs(**query):
    params = "&".join(f"{key}={value}" for key, value in {"per_page": 50, **query}.items())
    return [run for run in get(f"/actions/runs?{params}")["workflow_runs"] if run["name"] == WORKFLOW]


def failures(run):
    """Failed jobs of a run, each with its failed tests (or other errors)."""
    found = []
    for job in get(f"/actions/runs/{run['id']}/jobs")["jobs"]:
        if job["conclusion"] in ("success", "skipped", None):
            continue
        notes = [note for note in get(f"/check-runs/{job['id']}/annotations")
                 if note["annotation_level"] == "failure" and not note["message"].startswith(NOISE)]
        if job["conclusion"] == "cancelled" and not any(TIMED_OUT in note["message"] for note in notes):
            continue
        messages = []
        for note in notes:
            title = note.get("title") or ""
            messages.append((title + " :: " if title else "") + note["message"].strip())
        if not messages:
            steps = [step["name"] for step in job.get("steps", []) if step.get("conclusion") == "failure"]
            messages.append("failed step: " + (", ".join(steps) or "unknown") + " (log needs a GitHub login)")
        found.append((job["name"], job["html_url"], messages))
    return found


def describe(run):
    when = run["created_at"].replace("T", " ").replace("Z", " UTC")
    return f"{run['event']:<17} {run['head_sha'][:8]}  {when}  {run['html_url']}"


def report(run, found):
    print(("RED   " if found else "green ") + describe(run))
    for job, url, messages in found:
        print(f"      job {job}: {url}")
        for message in messages:
            lines = message.splitlines()
            print("        - " + lines[0][:300])
            for line in lines[1:12]:
                print("          " + line[:300])


def recent(hours):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    chosen = [run for run in runs(branch="main") if run["status"] == "completed"
              and datetime.fromisoformat(run["created_at"].replace("Z", "+00:00")) >= since]
    red = shown = 0
    for run in chosen:
        found = failures(run) if run["conclusion"] != "success" else []
        if run["conclusion"] == "cancelled" and not found:
            continue  # cancelled by a newer run or by hand, not by the time limit
        red += bool(found)
        shown += 1
        report(run, found)
    if not shown:
        print(f"No completed run on main in the last {hours} hours.")
        return 2
    print(f"\n{red} of {shown} runs red." if red else f"\nAll {shown} runs green.")
    return 1 if red else 0


def wait(sha):
    deadline = time.monotonic() + WAIT_MINUTES * 60
    while True:
        mine = [run for run in runs(head_sha=sha) if run["event"] == "push"]
        if mine and all(run["status"] == "completed" for run in mine):
            break
        if time.monotonic() > deadline:
            print(f"No finished push run for {sha[:8]} after {WAIT_MINUTES} minutes "
                  "(docs-only pushes start none).")
            return 2
        time.sleep(POLL_SECONDS)
    red = 0
    for run in mine:
        found = failures(run) if run["conclusion"] != "success" else []
        red += bool(found)
        report(run, found)
    return 1 if red else 0


def main():
    # A Windows console (cp1252) cannot print every character of a test's
    # failure text; it crashed the report of a red run (2026-10-23).
    sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hours", type=int, default=26)
    parser.add_argument("--wait", action="store_true", help="wait for the push run of --sha (default HEAD)")
    parser.add_argument("--sha", default="HEAD")
    args = parser.parse_args()
    try:
        if args.wait:
            sha = subprocess.run(["git", "rev-parse", args.sha], capture_output=True, text=True, check=True).stdout.strip()
            return wait(sha)
        return recent(args.hours)
    except ApiError as exc:
        print(exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
