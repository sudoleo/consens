"""Admin-owned runtime settings (the reference timezone), with atomic
revisions and bounded caching.

System prompts are code-owned: ``get_config()`` always serves the prompts from
``prompt_defaults``. Prompt texts and delegation settings stored in an older
Firestore document are ignored on read and dropped by the next save; the admin
only displays the prompts (see ``prompt_catalog``)."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import logging
import threading
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.observability import safe_exception
from app.services import persistence_guard
from app.services.prompt_defaults import DEFAULT_PROMPTS

CACHE_SECONDS = 30
# /prepare returns the answer prompt to the browser for /ask_* (12k/32k caps).
# Code prompts must stay below this, leaving room for the server-owned clock.
MAX_PROMPT_CHARS = 10_000
MAX_PROMPT_BYTES = 28_000
DEFAULT_TIMEZONE = "Europe/Berlin"
# Keys an admin may send; "prompts" and "delegation" are tolerated from legacy
# clients and ignored.
_ACCEPTED_KEYS = {"reference_timezone", "delegation", "prompts"}


class PromptConfigError(ValueError):
    pass


class PromptConfigConflict(PromptConfigError):
    pass


def defaults():
    return {"reference_timezone": DEFAULT_TIMEZONE, "prompts": dict(DEFAULT_PROMPTS)}


def validate_config(data):
    """Validate the editable settings and attach the prompts from code."""
    if not isinstance(data, dict) or "reference_timezone" not in data or not set(data) <= _ACCEPTED_KEYS:
        raise PromptConfigError("Provide reference_timezone only.")
    name = data["reference_timezone"]
    if not isinstance(name, str) or not name or len(name) > 64:
        raise PromptConfigError("Enter a valid IANA timezone, such as Europe/Berlin.")
    try:
        ZoneInfo(name)
    except (ValueError, ZoneInfoNotFoundError):
        raise PromptConfigError("Enter a valid IANA timezone, such as Europe/Berlin.") from None
    return {"reference_timezone": name, "prompts": dict(DEFAULT_PROMPTS)}


def _stored(config):
    """The persisted (prompt-free) part of a validated config."""
    return {"reference_timezone": config["reference_timezone"]}


def _snapshot(document):
    if not document:
        return {**defaults(), "revision": 0, "updated_at": None, "updated_by": None}
    config = validate_config({key: document[key] for key in ("reference_timezone",) if key in document})
    revision = document.get("revision")
    if type(revision) is not int or revision < 1:
        raise PromptConfigError("The saved prompt revision is invalid.")
    return {**config, "revision": revision, "updated_at": document.get("updated_at"),
            "updated_by": document.get("updated_by")}


def _holds_legacy_fields(document):
    """True for a legacy document that still stores (ignored) prompt texts or
    delegation settings."""
    return bool(document) and ("prompts" in document or "delegation" in document)


def editable(snapshot):
    """Admin view of a runtime snapshot: only what the admin can change."""
    return {**_stored(snapshot), **{key: snapshot.get(key) for key in ("revision", "updated_at", "updated_by")}}


class PromptConfigStore:
    def __init__(self, db=None, *, clock=time.monotonic):
        self._db = db
        self.clock = clock
        self._lock = threading.RLock()
        self._cached = _snapshot(None)
        self._expires = 0.0

    @property
    def db(self):
        if self._db is None:
            from app.core.security import db_firestore
            return db_firestore
        return self._db

    def document(self):
        return self.db.collection("app_config").document("prompts")

    def read(self, *, force=False):
        with self._lock:
            if not force and self.clock() < self._expires:
                return deepcopy(self._cached)
            try:
                snap = self.document().get(timeout=3.0, retry=None)
                current = _snapshot(snap.to_dict() if snap.exists else None)
            except Exception as exc:
                if force:
                    raise
                logging.warning("Prompt configuration refresh failed category=%s", safe_exception(exc))
                current = self._cached
            self._cached = deepcopy(current)
            self._expires = self.clock() + CACHE_SECONDS
            return deepcopy(current)

    def save(self, config, *, expected_revision, updated_by):
        config = validate_config(config)
        if type(expected_revision) is not int or expected_revision < 0:
            raise PromptConfigError("A valid revision is required.")
        ref = self.document()

        def operation(tx):
            snap = ref.get(transaction=tx, timeout=3.0, retry=None)
            raw = snap.to_dict() if snap.exists else None
            current = _snapshot(raw)
            if current["revision"] != expected_revision:
                raise PromptConfigConflict("Configuration changed in another session. Reload before saving; your draft has been kept.")
            effective = _stored(config)
            if _stored(current) == effective and not _holds_legacy_fields(raw):
                # An initial explicit Save should still create the database record.
                if current["revision"]:
                    return current
            document = {**effective, "revision": current["revision"] + 1,
                        "updated_at": datetime.now(timezone.utc), "updated_by": updated_by}
            history = ref.collection("revisions").document(f"{document['revision']:012d}")
            # Full overwrite: a legacy document's prompt texts and delegation settings are dropped.
            persistence_guard._set(tx, ref, document)
            persistence_guard._set(tx, history, document)
            return _snapshot(document)

        with self._lock:
            saved = persistence_guard._run_transaction(self.db, operation)
            self._cached = deepcopy(saved)
            self._expires = self.clock() + CACHE_SECONDS
            return deepcopy(saved)


_runtime_store = PromptConfigStore()


def get_config():
    return _runtime_store.read()


def admin_config():
    from app.services.prompt_catalog import prompt_catalog
    return {"config": editable(_runtime_store.read(force=True)),
            "defaults": editable(_snapshot(None)),
            "prompts_readonly": prompt_catalog(),
            "cache_seconds": CACHE_SECONDS}


def save_config(config, *, expected_revision, updated_by):
    return editable(_runtime_store.save(config, expected_revision=expected_revision, updated_by=updated_by))
