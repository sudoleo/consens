from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo
from fastapi import HTTPException
import app.core.config as cfg

def get_date_context() -> str:
    """Fresh server-owned clock; Berlin is a reference, not user geolocation."""
    now = datetime.now(ZoneInfo("Europe/Berlin"))
    weekday = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")[now.weekday()]
    offset = now.strftime("%z")
    return (
        f"Current date: {weekday}, {now.date().isoformat()}. "
        f"Reference time at request start: {now:%H:%M:%S}. "
        f"Reference timezone: Europe/Berlin (UTC{offset[:3]}:{offset[3:]}). "
        "Resolve relative dates such as today, tomorrow, and yesterday using this date, "
        "not dates in earlier messages, unless the user specifies another reference date or timezone. "
        "This reference timezone is an application default. The user's location and local "
        "timezone are unknown unless provided."
    )


def get_system_prompt() -> str:
    return (
        f"{get_date_context()}\n\n"
        "Please answer thoroughly and precisely, explaining your reasoning and covering the relevant details. Do not oversimplify. No follow-up questions."
    )

FOLLOWUP_CONTEXT_HEADER = "PREVIOUS EXCHANGE (context for a follow-up question):"


def build_followup_system_prompt(base_prompt: str, previous_question: str, previous_consensus: str) -> str:
    """Injiziert genau eine vorherige Frage/Konsens-Ebene vor den System-Prompt.
    Als Kontext geht bewusst nur der Konsens-Text mit, nicht die einzelnen
    Modellantworten (Kostenkontrolle)."""
    return (
        f"{FOLLOWUP_CONTEXT_HEADER}\n"
        f"Previous question: {previous_question}\n"
        f"Consensus answer to the previous question:\n{previous_consensus}\n"
        "END OF PREVIOUS EXCHANGE.\n\n"
        "INSTRUCTIONS:\n"
        "The user's current question is a follow-up to the exchange above. Resolve references "
        "(such as 'it', 'that approach', 'the second option') against that exchange and stay "
        "consistent with it, but answer the current question directly and on its own merits.\n\n"
        f"{base_prompt}"
    )


def count_words(text: Optional[str]) -> int:
    return len((text or "").strip().split())

def validate_model(model: str, allowed: set, provider: str, is_pro: bool = False):
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
