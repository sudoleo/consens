"""Projects: named groups of chats in the sidebar.

One document per account, ``users/{uid}/chat_state/projects``, holds the
list (``{id, name, created_at}``, in the order they were made). A chat joins
a project through ``project_id`` on its bookmark (routers/bookmarks.py);
every later save of the chat is a merge and keeps it, like a pin. The
account's deletion sweeps ``chat_state`` (ChatStore.delete_all_chats), so
the list leaves with the account.

A deleted project takes none of its chats along: its removal from the list
comes first, then its chats lose their ``project_id`` (clear_bookmarks). A
chat that still names a project the list does not hold is an ordinary chat
to the browser, so an interrupted clean-up shows nothing wrong.
"""

from __future__ import annotations

import logging
import re
import secrets
import unicodedata
from datetime import datetime, timezone

from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.observability import safe_exception
from app.services import persistence_guard

DOC = "projects"
FIELD = "project_id"
MAX_PROJECTS = 100
MAX_NAME_CHARS = 80
# Bookmarks a project lists and its deletion clears: the bookmark cap, so
# no chat of a project is ever left out.
MAX_PROJECT_BOOKMARKS = persistence_guard.MAX_BOOKMARKS_PER_USER
PROJECT_ID_RE = re.compile(r"p_[A-Za-z0-9]{12}")
_ID_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_CONTROL = re.compile(r"[\u0000-\u001f\u007f-\u009f​-‏ -‮⁠-⁤﻿]")
# Firestore's limit per batch is 500 writes; fewer keep a batch's request small.
_CLEAR_BATCH = 400


class ProjectNotFound(LookupError):
    """The account has no project with that id (deleted, or never made)."""


class ProjectLimitReached(RuntimeError):
    """The account has MAX_PROJECTS projects already."""


def ref(db, uid: str):
    return db.collection("users").document(uid).collection("chat_state").document(DOC)


def clean_name(raw) -> str:
    """A project's name as stored: one line, no invisible marks, at most
    MAX_NAME_CHARS. "" where nothing is left."""
    if not isinstance(raw, str):
        return ""
    text = _CONTROL.sub(" ", unicodedata.normalize("NFC", raw))
    return " ".join(text.split())[:MAX_NAME_CHARS].strip()


def valid_id(value) -> bool:
    return isinstance(value, str) and bool(PROJECT_ID_RE.fullmatch(value))


def _entries(data) -> list[dict]:
    projects = []
    seen = set()
    for entry in (data or {}).get("projects") or []:
        if not isinstance(entry, dict) or not valid_id(entry.get("id")) or entry["id"] in seen:
            continue
        name = clean_name(entry.get("name"))
        if not name:
            continue
        seen.add(entry["id"])
        projects.append({"id": entry["id"], "name": name, "created_at": str(entry.get("created_at") or "")})
    return projects[:MAX_PROJECTS]


def list_projects(db, uid: str) -> list[dict]:
    snapshot = ref(db, uid).get()
    return _entries(snapshot.to_dict() if snapshot.exists else {})


def ids_in(db, uid: str, transaction) -> set[str]:
    """The account's project ids as ``transaction`` reads them, so a write
    that names a project fails over once the project is gone."""
    snapshot = persistence_guard._get(ref(db, uid), transaction)
    return {entry["id"] for entry in _entries(snapshot.to_dict() if snapshot.exists else {})}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _change(db, uid: str, change):
    """Runs ``change(projects) -> result`` on the account's list in one
    transaction fenced against the account's deletion, and stores the list
    ``change`` leaves."""
    doc = ref(db, uid)

    def operation(transaction):
        persistence_guard.ensure_account_write_allowed(uid=uid, db=db, transaction=transaction)
        snapshot = persistence_guard._get(doc, transaction)
        projects = _entries(snapshot.to_dict() if snapshot.exists else {})
        result = change(projects)
        persistence_guard._set(transaction, doc, {"projects": projects, "updated_at": _now()})
        return result

    return persistence_guard._run_transaction(db, operation)


def create(db, uid: str, name: str) -> dict:
    name = clean_name(name)
    if not name:
        raise ValueError("A project needs a name.")
    project = {"id": "p_" + "".join(secrets.choice(_ID_ALPHABET) for _ in range(12)),
               "name": name, "created_at": _now()}

    def change(projects):
        if len(projects) >= MAX_PROJECTS:
            raise ProjectLimitReached("Project limit reached.")
        projects.append(project)
        return project

    return _change(db, uid, change)


def rename(db, uid: str, project_id: str, name: str) -> dict:
    name = clean_name(name)
    if not name:
        raise ValueError("A project needs a name.")

    def change(projects):
        for entry in projects:
            if entry["id"] == project_id:
                entry["name"] = name
                return dict(entry)
        raise ProjectNotFound("Project not found")

    return _change(db, uid, change)


def delete(db, uid: str, project_id: str) -> None:
    """Removes the project from the list, then lets its chats go back to
    the others (clear_bookmarks). Its chats stay."""
    def change(projects):
        kept = [entry for entry in projects if entry["id"] != project_id]
        if len(kept) == len(projects):
            raise ProjectNotFound("Project not found")
        projects[:] = kept

    _change(db, uid, change)
    clear_bookmarks(db, uid, project_id)


def bookmarks_query(db, uid: str, project_id: str):
    """The bookmarks of one project: one equality filter, which Firestore's
    automatic single-field index serves (no ordering, see the router)."""
    return (db.collection("users").document(uid).collection("bookmarks")
            .where(filter=FieldFilter(FIELD, "==", project_id)))


def clear_bookmarks(db, uid: str, project_id: str) -> int:
    """Takes ``project_id`` off every bookmark that still names it; returns
    how many. Never raises: a chat left naming a deleted project shows among
    the others anyway (module docstring). An update, never a set: a chat
    deleted meanwhile is not made again."""
    try:
        snapshots = list(bookmarks_query(db, uid, project_id).select([FIELD]).limit(MAX_PROJECT_BOOKMARKS).stream())
    except Exception as exc:
        logging.warning("Project bookmarks not cleared category=%s", safe_exception(exc))
        return 0
    cleared = 0
    batch_of = getattr(db, "batch", None)
    for start in range(0, len(snapshots), _CLEAR_BATCH):
        chunk = snapshots[start:start + _CLEAR_BATCH]
        if callable(batch_of):
            try:
                batch = batch_of()
                for snapshot in chunk:
                    batch.update(snapshot.reference, {FIELD: None})
                batch.commit()
                cleared += len(chunk)
                continue
            except Exception as exc:
                # One chat deleted meanwhile fails the whole batch: each on its own.
                logging.info("Project bookmarks batch fell back category=%s", safe_exception(exc))
        for snapshot in chunk:
            try:
                snapshot.reference.update({FIELD: None})
                cleared += 1
            except Exception as exc:
                logging.info("Project bookmark not cleared category=%s", safe_exception(exc))
    return cleared
