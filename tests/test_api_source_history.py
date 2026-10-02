"""Historic API source checks retain owner, run, answer and revision binding."""
from copy import deepcopy
import pytest
from app.services import source_check_jobs
from app.services.source_check_repository import SourceCheckRepository
from app.services.api_run_repository import API_RUNS_COLLECTION
from adapter_test_support import http_adapter, api_adapter
from test_source_check_repository import FakeDb, make_plan
from test_contradiction_verification import plan, CONSENSUS


@pytest.fixture
def historical(api_adapter, monkeypatch):
    h = api_adapter
    h.source = SourceCheckRepository(FakeDb())
    monkeypatch.setattr(source_check_jobs, "repository", lambda: h.source)
    h.run = h.runs.create_or_get(
        uid="owner",
        api_key_id="a" * 64,
        idempotency_key="history",
        request_payload={"question": "Q"},
        model_plan={},
        tier="free",
    )[0]
    h.url = "/api/v1/consensus/runs/" + h.run["run_id"] + "/source-check"
    return h


def seed(h, source_plan):
    job = h.source.create(
        uid="owner", run_key="api:" + h.run["run_id"], plan=source_plan, origin="api"
    )
    h.db.documents[(API_RUNS_COLLECTION, h.run["run_id"])].update(
        status="succeeded",
        result={
            "consensus_response": CONSENSUS,
            "source_verification": deepcopy(job["snapshot"]),
        },
    )
    return job


def test_historic_api_source_pages_owner_cursor_revision_and_cache(historical):
    h = historical
    job = seed(h, make_plan(9))
    found = []
    cursor = 0
    while cursor is not None:
        response = h.client.get(
            h.url, params={"cursor": cursor}, headers={"X-API-Key": h.key}
        )
        assert response.status_code == 200, response.text
        assert set(map(str.strip, response.headers["cache-control"].split(","))) == {
            "private",
            "no-store",
        }
        data = response.json()
        found.extend(data["source_verification"]["findings"])
        cursor = data["next_cursor"]
    assert len(found) == 9
    assert h.client.get(h.url).status_code == 401
    assert h.client.get(h.url, headers={"X-API-Key": h.other_key}).status_code == 404
    for cursor, status in ((-1, 422), (100000, 400)):
        assert (
            h.client.get(
                h.url, params={"cursor": cursor}, headers={"X-API-Key": h.key}
            ).status_code
            == status
        )
    unchanged = h.client.get(
        h.url, params={"after_revision": 0}, headers={"X-API-Key": h.key}
    )
    assert unchanged.json()["unchanged"] is True
    h.source.claim(job["job_id"])
    assert (
        h.client.get(
            h.url, params={"revision": 0}, headers={"X-API-Key": h.key}
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "field", ["job_id", "run_id", "answer_version", "prompt_version"]
)
@pytest.mark.parametrize("params", [{}, {"after_revision": 0}])
def test_historic_api_rejects_mismatched_snapshot_on_full_and_unchanged_polls(
    historical, field, params
):
    h = historical
    seed(h, plan(run_id="api:" + h.run["run_id"]))
    assert h.client.get(h.url, headers={"X-API-Key": h.key}).status_code == 200
    h.db.documents[(API_RUNS_COLLECTION, h.run["run_id"])]["result"][
        "source_verification"
    ][field] = "wrong"
    response = h.client.get(h.url, params=params, headers={"X-API-Key": h.key})
    assert response.status_code == 404, response.text
    assert CONSENSUS not in response.text
