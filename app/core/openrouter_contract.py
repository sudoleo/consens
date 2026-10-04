"""Dependency-free OpenRouter request facts.

Keep this module free of backend imports, environment loading and client SDKs.
"""

from __future__ import annotations

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_CHAT_COMPLETIONS_URL = f"{OPENROUTER_BASE_URL}/chat/completions"
OPENROUTER_REFERER = "https://consens.io"
OPENROUTER_TITLE = "consens.io"


def openrouter_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_REFERER,
        "X-Title": OPENROUTER_TITLE,
    }

