"""A rate limit speaks plainly and is no upgrade offer (Apple audit H6).

Every slowapi limit answers with an everyday sentence, `code: "rate_limited"`
and `retry_after` (also as Retry-After); a browser form gets the same as a
page.
"""
from unittest.mock import patch

from adapter_test_support import http_adapter, login  # noqa: F401 (fixture)
from test_watch_http_contract import watch_http  # noqa: F401 (fixture)

from app.core import rate_limit
from app.services import watch_service


def test_rate_limit_answers_with_a_sentence_code_and_retry_after(watch_http):
    h = watch_http
    token = watch_service.make_unsubscribe_token(h.watch["id"])
    statuses = [
        h.client.get("/watch/unsubscribe", params={"token": token}, headers={"accept": "application/json"})
        for _ in range(21)
    ]
    limited = statuses[-1]
    assert [r.status_code for r in statuses[:20]] == [200] * 20 and limited.status_code == 429
    body = limited.json()
    assert body["code"] == "rate_limited" and body["error"].startswith("Too many requests")
    assert "per 1 minute" not in limited.text and "detail" not in body
    assert 1 <= body["retry_after"] <= 60 and limited.headers["retry-after"] == str(body["retry_after"])
    page = h.client.get("/watch/unsubscribe", params={"token": token}, headers={"accept": "text/html"})
    assert page.status_code == 429 and "One moment, please" in page.text
    assert page.headers["retry-after"]

def test_rate_limit_sentence_scales_with_the_wait():
    assert rate_limit.rate_limit_message(30).endswith("Please wait a moment and try again.")
    assert rate_limit.rate_limit_message(600).endswith("Please try again in 10 minutes.")
    assert rate_limit.rate_limit_message(86_400).endswith("Please try again later.")


def test_a_plan_limit_is_named_apart_from_a_throttle(watch_http):
    """The app offers more watches only for ``limit_reached``; a throttle is
    always ``rate_limited`` (main.py)."""
    from test_watch_feature import share

    h = watch_http
    h.watch_db.stores["shares"]["P" * 16] = {
        **share(owner="owner", slug="other"), "question": "Is another thing true?", "question_hash": "other",
    }
    with patch("app.api.routers.watch.get_user_tier", return_value="free"), \
            patch.object(watch_service.cfg, "get_watch_active_limit", return_value=1):
        response = h.client.post("/api/watch", headers=login("owner"), json={
            "share_id": "P" * 16, "interval": "weekly", "visibility": "public",
        })
    assert response.status_code == 429
    assert response.json() == {"error": "Active watch limit reached.", "code": "limit_reached"}
    assert "retry-after" not in response.headers
