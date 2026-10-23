"""Mails in the reader's language (mailer._t, account_language, docs/i18n.md)."""
import asyncio
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core import i18n
from app.core.i18n_middleware import request_language
from app.services import account_language, mailer, notification_delivery, notification_outbox, persistence_guard
from app.services import watch_followers
from scripts import i18n as i18n_tool
from test_watch_feature import FakeDb, share


DELTA = {
    "summary": "Die Version 2 ist erschienen. Mehrere Händler listen sie.",
    "cause": "new_evidence",
    "sources": [{"title": "Händlerseite", "url": "https://example.test/v2"}],
    "held": "Der Preis bleibt gleich.",
    "goal": "Version 2 ist lieferbar",
    "goal_status": "not_met",
}
URLS = {"share_url": "https://www.consens.io/s/abc", "unsubscribe_url": "https://www.consens.io/watch/unsubscribe?token=t"}


def every_mail(language):
    """One message of each kind a reader can get, with German content."""
    question = "Ist die Version 2 schon lieferbar?"
    item = {"question": "Ist die Version 2 schon lieferbar?", "status": "active", "interval": "weekly",
            "run_weekday": "monday", "run_time": "08:00", "timezone": "America/Los_Angeles",
            "share_path": "/s/abc", "goal": "Version 2 ist lieferbar",
            "new_points": [{"notable": True, "change_summary": "Ein Händler listet sie."}]}
    return {
        "change": mailer.build_change_message(recipient="r@example.test", question=question, delta=DELTA,
                                              language=language, **URLS),
        "run": mailer.build_run_message(recipient="r@example.test", question=question, delta=DELTA, moved=False,
                                        consensus="Noch nicht lieferbar.", language=language, **URLS),
        "condition": mailer.build_condition_message(recipient="r@example.test", question=question,
                                                    goal="Version 2 ist lieferbar", reason="",
                                                    sources=DELTA["sources"], consensus="Lieferbar ab heute.",
                                                    language=language, **URLS),
        "paused": mailer.build_paused_message(recipient="r@example.test", question=question,
                                              resume_url="https://www.consens.io/watch/resume?token=r",
                                              language=language, **URLS),
        "follow": mailer.build_follow_confirm_message(recipient="r@example.test", question=question,
                                                      confirm_url="https://www.consens.io/c", share_url=URLS["share_url"],
                                                      language=language),
        "topic follow": mailer.build_topic_follow_confirm_message(
            recipient="r@example.test", title="Version 2", confirm_url="https://www.consens.io/c",
            topic_url="https://www.consens.io/topics/v2", language=language),
        "topic change": mailer.build_topic_change_message(
            recipient="r@example.test", title="Version 2", question=question, delta=DELTA,
            topic_url="https://www.consens.io/topics/v2", unsubscribe_url=URLS["unsubscribe_url"], language=language),
        "follower change": mailer.build_follower_change_message(recipient="r@example.test", question=question,
                                                                delta=DELTA, language=language, **URLS),
        "brief": mailer.build_brief_message(
            recipient="r@example.test", date_label="Freitag, 23. Oktober 2026", items=[item, {**item, "new_points": []}],
            changes_count=1, site_url="https://www.consens.io", unsubscribe_url=URLS["unsubscribe_url"],
            brief_timezone="Europe/Berlin", language=language),
        "setup": mailer.build_account_setup_message(recipient="r@example.test", setup_url="https://auth.example.test/x",
                                                    language=language),
        "existing": mailer.build_existing_account_message(recipient="r@example.test", login_url="https://www.consens.io/app",
                                                          reset_url="https://auth.example.test/x", language=language),
    }


def parts(message):
    html_part = message.get_body(preferencelist=("html",)).get_content()
    plain = message.get_body(preferencelist=("plain",)).get_content()
    return str(message["Subject"]), html_part, plain


def english_sentences():
    """The mailer's own sentences whose German differs: none may reach a German reader."""
    current = i18n.catalog("de")
    keys = {item.key for item in i18n_tool.server_keys("app/services/mailer.py")}
    found = []
    for key in keys:
        literal = i18n.fill(key, None)
        if "{" in literal or len(literal) < 12:
            continue
        if i18n.t(key, "de") != key:
            found.append(literal)
    assert len(found) > 80, "the mailer marks its sentences with _t/_h/_N"
    assert current is not None
    return found


@pytest.mark.parametrize("kind", list(every_mail("en")))
def test_a_german_reader_gets_no_english_sentence(kind):
    message = every_mail("de")[kind]
    subject, html_part, plain = parts(message)
    assert '<html lang="de">' in html_part
    for sentence in english_sentences():
        for name, text in (("subject", subject), ("html", html_part), ("plain", plain)):
            assert sentence not in text.replace("\n", " "), f"{kind} {name}: {sentence}"


def test_german_mails_read_german_and_keep_the_content():
    mails = every_mail("de")
    subject, html_part, plain = parts(mails["change"])
    assert subject == "Geändert: Ist die Version 2 schon lieferbar?"
    assert "Die Antwort hat sich geändert" in html_part and "Was gleich blieb" in html_part
    assert "Neuer Beleg: eine Quelle" in html_part
    assert "Noch nicht." in plain and "WARUM" in plain and "WAS SICH GEÄNDERT HAT" in plain
    # The reader's own words are never looked up: a question that is a
    # dictionary key stays as written.
    message = mailer.build_change_message(recipient="r@example.test", question="Resolved", delta=DELTA,
                                          language="de", **URLS)
    assert ">Resolved</p>" in parts(message)[1]
    # Umlauts leave ASCII: quoted-printable keeps the links of the text part readable.
    body = mails["setup"].get_body(preferencelist=("plain",))
    assert body["Content-Transfer-Encoding"] == "quoted-printable"
    assert "https://auth.example.test/x" in body.get_content()
    assert parts(mails["condition"])[2].count("Die neue Antwort erfüllt das Ziel.") == 1


def test_english_stays_the_default_for_an_unknown_or_missing_language():
    for language in ("", "fr", None):
        message = mailer.build_paused_message(recipient="r@example.test", question="Q?", language=language, **URLS)
        subject, html_part, _plain = parts(message)
        assert subject == "Watch paused: Q?" and '<html lang="en">' in html_part
    # The language never leaks out of a build.
    assert mailer._LANGUAGE.get() == "en"


def test_the_brief_writes_counts_dates_and_schedules_in_the_readers_words():
    moment = datetime(2026, 10, 3, 7, 0, tzinfo=timezone.utc)
    assert mailer.brief_date_label(moment) == "Saturday, 3 October 2026"
    assert mailer.brief_date_label(moment, language="de") == "Samstag, 3. Oktober 2026"
    weekly = {"status": "active", "interval": "weekly", "run_weekday": "monday", "run_time": "08:00",
              "timezone": "America/Los_Angeles"}
    daily = {"status": "active", "interval": "daily", "run_time": "07:30", "timezone": "Europe/Berlin"}
    assert mailer._brief_schedule(weekly, "Europe/Berlin") == "Weekly on Monday at 08:00 Los Angeles time"
    assert mailer._brief_schedule(daily, "Europe/Berlin") == "Daily at 07:30"
    token = mailer._LANGUAGE.set("de")
    try:
        assert mailer._brief_schedule(weekly, "Europe/Berlin") == "Jeden Montag um 08:00 (Ortszeit Los Angeles)"
        # "Daily" alone is the preset (Alltag); as a schedule it is Täglich.
        assert mailer._brief_schedule(daily, "Europe/Berlin") == "Täglich um 07:30"
        assert mailer._brief_schedule({"status": "active", "interval": "daily"}, "") == "Täglich"
        assert mailer._brief_status_label("resolved") == "Erreicht"
    finally:
        mailer._LANGUAGE.reset(token)
    assert i18n.t("Daily", "de") == "Alltag"
    subject, html_part, plain = parts(every_mail("de")["brief"])
    assert subject == "Morning Brief: 1 Änderung bei 2 Watches"
    assert "1 wichtige Änderung seit deinem letzten Morning Brief." in html_part
    assert "GEÄNDERT: Ein Händler listet sie." in plain and "Keine wesentliche Änderung." in plain
    english = parts(every_mail("en")["brief"])
    assert english[0] == "Morning brief: 1 change across 2 watches"
    assert "CHANGED: Ein Händler listet sie." in english[2]


def test_open_mail_patterns_cannot_catch_page_text():
    """German pages are translated with every dictionary file, mail.json too: a
    pattern of little more than placeholders would rewrite any matching page
    text ("Average response time" as a "{schedule} {city} time"). Those live
    under a context ("mail|…") that no page text starts with."""
    import json
    import re
    entries = json.loads((i18n.DICTIONARY_ROOT / "de" / "mail.json").read_text(encoding="utf-8"))
    for key in entries:
        if "{" in key and "|" not in key.split("{", 1)[0]:
            assert len(re.sub(r"\{[^{}]*\}", "", key).strip()) >= 5, key
    current = i18n.catalog("de")
    for text in ("Average response time", "In New York time", "Hello, my dear friend", "Updated at 10:00"):
        assert current.lookup(i18n.normalize(text)) in (None, text), text


# --- The account's language -------------------------------------------------

class Snap:
    def __init__(self, data):
        self.data = data

    @property
    def exists(self):
        return self.data is not None

    def to_dict(self):
        return dict(self.data) if self.data is not None else None


class Ref:
    def __init__(self, store, key):
        self.store, self.key = store, key

    def get(self, transaction=None):
        return Snap(self.store.get(self.key))


class Db:
    """users/{uid} and the deletion tombstones, with a merging transaction."""

    def __init__(self):
        self.stores = {"users": {}, persistence_guard.ACCOUNT_DELETION_JOBS_COLLECTION: {}}
        self.writes = 0

    def collection(self, name):
        store = self.stores[name]
        return SimpleNamespace(document=lambda key: Ref(store, key))

    def run_transaction(self, operation):
        db = self

        class Transaction:
            def set(self, ref, data, merge=False):
                db.writes += 1
                ref.store[ref.key] = {**(ref.store.get(ref.key) or {}), **data} if merge else dict(data)

        return operation(Transaction())


@pytest.fixture(autouse=True)
def forget_known_languages():
    account_language._known.clear()
    yield
    account_language._known.clear()


def test_the_account_keeps_the_language_it_reads_the_site_in():
    db = Db()
    db.stores["users"]["u1"] = {"tier": "pro"}
    assert account_language.of("u1", db=db) == "en"
    assert account_language.record("u1", "de", db=db) is True
    assert db.stores["users"]["u1"] == {"tier": "pro", "language": "de"}
    assert account_language.of("u1", db=db) == "de"
    # The next app load in the same language costs no read and no write.
    assert account_language.record("u1", "de", db=db) is False and db.writes == 1
    account_language._known.clear()
    assert account_language.record("u1", "de", db=db) is False and db.writes == 1
    assert account_language.record("u1", "en", db=db) is True
    assert account_language.record("u1", "xx", db=db) is False
    assert account_language.of("", db=db) == "en"


def test_a_deleted_account_gets_no_language_field():
    db = Db()
    db.stores[persistence_guard.ACCOUNT_DELETION_JOBS_COLLECTION]["gone"] = {"status": "pending"}
    assert account_language.record("gone", "de", db=db) is False
    assert "gone" not in db.stores["users"]


def test_a_broken_lookup_mails_in_english():
    class Broken:
        def collection(self, name):
            raise RuntimeError("firestore down")
    assert account_language.of("u1", db=Broken()) == "en"
    assert account_language.record("u1", "de", db=Broken()) is False


def test_user_status_records_the_language_after_answering():
    from app.api.routers import users as users_router
    app = FastAPI()
    app.include_router(users_router.router)
    with (
        patch.object(users_router, "verify_user_token", return_value="u1"),
        patch.object(users_router, "get_user_tier", return_value="free"),
        patch.object(users_router, "_token_budget", return_value={"day": "2026-10-23"}),
        patch.object(users_router, "is_user_admin", return_value=False),
        patch.object(users_router.account_language, "record") as record,
    ):
        response = TestClient(app).get("/user_status", headers={
            "Authorization": "Bearer token", "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"})
    assert response.status_code == 200
    record.assert_called_once_with("u1", "de", db=users_router.db_firestore)


def test_api_requests_carry_the_language_the_middleware_skips():
    app = FastAPI()

    @app.get("/api/probe")
    def probe(request: Request):
        return {"language": request_language(request)}

    client = TestClient(app)
    assert client.get("/api/probe").json() == {"language": "en"}
    assert client.get("/api/probe", headers={"Accept-Language": "de"}).json() == {"language": "de"}
    client.cookies.set(i18n.LANGUAGE_COOKIE, "en")
    assert client.get("/api/probe", headers={"Accept-Language": "de"}).json() == {"language": "en"}


# --- Delivery -----------------------------------------------------------------

def test_owner_mails_go_out_in_the_accounts_language():
    db = FakeDb()
    db.stores["users"]["u1"] = {"language": "de"}
    db.stores["watches"]["w1"] = {"owner_uid": "u1", "status": "active"}
    item = {"kind": notification_outbox.KIND_WATCH_ALERT, "uid": "u1", "resource_id": "w1",
            "payload": {"question": "Ist sie lieferbar?", "share_id": "A" * 16, "delta": DELTA}}
    sent = AsyncMock(return_value=True)
    user = SimpleNamespace(email="owner@example.test", email_verified=True)
    with (
        patch.object(notification_delivery.mailer, "is_configured", return_value=True),
        patch.object(notification_delivery.mailer, "send_message", sent),
        patch.object(notification_delivery.auth, "get_user", return_value=user),
        patch.dict(os.environ, {"WATCH_UNSUBSCRIBE_SECRET": "test-secret"}),
    ):
        outcome = asyncio.run(notification_delivery._deliver_watch_email(item, db))
        db.stores["users"]["u1"] = {}
        asyncio.run(notification_delivery._deliver_watch_email(item, db))
    assert outcome == (notification_outbox.SENT, "")
    assert sent.await_args_list[0].args[0]["Subject"] == "Geändert: Ist sie lieferbar?"
    assert sent.await_args_list[1].args[0]["Subject"] == "Moved: Ist sie lieferbar?"


def test_a_follower_reads_in_the_language_of_the_confirming_click():
    db = FakeDb()
    share_id = "F" * 16
    db.stores["shares"][share_id] = share(slug="follow-me")
    db.stores["watches"]["w1"] = {"share_id": share_id, "status": "active",
                                  "created_at": datetime(2026, 7, 18, tzinfo=timezone.utc), "interval": "weekly"}
    with patch.dict(os.environ, {"WATCH_UNSUBSCRIBE_SECRET": "test-secret"}):
        pending = watch_followers.request_follow(share_id, "visitor@example.com", db=db)
        watch_followers.confirm_follow(pending["token"], db=db, language="de")
        (follower_id, follower), = db.stores[watch_followers.FOLLOWERS_COLLECTION].items()
        assert follower["language"] == "de"

        item = {"kind": notification_outbox.KIND_WATCH_FOLLOWER, "resource_id": "w1", "recipient_id": follower_id,
                "payload": {"question": "Wird sich das ändern?", "share_id": share_id, "share_slug": "follow-me",
                            "delta": DELTA}}
        sent = AsyncMock(return_value=True)
        with (
            patch.object(notification_delivery.mailer, "is_configured", return_value=True),
            patch.object(notification_delivery.mailer, "send_message", sent),
        ):
            asyncio.run(notification_delivery._deliver_watch_follower(item, db))
    assert sent.await_args.args[0]["Subject"] == "Der KI-Konsens hat sich geändert: Wird sich das ändern?"
