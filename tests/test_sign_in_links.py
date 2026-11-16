"""The one-click sign-in link: its code's life, its limits and what it never tells."""
import hashlib
import logging
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import auth as auth_router
from app.core.rate_limit import api_uid_limiter, limiter
from app.services import mailer, registration, sign_in_links


NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
EMAIL = "Reader@Example.test"


# --- A Firestore double with real transaction semantics ------------------------
# Reads remember the version they saw; a commit whose reads changed meanwhile
# is retried, as Firestore does.

class Snapshot:
    def __init__(self, key, data, db):
        self.id = key[1]
        self._data = data
        self.exists = data is not None
        self.reference = Document(db, key)

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class Document:
    def __init__(self, db, key):
        self.db, self.key = db, key

    def get(self, transaction=None):
        with self.db.lock:
            if transaction is not None:
                transaction.reads[self.key] = self.db.versions.get(self.key, 0)
            return Snapshot(self.key, self.db.docs.get(self.key), self.db)

    def set(self, data):
        with self.db.lock:
            self.db.docs[self.key] = dict(data)
            self.db.bump(self.key)

    def delete(self):
        with self.db.lock:
            self.db.docs.pop(self.key, None)
            self.db.bump(self.key)


class Query:
    def __init__(self, db, name, filters=(), limit=None):
        self.db, self.name, self.filters, self._limit = db, name, list(filters), limit

    def where(self, field=None, op=None, value=None, *, filter=None):
        if filter is not None:
            field, op, value = filter.field_path, filter.op_string, filter.value
        return Query(self.db, self.name, [*self.filters, (field, op, value)], self._limit)

    def limit(self, count):
        return Query(self.db, self.name, self.filters, count)

    def stream(self):
        tests = {"==": lambda a, b: a == b, "<": lambda a, b: a is not None and a < b}
        with self.db.lock:
            found = [
                Snapshot(key, data, self.db) for key, data in self.db.docs.items()
                if key[0] == self.name and all(tests[op](data.get(field), value) for field, op, value in self.filters)
            ]
        return iter(found[: self._limit] if self._limit else found)


class Collection(Query):
    def document(self, doc_id):
        return Document(self.db, (self.name, doc_id))


class Transaction:
    def __init__(self):
        self.reads, self.deletes = {}, []

    def delete(self, ref):
        self.deletes.append(ref.key)


class FakeDb:
    def __init__(self):
        self.docs, self.versions = {}, {}
        self.lock = threading.RLock()
        self.attempts = 0

    def bump(self, key):
        self.versions[key] = self.versions.get(key, 0) + 1

    def collection(self, name):
        return Collection(self, name)

    def run_transaction(self, operation, max_attempts=5):
        for _ in range(max_attempts):
            self.attempts += 1
            tx = Transaction()
            result = operation(tx)
            with self.lock:
                if all(self.versions.get(key, 0) == seen for key, seen in tx.reads.items()):
                    for key in tx.deletes:
                        self.docs.pop(key, None)
                        self.bump(key)
                    return result
        raise RuntimeError("transaction contention")

    def links(self):
        return {key[1]: data for key, data in self.docs.items() if key[0] == sign_in_links.COLLECTION}


def account(uid="reader", email=EMAIL.lower(), *, verified=True, disabled=False, signed_in=True, providers=("password",)):
    return SimpleNamespace(
        uid=uid, email=email, email_verified=verified, disabled=disabled,
        user_metadata=SimpleNamespace(last_sign_in_timestamp=1700000000000 if signed_in else None),
        provider_data=[SimpleNamespace(provider_id=item) for item in providers],
    )


@pytest.fixture
def firebase():
    """Firebase Auth as the link sees it; nothing leaves the process."""
    state = SimpleNamespace(users={"reader": account()}, minted=[], updates=[], revoked=[])

    def get_user(uid):
        if uid not in state.users:
            raise sign_in_links.auth.UserNotFoundError("missing")
        return state.users[uid]

    def create_custom_token(uid):
        state.minted.append(uid)
        return f"custom-token-{uid}".encode("ascii")

    with (
        patch.object(sign_in_links.auth, "get_user", side_effect=get_user),
        patch.object(sign_in_links.auth, "create_custom_token", side_effect=create_custom_token),
        patch.object(sign_in_links.auth, "update_user", side_effect=lambda uid, **kw: state.updates.append((uid, kw))),
        patch.object(sign_in_links.auth, "revoke_refresh_tokens", side_effect=state.revoked.append),
    ):
        yield state


# --- The code's life ---------------------------------------------------------

def test_only_the_hash_of_the_code_is_stored_and_the_link_carries_it_in_the_fragment():
    db = FakeDb()
    code = sign_in_links.issue("reader", EMAIL, db=db, now=NOW)

    assert len(code) == 43 and len(code.encode()) * 6 // 8 >= 32
    stored = db.links()
    assert list(stored) == [hashlib.sha256(code.encode()).hexdigest()]
    record = stored[hashlib.sha256(code.encode()).hexdigest()]
    assert code not in repr(record)
    assert EMAIL.lower() not in repr(record) and EMAIL not in repr(record)
    assert record["uid"] == "reader"
    assert record["expires_at"] == NOW + timedelta(hours=1)
    url = sign_in_links.link_url(code)
    assert url == f"{sign_in_links.SITE_URL}/app#signin={code}"
    assert "?" not in url


def test_a_code_signs_in_once_and_is_gone_after(firebase):
    db = FakeDb()
    code = sign_in_links.issue("reader", EMAIL, db=db, now=NOW)

    sign_in = sign_in_links.redeem(code, db=db, now=NOW + timedelta(minutes=5))
    assert sign_in == sign_in_links.SignIn(token="custom-token-reader", first=False)
    assert db.links() == {}

    with pytest.raises(sign_in_links.LinkInvalid):
        sign_in_links.redeem(code, db=db, now=NOW + timedelta(minutes=6))
    assert firebase.minted == ["reader"]


def test_an_expired_code_is_refused_and_removed(firebase):
    db = FakeDb()
    code = sign_in_links.issue("reader", EMAIL, db=db, now=NOW)

    with pytest.raises(sign_in_links.LinkInvalid):
        sign_in_links.redeem(code, db=db, now=NOW + timedelta(hours=1))
    assert db.links() == {}
    assert firebase.minted == []


@pytest.mark.parametrize("code", ["", "short", "x" * 44, "a" * 42 + "!", "a" * 43 + "\n", None, 7])
def test_a_malformed_code_is_refused_without_a_read(code):
    db = FakeDb()
    with pytest.raises(sign_in_links.LinkInvalid):
        sign_in_links.redeem(code, db=db, now=NOW)
    assert db.attempts == 0


def test_a_wrong_code_is_refused_and_leaves_other_links_alone(firebase):
    db = FakeDb()
    code = sign_in_links.issue("reader", EMAIL, db=db, now=NOW)
    wrong = ("A" if code[0] != "A" else "B") + code[1:]

    with pytest.raises(sign_in_links.LinkInvalid):
        sign_in_links.redeem(wrong, db=db, now=NOW)
    assert len(db.links()) == 1
    assert sign_in_links.redeem(code, db=db, now=NOW).token == "custom-token-reader"


def test_two_requests_with_one_code_sign_in_once(firebase):
    """Both read the link before either commits; the second commit is retried
    and finds the link spent."""
    db = FakeDb()
    code = sign_in_links.issue("reader", EMAIL, db=db, now=NOW)
    both_read = threading.Barrier(2, timeout=5)
    real_get_user = sign_in_links.auth.get_user.side_effect

    def get_user_after_both_read(uid):
        both_read.wait()
        return real_get_user(uid)

    results = []

    def redeem():
        try:
            results.append(sign_in_links.redeem(code, db=db, now=NOW))
        except sign_in_links.LinkInvalid as exc:
            results.append(exc)

    with patch.object(sign_in_links.auth, "get_user", side_effect=get_user_after_both_read):
        threads = [threading.Thread(target=redeem) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)

    assert sorted(type(item).__name__ for item in results) == ["LinkInvalid", "SignIn"]
    assert db.links() == {}
    assert db.attempts == 3


def test_a_firebase_outage_keeps_the_link(firebase):
    db = FakeDb()
    code = sign_in_links.issue("reader", EMAIL, db=db, now=NOW)

    with patch.object(sign_in_links.auth, "get_user", side_effect=RuntimeError("upstream")):
        with pytest.raises(RuntimeError):
            sign_in_links.redeem(code, db=db, now=NOW)
    assert len(db.links()) == 1
    assert sign_in_links.redeem(code, db=db, now=NOW).token == "custom-token-reader"


@pytest.mark.parametrize("change", [
    {"email": "someone-else@example.test"},
    {"disabled": True},
    "deleted",
])
def test_a_link_for_an_account_that_changed_is_refused(firebase, change):
    db = FakeDb()
    code = sign_in_links.issue("reader", EMAIL, db=db, now=NOW)
    if change == "deleted":
        del firebase.users["reader"]
    else:
        firebase.users["reader"] = account(**change)

    with pytest.raises(sign_in_links.LinkInvalid):
        sign_in_links.redeem(code, db=db, now=NOW)
    assert db.links() == {}
    assert firebase.minted == []


def test_the_click_confirms_the_address_and_ends_an_earlier_password(firebase):
    db = FakeDb()
    firebase.users["reader"] = account(verified=False, signed_in=False)
    code = sign_in_links.issue("reader", EMAIL, db=db, now=NOW)

    sign_in = sign_in_links.redeem(code, db=db, now=NOW)

    assert sign_in.first is True
    [(uid, changes)] = firebase.updates
    assert uid == "reader" and changes["email_verified"] is True
    assert len(changes["password"]) >= 48
    assert firebase.revoked == ["reader"]


def test_a_confirmed_account_keeps_its_password_and_sessions(firebase):
    db = FakeDb()
    firebase.users["reader"] = account(verified=True, providers=("google.com", "password"))
    code = sign_in_links.issue("reader", EMAIL, db=db, now=NOW)

    sign_in_links.redeem(code, db=db, now=NOW)
    assert firebase.updates == [] and firebase.revoked == []


def test_an_unconfirmed_account_without_a_password_gets_none(firebase):
    db = FakeDb()
    firebase.users["reader"] = account(verified=False, providers=())
    code = sign_in_links.issue("reader", EMAIL, db=db, now=NOW)

    sign_in_links.redeem(code, db=db, now=NOW)
    assert firebase.updates == [("reader", {"email_verified": True})]


def test_expired_links_are_swept_and_an_account_takes_its_links_along():
    db = FakeDb()
    sign_in_links.issue("reader", EMAIL, db=db, now=NOW - timedelta(hours=2))
    fresh = sign_in_links.issue("reader", EMAIL, db=db, now=sign_in_links.utcnow())
    sign_in_links.issue("other", "other@example.test", db=db, now=sign_in_links.utcnow())

    assert sign_in_links.cleanup_expired(db=db) == 1
    assert len(db.links()) == 2

    sign_in_links.forget_account("reader", db=db)
    assert [record["uid"] for record in db.links().values()] == ["other"]
    assert hashlib.sha256(fresh.encode()).hexdigest() not in db.links()


def test_asking_whose_link_it_is_spends_nothing_and_changes_nothing(firebase):
    db = FakeDb()
    firebase.users["reader"] = account(verified=False, signed_in=False)
    code = sign_in_links.issue("reader", EMAIL, db=db, now=NOW)

    for _ in range(3):
        assert sign_in_links.account_address(code, db=db, now=NOW + timedelta(minutes=5)) == EMAIL.lower()

    assert len(db.links()) == 1
    assert firebase.updates == [] and firebase.revoked == [] and firebase.minted == []
    assert firebase.users["reader"].email_verified is False
    # Still the one link it was: it signs in once.
    assert sign_in_links.redeem(code, db=db, now=NOW).first is True
    with pytest.raises(sign_in_links.LinkInvalid):
        sign_in_links.account_address(code, db=db, now=NOW)


@pytest.mark.parametrize("case", ["unknown", "expired", "used", "malformed", "other address", "disabled", "deleted"])
def test_asking_about_a_refused_link_gets_the_one_refusal(firebase, case):
    db = FakeDb()
    code = sign_in_links.issue("reader", EMAIL, db=db, now=NOW)
    now = NOW + timedelta(minutes=5)
    if case == "unknown":
        code = ("A" if code[0] != "A" else "B") + code[1:]
    elif case == "expired":
        now = NOW + timedelta(hours=1)
    elif case == "used":
        sign_in_links.redeem(code, db=db, now=now)
    elif case == "malformed":
        code = code[:-1]
    elif case == "other address":
        firebase.users["reader"] = account(email="someone-else@example.test")
    elif case == "disabled":
        firebase.users["reader"] = account(disabled=True)
    else:
        del firebase.users["reader"]

    with pytest.raises(sign_in_links.LinkInvalid):
        sign_in_links.account_address(code, db=db, now=now)
    assert firebase.updates == [] and firebase.revoked == []


def test_a_withdrawn_code_no_longer_works(firebase):
    db = FakeDb()
    code = sign_in_links.issue("reader", EMAIL, db=db, now=NOW)
    sign_in_links.discard(code, db=db)
    with pytest.raises(sign_in_links.LinkInvalid):
        sign_in_links.redeem(code, db=db, now=NOW)


# --- The mail ------------------------------------------------------------------

@pytest.fixture
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(registration.mailer, "is_configured", lambda: True)
    monkeypatch.setattr(registration.mailer, "deliver_now", lambda message: sent.append(message) or True)
    return sent


def _body(message, kind):
    return message.get_body((kind,)).get_content()


@pytest.mark.parametrize("first,subject,button", [
    (True, "Welcome to consens.io", "Confirm and log in"),
    (False, "Your login link for consens.io", "Log in"),
])
def test_the_mail_holds_one_button_with_the_link(monkeypatch, outbox, first, subject, button):
    db = FakeDb()
    monkeypatch.setattr(sign_in_links, "_db", lambda _db: db)
    with patch.object(registration.requests, "post") as firebase_mail:
        assert registration.deliver_sign_in_email(EMAIL, uid="reader", first=first) is True

    firebase_mail.assert_not_called()
    [message] = outbox
    assert message["Subject"] == subject
    [stored] = db.links()
    html_part, plain = _body(message, "html"), _body(message, "plain")
    links = [part for part in html_part.split('href="')[1:]]
    assert len(links) == 1 and links[0].startswith(f"{sign_in_links.SITE_URL}/app#signin=")
    code = links[0].split("#signin=", 1)[1].split('"', 1)[0]
    assert hashlib.sha256(code.encode()).hexdigest() == stored
    assert f"{sign_in_links.SITE_URL}/app#signin={code}" in plain
    assert f">{button}</a>" in html_part
    # Written like the other account mails, without dashes between clauses.
    for text in (subject, html_part, plain):
        assert "–" not in text and "—" not in text and " - " not in text


def test_a_mail_that_cannot_go_out_withdraws_its_link_and_sends_the_setup_mail(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(sign_in_links, "_db", lambda _db: db)
    monkeypatch.setenv("FIREBASE_API_KEY", "test-key")
    monkeypatch.setattr(registration.mailer, "is_configured", lambda: True)
    monkeypatch.setattr(registration.mailer, "deliver_now", lambda message: False)
    with (
        patch.object(registration.auth, "generate_password_reset_link", return_value="https://reset.example.test/x"),
        patch.object(registration.requests, "post") as firebase_mail,
    ):
        assert registration.deliver_sign_in_email(EMAIL, uid="reader", first=True) is True

    assert db.links() == {}
    assert firebase_mail.call_args.kwargs["json"]["requestType"] == "PASSWORD_RESET"


def test_without_smtp_no_link_is_made_and_the_setup_mail_goes_out(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(sign_in_links, "_db", lambda _db: db)
    monkeypatch.setenv("FIREBASE_API_KEY", "test-key")
    monkeypatch.setattr(registration.mailer, "is_configured", lambda: False)
    with patch.object(registration.requests, "post") as firebase_mail:
        assert registration.deliver_sign_in_email(EMAIL, uid="reader", first=False) is True

    assert db.links() == {}
    firebase_mail.assert_called_once()


def test_a_storage_outage_falls_back_without_naming_the_address(monkeypatch, outbox, caplog):
    def broken(_db):
        raise RuntimeError(f"firestore said no to {EMAIL}")

    monkeypatch.setattr(sign_in_links, "_db", broken)
    with (
        patch.object(registration.auth, "generate_password_reset_link", return_value="https://reset.example.test/x"),
        caplog.at_level(logging.DEBUG),
    ):
        assert registration.deliver_sign_in_email(EMAIL, uid="reader", first=True) is True

    assert outbox[0]["Subject"] == "Finish setting up your consens.io account"
    assert EMAIL not in caplog.text and EMAIL.lower() not in caplog.text


def test_the_mail_speaks_german_to_a_german_reader():
    message = mailer.build_sign_in_message(recipient=EMAIL, sign_in_url="https://www.consens.io/app#signin=x",
                                           first=True, language="de")
    assert message["Subject"] == "Willkommen bei consens.io"
    assert "Bestätigen und anmelden" in _body(message, "html")
    plain = _body(message, "plain")
    assert "Der Link gilt einmal und eine Stunde lang." in plain
    assert "https://www.consens.io/app#signin=x" in plain


# --- The endpoint ----------------------------------------------------------------

@pytest.fixture
def client(monkeypatch, firebase):
    db = FakeDb()
    monkeypatch.setattr(sign_in_links, "_db", lambda _db: db)
    limiter.reset()
    api_uid_limiter.reset()
    app = FastAPI()
    app.include_router(auth_router.router)
    with TestClient(app) as test_client:
        test_client.db = db
        yield test_client
    limiter.reset()


def test_the_endpoint_trades_a_code_for_a_token(client):
    code = sign_in_links.issue("reader", EMAIL, db=client.db)
    response = client.post("/auth/email-link", json={"code": code})

    assert response.status_code == 200
    assert response.json() == {"token": "custom-token-reader", "first": False}
    assert response.headers["cache-control"] == "no-store"


def test_unknown_expired_and_used_links_get_the_same_answer(client):
    used = sign_in_links.issue("reader", EMAIL, db=client.db)
    assert client.post("/auth/email-link", json={"code": used}).status_code == 200
    expired = sign_in_links.issue("reader", EMAIL, db=client.db, now=sign_in_links.utcnow() - timedelta(hours=2))
    unknown = "A" * 43

    answers = [client.post("/auth/email-link", json={"code": code}) for code in (used, expired, unknown, "short")]
    assert {response.status_code for response in answers} == {400}
    assert len({response.content for response in answers}) == 1
    assert "token" not in answers[0].text


def test_an_outage_says_wait_and_names_nothing(client):
    code = sign_in_links.issue("reader", EMAIL, db=client.db)
    with patch.object(sign_in_links.auth, "get_user", side_effect=RuntimeError(f"upstream {EMAIL}")):
        response = client.post("/auth/email-link", json={"code": code})

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert EMAIL not in response.text and "upstream" not in response.text
    assert client.post("/auth/email-link", json={"code": code}).status_code == 200


def test_attempts_are_limited_per_ip(client):
    statuses = [client.post("/auth/email-link", json={"code": "A" * 43}).status_code for _ in range(11)]
    assert statuses[:10] == [400] * 10
    assert statuses[10] == 429


def test_the_request_takes_nothing_but_the_code(client):
    response = client.post("/auth/email-link", json={"code": "A" * 43, "uid": "reader"})
    assert response.status_code == 422


def test_no_code_token_or_address_reaches_the_log(client, caplog):
    codes = [sign_in_links.issue("reader", EMAIL, db=client.db) for _ in range(2)]
    with caplog.at_level(logging.DEBUG):
        client.post("/auth/email-link/account", json={"code": codes[0]})
        client.post("/auth/email-link", json={"code": codes[0]})
        client.post("/auth/email-link", json={"code": codes[0]})
        client.post("/auth/email-link/account", json={"code": codes[0]})
        with patch.object(sign_in_links.auth, "get_user", side_effect=RuntimeError(f"{codes[1]} {EMAIL}")):
            client.post("/auth/email-link/account", json={"code": codes[1]})
            client.post("/auth/email-link", json={"code": codes[1]})

    for secret in (*codes, "custom-token-reader", EMAIL, EMAIL.lower()):
        assert secret not in caplog.text


def test_the_account_question_names_the_address_and_leaves_the_link(client):
    code = sign_in_links.issue("reader", EMAIL, db=client.db)
    asked = client.post("/auth/email-link/account", json={"code": code})

    assert asked.status_code == 200
    assert asked.json() == {"email": EMAIL.lower()}
    assert asked.headers["cache-control"] == "no-store"
    assert len(client.db.links()) == 1
    assert client.post("/auth/email-link", json={"code": code}).status_code == 200


def test_the_account_question_refuses_like_the_sign_in(client):
    used = sign_in_links.issue("reader", EMAIL, db=client.db)
    client.post("/auth/email-link", json={"code": used})
    expired = sign_in_links.issue("reader", EMAIL, db=client.db, now=sign_in_links.utcnow() - timedelta(hours=2))
    codes = (used, expired, "A" * 43, "short")

    asked = [client.post("/auth/email-link/account", json={"code": code}) for code in codes]
    spent = client.post("/auth/email-link", json={"code": used})
    assert {response.status_code for response in asked} == {400}
    assert {response.content for response in asked} == {spent.content}
    assert "email" not in asked[0].json()


def test_the_account_question_is_limited_and_says_wait_in_an_outage(client):
    code = sign_in_links.issue("reader", EMAIL, db=client.db)
    with patch.object(sign_in_links.auth, "get_user", side_effect=RuntimeError("upstream")):
        outage = client.post("/auth/email-link/account", json={"code": code})
    assert outage.status_code == 503 and outage.headers["retry-after"] == "5"
    assert "upstream" not in outage.text

    statuses = [client.post("/auth/email-link/account", json={"code": "A" * 43}).status_code for _ in range(10)]
    assert statuses[:9] == [400] * 9
    assert statuses[9] == 429
