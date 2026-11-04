"""Explicit client tools and the shared OpenRouter search configuration.

Search executes in the selected model's request, no custom search service. Every tool needs a strict
argument model and a bounded executor."""
import contextlib
import contextvars
from dataclasses import dataclass
import functools
import json
import re
import threading
from typing import Callable, Optional

from pydantic import BaseModel, ValidationError

from app.core import config as cfg
from app.services.llm.engines import web_search_tool


def configured_model(model):
    # Reuse product routing: extra pinning excluded working Anthropic endpoints (HTTP 404).
    return model


def search_family(model):
    return next((p.key for p in cfg.PROVIDERS.values()
                 if model.model.startswith(p.openrouter_prefix.rstrip("/") + "/")), "")


# They bound what a round adds to the input; the publishers' own search may ignore them.
SEARCH_RESULTS, SEARCH_RESULT_CHARACTERS = 5, 2000


def search_tools(model, searches):
    """The one search configuration for every model, as in Consensus: engine "auto" lets OpenRouter
    choose the publisher's own search where one exists, Exa otherwise (Grok on Exa in
    engines.web_search_tool)."""
    return [web_search_tool(search_family(model), max_uses=searches, max_results=SEARCH_RESULTS,
                            max_total_results=SEARCH_RESULTS * searches,
                            max_characters=SEARCH_RESULT_CHARACTERS)] if searches else []


def argument_schema(arguments):
    """The argument model's JSON schema with every $ref written out in place: some providers never
    resolve $defs and guessed nested fields until the turn ended. Built once per model and handed
    out as a copy, since every message builds about 50 schemas."""
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
    """A flat schema in one line, optional fields with "?", for a tool description: that reaches the
    model with every provider, and even the flat schema left a model guessing on its first call."""
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
    return next((option for option in node.get("anyOf", ()) if key in option), node)


def _allowed_fields(schema, path):
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
    # activity(arguments, result) -> extra trace fields (result None while it runs).
    activity: Optional[Callable] = None
    # The tool reports while it runs: execute(..., report=fields) updates its trace event.
    reports: bool = False
    # The tool only reads and needs nothing another call of its step changes or asks: neighbouring
    # such calls run at the same time. Its execute must be thread-safe.
    concurrent: bool = False
    # With ``concurrent``: what the tool counts or keeps in order happens inside call_order. A call
    # of a tool without it gives up its place as it starts.
    ordered: bool = False

    def schema(self):
        if (not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", self.name)
                or self.arguments.model_config.get("extra") != "forbid"
                or not self.arguments.model_config.get("strict")):
            raise ValueError("Tools require strict server-owned argument schemas")
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                "parameters": argument_schema(self.arguments)}}


# The running call's place in its group: (CallOrder, index), None outside one.
_CALL_TURN = contextvars.ContextVar("agent_call_turn", default=None)


class CallOrder:
    """The places of one group's calls: a call passes call_order once every earlier call passed it
    or gave up its place."""

    def __init__(self, count):
        self._condition = threading.Condition()
        self._given = [False] * count

    def enter(self, index):
        _CALL_TURN.set((self, index))

    def give(self, index):
        with self._condition:
            self._given[index] = True
            self._condition.notify_all()

    def wait(self, index, cancellation=None):
        with self._condition:
            while not all(self._given[:index]):
                if cancellation is not None:
                    cancellation.raise_if_cancelled()
                self._condition.wait(.1)


def give_turn():
    turn = _CALL_TURN.get()
    if turn is not None:
        turn[0].give(turn[1])


@contextlib.contextmanager
def call_order(cancellation=None):
    """Inside, the calls of a group come in call order whichever thread arrives first, so a limit
    refuses the later call. Outside a group it waits for nothing."""
    turn = _CALL_TURN.get()
    if turn is None:
        yield
        return
    order, index = turn
    order.wait(index, cancellation)
    try:
        yield
    finally:
        order.give(index)


def _decode_stringified(arguments, value, unique):
    """Claude sometimes sends an array or object argument as its JSON text; strict validation
    rejected the call and the model repeated it until the turn ended. A string that decodes to the
    declared container type is taken as it; anything else is left for validation."""
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


# A bound against a runaway registry, far below the providers' own (128). An admin's largest message
# offers 27 tools.
MAX_TOOLS = 40


class ToolRegistry:
    def __init__(self, tools=(), *, argument_limit=2048):
        self.default_argument_limit = argument_limit
        # The streaming client needs the largest cap any tool accepts; each tool is validated
        # against its own.
        self.argument_limit = max([argument_limit, *(t.argument_limit or 0 for t in tools)])
        self.tools = {tool.name: tool for tool in tools}
        if len(self.tools) != len(tools) or len(tools) > MAX_TOOLS:
            raise ValueError("Invalid tool registry")
        self.schemas = [tool.schema() for tool in tools]

    def validate(self, call):
        # Every refusal names what to change: the model reads only this text, and a bare "not
        # authorized" made it repeat the call until the turn ended.
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
        # Reject duplicate JSON keys rather than silently accepting the last.
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("Duplicate tool argument")
                value[key] = item
            return value
        try:
            # A call without arguments may stream none at all.
            value = json.loads(raw if raw.strip() else "{}", object_pairs_hook=unique)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{tool.name} arguments are not valid JSON ({exc.msg}); send one JSON object.") from exc
        if isinstance(value, dict):
            value = _decode_stringified(tool.arguments, value, unique)
        try:
            arguments = tool.arguments.model_validate(value)
        except ValidationError as exc:
            # Field and message only (pydantic's text repeats the input and a docs URL per error,
            # and the cut dropped later errors). An unknown field names the fields its object takes,
            # the same mistake in every list item is one problem, and the refusal ends with the
            # whole argument form: models otherwise kept guessing.
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
            raise ValueError(f"Invalid {tool.name} arguments - {'; '.join(problems)}. "
                             f"Expected arguments: {argument_shape(schema)}") from exc
        return tool, arguments

    def _unknown_notes(self):
        """What an unknown tool's refusal adds: which tool opens web pages, and that the workspace's
        tools come with open_workspace while it is closed."""
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
