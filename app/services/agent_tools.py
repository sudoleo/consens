"""Explicit read-only client tools and shared OpenRouter search configuration.

No custom search service: search executes in the selected model's request.
The direct loop's registry is empty by default. Delegation supplies its own
server-owned registry; tools require a strict argument model and bounded executor.
"""
from dataclasses import dataclass
import functools
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


def argument_schema(arguments):
    """The argument model's JSON schema with every $ref written out in place.

    Pydantic puts nested models under $defs. DeepSeek V4.1 Flash never saw
    them: it called create_document three times with guessed section fields
    ("blocks", "content", "text") until the turn ended (2026-11-01), and
    needed three attempts at prepare_settings_change before. A flat schema
    shows every provider the whole structure.

    Built once per model and handed out as a copy: every message builds its
    tools (about 50 schemas) before its first request."""
    return json.loads(_flat_schema(arguments))


@functools.lru_cache(maxsize=None)
def _flat_schema(arguments):
    schema = arguments.model_json_schema()
    definitions = schema.pop("$defs", {})

    def resolve(node, seen):
        if isinstance(node, list):
            return [resolve(item, seen) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" not in node:
            return {key: resolve(value, seen) for key, value in node.items()}
        name = node["$ref"].rsplit("/", 1)[-1]
        if name in seen:
            raise ValueError("Tool argument schemas must not be recursive")
        siblings = {key: resolve(value, seen) for key, value in node.items() if key != "$ref"}
        return {**resolve(definitions[name], seen | {name}), **siblings}

    return json.dumps(resolve(schema, frozenset()))


def argument_shape(node):
    """A flat schema in one line, optional fields with "?":
    {title: string, sections: [{heading: string, paragraphs?: [string]}]}.

    For a tool description: with the flat schema, DeepSeek V4.1 Flash still
    guessed the document's fields on its first call (2026-11-01), and a
    description reaches the model with every provider."""
    options = [option for option in node.get("anyOf", [node]) if option.get("type") != "null"]
    if len(options) != 1:
        return " | ".join(argument_shape(option) for option in options)
    node = options[0]
    if "properties" in node:
        required = set(node.get("required", ()))
        return "{" + ", ".join(f"{key}{'' if key in required else '?'}: {argument_shape(value)}"
                               for key, value in node["properties"].items()) + "}"
    if node.get("type") == "array":
        return f"[{argument_shape(node.get('items', {}))}]"
    if "const" in node or "enum" in node:
        return " | ".join(json.dumps(value) for value in node.get("enum", [node.get("const")]))
    return node.get("type", "any")


def _option(node, key):
    """The anyOf option of an optional field that carries ``key``."""
    return next((option for option in node.get("anyOf", ()) if key in option), node)


def _allowed_fields(schema, path):
    """The fields the object at ``path`` takes, for an unknown-field refusal."""
    node = schema
    for part in path:
        node = (_option(node, "items").get("items") if isinstance(part, int)
                else _option(node, "properties").get("properties", {}).get(part))
        if not isinstance(node, dict):
            return []
    return list(_option(node, "properties").get("properties", {}))


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
    # The tool reports while it runs: execute(..., report=fields) updates its
    # running trace event with ``fields`` (a VM command's output so far).
    reports: bool = False

    def schema(self):
        if (not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", self.name)
                or self.arguments.model_config.get("extra") != "forbid"
                or not self.arguments.model_config.get("strict")):
            raise ValueError("Tools require strict server-owned argument schemas")
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                "parameters": argument_schema(self.arguments)}}


def _decode_stringified(arguments, value, unique):
    """Claude sometimes sends an array or object argument as its JSON text
    ("memory": "[]"). Strict validation rejected the whole call, and the model
    repeated it until the turn ended (2026-10-07). A string that decodes to
    the declared container type is taken as that container; anything else is
    left for validation to reject."""
    properties = argument_schema(arguments).get("properties", {})
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


# A bound against a runaway registry, far below the providers' own limits
# (OpenAI and Gemini take 128). An admin's largest message (workers, files,
# Memory, VM with GitHub and pictures) offers 27 tools; 20 failed every
# message of such a chat (2026-10-26, tests/test_agent_vm.py).
MAX_TOOLS = 40


class ToolRegistry:
    def __init__(self, tools=(), *, argument_limit=2048):
        self.default_argument_limit = argument_limit
        # The streaming client needs the largest cap any tool accepts; each
        # tool is still validated against its own limit below.
        self.argument_limit = max([argument_limit, *(t.argument_limit or 0 for t in tools)])
        self.tools = {tool.name: tool for tool in tools}
        if len(self.tools) != len(tools) or len(tools) > MAX_TOOLS:
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
            raise ValueError(" ".join(["Tool is not authorized: unknown tool. Available tools: "
                                       f"{', '.join(self.tools)}.", *self._unknown_notes()]))
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
            # A call without arguments may stream none at all; that is an
            # empty object (read_settings takes no arguments).
            value = json.loads(raw if raw.strip() else "{}", object_pairs_hook=unique)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{tool.name} arguments are not valid JSON ({exc.msg}); send one JSON object.") from exc
        if isinstance(value, dict):
            value = _decode_stringified(tool.arguments, value, unique)
        try:
            arguments = tool.arguments.model_validate(value)
        except ValidationError as exc:
            # Field and message only: pydantic's default text repeats the
            # input and a docs URL per error, and the 500-character cut
            # dropped every error after the second. An unknown field also
            # names the fields its object takes: "Extra inputs are not
            # permitted" alone left DeepSeek guessing (2026-11-01). The same
            # mistake in every list item is one problem ("and 9 more like
            # it"): ten slides with "bullets" filled the cut before the
            # document's own fields came up.
            schema, problems, alike, named = argument_schema(tool.arguments), [], {}, set()
            for error in exc.errors(include_url=False, include_input=False):
                place = tuple(None if isinstance(part, int) else part for part in error["loc"])
                key = (place, error["type"], error["msg"])
                if key in alike:
                    alike[key][1] += 1
                    continue
                alike[key] = [len(problems), 0]
                problem = f"{'.'.join(str(part) for part in error['loc']) or 'arguments'}: {error['msg']}"
                if error["type"] == "extra_forbidden" and place[:-1] not in named:
                    named.add(place[:-1])
                    allowed = _allowed_fields(schema, error["loc"][:-1])
                    if allowed:
                        problem += f" (allowed here: {', '.join(allowed)})"
                problems.append(problem)
            for index, more in alike.values():
                if more:
                    problems[index] += f" (and {more} more like it)"
            raise ValueError(f"Invalid {tool.name} arguments - {'; '.join(problems)}") from exc
        return tool, arguments

    def _unknown_notes(self):
        """What an unknown tool's refusal adds, true of this registry: which
        tool opens web pages (read_source's own description says which ones:
        any public page), and that the workspace's
        tools come with open_workspace while it is closed (audit L7: a direct
        call of browser did not say so)."""
        notes = []
        if "read_source" in self.tools:
            notes.append("Of these, read_source opens web pages.")
        elif "browser" not in self.tools and "open_workspace" not in self.tools:
            notes.append("There is no tool that opens web pages.")
        if "open_workspace" in self.tools:
            notes.append("Your workspace is closed in this message: its tools, the browser and vm_exec among "
                         "them, come from the step after open_workspace ran.")
        return notes

    def result(self, tool, arguments, *, cancellation, limit):
        cancellation.raise_if_cancelled()
        result = tool.execute(arguments, cancellation=cancellation)
        cancellation.raise_if_cancelled()
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
        if len(encoded) > limit:
            raise ValueError("Tool result exceeds limit")
        return encoded
