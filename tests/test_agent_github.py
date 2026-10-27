"""GitHub for the agent's VM through a GitHub App each user installs
(agent_github.py, routers/agent_github.py). GitHub is httpx.MockTransport,
the VM is FakeVM (test_agent_vm.py); nothing calls GitHub, Sprites or a model.

What matters most: a user can only ever use the repositories GitHub itself
says they may access, never an installation named in a URL; tokens are minted
per operation for one repository and stay in the backend; nothing goes to
GitHub before the user confirms the card.
"""
import base64
import io
import json
import shutil
import subprocess
import tarfile

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.api.routers import agent_github as github_router
from app.services import agent_github, agent_vm, prompt_defaults
from app.services.agent_github import (NO_ACCESS, NO_PUSH, NOT_CONNECTED, NOT_SET_UP, WORKFLOWS_REFUSED, GitHubApp,
                                       GitHubConnections, GithubImportArgs, PullRequests, changes_command,
                                       diff_command, parse_changes, unpack_command)
from test_agent_runs import AUTH, UID, api, store  # noqa: F401  (fixtures)
from test_agent_vm import Agent, _admin_allowance, fake_vm, results, tool_events, vm_loop  # noqa: F401  (fixtures)

SHA = "a1b2c3d4e5f6" + "0" * 28
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                        serialization.NoEncryption()).decode()
ENV = {"GITHUB_APP_ID": "123", "GITHUB_APP_PRIVATE_KEY": PEM.replace("\n", "\\n"), "GITHUB_APP_CLIENT_ID": "Iv1.abc",
       "GITHUB_APP_CLIENT_SECRET": "client-secret", "GITHUB_APP_SLUG": "consens-io"}


def tarball(files):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(f"maxl-app-{SHA[:7]}/{name}")
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return raw.getvalue()


ARCHIVE = tarball({"README.md": b"# App\n", "src/main.py": b"print('hi')\n"})


class FakeGitHub:
    """GitHub's REST API for the app 123 with one installation (9) of the
    user maxl; ``requests`` records (method, url path, authorization, body)."""

    def __init__(self):
        self.requests, self.removed, self.installations = [], set(), [9]
        self.tokens = 0

    def __call__(self, request):
        path, method = request.url.path, request.method
        body = json.loads(request.content) if request.content and request.headers.get("content-type", "").startswith(
            "application/json") else request.content.decode() if request.content else None
        self.requests.append((method, request.url.host, path, request.headers.get("authorization"), body))
        if request.url.host == "codeload.github.com":
            return httpx.Response(200, content=ARCHIVE)
        if request.url.host == "github.com" and path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": "ghu_user"} if "code=good" in body else
                                  {"error": "bad_verification_code"})
        if path == "/user":
            return httpx.Response(200, json={"login": "maxl"})
        if path == "/user/installations":
            installations = [{"id": i, "app_id": 123, "account": {"login": "maxl"}} for i in self.installations]
            return httpx.Response(200, json={"installations": installations + [
                {"id": 77, "app_id": 999, "account": {"login": "someone"}}]})
        if path == "/user/installations/9/repositories":
            return httpx.Response(200, json={"repositories": [
                {"full_name": "maxl/app", "private": True, "permissions": {"pull": True, "push": True}},
                {"full_name": "org/readonly", "private": False, "permissions": {"pull": True, "push": False}},
                {"full_name": "org/hidden", "private": True, "permissions": {"pull": False}}]})
        if method == "DELETE" and path == "/applications/Iv1.abc/token":
            return httpx.Response(204)
        if method == "POST" and path.startswith("/app/installations/") and path.endswith("/access_tokens"):
            if int(path.split("/")[3]) in self.removed:
                return httpx.Response(404, json={"message": "Not Found"})
            self.tokens += 1
            return httpx.Response(201, json={"token": f"ghs_{self.tokens}", "expires_at": "2099-01-01T00:00:00Z"})
        if path == "/repos/maxl/app":
            return httpx.Response(200, json={"default_branch": "main"})
        if path == "/repos/maxl/app/commits/main":
            return httpx.Response(200, json={"sha": SHA})
        if path == f"/repos/maxl/app/tarball/{SHA}":
            return httpx.Response(302, headers={"Location": f"https://codeload.github.com/maxl/app/legacy.tar.gz/{SHA}?token=x"})
        if path == "/repos/maxl/app/branches/main":
            return httpx.Response(200, json={"name": "main"})
        if path.startswith("/repos/maxl/app/branches/"):
            return httpx.Response(404, json={"message": "Branch not found"})
        if path == f"/repos/maxl/app/git/commits/{SHA}":
            return httpx.Response(200, json={"tree": {"sha": "tree0"}})
        if method == "POST" and path == "/repos/maxl/app/git/blobs":
            return httpx.Response(201, json={"sha": "blob-" + base64.b64decode(body["content"]).decode()[:6]})
        if method == "POST" and path == "/repos/maxl/app/git/trees":
            return httpx.Response(201, json={"sha": "tree1"})
        if method == "POST" and path == "/repos/maxl/app/git/commits":
            return httpx.Response(201, json={"sha": "commit1"})
        if method == "POST" and path == "/repos/maxl/app/git/refs":
            return httpx.Response(201, json={"ref": body["ref"]})
        if method == "POST" and path == "/repos/maxl/app/pulls":
            return httpx.Response(201, json={"number": 12, "html_url": "https://github.com/maxl/app/pull/12"})
        return httpx.Response(500, json={"message": f"unexpected {method} {path}"})


@pytest.fixture
def github(monkeypatch):
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    fake = FakeGitHub()
    real = GitHubApp.__init__

    def offline(self, config=None, *, transport=None, clock=None):
        real(self, config, transport=httpx.MockTransport(fake), clock=clock or (lambda: 1_800_000_000.0))
    monkeypatch.setattr(GitHubApp, "__init__", offline)
    return fake


@pytest.fixture
def gh_api(api, monkeypatch):
    """The agent API of test_agent_runs plus the GitHub routes."""
    client, store, calls = api
    client.app.include_router(github_router.router)
    monkeypatch.setattr(github_router, "db_firestore", store.db)
    return client, store, calls


def connected(store, github):
    """The user's connection as finish saves it."""
    connections = GitHubConnections(store.db)
    data, browser = connections.start(UID)
    connections.finish(UID, data["state"], "good", browser)
    return connections


# --- Connecting -------------------------------------------------------------------

def test_connecting_saves_only_what_github_says_this_user_may_use(gh_api, github):
    client, store, _ = gh_api
    started = client.post("/agent/github/connect", headers=AUTH)
    assert started.status_code == 200
    data = started.json()
    assert data["install_url"].startswith("https://github.com/apps/consens-io/installations/new?state=")
    assert data["authorize_url"].startswith("https://github.com/login/oauth/authorize?client_id=Iv1.abc&state=")
    cookie = started.cookies.get("consens_github_oauth")
    assert cookie and cookie not in started.text
    # A spoofed installation in the callback URL changes nothing: only the
    # user's token decides (GET /user/installations).
    page = client.get("/agent/github/callback?code=good&installation_id=77&setup_action=install")
    assert page.status_code == 200 and "consens-github-oauth" in page.text
    # The browser that started it sends its cookie back (the client keeps it).
    assert client.cookies.get("consens_github_oauth") == cookie
    finished = client.post("/agent/github/finish", json={"state": data["state"], "code": "good"}, headers=AUTH)
    assert finished.status_code == 200
    info = finished.json()
    assert info["connected"] is True and info["login"] == "maxl"
    assert info["repositories"] == ["maxl/app", "org/readonly"]
    saved = store.db.collection("users").document(UID).collection("github_connections").document("github").get().to_dict()
    assert [item["id"] for item in saved["installations"]] == [9]
    assert saved["installations"][0]["repositories"][1] == {"full_name": "org/readonly", "private": False, "push": False}
    # The user token was only read with, then revoked; it is stored nowhere.
    assert ("DELETE", "api.github.com", "/applications/Iv1.abc/token") in [r[:3] for r in github.requests]
    assert "ghu_user" not in json.dumps(saved)
    assert client.get("/agent/github/connection", headers=AUTH).json()["connected"] is True


def test_a_connection_needs_its_own_browser_and_state_once(gh_api, github):
    client, store, _ = gh_api
    data = client.post("/agent/github/connect", headers=AUTH).json()
    # Without the cookie of the browser that started it (another browser, a forged link).
    client.cookies.clear()
    assert client.post("/agent/github/finish", json={"state": data["state"], "code": "good"}, headers=AUTH).status_code == 401
    # The state is spent either way.
    connections = GitHubConnections(store.db)
    data, browser = connections.start(UID)
    connections.finish(UID, data["state"], "good", browser)
    with pytest.raises(agent_github.GitHubUnavailable):
        connections.finish(UID, data["state"], "good", browser)
    # Another account cannot finish this user's connection.
    data, browser = connections.start(UID)
    with pytest.raises(agent_github.GitHubUnavailable):
        connections.finish("someone-else", data["state"], "good", browser)
    # GitHub refusing the code connects nothing.
    data, browser = connections.start("fresh-user")
    with pytest.raises(agent_github.GitHubUnavailable):
        connections.finish("fresh-user", data["state"], "bad", browser)
    assert connections.public("fresh-user")["connected"] is False


def test_without_the_app_github_is_not_set_up(gh_api, fake_vm, monkeypatch):
    client, store, _ = gh_api
    for key in ENV:
        monkeypatch.delenv(key, raising=False)
    assert client.post("/agent/github/connect", headers=AUTH).status_code == 503
    assert client.get("/agent/github/connection", headers=AUTH).json()["configured"] is False
    script = Agent([[("github_import", {"repo": "maxl/app"})]])
    loop = vm_loop(store, script)
    list(loop.run())
    # The tools come with the VM and say it calmly.
    assert {"github_import", "prepare_pull_request"} <= set(script.offered[0])
    assert prompt_defaults.AGENT_GITHUB_PROMPT in script.systems[0]
    assert results(loop) == [{"error": NOT_SET_UP}]


def test_disconnecting_forgets_the_connection(gh_api, github):
    client, store, _ = gh_api
    connected(store, github)
    info = client.delete("/agent/github/connection", headers=AUTH).json()
    assert info["connected"] is False and "uninstall it on GitHub" in info["notice"]


# --- Tokens and the import --------------------------------------------------------

def test_an_import_gets_a_token_for_that_repository_alone_and_none_reaches_the_vm(store, fake_vm, github):
    connected(store, github)
    script = Agent([[("github_import", {"repo": "maxl/app"})], [("github_import", {"repo": "org/hidden"})]])
    loop = vm_loop(store, script)
    events = list(loop.run())
    imported, hidden = results(loop)
    assert imported == {"repo": "maxl/app", "ref": "main", "commit": SHA, "path": "/home/sprite/repos/app",
                        "files": 2, "bytes": len(ARCHIVE), "chat_folder": agent_vm.chat_dir(loop.chat_id)}
    assert hidden == {"error": NO_ACCESS.format(repo="org/hidden")}
    [grant] = [r for r in github.requests if r[2].endswith("/access_tokens")]
    assert grant[2] == "/app/installations/9/access_tokens"
    assert grant[4] == {"repositories": ["app"], "permissions": {"contents": "read"}}
    claims = jwt.decode(grant[3].removeprefix("Bearer "), KEY.public_key(), algorithms=["RS256"],
                        options={"verify_exp": False, "verify_iat": False})
    assert claims["iss"] == "123"
    name = agent_vm.workspace_name(UID)
    archive = f"/tmp/consens-import-{SHA[:12]}.tar.gz"
    assert fake_vm.vms[name]["files"][archive] == ARCHIVE
    command = next(call[2] for call in fake_vm.calls if call[0] == "exec")
    assert command == unpack_command(archive, "/home/sprite/repos/app", "maxl/app", "main", SHA)
    everything = repr(fake_vm.calls) + repr(fake_vm.vms)
    assert "ghs_" not in everything and "ghu_" not in everything and "client-secret" not in everything
    assert [r[3] for r in github.requests if r[1] == "codeload.github.com"] == [None]
    done = [e for e in tool_events(events, "github_import") if e["status"] == "succeeded"][0]
    assert done["repo"] == "maxl/app" and done["path"] == "/home/sprite/repos/app"


def test_an_app_removed_on_github_shows_as_not_connected(store, fake_vm, github):
    connected(store, github)
    github.removed.add(9)
    loop = vm_loop(store, Agent([[("github_import", {"repo": "maxl/app"})], [("github_import", {"repo": "maxl/app"})]]))
    list(loop.run())
    removed, again = results(loop)
    assert "no longer connected" in removed["error"]
    assert again == {"error": NOT_CONNECTED}
    assert GitHubConnections(store.db).public(UID)["connected"] is False


def test_import_arguments_are_checked_before_anything_runs(store, fake_vm, github):
    connected(store, github)
    loop = vm_loop(store, Agent([[("github_import", {"repo": "maxl/app", "ref": "bad..ref"})],
                                 [("github_import", {"repo": "maxl/app", "dest": ".."})]]))
    list(loop.run())
    assert ["branch, tag or commit" in r["error"] or "plain folder name" in r["error"] for r in results(loop)] == [True, True]
    assert not [call for call in fake_vm.calls if call[0] in {"write", "exec"}]
    with pytest.raises(ValueError):
        GithubImportArgs(repo="not a repo")


# --- Pull requests ----------------------------------------------------------------

RAW = ("consens-raw\0:100644 100644 aaaa bbbb M\0src/main.py\0:000000 100755 0000 cccc A\0bin/run\0"
       ":100644 000000 dddd 0000 D\0old.txt\0consens-numstat\0" "3\t1\tsrc/main.py\0" "2\t0\tbin/run\0" "0\t5\told.txt\0")
PATH = "/home/sprite/repos/app"


@pytest.mark.skipif(not all(shutil.which(tool) for tool in ("bash", "git", "tar")), reason="needs bash, git, tar")
def test_the_vm_commands_list_changes_against_the_import_with_real_git(tmp_path):
    # The VM's repository is a fresh git init with its own commit: GitHub's
    # commit SHA from the import record is no object there ("bad object").
    # The fake VM above only matches command strings; this runs them.
    source = tmp_path / "src" / "maxl-app-abc"
    source.mkdir(parents=True)
    (source / "greeting.txt").write_text("hi\n")
    with tarfile.open(tmp_path / "arch.tgz", "w:gz") as archive:
        archive.add(source, arcname="maxl-app-abc")

    def run(command):
        done = subprocess.run(["bash", "-c", command], cwd=tmp_path, capture_output=True)
        assert done.returncode == 0, done.stderr.decode(errors="replace")
        return done.stdout.decode()

    run(unpack_command("arch.tgz", "repo", "maxl/app", "main", SHA))
    (tmp_path / "repo" / "greeting.txt").write_text("hello\n")
    (tmp_path / "repo" / "new.txt").write_text("new\n")
    changes = parse_changes(run(changes_command("repo")))
    assert [(item["path"], item["change"]) for item in changes] == [("greeting.txt", "modified"), ("new.txt", "added")]
    assert "+hello" in run(diff_command("repo"))


def test_git_changes_are_read_with_their_modes_and_counts():
    assert parse_changes(RAW) == [
        {"path": "src/main.py", "change": "modified", "mode": "100644", "additions": 3, "deletions": 1},
        {"path": "bin/run", "change": "added", "mode": "100755", "additions": 2, "deletions": 0},
        {"path": "old.txt", "change": "deleted", "mode": "100644", "additions": 0, "deletions": 5}]


def prepared(store, fake_vm, github, *, raw=RAW, args=None):
    connected(store, github)
    script = Agent([[("prepare_pull_request", {"path": "repos/app", "title": "Fix  the greeting",
                                               "body": "Says hello.", **(args or {})})]])
    loop = vm_loop(store, script, audit="off")
    loop.vm_tools.session.ready(agent_vm_tools_cancellation())
    files = fake_vm.vms[agent_vm.workspace_name(UID)]["files"]
    files[f"{PATH}/.git/consens-import.json"] = json.dumps({"repo": "maxl/app", "ref": "main", "commit": SHA}).encode()
    files[f"{PATH}/src/main.py"] = b"print('hello')\n"
    files[f"{PATH}/bin/run"] = b"#!/bin/sh\necho run\n"
    fake_vm.commands[changes_command(PATH)] = ([("stdout", raw.encode())], 0, .1)
    fake_vm.commands[diff_command(PATH)] = ([("stdout", b"--- a/src/main.py\n+++ b/src/main.py\n-hi\n+hello\n")], 0, .1)
    list(loop.run())
    return loop, files


def agent_vm_tools_cancellation():
    from app.services.llm.provider_runtime import ProviderCancellation
    return ProviderCancellation()


def turn_of(store, loop):
    return store._turn_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()


def test_a_prepared_pull_request_is_a_card_and_nothing_goes_to_github(store, fake_vm, github):
    loop, _ = prepared(store, fake_vm, github)
    [result] = results(loop)
    assert result["status"] == "prepared" and result["repo"] == "maxl/app" and result["base"] == "main"
    assert result["branch"].startswith("consens/fix-the-greeting-") and result["files"] == 3
    proposal = turn_of(store, loop)["agent_pull_request"]
    assert proposal["status"] == "pending" and proposal["title"] == "Fix the greeting"
    assert [(f["path"], f["change"]) for f in proposal["files"]] == [("src/main.py", "modified"), ("bin/run", "added"),
                                                                    ("old.txt", "deleted")]
    assert proposal["files"][0]["sha256"] and "sha256" not in proposal["files"][2]
    assert proposal["diff"].startswith("--- a/src/main.py") and len(proposal["hash"]) == 64
    # Before the card: read only. No blob, tree, commit, branch or pull request.
    assert not [r for r in github.requests if r[0] == "POST" and "/repos/" in r[2]]
    grants = [r[4] for r in github.requests if r[2].endswith("/access_tokens")]
    assert grants == [{"repositories": ["app"], "permissions": {"contents": "read"}}]
    # The browser gets the card with the turn.
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_pull_request"]["hash"] == proposal["hash"]


def test_workflows_a_read_only_repository_and_an_unimported_folder_are_refused(store, fake_vm, github):
    loop, _ = prepared(store, fake_vm, github, raw="consens-raw\0:100644 100644 a b M\0.github/workflows/ci.yml\0"
                                                   "consens-numstat\0" "1\t1\t.github/workflows/ci.yml\0")
    assert results(loop) == [{"error": WORKFLOWS_REFUSED}]
    assert "agent_pull_request" not in turn_of(store, loop)
    loop = vm_loop(store, Agent([[("prepare_pull_request", {"path": "elsewhere", "title": "x"})]]), request_id="two")
    list(loop.run())
    assert "only from a repository brought in with github_import" in results(loop)[0]["error"]
    connections = GitHubConnections(store.db)
    with pytest.raises(agent_github.GitHubUnavailable, match="not push"):
        connections.access(UID, "org/readonly", push=True)
    assert NO_PUSH.format(repo="org/readonly").startswith("The user may read org/readonly")


def test_the_card_creates_a_new_branch_and_the_pull_request(store, fake_vm, github):
    loop, _ = prepared(store, fake_vm, github)
    proposal = turn_of(store, loop)["agent_pull_request"]
    done = PullRequests(store.db, vm_factory=fake_vm.backend).confirm(UID, loop.chat_id, loop.turn_id, proposal["hash"])
    assert done["status"] == "succeeded"
    assert done["result"] == {"number": 12, "url": "https://github.com/maxl/app/pull/12", "commit": "commit1"}
    writes = [(r[2], r[4]) for r in github.requests if r[0] == "POST" and "/repos/" in r[2]]
    blobs = [body for path, body in writes if path.endswith("/git/blobs")]
    assert sorted(base64.b64decode(b["content"]) for b in blobs) == [b"#!/bin/sh\necho run\n", b"print('hello')\n"]
    tree = next(body for path, body in writes if path.endswith("/git/trees"))
    assert tree["base_tree"] == "tree0"
    assert {(e["path"], e["mode"], e["sha"] is None) for e in tree["tree"]} == {
        ("src/main.py", "100644", False), ("bin/run", "100755", False), ("old.txt", "100644", True)}
    commit = next(body for path, body in writes if path.endswith("/git/commits"))
    assert commit["parents"] == [SHA] and commit["message"] == "Fix the greeting\n\nSays hello."
    ref = next(body for path, body in writes if path.endswith("/git/refs"))
    assert ref["ref"] == f"refs/heads/{proposal['branch']}" and ref["sha"] == "commit1"
    pull = next(body for path, body in writes if path.endswith("/pulls"))
    assert pull == {"title": "Fix the greeting", "body": "Says hello.", "head": proposal["branch"], "base": "main"}
    # The write token: that repository, contents and pull requests only.
    grants = [r[4] for r in github.requests if r[2].endswith("/access_tokens")]
    assert grants[-1] == {"repositories": ["app"], "permissions": {"contents": "write", "pull_requests": "write"}}
    assert turn_of(store, loop)["agent_pull_request"]["status"] == "succeeded"
    # Once.
    with pytest.raises(agent_github.GitHubUnavailable, match="already handled"):
        PullRequests(store.db, vm_factory=fake_vm.backend).confirm(UID, loop.chat_id, loop.turn_id, proposal["hash"])


def test_files_changed_after_the_preview_never_go_to_github(store, fake_vm, github):
    loop, files = prepared(store, fake_vm, github)
    proposal = turn_of(store, loop)["agent_pull_request"]
    files[f"{PATH}/src/main.py"] = b"print('something else')\n"
    done = PullRequests(store.db, vm_factory=fake_vm.backend).confirm(UID, loop.chat_id, loop.turn_id, proposal["hash"])
    assert done["status"] == "failed" and "changed since the preview" in done["error"]
    assert not [r for r in github.requests if r[0] == "POST" and "/repos/" in r[2]]


def test_a_discarded_or_altered_card_creates_nothing(gh_api, fake_vm, github):
    client, store, _ = gh_api
    loop, _ = prepared(store, fake_vm, github)
    proposal = turn_of(store, loop)["agent_pull_request"]
    url = f"/agent/chats/{loop.chat_id}/turns/{loop.turn_id}/pull-request"
    assert client.post(url, json={"expected_hash": "0" * 64}, headers=AUTH).status_code == 409
    discarded = client.post(url + "/discard", json={"expected_hash": proposal["hash"]}, headers=AUTH)
    assert discarded.status_code == 200 and discarded.json()["pull_request"]["status"] == "discarded"
    assert client.post(url, json={"expected_hash": proposal["hash"]}, headers=AUTH).status_code == 409
    assert not [r for r in github.requests if r[0] == "POST" and "/repos/" in r[2]]


def test_account_deletion_removes_the_connection():
    from app.services import account_deletion
    import inspect
    source = inspect.getsource(account_deletion.AccountDeletionJob._delete_user_subcollections) \
        if hasattr(account_deletion, "AccountDeletionJob") else inspect.getsource(account_deletion)
    assert '"github_connections", "github_oauth_states"' in source
