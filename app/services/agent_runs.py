"""Agent turn orchestration and idempotent shadow accounting.

Each paid step has a durable llm_calls receipt. Claims are never re-executed,
even after a process crash. Receipts contain no prompts or answers. Account
totals and settlement commit together; chat deletion cannot erase incurred
usage and account tombstones prevent resurrecting a deleted user.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import re

from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.services import persistence_guard, prompt_config
from app.services import agent_quota
from app.services.agent_runtime import AgentCapacityExceeded
from app.services.agent_sessions import AgentSessionStore, review_tail
from app.services.chat_store import ChatStore, ChatNotFound, TurnStatusConflict, TURN_PAGE_SIZE_MAX, normalize_turn_sources
from app.services.llm.agent_client import AgentModel
from app.services.llm.base import get_date_context


CONTEXT_CHAR_LIMIT = 120_000
# A chat longer than CONTEXT_CHAR_LIMIT keeps its newest messages. The oldest
# leave in steps of this many messages, so the replayed history starts at the
# same message for a while and providers keep serving it from the prompt cache.
HISTORY_STEP_TURNS = 4
HISTORY_OMITTED_NOTE = ("Earlier messages of this chat are not included: the chat is longer than what is sent to the model. "
                        "If the user refers to something you cannot see, say so.")
# The answer of a turn that broke off before its answer, where its work
# record follows (agent_compaction.work_record): the next message, mostly
# "Retry" with the same question, goes on from that work.
FAILED_TURN_RESUME = ("[This previous turn did not finish successfully. No assistant answer was saved. The work "
                      "record below lists what it already did: build on it instead of repeating it, and run "
                      "again only what you need fresh.]")
OWNER_CONCURRENT_RUNS = 2
RUN_LEASE_SECONDS = 300
# The saved activity of one turn, as UTF-8 JSON, within the turn document's
# 1 MiB next to the answer and its review (agent_comparison: up to 600 kB).
# Only a long VM run comes near it (one event per command, each with its
# output's end). It takes what the rest of the turn leaves, less a margin for
# Firestore's own per-field overhead: a turn that outgrows the document fails
# finish_run, and the answer is lost.
TURN_DOCUMENT_BYTES = 1_048_576
TURN_DOCUMENT_MARGIN = 64_000
ACTIVITY_MAX_BYTES = 600_000
ACTIVITY_SHORT_CHARS = 200
PLAN_ITEM_SHORT_CHARS = 60
# A model call's own times on its receipt (settle).
REQUEST_TIMES = ("request_started_at", "first_token_at", "stream_ended_at")
# What the conversation needs of an earlier turn (messages): not its
# activity, review or work log, which take up to about a megabyte.
HISTORY_FIELDS = ("status", "question", "assistant_response", "consensus", "app_context",
                  "agent_work_record", "sources", "agent_answer_fixed_at", "agent_history_summary")


def in_history(turn):
    """Whether the next message reads ``turn``: finished, or its answer fixed
    while its reviewers still work (hand_over), which does not change it."""
    return turn.get("status") in {"completed", "failed"} or review_tail(turn)


class ConversationTooLong(ValueError):
    """The newest message alone does not fit the selected model's window."""


def history_start(sizes, budget):
    """Index of the oldest earlier message the context keeps.

    The smallest cut that fits, rounded up to a multiple of
    HISTORY_STEP_TURNS while that still keeps a message."""
    rest, cut = sum(sizes), 0
    while cut < len(sizes) and rest > budget:
        rest -= sizes[cut]
        cut += 1
    if not cut:
        return 0
    stepped = -(-cut // HISTORY_STEP_TURNS) * HISTORY_STEP_TURNS
    return stepped if stepped < len(sizes) else cut


def json_bytes(value):
    """Size of ``value`` as UTF-8 JSON, what a Firestore document holds."""
    return len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"))


def activity_budget(turn, patch):
    """Bytes the activity may take next to everything else the turn keeps."""
    rest = {key: value for key, value in {**turn, **patch}.items() if key != "agent_activity"}
    return max(0, min(ACTIVITY_MAX_BYTES, TURN_DOCUMENT_BYTES - TURN_DOCUMENT_MARGIN - json_bytes(rest)))


def bounded_activity(activity, limit=None):
    """``activity`` as saved: within ``limit`` bytes of UTF-8 JSON (default
    ACTIVITY_MAX_BYTES). Opened pages lose their picture first (``preview``,
    their card keeps title and address), then the oldest events lose their VM output
    (``output_truncated``) and their thinking's sections, then their
    long texts and plan steps are shortened; the events and their order
    stay. Only when that is not enough
    do the oldest events go: the answer never does."""
    limit = ACTIVITY_MAX_BYTES if limit is None else limit
    size = json_bytes(activity)
    if size <= limit:
        return activity
    events = [dict(event) for event in activity]
    for event in events:
        if size <= limit:
            return events
        if event.get("preview"):
            before = json_bytes(event)
            del event["preview"]
            size -= before - json_bytes(event)
    for shorten in (False, True):
        for event in events:
            if size <= limit:
                return events
            before = json_bytes(event)
            if not shorten and event.get("output"):
                event["output"], event["output_truncated"] = "", True
            elif not shorten and event.get("sections"):
                # A step's thinking (ReasoningProgress.sections) keeps its line.
                del event["sections"]
            elif shorten:
                for key in ("text", "command"):
                    value = event.get(key)
                    if isinstance(value, str) and len(value) > ACTIVITY_SHORT_CHARS:
                        event[key] = value[:ACTIVITY_SHORT_CHARS - 1] + "…"
                if isinstance(event.get("items"), list):
                    event["items"] = [{**item, "content": item["content"][:PLAN_ITEM_SHORT_CHARS - 1] + "…"}
                                      if isinstance(item, dict) and isinstance(item.get("content"), str)
                                      and len(item["content"]) > PLAN_ITEM_SHORT_CHARS else item
                                      for item in event["items"]]
            size -= before - json_bytes(event)
    while events and size > limit:
        size -= json_bytes(events.pop(0)) + 1
    return events


def agent_sources(completion, review=None):
    """Keep provider/search citations on the canonical turn, across all steps."""
    sources = list(getattr(completion, "sources", []) or [])
    for event in completion.activity:
        sources.extend(event.get("sources") or [])
    for comparison in (review or {}).get("comparisons", []):
        for answer in comparison.get("answers", []):
            sources.extend(answer.get("sources") or [])
    return normalize_turn_sources(sources)


# Volatile per-message context (clock to the second, selected model; from
# DelegationLoop the chat's file list and this message's Google selection)
# travels with the newest user message instead of the system prompt. The system prompt
# and the replayed history then stay byte-identical across a chat's messages,
# so providers can serve them from their prompt cache. A clock at the top of
# the system prompt would invalidate every cached token after it on every message.
# The history repeats an earlier question with the context it was sent with
# (the turn's ``app_context``): with OpenRouter's search tool a Claude request
# caches only at its very end, so the next message reads the previous one's
# first step only if it starts with exactly that prompt (live probe 2026-10-23,
# docs/codebase-map.md "Feste Cache-Punkte").
APP_CONTEXT_OPEN = "[consens.io context for this message, supplied by the app, not written by the user]"
APP_CONTEXT_CLOSE = "[end of app context]"


def get_agent_turn_context(model=None, config=None, device_timezone=None):
    """``device_timezone``: the zone the user's browser reported (AgentRequest),
    else the app's reference zone."""
    config = config or prompt_config.get_config()
    context = get_date_context(device_timezone or config["reference_timezone"], device=bool(device_timezone))
    if model is not None:
        context += f"\nSelected model for this response: {model.label} ({model.model})."
    return context


def with_app_context(question, context):
    return f"{APP_CONTEXT_OPEN}\n{context}\n{APP_CONTEXT_CLOSE}\n\n{question}"


def add_app_context(content, context):
    """``content`` with ``context`` as the last lines of its app context
    (one built by ``with_app_context``); a message without one gets it."""
    if isinstance(content, str) and content.startswith(APP_CONTEXT_OPEN):
        head, separator, rest = content.partition(f"\n{APP_CONTEXT_CLOSE}\n\n")
        if separator:
            return f"{head}\n{context}{separator}{rest}"
    return with_app_context(content, context)


def strip_app_context(content):
    """The user's own words of a message built by ``with_app_context``."""
    if isinstance(content, str) and content.startswith(APP_CONTEXT_OPEN):
        _, separator, rest = content.partition(APP_CONTEXT_CLOSE + "\n\n")
        if separator:
            return rest
    return content


class AgentRunStore(AgentSessionStore, ChatStore):
    def repair_quota_period(self, uid, day):
        ref = agent_quota.quota_ref(self.db, uid, day)
        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            previous = ref.get(transaction=tx).to_dict() or {}
            corrected = agent_quota.normalize(previous)
            if corrected != previous:
                tx.set(ref, corrected)
            return corrected
        return self._agent_transaction(uid, operation)

    def recover_allowance(self, uid):
        # Expired roots can outlive the owner's active lease map. Query their
        # durable run state, including when the user never reopens that bookmark.
        roots = self.db.collection('users').document(uid).collection('llm_calls').where(
            filter=FieldFilter('run_status', '==', 'running')).where(
            filter=FieldFilter('policy.delegation', '==', True)).limit(20).stream()
        now = datetime.now(timezone.utc)
        running = 0
        for snapshot in roots:
            running += 1
            root = snapshot.to_dict() or {}
            lease = root.get('lease_until')
            if (isinstance(lease, datetime) and lease <= now and (root.get('policy') or {}).get('delegation')
                    and root.get('chat_id') and root.get('turn_id')):
                self.reap_delegation(uid, root['chat_id'], root['turn_id'])
        # Whether any delegation root is still running (the caller may then
        # skip asking again for a while when there is none).
        return running

    def active_ref(self, uid):
        return self.db.collection("users").document(uid).collection("chat_state").document("agent_runs")

    def receipt_ref(self, uid, chat_id, turn_id, step="completion:0"):
        if not re.fullmatch(r"(?:completion|agent:[a-f0-9]{32}):(?:0|[1-9][0-9]*)", step):
            raise ValueError("Invalid agent step")
        key = hashlib.sha256(f"agent\0{chat_id}\0{turn_id}\0{step}".encode()).hexdigest()
        return self.db.collection("users").document(uid).collection("llm_calls").document(key)

    def history_page(self, uid, chat_id, cursor="", *, checked=False):
        """One page of a chat's turns as messages reads them (HISTORY_FIELDS).
        The Agent route reads the first while it creates the turn."""
        return self._list_turn_snapshots(uid, chat_id, cursor=cursor, limit=TURN_PAGE_SIZE_MAX,
                                         fields=HISTORY_FIELDS, checked=checked)

    @staticmethod
    def history_current(page, target):
        """Whether ``page``, read before ``target`` was created, still holds
        every earlier turn as it is: none of them pending (one that finished
        or was swept in between is read again), all of them there (a single
        page). Else messages reads its own."""
        earlier = [(s.to_dict() or {}) for s in page["snapshots"]]
        earlier = [turn for turn in earlier if turn.get("position", 0) < target["position"]]
        return (all(in_history(turn) for turn in earlier)
                and (page.get("has_more") or len(earlier) == target["position"] - 1))

    def messages(self, uid, chat_id, target, model=None, config=None, sources=None, context=None, first_page=None,
                 history_chars=None, summary=None):
        """The conversation for the target turn. ``sources``, a list, receives
        the saved sources of the earlier turns it includes (read_source may
        open them; agent_read_source, "Sources from the chat itself").
        ``context``: the app context the target turn was created with
        (create_turn ``app_context``); an earlier turn's question comes back
        with its own, so the prompt continues the one that turn first sent.
        ``first_page``: history_page read beside the turn's creation, used
        where history_current says it still holds.

        A chat longer than CONTEXT_CHAR_LIMIT keeps its newest messages
        (history_start) and tells the model so in this message's app context.
        ``history_chars`` keeps less: a Watch's scheduled run reads only its
        chat's newest messages (agent_watches.HISTORY_CHARS).

        A turn that worked in its VM is followed by its work record
        (``agent_work_record``, agent_compaction.work_record) as an app
        message, exactly as saved: what the agent did there, which question
        and answer alone do not say.

        The newest saved summary of the history (``agent_history_summary``
        of an earlier turn, agent_compaction "Summaries") stands for the
        messages it covers, exactly as saved; their sources stay openable.
        ``summary``, a dict, receives the plan of the next one once the
        history since passes HISTORY_SUMMARY_ABOVE_CHARS (DelegationLoop
        writes it in its first step): ``end``, the index where the messages
        that stay word for word begin, ``through``, the position of the last
        message it covers, ``turns`` and ``partial``. A Watch's scheduled run
        (``history_chars``) neither reads nor plans one."""
        from app.services import agent_compaction
        config = config or prompt_config.get_config()
        system_prompt = config["prompts"]["agent"]
        messages = [{"role": "system", "content": system_prompt}]
        earlier = []
        # The newest saved summary of the history and its turn's position.
        saved_summary, summary_at = None, -1
        cursor = ""
        while True:
            # Agent answers live on the turn itself. Do not issue an empty
            # model_answers subcollection query for every message in history.
            if not cursor and first_page is not None and self.history_current(first_page, target):
                page = first_page
            else:
                page = self.history_page(uid, chat_id, cursor)
            for snapshot in page["snapshots"]:
                turn = snapshot.to_dict() or {}
                if turn["position"] >= target["position"] or not in_history(turn):
                    continue
                question, answer = turn["question"], turn.get("assistant_response", turn.get("consensus", ""))
                if isinstance(turn.get("app_context"), str) and turn["app_context"]:
                    question = with_app_context(question, turn["app_context"])
                record = turn.get("agent_work_record")
                if turn["status"] == "failed":
                    # Match the visible saved conversation without claiming that
                    # an interrupted answer or its review completed successfully.
                    # With a work record (after any broken-off run with tool
                    # calls) the next attempt builds on it.
                    answer = ("[This previous turn did not finish successfully. The saved response below may be incomplete or unreviewed.]\n\n" + answer
                              if answer else FAILED_TURN_RESUME if isinstance(record, str) and record
                              else "[This previous turn did not finish successfully. No assistant answer was saved.]")
                earlier.append((turn["position"], question, answer, turn.get("sources") or [],
                                record if isinstance(record, str) else ""))
                found = turn.get("agent_history_summary")
                if (isinstance(found, dict) and agent_compaction.is_summary(found.get("content"))
                        and type(found.get("through")) is int and turn["position"] > summary_at):
                    saved_summary, summary_at = found, turn["position"]
            cursor = page.get("next_cursor") or ""
            if not cursor:
                break
        if history_chars:
            saved_summary = None
        budget = CONTEXT_CHAR_LIMIT - len(system_prompt) - len(target["question"])
        if saved_summary is not None:
            budget -= len(saved_summary["content"])
            messages.append({"role": "user", "content": saved_summary["content"]})
            covered = [item for item in earlier if item[0] <= saved_summary["through"]]
            earlier = [item for item in earlier if item[0] > saved_summary["through"]]
            if sources is not None:
                # Covered by the summary, their sources stay openable (read_source).
                for item in covered:
                    sources.extend(source for source in item[3] if isinstance(source, dict))
        sizes = [len(question) + len(answer) + len(record) for _, question, answer, _, record in earlier]
        start = history_start(sizes, min(budget, history_chars) if history_chars else budget)
        starts = []
        for _, question, answer, saved, record in earlier[start:]:
            starts.append(len(messages))
            messages.extend([{"role": "user", "content": question},
                             {"role": "assistant", "content": answer}])
            if record:
                messages.append({"role": "user", "content": record})
            if sources is not None:
                sources.extend(source for source in saved if isinstance(source, dict))
        replayed = sizes[start:]
        held = sum(replayed) + (len(saved_summary["content"]) if saved_summary is not None else 0)
        if summary is not None and not history_chars and held > agent_compaction.HISTORY_SUMMARY_ABOVE_CHARS:
            keep = agent_compaction.history_keep(replayed)
            if keep < len(replayed):
                summary.update({
                    "end": starts[len(replayed) - keep], "through": earlier[start:][len(replayed) - keep - 1][0],
                    "turns": len(replayed) - keep,
                    "partial": bool(start) or (saved_summary is not None
                                               and agent_compaction.HISTORY_SUMMARY_PARTIAL in saved_summary["content"])})
        context = context or get_agent_turn_context(model, config)
        if start:
            # The newest message's context changes every message anyway, so
            # the note costs no cached prefix.
            context += "\n" + HISTORY_OMITTED_NOTE
        messages.append({"role": "user", "content": with_app_context(target["question"], context)})
        from app.services.agent_tokens import input_estimate, minimum_output
        if model and input_estimate(messages, request_config=model.request_config) + minimum_output(model) > model.context_length:
            raise ConversationTooLong("This conversation is too long for the selected model. Choose a model with a larger context or start a new chat.")
        return messages

    def claim(self, uid, chat_id, turn_id, model: AgentModel, *, step="completion:0", run_token="", policy=None, reservation=None,
              overdraft=False):
        if reservation is not None:
            return self._claim_delegated(uid, chat_id, turn_id, model, step=step, run_token=run_token,
                                         policy=policy, reservation=reservation, overdraft=overdraft)
        receipt_ref = self.receipt_ref(uid, chat_id, turn_id, step)
        root_ref = self.receipt_ref(uid, chat_id, turn_id)
        index = int(step.split(":")[1])
        previous_ref = self.receipt_ref(uid, chat_id, turn_id, f"completion:{index - 1}") if index else None
        chat_ref, turn_ref = self._chat_ref(uid, chat_id), self._turn_ref(uid, chat_id, turn_id)
        user_ref = self.db.collection("users").document(uid)
        active_ref = self.active_ref(uid)

        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            receipt = receipt_ref.get(transaction=tx)
            chat = chat_ref.get(transaction=tx)
            turn = turn_ref.get(transaction=tx)
            user = user_ref.get(transaction=tx)
            active = active_ref.get(transaction=tx)
            root = root_ref.get(transaction=tx) if index else receipt
            previous = previous_ref.get(transaction=tx) if previous_ref else None
            if not chat.exists or not turn.exists or (chat.to_dict() or {}).get("status") != "active":
                raise ChatNotFound("Chat not found")
            if receipt.exists:
                return False
            chat_data, turn_data = chat.to_dict() or {}, turn.to_dict() or {}
            if (chat_data.get("execution_mode") != "agent" or turn_data.get("execution_mode") != "agent"
                    or turn_data.get("status") != "pending" or chat_data.get("agent_turn_id") != turn_id
                    or chat_data.get("agent_lock_until") <= datetime.now(timezone.utc)):
                raise TurnStatusConflict("Agent turn is no longer runnable")
            now = datetime.now(timezone.utc)
            leases = {key: expires for key, expires in ((active.to_dict() or {}).get("leases") or {}).items()
                      if isinstance(expires, datetime) and expires > now}
            if index:
                root_data = root.to_dict() or {}
                previous_data = previous.to_dict() or {}
                if (not run_token or root_data.get("run_token") != run_token or root_data.get("run_status") != "running"
                        or root_data.get("last_step") != f"completion:{index - 1}"
                        or previous_data.get("status") != "succeeded" or root_ref.id not in leases
                        or index >= (root_data.get("policy") or {}).get("max_calls", 1)):
                    raise TurnStatusConflict("Agent step is not authorized to continue")
            elif len(leases) >= OWNER_CONCURRENT_RUNS:
                raise AgentCapacityExceeded("Two agent responses are already running. Wait for one to finish.")
            else:
                leases[root_ref.id] = now + timedelta(seconds=RUN_LEASE_SECONDS)
            totals = dict((user.to_dict() or {}).get("agent_usage") or {})
            totals["calls"] = totals.get("calls", 0) + 1
            totals["unsettled_calls"] = totals.get("unsettled_calls", 0) + 1
            totals.update(currency="USD", billing_mode="simulation")
            tx.set(receipt_ref, {
                "schema_version": 2, "purpose": "agent", "step": step,
                "chat_id": chat_id, "turn_id": turn_id, "status": "running",
                "model": model.snapshot(), "created_at": firestore.SERVER_TIMESTAMP,
                **({"run_token": run_token, "run_status": "running", "last_step": step,
                    "policy": policy or {}} if not index else {}),
            })
            if index:
                tx.update(root_ref, {"last_step": step})
            else:
                tx.update(chat_ref, {"agent_lock_until": now + timedelta(seconds=RUN_LEASE_SECONDS)})
            tx.set(active_ref, {"leases": leases})
            if user.exists:
                tx.update(user_ref, {"agent_usage": totals})
            else:
                tx.set(user_ref, {"agent_usage": totals})
            return True

        return self._agent_transaction(uid, operation)

    def _expected_daily(self, uid):
        """The ledger document a claim of now books into (agent_quota.period_key
        of the cached budget configuration), or None when it cannot be told:
        the settlement then reads the receipt's own day on its own."""
        try:
            from app.services import agent_budget_config
            return agent_quota.quota_ref(self.db, uid, agent_quota.period_key(agent_budget_config.get_config(self.db)))
        except Exception:
            return None

    def settle(self, uid, chat_id, turn_id, *, completion, status, step="completion:0", final=True):
        if status not in {"succeeded", "failed", "cancelled"}:
            raise ValueError("Invalid agent settlement status")
        receipt_ref = self.receipt_ref(uid, chat_id, turn_id, step)
        chat_ref, turn_ref = self._chat_ref(uid, chat_id), self._turn_ref(uid, chat_id, turn_id)
        user_ref = self.db.collection("users").document(uid)
        active_ref = self.active_ref(uid)
        root_ref = self.receipt_ref(uid, chat_id, turn_id)
        # The ledger day a claim of now books into (_claim_delegated): read
        # in the same round trip as the rest, it is almost always the
        # receipt's own, which spares every settlement a second round trip
        # under the account's lock.
        expected_daily = self._expected_daily(uid)

        def operation(tx):
            # One round trip for all of them (_read_all), the expected ledger
            # day included; the receipt names the day it books into. Chat,
            # turn and the account's running responses only for a final
            # settlement: a step's with final=False (every step of a
            # delegated run) touches none of them.
            tombstone, receipt, root, *rest = self._read_all(tx, (
                persistence_guard.deletion_ref(self.db, uid), receipt_ref, root_ref,
                *((chat_ref, turn_ref, active_ref) if final else ()),
                *([expected_daily] if expected_daily is not None else [])))
            chat, turn, active = rest[:3] if final else (None, None, None)
            guessed = rest[3:] if final else rest
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx, snapshot=tombstone)
            if not receipt.exists:
                raise ChatNotFound("Agent receipt not found")
            if (receipt.to_dict() or {}).get("status") != "running":
                return False
            root_data = (receipt if step == "completion:0" else root).to_dict() or {}
            receipt_data = receipt.to_dict() or {}
            daily_ref = (agent_quota.quota_ref(self.db, uid, receipt_data["quota_day"])
                         if receipt_data.get("quota_day") else None)
            if daily_ref is None:
                daily = None
            elif guessed and daily_ref.path == expected_daily.path:
                daily = guessed[0].to_dict()
            else:
                # A call claimed before midnight or a reset: its own day.
                daily = daily_ref.get(transaction=tx).to_dict()
            usage = completion.usage
            # A receipt without a ledger day (a claim without a reservation,
            # the plain AgentLoop) still counts on the user document; every
            # other call in its day's ledger (agent_quota.count_claim).
            user = user_ref.get(transaction=tx) if daily_ref is None else None
            estimate = None
            if daily_ref:
                tx.set(daily_ref, agent_quota.count_settlement(
                    agent_quota.settle(daily, receipt_data["quota_reserved"], usage,
                                       measurable=bool(completion.generation_id)), usage))
                estimate = agent_quota.unknown_estimate(receipt_data["quota_reserved"], usage)
            elif user.exists:
                ledger = agent_quota.count_settlement({"agent_usage": (user.to_dict() or {}).get("agent_usage")}, usage)
                tx.update(user_ref, {"agent_usage": {**ledger["agent_usage"], "updated_at": firestore.SERVER_TIMESTAMP}})
            if final:
                leases = dict((active.to_dict() or {}).get("leases") or {})
                leases.pop(self.receipt_ref(uid, chat_id, turn_id).id, None)
                tx.set(active_ref, {"leases": leases})
            receipt_patch = {
                "status": status, "usage": usage,
                "usage_status": "unavailable" if usage is None else "measured" if usage.get("complete", True) else "partial",
                "generation_id": completion.generation_id, "finish_reason": completion.finish_reason,
                "settled_at": firestore.SERVER_TIMESTAMP,
            }
            if getattr(completion, "search_hits", None) is not None:
                # The pages a step that searched kept (agent_client._record_missing_citations).
                receipt_patch["search_hits"] = completion.search_hits
            for field in REQUEST_TIMES:
                # When the request left, its first token came and its stream
                # ended (AgentCompletion.stream): between created_at
                # and settled_at, the provider's part and ours.
                if isinstance(getattr(completion, field, None), datetime):
                    receipt_patch[field] = getattr(completion, field)
            if isinstance(getattr(completion, "endpoint", None), str) and completion.endpoint:
                # Which endpoint served the request (the stream's
                # ``provider``): what a failed step's retry avoids, and where
                # a model's slow or declined steps ran.
                receipt_patch["endpoint"] = completion.endpoint
            review_round = getattr(completion, "review_round", None)
            if isinstance(review_round, str) and review_round:
                # A reviewer's call: live, gate, final, repair
                # or hedge (agent_audit; DelegationLoop.worker_completion).
                receipt_patch["round"] = review_round
            charged = agent_quota.measured_charge(usage)
            if daily_ref and charged is not None:
                # What the account was charged, in micro-euros.
                receipt_patch["quota_charged"] = charged
            if estimate is not None:
                # Bounded uncertainty: the ledger now carries this estimate.
                # Only a provider generation id makes later measurement possible.
                receipt_patch.update(
                    quota_estimate=estimate,
                    quota_reconcile="pending" if completion.generation_id else "final",
                    quota_reconcile_attempts=0,
                )
            tx.update(receipt_ref, receipt_patch)
            delegated = self._delegated_settlement(root_data, step, status, usage)
            if delegated:
                tx.update(root_ref, delegated)
            chat_data = (chat.to_dict() or {}) if final else {}
            if final and chat.exists and turn.exists and chat_data.get("status") == "active":
                if (turn.to_dict() or {}).get("status") == "pending":
                    patch = {"status": "completed" if status == "succeeded" else "failed",
                             "updated_at": firestore.SERVER_TIMESTAMP}
                    patch.update(agent_usage=usage,
                                 agent_finish_reason=completion.finish_reason,
                                 agent_reasoning_truncated=completion.reasoning_truncated,
                                 sources=agent_sources(completion))
                    if status == "succeeded":
                        # Legacy history/rendering contract; execution_mode is
                        # authoritative and no consensus computation took place.
                        patch.update(assistant_response=completion.text, completed_at=firestore.SERVER_TIMESTAMP,
                                     differences="", differences_data=None, included_models=[])
                    else:
                        patch["error_code"] = "cancelled" if status == "cancelled" else "agent_failed"
                        patch["failed_at"] = firestore.SERVER_TIMESTAMP
                    patch["agent_activity"] = bounded_activity(
                        completion.activity, activity_budget(turn.to_dict() or {}, patch))
                    tx.update(turn_ref, patch)
                if chat_data.get("agent_turn_id") == turn_id:
                    tx.update(chat_ref, {"agent_lock_until": datetime.now(timezone.utc),
                                         "updated_at": firestore.SERVER_TIMESTAMP})
            return True

        return self._agent_transaction(uid, operation)

    def hand_over(self, uid, chat_id, turn_id, *, run_token, completion):
        """The answer is fixed and only its review is left (agent_audit): the
        chat is free for its next message from here on (DelegationLoop._hand_over).

        The turn stays ``pending`` until the reviewers are done (finish_run),
        but says since when its answer stands (``agent_answer_fixed_at``,
        agent_sessions.review_tail) and already carries what the next message
        reads of it (answer, sources, work record, messages). The chat's lock
        ends, and the run gives up its place among the account's running
        responses. False when the run no longer holds the chat (stopped,
        reaped): it then ends through finish_run alone."""
        root_ref = self.receipt_ref(uid, chat_id, turn_id)
        chat_ref, turn_ref, active_ref = self._chat_ref(uid, chat_id), self._turn_ref(uid, chat_id, turn_id), self.active_ref(uid)

        def operation(tx):
            tombstone, root, chat, turn, active = self._read_all(tx, (
                persistence_guard.deletion_ref(self.db, uid), root_ref, chat_ref, turn_ref, active_ref))
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx, snapshot=tombstone)
            data, chat_data, turn_data = root.to_dict() or {}, chat.to_dict() or {}, turn.to_dict() or {}
            if (not run_token or data.get("run_token") != run_token or data.get("run_status") != "running"
                    or data.get("cancel_requested") or chat_data.get("status") != "active"
                    or chat_data.get("agent_turn_id") != turn_id or turn_data.get("status") != "pending"):
                return False
            patch = {"agent_answer_fixed_at": firestore.SERVER_TIMESTAMP, "updated_at": firestore.SERVER_TIMESTAMP,
                     "assistant_response": completion.text,
                     "sources": agent_sources(completion, turn_data.get("agent_review"))}
            if getattr(completion, "work_record", None):
                patch["agent_work_record"] = completion.work_record
            if getattr(completion, "vm", None):
                patch["agent_vm"] = completion.vm
            tx.update(turn_ref, patch)
            chat_patch = {"agent_lock_until": datetime.now(timezone.utc), "updated_at": firestore.SERVER_TIMESTAMP}
            if isinstance(getattr(completion, "workspace_used", None), bool):
                chat_patch["agent_workspace_used"] = completion.workspace_used
            tx.update(chat_ref, chat_patch)
            leases = dict((active.to_dict() or {}).get("leases") or {})
            if leases.pop(root_ref.id, None) is not None:
                tx.set(active_ref, {"leases": leases})
            return True

        return self._agent_transaction(uid, operation)

    def save_history_summary(self, uid, chat_id, turn_id, *, run_token, summary):
        """The summary of the chat's history this turn's first step wrote
        (DelegationLoop._summarize): saved on the turn right away, so later
        messages start with it (messages) also when this one fails. False
        when the run no longer holds the turn."""
        root_ref, turn_ref = self.receipt_ref(uid, chat_id, turn_id), self._turn_ref(uid, chat_id, turn_id)

        def operation(tx):
            tombstone, root, turn = self._read_all(tx, (persistence_guard.deletion_ref(self.db, uid), root_ref, turn_ref))
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx, snapshot=tombstone)
            data = root.to_dict() or {}
            if (not run_token or data.get("run_token") != run_token or data.get("run_status") != "running"
                    or not turn.exists or (turn.to_dict() or {}).get("status") != "pending"):
                return False
            tx.update(turn_ref, {"agent_history_summary": summary})
            return True

        return self._agent_transaction(uid, operation)

    def finish_run(self, uid, chat_id, turn_id, *, completion, status, run_token):
        """End the run once, independently of each paid step's settlement."""
        if status not in {"succeeded", "failed", "cancelled"}:
            raise ValueError("Invalid agent run status")
        root_ref = self.receipt_ref(uid, chat_id, turn_id)
        chat_ref, turn_ref = self._chat_ref(uid, chat_id), self._turn_ref(uid, chat_id, turn_id)
        active_ref = self.active_ref(uid)

        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            root, chat, turn, active = (ref.get(transaction=tx) for ref in (root_ref, chat_ref, turn_ref, active_ref))
            data = root.to_dict() or {}
            if not run_token or data.get("run_token") != run_token:
                raise TurnStatusConflict("Agent run owner does not match")
            if data.get("run_status") != "running":
                return False
            last = self.receipt_ref(uid, chat_id, turn_id, data["last_step"]).get(transaction=tx).to_dict() or {}
            if (last.get("status") == "running" or "running" in data.get("step_states", {}).values()
                    or (status == "succeeded" and last.get("status") != "succeeded")):
                raise TurnStatusConflict("Agent step has not settled")
            # The review ends below as the reviewers left it (agent_audit.py).
            review = (turn.to_dict() or {}).get("agent_review")
            closed = {"run_status": status, "finished_at": firestore.SERVER_TIMESTAMP}
            if not chat.exists or (chat.to_dict() or {}).get("status") != "active":
                # The chat went while the run still wrote (a temporary chat
                # left mid-run): the texts its deletion took
                # from this receipt (chat_store.RUN_RECEIPT_TEXT_FIELDS) do not
                # stay because the run outlived it by a few seconds.
                from app.services.chat_store import RUN_RECEIPT_TEXT_FIELDS
                closed.update({name: firestore.DELETE_FIELD for name in RUN_RECEIPT_TEXT_FIELDS if name in data})
            tx.update(root_ref, closed)
            leases = dict((active.to_dict() or {}).get("leases") or {})
            leases.pop(root_ref.id, None)
            tx.set(active_ref, {"leases": leases})
            chat_data, turn_data = chat.to_dict() or {}, turn.to_dict() or {}
            if chat.exists and turn.exists and chat_data.get("status") == "active" and turn_data.get("status") == "pending":
                # An answer that already stands (hand_over) stays the answer
                # when its reviewers' run ends otherwise (the reaper after a
                # hard kill): the user took it and may have gone on. Only its
                # review ends unfinished. The reaper's completion is empty, so
                # the handed-over text and sources stay.
                fixed = status != "succeeded" and review_tail(turn_data)
                sources = agent_sources(completion, review)
                if fixed:
                    sources = normalize_turn_sources([*(turn_data.get("sources") or []), *sources])
                patch = {"status": "completed" if status == "succeeded" or fixed else "failed", "updated_at": firestore.SERVER_TIMESTAMP,
                         "agent_usage": completion.usage,
                         "agent_finish_reason": completion.finish_reason,
                         "agent_reasoning_truncated": completion.reasoning_truncated,
                         "sources": sources}
                if getattr(completion, "vm", None):
                    # The Agent VM's summary (agent_vm_tools.VMSession.summary):
                    # the message's checkpoint and the commands' run time.
                    patch["agent_vm"] = completion.vm
                if getattr(completion, "work_record", None):
                    # What the next message is told this one did (messages).
                    patch["agent_work_record"] = completion.work_record
                if getattr(completion, "holds", None):
                    # The turn's pauses (DelegationLoop._end_hold): kind, gate,
                    # ask, domain, reviewer, decision and seconds, no reasons.
                    patch["agent_holds"] = completion.holds
                if isinstance(getattr(completion, "wrap_up", None), dict):
                    # Which limit ended its work (DelegationLoop._wrap_up):
                    # reason code, steps and seconds, no text.
                    patch["agent_wrap_up"] = completion.wrap_up
                if status == "succeeded" or fixed:
                    patch.update(assistant_response=completion.text or (turn_data.get("assistant_response") or "" if fixed else ""),
                                 completed_at=firestore.SERVER_TIMESTAMP,
                                 differences="", differences_data=None, included_models=[])
                    if status == "succeeded" and review and review.get("mode") == "audit" and review.get("status") in {"required", "running"}:
                        # A review (agent_audit.py) whose last saves failed: a
                        # finished answer never keeps "reviewing".
                        patch["agent_review"] = {**review, "status": "failed"}
                if status != "succeeded":
                    if not fixed:
                        patch.update(error_code="cancelled" if status == "cancelled" else "agent_failed", failed_at=firestore.SERVER_TIMESTAMP)
                        patch["agent_failure"] = getattr(completion, "failure", None) or {
                            "code": "cancelled" if status == "cancelled" else "agent_failed",
                            "error": "Response stopped. Available results have been saved." if status == "cancelled" else "The response could not be completed. Available results have been saved."}
                        # The streamed text is all there is: comparisons only
                        # advise, the answer is the agent's own.
                        if completion.text:
                            patch["assistant_response"] = completion.text
                    if review:
                        # A crash/stop cannot leave a saved review looking live.
                        # A review that had already finished keeps its result:
                        # a later failure (a final bookkeeping or provider step)
                        # must not relabel a reviewed answer as unreviewed
                        # ("off": reviewers the user's setting kept away).
                        review = dict(review)
                        if review.get("status") not in {"succeeded", "partial", "off"}:
                            review["status"] = ("cancelled" if status == "cancelled" else
                                                "missing" if review.get("status") == "required" else "failed")
                        for comparison in review.get("comparisons", []):
                            if comparison.get("status") == "running":
                                comparison["status"] = "cancelled" if status == "cancelled" else "failed"
                        audit = review.get("audit")
                        if isinstance(audit, dict) and isinstance(audit.get("reviewers"), list):
                            # Reviewers a crash or the reaper left at work
                            # (AnswerAudit.close never ran): none still is.
                            review["audit"] = {**audit, "reviewers": [
                                {**row, "status": "failed", "failure": {"code": "run_interrupted"}}
                                if isinstance(row, dict) and row.get("status") in {"waiting", "running"} else row
                                for row in audit["reviewers"]]}
                        # A pasted text's check of the retired check_text,
                        # still running on an older turn the reaper ends.
                        passage = review.get("passage_check")
                        if isinstance(passage, dict) and passage.get("status") in {"waiting", "running"}:
                            review["passage_check"] = {**passage, "status": "cancelled" if status == "cancelled" else "failed"}
                        # A page read (read_source) the run ended during.
                        review["read_sources"] = [
                            {**read, "status": "failed", "error": "stopped" if status == "cancelled" else "unavailable"}
                            if isinstance(read, dict) and read.get("status") == "running" else read
                            for read in review.get("read_sources") or []]
                        if not review["read_sources"]:
                            review.pop("read_sources")
                        patch["agent_review"] = review
                # Last: the activity takes the room the rest of the turn leaves.
                if completion.activity or not fixed:
                    patch["agent_activity"] = bounded_activity(completion.activity, activity_budget(turn_data, patch))
                tx.update(turn_ref, patch)
                # A chat that already runs its next message (hand_over) keeps
                # that message's state.
                owner = chat_data.get("agent_turn_id") == turn_id
                if owner and isinstance(getattr(completion, "workspace_used", None), bool):
                    # Whether the chat's next message starts with the workspace
                    # open (routers/agent.py, AGENT_WORKSPACE_ON_DEMAND).
                    tx.update(chat_ref, {"agent_workspace_used": completion.workspace_used})
                if owner:
                    tx.update(chat_ref, {"agent_lock_until": datetime.now(timezone.utc), "updated_at": firestore.SERVER_TIMESTAMP})
            return True

        return self._agent_transaction(uid, operation)

    def release_unclaimed(self, uid, chat_id, turn_id, *, failure=None, expired_only=False):
        """Failures before the provider claim consume neither tokens nor quota."""
        chat_ref, turn_ref = self._chat_ref(uid, chat_id), self._turn_ref(uid, chat_id, turn_id)
        receipt_ref = self.receipt_ref(uid, chat_id, turn_id)
        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            chat, turn, receipt = chat_ref.get(transaction=tx), turn_ref.get(transaction=tx), receipt_ref.get(transaction=tx)
            if receipt.exists or not chat.exists or not turn.exists:
                return
            data = chat.to_dict() or {}
            turn_data = turn.to_dict() or {}
            if (data.get("status") != "active" or turn_data.get("status") != "pending"
                    or data.get("execution_mode") != "agent" or turn_data.get("execution_mode") != "agent"):
                return
            owns_lock = data.get("agent_turn_id") == turn_id
            now = datetime.now(timezone.utc)
            if expired_only and owns_lock and data.get("agent_lock_until", now) > now:
                return
            tx.update(turn_ref, {"status": "failed", "error_code": "agent_failed",
                "agent_failure": failure or {"code": "agent_failed", "error": "This response ended before an answer was available."},
                "updated_at": firestore.SERVER_TIMESTAMP})
            if owns_lock:
                tx.update(chat_ref, {"agent_lock_until": now})
        self._agent_transaction(uid, operation)
