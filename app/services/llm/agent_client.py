"""One provider step. Tool execution, run budgets and persistence live outside."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
import os
import re
from urllib.parse import urlsplit
import uuid

from app.core import config as cfg
from app.core.observability import record_metric
from app.core.openrouter_contract import provider_routing
from app.services.agent_provider_limits import ModelDeclined, ModelEmptyAnswer, ModelOutputLimit
from app.services.agent_costs import provider_cost_nanos, search_cost_nanos, token_cost_nanos
from app.services.llm import agent_model_metadata

from app.services.llm.citations import is_search_result, presearch_end, shift_citation
from app.services.llm.engines import OPENROUTER_CHAT_COMPLETIONS_URL, _ProviderHTTPStatusError, _ProviderResponseError, openrouter_headers
from app.services.llm.provider_dispatch import never_reached_provider
from app.services.llm.provider_runtime import (
    AnalysisBudget, bind_analysis_budget, cancellable_sse_lines, current_analysis_budget,
)
from app.services.llm.streaming import _sse_pairs


@dataclass(frozen=True)
class AgentModel:
    # Claude Sonnet 5.5: in a blind test of 20 questions it ranked first most often and surfaced
    # twice as many contradictions as GPT-6 Luna.
    model: str = "anthropic/claude-sonnet-5.5"
    label: str = "Claude Sonnet 5.5"
    max_output_tokens: int = 4096
    # USD / million tokens. A versioned simulation, not an invoice.
    input_usd_per_million: str = "2.00"
    output_usd_per_million: str = "10.00"
    cache_read_usd_per_million: str = "0.20"
    cache_write_usd_per_million: str = "2.50"
    web_search_usd_per_request: str | None = None
    pricing_version: str = "openrouter-2026-10-07"
    selection_id: str = "claude-sonnet-5.5"
    reasoning_effort: str = "default"
    request_config: dict = field(default_factory=dict)
    context_length: int = 1_000_000

    def snapshot(self):
        return asdict(self)

    def settings(self):
        from app.services.agent_policy import tools_for_model
        return {"model_id": self.selection_id, "model": self.model, "label": self.label,
                "reasoning_effort": self.reasoning_effort,
                "reasoning": self.request_config.get("reasoning", {}),
                "tools": list(tools_for_model(self))}


def agent_model_label() -> str:
    """The default agent model's display name without the price catalog, so the app's first frame
    names the model it really runs on."""
    defaults = AgentModel()
    model_id = os.environ.get("AGENT_MODEL", defaults.model).strip()
    entry = next((entry for entry in cfg.MODEL_CONFIGS.values() if entry.api_model == model_id), None)
    return entry.label if entry else defaults.label if model_id == defaults.model else model_id


def agent_model(*, _metadata=None) -> AgentModel:
    """Operator configuration is explicit; never silently substitute a model."""
    defaults = AgentModel()
    model_id = os.environ.get("AGENT_MODEL", defaults.model).strip()
    metadata = (_metadata if _metadata is not None else agent_model_metadata.snapshot()).get(model_id)
    if not metadata:
        raise ValueError("The configured agent model needs a catalog entry with prices and context limits.")
    entry = next((entry for entry in cfg.MODEL_CONFIGS.values() if entry.api_model == model_id), None)
    pricing = metadata["pricing"]
    defaults = replace(defaults, model=model_id, label=entry.label if entry else defaults.label if model_id == defaults.model else model_id,
        input_usd_per_million=str(Decimal(pricing["prompt"]) * 1_000_000),
        output_usd_per_million=str(Decimal(pricing["completion"]) * 1_000_000),
        cache_read_usd_per_million=str(Decimal(pricing.get("input_cache_read", pricing["prompt"])) * 1_000_000),
        cache_write_usd_per_million=str(Decimal(pricing.get("input_cache_write", pricing["prompt"])) * 1_000_000),
        web_search_usd_per_request=pricing.get("web_search"), pricing_version=metadata.get('_version', _CATALOG['version']))
    values = {}
    for name in ("model", "label", "input_usd_per_million", "output_usd_per_million",
                 "cache_read_usd_per_million", "cache_write_usd_per_million", "pricing_version"):
        values[name] = os.environ.get("AGENT_" + name.upper(), getattr(defaults, name)).strip()
        if not values[name]:
            raise ValueError("Empty agent configuration")
    values["max_output_tokens"] = int(os.environ.get("AGENT_MAX_OUTPUT_TOKENS", "4096"))
    if not 256 <= values["max_output_tokens"] <= 16384:
        raise ValueError("Invalid agent output limit")
    for name in ("input_usd_per_million", "output_usd_per_million", "cache_read_usd_per_million", "cache_write_usd_per_million"):
        price = Decimal(values[name])
        if not price.is_finite() or price < 0 or price > 1000:
            raise ValueError("Invalid agent price")
    values["max_output_tokens"] = min(values["max_output_tokens"], metadata["top_provider"].get("max_completion_tokens") or values["max_output_tokens"])
    # The registry ID, like every other model in the picker: premium and access checks see the ID
    # they know.
    return AgentModel(**values, selection_id=entry.internal_id if entry else values["model"], context_length=metadata["context_length"],
                      web_search_usd_per_request=defaults.web_search_usd_per_request,
                      request_config=dict(entry.request_config or {}) if entry else {})


def default_agent_model_id() -> str:
    """Registry ID of the default chat model (AGENT_MODEL or the code default)."""
    return agent_model().selection_id


_CATALOG = agent_model_metadata.BASELINE
# The answer has no product length cap: it may use the chat model's own completion limit.
ANSWER_OUTPUT_CEILING = 32_768  # about 130 kB of text
ANSWER_OUTPUT_FALLBACK = 32_768
# Reasoning counts against the same allowance, and adaptive thinking (Claude) ignores effort and
# thinking budgets alike: Sonnet 5.5 at "max" used all 32,768 tokens before writing a word. So a
# step that may write the answer gets this much on top.
ANSWER_REASONING_HEADROOM = 32_768
# Routing steps had the same problem: Sonnet 5.5 "max" used about 3,900 of 4,096 tokens in its first
# step. Three times the text allowance on top gives thinking about four times its room while a
# routing reservation stays well below the answer's.
ROUTING_REASONING_HEADROOM = 12_288
# Reasoning for the one retry after a thought-only step, in this order. "low" first, not the
# lightest: a forced Sonnet 5.5 retry at "low" answered in 15 s with the answer's quality intact.
RETRY_EFFORTS = ("low", "minimal", "none")
# Visible reasoning one step stores; beyond it deltas still stream live.
REASONING_STORAGE_CHARS = 32_000
# Longer output is cut and finishes as "length", so a long answer is kept truncated instead of
# failing the step.
TEXT_STORAGE_CHARS = 100_000
# Five sources cut off the evidence of a thorough comparison answer (three search rounds of five
# results).
ANSWER_SOURCES_MAX = 10
# Source text attached to a URL citation (Exa up to 2000, other engines up to about 4000). In memory
# for the source excerpts only, never stored or streamed.
CITATION_CONTENT_CHARS = 4000
# Per call; providers repeat cumulative annotation snapshots.
CITATIONS_MAX = 40
# A response numbers the provider's own calls (web searches) too, so the agent's call may come after
# them.
TOOL_INDEX_BOUND = 64
# Any other field of a step that searched without a URL citation is logged by name.
_KNOWN_CHUNK_FIELDS = frozenset({"id", "object", "created", "model", "provider", "choices", "usage",
                                 "system_fingerprint", "service_tier", "error"})
DECLINED_NATIVE_REASONS = frozenset({"refusal", "content_filter", "safety", "prohibited_content"})


class AgentStreamIncomplete(RuntimeError):
    """The stream ended without an answer or a completed tool call; its log detail never says what
    it said."""
    def __init__(self, diagnostic):
        super().__init__("Agent stream ended without a completed answer")
        self.safe_diagnostic = diagnostic


_KNOWN_CHOICE_FIELDS = frozenset({"index", "delta", "finish_reason", "native_finish_reason", "logprobs", "message"})
_KNOWN_DELTA_FIELDS = frozenset({"role", "content", "reasoning", "reasoning_content", "reasoning_details",
                                 "tool_calls", "annotations", "refusal"})
# OpenAI's own citation marks, private-use characters in the text
# ([E200]cite[E202]turn2search0[E201] or with URLs, sometimes without the closing mark). GPT-6 Luna
# wrote them instead of links, and dropping them dropped the answer's sources: a mark's URLs become
# markdown links, other references and stray characters go.
CITE_OPEN, CITE_CLOSE, CITE_SEP = chr(0xE200), chr(0xE201), chr(0xE202)
CITE_MARK = re.compile(CITE_OPEN + r"[^\s" + CITE_CLOSE + "]*" + CITE_CLOSE + "?|[" + CITE_CLOSE + "-" + chr(0xE2FF) + "]")
# A mark split across chunks waits this long for its end; longer is no mark.
CITE_HOLD_CHARS = 8192


def _cite_links(mark):
    """Markdown links for the URLs of one citation mark; nothing for references without a URL."""
    links = []
    for ref in mark.strip(CITE_OPEN + CITE_CLOSE).split(CITE_SEP):
        try:
            parsed = urlsplit(ref)
            valid = (len(ref) <= 2048 and parsed.scheme in {"https", "http"} and parsed.hostname
                     and not parsed.username and not parsed.password)
        except ValueError:
            valid = False
        if valid:
            host = parsed.hostname[4:] if parsed.hostname.startswith("www.") else parsed.hostname
            link = f"[{host}]({ref.replace('(', '%28').replace(')', '%29')})"
            if link not in links:
                links.append(link)
    return " · ".join(links)


def _metadata(model):
    try:
        return agent_model_metadata.snapshot().get(model.model) or {}
    except Exception:
        return {}


def reasoning_active(model, metadata=None):
    """Whether a request of this model really reasons (and needs headroom): not without catalog
    reasoning, at "none", switched off by the registry, or for a model that reasons only on request."""
    metadata = _metadata(model) if metadata is None else metadata
    catalog = metadata.get("reasoning")
    if not catalog:
        return False
    reasoning = model.request_config.get("reasoning") or {}
    if reasoning.get("effort") == "none" or reasoning.get("enabled") is False:
        return False
    if reasoning.get("effort") or reasoning.get("enabled") is True or reasoning.get("max_tokens"):
        return True
    return catalog.get("default_enabled") is not False


def answer_output_limit(model):
    metadata = _metadata(model)
    limit = int((metadata.get("top_provider") or {}).get("max_completion_tokens") or ANSWER_OUTPUT_FALLBACK)
    allowance = ANSWER_OUTPUT_CEILING
    if reasoning_active(model, metadata):
        allowance += ANSWER_REASONING_HEADROOM
    return max(model.max_output_tokens, min(limit, allowance))


def routing_output_limit(model):
    """The routing step's text allowance plus ROUTING_REASONING_HEADROOM while the model reasons,
    within its own completion limit."""
    metadata = _metadata(model)
    if not reasoning_active(model, metadata):
        return model.max_output_tokens
    allowance = model.max_output_tokens + ROUTING_REASONING_HEADROOM
    limit = int((metadata.get("top_provider") or {}).get("max_completion_tokens") or allowance)
    return max(model.max_output_tokens, min(limit, allowance))


def lighter_reasoning(model):
    """The model at a lighter reasoning level for the one retry after a step that only reasoned, or
    None when none is lighter."""
    metadata = _metadata(model)
    if not metadata.get("reasoning"):
        return None
    choices = _choices(model, metadata)
    current = (model.request_config.get("reasoning") or {}).get("effort")
    ceiling = _EFFORTS.index(current) if current in _EFFORTS else len(_EFFORTS)
    effort = next((effort for effort in RETRY_EFFORTS
                   if effort in choices and _EFFORTS.index(effort) < ceiling), None)
    if effort is None:
        return None
    return _resolve_effort(model, metadata, effort)
_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
REASONING_LEVELS = _EFFORTS
# "default" (the model's own) or one of the levels.
REASONING_EFFORT_PATTERN = rf"^(default|{'|'.join(_EFFORTS)})$"


def _choices(model, metadata):
    reasoning = metadata.get("reasoning") or {}
    efforts = reasoning.get("supported_efforts", [])
    if efforts is None:
        efforts = _EFFORTS
    fixed = model.selection_id.endswith(("-no-reasoning", "-non-reasoning"))
    allowed = [x for x in _EFFORTS if x in efforts and not (x == "none" and reasoning.get("mandatory"))]
    return ["default", *(allowed if not fixed else [])]


def _ordered_entries():
    return [entry for provider in cfg.PROVIDERS
            for model_id in cfg.get_ordered_models(provider)
            if (entry := cfg.get_model_config(model_id, provider)) is not None]


def agent_models(*, _metadata=None):
    """The DB-backed admin model lists and order, without a second allowlist."""
    catalog = _metadata if _metadata is not None else agent_model_metadata.snapshot()
    default = agent_model(_metadata=catalog)
    result = [(default, catalog[default.model])]
    for entry in _ordered_entries():
        metadata = catalog.get(entry.api_model)
        if not metadata or entry.internal_id == default.selection_id:
            continue
        pricing = metadata["pricing"]
        per_million = lambda key, fallback: str(Decimal(pricing.get(key, fallback)) * 1_000_000)
        result.append((AgentModel(
            model=entry.api_model, label=entry.label, selection_id=entry.internal_id,
            max_output_tokens=min(default.max_output_tokens, metadata["top_provider"].get("max_completion_tokens") or default.max_output_tokens),
            input_usd_per_million=per_million("prompt", "0"),
            output_usd_per_million=per_million("completion", "0"),
            cache_read_usd_per_million=per_million("input_cache_read", pricing["prompt"]),
            cache_write_usd_per_million=per_million("input_cache_write", pricing["prompt"]),
            web_search_usd_per_request=pricing.get("web_search"),
            pricing_version=metadata.get('_version', _CATALOG['version']), request_config=dict(entry.request_config or {}),
            context_length=metadata["context_length"],
        ), metadata))
    return result


def _provider_options(model):
    provider = next((p for p in cfg.PROVIDERS.values()
                     if model.model.startswith(p.openrouter_prefix)), None)
    return {"provider": provider.key if provider else "other",
            "provider_label": provider.label if provider else "Other models"}


def agent_model_options():
    from app.services.agent_policy import tools_for_model
    catalog = agent_model_metadata.snapshot()
    options = [
        {"id": model.selection_id, "label": model.label, **_provider_options(model),
         "available": True, "premium": model.selection_id in cfg.PREMIUM_MODELS,
         "early_access": False,
         "reasoning_efforts": _choices(model, metadata),
         "default_reasoning": model.request_config.get("reasoning", metadata.get("reasoning") or {}),
         "reasoning_available": bool(metadata.get("reasoning")),
         # What Auto becomes without Pro (null: the model's own default).
         "free_default_effort": _free_default_effort(model, metadata),
         "tools_by_effort": {effort: list(tools_for_model(model))
                             for effort in _choices(model, metadata)}}
        for model, metadata in agent_models(_metadata=catalog)
    ]
    available = {item['id']: item for item in options}
    default = options[0]
    # Free for every tier even where it is premium elsewhere ("Early access").
    default.update(premium=False, early_access=True)
    # An invalid admin entry stays visible with a reason instead of disappearing or inheriting
    # made-up prices.
    models = [default]
    for entry in _ordered_entries():
        if entry.internal_id == default['id']:
            continue
        models.append(available.get(entry.internal_id) or {
            'id': entry.internal_id, 'label': entry.label, 'provider': entry.provider,
            'provider_label': cfg.PROVIDERS[entry.provider].label,
            'available': False, 'premium': entry.internal_id in cfg.PREMIUM_MODELS, 'unavailable_reason': 'Model information unavailable · check the model ID or retry later',
            'reasoning_efforts': ['default'], 'reasoning_available': False,
        })
    # Saved selections may carry a migrated ID: the browser maps them like resolve_agent_model
    # instead of resetting the user's choice.
    ids = {model['id'] for model in models}
    aliases = {legacy: target for migrations in cfg.PROVIDER_MODEL_MIGRATIONS.values()
               for legacy, target in migrations.items() if target in ids and legacy not in ids}
    return {'default_model_id': default['id'], 'models': models, 'aliases': aliases}


def metered_model(model_id, *, max_tokens=2048):
    entry = cfg.get_model_config(model_id)
    if entry is None:
        raise ValueError("Unknown comparison or judge model")
    metadata = agent_model_metadata.snapshot().get(entry.api_model)
    if not metadata:
        raise ValueError("This model has no metering catalog entry")
    pricing = metadata["pricing"]
    million = lambda key, fallback: str(Decimal(pricing.get(key, fallback)) * 1_000_000)
    return AgentModel(model=entry.api_model, label=entry.label, selection_id=entry.internal_id,
        max_output_tokens=min(max_tokens, metadata["top_provider"].get("max_completion_tokens") or max_tokens),
        input_usd_per_million=million("prompt", "0"), output_usd_per_million=million("completion", "0"),
        cache_read_usd_per_million=million("input_cache_read", pricing["prompt"]),
        cache_write_usd_per_million=million("input_cache_write", pricing["prompt"]),
        context_length=metadata["context_length"], pricing_version=metadata.get('_version', _CATALOG['version']),
        request_config=dict(entry.request_config or {}))


def resolve_agent_model(model_id=None, reasoning_effort="default", *, models=None):
    models = agent_models() if models is None else models
    # A saved chat model may carry a migrated ID.
    wanted = cfg.canonical_model_id(model_id) if model_id else models[0][0].selection_id
    for model, metadata in models:
        # Older clients may still send the default by its OpenRouter ID.
        if wanted not in (model.selection_id, model.model):
            continue
        return _resolve_effort(model, metadata, reasoning_effort)
    if model_id in cfg.MODEL_CONFIGS:
        raise ValueError('Model information is temporarily unavailable. Check the model ID or try again later.')
    raise ValueError("This model is not available in Agent Beta.")


def with_reasoning_summary(model, _metadata=None):
    """OpenAI streams only encrypted reasoning unless a summary is requested: asking adds no
    reasoning, it makes it readable."""
    metadata = (_metadata if _metadata is not None else agent_model_metadata.snapshot()).get(model.model) or {}
    reasoning = dict((model.request_config or {}).get("reasoning") or {})
    if (not model.model.startswith("openai/") or not metadata.get("reasoning")
            or reasoning.get("effort") == "none" or reasoning.get("enabled") is False):
        return model
    return replace(model, request_config={**(model.request_config or {}), "reasoning": {**reasoning, "summary": "auto"}})


# "Auto" sends no level, and some models' own default is a Pro level ("high" for Claude Sonnet 5.5):
# without Pro, Auto means this level.
FREE_DEFAULT_REASONING = "medium"
# The expensive levels are Pro: they multiply thinking tokens.
PRO_REASONING_EFFORTS = frozenset({"high", "xhigh", "max"})


def _free_default_effort(model, metadata):
    """The level Auto stands for without Pro, or None to keep the model default. A pinned low
    setting stays (Auto is the only way to use it); a pinned Pro level becomes Medium."""
    pinned = (model.request_config or {}).get("reasoning") or {}
    if pinned and pinned.get("effort") not in PRO_REASONING_EFFORTS:
        return None
    return FREE_DEFAULT_REASONING if FREE_DEFAULT_REASONING in _choices(model, metadata) else None


def free_default_effort(model_id=None):
    """`_free_default_effort` for a selectable chat model, found like resolve_agent_model finds it
    (migrated IDs included), None if unknown."""
    models = agent_models()
    wanted = cfg.canonical_model_id(model_id) if model_id else models[0][0].selection_id
    for model, metadata in models:
        if wanted in (model.selection_id, model.model):
            return _free_default_effort(model, metadata)
    return None


def _resolve_effort(model, metadata, reasoning_effort):
    if reasoning_effort not in _choices(model, metadata):
        raise ValueError("This reasoning level is not supported by the selected model.")
    config = dict(model.request_config)
    reasoning = dict(config.get("reasoning") or {})
    if reasoning_effort != "default":
        reasoning = {"effort": reasoning_effort}
    if metadata.get("reasoning"):
        reasoning["exclude"] = False
        if model.model.startswith("openai/") and reasoning.get("effort") != "none":
            reasoning["summary"] = "auto"
    if reasoning:
        config["reasoning"] = reasoning
    return replace(model, request_config=config, reasoning_effort=reasoning_effort)


SERVER_TOOL_USAGE_FIELDS = ("server_tool_use_details", "server_tool_use")


def reported_searches(raw: dict):
    """The web searches a usage object reports, unvalidated, or None. Only ``web_search_requests``
    counts: ``tool_calls_executed`` counts every server tool and failed attempts."""
    for field in SERVER_TOOL_USAGE_FIELDS:
        value = raw.get(field)
        if isinstance(value, dict) and "web_search_requests" in value:
            return value["web_search_requests"]
    return None


def measured_usage(raw: object, model: AgentModel, *, searches_enabled=False) -> dict | None:
    """Missing counts are unknown, never estimated or set to zero."""
    if not isinstance(raw, dict):
        return None
    prompt = raw.get("prompt_tokens", raw.get("input_tokens"))
    completion = raw.get("completion_tokens", raw.get("output_tokens"))
    valid = lambda value: type(value) is int and 0 <= value <= 10_000_000
    tokens_known = valid(prompt) and valid(completion)
    cost = provider_cost_nanos(raw.get("cost"))
    if not tokens_known and cost is None:
        return None
    prompt_details = raw.get("prompt_tokens_details", raw.get("input_tokens_details")) or {}
    output_details = raw.get("completion_tokens_details", raw.get("output_tokens_details")) or {}
    cached = prompt_details.get("cached_tokens", 0) if isinstance(prompt_details, dict) else 0
    reasoning = output_details.get("reasoning_tokens", 0) if isinstance(output_details, dict) else 0
    written = prompt_details.get("cache_write_tokens", 0) if isinstance(prompt_details, dict) else 0
    cached = cached if tokens_known and valid(cached) and cached <= prompt else 0
    written = written if tokens_known and valid(written) and written <= prompt - cached else 0
    reasoning = reasoning if tokens_known and valid(reasoning) and reasoning <= completion else 0
    searches = reported_searches(raw)
    searches_known = valid(searches)
    source = "provider" if cost is not None else "catalog"
    cost_complete = tokens_known
    if cost is None:
        cost = token_cost_nanos(model, prompt, completion, cached, written)
        if searches_enabled:
            price = search_cost_nanos(model)
            cost_complete = searches_known and (searches == 0 or price is not None)
            if searches_known and price is not None:
                cost += searches * price
    # Integer nanodollars avoid float drift. Reasoning is already in completion_tokens.
    return {
        "input_tokens": prompt if tokens_known else None, "output_tokens": completion if tokens_known else None,
        "cached_input_tokens": cached if tokens_known else None, "cache_write_tokens": written if tokens_known else None,
        "reasoning_tokens": reasoning if tokens_known else None,
        "web_search_requests": searches if searches_known else None,
        "estimated_cost_nano_usd": cost, "cost_source": source, "complete": tokens_known,
        "cost_complete": source == "provider" or cost_complete,
        "pricing_version": model.pricing_version,
        "source": "provider", "billing_mode": "simulation", "currency": "USD",
    }


_READABLE_FIELDS = {"text": "reasoning.text", "summary": "reasoning.summary"}
# Providers that sign their thinking reject replayed thought text without a signature. Gemini signs
# only its encrypted block, so its text is shown live but not replayed.
_SIGNED_TEXT_FORMATS = {"google-gemini-v1", "anthropic-claude-v1"}


def prompt_cache_control(model):
    """Explicit prompt caching where a provider needs it.

    Anthropic (and Qwen) cache only behind ``cache_control``; the others cache prefixes on their
    own. Every step re-sends system prompt, memory and history, so later steps read them at about a
    tenth of the price as long as they reach the same endpoint. Writing costs a quarter more than
    plain input, so a request nothing continues (a judge) skips the marker unless its own search
    rounds re-read the prompt."""
    name = str(getattr(model, "model", "") or "")
    if name.startswith(("anthropic/", "qwen/")):
        return {"type": "ephemeral"}
    return None


def with_cache_points(messages, cache, history_end=None):
    """``messages`` with ``cache`` on the system prompt and on the chat's last earlier message
    (``history_end``) as breakpoints of their own, or None when neither can carry one.

    The top-level marker sits on the last block, which the chat's next message does not continue
    (the step's tool calls become an answer, the app context changes): without these points it paid
    the write for its whole prompt again. A token is written once whichever breakpoint covers it, so
    the extra points cost nothing on a miss.

    With OpenRouter's search tool in the request only the last breakpoint is cached (measured on
    Vertex): agent steps carry the tool, so their next message reads through the history instead,
    which repeats each question exactly as sent. These points serve requests without the tool (chats
    with Google data)."""
    points = [0] if messages and messages[0].get("role") == "system" else []
    if type(history_end) is int and 0 < history_end < len(messages) - 1:
        points.append(history_end)
    marked = list(messages)
    for index in points:
        content = marked[index].get("content")
        if not isinstance(content, str) or not content:
            continue
        marked[index] = {**marked[index], "content": [{"type": "text", "text": content, "cache_control": cache}]}
    return marked if any(marked[index] is not messages[index] for index in points) else None


# Set once a provider refused a request for its explicit cache points: this process sends none after
# that.
_CACHE_POINTS_REFUSED = False


def _sse_lines(open_lines, payload, fallback=None):
    """The provider's stream for ``payload``. Refused outright (HTTP 400 before any line), it goes
    once more as ``fallback`` without explicit cache points; when that goes through, this process
    stops sending them. A refused request is not billed."""
    global _CACHE_POINTS_REFUSED
    lines = open_lines(payload)
    try:
        try:
            first = next(lines, None)
        except _ProviderHTTPStatusError as exc:
            if fallback is None or exc.status_code != 400:
                raise
            diagnostic = exc.safe_diagnostic
            lines = open_lines(fallback)
            first = next(lines, None)
            _CACHE_POINTS_REFUSED = True
            logging.warning("Provider refused explicit cache points, sending without them model=%s diagnostic=%s",
                            fallback.get("model"), diagnostic)
            record_metric("cache_points_refused", str(fallback.get("model")), outcome="failure")
        if first is None:
            return
        yield first
        yield from lines
    finally:
        lines.close()


def _continues(last, detail):
    kind = detail["type"]
    if kind != last.get("type") or kind not in _READABLE_FIELDS.values():
        return False
    for name in ("index", "id", "format", "signature"):
        mine, theirs = last.get(name), detail.get(name)
        if mine not in (None, "") and theirs not in (None, "") and mine != theirs:
            return False
    return True


def _replayable(detail):
    return not (detail.get("type") == "reasoning.text" and detail.get("format") in _SIGNED_TEXT_FORMATS
                and not detail.get("signature"))


class AgentCompletion:
    """Mutable receipt that survives cancellation and errors after any streamed event."""
    def __init__(self):
        self.text = ""
        self.usage = None
        self.generation_id = ""
        self.finish_reason = ""
        self.activity = []
        self.reasoning_chars = 0
        self.reasoning_truncated = False
        self.step_id = "completion:0"
        self.tool_calls = []
        self.sources = []
        # Per citation: URL, source text and where the answer cites it; transient evidence for the
        # source excerpts.
        self.citations = []
        self._citation_keys = set()
        # Distinct pages a step that searched kept, None for a step without a search.
        self.search_hits = None
        self._shapes = set()
        # Text length when the first search results arrived (_drop_presearch_text).
        self._results_at = None
        # Citation marks: an unfinished one held back, the provider's text length so far and what
        # was removed where.
        self._mark = ""
        self._raw_chars = 0
        self._removed = []
        self._tool_parts = {}
        # The stream index the last call fragment named, and the fragments that named no call of
        # ours.
        self._tool_last = None
        self.skipped_tool_parts = 0
        self._raw_usage = {}
        self._final_usage_fields = set()
        self.tool_argument_limit = 2048
        self.tool_call_limit = 1
        self._reasoning_parts = []
        self._reasoning_text = ""
        self.output_limited = False
        self.native_finish_reason = ""
        self.refusal = False
        # A helper call's own OpenRouter session, and whether no later request re-sends its prompt.
        self.session_id = None
        self.one_off = False
        # Index of the chat's last earlier message, a cache point of its own (with_cache_points).
        self.history_end = None
        # When the request left, its first token arrived and its stream ended (UTC), kept on the
        # receipt: claim to settlement splits into ours, the provider's and ours again.
        self.request_started_at = self.first_token_at = self.stream_ended_at = None
        # Several calls per step; off, the request asks for one call.
        self.parallel_tool_calls = False
        # Calls past tool_call_limit stay without arguments, ids in over_limit_ids, so each gets a
        # result instead of vanishing from the conversation.
        self.keep_over_limit = False
        self._over_limit = set()
        self.over_limit_ids = set()

    def _output_limited(self):
        """The step ended without a usable answer or tool call after reasoning: nothing written, a
        call cut off, or no text after reasoning. The same request would end the same way again."""
        if self.finish_reason == "tool_calls":
            return False
        if self.finish_reason in {"length", "max_tokens"}:
            return bool(self._tool_parts) or not self.text.strip()
        reasoned = bool(self.reasoning_chars or self._reasoning_parts or self._reasoning_text
                        or ((self.usage or {}).get("reasoning_tokens") or 0) > 0)
        return (self.finish_reason in {"stop", ""} and reasoned
                and not self._tool_parts and not self.text.strip())

    def _declined(self):
        """The provider's safety filter ended the step: content_filter, its own refusal reason or a
        refusal text."""
        return (self.refusal or self.finish_reason == "content_filter"
                or self.native_finish_reason.lower() in DECLINED_NATIVE_REASONS)

    def _end_diagnostic(self):
        """How a stream without an answer ended, as log detail (never what it said)."""
        def word(value):
            return re.sub(r"[^A-Za-z0-9.-]", "-", value)[:40] or "none"
        return (f"finish={word(self.finish_reason)} native={word(self.native_finish_reason)} "
                f"text={len(self.text.strip())} tool_parts={len(self._tool_parts)} "
                f"output_tokens={(self.usage or {}).get('output_tokens')}")

    def record_rejection(self, error, model):
        # A rejected admission never opened a generation and an unconnected or undispatched request
        # never reached the provider; timeouts, 5xx and errors inside an accepted stream can still
        # have incurred usage.
        if (self.usage is not None or self.generation_id or self.text
                or self.reasoning_chars or self._tool_parts):
            return
        if (isinstance(error, _ProviderHTTPStatusError)
                and error.status_code in {400, 401, 402, 403, 404, 413, 422, 429}):
            self.record_unstarted(model)
            self.usage["source"] = "provider_rejection"
        elif never_reached_provider(error):
            self.record_unstarted(model)
            self.usage["source"] = "not_dispatched"

    def record_unstarted(self, model):
        self.usage = measured_usage({"prompt_tokens": 0, "completion_tokens": 0, "cost": 0,
                                    "server_tool_use": {"web_search_requests": 0}}, model)
        self.usage["source"] = "not_started"

    def assistant_message(self):
        """Exact provider continuation data; never a public message or stored trace."""
        message = {"role": "assistant", "content": self.text}
        if self.tool_calls:
            message["tool_calls"] = self.tool_calls
        if self._reasoning_parts:
            details = [detail for detail in self._reasoning_parts if _replayable(detail)]
            if details:
                message["reasoning_details"] = details
        elif self._reasoning_text:
            message["reasoning"] = self._reasoning_text
        return message

    def _preserve_reasoning(self, delta):
        """Rebuild provider reasoning blocks from streamed fragments, as OpenRouter's SDK does:
        readable fragments extend the previous block of their kind, encrypted blocks are kept byte
        for byte, never joined. ``index`` alone is no identity: Gemini sends text and signature both
        at index 0."""
        for detail in delta.get("reasoning_details") or []:
            if not isinstance(detail, dict) or not isinstance(detail.get("type"), str):
                continue  # Provider noise must not end an otherwise valid step.
            last = self._reasoning_parts[-1] if self._reasoning_parts else None
            if last is not None and _continues(last, detail):
                for name, value in detail.items():
                    if name in _READABLE_FIELDS and isinstance(value, str):
                        last[name] = last.get(name, "") + value
                    elif value not in (None, "") and last.get(name) in (None, ""):
                        last[name] = value
            else:
                self._reasoning_parts.append(dict(detail))
        text = delta.get("reasoning") or delta.get("reasoning_content")
        if isinstance(text, str):
            self._reasoning_text += text
        if len(json.dumps(self._reasoning_parts)) + len(self._reasoning_text) > 128_000:
            raise ValueError("Reasoning continuation exceeds context limit")

    def event(self, kind, event_id, **data):
        event = {"version": 1, "step_id": self.step_id, "kind": kind, "id": event_id, **data}
        existing = next((item for item in self.activity if item["id"] == event_id), None)
        if existing is None:
            if kind == "reasoning" and len(self.activity) >= 32:
                self.reasoning_truncated = True
                return None
            self.activity.append({k: v for k, v in event.items() if k != "append"})
        elif data.get("append"):
            existing["text"] += data["text"]
        else:
            existing.update(event)
        return {"type": "activity", **event}

    def reasoning_events(self, delta):
        details = delta.get("reasoning_details")
        if not isinstance(details, list) or not details:
            text = delta.get("reasoning") or delta.get("reasoning_content")
            details = [{"type": "reasoning.text", "text": text, "index": 0}] if isinstance(text, str) and text else []
        for index, detail in enumerate(details):
            if not isinstance(detail, dict):
                continue
            kind = detail.get("type")
            text = detail.get("summary" if kind == "reasoning.summary" else "text")
            if kind not in {"reasoning.text", "reasoning.summary"} or not isinstance(text, str) or not text:
                # Encrypted reasoning is not display text and is never persisted.
                continue
            block_id = str(detail.get("index", index))[:40]
            event_id, form = f"{kind}:{block_id}", kind.split(".")[1]
            available = max(0, REASONING_STORAGE_CHARS - self.reasoning_chars)
            self.reasoning_truncated |= len(text) > available
            stored, rest = text[:available], text[available:]
            event = None
            if stored:
                self.reasoning_chars += len(stored)
                event = self.event("reasoning", event_id, format=form, text=stored, append=True)
                if event:
                    yield event
            unstored = rest if event else text
            if unstored:
                # Past the stored bound the model keeps thinking for minutes: live progress sees
                # every delta, nothing more is stored.
                yield {"type": "activity", "version": 1, "step_id": self.step_id, "kind": "reasoning",
                       "id": event_id, "format": form, "text": unstored, "append": True, "transient": True}

    def _tool_delta(self, raw):
        """Collect the call fragments of one chunk; no fragment fails the step. One that names no
        call of ours is skipped; a field past its limit keeps one character more, so the registry
        refuses it with its limit and the model reads why. Any index below TOOL_INDEX_BOUND names a
        call: the provider's own searches count in the numbering, and after four of them the agent's
        call arrived as index 5."""
        if not isinstance(raw, list):
            self.skipped_tool_parts += 1
            return
        for part in raw:
            if not isinstance(part, dict):
                self.skipped_tool_parts += 1
                continue
            index = part.get("index")
            if index is None:
                # A fragment without an index continues the call before it.
                index = 0 if self._tool_last is None else self._tool_last
            if (type(index) is not int or not 0 <= index < TOOL_INDEX_BOUND
                    or (part.get("type") or "function") != "function"):
                self.skipped_tool_parts += 1
                continue
            target = self._tool_parts.get(index)
            if target is None:
                if len(self._tool_parts) - len(self._over_limit) >= self.tool_call_limit:
                    if not self.keep_over_limit:
                        self.skipped_tool_parts += 1
                        continue
                    self._over_limit.add(index)
                target = self._tool_parts[index] = {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
            self._tool_last = index
            function = part.get("function") if isinstance(part.get("function"), dict) else {}
            # A call past the limit keeps its id and name, never its arguments.
            argument_limit = -1 if index in self._over_limit else self.tool_argument_limit
            for key, source, output, limit in (("id", part, target, 160), ("name", function, target["function"], 64),
                                                ("arguments", function, target["function"], argument_limit)):
                fragment = source.get(key)
                if key == "arguments" and isinstance(fragment, (dict, list)):
                    # Arguments sent as an object instead of JSON text.
                    fragment = json.dumps(fragment, ensure_ascii=False)
                if not isinstance(fragment, str) or not fragment:
                    continue
                room = limit + 1 - len(output[key])
                if room > 0:
                    output[key] += fragment[:room]

    def _completed_tool_calls(self):
        """The step's calls in stream order, each with an id a provider takes back: an id with other
        characters, too long or missing is renamed, the same way in its tool result."""
        calls, seen = [], set()
        self.over_limit_ids = set()
        for number, index in enumerate(sorted(self._tool_parts)):
            call = self._tool_parts[index]
            ident = re.sub(r"[^A-Za-z0-9_-]", "_", call["id"])[:64]
            if not ident or ident in seen:
                ident = f"call_{number}_{uuid.uuid4().hex[:12]}"
            seen.add(ident)
            if index in self._over_limit:
                # Not run: an empty object, valid for every provider.
                self.over_limit_ids.add(ident)
                call = {**call, "function": {**call["function"], "arguments": "{}"}}
            calls.append({**call, "id": ident})
        return calls

    def _annotations(self, raw, before):
        """URL citations of one chunk; ``before`` is the text length ahead of its own text."""
        if not isinstance(raw, list):
            return
        for annotation in raw[:20]:
            value = annotation.get("url_citation") if isinstance(annotation, dict) else None
            if not isinstance(value, dict):
                continue
            url = value.get("url")
            if not isinstance(url, str) or len(url) > 2048 or any(c.isspace() or ord(c) < 32 for c in url):
                continue
            try:
                parsed = urlsplit(url)
                valid = parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username and not parsed.password
            except ValueError:
                valid = False
            if not valid:
                continue
            if self._results_at is None and is_search_result(value):
                self._results_at = before
            known = any(s["url"] == url for s in self.sources)
            if not known and len(self.sources) < ANSWER_SOURCES_MAX:
                title = value.get("title")
                self.sources.append({"url": url, "title": title[:200] if isinstance(title, str) else parsed.hostname})
                known = True
            if known:
                self._citation(url, value)

    def _visible(self, chunk, *, final=False):
        """``chunk`` with citation marks turned into links. A mark still open at its end waits for
        the next chunk; ``final`` releases what is held. Replaced spans are kept in provider
        positions for the citation offsets."""
        text = self._mark + chunk
        start = self._raw_chars - len(self._mark)
        self._raw_chars += len(chunk)
        self._mark = ""
        if text.isascii():
            return text
        opened = text.rfind(CITE_OPEN)
        if not final and opened >= 0:
            tail = text[opened:]
            if CITE_CLOSE not in tail and not any(c.isspace() for c in tail) and len(tail) < CITE_HOLD_CHARS:
                self._mark, text = tail, text[:opened]
        parts, last = [], 0
        for match in CITE_MARK.finditer(text):
            links = _cite_links(match.group(0))
            parts += [text[last:match.start()], links]
            self._removed.append((start + match.start(), match.end() - match.start(), len(links)))
            last = match.end()
        parts.append(text[last:])
        return "".join(parts)

    def _shown_index(self, index):
        """A provider text position in the shown text: replaced marks no longer count, their links
        do."""
        shown = index
        for at, length, added in self._removed:
            if index >= at + length:
                shown += added - length
            elif index > at:
                shown += min(added, index - at) - (index - at)
        return shown

    def _citation(self, url, value):
        """Keep where the answer cites ``url`` and its source text. Some adapters send 0/0 offsets:
        the text length so far is the fallback anchor. Provider offsets count removed citation marks
        and are moved."""
        def offset(name):
            number = value.get(name)
            return self._shown_index(number) if type(number) is int and number >= 0 else None
        key = (url, offset("start_index"), offset("end_index"))
        if key in self._citation_keys or len(self.citations) >= CITATIONS_MAX:
            # Repeated cumulative snapshots: the first is closest to its claim.
            return
        self._citation_keys.add(key)
        content = value.get("content")
        self.citations.append({"url": url, "content": content[:CITATION_CONTENT_CHARS] if isinstance(content, str) else "",
                               "start_index": key[1], "end_index": key[2], "fallback_end_index": len(self.text)})

    def _drop_presearch_text(self, model):
        """Drop what the model wrote before its first search results: Claude announces its
        server-side search and OpenRouter joins that text to the answer. Text and citation offsets
        move together. Text the user already saw as the answer stays (``published``), or an answer
        that searched midway lost its opening."""
        if getattr(self, "published", ""):
            self._results_at = None
            return
        cut = presearch_end(self.text, self._results_at)
        self._results_at = None
        if cut:
            self.text = self.text[cut:]
            self.citations = [shift_citation(citation, cut) for citation in self.citations]
            record_metric("presearch_text", model.model, processed=cut)

    def _record_search_overrun(self, model, limit):
        """Count searches beyond the requested limit, per model: OpenRouter does not enforce
        ``max_uses`` for every search (Claude Haiku 4.5 searched 2-3 times at a limit of 1). They
        ran and are paid; usage books the real count."""
        count = (self.usage or {}).get("web_search_requests")
        if limit and type(count) is int and count > limit:
            record_metric("search_overrun", model.model, processed=count - limit)

    def _note_shapes(self, data, choice, delta):
        """Field names of a chunk beyond the known ones and its annotation kinds: where a provider's
        hits arrive when they are not URL citations. Names only, never values."""
        shapes = self._shapes
        if len(shapes) >= 40:
            return
        shapes.update(f"chunk.{key}" for key in data if key not in _KNOWN_CHUNK_FIELDS)
        shapes.update(f"choice.{key}" for key in choice if key not in _KNOWN_CHOICE_FIELDS)
        shapes.update(f"delta.{key}" for key in delta if key not in _KNOWN_DELTA_FIELDS)
        for where, raw in (("delta", delta.get("annotations")), ("message", (choice.get("message") or {}).get("annotations"))):
            for annotation in raw[:5] if isinstance(raw, list) else []:
                if isinstance(annotation, dict):
                    shapes.add(f"{where}.annotation:{str(annotation.get('type'))[:40]}:{','.join(sorted(annotation)[:8])}")

    def _record_missing_citations(self, model):
        """A step that searched but kept no hit (GPT-6 Luna in every logged step) has nothing of the
        search for its sources or reviewers: logged with the chunk shapes seen, never failing the
        step. Every searching step counts as ``search_step`` with its ``search_hits`` for the
        receipt."""
        count = (self.usage or {}).get("web_search_requests")
        if type(count) is int and count > 0:
            self.search_hits = len({source.get("url") for source in self.sources}
                                   | {citation.get("url") for citation in self.citations})
            record_metric("search_step", model.model, processed=count)
        if type(count) is int and count > 0 and not self.sources and not self.citations:
            record_metric("search_without_citations", model.model, processed=count)
            logging.warning("Agent search without citations model=%s searches=%s shapes=%s",
                            model.model, count, ";".join(sorted(self._shapes))[:1500])

    def stream(self, *, model: AgentModel, messages: list[dict], api_key: str, tools=None,
               native_searches=0, allow_tool_calls=False, prompt_cache=True, session_id=None, tool_choice=None):
        """``session_id`` keeps the request on the endpoint of the chat's earlier steps; without one
        a helper keeps its own. ``allow_tool_calls=False``: the step may only write and its calls
        are dropped. The agent's steps send tool_choice "auto" in every step, since Anthropic's
        cached prefix includes it; with it, a reply of dropped calls alone ends as ``tool_calls``
        without text for the caller's retry."""
        session_id = session_id or self.session_id
        payload = {
            "model": model.model, "messages": messages,
            "max_tokens": model.max_output_tokens,
            "stream": True, "stream_options": {"include_usage": True},
        }
        payload.update({k: v for k, v in model.request_config.items() if k != "provider" and not k.startswith("_agent_")})
        payload.update(model=model.model, messages=messages, max_tokens=model.max_output_tokens,
                       stream=True, stream_options={"include_usage": True})
        # Fastest endpoint without prompt collection; the registry may pin a host, a chat with
        # Google data adds zero data retention.
        payload["provider"] = provider_routing(model.request_config.get("provider"))
        # Execution fields are owned by this adapter, never model arguments, user settings or
        # registry configuration.
        for field in ("tools", "tool_choice", "plugins", "parallel_tool_calls", "max_tool_calls", "stop_server_tools_when",
                      "session_id"):
            payload.pop(field, None)
        headers = openrouter_headers(api_key)
        if session_id:
            # A header can never make a request invalid.
            headers["x-session-id"] = session_id
        if any(isinstance(m.get("content"), list) and any(b.get("type") == "file" for b in m["content"]) for m in messages):
            payload["plugins"] = [{"id": "file-parser", "pdf": {"engine": "native"}}]
        if tools:
            payload["tools"] = tools
            if any(tool.get("type") == "function" for tool in tools):
                payload["tool_choice"] = tool_choice or ("auto" if allow_tool_calls or native_searches else "none")
                # Part of Anthropic's tool_choice: a change rewrites the cached messages.
                payload["parallel_tool_calls"] = bool(self.parallel_tool_calls)
        if native_searches:
            payload["max_tool_calls"] = native_searches
        # Cached for requests that read the prompt again: next steps and messages, retries and this
        # request's own search rounds. A one-off call without search would only pay the write.
        cache = prompt_cache_control(model) if prompt_cache and (native_searches or not self.one_off) else None
        fallback = None
        if cache:
            payload["cache_control"] = cache
            marked = None if _CACHE_POINTS_REFUSED else with_cache_points(messages, cache, self.history_end)
            if marked is not None:
                fallback, payload = payload, {**payload, "messages": marked}
        from app.services.llm.provider_runtime import ProviderProgressWatchdog, _bounded_env_float
        progress = ProviderProgressWatchdog(_bounded_env_float("AGENT_PROVIDER_STALL_SECONDS", 180, 30, 600))
        with bind_analysis_budget(current_analysis_budget() or AnalysisBudget(seconds=180, max_calls=1)):
            self.request_started_at = datetime.now(timezone.utc)
            lines = _sse_lines(
                lambda body: cancellable_sse_lines(OPENROUTER_CHAT_COMPLETIONS_URL, json=body,
                                                   headers=headers, progress=progress),
                payload, fallback,
            )
            text_capped = False
            try:
                for _, encoded in _sse_pairs(lines):
                    if len(encoded) > 256_000:
                        raise ValueError("Provider event exceeds limit")
                    if encoded.strip() == "[DONE]":
                        break
                    data = json.loads(encoded)
                    if not isinstance(data, dict):
                        continue
                    # Comments, repeated counters and empty deltas only prove the socket is alive;
                    # they cannot renew admission forever.
                    if any(any((choice.get("delta") or {}).get(key) for key in
                               ("content", "reasoning", "reasoning_content", "reasoning_details", "tool_calls"))
                           or (choice.get("finish_reason") and not self.finish_reason)
                           for choice in data.get("choices") or []):
                        progress.touch()
                        if self.first_token_at is None:
                            self.first_token_at = datetime.now(timezone.utc)
                    self.generation_id = str(data.get("id") or self.generation_id)[:200]
                    terminal = self.finish_reason or any(choice.get("finish_reason") for choice in data.get("choices") or [])
                    reported = data.get("usage")
                    if isinstance(reported, dict):
                        if any(type(reported.get(key)) is int and reported[key] > self._raw_usage.get(key, -1)
                               for key in ("prompt_tokens", "completion_tokens", "input_tokens", "output_tokens")
                               if type(self._raw_usage.get(key, -1)) is int):
                            progress.touch()
                        if terminal:
                            self._final_usage_fields.update(reported)
                        for field in ("prompt_tokens", "completion_tokens", "prompt_tokens_details", "completion_tokens_details",
                                      "input_tokens", "output_tokens", "input_tokens_details", "output_tokens_details", "cost"):
                            if field in reported:
                                if field.endswith("_details") and isinstance(reported[field], dict):
                                    previous = self._raw_usage.get(field)
                                    self._raw_usage[field] = {**(previous if isinstance(previous, dict) else {}), **reported[field]}
                                else:
                                    self._raw_usage[field] = reported[field]
                        for field in SERVER_TOOL_USAGE_FIELDS:
                            server_use = reported.get(field)
                            if isinstance(server_use, dict) and "web_search_requests" in server_use:
                                self._raw_usage[field] = {"web_search_requests": server_use["web_search_requests"]}
                    usage = measured_usage(self._raw_usage, model, searches_enabled=bool(native_searches)) if isinstance(reported, dict) else None
                    if native_searches and isinstance(reported, dict):
                        count = reported_searches(self._raw_usage)
                        known = type(count) is int and 0 <= count <= 10_000
                        if usage is None and known:
                            # Search cost can be known even if token usage is not.
                            price = search_cost_nanos(model)
                            usage = {"input_tokens": None, "output_tokens": None, "cached_input_tokens": None,
                                     "reasoning_tokens": None, "estimated_cost_nano_usd": count * price if price is not None else None,
                                     "web_search_requests": count, "complete": False, "cost_source": "catalog",
                                     "pricing_version": model.pricing_version, "source": "provider",
                                     "billing_mode": "simulation", "currency": "USD"}
                    if usage is not None:
                        # Cumulative telemetry before the terminal choice is a lower bound, not a
                        # final receipt.
                        final_tokens = (bool(self._final_usage_fields & {"prompt_tokens", "input_tokens"})
                                        and bool(self._final_usage_fields & {"completion_tokens", "output_tokens"}))
                        if not final_tokens:
                            usage.update(provisional=True, complete=False)
                        if (not terminal or (usage.get("cost_source") == "provider" and "cost" not in self._final_usage_fields)
                                or (usage.get("cost_source") == "catalog" and not final_tokens)):
                            usage["cost_complete"] = False
                        self.usage = usage
                        yield self.event("usage", "usage", usage=usage)
                    if data.get("error"):
                        raise _ProviderResponseError(data["error"])
                    for choice in data.get("choices") or []:
                        if not isinstance(choice, dict) or choice.get("index", 0) != 0:
                            # One completion was asked for; another is not this step's.
                            continue
                        delta = choice.get("delta") or {}
                        before = len(self.text)
                        if allow_tool_calls:
                            self._preserve_reasoning(delta)
                        if delta.get("tool_calls"):
                            if allow_tool_calls:
                                calling = bool(self._tool_parts)
                                self._tool_delta(delta["tool_calls"])
                                if self._tool_parts and not calling:
                                    # Text before it is no answer: the loop moves it into the
                                    # timeline.
                                    yield self.event("status", "tool_call", status="working")
                            else:
                                # A step that may only write and calls anyway: the call is not run,
                                # its text stands.
                                self.skipped_tool_parts += 1
                        yield from self.reasoning_events(delta)
                        chunk = delta.get("content")
                        if isinstance(chunk, str) and chunk:
                            chunk = self._visible(chunk)
                        if isinstance(chunk, str) and chunk and len(self.text) >= TEXT_STORAGE_CHARS:
                            # Beyond the storage limit: keep reading for usage and cost, but end the
                            # answer as truncated.
                            text_capped = True
                        elif isinstance(chunk, str) and chunk:
                            if not self.text:
                                yield self.event("status", "responding", status="responding")
                            if len(self.text) + len(chunk) > TEXT_STORAGE_CHARS:
                                chunk, text_capped = chunk[:TEXT_STORAGE_CHARS - len(self.text)], True
                            self.text += chunk
                            yield {"type": "delta", "text": chunk}
                        # After the text of the same chunk: a citation's position includes the claim
                        # it arrived with.
                        self._annotations(delta.get("annotations"), before)
                        self._annotations((choice.get("message") or {}).get("annotations"), before)
                        if native_searches:
                            self._note_shapes(data, choice, delta)
                        if delta.get("refusal") or (choice.get("message") or {}).get("refusal"):
                            self.refusal = True
                        if isinstance(choice.get("native_finish_reason"), str) and choice["native_finish_reason"]:
                            self.native_finish_reason = choice["native_finish_reason"][:40]
                        if choice.get("finish_reason"):
                            self.finish_reason = str(choice["finish_reason"])
                # A mark still held ends with the stream (Luna writes URL-only marks without a
                # closing mark).
                rest = self._visible("", final=True)
                if rest and not text_capped:
                    self.text += rest
                    yield {"type": "delta", "text": rest}
                self._drop_presearch_text(model)
                if text_capped and self.finish_reason == "stop":
                    self.finish_reason = "length"
                if allow_tool_calls and self._tool_parts and self.finish_reason in {"tool_calls", "stop", "function_call"}:
                    # Some providers end calls with "stop" instead of "tool_calls".
                    self.finish_reason = "tool_calls"
                    self.tool_calls = self._completed_tool_calls()
                    if self.over_limit_ids:
                        logging.info("Agent calls past the step's limit model=%s step=%s count=%s limit=%s",
                                     model.model, self.step_id, len(self.over_limit_ids), self.tool_call_limit)
                elif not allow_tool_calls and self.finish_reason == "tool_calls" and self.text.strip():
                    # A call it may not make: its text is the answer.
                    self.finish_reason = "stop"
                calls_only = (tool_choice == "auto" and not allow_tool_calls and self.skipped_tool_parts
                              and not self.text.strip())
                if calls_only:
                    self.finish_reason = "tool_calls"
                if self.skipped_tool_parts:
                    logging.warning("Agent tool call fragments skipped model=%s step=%s count=%s kept=%s",
                                    model.model, self.step_id, self.skipped_tool_parts, len(self.tool_calls or []))
                if not self.tool_calls and not self.text.strip() and self._declined():
                    raise ModelDeclined()
                if not self.tool_calls and self._output_limited():
                    # The whole allowance went into reasoning, or reasoning and a cut call: the same
                    # request would end the same way. A stop without a word after reasoning is
                    # chance instead (ModelEmptyAnswer).
                    self.output_limited = True
                    raise (ModelOutputLimit() if self.finish_reason in {"length", "max_tokens"}
                           else ModelEmptyAnswer())
                if not self.tool_calls and not calls_only and (
                        self._tool_parts or self.finish_reason not in {"stop", "length"} or not self.text.strip()):
                    raise AgentStreamIncomplete(self._end_diagnostic())
            finally:
                lines.close()
                self.stream_ended_at = datetime.now(timezone.utc)
                # Also the partial text of a stream that broke off.
                self._drop_presearch_text(model)
                self._record_search_overrun(model, native_searches)
                if native_searches:
                    self._record_missing_citations(model)
