"""Explicit read-only client tools and provider-native tool configuration.

No custom search service: native search executes in the selected provider's
request. The client registry is intentionally empty until a product tool is
approved; new tools must supply a strict argument model and bounded executor.
"""
from dataclasses import dataclass, replace
import json
import re
from typing import Callable

from pydantic import BaseModel

from app.services.agent_policy import tools_for_model


def configured_model(model):
    if "web_search" not in tools_for_model(model):
        return model
    config = dict(model.request_config)
    config["provider"] = {**config.get("provider", {}), "only": ["anthropic"]}
    return replace(model, request_config=config)


def native_tools(searches):
    return [{"type": "openrouter:web_search", "parameters": {"engine": "native", "max_uses": searches}}] if searches else []


@dataclass(frozen=True)
class ReadOnlyTool:
    name: str
    description: str
    arguments: type[BaseModel]
    execute: Callable

    def schema(self):
        if (not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", self.name)
                or self.arguments.model_config.get("extra") != "forbid"
                or not self.arguments.model_config.get("strict")):
            raise ValueError("Tools require strict server-owned argument schemas")
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                "parameters": self.arguments.model_json_schema()}}


class ToolRegistry:
    def __init__(self, tools=()):
        self.tools = {tool.name: tool for tool in tools}
        if len(self.tools) != len(tools) or len(tools) > 8:
            raise ValueError("Invalid tool registry")
        self.schemas = [tool.schema() for tool in tools]

    def validate(self, call):
        function = call.get("function") or {}
        tool = self.tools.get(function.get("name"))
        raw = function.get("arguments")
        if tool is None or not isinstance(raw, str) or len(raw) > 2048:
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
