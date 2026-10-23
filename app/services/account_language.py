"""The language an account reads the site in, for mails sent without a request.

Every app load asks /user_status; the language that request was served in
(i18n_middleware: the ``consens_lang`` cookie, else the browser's
Accept-Language) is recorded on ``users/{uid}`` as ``language``. Watch
alerts and the Morning Brief go out from the outbox long after any request
and read it back (notification_delivery). Followers have no account: their
language comes with the click that confirms the follow (watch_followers,
topics). Without a record a mail stays English, as before.
"""

from __future__ import annotations

import logging
import threading

from cachetools import TTLCache

from app.core import i18n
from app.core.observability import safe_exception
from app.services import persistence_guard

FIELD = "language"
# The language this process last found or wrote per account: an unchanged
# language costs the next app load no Firestore read.
_known = TTLCache(maxsize=4096, ttl=6 * 3600)
_known_lock = threading.Lock()


def _ref(db, uid: str):
    return db.collection("users").document(uid)


def record(uid: str, language: str, *, db) -> bool:
    """Store ``language`` for the account when it differs; True when written.

    Never raises: a mail in the earlier language is no reason to fail the
    request that noticed the change."""
    uid = str(uid or "").strip()
    if not uid or language not in i18n.LANGUAGES:
        return False
    with _known_lock:
        if _known.get(uid) == language:
            return False

    def operation(transaction):
        # A deleted account must not regain a user document through this field.
        persistence_guard.ensure_account_write_allowed(uid=uid, db=db, transaction=transaction)
        ref = _ref(db, uid)
        snapshot = ref.get(transaction=transaction)
        current = (snapshot.to_dict() or {}) if snapshot.exists else {}
        if current.get(FIELD) == language:
            return False
        transaction.set(ref, {FIELD: language}, merge=True)
        return True

    try:
        written = bool(persistence_guard._run_transaction(db, operation))
    except persistence_guard.AccountDeletionInProgress:
        return False
    except Exception as exc:
        logging.warning("Account language not recorded category=%s", safe_exception(exc))
        return False
    with _known_lock:
        _known[uid] = language
    return written


def of(uid: str, *, db) -> str:
    """The account's recorded language; English without one or on any error."""
    uid = str(uid or "").strip()
    if not uid:
        return i18n.DEFAULT_LANGUAGE
    try:
        snapshot = _ref(db, uid).get()
        stored = ((snapshot.to_dict() or {}) if snapshot.exists else {}).get(FIELD)
    except Exception as exc:
        logging.warning("Account language lookup failed category=%s", safe_exception(exc))
        return i18n.DEFAULT_LANGUAGE
    return stored if stored in i18n.LANGUAGES else i18n.DEFAULT_LANGUAGE
