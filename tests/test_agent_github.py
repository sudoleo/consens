"""GitHub for the agent's VM (agent_github.py): the backend brings a
repository into the VM, the token never goes there. GitHub is
httpx.MockTransport, the VM is FakeVM (test_agent_vm.py); nothing here
calls GitHub, Sprites or a model.
"""
import io
import json
import tarfile

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.services import agent_github, agent_vm, prompt_defaults
from app.services.agent_github import GitHub, GithubImportArgs, GitHubUnavailable, unpack_command
from app.services.llm.provider_runtime import ProviderCancellation
from test_agent_runs import UID, store  # noqa: F401  (fixture)
from test_agent_vm import Agent, _admin_allowance, fake_vm, results, tool_events, vm_loop  # noqa: F401  (fixtures)

SHA = "a1b2c3d4e5f6" + "0" * 28


def tarball(files):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(f"owner-app-{SHA[:7]}/{name}")
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return raw.getvalue()


ARCHIVE = tarball({"README.md": b"# App\n", "src/main.py": b"print('hi')\n"})


class FakeGitHub:
    """The REST API for one repository ``owner/app``; ``requests`` records
    (host, method, path, authorization)."""

    def __init__(self, *, archive=ARCHIVE, refuse=()):
        self.archive, self.refuse, self.requests = archive, set(refuse), []

    def __call__(self, request):
        path = request.url.path
        self.requests.append((request.url.host, request.method, path, request.headers.get("authorization")))
        if path in self.refuse:
            return httpx.Response(404, json={"message": "Not Found"})
        if request.url.host == "codeload.github.com":
            return httpx.Response(200, content=self.archive)
        if path == "/repos/owner/app":
            return httpx.Response(200, json={"default_branch": "main"})
        if path in ("/repos/owner/app/commits/main", "/repos/owner/app/commits/v2"):
            return httpx.Response(200, json={"sha": SHA})
        if path == f"/repos/owner/app/tarball/{SHA}":
            return httpx.Response(302, headers={"Location": f"https://codeload.github.com/owner/app/legacy.tar.gz/{SHA}?token=short"})
        if path == "/repos/owner/app/installation":
            return httpx.Response(200, json={"id": 9})
        if path == "/app/installations/9/access_tokens":
            assert json.loads(request.content) == {"repositories": ["app"]}
            return httpx.Response(201, json={"token": "ghs_installation", "expires_at": "2099-01-01T00:00:00Z"})
        return httpx.Response(500)


@pytest.fixture(autouse=True)
def _no_cached_tokens(monkeypatch):
    monkeypatch.setattr(agent_github, "_TOKENS", {})
    for name in ("AGENT_GITHUB_TOKEN", "AGENT_GITHUB_APP_ID", "AGENT_GITHUB_APP_PRIVATE_KEY"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def github(monkeypatch):
    api = FakeGitHub()
    monkeypatch.setenv("AGENT_GITHUB_TOKEN", "github_pat_secret")
    monkeypatch.setattr(agent_github, "GitHub", lambda: GitHub(transport=httpx.MockTransport(api)))
    return api


def test_github_is_offered_only_with_credentials(store, fake_vm, monkeypatch):
    assert agent_github.configured() is False
    script = Agent()
    loop = vm_loop(store, script)
    list(loop.run())
    assert "github_import" not in script.offered[0] and prompt_defaults.AGENT_GITHUB_PROMPT not in script.systems[0]
    monkeypatch.setenv("AGENT_GITHUB_APP_ID", "123")
    assert agent_github.configured() is False  # an app needs its key too
    monkeypatch.setenv("AGENT_GITHUB_APP_PRIVATE_KEY", "-----BEGIN PRIVATE KEY-----")
    assert agent_github.configured() is True
    script = Agent()
    loop = vm_loop(store, script, request_id="two")
    list(loop.run())
    assert "github_import" in script.offered[0] and prompt_defaults.AGENT_GITHUB_PROMPT in script.systems[0]


def test_a_repository_comes_into_the_vm_without_its_token(store, fake_vm, github):
    script = Agent([[("github_import", {"repo": "owner/app"})]])
    loop = vm_loop(store, script)
    events = list(loop.run())
    [result] = results(loop)
    assert result == {"repo": "owner/app", "ref": "main", "commit": SHA, "path": "/home/sprite/repos/app",
                      "files": 2, "bytes": len(ARCHIVE)}
    name = agent_vm.vm_name(UID, loop.chat_id)
    archive = f"/tmp/consens-import-{SHA[:12]}.tar.gz"
    assert fake_vm.vms[name]["files"][archive] == ARCHIVE
    [command] = [call[2] for call in fake_vm.calls if call[0] == "exec"]
    assert command == unpack_command(archive, "/home/sprite/repos/app", "owner/app", "main", SHA)
    assert "tar -xzf" in command and "git init -q" in command and "consens.io import of owner/app@a1b2c3d4e5f6" in command
    # The token went to GitHub's API only: never into the VM, never to the download host.
    assert "github_pat_secret" not in repr(fake_vm.calls) and "github_pat_secret" not in repr(fake_vm.vms)
    api = [request for request in github.requests if request[0] == "api.github.com"]
    assert api and all(request[3] == "Bearer github_pat_secret" for request in api)
    assert [request[3] for request in github.requests if request[0] == "codeload.github.com"] == [None]
    done = [e for e in tool_events(events, "github_import") if e["status"] == "succeeded"][0]
    assert done["repo"] == "owner/app" and done["path"] == "/home/sprite/repos/app"
    entry = next(e for e, _ in loop.work_log.entries_after(0) if e["kind"] == "tool" and e["name"] == "github_import")
    assert entry["data"] == "vm"


def test_an_app_gets_a_token_for_the_one_repository_and_reuses_it(store, fake_vm, monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    api = FakeGitHub()
    client = GitHub(transport=httpx.MockTransport(api), clock=lambda: 1_800_000_000.0,
                    env={"AGENT_GITHUB_APP_ID": "123", "AGENT_GITHUB_APP_PRIVATE_KEY": pem.replace("\n", "\\n")})
    assert client.token("owner/app") == "ghs_installation"
    assert client.token("owner/app") == "ghs_installation"
    granted = [r for r in api.requests if r[2].endswith("/access_tokens")]
    assert len(granted) == 1
    claims = jwt.decode(granted[0][3].removeprefix("Bearer "), key.public_key(), algorithms=["RS256"],
                        options={"verify_exp": False, "verify_iat": False})
    assert claims["iss"] == "123" and claims["exp"] - claims["iat"] <= 600
    assert client.commit("owner/app", "v2", token="ghs_installation") == (SHA, "v2")


def test_github_refusals_are_the_agents_tool_errors(store, fake_vm, monkeypatch, github):
    github.refuse.add("/repos/owner/app/commits/nope")
    loop = vm_loop(store, Agent([[("github_import", {"repo": "owner/app", "ref": "nope"})],
                                 [("github_import", {"repo": "owner/app", "ref": "bad..ref"})]]))
    list(loop.run())
    refused, invalid = results(loop)
    assert "no access" in refused["error"] and "branch, tag or commit" in invalid["error"]
    # Nothing reached the VM.
    assert not [call for call in fake_vm.calls if call[0] in {"write", "exec"}]
    with pytest.raises(ValueError):
        GithubImportArgs(repo="not a repo")


def test_a_large_repository_or_a_taken_folder_is_said_plainly(store, fake_vm, monkeypatch, github):
    loop = vm_loop(store, Agent())
    tools = agent_github.GitHubTools(loop.vm_tools)
    cancellation = ProviderCancellation()
    monkeypatch.setattr(agent_github, "IMPORT_BYTES", 100)
    with pytest.raises(GitHubUnavailable, match="larger than"):
        tools.import_repo(GithubImportArgs(repo="owner/app"), cancellation=cancellation)
    monkeypatch.setattr(agent_github, "IMPORT_BYTES", 10_000_000)
    archive = f"/tmp/consens-import-{SHA[:12]}.tar.gz"
    command = unpack_command(archive, "/home/sprite/repos/web", "owner/app", "main", SHA)
    fake_vm.commands[command] = ([("stderr", b"/home/sprite/repos/web already exists\n")], 3, .1)
    with pytest.raises(ValueError, match="already exists"):
        tools.import_repo(GithubImportArgs(repo="owner/app", dest="web"), cancellation=cancellation)
    with pytest.raises(ValueError, match="plain folder name"):
        tools.import_repo(GithubImportArgs(repo="owner/app", dest=".."), cancellation=cancellation)
