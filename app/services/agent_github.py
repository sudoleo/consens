"""GitHub for the agent's VM (docs/agent-mode.md, "GitHub aus der VM").

Repositories come into the VM through the backend; the GitHub token never
does. A command in the VM can therefore neither push nor read a repository
the user did not name, and a page the agent read cannot talk it into either.

Credentials, from the backend's environment (none: no GitHub tool):
- AGENT_GITHUB_APP_ID and AGENT_GITHUB_APP_PRIVATE_KEY (PEM; ``\\n`` escapes work): a
  GitHub App installed on the repositories the agent may use. Each import
  gets an installation token for that one repository, valid for an hour
  (cached until five minutes before it expires).
- AGENT_GITHUB_TOKEN: a fine-grained personal access token, for its owner only.
The VM is for admins (AgentPreferences.vm), so either one belongs to the
installation's operator.

github_import(repo, ref, dest): the backend resolves ``ref`` (default: the
repository's default branch) to its commit, downloads that commit's tarball
(private repositories too, at most IMPORT_BYTES), writes it into the VM and
unpacks it into ~/repos/<name> as a fresh git repository with one commit,
"consens.io import of owner/name@<sha>"; ``.git/consens-import.json`` names
repository, ref and commit for a later pull request. Public repositories can
also be cloned in the VM itself (the VM reaches github.com), private ones only
this way.

Not yet: pull requests. Planned like the Gmail drafts (agent_gmail.py): a
``prepare_pull_request`` reads the changes from the VM, the user confirms a
card, and the backend creates branch, commit and pull request with the same
credentials (Git Data API), never the VM.
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import shlex
import tarfile
import threading
import time

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.observability import safe_exception
from app.services.agent_tools import ReadOnlyTool

API = "https://api.github.com"
API_VERSION = "2022-11-28"
REQUEST_SECONDS = 30
DOWNLOAD_SECONDS = 120
IMPORT_BYTES = 50 * 1024 * 1024
UNPACK_SECONDS = 180
# An installation token lives an hour; it is used until this long before.
TOKEN_MARGIN_SECONDS = 300
REPO = r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}$"
REF = r"^[A-Za-z0-9._/-]{1,200}$"
NAME = r"^[A-Za-z0-9._-]{1,100}$"
REPOS_DIR = "/home/sprite/repos"
IMPORT_RECORD = ".git/consens-import.json"


class GitHubUnavailable(ValueError):
    """What the agent reads when GitHub refused or failed (a tool error)."""


class GithubImportArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    repo: str = Field(pattern=REPO, description="owner/name")
    ref: str = Field(default="", max_length=200, description="Branch, tag or commit; default the default branch.")
    dest: str = Field(default="", max_length=100, description="Folder name under /home/sprite/repos; default the "
                                                                "repository's name.")


def configured():
    """Whether the environment holds GitHub credentials."""
    return bool(os.getenv("AGENT_GITHUB_TOKEN", "").strip()
                or (os.getenv("AGENT_GITHUB_APP_ID", "").strip()
                    and os.getenv("AGENT_GITHUB_APP_PRIVATE_KEY", "").strip()))


_TOKENS = {}
_TOKENS_LOCK = threading.Lock()


class GitHub:
    """The backend's GitHub client (``transport``, ``clock`` for tests)."""

    def __init__(self, *, transport=None, clock=time.time, env=None):
        env = os.environ if env is None else env
        self._pat = (env.get("AGENT_GITHUB_TOKEN") or "").strip()
        self._app_id = (env.get("AGENT_GITHUB_APP_ID") or "").strip()
        self._key = (env.get("AGENT_GITHUB_APP_PRIVATE_KEY") or "").strip().replace("\\n", "\n")
        self._clock = clock
        self._http = httpx.Client(base_url=API, timeout=REQUEST_SECONDS, transport=transport, follow_redirects=True,
                                  headers={"Accept": "application/vnd.github+json",
                                           "X-GitHub-Api-Version": API_VERSION,
                                           "User-Agent": "consens.io-agent"})

    def close(self):
        self._http.close()

    def _request(self, method, path, *, token, **kwargs):
        try:
            response = self._http.request(method, path, headers={"Authorization": f"Bearer {token}"}, **kwargs)
        except httpx.HTTPError as exc:
            logging.warning("GitHub request failed category=%s", safe_exception(exc))
            raise GitHubUnavailable("GitHub is not reachable right now. Try again later.") from None
        if response.status_code in (401, 403, 404):
            raise GitHubUnavailable("GitHub refused: this repository does not exist or consens.io has no access "
                                    "to it.")
        if not response.is_success:
            logging.warning("GitHub request refused status=%s", response.status_code)
            raise GitHubUnavailable(f"GitHub refused the request (HTTP {response.status_code}).")
        return response

    def _app_jwt(self):
        import jwt
        now = int(self._clock())
        return jwt.encode({"iat": now - 60, "exp": now + 540, "iss": self._app_id}, self._key, algorithm="RS256")

    def token(self, repo):
        """A token for ``repo``: the personal one, or an installation token
        of the app for this repository only."""
        if self._pat:
            return self._pat
        if not (self._app_id and self._key):
            raise GitHubUnavailable("GitHub is not set up on this installation.")
        with _TOKENS_LOCK:
            cached = _TOKENS.get((self._app_id, repo))
            if cached and cached[1] - TOKEN_MARGIN_SECONDS > self._clock():
                return cached[0]
        app = self._app_jwt()
        installation = self._request("GET", f"/repos/{repo}/installation", token=app).json()["id"]
        granted = self._request("POST", f"/app/installations/{int(installation)}/access_tokens", token=app,
                                json={"repositories": [repo.split("/", 1)[1]]}).json()
        expires = self._clock() + 3600
        try:
            from datetime import datetime
            expires = datetime.fromisoformat(granted["expires_at"].replace("Z", "+00:00")).timestamp()
        except (KeyError, ValueError, AttributeError):
            pass
        with _TOKENS_LOCK:
            _TOKENS[(self._app_id, repo)] = (granted["token"], expires)
        return granted["token"]

    def commit(self, repo, ref, *, token):
        """``(sha, ref)``: the commit ``ref`` names (default branch if empty)."""
        if not ref:
            ref = self._request("GET", f"/repos/{repo}", token=token).json()["default_branch"]
        data = self._request("GET", f"/repos/{repo}/commits/{ref}", token=token).json()
        return data["sha"], ref

    def tarball(self, repo, sha, *, token):
        """The commit's files as a gzipped tar, at most IMPORT_BYTES."""
        data = bytearray()
        try:
            with self._http.stream("GET", f"/repos/{repo}/tarball/{sha}", timeout=DOWNLOAD_SECONDS,
                                   headers={"Authorization": f"Bearer {token}"}) as response:
                if response.status_code in (401, 403, 404):
                    raise GitHubUnavailable("GitHub refused: this repository does not exist or consens.io has no "
                                            "access to it.")
                if not response.is_success:
                    raise GitHubUnavailable(f"GitHub refused the download (HTTP {response.status_code}).")
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > IMPORT_BYTES:
                        raise GitHubUnavailable(f"The repository is larger than {IMPORT_BYTES // (1024 * 1024)} MB "
                                                "packed. Clone a public one with git in the VM instead.")
        except httpx.HTTPError as exc:
            logging.warning("GitHub download failed category=%s", safe_exception(exc))
            raise GitHubUnavailable("GitHub is not reachable right now. Try again later.") from None
        return bytes(data)


def _count_files(raw):
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
            return sum(1 for member in archive if member.isfile())
    except (tarfile.TarError, OSError, EOFError):
        raise GitHubUnavailable("GitHub sent an archive that could not be read.") from None


def unpack_command(archive, dest, repo, ref, sha):
    """The VM's part: unpack into a new folder (exit 3 if it exists), then
    one commit of what came, with the import named in IMPORT_RECORD."""
    q = shlex.quote
    record = json.dumps({"repo": repo, "ref": ref, "commit": sha})
    return (f"set -e; dest={q(dest)}; if [ -e \"$dest\" ]; then echo \"$dest already exists\" >&2; exit 3; fi; "
            f"mkdir -p \"$dest\"; tar -xzf {q(archive)} -C \"$dest\" --strip-components=1; rm -f {q(archive)}; "
            "cd \"$dest\"; if command -v git >/dev/null; then git init -q; "
            f"printf '%s\\n' {q(record)} > {IMPORT_RECORD}; git add -A; "
            "git -c user.name=consens.io -c user.email=agent@consens.io commit -q --no-verify "
            f"-m {q(f'consens.io import of {repo}@{sha[:12]}')}; "
            "else echo 'git is not installed: the files are there without a repository' >&2; fi")


class GitHubTools:
    """The GitHub tools of one message, next to its VM tools (VMTools)."""

    def __init__(self, vm_tools, *, github=None):
        self.vm = vm_tools
        self._github = github

    @property
    def github(self):
        if self._github is None:
            self._github = GitHub()
        return self._github

    def tools(self):
        return [ReadOnlyTool("github_import", "Copy a GitHub repository (a private one too, if consens.io may read "
                             "it) into /home/sprite/repos in your VM, as a git repository with one commit of its "
                             "state. Returns the folder and the commit.", GithubImportArgs, self.import_repo,
                             activity=self._activity, reports=True)]

    def _dest(self, args):
        name = (args.dest.strip() or args.repo.split("/", 1)[1]).removesuffix(".git")
        if not re.fullmatch(NAME, name) or name in {".", ".."}:
            raise ValueError("dest must be a plain folder name (letters, digits, . _ -).")
        return f"{REPOS_DIR}/{name}"

    def import_repo(self, args, *, cancellation, report=None):
        from app.services import agent_vm_tools
        report = report or (lambda fields: None)
        if args.ref and (not re.fullmatch(REF, args.ref) or ".." in args.ref):
            raise ValueError("ref must be a branch, tag or commit name.")
        dest = self._dest(args)
        token = self.github.token(args.repo)
        sha, ref = self.github.commit(args.repo, args.ref, token=token)
        cancellation.raise_if_cancelled()
        raw = self.github.tarball(args.repo, sha, token=token)
        files = _count_files(raw)
        report({"repo": args.repo, "bytes": len(raw)})
        self.vm._start(cancellation)
        session = self.vm.session
        archive = f"/tmp/consens-import-{sha[:12]}.tar.gz"
        self.vm._provider("write", lambda: session.backend.write_file(session.name, archive, raw))
        outcome_text = []
        outcome = self.vm._provider("exec", lambda: session.backend.exec(
            session.name, unpack_command(archive, dest, args.repo, ref, sha), cwd=agent_vm_tools.HOME,
            timeout=UNPACK_SECONDS,
            on_output=lambda stream, chunk: outcome_text.append(chunk), cancellation=cancellation))
        if outcome.exit_code != 0:
            said = b"".join(outcome_text).decode("utf-8", "replace").strip()[-500:]
            if outcome.exit_code == 3:
                raise ValueError(f"{dest} already exists. Import into another folder (dest) or work in that one.")
            raise ValueError(f"Unpacking failed in the VM: {said or 'no output'}")
        return session.announce({"repo": args.repo, "ref": ref, "commit": sha, "path": dest, "files": files,
                                 "bytes": len(raw)})

    def _activity(self, args, result):
        try:
            path = self._dest(args)
        except ValueError:
            path = ""
        return {"path": path, "repo": args.repo, **self.vm._outcome(result)}
