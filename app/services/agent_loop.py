"""Bounded model/tool orchestration, independent of HTTP and provider transport."""
from uuid import uuid4

from app.services.agent_costs import RunCosts
from app.services.agent_policy import AgentPolicy, supports_client_tools, tools_for_model
from app.services.agent_tools import ToolRegistry, native_tools
from app.services.chat_store import TurnStatusConflict
from app.services.llm.agent_client import AgentCompletion
from app.services.llm.provider_runtime import (
    AnalysisBudget, AnalysisBudgetExceeded, ProviderCancelled, bind_analysis_budget,
)


class AgentLoop:
    def __init__(self, *, store, uid, chat_id, turn_id, model, messages, api_key,
                 cancellation, policy=None, registry=None, completion_factory=AgentCompletion, mock_answer=None):
        self.store, self.uid, self.chat_id, self.turn_id = store, uid, chat_id, turn_id
        self.model, self.messages, self.api_key = model, list(messages), api_key
        self.cancellation = cancellation
        self.policy = policy or AgentPolicy()
        self.registry = registry or ToolRegistry()
        self.factory, self.mock_answer = completion_factory, mock_answer
        self.completion = AgentCompletion()
        self.completion.step_id = "run"
        self.run_token = uuid4().hex
        self.claimed = False
        self.costs = RunCosts(self.policy)
        self.remaining_tools = self.policy.max_tools
        self.seen_calls = set()

    def check(self, budget):
        self.cancellation.raise_if_cancelled()
        budget.check()

    def activity(self, event):
        """One bounded trace, with identities stable across all model steps."""
        if not event:
            return None
        event = dict(event)
        step = event.pop("step_id", "run")
        event_id, kind = event.pop("id"), event.pop("kind")
        for key in ("version", "type"):
            event.pop(key, None)
        if kind == "reasoning":
            text = event.get("text", "")
            available = max(0, 32_000 - self.completion.reasoning_chars)
            self.completion.reasoning_truncated |= len(text) > available
            event["text"] = text[:available]
            self.completion.reasoning_chars += len(event["text"])
            if not event["text"]:
                return None
        self.completion.step_id = step
        return self.completion.event(kind, f"{step}/{event_id}", **event)

    def status(self, step, event_id, **data):
        return self.activity({"step_id": step, "id": event_id, "kind": "status", **data})

    def tool_event(self, step, name, status, **data):
        if "sources" in data:
            data["sources"] = data["sources"][:self.policy.result_sources]
        return self.activity({"step_id": step, "id": "tool", "kind": "tool", "name": name, "status": status, **data})

    def run(self):
        status = "failed"
        budget = AnalysisBudget(seconds=self.policy.seconds, max_calls=self.policy.max_calls)
        try:
            with bind_analysis_budget(budget):
                for index in range(self.policy.max_calls):
                    self.check(budget)
                    step = f"completion:{index}"
                    # Native searches have a provider-owned schema and execute
                    # inside this exact call. Reserve ALL remaining search uses
                    # upfront; missing usage can never authorize another search.
                    searches = self.remaining_tools if "web_search" in tools_for_model(self.model) else 0
                    schemas = self.registry.schemas if supports_client_tools(self.model) else []
                    allow_client = bool(schemas) and self.remaining_tools > 0 and index + 1 < self.policy.max_calls
                    tools = [*schemas, *native_tools(searches)]
                    reservation = self.costs.reserve(self.model, self.messages, tools, native_searches=searches)
                    value = self.factory()
                    value.step_id = step
                    if not self.store.claim(self.uid, self.chat_id, self.turn_id, self.model, step=step,
                                            run_token=self.run_token, policy=self.policy.snapshot()):
                        raise TurnStatusConflict("This agent step has already started. Reopen the saved conversation.")
                    self.claimed = True
                    step_status = "failed"
                    try:
                        self.check(budget)
                        if index == 0:
                            yield {"type": "started", "chat_id": self.chat_id, "turn_id": self.turn_id}
                        yield self.status(step, "started", status="working", settings=self.model.settings(), clear_response=index > 0)
                        if self.mock_answer is not None:
                            value.text, value.finish_reason = self.mock_answer, "stop"
                            yield {"type": "delta", "text": value.text}
                        else:
                            provider_stream = value.stream(model=self.model, messages=self.messages, api_key=self.api_key,
                                                           tools=tools, native_searches=searches, allow_tool_calls=allow_client)
                            try:
                                for event in provider_stream:
                                    self.check(budget)
                                    if event["type"] == "activity":
                                        # Publish measured totals once the step settles.
                                        if event["kind"] == "usage":
                                            continue
                                        event = self.activity(event)
                                    if event:
                                        yield event
                            finally:
                                provider_stream.close()
                        self.check(budget)
                        step_status = "succeeded"
                    except (ProviderCancelled, GeneratorExit):
                        step_status = "cancelled"
                        raise
                    finally:
                        self.costs.reconcile(reservation, value.usage)
                        self.completion.usage = self.costs.total()
                        self.completion.reasoning_truncated |= value.reasoning_truncated
                        if searches and step_status != "succeeded":
                            self.tool_event(f"{step}:web_search", "web_search", "unknown", sources=value.sources,
                                            text="The request ended before search completion could be confirmed.", provider_native=True)
                        self.store.settle(self.uid, self.chat_id, self.turn_id, completion=value,
                                          status=step_status, step=step, final=False)
                    self.check(budget)
                    if searches:
                        count = value.usage.get("web_search_requests") if value.usage else None
                        known = type(count) is int and 0 <= count <= searches
                        self.remaining_tools -= count if known else searches
                        # The Chat API exposes citations/usage, not native start
                        # timestamps or raw search queries. Do not invent them.
                        if (known and count) or value.sources:
                            yield self.tool_event(f"{step}:web_search", "web_search", "succeeded",
                                count=count if known else None, sources=value.sources, provider_native=True)
                        elif not known:
                            yield self.tool_event(f"{step}:web_search", "web_search", "unknown", provider_native=True)
                    yield self.activity({"step_id": "run", "id": "usage", "kind": "usage", "usage": self.completion.usage})
                    self.completion.text, self.completion.finish_reason = value.text, value.finish_reason
                    self.costs.check()
                    if not value.tool_calls:
                        status = "succeeded"
                        return
                    if not allow_client or len(value.tool_calls) != 1:
                        raise AnalysisBudgetExceeded("The agent's tool or step budget was reached.")
                    call = value.tool_calls[0]
                    tool_step = f"tool:{index}"
                    if call["id"] in self.seen_calls:
                        raise TurnStatusConflict("The model repeated a tool call identity.")
                    self.seen_calls.add(call["id"])
                    try:
                        tool, arguments = self.registry.validate(call)
                    except (ValueError, TypeError):
                        yield self.tool_event(tool_step, "unavailable", "blocked", text="The requested tool or arguments were not allowed.")
                        raise ValueError("Tool request was not allowed") from None
                    if self.remaining_tools <= 0:
                        yield self.tool_event(tool_step, tool.name, "blocked", text="Tool budget reached.")
                        raise AnalysisBudgetExceeded("The agent's tool budget was reached.")
                    self.remaining_tools -= 1
                    try:
                        yield self.tool_event(tool_step, tool.name, "running")
                        self.check(budget)
                        result = self.registry.result(tool, arguments, cancellation=self.cancellation, limit=self.policy.result_chars)
                        self.check(budget)
                    except (ProviderCancelled, GeneratorExit):
                        self.tool_event(tool_step, tool.name, "cancelled")
                        raise
                    except Exception:
                        yield self.tool_event(tool_step, tool.name, "failed", text="The tool could not complete.")
                        raise
                    yield self.tool_event(tool_step, tool.name, "succeeded", text=result)
                    # Only a non-thinking protocol is enabled for client tools.
                    self.messages.extend([{"role": "assistant", "content": value.text, "tool_calls": value.tool_calls},
                        {"role": "tool", "tool_call_id": call["id"], "content": result}])
                raise AnalysisBudgetExceeded("The agent's step budget was reached.")
        except (ProviderCancelled, GeneratorExit):
            status = "cancelled"
            raise
        finally:
            self.status("run", "finished", status=status, finish_reason=self.completion.finish_reason)
            if self.claimed:
                self.store.finish_run(self.uid, self.chat_id, self.turn_id, completion=self.completion,
                                      status=status, run_token=self.run_token)
            else:
                self.store.release_unclaimed(self.uid, self.chat_id, self.turn_id)
