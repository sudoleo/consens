import runpy
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci_status.py"


def load(responses):
    script = runpy.run_path(str(SCRIPT), run_name="ci_status")
    script["failures"].__globals__["get"] = lambda path: responses[path]
    return script


def job(job_id, conclusion):
    return {"id": job_id, "name": f"job-{job_id}", "conclusion": conclusion,
            "html_url": f"https://example.test/{job_id}", "steps": []}


def note(message, title=""):
    return {"annotation_level": "failure", "message": message, "title": title}


def test_a_job_over_its_time_limit_is_red_and_a_cancelled_one_is_not():
    # Both end "cancelled"; only the time limit is a failure (nightly
    # browser suite 2026-10-25, unseen by the CI watcher).
    script = load({
        "/actions/runs/1/jobs": {"jobs": [job(10, "cancelled"), job(11, "cancelled"), job(12, "success")]},
        "/check-runs/10/annotations": [
            note("The job has exceeded the maximum execution time of 35m0s"),
            note("The operation was canceled."),
            note("Still running when the time ran out:\ntests/e2e/test_c.py::test_hangs", "Suite cut off after 2 tests"),
        ],
        "/check-runs/11/annotations": [note("Canceling since a higher priority waiting request exists"),
                                       note("The operation was canceled.")],
    })
    found = script["failures"]({"id": 1})
    assert [(name, messages) for name, _, messages in found] == [("job-10", [
        "The job has exceeded the maximum execution time of 35m0s",
        "Suite cut off after 2 tests :: Still running when the time ran out:\ntests/e2e/test_c.py::test_hangs",
    ])]


def test_requests_trust_certifi_besides_the_system_store(monkeypatch):
    # Windows' store lacked the issuer of api.github.com (2026-10-27): every
    # --wait after a push ended "unreachable" instead of green or red.
    import io
    import ssl
    import urllib.request

    import certifi

    seen = {}

    def urlopen(request, **kwargs):
        seen.update(kwargs)
        return io.BytesIO(b"{}")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    script = runpy.run_path(str(SCRIPT), run_name="ci_status")
    assert script["get"]("/x") == {}
    trusted = seen["context"].get_ca_certs()
    bundle = ssl.create_default_context(cafile=certifi.where()).get_ca_certs()
    assert bundle and all(cert in trusted for cert in bundle)
