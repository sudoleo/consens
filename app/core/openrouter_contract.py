"""Dependency-free OpenRouter request facts shared by backend and publisher.

Keep this module free of backend imports, environment loading and client SDKs.
The scheduled publisher runs on stock Python without installed packages.
"""

from __future__ import annotations

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_CHAT_COMPLETIONS_URL = f"{OPENROUTER_BASE_URL}/chat/completions"
OPENROUTER_REFERER = "https://consens.io"
OPENROUTER_TITLE = "consens.io"
DEFAULT_PUBLISHER_TOPIC_MODEL = "gpt-5.6-luna"
REASONING_EFFORT_FOR_PUBLISHER_SCREEN = "low"


def openrouter_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_REFERER,
        "X-Title": OPENROUTER_TITLE,
    }


def publisher_topic_model(value: str | None) -> str:
    """Accept legacy bare OpenAI IDs or fully qualified OpenRouter IDs."""
    model = str(value or "").strip() or DEFAULT_PUBLISHER_TOPIC_MODEL
    return model if "/" in model else f"openai/{model}"
