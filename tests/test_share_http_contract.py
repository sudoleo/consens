"""App share POST reaches real snapshot/quota storage; OG route renders it."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO
import pytest
from PIL import Image, ImageDraw
from app.services import share_snapshots as snapshots, watch_service, og_image
from adapter_test_support import http_adapter, login
from test_share_feature import FakeDb, make_pending


@pytest.fixture
def share_http(http_adapter, monkeypatch):
    h = http_adapter
    h.share_db = FakeDb()
    h.result_id = "R" * 16
    h.share_db.stores[snapshots.PENDING_COLLECTION][h.result_id] = make_pending(
        uid="owner",
        question="Unique public question?",
        differences_data={
            "agreement": {"score": 71},
            "claims": [],
            "differences": [],
            "models_compared": ["OpenAI", "Gemini", "Mistral"],
        },
    )
    monkeypatch.setattr(snapshots, "db_firestore", h.share_db)
    monkeypatch.setattr(watch_service, "db_firestore", h.share_db)
    snapshots._share_cache.clear()
    og_image._cache.clear()
    yield h
    snapshots._share_cache.clear()
    og_image._cache.clear()


def test_app_share_publishes_authoritative_content_and_retry_does_not_charge_twice(
    share_http,
):
    h = share_http
    payload = {
        "result_id": h.result_id,
        "question": "FORGED",
        "consensus_md": "FORGED",
        "owner_uid": "stranger",
        "visibility": "private",
    }
    first = h.client.post("/api/share", json=payload, headers=login("owner"))
    assert first.status_code == 200, first.text
    data = first.json()
    stored = h.share_db.stores[snapshots.SHARES_COLLECTION][data["share_id"]]
    assert stored["owner_uid"] == "owner" and stored["visibility"] == "public"
    assert stored["question"] == "Unique public question?" and "FORGED" not in str(
        stored
    )
    assert data["path"] == snapshots.share_path(stored["slug"], data["share_id"])
    assert data["url"].endswith(data["path"]) and data["created"] is True
    before = deepcopy(dict(h.share_db.stores))
    second = h.client.post("/api/share", json=payload, headers=login("owner"))
    assert second.status_code == 200 and second.json()["created"] is False
    assert second.json()["share_id"] == data["share_id"]
    assert dict(h.share_db.stores) == before


@pytest.mark.parametrize(
    "identity,result,expected",
    [
        (None, "R" * 16, 401),
        ("stranger", "R" * 16, 403),
        ("owner", "missing", 404),
        ("owner", "", 400),
    ],
)
def test_app_share_rejects_unauthorized_or_missing_result(
    share_http, identity, result, expected
):
    h = share_http
    before = deepcopy(dict(h.share_db.stores))
    response = h.client.post(
        "/api/share",
        json={"result_id": result},
        headers=login(identity) if identity else {},
    )
    assert response.status_code == expected and "error" in response.json()
    assert not h.share_db.stores[snapshots.SHARES_COLLECTION]
    assert (
        h.share_db.stores[snapshots.PENDING_COLLECTION]
        == before[snapshots.PENDING_COLLECTION]
    )


def test_app_share_expiry_quota_and_transaction_failure_never_publish(share_http):
    h = share_http
    quota = snapshots._daily_share_quota_ref(h.share_db, "owner")
    quota.set(
        {
            "date": snapshots._utcnow().strftime("%Y-%m-%d"),
            "count": snapshots.SHARE_DAILY_LIMIT,
        }
    )
    response = h.client.post(
        "/api/share", json={"result_id": h.result_id}, headers=login("owner")
    )
    assert response.status_code == 429, response.text
    assert not h.share_db.stores[snapshots.SHARES_COLLECTION]
    quota.delete()
    h.share_db.fail_transaction_after_staged_writes = 1
    response = h.client.post(
        "/api/share", json={"result_id": h.result_id}, headers=login("owner")
    )
    assert response.status_code == 500 and "injected" not in response.text
    assert not h.share_db.stores[snapshots.SHARES_COLLECTION]
    h.share_db.fail_transaction_after_staged_writes = None
    h.share_db.stores[snapshots.PENDING_COLLECTION][h.result_id][
        "expires_at"
    ] = datetime.now(timezone.utc) - timedelta(seconds=1)
    response = h.client.post(
        "/api/share", json={"result_id": h.result_id}, headers=login("owner")
    )
    assert response.status_code == 404
    assert not h.share_db.stores[snapshots.SHARES_COLLECTION]


def test_og_http_route_renders_stored_question_score_and_private_revocation(
    share_http, monkeypatch
):
    h = share_http
    texts = []
    original = ImageDraw.ImageDraw.text

    def capture(self, xy, text, *args, **kwargs):
        texts.append(str(text))
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", capture)
    created = h.client.post(
        "/api/share", json={"result_id": h.result_id}, headers=login("owner")
    ).json()
    url = created["path"] + "/og.png"
    response = h.client.get(url)
    assert response.status_code == 200, response.text
    image = Image.open(BytesIO(response.content))
    assert (
        image.size == (1200, 630)
        and len(image.crop((72, 150, 1128, 430)).getcolors(1_000_000)) > 20
    )
    assert "Unique public question?" in texts and "71" in texts
    assert any("3 AI models" in text for text in texts)
    stored = h.share_db.stores[snapshots.SHARES_COLLECTION][created["share_id"]]
    for patch in (
        {"visibility": "private"},
        {"visibility": "public", "status": "revoked"},
    ):
        stored.update(patch)
        snapshots.invalidate_share_cache(created["share_id"])
        assert h.client.get(url).status_code == 404
