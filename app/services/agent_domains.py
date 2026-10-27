"""The workbench's network, per chat (since 2026-10-27, docs/agent-mode.md
"Netz der Werkbank").

The workbench reaches the package registries (agent_vm.WORKBENCH_RULES) and
nothing else. Another domain needs the user: the agent asks with
``request_domain`` (domain, reason), the reviewers judge the request before
the user sees it (a gate round, agent_audit.AnswerAudit.open_gate), and the
user decides on a card (DelegationLoop._domain_wait). Never by itself, also
not when the user named the domain in a message: reading the user's words
for permission would be a text filter again (Max, 2026-10-27).

What the user allowed holds for the chat (``agent_domains`` on the chat
document, gone with it): while the chat's message has the workspace, its
domains are in the workbench's policy (VMSession.ready, applied at once), and
when the message ends the policy goes back to the registries (VMSession.close).
Reading the web goes on through web_search and read_source in the backend;
GitHub only through github_import (github.com stays closed).
"""
from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
import json
import logging
import re

from pydantic import BaseModel, ConfigDict, Field

from app.core.observability import safe_exception
from app.services import agent_vm
from app.services.agent_tools import ReadOnlyTool

CHAT_FIELD = "agent_domains"
MAX_DOMAINS = 20
REASON_CHARS = 300
_LABEL = r"(?!-)[a-z0-9-]{1,63}(?<!-)"
DOMAIN = re.compile(rf"^{_LABEL}(?:\.{_LABEL})+$")
# Never on request: the provider's own network and API, and GitHub, which
# comes in only through github_import.
CLOSED = ("internal", "flycast", "sprites.dev", "sprites.app", "fly.dev", "github.com", "githubusercontent.com")
GITHUB = ("github.com", "githubusercontent.com")

# What the agent reads when the user did not allow it, or wrote instead.
DOMAIN_DENIED = ("The user did not allow {domain} for this chat. Go on without it, and do not ask for it again "
                 "in this message.")


class RequestDomainArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    domain: str = Field(min_length=3, max_length=253, description="One host name, like api.example.com (no "
                        "address, no wildcard).")
    reason: str = Field(min_length=3, max_length=REASON_CHARS, description="What you need it for, in a sentence "
                        "the user reads on the card.")


def normalize(domain):
    """The host name as the policy takes it, or ValueError with what to do."""
    text = str(domain or "").strip().lower().rstrip(".")
    if "://" in text or "/" in text or ":" in text or "*" in text:
        raise ValueError("domain is one host name only, like api.example.com: no scheme, path, port or wildcard.")
    try:
        ipaddress.ip_address(text)
    except ValueError:
        pass
    else:
        raise ValueError("Addresses cannot be allowed, only host names.")
    if not DOMAIN.fullmatch(text):
        raise ValueError(f"{domain} is no valid host name.")
    if any(text == closed or text.endswith("." + closed) for closed in CLOSED):
        if any(text == name or text.endswith("." + name) for name in GITHUB):
            raise ValueError("GitHub stays closed for the workspace: bring repositories in with github_import "
                             "(public ones too).")
        raise ValueError(f"{text} cannot be allowed.")
    return text


def open_already(domain):
    """Whether the registries' rules already let it through."""
    for rule in agent_vm.WORKBENCH_RULES:
        pattern = rule["domain"]
        if domain == pattern or (pattern.startswith("*.") and domain.endswith(pattern[1:])):
            return True
    return False


def granted(chat_data):
    """The domains the user allowed for the chat, in order."""
    items = (chat_data or {}).get(CHAT_FIELD) or []
    names = []
    for item in items if isinstance(items, list) else []:
        name = item.get("domain") if isinstance(item, dict) else None
        if isinstance(name, str) and DOMAIN.fullmatch(name) and name not in names:
            names.append(name)
    return names[:MAX_DOMAINS]


def rules(domains=()):
    """The workbench's policy: the registries and the chat's domains."""
    return [*agent_vm.WORKBENCH_RULES,
            *({"domain": name, "action": "allow"} for name in domains if not open_already(name))]


def grant(store, uid, chat_id, domain, turn_id):
    """The user allowed ``domain`` for the chat: saved on it (transaction,
    the chat still active). Returns the chat's domains now."""
    from app.services import persistence_guard
    from app.services.chat_store import ChatNotFound
    chat = store._chat_ref(uid, chat_id)
    outcome = {}

    def operation(tx):
        persistence_guard.ensure_account_write_allowed(uid=uid, db=store.db, transaction=tx)
        data = chat.get(transaction=tx).to_dict() or {}
        if data.get("status") != "active":
            raise ChatNotFound("Chat not found")
        items = [item for item in (data.get(CHAT_FIELD) or []) if isinstance(item, dict)]
        if domain not in granted(data):
            if len(items) >= MAX_DOMAINS:
                raise ValueError(f"This chat already has {MAX_DOMAINS} allowed domains, the most it takes.")
            items.append({"domain": domain, "turn_id": turn_id,
                          "at": datetime.now(timezone.utc).isoformat()})
            tx.update(chat, {CHAT_FIELD: items})
        outcome["domains"] = granted({CHAT_FIELD: items})
    store._transaction(operation)
    return outcome["domains"]


def requested(call):
    """``(domain, reason)`` of a request_domain call, or None when its
    arguments are not valid (the tool then says why)."""
    function = (call or {}).get("function") or {}
    if function.get("name") != "request_domain":
        return None
    arguments = function.get("arguments")
    try:
        args = RequestDomainArgs.model_validate(json.loads(arguments) if isinstance(arguments, str) else arguments)
        return normalize(args.domain), " ".join(args.reason.split())
    except Exception:
        return None


class DomainTools:
    """request_domain of one message, next to its VM tools (VMTools). The
    loop runs it only after the user allowed the domain on the card
    (DelegationLoop._domain_wait puts it in ``loop.allowed_domains``)."""

    def __init__(self, vm_tools):
        self.vm = vm_tools

    def tools(self):
        return [ReadOnlyTool(
            "request_domain", "Ask the user to let your workspace reach one more domain for this chat, such as an "
            "API your code calls. Your workspace reaches only the package registries (apt, pip, npm) by default. "
            "The user decides on a card; reading web pages works without this (web_search, read_source).",
            RequestDomainArgs, self.request, activity=self._activity)]

    def request(self, args, *, cancellation, report=None):
        loop = self.vm.loop
        domain = normalize(args.domain)
        if open_already(domain):
            return {"domain": domain, "status": "open", "note": "Your workspace reaches it already."}
        if domain not in getattr(loop, "allowed_domains", set()):
            raise ValueError(DOMAIN_DENIED.format(domain=domain))
        domains = grant(loop.store, loop.uid, loop.chat_id, domain, loop.turn_id)
        session = self.vm.session
        with session._lock:
            session.domains = list(domains)
            live = session.state == "ready" and session.leased
        if live:
            try:
                session.backend.set_policy(session.name, rules(domains))
            except Exception as exc:
                # Saved for the chat: its next message has it.
                logging.warning("Agent workbench policy update failed category=%s", safe_exception(exc))
                return {"domain": domain, "status": "allowed",
                        "note": "The user allowed it for this chat; it works from your next message on."}
        return {"domain": domain, "status": "allowed",
                "note": "The user allowed it: your workspace reaches it for the rest of this chat."}

    def _activity(self, args, result):
        try:
            domain = normalize(args.domain)
        except ValueError:
            domain = str(args.domain)[:253]
        fields = {"domain": domain}
        if isinstance(result, dict) and result.get("status") in {"allowed", "open"}:
            fields["domain_status"] = result["status"]
        return fields
