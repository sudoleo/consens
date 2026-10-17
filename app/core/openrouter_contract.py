"""Dependency-free OpenRouter request facts.

Keep this module free of backend imports, environment loading and client SDKs.
"""

from __future__ import annotations

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_CHAT_COMPLETIONS_URL = f"{OPENROUTER_BASE_URL}/chat/completions"
OPENROUTER_REFERER = "https://consens.io"
OPENROUTER_TITLE = "consens.io"

# Provider routing of every model request (since 2026-10-17): the endpoint
# with the highest measured throughput among those that neither keep prompts
# for training nor otherwise collect them. Zero data retention is no longer
# required in general: under it GPT-6 Luna could only run on Azure, whose
# endpoints answered with up to minutes of delay. A chat with Google data
# adds it back (google_connections.restricted_model).
DEFAULT_PROVIDER_ROUTING = {"sort": "throughput", "data_collection": "deny"}


def provider_routing(overrides: dict | None = None) -> dict:
    """A fresh copy of the default routing, with a model's own settings on top."""
    return {**DEFAULT_PROVIDER_ROUTING, **(overrides or {})}


def openrouter_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_REFERER,
        "X-Title": OPENROUTER_TITLE,
    }

