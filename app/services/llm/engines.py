"""Unified OpenRouter transport for all consens.io model families."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math
from typing import Any

import requests

import app.core.config as cfg
from app.core.openrouter_contract import (
    OPENROUTER_BASE_URL,
    OPENROUTER_CHAT_COMPLETIONS_URL,
    OPENROUTER_REFERER,
    OPENROUTER_TITLE,
    openrouter_headers,
)
from app.core.observability import provider_error_diagnostic, safe_exception
from app.services.llm.attachments import (
    IMAGE_MIMES,
    build_attachment_question_suffix,
    native_attachments_for_provider,
)
from app.services.llm.base import get_system_prompt
from app.services.llm.citations import coerce_text, parse_openrouter_response, result_text
from app.services.llm import completion, usage_meter
from app.services.llm.provider_dispatch import never_reached_provider
from app.services.llm.provider_runtime import PROVIDER_HTTP_TIMEOUT, managed_provider_resource

logger = logging.getLogger(__name__)

# Basis-Modell je Familie aus der Provider-Registry. Der Reasoning-Schalter
# (Wire-Feld ``deep_search``) tauscht seit 2026-10-02 KEIN Modell mehr: er
# laesst dasselbe gewaehlte Modell nur laenger nachdenken.
_DEFAULT_MODEL_BY_PROVIDER = {
    provider.key: provider.base_model for provider in cfg.PROVIDERS.values()
}


# Suchmaschine je Familie. "auto" laesst OpenRouter waehlen und trifft fuer
# fuenf Familien die richtige Wahl. Grok ist die Ausnahme: dort landet "auto"
# auf xAIs nativer Live-Suche, die `max_uses` und `max_results` schlicht
# ignoriert. Gemessen am 2026-08-31, gleiche Frage, je zwei Laeufe:
#
#   grok, engine "auto"  ->  6-11 Quellen, ~66.000 Prompt-Tokens, ~0,10 $, 20 s TTFT
#   grok, engine "exa"   ->     5 Quellen,   ~4.800 Prompt-Tokens, ~0,015 $, 4 s TTFT
#
# Gleiche Antwortlaenge, weniger Quellenflut, ein Viertel der Wartezeit und ein
# Sechstel der Kosten. Fuer die anderen Familien bleibt "auto" richtig: bei
# Gemini schaltet ein erzwungenes "native" die Grounding-Suche ganz ab.
_SEARCH_ENGINE_BY_PROVIDER = {"grok": "exa"}


def web_search_tool(provider: str, *, max_uses: int, **limits) -> dict:
    """One search configuration shared by Consensus and Agent chat."""
    return {"type": "openrouter:web_search", "parameters": {
        "engine": _SEARCH_ENGINE_BY_PROVIDER.get(provider, "auto"),
        "max_uses": max_uses, **limits,
    }}


class _ProviderHTTPStatusError(RuntimeError):
    """Content-free upstream status error for metrics and retry policy."""

    def __init__(self, status_code: int, *, retry_after=None, diagnostic=None):
        super().__init__("upstream provider returned an HTTP error")
        self.status_code = int(status_code)
        self.retry_after = retry_after
        # Allowlisted tokens only (see provider_error_diagnostic), never body text.
        self.safe_diagnostic = diagnostic


class _ProviderResponseError(RuntimeError):
    """An upstream error body/SSE event, possibly inside an HTTP 200 response."""

    def __init__(self, error):
        super().__init__("upstream provider returned an error in the response")
        code = error.get("code") if isinstance(error, dict) else None
        if isinstance(code, str) and len(code) == 3 and code.isascii() and code.isdecimal():
            code = int(code)
        # Retain only HTTP error status metadata, never raw provider details.
        self.status_code = code if type(code) is int and 400 <= code <= 599 else None
        self.safe_diagnostic = provider_error_diagnostic(error)


def _raise_provider_http_status(response, *, body: bytes | None = None) -> None:
    headers = getattr(response, "headers", {})
    delay = _retry_after_seconds(headers.get("Retry-After"))
    diagnostic = None
    if body:
        try:
            parsed = json.loads(body.decode("utf-8", errors="replace"))
        except ValueError:
            parsed = None
        diagnostic = provider_error_diagnostic(parsed.get("error") if isinstance(parsed, dict) else None)
    raise _ProviderHTTPStatusError(int(response.status_code), retry_after=delay, diagnostic=diagnostic)


def _retry_after_seconds(value):
    if not isinstance(value, str) or len(value) > 100:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            seconds = (date - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return None
    return max(1, math.ceil(seconds)) if math.isfinite(seconds) and 0 <= seconds <= 86400 else None


def _error(provider: str, error: Exception | str, *, timeout: bool = False):
    category = safe_exception(error) if isinstance(error, BaseException) else "provider_error"
    error_code = (
        "provider_timeout"
        if timeout
        or (isinstance(error, BaseException) and "timeout" in category.lower())
        or category.endswith(":408")
        or category.endswith(":504")
        else "provider_request_failed"
    )
    logger.error("Provider request failed provider=%s category=%s", provider, category)
    return {
        "text": "",
        "sources": [],
        "error": f"{provider} could not complete this request. Please try again later.",
        "error_code": error_code,
    }


def _merge_nested_config(payload: dict, config: dict | None):
    if not config:
        return
    for key, value in config.items():
        if isinstance(value, dict) and isinstance(payload.get(key), dict):
            _merge_nested_config(payload[key], value)
        else:
            payload[key] = value


def _log_model_selection(
    provider: str,
    api_model: str,
    deep_search: bool,
    model_override: str | None,
) -> None:
    logger.info(
        "Provider model selected: %s -> %s | reasoning=%s | override=%s",
        provider,
        api_model,
        deep_search,
        model_override,
    )


def _openrouter_user_content(question: str, attachments: list[dict]) -> str | list[dict]:
    if not attachments:
        return question
    content: list[dict[str, Any]] = [{"type": "text", "text": question}]
    for attachment in attachments:
        mime = attachment["mime"]
        data_url = f"data:{mime};base64,{attachment['data']}"
        if mime in IMAGE_MIMES:
            content.append({"type": "image_url", "image_url": {"url": data_url}})
        else:
            content.append({
                "type": "file",
                "file": {
                    "filename": attachment["name"],
                    "file_data": data_url,
                },
            })
    return content


def build_provider_payload(
    provider: str,
    *,
    question: str = "dry run",
    system_prompt: str | None = None,
    model_override: str | None = None,
    deep_search: bool = False,
    max_output_tokens: int | None = None,
    attachments: list[dict] | None = None,
    benchmark_mode: bool = False,
) -> dict:
    """Build the one OpenRouter Chat Completions payload used by every family.

    ``deep_search`` is the kept wire name of the Reasoning switch: the same
    model runs with more reasoning (see ``cfg.effective_model_reasoning``) and
    a larger output cap, without a model swap, extra prompt or wider search.
    """
    provider_key = str(provider or "").lower()
    if provider_key not in _DEFAULT_MODEL_BY_PROVIDER:
        raise ValueError(f"Unsupported model family: {provider}")

    system = system_prompt if system_prompt is not None else get_system_prompt()

    default_model = _DEFAULT_MODEL_BY_PROVIDER[provider_key]
    internal_model = model_override or default_model
    api_model, model_config = cfg.resolve_api_model(
        internal_model,
        default_model,
        provider_key,
    )
    max_tokens = int(max_output_tokens) if max_output_tokens is not None else cfg.get_output_token_limit(True, deep_search)

    provider_attachments = native_attachments_for_provider(attachments or [], provider_key)
    fallback_suffix = build_attachment_question_suffix(attachments or [], provider_key)
    if fallback_suffix:
        question = (question or "") + fallback_suffix

    payload = {
        "model": api_model,
        "messages": [
            {"role": "system", "content": system or " "},
            {
                "role": "user",
                "content": _openrouter_user_content(question, provider_attachments),
            },
        ],
        "max_tokens": max_tokens,
        # Privacy policy, not provider pinning: only zero-retention endpoints may run.
        "provider": {"zdr": True},
    }
    if not benchmark_mode:
        max_uses = 1
        payload["tools"] = [web_search_tool(provider_key, max_uses=max_uses)]
        payload["max_tool_calls"] = max_uses + 1

    request_config = dict(model_config.request_config or {})
    reasoning_config, _reasoning_source = cfg.effective_model_reasoning(
        provider_key,
        internal_model,
        reasoning=deep_search,
    )
    if reasoning_config is not None:
        request_config["reasoning"] = reasoning_config
    _merge_nested_config(payload, request_config)

    return {
        "provider": provider_key,
        "endpoint": "chat.completions",
        "internal_model": internal_model,
        "api_model": api_model,
        "is_low_reasoning": bool(model_config.is_low_reasoning) if model_config else False,
        "payload": payload,
    }


def query_model(
    provider: str,
    question: str,
    api_key: str,
    system_prompt: str | None = None,
    deep_search: bool = False,
    model_override: str | None = None,
    max_output_tokens: int | None = None,
    attachments: list[dict] | None = None,
    benchmark_mode: bool = False,
):
    """Run one non-streaming model request through OpenRouter."""
    provider_key = str(provider or "").lower()
    label = cfg.provider_label(provider)
    try:
        request_data = build_provider_payload(
            provider,
            question=question,
            system_prompt=system_prompt,
            model_override=model_override,
            deep_search=deep_search,
            max_output_tokens=max_output_tokens,
            attachments=attachments,
            benchmark_mode=benchmark_mode,
        )
        _log_model_selection(label, request_data["api_model"], deep_search, model_override)
        metered = usage_meter.start_call(request_data["payload"])
        try:
            response = requests.post(
                OPENROUTER_CHAT_COMPLETIONS_URL,
                headers=openrouter_headers(api_key),
                json=request_data["payload"],
                timeout=PROVIDER_HTTP_TIMEOUT,
            )
            with managed_provider_resource(response):
                if response.status_code >= 400:
                    _raise_provider_http_status(response)
                data = response.json()
        except _ProviderHTTPStatusError:
            metered.rejected()
            raise
        except BaseException as exc:
            # A connect failure never reached the provider; anything later
            # (read timeout, cut body, cancellation) is a started call.
            if never_reached_provider(exc):
                metered.rejected()
            else:
                metered.finish()
            raise
        metered.finish(data.get("usage") if isinstance(data, dict) else None)
        if data.get("error"):
            raise _ProviderResponseError(data["error"])
        choice = (data.get("choices") or [{}])[0] or {}
        message = choice.get("message") or {}
        result = parse_openrouter_response(
            coerce_text(message.get("content")),
            message.get("annotations") or data.get("citations") or [],
            provider_key,
        )
        if not result_text(result):
            return {
                "text": "",
                "sources": [],
                "error": "The model returned no answer. Please try again.",
                "error_code": "empty_response",
            }
        # A complete JSON body is a transport confirmation; the finish reason
        # still decides whether the text itself was cut at the token limit.
        result["completion"] = completion.completion_state(
            choice.get("finish_reason"), terminated=True
        )
        if result["completion"] != completion.COMPLETE:
            result["finish_reason"] = str(choice.get("finish_reason") or "")[:40]
        return result
    except Exception as exc:
        return _error(label, exc)
