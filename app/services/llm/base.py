from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo
from fastapi import HTTPException
import app.core.config as cfg
from app.services import prompt_config

def get_date_context(timezone_name=None) -> str:
    """Fresh server-owned clock; the configured zone is not user geolocation."""
    timezone_name = timezone_name or prompt_config.get_config()["reference_timezone"]
    now = datetime.now(ZoneInfo(timezone_name))
    weekday = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")[now.weekday()]
    offset = now.strftime("%z")
    return (
        f"Current date: {weekday}, {now.date().isoformat()}. "
        f"Reference time at request start: {now:%H:%M:%S}. "
        f"Reference timezone: {timezone_name} (UTC{offset[:3]}:{offset[3:]}). "
        "Resolve relative dates such as today, tomorrow, and yesterday using this date, "
        "not dates in earlier messages, unless the user specifies another reference date or timezone. "
        "This reference timezone is an application default. The user's location and local "
        "timezone are unknown unless provided."
    )


def get_system_prompt() -> str:
    config = prompt_config.get_config()
    return f"{get_date_context(config['reference_timezone'])}\n\n{config['prompts']['answers']}"

def count_words(text: Optional[str]) -> int:
    return len((text or "").strip().split())

def validate_model(model: str, allowed: set, provider: str, is_pro: bool = False):
    # Checks the current form of a migrated ID (grok-4.3-no-reasoning ->
    # grok-4.3, 2026-10-11); the request itself resolves it the same way.
    model = cfg.canonical_model_id(model) if model else model
    if model and model not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model}' is not allowed for {provider}."
        )

    model_config = cfg.get_model_config(model)
    is_pro_only = (
        model in cfg.PREMIUM_MODELS
        and not (model_config and model_config.is_free)
    )
    if is_pro_only and not is_pro:
        raise HTTPException(
            status_code=403,
            detail=(
                f"The model '{model}' is off for this account because it costs a multiple "
                "of a normal run. Pick another model, or use your own API keys."
            )
        )
