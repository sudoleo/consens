"""GitHub for the agent's VM through a GitHub App each user installs
(docs/agent-mode.md, "GitHub aus der VM").

Configuration (backend environment, all five or GitHub is "not set up"):
GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY (PEM; ``\\n`` escapes work),
GITHUB_APP_CLIENT_ID, GITHUB_APP_CLIENT_SECRET and GITHUB_APP_SLUG (the name
in https://github.com/apps/<slug>). The app is public, so any GitHub account
can install it on repositories of its choice.

Connecting (per user, Settings -> GitHub; GitHubConnections), like Google's:
1. ``start``: a one-time state (STATE_MINUTES) under the user's
   ``github_oauth_states``, bound to this browser by an HttpOnly cookie; the
   popup opens the app's installation page with it.
2. GitHub sends the popup to the callback page (the app's Callback URL, with
   "Request user authorization (OAuth) during installation"), which hands the
   code to the window that opened it. Without a code (an existing
   installation) the popup asks for the user's authorization instead.
3. ``finish`` (the signed-in user, the state, the cookie, the code): the code
   becomes a user-to-server token; GET /user/installations lists the
   installations of this app the GitHub user may access, and per installation
   the repositories with the user's own permissions. Only that is saved
   (``github_connections/github``), never an installation_id from a URL (a
   spoofed one would let one user use another's repositories, GitHub's own
   warning). The user token is revoked at once and never stored.

Tokens: one installation token per operation, minted by the backend with the
app's key, for the one repository and the permissions the operation needs
(contents read for an import; contents and pull requests write for a pull
request). It never reaches the VM, the browser or a model. The user's own
GitHub permission bounds it as well: an import needs read access, a pull
request push access, as GitHub reported them when the user connected; a
repository added later needs "Connect" again. An app the user removed on
GitHub shows at the next use: the token request fails, the tool says
"not connected" and that installation leaves the saved connection.

Tools (with the VM, GitHubTools): ``github_import`` downloads a commit's
tarball and unpacks it in the VM as a git repository with one commit, named
in ``.git/consens-import.json``; ``prepare_pull_request`` reads the changes
against that commit from the VM and saves a proposal on the turn
(``agent_pull_request``, the card under the answer). Nothing goes to GitHub
until the user confirms the card (PullRequests.confirm): the backend reads
the files again, checks them against the preview, and creates blobs, tree,
commit, a new branch and the pull request, never a push to an existing
branch. Without the Workflows permission GitHub refuses changes under
``.github/workflows``; the tool says so before.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import logging
import os
import posixpath
import re
import secrets
import shlex
import tarfile
import time
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.observability import safe_exception
from app.services.agent_tools import ReadOnlyTool

API = "https://api.github.com"
WEB = "https://github.com"
API_VERSION = "2022-11-28"
REQUEST_SECONDS = 30
DOWNLOAD_SECONDS = 120
IMPORT_BYTES = 50 * 1024 * 1024
UNPACK_SECONDS = 180
STATE_MINUTES = 10
# What a connection keeps of GitHub's lists.
MAX_INSTALLATIONS = 10
MAX_REPOSITORIES = 500
PAGE = 100
# A pull request: how much the backend carries from the VM to GitHub.
PR_FILES = 200
PR_FILE_BYTES = 5 * 1024 * 1024
PR_BYTES = 20 * 1024 * 1024
DIFF_CHARS = 12_000
APPROVAL_MINUTES = 60
REPO = r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}$"
REF = r"^[A-Za-z0-9._/-]{1,200}$"
BRANCH = r"^[A-Za-z0-9._/-]{1,100}$"
NAME = r"^[A-Za-z0-9._-]{1,100}$"
REPOS_DIR = "/home/sprite/repos"
IMPORT_RECORD = ".git/consens-import.json"
WORKFLOWS = ".github/workflows/"

NOT_SET_UP = "GitHub is not set up on this installation. Say so; the user cannot connect it yet."
NOT_CONNECTED = ("GitHub is not connected. The user can connect it in Settings, Agent, GitHub, and choose the "
                 "repositories there.")
NO_ACCESS = ("consens.io has no access to {repo} for this user. They can add the repository to the GitHub app "
             "and connect again in Settings, Agent, GitHub.")
NO_PUSH = ("The user may read {repo} but not push to it, so no pull request can come from here. Say so.")
WORKFLOWS_REFUSED = ("This change touches .github/workflows, which consens.io may not change (the GitHub app has no "
                     "Workflows permission). Leave those files out of the pull request.")
UNAVAILABLE = "GitHub is not reachable right now. Try again later."


class GitHubUnavailable(ValueError):
    """What the agent or the user reads when GitHub refused or failed."""

    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


def configuration(env=None):
    """The app's settings, or None while any of the five is missing."""
    env = os.environ if env is None else env
    values = {key: (env.get(f"GITHUB_APP_{key}") or "").strip()
              for key in ("ID", "PRIVATE_KEY", "CLIENT_ID", "CLIENT_SECRET", "SLUG")}
    if not all(values.values()):
        return None
    values["PRIVATE_KEY"] = values["PRIVATE_KEY"].replace("\\n", "\n")
    return values


def configured():
    return configuration() is not None


def now():
    return datetime.now(timezone.utc)


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


class GitHubApp:
    """GitHub's REST API as the app, as one of its installations or as a
    user (``transport``, ``clock`` for tests)."""

    def __init__(self, config=None, *, transport=None, clock=time.time):
        self.config = config or configuration()
        if self.config is None:
            raise GitHubUnavailable(NOT_SET_UP, 503)
        self._clock = clock
        self._http = httpx.Client(timeout=REQUEST_SECONDS, transport=transport, follow_redirects=True,
                                  headers={"Accept": "application/vnd.github+json",
                                           "X-GitHub-Api-Version": API_VERSION,
                                           "User-Agent": "consens.io-agent"})

    def close(self):
        self._http.close()

    def request(self, method, path, *, token=None, auth=None, missing_ok=False, **kwargs):
        url = path if path.startswith("https://") else API + path
        headers = {**(kwargs.pop("headers", None) or {}), **({"Authorization": f"Bearer {token}"} if token else {})}
        try:
            response = self._http.request(method, url, headers=headers, auth=auth, **kwargs)
        except httpx.HTTPError as exc:
            logging.warning("GitHub request failed category=%s", safe_exception(exc))
            raise GitHubUnavailable(UNAVAILABLE, 503) from None
        if missing_ok and response.status_code == 404:
            return None
        if not response.is_success:
            logging.warning("GitHub request refused status=%s", response.status_code)
            message = ""
            try:
                message = str(response.json().get("message") or "")
            except ValueError:
                pass
            if "workflow" in message.lower():
                raise GitHubUnavailable(WORKFLOWS_REFUSED, 409)
            error = GitHubUnavailable(f"GitHub refused the request (HTTP {response.status_code}).", 502)
            error.github_status = response.status_code
            raise error
        return response

    # --- As the app -----------------------------------------------------------

    def app_jwt(self):
        import jwt
        issued = int(self._clock())
        return jwt.encode({"iat": issued - 60, "exp": issued + 540, "iss": self.config["ID"]},
                          self.config["PRIVATE_KEY"], algorithm="RS256")

    def installation_token(self, installation_id, repo, permissions):
        """A token of ``installation_id`` for ``repo`` alone and
        ``permissions`` alone; None when the installation is gone."""
        try:
            response = self.request("POST", f"/app/installations/{int(installation_id)}/access_tokens",
                                    token=self.app_jwt(),
                                    json={"repositories": [repo.split("/", 1)[1]], "permissions": permissions})
        except GitHubUnavailable as exc:
            if getattr(exc, "github_status", None) in (401, 403, 404, 422):
                return None
            raise
        return response.json()["token"]

    # --- As the user (connecting only) ------------------------------------------

    def install_url(self, state):
        return f"{WEB}/apps/{self.config['SLUG']}/installations/new?" + urlencode({"state": state})

    def authorize_url(self, state):
        return f"{WEB}/login/oauth/authorize?" + urlencode({"client_id": self.config["CLIENT_ID"], "state": state})

    def user_token(self, code):
        response = self.request("POST", f"{WEB}/login/oauth/access_token", headers={"Accept": "application/json"},
                                data={"client_id": self.config["CLIENT_ID"],
                                      "client_secret": self.config["CLIENT_SECRET"], "code": code})
        token = response.json().get("access_token") if response is not None else None
        if not token:
            raise GitHubUnavailable("GitHub did not confirm the authorization. Connect again.", 401)
        return token

    def revoke_user_token(self, token):
        """Best effort: the user token was only needed to read the lists."""
        try:
            self.request("DELETE", f"/applications/{self.config['CLIENT_ID']}/token", missing_ok=True,
                         auth=(self.config["CLIENT_ID"], self.config["CLIENT_SECRET"]), json={"access_token": token})
        except GitHubUnavailable:
            logging.info("GitHub user token not revoked")

    def _pages(self, path, key, token, limit):
        items = []
        for page in range(1, limit // PAGE + 2):
            data = self.request("GET", path, token=token, params={"per_page": PAGE, "page": page}).json()
            batch = data.get(key) or []
            items.extend(batch)
            if len(batch) < PAGE or len(items) >= limit:
                break
        return items[:limit]

    def user_installations(self, token):
        """The installations of this app the token's user may access, each
        with its repositories and the user's permissions on them."""
        login = self.request("GET", "/user", token=token).json().get("login") or ""
        installations = []
        for item in self._pages("/user/installations", "installations", token, MAX_INSTALLATIONS):
            if str(item.get("app_id")) != str(self.config["ID"]):
                continue
            repositories = []
            for repo in self._pages(f"/user/installations/{int(item['id'])}/repositories", "repositories", token,
                                    MAX_REPOSITORIES):
                rights = repo.get("permissions") or {}
                if re.fullmatch(REPO, str(repo.get("full_name") or "")) and rights.get("pull"):
                    repositories.append({"full_name": repo["full_name"], "private": bool(repo.get("private")),
                                         "push": bool(rights.get("push"))})
            account = item.get("account") or {}
            installations.append({"id": int(item["id"]), "account": str(account.get("login") or ""),
                                  "repositories": repositories})
        return login, installations


class GitHubConnections:
    """Who may use which repositories through the app (Firestore, per user)."""

    def __init__(self, db, *, app=None):
        from app.services.chat_store import ChatStore
        self.db, self.chats, self._app = db, ChatStore(db), app

    @property
    def app(self):
        if self._app is None:
            self._app = GitHubApp()
        return self._app

    def ref(self, uid):
        return self.db.collection("users").document(uid).collection("github_connections").document("github")

    def state_ref(self, uid, state):
        return self.db.collection("users").document(uid).collection("github_oauth_states").document(sha(state))

    def guard(self, uid, tx=None):
        from app.services import persistence_guard
        persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)

    def public(self, uid):
        """What Settings shows."""
        data = self.ref(uid).get().to_dict() or {}
        installations = data.get("installations") or []
        return {"configured": configured(), "connected": bool(installations), "login": data.get("login") or "",
                "accounts": [item.get("account") for item in installations],
                "repositories": sorted(repo["full_name"] for item in installations for repo in item["repositories"])[:200],
                "manage_url": f"{WEB}/settings/installations"}

    def start(self, uid):
        """``({install, authorize, state}, browser secret)`` for the popup."""
        self.guard(uid)
        state, browser = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        ref = self.state_ref(uid, state)
        data = {"expires_at": (now() + timedelta(minutes=STATE_MINUTES)).isoformat(), "browser_hash": sha(browser)}

        def save(tx):
            self.guard(uid, tx)
            tx.set(ref, data)
        self.chats._transaction(save)
        return {"install_url": self.app.install_url(state), "authorize_url": self.app.authorize_url(state),
                "state": state}, browser

    def finish(self, uid, state, code, browser):
        ref = self.state_ref(uid, state)

        def claim(tx):
            self.guard(uid, tx)
            data = ref.get(transaction=tx).to_dict() or {}
            if (data.get("expires_at", "") <= now().isoformat() or data.get("used")
                    or not secrets.compare_digest(data.get("browser_hash", ""), sha(browser or ""))):
                raise GitHubUnavailable("This GitHub connection was not started in this browser or has expired. "
                                        "Connect again.", 401)
            tx.update(ref, {"used": True})
        self.chats._transaction(claim)
        token = self.app.user_token(code)
        try:
            login, installations = self.app.user_installations(token)
        finally:
            self.app.revoke_user_token(token)
        target = self.ref(uid)

        def save(tx):
            self.guard(uid, tx)
            tx.set(target, {"login": login, "installations": installations, "connected_at": now().isoformat()})
            tx.delete(ref)
        self.chats._transaction(save)
        return self.public(uid)

    def disconnect(self, uid):
        def remove(tx):
            self.guard(uid, tx)
            tx.delete(self.ref(uid))
        self.chats._transaction(remove)
        return {**self.public(uid), "notice": "GitHub disconnected here. To remove the app from your repositories "
                                              "too, uninstall it on GitHub."}

    def access(self, uid, repo, *, push=False):
        """The installation through which ``uid`` may use ``repo``."""
        if not configured():
            raise GitHubUnavailable(NOT_SET_UP, 503)
        data = self.ref(uid).get().to_dict() or {}
        installations = data.get("installations") or []
        if not installations:
            raise GitHubUnavailable(NOT_CONNECTED, 409)
        for item in installations:
            for entry in item.get("repositories") or []:
                if entry.get("full_name", "").lower() == repo.lower():
                    if push and not entry.get("push"):
                        raise GitHubUnavailable(NO_PUSH.format(repo=repo), 403)
                    return int(item["id"]), entry["full_name"]
        raise GitHubUnavailable(NO_ACCESS.format(repo=repo), 403)

    def forget(self, uid, installation_id):
        """An installation GitHub no longer knows leaves the connection."""
        target = self.ref(uid)

        def remove(tx):
            self.guard(uid, tx)
            data = target.get(transaction=tx).to_dict() or {}
            kept = [item for item in data.get("installations") or [] if int(item.get("id", 0)) != int(installation_id)]
            if kept:
                tx.update(target, {"installations": kept})
            elif data:
                tx.delete(target)
        try:
            self.chats._transaction(remove)
        except Exception as exc:
            logging.warning("GitHub installation not forgotten category=%s", safe_exception(exc))

    def token(self, uid, repo, permissions, *, push=False):
        """``(token, repo)``: an installation token for this one operation."""
        installation, name = self.access(uid, repo, push=push)
        token = self.app.installation_token(installation, name, permissions)
        if token is None:
            self.forget(uid, installation)
            raise GitHubUnavailable("GitHub is no longer connected: the app was removed from this repository or "
                                    "account. The user can connect again in Settings, Agent, GitHub.", 409)
        return token, name


# --- Tools ------------------------------------------------------------------------

class GithubImportArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    repo: str = Field(pattern=REPO, description="owner/name")
    ref: str = Field(default="", max_length=200, description="Branch, tag or commit; default the default branch.")
    dest: str = Field(default="", max_length=100, description="Folder name under /home/sprite/repos; default the "
                                                                "repository's name.")


class PreparePullRequestArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str = Field(min_length=1, max_length=1024, description="The repository's folder in the VM, as "
                                                                  "github_import made it.")
    title: str = Field(min_length=1, max_length=256)
    body: str = Field(default="", max_length=20_000, description="The pull request's description.")
    branch: str = Field(default="", max_length=100, description="New branch name; default one is made up.")
    base: str = Field(default="", max_length=200, description="Branch to merge into; default the imported branch.")


def _count_files(raw):
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
            return sum(1 for member in archive if member.isfile())
    except (tarfile.TarError, OSError, EOFError):
        raise GitHubUnavailable("GitHub sent an archive that could not be read.") from None


def unpack_command(archive, dest, repo, ref, sha_):
    """The VM's part: unpack into a new folder (exit 3 if it exists), then
    one commit of what came, with the import named in IMPORT_RECORD."""
    q = shlex.quote
    record = json.dumps({"repo": repo, "ref": ref, "commit": sha_})
    return (f"set -e; dest={q(dest)}; if [ -e \"$dest\" ]; then echo \"$dest already exists\" >&2; exit 3; fi; "
            f"mkdir -p \"$dest\"; tar -xzf {q(archive)} -C \"$dest\" --strip-components=1; rm -f {q(archive)}; "
            "cd \"$dest\"; if command -v git >/dev/null; then git init -q; "
            f"printf '%s\\n' {q(record)} > {IMPORT_RECORD}; git add -A; "
            "git -c user.name=consens.io -c user.email=agent@consens.io commit -q --no-verify "
            f"-m {q(f'consens.io import of {repo}@{sha_[:12]}')}; "
            "else echo 'git is not installed: the files are there without a repository' >&2; fi")


def changes_command(path, commit):
    """Stages everything and lists the changes against the imported commit:
    ``git diff --raw`` and ``--numstat``, NUL-separated, between markers."""
    q = shlex.quote
    return (f"set -e; cd {q(path)}; git add -A; printf 'consens-raw\\0'; "
            f"git diff --cached --no-renames --raw -z {q(commit)}; printf 'consens-numstat\\0'; "
            f"git diff --cached --no-renames --numstat -z {q(commit)}")


def diff_command(path, commit, chars=DIFF_CHARS):
    q = shlex.quote
    return f"cd {q(path)}; git diff --cached --no-renames {q(commit)} | head -c {int(chars) + 1}"


def parse_changes(text):
    """``[{path, change, mode, additions, deletions}]`` of changes_command."""
    raw, _, numstat = text.partition("consens-numstat\0")
    raw = raw.split("consens-raw\0", 1)[-1]
    parts = [part for part in raw.split("\0")]
    files = []
    index = 0
    while index + 1 < len(parts):
        head, path = parts[index], parts[index + 1]
        index += 2
        fields = head.lstrip(":").split()
        if len(fields) < 5 or not path:
            continue
        status = fields[4][:1]
        change = {"A": "added", "D": "deleted"}.get(status, "modified")
        files.append({"path": path, "change": change, "mode": fields[1] if change != "deleted" else fields[0]})
    counts = {}
    for entry in numstat.split("\0"):
        bits = entry.split("\t", 2)
        if len(bits) == 3:
            counts[bits[2]] = (bits[0], bits[1])
    for item in files:
        added, deleted = counts.get(item["path"], ("-", "-"))
        item["additions"] = int(added) if added.isdigit() else None
        item["deletions"] = int(deleted) if deleted.isdigit() else None
    return files


def _slug(text):
    words = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return words[:40].rstrip("-") or "change"


def valid_branch(name):
    return (bool(re.fullmatch(BRANCH, name)) and ".." not in name and not name.startswith(("/", "-"))
            and not name.endswith(("/", ".lock", ".")) and "//" not in name)


class GitHubTools:
    """The GitHub tools of one message, next to its VM tools (VMTools)."""

    def __init__(self, vm_tools, *, connections=None):
        self.vm = vm_tools
        self._connections = connections

    @property
    def connections(self):
        if self._connections is None:
            self._connections = GitHubConnections(self.vm.loop.store.db)
        return self._connections

    def tools(self):
        return [
            ReadOnlyTool("github_import", "Copy a GitHub repository the user connected (a private one too) into "
                         "/home/sprite/repos in your VM, as a git repository with one commit of its state. Returns "
                         "the folder and the commit.", GithubImportArgs, self.import_repo,
                         activity=self._activity, reports=True),
            ReadOnlyTool("prepare_pull_request", "Prepare a pull request from your changes to a repository you "
                         "imported with github_import: the user sees the changes on a card under your answer and "
                         "decides; nothing goes to GitHub before that.", PreparePullRequestArgs, self.prepare,
                         activity=self._pr_activity, reports=True),
        ]

    def _dest(self, args):
        name = (args.dest.strip() or args.repo.split("/", 1)[1]).removesuffix(".git")
        if not re.fullmatch(NAME, name) or name in {".", ".."}:
            raise ValueError("dest must be a plain folder name (letters, digits, . _ -).")
        return f"{REPOS_DIR}/{name}"

    def _app_for_import(self):
        return self.connections.app

    def import_repo(self, args, *, cancellation, report=None):
        from app.services import agent_vm_tools
        report = report or (lambda fields: None)
        if args.ref and (not re.fullmatch(REF, args.ref) or ".." in args.ref):
            raise ValueError("ref must be a branch, tag or commit name.")
        dest = self._dest(args)
        token, repo = self.connections.token(self.vm.loop.uid, args.repo, {"contents": "read"})
        app = self.connections.app
        if args.ref:
            ref = args.ref
        else:
            ref = app.request("GET", f"/repos/{repo}", token=token).json()["default_branch"]
        commit = app.request("GET", f"/repos/{repo}/commits/{ref}", token=token).json()["sha"]
        cancellation.raise_if_cancelled()
        raw = self._tarball(app, repo, commit, token)
        files = _count_files(raw)
        report({"repo": repo, "bytes": len(raw)})
        self.vm._start(cancellation)
        session = self.vm.session
        archive = f"/tmp/consens-import-{commit[:12]}.tar.gz"
        self.vm._provider("write", lambda: session.backend.write_file(session.name, archive, raw))
        said = []
        outcome = self.vm._provider("exec", lambda: session.backend.exec(
            session.name, unpack_command(archive, dest, repo, ref, commit), cwd=agent_vm_tools.HOME,
            timeout=UNPACK_SECONDS, on_output=lambda stream, chunk: said.append(chunk), cancellation=cancellation))
        if outcome.exit_code != 0:
            text = b"".join(said).decode("utf-8", "replace").strip()[-500:]
            if outcome.exit_code == 3:
                raise ValueError(f"{dest} already exists. Import into another folder (dest) or work in that one.")
            raise ValueError(f"Unpacking failed in the VM: {text or 'no output'}")
        return session.announce({"repo": repo, "ref": ref, "commit": commit, "path": dest, "files": files,
                                 "bytes": len(raw)})

    @staticmethod
    def _tarball(app, repo, commit, token):
        data = bytearray()
        try:
            with app._http.stream("GET", f"{API}/repos/{repo}/tarball/{commit}", timeout=DOWNLOAD_SECONDS,
                                  headers={"Authorization": f"Bearer {token}"}) as response:
                if not response.is_success:
                    raise GitHubUnavailable(f"GitHub refused the download (HTTP {response.status_code}).")
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > IMPORT_BYTES:
                        raise GitHubUnavailable(f"The repository is larger than {IMPORT_BYTES // (1024 * 1024)} MB "
                                                "packed. Clone a public one with git in the VM instead.")
        except httpx.HTTPError as exc:
            logging.warning("GitHub download failed category=%s", safe_exception(exc))
            raise GitHubUnavailable(UNAVAILABLE) from None
        return bytes(data)

    def _run(self, command, cancellation, timeout=120):
        from app.services.agent_vm_tools import HOME, _Output
        session = self.vm.session
        output = _Output()
        outcome = self.vm._provider("exec", lambda: session.backend.exec(
            session.name, command, cwd=HOME, timeout=timeout, on_output=output.add, cancellation=cancellation))
        return outcome.exit_code, bytes(output.streams["stdout"]).decode("utf-8", "replace")

    def prepare(self, args, *, cancellation, report=None):
        from app.services import agent_vm
        from app.services.agent_vm_tools import vm_path
        report = report or (lambda fields: None)
        loop = self.vm.loop
        path = vm_path(args.path).rstrip("/")
        self.vm._start(cancellation)
        session = self.vm.session
        try:
            raw, _ = self.vm._provider("read", lambda: session.backend.read_file(
                session.name, f"{path}/{IMPORT_RECORD}", limit=4096))
            record = json.loads(raw.decode("utf-8"))
            repo, imported_ref, commit = record["repo"], record["ref"], record["commit"]
        except (agent_vm.VMFileMissing, ValueError, KeyError, TypeError):
            raise ValueError("A pull request comes only from a repository brought in with github_import: "
                             f"{path} has no {IMPORT_RECORD}.") from None
        if not re.fullmatch(REPO, str(repo)) or not re.fullmatch(r"[0-9a-f]{40}", str(commit)):
            raise ValueError(f"{path}/{IMPORT_RECORD} is not a valid import record.")
        base = args.base.strip() or imported_ref
        if not valid_branch(base):
            raise ValueError("base must be a branch name.")
        token, repo = self.connections.token(loop.uid, repo, {"contents": "read"}, push=True)
        app = self.connections.app
        if app.request("GET", f"/repos/{repo}/branches/{base}", token=token, missing_ok=True) is None:
            raise ValueError(f"{base} is no branch of {repo}. Name the branch to merge into as base.")
        branch = args.branch.strip() or f"consens/{_slug(args.title)}-{secrets.token_hex(2)}"
        if not valid_branch(branch) or branch == base:
            raise ValueError("branch must be a new branch name (letters, digits, . _ - /), not the base.")
        if app.request("GET", f"/repos/{repo}/branches/{branch}", token=token, missing_ok=True) is not None:
            raise ValueError(f"The branch {branch} already exists in {repo}. Choose another name.")
        code, text = self._run(changes_command(path, commit), cancellation)
        if code != 0:
            raise ValueError("git could not list the changes in the VM.")
        files = parse_changes(text)
        if not files:
            raise ValueError(f"There are no changes against the imported commit in {path}.")
        if len(files) > PR_FILES:
            raise ValueError(f"{len(files)} files changed, at most {PR_FILES} go into one pull request. Leave build "
                             "output out (.gitignore) or split the change.")
        if any(item["path"].startswith(WORKFLOWS) for item in files):
            raise ValueError(WORKFLOWS_REFUSED)
        total = 0
        for item in files:
            if item["change"] == "deleted":
                continue
            content = self._read(path, item["path"])
            total += len(content)
            if total > PR_BYTES:
                raise ValueError(f"The changed files are larger than {PR_BYTES // (1024 * 1024)} MB together.")
            item.update(size=len(content), sha256=hashlib.sha256(content).hexdigest())
        _, diff = self._run(diff_command(path, commit), cancellation)
        report({"repo": repo, "files": len(files)})
        proposal = {"id": secrets.token_hex(8), "status": "pending", "repo": repo, "base": base, "branch": branch,
                    "title": " ".join(args.title.split()), "body": args.body.strip(), "path": path,
                    "commit": commit, "files": files, "diff": diff[:DIFF_CHARS],
                    "diff_truncated": len(diff) > DIFF_CHARS, "turn_id": loop.turn_id,
                    "created_at": now().isoformat(),
                    "approval_until": (now() + timedelta(minutes=APPROVAL_MINUTES)).isoformat()}
        proposal["hash"] = digest({key: value for key, value in proposal.items() if key not in {"status", "hash"}})
        self._save(proposal)
        loop.pull_request_proposal = proposal
        return session.announce({"status": "prepared", "repo": repo, "branch": branch, "base": base,
                                 "files": len(files),
                                 "instruction": "The user sees the changes on a card under your answer and creates "
                                                "the pull request there. Nothing went to GitHub yet: never say a pull "
                                                "request exists."})

    def _read(self, path, name):
        from app.services import agent_vm
        session = self.vm.session
        full = posixpath.normpath(f"{path}/{name}")
        if not full.startswith(path + "/"):
            raise ValueError(f"{name} lies outside the repository.")
        try:
            content, complete = self.vm._provider("read", lambda: session.backend.read_file(
                session.name, full, limit=PR_FILE_BYTES + 1))
        except agent_vm.VMFileMissing:
            raise ValueError(f"{name} disappeared while preparing. Prepare again.") from None
        if not complete or len(content) > PR_FILE_BYTES:
            raise ValueError(f"{name} is larger than {PR_FILE_BYTES // (1024 * 1024)} MB.")
        return content

    def _save(self, proposal):
        """On the running turn (``agent_pull_request``), the latest wins."""
        from app.services import persistence_guard
        loop = self.vm.loop
        store = loop.store
        chat_ref = store._chat_ref(loop.uid, loop.chat_id)
        turn_ref = store._turn_ref(loop.uid, loop.chat_id, loop.turn_id)

        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=loop.uid, db=store.db, transaction=tx)
            chat, turn = chat_ref.get(transaction=tx), turn_ref.get(transaction=tx)
            if (not turn.exists or (turn.to_dict() or {}).get("status") != "pending"
                    or not chat.exists or (chat.to_dict() or {}).get("status") != "active"):
                raise ValueError("This answer has already finished. Nothing was prepared.")
            tx.update(turn_ref, {"agent_pull_request": proposal})
        store._transaction(operation)

    def _activity(self, args, result):
        try:
            path = self._dest(args)
        except ValueError:
            path = ""
        return {"path": path, "repo": args.repo, **self.vm._outcome(result)}

    def _pr_activity(self, args, result):
        return {"path": args.path, **self.vm._outcome(result)}


# --- Confirming a pull request ------------------------------------------------------

class PullRequests:
    """The card's two answers to a prepared pull request (routers/agent_github.py)."""

    def __init__(self, db, *, connections=None, vm_factory=None):
        from app.services.agent_runs import AgentRunStore
        self.db, self.store = db, AgentRunStore(db)
        self.connections = connections or GitHubConnections(db)
        self._vm_factory = vm_factory

    def _claim(self, uid, chat_id, turn_id, expected_hash, target):
        from app.services import persistence_guard
        ref = self.store._turn_ref(uid, chat_id, turn_id)

        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            turn = ref.get(transaction=tx).to_dict() or {}
            proposal = turn.get("agent_pull_request")
            if not isinstance(proposal, dict) or proposal.get("hash") != expected_hash:
                raise GitHubUnavailable("This pull request changed. Review the current card.", 409)
            if proposal.get("status") != "pending":
                raise GitHubUnavailable("This pull request was already handled.", 409)
            if target == "executing" and proposal.get("approval_until", "") <= now().isoformat():
                raise GitHubUnavailable("This preview has expired. Ask the agent to prepare the pull request "
                                        "again.", 409)
            proposal = {**proposal, "status": target}
            tx.update(ref, {"agent_pull_request": proposal})
            return proposal
        return self.store._transaction(operation)

    def _finish(self, uid, chat_id, turn_id, patch):
        ref = self.store._turn_ref(uid, chat_id, turn_id)

        def operation(tx):
            turn = ref.get(transaction=tx).to_dict() or {}
            proposal = turn.get("agent_pull_request") or {}
            tx.update(ref, {"agent_pull_request": {**proposal, **patch}})
            return {**proposal, **patch}
        return self.store._transaction(operation)

    def discard(self, uid, chat_id, turn_id, expected_hash):
        return public_proposal(self._claim(uid, chat_id, turn_id, expected_hash, "discarded"))

    def confirm(self, uid, chat_id, turn_id, expected_hash):
        proposal = self._claim(uid, chat_id, turn_id, expected_hash, "executing")
        try:
            result = self._create(uid, chat_id, proposal)
            patch = {"status": "succeeded", "result": result, "error": None}
        except GitHubUnavailable as exc:
            patch = {"status": "failed", "error": str(exc)}
        except ValueError as exc:
            patch = {"status": "failed", "error": str(exc)}
        except Exception as exc:
            logging.warning("GitHub pull request failed category=%s", safe_exception(exc))
            patch = {"status": "failed", "error": "The pull request could not be created. Check the repository on "
                                                  "GitHub before you try again."}
        return public_proposal(self._finish(uid, chat_id, turn_id, patch))

    def _contents(self, uid, chat_id, proposal):
        """The previewed files, read again from the VM and checked against
        the preview: what the user saw is what goes to GitHub."""
        from app.services import agent_vm
        chat = self.store._chat_ref(uid, chat_id).get().to_dict() or {}
        record = chat.get("agent_vm") or {}
        if record.get("name") != agent_vm.vm_name(uid, chat_id):
            raise ValueError("The chat's VM is gone. Prepare the pull request again.")
        vm = (self._vm_factory or agent_vm.backend)()
        if vm is None:
            raise ValueError("The VM is not available right now. Try again later.")
        contents = {}
        try:
            vm.ensure(record["name"])
            for item in proposal["files"]:
                if item["change"] == "deleted":
                    continue
                try:
                    raw, complete = vm.read_file(record["name"], f"{proposal['path']}/{item['path']}",
                                                 limit=PR_FILE_BYTES + 1)
                except agent_vm.VMFileMissing:
                    raw, complete = b"", False
                if not complete or hashlib.sha256(raw).hexdigest() != item.get("sha256"):
                    raise ValueError(f"{item['path']} changed since the preview. Ask the agent to prepare the pull "
                                     "request again.")
                contents[item["path"]] = raw
        except agent_vm.VMUnavailable:
            raise ValueError("The VM is not available right now. Try again later.") from None
        finally:
            vm.close()
        return contents

    def _create(self, uid, chat_id, proposal):
        contents = self._contents(uid, chat_id, proposal)
        token, repo = self.connections.token(uid, proposal["repo"],
                                             {"contents": "write", "pull_requests": "write"}, push=True)
        app = self.connections.app
        tree_base = app.request("GET", f"/repos/{repo}/git/commits/{proposal['commit']}", token=token).json()["tree"]["sha"]
        entries = []
        for item in proposal["files"]:
            mode = item.get("mode") if item.get("mode") in {"100644", "100755", "120000"} else "100644"
            if item["change"] == "deleted":
                entries.append({"path": item["path"], "mode": mode, "type": "blob", "sha": None})
                continue
            blob = app.request("POST", f"/repos/{repo}/git/blobs", token=token, json={
                "content": base64.b64encode(contents[item["path"]]).decode(), "encoding": "base64"}).json()["sha"]
            entries.append({"path": item["path"], "mode": mode, "type": "blob", "sha": blob})
        tree = app.request("POST", f"/repos/{repo}/git/trees", token=token,
                           json={"base_tree": tree_base, "tree": entries}).json()["sha"]
        message = proposal["title"] + (f"\n\n{proposal['body']}" if proposal.get("body") else "")
        commit = app.request("POST", f"/repos/{repo}/git/commits", token=token,
                             json={"message": message, "tree": tree, "parents": [proposal["commit"]]}).json()["sha"]
        app.request("POST", f"/repos/{repo}/git/refs", token=token,
                    json={"ref": f"refs/heads/{proposal['branch']}", "sha": commit})
        pull = app.request("POST", f"/repos/{repo}/pulls", token=token, json={
            "title": proposal["title"], "body": proposal.get("body") or "", "head": proposal["branch"],
            "base": proposal["base"]}).json()
        url = str(pull.get("html_url") or "")
        if not url.startswith(f"{WEB}/"):
            url = f"{WEB}/{repo}/pulls"
        return {"number": pull.get("number"), "url": url, "commit": commit}


PUBLIC_FIELDS = ("id", "status", "repo", "base", "branch", "title", "body", "files", "diff", "diff_truncated", "hash",
                 "approval_until", "result", "error")


def public_proposal(proposal):
    """What the browser gets of a proposal (the card)."""
    return {key: proposal[key] for key in PUBLIC_FIELDS if key in (proposal or {})}
