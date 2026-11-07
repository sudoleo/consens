"""Dependency-free OpenRouter request facts.

Keep this module free of backend imports, environment loading and client SDKs.
"""

from __future__ import annotations

import hashlib

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_CHAT_COMPLETIONS_URL = f"{OPENROUTER_BASE_URL}/chat/completions"
OPENROUTER_REFERER = "https://consens.io"
OPENROUTER_TITLE = "consens.io"

# Provider routing of every model request: the endpoint
# with the highest measured throughput among those that neither keep prompts
# for training nor otherwise collect them. Zero data retention is not
# required in general: under it GPT-6 Luna could only run on Azure, whose
# endpoints answered with up to minutes of delay. A chat with Google data
# adds it back (google_connections.restricted_model).
DEFAULT_PROVIDER_ROUTING = {"sort": "throughput", "data_collection": "deny"}

# Agent requests prefer, among those endpoints, the ones
# that start to answer quickly, and of those the one with the highest
# throughput. Most Agent steps write a tool call or a short answer (about 200
# tokens), so the wait for the first token decides. Throughput alone put
# every step of a GPT-6.1 Terra turn on the endpoint with the slowest start
# (2026-11-05: 3.5 s at p50 and 8.7 s at p90; other endpoints of the same
# model started in 1.3 s, docs/agent-speed-plan-2026-11-05.md). A preference
# only: OpenRouter moves an endpoint over the limit to the end of its list
# and never refuses a request for it. Seconds, measured over five minutes.
AGENT_PREFERRED_MAX_LATENCY = {"p50": 2, "p90": 5}


def provider_routing(overrides: dict | None = None) -> dict:
    """A fresh copy of the default routing, with a model's own settings on top."""
    return {**DEFAULT_PROVIDER_ROUTING, **(overrides or {})}


def agent_provider_routing(overrides: dict | None = None) -> dict:
    """The routing of an Agent request: the default routing preferring
    endpoints that start quickly (AGENT_PREFERRED_MAX_LATENCY), with a
    model's own settings on top."""
    return {**DEFAULT_PROVIDER_ROUTING, "preferred_max_latency": dict(AGENT_PREFERRED_MAX_LATENCY),
            **(overrides or {})}


def provider_session_id(uid: str, chat_id: str, worker_id: str = "") -> str:
    """OpenRouter's session (header ``x-session-id``) for the chat model's
    steps in one chat, or with ``worker_id`` for the requests of one helper
    call of it (DelegationLoop.worker_completion).

    Every Agent step re-sends system prompt, memory and history, and so does
    the chat's next message. Each endpoint caches that prefix only for itself
    (Anthropic, Vertex and Bedrock serve the same Claude model with separate
    caches). Without a session OpenRouter keeps a conversation on one
    endpoint only after it has seen a cache hit there, so the throughput
    sort could send the next step to a cold endpoint and pay the full prefix
    again (2026-10-17: Sonnet wrote the cache in 93 of 134 calls and read it
    in 32). With a session it stays on the endpoint of the first successful
    request, falls back when that one fails, and forgets it after ten idle
    minutes. Opaque on purpose: neither the uid nor the chat id leaves the
    server.
    """
    scope = f"consens.io agent chat\0{uid}\0{chat_id}" + (f"\0worker\0{worker_id}" if worker_id else "")
    return hashlib.sha256(scope.encode("utf-8")).hexdigest()[:32]


def openrouter_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_REFERER,
        "X-Title": OPENROUTER_TITLE,
    }

