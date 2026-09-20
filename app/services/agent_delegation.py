"""One-level, bidirectional agent sessions with bounded concurrent providers."""
from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import json
import logging
import queue
import threading
import time
from itertools import count
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.services.agent_costs import aggregate_usage
from app.services.agent_quota import AgentTokenBudgetExceeded
from app.services.agent_loop import AgentLoop
from app.services.agent_progress import ReasoningProgress, StreamProgress
from app.services.agent_policy import supports_delegation
from app.services.agent_provider_limits import AgentRunInterrupted, agent_failure, provider_cooldowns
from app.services.agent_tools import ReadOnlyTool, ToolRegistry, search_tools
from app.services.llm.agent_client import AgentCompletion, agent_models, resolve_agent_model
from app.services.llm.provider_runtime import (
    AnalysisBudget, AnalysisBudgetExceeded, ProviderCancellation, ProviderCancelled,
    bind_analysis_budget, bind_provider_cancellation,
)


class StrictArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class StartAgent(StrictArgs):
    title: str = Field(min_length=1, max_length=100)
    goal: str = Field(min_length=1, max_length=2000)
    context: str = Field(max_length=12_000)
    constraints: str = Field(min_length=1, max_length=2000)
    expected_output: str = Field(min_length=1, max_length=1000)
    acceptance_criteria: str = Field(min_length=1, max_length=2000)
    model_id: str = Field(min_length=1, max_length=160)


class AgentTarget(StrictArgs):
    agent_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class SendAgent(AgentTarget):
    text: str = Field(min_length=1, max_length=8000)
    kind: Literal["message", "answer", "rework"] = "message"


class WaitAgents(StrictArgs):
    seconds: int = Field(default=20, ge=0, le=30)


class Report(StrictArgs):
    kind: Literal["question", "blocker", "progress"]
    text: str = Field(min_length=1, max_length=8000)


class ReviewAgent(AgentTarget):
    accepted: bool
    check: str = Field(min_length=1, max_length=2000)
    use_fallback: bool = False


@dataclass
class Worker:
    id: str
    model: object
    messages: list
    state: str = "waiting"
    inbox: deque = field(default_factory=deque)
    cancellation: ProviderCancellation = field(default_factory=ProviderCancellation)
    thread: object = None
    usages: list = field(default_factory=list)
    calls: int = 0
    reviewed: bool = False
    started: float = field(default_factory=time.monotonic)
    stream_chars: int = 0
    progress_seq: int = 0
    session_seq: int = 0


class DelegationLoop(AgentLoop):
    def __init__(self, *, delegation_config, worker_model_ids=None, cooldowns=None, comparison_models=None,
                 check_sources=False, source_limits=None, **kwargs):
        super().__init__(**kwargs)
        self.config = dict(delegation_config)
        self.cooldowns = cooldowns or provider_cooldowns
        self.workers = {}
        self.condition = threading.Condition(threading.RLock())
        self.slots = threading.BoundedSemaphore(self.policy.max_parallel)
        self.outgoing = queue.Queue(maxsize=1024)
        self.live_progress = {}
        self.unsettled = {}
        self.mailbox = deque()
        self.tools_used = 0
        self.search_remaining = self.policy.max_searches
        self.closed = threading.Event()
        self.watch_error = None
        self.search_handoff = False
        self.budget = AnalysisBudget(seconds=self.policy.seconds, max_calls=self.policy.max_calls,
                                     unlimited=self.policy.account_budget_only)
        self.models = {model.selection_id: resolve_agent_model(model.selection_id)
                       for model, _ in agent_models() if supports_delegation(resolve_agent_model(model.selection_id))
                       and (worker_model_ids is None or model.selection_id in worker_model_ids)}
        catalog = [{"id": m.selection_id, "label": m.label, "input_usd_per_million": m.input_usd_per_million,
                    "output_usd_per_million": m.output_usd_per_million, "context_length": m.context_length}
                   for m in self.models.values()]
        self.messages[0] = dict(self.messages[0])
        if self.config["enabled"] or comparison_models is None:
            self.messages[0]["content"] += ("\n\n" + self.config["orchestrator_prompt"]
                + "\nAvailable worker models (server registry): " + json.dumps(catalog))
        if not self.policy.account_budget_only:
            self.messages[0]["content"] += "\nShared run limits: " + json.dumps(self.policy.snapshot())
        self.registry = ToolRegistry([
            ReadOnlyTool("start_agent", "Start a bounded subtask in a new worker session. Returns immediately.", StartAgent, self.start_agent),
            ReadOnlyTool("send_agent", "Send a clarification, answer or rework in the same worker session.", SendAgent, self.send_agent),
            ReadOnlyTool("wait_agents", "Wait for semantic messages or results. Does not wait on tokens.", WaitAgents, self.wait_agents),
            ReadOnlyTool("stop_agent", "Stop this worker including its active provider request.", AgentTarget, self.stop_agent),
            ReadOnlyTool("review_agent", "Record your actual verification of a result or fallback after failure.", ReviewAgent, self.review_agent),
        ], argument_limit=24_000)
        self.comparison = None
        if comparison_models is not None:
            from app.services.agent_comparison import ComparisonTools, PROMPT
            self.models = {key: replace(model, request_config={**model.request_config, "_agent_bounded_search": True})
                           for key, model in self.models.items()}
            self.comparison = ComparisonTools(self, comparison_models, check_sources=check_sources, source_limits=source_limits)
            self.messages[0]["content"] += "\n" + PROMPT
            if check_sources:
                from app.services.agent_contradictions import PROMPT as SOURCE_PROMPT
                self.messages[0]["content"] += "\n" + SOURCE_PROMPT
            else:
                self.messages[0]["content"] += "\nCheck contradictions is OFF. No original-source adjudication tool is authorized for this message. Model agreement is still checked by judge_answer."
            if not self.policy.account_budget_only:
                self.messages[0]["content"] += "\nAt most three comparisons and two checked answer versions per message."
            self.registry = ToolRegistry([*(self.registry.tools.values() if self.config["enabled"] else []),
                                          *self.comparison.tools], argument_limit=24_000)

    def _check(self, cancellation=None):
        if self.watch_error:
            raise self.watch_error
        self.cancellation.raise_if_cancelled()
        if cancellation:
            cancellation.raise_if_cancelled()
        self.budget.check()

    def _publish(self, worker, *, patch=None, text=None, kind="message", sender="orchestrator", recipient=None):
        with self.condition:
            return self._publish_locked(worker, patch=patch, text=text, kind=kind, sender=sender, recipient=recipient)

    def _publish_locked(self, worker, *, patch=None, text=None, kind="message", sender="orchestrator", recipient=None):
        patch = dict(patch or {})
        if worker.state not in {"completed", "failed", "stopped"}:
            patch.setdefault("duration_ms", max(0, int((time.monotonic() - worker.started) * 1000)))
        message = {"text": text, "kind": kind, "sender": sender, "recipient": recipient or worker.id} if text is not None else None
        if message and patch:
            message.update({key: patch[key] for key in ("sources", "result_truncated", "finish_reason") if key in patch})
        event = self.store.publish_agent(self.uid, self.chat_id, self.turn_id, run_token=self.run_token,
            agent_id=worker.id, patch=patch, message=message)
        worker.session_seq = event["agent"]["seq"]
        self.outgoing.put_nowait(event)
        if sender == worker.id and message and getattr(worker, "kind", "worker") == "worker":
            with self.condition:
                self.mailbox.append({**message, "agent_id": worker.id, "message_id": event["id"], "seq": event["seq"]})
                self.condition.notify_all()
        return event

    def _stream_progress(self, worker, progress, usage, *, streaming=True, force=False):
        # Cumulative provider snapshots replace the current step's measurement;
        # only settled earlier steps are added. Telemetry never enters receipts.
        measured = usage and all(type(usage.get(key)) is int and usage[key] >= 0
                                 for key in ("input_tokens", "output_tokens"))
        snapshot = progress.snapshot(aggregate_usage([*worker.usages, usage]) if measured else None,
                                     streaming=streaming, force=force)
        worker.stream_chars = progress.chars
        if snapshot is None:
            return
        with self.condition:
            worker.progress_seq += 1
            # Keep only the latest visual snapshot per session. A slow reader
            # must never fill the durable-event queue with disposable counters.
            self.live_progress[worker.id] = {"type": "delegation_progress", "version": 1,
                "chat_id": self.chat_id, "turn_id": self.turn_id, "agent_id": worker.id,
                "session_seq": worker.session_seq, "seq": worker.progress_seq,
                "duration_ms": max(0, int((time.monotonic() - worker.started) * 1000)), **snapshot}

    def _state(self, worker, status, **patch):
        with self.condition:
            worker.state = status
            if status in {"completed", "failed", "stopped"}:
                patch.setdefault("ended_at", datetime.now(timezone.utc).isoformat())
            self._publish(worker, patch={"status": status, "duration_ms": int((time.monotonic() - worker.started) * 1000),
                                        "usage": aggregate_usage(worker.usages), **patch})
            self.condition.notify_all()

    def _worker(self, agent_id):
        worker = self.workers.get(agent_id)
        if worker is None:
            raise ValueError("Unknown agent in this run")
        return worker

    def start_agent(self, args, *, cancellation):
        self._check(cancellation)
        with self.condition:
            active = sum(not w.reviewed and w.state not in {"failed", "stopped"} for w in self.workers.values())
            if (active if self.policy.account_budget_only else len(self.workers)) >= self.policy.max_agents:
                raise ValueError("Agent limit reached; use an existing session or finish the work yourself.")
            if args.model_id not in self.models:
                raise ValueError("Model has no verified worker tool protocol. Select an offered worker model.")
            assignment = args.model_dump(exclude={"model_id", "title"})
            encoded = json.dumps(assignment, ensure_ascii=False)
            if len(encoded) > self.policy.context_chars:
                raise ValueError("Assignment exceeds the configured context limit")
            worker = Worker(uuid4().hex, self.models[args.model_id], [
                {"role": "system", "content": "You are a research worker inside consens.io, a multi-model question-answering app. "
                    "Complete your assigned supporting task for its Consensus workflow.\n" + self.config["worker_prompt"]},
                {"role": "user", "content": encoded}])
            self._publish(worker, patch={"title": args.title, "assignment": assignment, "task_id": uuid4().hex,
                "model": worker.model.settings(), "status": "waiting", "duration_ms": 0, "usage": None,
                "created_at": datetime.now(timezone.utc).isoformat()})
            self.workers[worker.id] = worker
            worker.inbox.append(None)  # Initial assignment is already in the conversation.
            worker.thread = threading.Thread(target=self._work, args=(worker,), name="agent-worker", daemon=True)
            worker.thread.start()
            return {"agent_id": worker.id, "status": "waiting"}

    def send_agent(self, args, *, cancellation):
        self._check(cancellation)
        if len(args.text) > self.policy.message_chars:
            raise ValueError("Message exceeds the configured limit")
        with self.condition:
            worker = self._worker(args.agent_id)
            if worker.state in {"failed", "stopped"} or worker.cancellation.cancelled:
                raise ValueError("This worker stopped; handle the task yourself or start a replacement.")
            self._publish(worker, text=args.text, kind=args.kind)
            worker.inbox.append(args.text)
            worker.reviewed = False
            if worker.state in {"completed", "review", "question", "waiting"}:
                self._state(worker, "rework" if args.kind == "rework" else "waiting")
            self.condition.notify_all()
            return {"agent_id": worker.id, "delivery": "next_model_boundary"}

    def stop_agent(self, args, *, cancellation):
        self._check(cancellation)
        worker = self._worker(args.agent_id)
        worker.cancellation.cancel()
        with self.condition:
            self.condition.notify_all()
        return {"agent_id": worker.id, "status": "stopping", "next": "Verify a fallback with review_agent."}

    def review_agent(self, args, *, cancellation):
        self._check(cancellation)
        with self.condition:
            worker = self._worker(args.agent_id)
            if worker.state not in {"review", "failed", "stopped", "completed"} or worker.inbox:
                raise ValueError("Wait for the current result before reviewing it.")
            self._publish(worker, text=args.check, kind="review")
            worker.reviewed = args.accepted or args.use_fallback
            if worker.reviewed and worker.state == "review":
                self._state(worker, "completed", review_outcome="fallback" if args.use_fallback else "accepted",
                            ended_at=datetime.now(timezone.utc).isoformat())
            return {"agent_id": worker.id, "accepted": args.accepted, "fallback_verified": args.use_fallback,
                    "next": "Request targeted rework, or verify your own replacement with use_fallback=true." if not worker.reviewed else "verified"}

    def _mail(self):
        with self.condition:
            messages = list(self.mailbox)
            self.mailbox.clear()
            return messages

    def wait_agents(self, args, *, cancellation):
        until = time.monotonic() + args.seconds
        with self.condition:
            while not self.mailbox and any(w.state in {"working", "waiting", "rework"} for w in self.workers.values()):
                self._check(cancellation)
                left = until - time.monotonic()
                if left <= 0:
                    break
                self.condition.wait(min(.2, left))
            return {"messages": self._mail(), "agents": self._summaries()}

    def _summaries(self):
        return [{"agent_id": w.id, "status": w.state, "reviewed": w.reviewed} for w in self.workers.values()]

    def _report(self, worker, args, *, cancellation):
        self._check(cancellation)
        if len(args.text) > self.policy.message_chars:
            raise ValueError("Report exceeds the configured message limit")
        self._publish(worker, text=args.text, kind=args.kind, sender=worker.id, recipient="orchestrator")
        if args.kind in {"question", "blocker"}:
            self._state(worker, "question")
        return {"delivered": True, "wait_for_reply": args.kind in {"question", "blocker"}}

    def _execute(self, registry, value, cancellation, call=None):
        call = call or value.tool_calls[0]
        identity = (value.step_id, call["id"])
        if identity in self.seen_calls:
            raise ValueError("Duplicate tool call")
        self.seen_calls.add(identity)
        with self.condition:
            self.tools_used += 1
            if not self.policy.account_budget_only and self.tools_used > self.policy.max_tools:
                raise AnalysisBudgetExceeded("Shared tool limit reached")
        tool = None
        status = "failed"
        def publish(status):
            if registry is self.registry and tool:
                self.outgoing.put_nowait(self.tool_event(f"{value.step_id}:{call['id']}", tool.name, status))
        try:
            tool, args = registry.validate(call)
            publish("running")
            result = tool.execute(args, cancellation=cancellation)
            status = "succeeded"
        except ProviderCancelled:
            status = "cancelled"
            raise
        except (ValueError, TypeError) as exc:
            # A schema/selection error is safe feedback, not a provider retry.
            result = {"error": str(exc)[:500]}
        finally:
            publish(status)
        return {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False)}

    def _admit_chat_step(self, model, messages, step, registry, cancellation, searches, claim_policy, worker):
        """Retry admission, never generation. All successful claims stay atomic.

        Contention is backpressure, not exhaustion. Wait for active receipts,
        then drop optional search and fit the actual provider output cap if needed.
        """
        from app.services.agent_tokens import input_estimate, minimum_output
        model = replace(model, request_config={**model.request_config, "_agent_bounded_search": True})
        search_limited, waiting = False, False
        delay, recovered_at = .1, time.monotonic()
        while True:
            self._check(cancellation)
            tools = [*registry.schemas, *search_tools(model, searches)]
            if not searches:
                room = model.context_length - input_estimate(messages, tools, model.request_config)
                if room < minimum_output(model):
                    raise AnalysisBudgetExceeded("The selected model's context limit was reached.")
                model = replace(model, max_output_tokens=min(model.max_output_tokens, room))
            reservation = None
            try:
                reservation = self.costs.reserve(model, messages, tools, native_searches=searches)
                claimed = self.store.claim(self.uid, self.chat_id, self.turn_id, model, step=step,
                    run_token=self.run_token, policy=claim_policy, reservation=reservation)
                return model, messages, tools, searches, reservation, claimed, search_limited
            except BaseException as exc:
                if reservation is not None:
                    self.costs.release(reservation)
                if isinstance(exc, AgentTokenBudgetExceeded):
                    inputs = input_estimate(messages, tools, model.request_config)
                    minimum = inputs + minimum_output(model)
                    if exc.reserved and ((not searches and minimum <= exc.remaining + exc.reserved)
                                         or (searches and exc.required <= exc.remaining + exc.reserved)):
                        if not waiting:
                            waiting = True
                            if worker:
                                self._state(worker, "waiting")
                            else:
                                yield self.status(step, "allowance", status="waiting",
                                    text="Waiting for active model calls to finish and release their unused allowance.")
                        # A failed settlement must not strand sibling waiters.
                        with self.condition:
                            unsettled = list(self.unsettled.items())
                        for pending_step, (value, status) in unsettled:
                            self._settle_step(pending_step, value, status)
                        if time.monotonic() - recovered_at >= 3:
                            self.store.recover_allowance(self.uid)
                            recovered_at = time.monotonic()
                        with self.condition:
                            self.condition.wait(delay)
                        delay = min(3, delay * 2)
                        if not worker:
                            yield from self._events()
                        continue
                    if not searches:
                        inputs = input_estimate(messages, tools, model.request_config)
                        output = min(model.max_output_tokens, exc.remaining - inputs)
                        if output < minimum_output(model):
                            raise
                        model = replace(model, max_output_tokens=output)
                        continue
                elif not isinstance(exc, AnalysisBudgetExceeded) or not searches:
                    raise
                # An optional search cannot fit even without competing calls.
                searches, search_limited = 0, True
                messages = [*messages]
                messages[0] = {**messages[0], "content": messages[0]["content"] +
                    "\nWeb search is unavailable for this step within the available token/context allowance. "
                    "Use existing evidence, state uncertainty, and do not imply new web research."}

    def _step(self, model, messages, step, registry, cancellation, *, worker=None, searches_enabled=True):
        self._check(cancellation)
        if not self.policy.account_budget_only and len(json.dumps(messages, ensure_ascii=False)) > self.policy.context_chars:
            raise AnalysisBudgetExceeded("Agent session context limit reached")
        self.cooldowns.check(model, self.api_key)
        with self.condition:
            if not self.policy.account_budget_only and worker and self.costs.calls >= self.policy.max_calls - 2:
                raise AnalysisBudgetExceeded("Remaining calls are reserved for the orchestrator")
            searches = (1 if self.policy.account_budget_only else min(1, self.search_remaining)) if searches_enabled else 0
            if not self.policy.account_budget_only:
                self.search_remaining -= searches
        tools = [*registry.schemas, *search_tools(model, searches)]
        reservation = None
        try:
            if not self.policy.account_budget_only:
                reservation = self.costs.reserve(model, messages, tools, native_searches=searches)
        except Exception:
            with self.condition:
                self.search_remaining += searches
            raise
        claimed = False
        provider_attempted = False
        value = self.factory()
        value.step_id, value.tool_argument_limit = step, registry.argument_limit
        value.tool_call_limit = 4
        worker_progress = ReasoningProgress() if worker else None
        stream_progress = StreamProgress(worker.stream_chars) if worker else None
        status = "failed"
        search_limited = False
        try:
            claim_policy = {**self.policy.snapshot(), "worker_models": [m.snapshot() for m in self.models.values()]}
            try:
                if self.policy.account_budget_only:
                    model, messages, tools, searches, reservation, claimed, search_limited = yield from self._admit_chat_step(
                        model, messages, step, registry, cancellation, searches, claim_policy, worker)
                else:
                    claimed = self.store.claim(self.uid, self.chat_id, self.turn_id, model, step=step,
                        run_token=self.run_token, policy=claim_policy, reservation=reservation)
            except AgentTokenBudgetExceeded:
                if self.policy.account_budget_only or not searches:
                    raise
                # Admission failed before any paid request. Keep all hard
                # bounds, but allow a response from the evidence already held.
                self.costs.release(reservation)
                reservation = None
                with self.condition:
                    self.search_remaining += searches
                searches = 0
                tools = registry.schemas
                messages = [*messages]
                messages[0] = {**messages[0], "content": messages[0]["content"] +
                    "\nWeb search is unavailable for this step because its token reservation exceeds the remaining daily allowance. "
                    "Use existing evidence, state any uncertainty, and do not imply new web research."}
                if not self.policy.account_budget_only and len(json.dumps(messages, ensure_ascii=False)) > self.policy.context_chars:
                    raise AnalysisBudgetExceeded("Agent session context limit reached")
                reservation = self.costs.reserve(model, messages, tools)
                claimed = self.store.claim(self.uid, self.chat_id, self.turn_id, model, step=step,
                    run_token=self.run_token, policy=claim_policy, reservation=reservation)
                search_limited = True
            if not claimed:
                raise ValueError("This model step has already started")
            self.claimed = True
            if worker:
                if worker.state == "waiting":
                    self._state(worker, "working")
                self._stream_progress(worker, stream_progress, None, force=True)
            if not worker:
                if step == "completion:0":
                    yield {"type": "started", "chat_id": self.chat_id, "turn_id": self.turn_id, "delegation": True}
                if search_limited:
                    yield self.tool_event(step + ":web_search", "web_search", "blocked",
                        text="Web search was skipped for this step: available tokens do not cover the search and its follow-up response. Continuing with existing sources.")
                yield self.status(step, "started", status="working", settings=model.settings(),
                                  clear_response=step != "completion:0" and not (self.comparison and self.comparison.text))
            if self.mock_answer is not None:
                value.text, value.finish_reason = self.mock_answer, "stop"
                if not worker:
                    yield {"type": "delta", "text": value.text}
            else:
                self._check(cancellation)
                provider_attempted = True
                source = value.stream(model=model, messages=messages, api_key=self.api_key, tools=tools,
                                      native_searches=searches, allow_tool_calls=True)
                try:
                    for event in source:
                        self._check(cancellation)
                        if worker and event.get("type") == "activity":
                            compact = worker_progress.update(event)
                            if compact:
                                self._publish(worker, patch={"progress_text": compact["text"], "progress_kind": compact["summary_source"]})
                        if worker:
                            stream_progress.update(event)
                            self._stream_progress(worker, stream_progress, value.usage)
                        if not worker:
                            yield from self._events()
                            if event["type"] == "activity":
                                if event["kind"] == "usage":
                                    continue
                                event = self.activity(event)
                            if event and self.comparison and self.comparison.text and event["type"] == "delta" and not value.text[:-len(event["text"])]:
                                yield self.status(step, "revision", status="working", clear_response=True)
                            if event:
                                yield event
                finally:
                    source.close()
            self._check(cancellation)
            status = "succeeded"
        except (ProviderCancelled, GeneratorExit):
            status = "cancelled"
            raise
        except Exception as exc:
            value.record_rejection(exc, model)
            self.cooldowns.record(model, self.api_key, exc)
            raise
        finally:
            if not worker and value.text:
                # Retain streamed text when a provider fails mid-answer. Reviewed
                # candidates are checkpointed separately, with their exact hash.
                self.completion.text = value.text
            if claimed:
                if not provider_attempted and self.mock_answer is None:
                    value.record_unstarted(model)
                if worker:
                    self._stream_progress(worker, stream_progress, value.usage, streaming=False, force=True)
                self.costs.reconcile(reservation, value.usage)
                if worker:
                    worker.usages.append(value.usage)
                with self.condition:
                    self.unsettled[step] = (value, status)
                self._settle_step(step, value, status)
            elif reservation is not None:
                self.costs.release(reservation)
            count = (value.usage or {}).get("web_search_requests")
            with self.condition:
                if self.policy.account_budget_only:
                    pass
                elif not claimed:
                    self.search_remaining += searches
                elif type(count) is int and 0 <= count <= searches:
                    self.search_remaining += searches - count
            if (not worker and value.text and self.comparison and self.comparison.comparisons
                    and not value.tool_calls and not value._tool_parts
                    and (status != "succeeded" or value.finish_reason == "length")):
                # Persist partial synthesis only after the mandatory settlement.
                self.comparison.capture(value.text)
        self.costs.check()
        if not worker:
            yield self.activity({"step_id": "run", "id": "usage", "kind": "usage", "usage": self.costs.total()})
            if value.sources or (type(count) is int and count > 0):
                yield self.tool_event(step + ":web_search", "web_search", "succeeded", sources=value.sources, count=count, server_tool=True)
        return value

    def _settle_step(self, step, value, status):
        """Retry only the idempotent receipt write, including ambiguous commits."""
        from google.api_core.exceptions import Aborted, DeadlineExceeded, InternalServerError, ServiceUnavailable
        transient = (Aborted, DeadlineExceeded, InternalServerError, ServiceUnavailable)
        for attempt in range(3):
            try:
                self.store.settle(self.uid, self.chat_id, self.turn_id, completion=value,
                                  status=status, step=step, final=False)
                with self.condition:
                    self.unsettled.pop(step, None)
                    self.condition.notify_all()
                return
            except Exception as exc:
                # Firestore wraps exhausted transaction conflicts in ValueError.
                if not isinstance(exc, transient) and not isinstance(exc.__cause__, transient):
                    raise
                if attempt == 2:
                    raise
                logging.warning("Agent receipt write retry attempt=%d", attempt + 1)
                time.sleep(.1 * 2 ** attempt)

    def _work(self, worker):
        unregister = self.cancellation.register(worker.cancellation)
        registry = ToolRegistry([ReadOnlyTool("report_to_orchestrator", "Report a finding, blocker or question to the orchestrator.",
            Report, lambda args, cancellation: self._report(worker, args, cancellation=cancellation))], argument_limit=10_000)
        try:
            with bind_provider_cancellation(worker.cancellation), bind_analysis_budget(self.budget):
                ready = False
                while not self.closed.is_set():
                    with self.condition:
                        while not ready and not worker.inbox:
                            self._check(worker.cancellation)
                            self.condition.wait(.2)
                        self._check(worker.cancellation)
                        if worker.state in {"review", "completed", "question"}:
                            self._state(worker, "waiting")
                        while worker.inbox:
                            text = worker.inbox.popleft()
                            if text is not None:
                                worker.messages.append({"role": "user", "content": "Orchestrator message:\n" + text})
                    if not self.policy.account_budget_only and worker.calls >= self.policy.worker_calls:
                        raise AnalysisBudgetExceeded("Worker call limit reached")
                    while not self.slots.acquire(timeout=.2):
                        self._check(worker.cancellation)
                    try:
                        self._state(worker, "working")
                        generator = self._step(worker.model, worker.messages, f"agent:{worker.id}:{worker.calls}",
                                               registry, worker.cancellation, worker=worker)
                        try:
                            while True:
                                next(generator)
                        except StopIteration as done:
                            value = done.value
                        worker.calls += 1
                    finally:
                        self.slots.release()
                    worker.messages.append(value.assistant_message())
                    if value.tool_calls:
                        results = [self._execute(registry, value, worker.cancellation, call) for call in value.tool_calls]
                        worker.messages.extend(results)
                        ready = not any(json.loads(result["content"]).get("wait_for_reply", False) for result in results)
                    else:
                        # A result and a concurrently queued clarification stay ordered.
                        with self.condition:
                            worker.reviewed = False
                            self._state(worker, "review", sources=value.sources, finish_reason=value.finish_reason)
                            self._publish(worker, text=value.text[:self.policy.result_chars], kind="result",
                                          sender=worker.id, recipient="orchestrator",
                                          patch={"result_truncated": len(value.text) > self.policy.result_chars,
                                                 "sources": value.sources, "finish_reason": value.finish_reason})
                        ready = False
        except (ProviderCancelled, GeneratorExit):
            if worker.state != "completed":
                self._terminal(worker, "stopped", "Worker stopped.")
        except Exception as exc:
            failure = agent_failure(exc)
            self._terminal(worker, "failed", failure["error"], failure)
        finally:
            unregister()
            worker.cancellation.cancel()
            if worker.state not in {"completed", "failed", "stopped"}:
                self._terminal(worker, "stopped", "Run ended.")

    def _terminal(self, worker, state, text, failure=None):
        try:
            with self.condition:
                self._state(worker, state, ended_at=datetime.now(timezone.utc).isoformat(), failure=failure)
                self._publish(worker, text=text[:self.policy.message_chars], kind="failure", sender=worker.id, recipient="orchestrator")
        except Exception:
            # Deletion/tombstones prohibit recreating a session. Cancellation still completes.
            worker.state = state
            self.cancellation.cancel()

    def _events(self):
        with self.condition:
            events = []
            while True:
                try:
                    events.append(self.outgoing.get_nowait())
                except queue.Empty:
                    break
            events.extend(self.live_progress.values())
            self.live_progress.clear()
        yield from events

    def _execute_stream(self, value, call):
        """Keep SSE live while a tool fans out or waits for both judges."""
        from contextvars import copy_context
        result = queue.Queue(maxsize=1)
        def work():
            try:
                result.put((self._execute(self.registry, value, self.cancellation, call), None))
            except BaseException as exc:
                result.put((None, exc))
        worker = threading.Thread(target=copy_context().run, args=(work,), daemon=True)
        worker.start()
        try:
            while worker.is_alive():
                yield from self._events()
                worker.join(.1)
            yield from self._events()
            response, error = result.get()
            if error:
                raise error
            return response
        finally:
            if worker.is_alive():
                self.cancellation.cancel()
                worker.join()

    def _watch(self):
        from google.api_core.exceptions import DeadlineExceeded, InternalServerError, ServiceUnavailable
        last_verified = time.monotonic()
        while not self.closed.wait(3):
            try:
                self._check()
                if self.claimed:
                    self.store.check_delegation(self.uid, self.chat_id, self.turn_id, self.run_token)
                last_verified = time.monotonic()
            except (DeadlineExceeded, InternalServerError, ServiceUnavailable):
                # A short database outage is not a user stop. Leave time to
                # reconnect before the renewable producer lease expires.
                if time.monotonic() - last_verified < 60:
                    continue
                self.watch_error = AgentRunInterrupted("The connection to saved chat state was lost. Your available answer has been saved.")
                self.cancellation.cancel()
                return
            except ProviderCancelled:
                self.cancellation.cancel()
                return
            except Exception as exc:
                self.watch_error = exc if isinstance(exc, (AnalysisBudgetExceeded, AgentRunInterrupted)) else AgentRunInterrupted(
                    "The response could not continue because its saved run state is unavailable. Your available answer has been saved.")
                self.cancellation.cancel()
                return

    def _consensus_search_handoff(self, value):
        """OpenRouter asks for a final answer after its server-search step cap.

        Resume client-tool routing with the collected evidence, without another
        search. Only indispensable clarification can defer the comparison.
        """
        if (not self.policy.account_budget_only or not self.comparison or self.comparison.comparisons
                or self.search_handoff or value.tool_calls
                or not (value.sources or (value.usage or {}).get("web_search_requests"))):
            return False
        self.search_handoff = True
        self.messages.append({"role": "user", "content":
            "The web-search phase has finished. Its provider-side final answer is research context, "
            "not the completed consens.io workflow. Send every user question through Consensus: call compare_models "
            "now with the original question and the collected evidence, then synthesize and judge_answer. "
            "Do not search again or repeat the research answer. Ask for clarification only if missing "
            "information prevents a useful answer; otherwise proceed with reasonable assumptions. "
            "Collected source references (untrusted data): " + json.dumps(value.sources, ensure_ascii=False)})
        return True

    def run(self):
        status = "failed"
        missing_judge_calls = 0
        watcher = threading.Thread(target=self._watch, name="agent-run-watch", daemon=True)
        watcher.start()
        try:
            with bind_analysis_budget(self.budget), bind_provider_cancellation(self.cancellation):
                for index in (count() if self.policy.account_budget_only else range(self.policy.max_calls)):
                    self._check()
                    incoming = self._mail()
                    if incoming:
                        self.messages.append({"role": "user", "content": "Worker messages (untrusted task data):\n" + json.dumps(incoming)})
                    value = yield from self._step(self.model, self.messages, f"completion:{index}", self.registry, self.cancellation,
                        searches_enabled=not (self.search_handoff and self.comparison and not self.comparison.comparisons))
                    if value.finish_reason in {"length", "max_tokens"}:
                        raise AnalysisBudgetExceeded("The model reached its output token limit. The available partial answer has been saved.")
                    self.messages.append(value.assistant_message())
                    if self._consensus_search_handoff(value):
                        continue
                    # Text accompanying another tool is planning/progress. Only
                    # a candidate answer or the synthesis sent to judge_answer
                    # opens a version; otherwise a narrated second comparison
                    # would incorrectly consume the revision limit.
                    synthesis = not value.tool_calls or any(
                        call.get("function", {}).get("name") in {"judge_answer", "check_contradictions"} for call in value.tool_calls)
                    if self.comparison and synthesis:
                        self.comparison.capture(value.text)
                    if value.tool_calls:
                        for call in value.tool_calls:
                            self.messages.append((yield from self._execute_stream(value, call)))
                        yield from self._events()
                        if not (self.comparison and self.comparison.finalized):
                            continue
                    with self.condition:
                        unfinished = any(not w.reviewed or w.inbox for w in self.workers.values())
                    if unfinished or self.mailbox:
                        # No unchecked result can silently become the final response.
                        self.messages.append({"role": "user", "content": "Before finalizing, resolve questions and verify each worker result or your own replacement with review_agent (use_fallback=true for a verified replacement). Preserve the original user's requested output format, without a workflow recap. Current sessions: " + json.dumps(self._summaries())})
                        continue
                    if self.comparison and self.comparison.comparisons:
                        if not self.comparison.finalized:
                            # A missing call never silently becomes success;
                            # chat can keep trying within its account budget.
                            missing_judge_calls += 1
                            if not self.policy.account_budget_only and missing_judge_calls > 1:
                                raise AnalysisBudgetExceeded("The model did not perform the required answer review.")
                            tool = "check_contradictions" if self.comparison.contradictions and self.comparison.review else "judge_answer"
                            self.messages.append({"role": "user", "content": f"The synthesis is visible. Call {tool} now for that exact answer; do not repeat it."})
                            continue
                        self.completion.text = self.comparison.text
                        self.completion.finish_reason = "stop"
                    else:
                        self.completion.text, self.completion.finish_reason = value.text, value.finish_reason
                    status = "succeeded"
                    break
                else:
                    raise AnalysisBudgetExceeded("Agent orchestration call limit reached")
        except ProviderCancelled:
            if self.watch_error:
                self.completion.failure = agent_failure(self.watch_error)
                raise self.watch_error
            status = "cancelled"
            raise
        except GeneratorExit:
            status = "cancelled"
            raise
        except Exception as exc:
            self.completion.failure = agent_failure(exc)
            raise
        finally:
            self.closed.set()
            for worker in self.workers.values():
                worker.cancellation.cancel()
            with self.condition:
                self.condition.notify_all()
            for worker in self.workers.values():
                worker.thread.join()
            watcher.join()
            # Provider threads are joined; retain and retry their original
            # measurements before finalizing. Never rerun a paid model step.
            for step, (value, step_status) in list(self.unsettled.items()):
                self._settle_step(step, value, step_status)
            self.completion.usage = self.costs.total()
            self.status("run", "finished", status=status, finish_reason=self.completion.finish_reason)
            if self.claimed:
                self.store.finish_run(self.uid, self.chat_id, self.turn_id, completion=self.completion,
                                      status=status, run_token=self.run_token)
            else:
                self.store.release_unclaimed(self.uid, self.chat_id, self.turn_id, failure=getattr(self.completion, "failure", None))
        yield from self._events()
        yield self.activity({"step_id": "run", "id": "usage", "kind": "usage", "usage": self.completion.usage})
