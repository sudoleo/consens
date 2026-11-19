"""Projects in the sidebar: the account's list (chat_projects) and the
routes that make, rename and delete projects and move chats between them
(routers/bookmarks.py)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import bookmarks as bookmarks_router
from app.core.rate_limit import limiter
from app.services import chat_projects, persistence_guard
from test_chat_history import FakeChatDatabase

LIST_START = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
AUTH = {"Authorization": "Bearer token"}


def _client(database, uid="uid-1"):
    limiter._storage.reset()
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)
    patches = (patch.object(bookmarks_router, "verify_user_token", return_value=uid),
               patch.object(bookmarks_router, "db_firestore", database))
    return TestClient(app), patches


def _call(database, method, path, json=None, uid="uid-1"):
    client, patches = _client(database, uid)
    with patches[0], patches[1]:
        return client.request(method, path, headers=AUTH, json=json)


def _seed(database, ids, uid="uid-1"):
    for index, bookmark_id in enumerate(ids):
        database.documents[("users", uid, "bookmarks", bookmark_id)] = {
            "query": f"Question {bookmark_id}", "timestamp": LIST_START - timedelta(minutes=index),
        }


def _create(database, name):
    response = _call(database, "POST", "/projects", {"name": name})
    assert response.status_code == 200, response.text
    return response.json()["project"]


def _move(database, bookmark_id, project_id):
    return _call(database, "PATCH", f"/bookmarks/{bookmark_id}/project", {"project_id": project_id})


def test_a_project_is_made_renamed_and_listed_with_the_first_page_only():
    database = FakeChatDatabase()
    _seed(database, ["b1", "b2", "b3"])

    tax = _create(database, "  Tax\n2026  ")
    move = _create(database, "Move to Berlin")
    renamed = _call(database, "PATCH", f"/projects/{tax['id']}", {"name": "Taxes 2026"})
    first = _call(database, "GET", "/bookmarks?limit=2")
    second = _call(database, "GET", "/bookmarks?limit=2&cursor=" + first.json()["next_cursor"])

    assert chat_projects.valid_id(tax["id"]) and tax["id"] != move["id"]
    assert tax["name"] == "Tax 2026"
    assert renamed.json()["project"]["name"] == "Taxes 2026"
    assert [(p["id"], p["name"]) for p in first.json()["projects"]] == [
        (tax["id"], "Taxes 2026"), (move["id"], "Move to Berlin")]
    assert "projects" not in second.json()
    assert _call(database, "GET", "/projects").json()["projects"] == first.json()["projects"]


def test_a_project_needs_a_name_and_the_list_has_a_cap():
    database = FakeChatDatabase()
    blank = _call(database, "POST", "/projects", {"name": " ​\n "})
    cut = _create(database, "x" * 300)
    database.documents[("users", "uid-1", "chat_state", "projects")] = {"projects": [
        {"id": f"p_{index:012d}", "name": f"P{index}", "created_at": ""}
        for index in range(chat_projects.MAX_PROJECTS)]}
    full = _call(database, "POST", "/projects", {"name": "One more"})

    assert blank.status_code == 400
    assert len(cut["name"]) == chat_projects.MAX_NAME_CHARS
    assert full.status_code == 409
    assert f"You have {chat_projects.MAX_PROJECTS} projects." in full.json()["detail"]
    assert len(_call(database, "GET", "/projects").json()["projects"]) == chat_projects.MAX_PROJECTS


def test_a_chat_moves_into_a_project_keeps_it_through_later_saves_and_moves_out():
    database = FakeChatDatabase()
    _seed(database, ["b1", "b2", "b3"])
    project = _create(database, "Research")

    moved = _move(database, "b3", project["id"])
    _move(database, "b1", project["id"])
    persistence_guard.write_bookmark(
        uid="uid-1", db=database, patch={"responses": {"consensus": "A later answer"}},
        doc_ref=database.collection("users").document("uid-1").collection("bookmarks").document("b3"))
    inside = _call(database, "GET", f"/projects/{project['id']}/bookmarks")
    listed = {row["id"]: row["project_id"] for row in _call(database, "GET", "/bookmarks").json()["bookmarks"]}
    out = _move(database, "b1", None)

    assert moved.status_code == 200, moved.text
    assert moved.json()["bookmark"]["project_id"] == project["id"]
    # Newest first, whatever order they joined in.
    assert [row["id"] for row in inside.json()["bookmarks"]] == ["b1", "b3"]
    assert listed == {"b1": project["id"], "b2": None, "b3": project["id"]}
    assert out.json()["bookmark"]["project_id"] is None
    assert [row["id"] for row in _call(database, "GET", f"/projects/{project['id']}/bookmarks")
            .json()["bookmarks"]] == ["b3"]


def test_a_chat_cannot_move_into_a_project_that_is_not_there_nor_be_made_by_a_move():
    database = FakeChatDatabase()
    _seed(database, ["b1"])
    project = _create(database, "Research")

    unknown = _move(database, "b1", "p_000000000000")
    malformed = _move(database, "b1", "../other")
    missing = _move(database, "gone_bookmark", project["id"])
    wrong_type = _move(database, "b1", 5)

    assert unknown.status_code == 404 and unknown.json()["detail"] == "Project not found"
    assert malformed.status_code == 404
    assert missing.status_code == 404
    assert wrong_type.status_code == 422
    assert "project_id" not in database.documents[("users", "uid-1", "bookmarks", "b1")]
    assert ("users", "uid-1", "bookmarks", "gone_bookmark") not in database.documents


def test_deleting_a_project_keeps_its_chats_and_lets_them_go_back():
    database = FakeChatDatabase()
    _seed(database, ["b1", "b2"])
    keep = _create(database, "Keep")
    gone = _create(database, "Gone")
    _move(database, "b1", gone["id"])
    _move(database, "b2", keep["id"])

    deleted = _call(database, "DELETE", f"/projects/{gone['id']}")
    again = _call(database, "DELETE", f"/projects/{gone['id']}")
    rows = {row["id"]: row["project_id"] for row in _call(database, "GET", "/bookmarks").json()["bookmarks"]}

    assert deleted.status_code == 200, deleted.text
    assert again.status_code == 404
    assert rows == {"b1": None, "b2": keep["id"]}
    assert [p["id"] for p in _call(database, "GET", "/projects").json()["projects"]] == [keep["id"]]
    assert _move(database, "b2", gone["id"]).status_code == 404


def test_a_chat_naming_a_project_the_list_lost_lists_like_any_other():
    """An interrupted clean-up leaves a stale id; the list still shows a
    well-formed one, and the browser treats an id it has no project for as
    no project (chat-list.js)."""
    database = FakeChatDatabase()
    _seed(database, ["b1", "b2"])
    database.documents[("users", "uid-1", "bookmarks", "b1")]["project_id"] = "p_aaaaaaaaaaaa"
    database.documents[("users", "uid-1", "bookmarks", "b2")]["project_id"] = {"not": "an id"}

    rows = {row["id"]: row["project_id"] for row in _call(database, "GET", "/bookmarks").json()["bookmarks"]}

    assert rows == {"b1": "p_aaaaaaaaaaaa", "b2": None}


def test_an_account_being_deleted_makes_no_project():
    database = FakeChatDatabase()
    database.documents[(persistence_guard.ACCOUNT_DELETION_JOBS_COLLECTION, "uid-1")] = {"status": "pending"}

    response = _call(database, "POST", "/projects", {"name": "Late"})

    assert response.status_code == 409
    assert ("users", "uid-1", "chat_state", "projects") not in database.documents


def test_projects_belong_to_their_account():
    database = FakeChatDatabase()
    _seed(database, ["b1"], uid="uid-2")
    mine = _create(database, "Mine")

    theirs = _call(database, "GET", "/projects", uid="uid-2")
    move = _call(database, "PATCH", "/bookmarks/b1/project", {"project_id": mine["id"]}, uid="uid-2")
    rename = _call(database, "PATCH", f"/projects/{mine['id']}", {"name": "Taken"}, uid="uid-2")

    assert theirs.json()["projects"] == []
    assert move.status_code == 404
    assert rename.status_code == 404
    assert _call(database, "GET", "/projects").json()["projects"][0]["name"] == "Mine"


def test_project_answers_are_never_cached():
    """Project names are the account's own words, like its chat titles."""
    from app.core.security import CustomSecurityMiddleware

    database = FakeChatDatabase()
    limiter._storage.reset()
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(bookmarks_router.router)
    app.add_middleware(CustomSecurityMiddleware)
    with patch.object(bookmarks_router, "verify_user_token", return_value="uid-1"), \
            patch.object(bookmarks_router, "db_firestore", database):
        client = TestClient(app)
        made = client.post("/projects", headers=AUTH, json={"name": "Private"})
        listed = client.get(f"/projects/{made.json()['project']['id']}/bookmarks", headers=AUTH)

    assert made.headers["cache-control"] == "private, no-store"
    assert listed.headers["cache-control"] == "private, no-store"
