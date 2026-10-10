"""Explicit read-only client tools and shared OpenRouter search configuration.

No custom search service: search executes in the selected model's request.
The direct loop's registry is empty by default. Delegation supplies its own
server-owned registry; tools require a strict argument model and bounded executor.
"""
from dataclasses import dataclass
import json
import re
from typing import Callable, Optional

from pydantic import BaseModel, ValidationError

from app.core import config as cfg
from app.services.llm.engines import web_search_tool


def configured_model(model):
    # Reuse product routing. Extra Agent-only pinning/require_parameters
    # excluded working Anthropic endpoints (HTTP 404).
    return model


def search_family(model):
    return next((p.key for p in cfg.PROVIDERS.values()
                 if model.model.startswith(p.openrouter_prefix.rstrip("/") + "/")), "")


# Exa results per search round. They bound what a round can add to the
# input (SEARCH_INPUT_TOKENS); the publishers' own search may ignore them.
SEARCH_RESULTS, SEARCH_RESULT_CHARACTERS = 5, 2000


def search_tools(model, searches):
    """The one search configuration for every model, as in Consensus.

    Engine "auto" lets OpenRouter choose: the publisher's own search where one
    exists (Google grounding, OpenAI, Anthropic), Exa otherwise. The only
    exception, Grok on Exa, lives in engines.web_search_tool. See
    docs/agent-mode.md, "Websuche".
    """
    return [web_search_tool(search_family(model), max_uses=searches, max_results=SEARCH_RESULTS,
                            max_total_results=SEARCH_RESULTS * searches,
                            max_characters=SEARCH_RESULT_CHARACTERS)] if searches else []


@dataclass(frozen=True)
class ReadOnlyTool:
    name: str
    description: str
    arguments: type[BaseModel]
    execute: Callable
    # Optional per-tool cap on raw JSON arguments; defaults to the registry's.
    argument_limit: Optional[int] = None
    # Optional activity(arguments, result) -> extra fields of the tool's trace
    # event (result is None while it runs), e.g. the host read_source opens.
    activity: Optional[Callable] = None

    def schema(self):
        if (not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", self.name)
                or self.arguments.model_config.get("extra") != "forbid"
                or not self.arguments.model_config.get("strict")):
            raise ValueError("Tools require strict server-owned argument schemas")
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                "parameters": self.arguments.model_json_schema()}}


def _decode_stringified(arguments, value, unique):
    """Claude sometimes sends an array or object argument as its JSON text
    ("memory": "[]"). Strict validation rejected the whole call, and the model
    repeated it until the turn ended (2026-10-07). A string that decodes to
    the declared container type is taken as that container; anything else is
    left for validation to reject."""
    properties = arguments.model_json_schema().get("properties", {})
    decoded = dict(value)
    for key, item in value.items():
        if not isinstance(item, str) or key not in properties:
            continue
        spec = properties[key]
        types = {spec.get("type"), *(option.get("type") for option in spec.get("anyOf", []))}
        if not types & {"array", "object"}:
            continue
        try:
            parsed = json.loads(item, object_pairs_hook=unique)
        except ValueError:
            continue
        if ("array" in types and isinstance(parsed, list)) or ("object" in types and isinstance(parsed, dict)):
            decoded[key] = parsed
    return decoded


class ToolRegistry:
    def __init__(self, tools=(), *, argument_limit=2048):
        self.default_argument_limit = argument_limit
        # The streaming client needs the largest cap any tool accepts; each
        # tool is still validated against its own limit below.
        self.argument_limit = max([argument_limit, *(t.argument_limit or 0 for t in tools)])
        self.tools = {tool.name: tool for tool in tools}
        if len(self.tools) != len(tools) or len(tools) > 20:
            raise ValueError("Invalid tool registry")
        self.schemas = [tool.schema() for tool in tools]

    def validate(self, call):
        # Every refusal names what to change: the model reads only this text,
        # and a bare "not authorized" let Claude repeat the same call until
        # the turn ended (2026-10-09).
        function = call.get("function") or {}
        tool = self.tools.get(function.get("name"))
        raw = function.get("arguments")
        if tool is None:
            pages = ("read_source opens only URLs that comparison answers cited." if "read_source" in self.tools
                     else "There is no tool that opens web pages.")
            raise ValueError(f"Tool is not authorized: unknown tool. Available tools: {', '.join(self.tools)}. {pages}")
        limit = tool.argument_limit or self.default_argument_limit
        if not isinstance(raw, str) or len(raw) > limit:
            raise ValueError(f"Tool is not authorized: {tool.name} arguments must be one JSON object "
                             f"of at most {limit} characters.")
        # Reject duplicate JSON keys, rather than silently accepting the last.
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("Duplicate tool argument")
                value[key] = item
            return value
        try:
            value = json.loads(raw, object_pairs_hook=unique)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{tool.name} arguments are not valid JSON ({exc.msg}); send one JSON object.") from exc
        if isinstance(value, dict):
            value = _decode_stringified(tool.arguments, value, unique)
        try:
            arguments = tool.arguments.model_validate(value)
        except ValidationError as exc:
            # Field and message only: pydantic's default text repeats the
            # input and a docs URL per error, and the 500-character cut
            # dropped every error after the second.
            problems = "; ".join(
                f"{'.'.join(str(part) for part in error['loc']) or 'arguments'}: {error['msg']}"
                for error in exc.errors(include_url=False, include_input=False))
            raise ValueError(f"Invalid {tool.name} arguments - {problems}") from exc
        return tool, arguments

    def result(self, tool, arguments, *, cancellation, limit):
        cancellation.raise_if_cancelled()
        result = tool.execute(arguments, cancellation=cancellation)
        cancellation.raise_if_cancelled()
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
        if len(encoded) > limit:
            raise ValueError("Tool result exceeds limit")
        return encoded
