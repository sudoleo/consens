"""Explicit read-only client tools and shared OpenRouter search configuration.

No custom search service: search executes in the selected model's request.
The direct loop's registry is empty by default. Delegation supplies its own
server-owned registry; tools require a strict argument model and bounded executor.
"""
from dataclasses import dataclass
import json
import re
from typing import Callable, Optional

from pydantic import BaseModel

from app.core import config as cfg
from app.services.llm.engines import web_search_tool


def configured_model(model):
    # Reuse product routing. Extra Agent-only pinning/require_parameters
    # excluded working Anthropic endpoints (HTTP 404).
    return model


def search_family(model):
    return next((p.key for p in cfg.PROVIDERS.values()
                 if model.model.startswith(p.openrouter_prefix.rstrip("/") + "/")), "")


def search_tools(model, searches):
    if model.request_config.get("_agent_bounded_search"):
        # Rich: five longer results per round, for full answers and research.
        rich = model.request_config.get("_agent_rich_search")
        results, characters = (5, 2000) if rich else (3, 1000)
        return [web_search_tool(search_family(model), max_uses=searches, engine="exa",
                max_results=results, max_total_results=results * searches, max_characters=characters)] if searches else []
    return [web_search_tool(search_family(model), max_uses=searches,
                           max_results=5, max_total_results=5 * searches, max_characters=2000)] if searches else []


def uses_native_search(model):
    # auto delegates these publishers to native search; Grok deliberately
    # shares Consensus's bounded Exa route. Other families use Exa via auto.
    return not model.request_config.get("_agent_bounded_search") and search_family(model) in {"openai", "anthropic", "gemini"}


@dataclass(frozen=True)
class ReadOnlyTool:
    name: str
    description: str
    arguments: type[BaseModel]
    execute: Callable
    # Optional per-tool cap on raw JSON arguments; defaults to the registry's.
    argument_limit: Optional[int] = None

    def schema(self):
        if (not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", self.name)
                or self.arguments.model_config.get("extra") != "forbid"
                or not self.arguments.model_config.get("strict")):
            raise ValueError("Tools require strict server-owned argument schemas")
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                "parameters": self.arguments.model_json_schema()}}


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
        function = call.get("function") or {}
        tool = self.tools.get(function.get("name"))
        raw = function.get("arguments")
        limit = (tool.argument_limit or self.default_argument_limit) if tool else 0
        if tool is None or not isinstance(raw, str) or len(raw) > limit:
            raise ValueError("Tool is not authorized")
        # Reject duplicate JSON keys, rather than silently accepting the last.
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("Duplicate tool argument")
                value[key] = item
            return value
        arguments = tool.arguments.model_validate(json.loads(raw, object_pairs_hook=unique))
        return tool, arguments

    def result(self, tool, arguments, *, cancellation, limit):
        cancellation.raise_if_cancelled()
        result = tool.execute(arguments, cancellation=cancellation)
        cancellation.raise_if_cancelled()
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
        if len(encoded) > limit:
            raise ValueError("Tool result exceeds limit")
        return encoded
