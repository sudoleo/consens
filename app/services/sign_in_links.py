"""One-click sign-in from an e-mail.

The mail carries a link with a single-use code. The page first asks whose
link it is (POST /auth/email-link/account, spends nothing), then trades the
code once for a Firebase custom token (POST /auth/email-link) and signs in
with it.

Firestore keeps the code's SHA-256 as the document id and nothing that turns
back into a link. The code sits in the URL fragment, which no request
carries: it stays out of access logs, and a mail scanner that fetches the
link spends nothing. Only the page's own POST does.
"""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from firebase_admin import auth, firestore

from app.core.observability import safe_exception
from app.core.site import SITE_URL


COLLECTION = "sign_in_links"
CODE_BYTES = 32
LINK_LIFETIME = timedelta(hours=1)
# secrets.token_urlsafe(32): 43 characters of the URL-safe alphabet.
_CODE = re.compile(r"[A-Za-z0-9_-]{43}")


class LinkInvalid(Exception):
    """Unknown, expired, already used, or no longer its account's address.

    One exception and one answer for all of them: the page says the same
    sentence either way."""


@dataclass(frozen=True)
class SignIn:
    token: str
    # The account's first sign-in (it was created by the sign-up this link
    # answers, or never used since).
    first: bool


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _address(email) -> str:
    return str(email or "").strip().lower()


def _db(db):
    if db is not None:
        return db
    from app.core.security import db_firestore
    return db_firestore


def _where(collection, field: str, operator: str, value):
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter

        return collection.where(filter=FieldFilter(field, operator, value))
    except (ImportError, TypeError):
        return collection.where(field, operator, value)


def _run(db, operation):
    @firestore.transactional
    def run(tx):
        return operation(tx)

    return run(db.transaction())


def _expired(record: dict, now: datetime) -> bool:
    expires_at = record.get("expires_at")
    if not isinstance(expires_at, datetime) or expires_at.tzinfo is None:
        return True
    return expires_at.astimezone(timezone.utc) <= now.astimezone(timezone.utc)


def link_url(code: str) -> str:
    return f"{SITE_URL}/app#signin={code}"


def issue(uid: str, email: str, *, db=None, now: datetime | None = None) -> str:
    """A new code for ``uid``; the caller mails :func:`link_url` of it.
    AccountDeletionInProgress once the account's deletion began: it takes
    the account's links in one step, a link made after it would stay."""
    from app.services import persistence_guard
    now = now or utcnow()
    code = secrets.token_urlsafe(CODE_BYTES)
    database = _db(db)
    ref = database.collection(COLLECTION).document(_digest(code))

    def operation(tx):
        persistence_guard.ensure_account_write_allowed(uid=uid, db=database, transaction=tx, now=now)
        tx.set(ref, {
            "uid": uid,
            # Checked again when the link is used: the click proves this
            # address, not whatever the account is called by then.
            "email_hash": _digest(_address(email)),
            "created_at": now,
            "expires_at": now + LINK_LIFETIME,
        })
    _run(database, operation)
    return code


def discard(code: str, *, db=None) -> None:
    """Withdraw a code whose mail did not go out."""
    if isinstance(code, str) and _CODE.fullmatch(code):
        _db(db).collection(COLLECTION).document(_digest(code)).delete()


def forget_account(uid: str, *, db=None) -> None:
    """Every open link of an account (account deletion)."""
    for snapshot in _where(_db(db).collection(COLLECTION), "uid", "==", uid).stream():
        snapshot.reference.delete()


def cleanup_expired(db=None, max_docs: int = 500) -> int:
    """Links nobody used (retention_maintenance.py, hourly)."""
    deleted = 0
    query = _where(_db(db).collection(COLLECTION), "expires_at", "<", utcnow()).limit(max_docs)
    for snapshot in query.stream():
        snapshot.reference.delete()
        deleted += 1
    return deleted


_REFUSED = object()


def _account(record: dict):
    """The Firebase user a link may still sign in, or None.

    Raises on a Firebase outage."""
    uid = str(record.get("uid") or "")
    if not uid:
        return None
    try:
        user = auth.get_user(uid)
    except auth.UserNotFoundError:
        return None
    if getattr(user, "disabled", False):
        return None
    if _digest(_address(getattr(user, "email", ""))) != record.get("email_hash"):
        return None
    return user


def account_address(code: str, *, db=None, now: datetime | None = None) -> str:
    """The address a link would log in, without spending it or touching the
    account. The page asks this first, so that a link opened anywhere but in
    the browser that asked for it logs in only after a click there."""
    if not isinstance(code, str) or not _CODE.fullmatch(code):
        raise LinkInvalid()
    snapshot = _db(db).collection(COLLECTION).document(_digest(code)).get()
    record = (snapshot.to_dict() or {}) if snapshot.exists else {}
    if not record or _expired(record, now or utcnow()):
        raise LinkInvalid()
    user = _account(record)
    if user is None:
        raise LinkInvalid()
    return _address(user.email)


def _sign_in(record: dict):
    """The custom token for the link's account, or _REFUSED.

    Raises on a Firebase outage, which puts the link back (redeem)."""
    user = _account(record)
    if user is None:
        return _REFUSED
    uid = user.uid
    metadata = getattr(user, "user_metadata", None)
    first = not getattr(metadata, "last_sign_in_timestamp", None)
    if not getattr(user, "email_verified", False):
        # The click proves the mailbox. Ways in that were attached before
        # that proof do not carry over: a password is replaced, every other
        # sign-in provider is removed, and sessions opened with them end here.
        changes = {"email_verified": True}
        providers = {getattr(item, "provider_id", "") for item in (getattr(user, "provider_data", None) or [])}
        providers.discard("")
        if "password" in providers:
            changes["password"] = secrets.token_urlsafe(48)
        others = sorted(providers - {"password"})
        if others:
            changes["providers_to_delete"] = others
        auth.update_user(uid, **changes)
        auth.revoke_refresh_tokens(uid)
    token = auth.create_custom_token(uid)
    return SignIn(token.decode("ascii") if isinstance(token, bytes) else str(token), first)


def redeem(code: str, *, db=None, now: datetime | None = None) -> SignIn:
    """Spend ``code`` once and sign its account in.

    Read and delete happen in one transaction: of two requests with the same
    code, one gets the link and the other LinkInvalid. Only the one that got
    it touches the account, after the commit: the transaction runs again
    for the request that lost, and a click that confirms the address there
    as well ended the session the other had just opened
    (revoke_refresh_tokens). A Firebase outage puts the link back, so it
    stays usable.
    """
    if not isinstance(code, str) or not _CODE.fullmatch(code):
        raise LinkInvalid()
    db = _db(db)
    now = now or utcnow()
    ref = db.collection(COLLECTION).document(_digest(code))

    def spend(tx):
        # The reference's own get binds the read to the transaction and
        # returns the one snapshot (Transaction.get yields a generator).
        snapshot = ref.get(transaction=tx)
        if not snapshot.exists:
            return None
        record = snapshot.to_dict() or {}
        tx.delete(ref)
        return _REFUSED if _expired(record, now) else record

    record = _run(db, spend)
    if not isinstance(record, dict):
        raise LinkInvalid()
    try:
        result = _sign_in(record)
    except Exception:
        _put_back(ref, record)
        raise
    if not isinstance(result, SignIn):
        raise LinkInvalid()
    return result


def _put_back(ref, record: dict) -> None:
    """A spent link whose sign-in did not happen, usable again; best effort,
    the failure that brought it here is what the request answers."""
    try:
        ref.set(record)
    except Exception as exc:
        logging.warning("Sign-in link not put back category=%s", safe_exception(exc))
