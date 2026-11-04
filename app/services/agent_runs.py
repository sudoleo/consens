"""Agent turn orchestration and idempotent shadow accounting.

Each paid step has a durable llm_calls receipt without prompts or answers, and claims are never
re-executed, even after a crash. Account totals and settlement commit together; chat deletion cannot
erase incurred usage and account tombstones prevent resurrecting a deleted user."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re

from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.services import persistence_guard, prompt_config
from app.services import agent_quota
from app.services.agent_sessions import AgentSessionStore, review_tail
from app.services.chat_store import ChatStore, ChatNotFound, TurnStatusConflict, TURN_PAGE_SIZE_MAX, normalize_turn_sources
from app.services.llm.base import get_date_context


CONTEXT_CHAR_LIMIT = 120_000
# The oldest messages leave in steps, so the replayed history starts at the same message for a while
# and stays in the prompt cache.
HISTORY_STEP_TURNS = 4
HISTORY_OMITTED_NOTE = ("Earlier messages of this chat are not included: the chat is longer than what is sent to the model. "
                        "If the user refers to something you cannot see, say so.")
# A turn that broke off before its answer: the next message, mostly "Retry", goes on from its work
# record.
FAILED_TURN_RESUME = ("[This previous turn did not finish successfully. No assistant answer was saved. The work "
                      "record below lists what it already did: build on it instead of repeating it, and run "
                      "again only what you need fresh.]")
OWNER_CONCURRENT_RUNS = 2
RUN_LEASE_SECONDS = 300
# The saved activity of one turn must fit the 1 MiB turn document next to the answer and review. It
# takes what the rest leaves, less a margin for Firestore's per-field overhead: a fixed budget let a
# long VM run outgrow the document and lose its answer.
TURN_DOCUMENT_BYTES = 1_048_576
TURN_DOCUMENT_MARGIN = 64_000
ACTIVITY_MAX_BYTES = 600_000
ACTIVITY_SHORT_CHARS = 200
PLAN_ITEM_SHORT_CHARS = 60
REQUEST_TIMES = ("request_started_at", "first_token_at", "stream_ended_at")
# What the conversation needs of an earlier turn: not its activity, review or work log, up to about
# a megabyte.
HISTORY_FIELDS = ("status", "question", "assistant_response", "consensus", "app_context",
                  "agent_work_record", "sources", "agent_answer_fixed_at", "agent_history_summary",
                  "agent_history_summary_failed")


def in_history(turn):
    """Whether the next message reads ``turn``: finished, or its answer fixed while its reviewers
    work."""
    return turn.get("status") in {"completed", "failed"} or review_tail(turn)


class ConversationTooLong(ValueError):
    """The newest message alone does not fit the selected model's window."""


def history_start(sizes, budget):
    """Index of the oldest earlier message the context keeps: the smallest cut that fits, rounded up
    to a multiple of HISTORY_STEP_TURNS while that keeps a message."""
    rest, cut = sum(sizes), 0
    while cut < len(sizes) and rest > budget:
        rest -= sizes[cut]
        cut += 1
    if not cut:
        return 0
    stepped = -(-cut // HISTORY_STEP_TURNS) * HISTORY_STEP_TURNS
    return stepped if stepped < len(sizes) else cut


def json_bytes(value):
    return len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"))


def activity_budget(turn, patch):
    rest = {key: value for key, value in {**turn, **patch}.items() if key != "agent_activity"}
    return max(0, min(ACTIVITY_MAX_BYTES, TURN_DOCUMENT_BYTES - TURN_DOCUMENT_MARGIN - json_bytes(rest)))


def bounded_activity(activity, limit=None):
    """``activity`` within ``limit`` bytes of UTF-8 JSON. Pictures go first, then the oldest events'
    VM output and thinking sections, then long texts and plan steps are shortened; only then do the
    oldest events go. The answer never does."""
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
                # A step's thinking keeps its line.
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
    """Keep provider and search citations on the canonical turn, across all steps."""
    sources = list(getattr(completion, "sources", []) or [])
    for event in completion.activity:
        sources.extend(event.get("sources") or [])
    for comparison in (review or {}).get("comparisons", []):
        for answer in comparison.get("answers", []):
            sources.extend(answer.get("sources") or [])
    return normalize_turn_sources(sources)


# Volatile per-message context travels with the newest user message, not the system prompt, so
# system prompt and history stay byte-identical across a chat's messages for the prompt cache. The
# history repeats an earlier question with the context it was sent with: with OpenRouter's search
# tool a Claude request caches only at its very end, so the next message reads the previous one's
# first step only if it starts with exactly that prompt.
APP_CONTEXT_OPEN = "[consens.io context for this message, supplied by the app, not written by the user]"
APP_CONTEXT_CLOSE = "[end of app context]"


def get_agent_turn_context(model=None, config=None, device_timezone=None):
    """``device_timezone``: the zone the user's browser reported, else the app's reference zone."""
    config = config or prompt_config.get_config()
    context = get_date_context(device_timezone or config["reference_timezone"], device=bool(device_timezone))
    if model is not None:
        context += f"\nSelected model for this response: {model.label} ({model.model})."
    return context


def with_app_context(question, context):
    return f"{APP_CONTEXT_OPEN}\n{context}\n{APP_CONTEXT_CLOSE}\n\n{question}"


def add_app_context(content, context):
    """``content`` with ``context`` as the last lines of its app context; a message without one gets
    it."""
    if isinstance(content, str) and content.startswith(APP_CONTEXT_OPEN):
        head, separator, rest = content.partition(f"\n{APP_CONTEXT_CLOSE}\n\n")
        if separator:
            return f"{head}\n{context}{separator}{rest}"
    return with_app_context(content, context)


def strip_app_context(content):
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
        # Expired roots can outlive the owner's active lease map, so their durable run state is
        # queried.
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
        # Whether any run root is still running, so the caller may skip asking again for a while.
        return running

    def active_ref(self, uid):
        return self.db.collection("users").document(uid).collection("chat_state").document("agent_runs")

    def receipt_ref(self, uid, chat_id, turn_id, step="completion:0"):
        if not re.fullmatch(r"(?:completion|agent:[a-f0-9]{32}):(?:0|[1-9][0-9]*)", step):
            raise ValueError("Invalid agent step")
        key = hashlib.sha256(f"agent\0{chat_id}\0{turn_id}\0{step}".encode()).hexdigest()
        return self.db.collection("users").document(uid).collection("llm_calls").document(key)

    def history_page(self, uid, chat_id, cursor="", *, checked=False):
        """One page of a chat's turns as messages reads them; the Agent route reads the first while
        it creates the turn."""
        return self._list_turn_snapshots(uid, chat_id, cursor=cursor, limit=TURN_PAGE_SIZE_MAX,
                                         fields=HISTORY_FIELDS, checked=checked)

    @staticmethod
    def history_current(page, target):
        """Whether ``page``, read before ``target`` was created, still holds every earlier turn as
        it is (none pending, a single page). Else messages reads its own."""
        earlier = [(s.to_dict() or {}) for s in page["snapshots"]]
        earlier = [turn for turn in earlier if turn.get("position", 0) < target["position"]]
        return (all(in_history(turn) for turn in earlier)
                and (page.get("has_more") or len(earlier) == target["position"] - 1))

    def messages(self, uid, chat_id, target, model=None, config=None, sources=None, context=None, first_page=None,
                 history_chars=None, summary=None):
        """The conversation for the target turn. ``sources`` receives the saved sources of the
        included turns for read_source. ``context``: the target turn's app context; earlier
        questions come back with their own, so the prompt continues the one each turn first sent.
        ``first_page``: used where history_current says it holds.

        A chat longer than CONTEXT_CHAR_LIMIT keeps its newest messages and says so in the app
        context; ``history_chars`` keeps less (a Watch's run). A turn that worked in its VM is
        followed by its saved work record. The newest saved history summary stands for the messages
        it covers, their sources still openable. ``summary`` receives the plan of the next one once
        the history passes HISTORY_SUMMARY_ABOVE_CHARS (after a failed one, once it grew by
        HISTORY_SUMMARY_RETRY_CHARS); a Watch's run neither reads nor plans one."""
        from app.services import agent_compaction
        config = config or prompt_config.get_config()
        system_prompt = config["prompts"]["agent"]
        messages = [{"role": "system", "content": system_prompt}]
        earlier = []
        # The newest saved summary and the newest failed attempt, with their turns' positions.
        saved_summary, summary_at = None, -1
        failed_summary, failed_at = None, -1
        cursor = ""
        while True:
            # Agent answers live on the turn itself: no model_answers query per message.
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
                    # Match the visible saved conversation without claiming an interrupted answer or
                    # its review completed; the next attempt builds on a work record.
                    answer = ("[This previous turn did not finish successfully. The saved response below may be incomplete or unreviewed.]\n\n" + answer
                              if answer else FAILED_TURN_RESUME if isinstance(record, str) and record
                              else "[This previous turn did not finish successfully. No assistant answer was saved.]")
                earlier.append((turn["position"], question, answer, turn.get("sources") or [],
                                record if isinstance(record, str) else ""))
                found = turn.get("agent_history_summary")
                if (isinstance(found, dict) and agent_compaction.is_summary(found.get("content"))
                        and type(found.get("through")) is int and turn["position"] > summary_at):
                    saved_summary, summary_at = found, turn["position"]
                failed = turn.get("agent_history_summary_failed")
                if isinstance(failed, dict) and type(failed.get("held")) is int and turn["position"] > failed_at:
                    failed_summary, failed_at = failed, turn["position"]
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
                # Covered by the summary, their sources stay openable.
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
        backoff = (failed_summary["held"] + agent_compaction.HISTORY_SUMMARY_RETRY_CHARS
                   if failed_summary is not None and failed_at > summary_at else 0)
        if (summary is not None and not history_chars and held > agent_compaction.HISTORY_SUMMARY_ABOVE_CHARS
                and held >= backoff):
            keep = agent_compaction.history_keep(replayed)
            if keep < len(replayed):
                summary.update({
                    "end": starts[len(replayed) - keep], "through": earlier[start:][len(replayed) - keep - 1][0],
                    "turns": len(replayed) - keep, "held": held,
                    "partial": bool(start) or (saved_summary is not None
                                               and agent_compaction.HISTORY_SUMMARY_PARTIAL in saved_summary["content"])})
        context = context or get_agent_turn_context(model, config)
        if start:
            # The newest message's context changes every message anyway: the note costs no cached
            # prefix.
            context += "\n" + HISTORY_OMITTED_NOTE
        messages.append({"role": "user", "content": with_app_context(target["question"], context)})
        from app.services.agent_tokens import input_estimate, minimum_output
        if model and input_estimate(messages, request_config=model.request_config) + minimum_output(model) > model.context_length:
            raise ConversationTooLong("This conversation is too long for the selected model. Choose a model with a larger context or start a new chat.")
        return messages

    def _expected_daily(self, uid):
        """The ledger document a claim of now books into, or None: the settlement then reads the
        receipt's own day."""
        try:
            from app.services import agent_budget_config
            return agent_quota.quota_ref(self.db, uid, agent_quota.period_key(agent_budget_config.get_config(self.db)))
        except Exception:
            return None

    def settle(self, uid, chat_id, turn_id, *, completion, status, step="completion:0", expected=0):
        """``expected``: what such a call of the run measured, in micro-euros, for a call without a
        final cost."""
        if status not in {"succeeded", "failed", "cancelled"}:
            raise ValueError("Invalid agent settlement status")
        receipt_ref = self.receipt_ref(uid, chat_id, turn_id, step)
        root_ref = self.receipt_ref(uid, chat_id, turn_id)
        # Read in the same round trip as the rest; almost always the receipt's own day, which saves
        # a second round trip under the account's lock.
        expected_daily = self._expected_daily(uid)

        def operation(tx):
            tombstone, receipt, root, *guessed = self._read_all(tx, (
                persistence_guard.deletion_ref(self.db, uid), receipt_ref, root_ref,
                *([expected_daily] if expected_daily is not None else [])))
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx, snapshot=tombstone)
            if not receipt.exists:
                raise ChatNotFound("Agent receipt not found")
            if (receipt.to_dict() or {}).get("status") != "running":
                return False
            root_data = (receipt if step == "completion:0" else root).to_dict() or {}
            receipt_data = receipt.to_dict() or {}
            daily_ref = agent_quota.quota_ref(self.db, uid, receipt_data["quota_day"])
            if guessed and daily_ref.path == expected_daily.path:
                daily = guessed[0].to_dict()
            else:
                # A call claimed before midnight or a reset: its own day.
                daily = daily_ref.get(transaction=tx).to_dict()
            usage = completion.usage
            tx.set(daily_ref, agent_quota.count_settlement(
                agent_quota.settle(daily, receipt_data["quota_reserved"], usage,
                                   measurable=bool(completion.generation_id), expected=expected), usage))
            estimate = agent_quota.unknown_estimate(receipt_data["quota_reserved"], usage, expected=expected)
            receipt_patch = {
                "status": status, "usage": usage,
                "usage_status": "unavailable" if usage is None else "measured" if usage.get("complete", True) else "partial",
                "generation_id": completion.generation_id, "finish_reason": completion.finish_reason,
                "settled_at": firestore.SERVER_TIMESTAMP,
            }
            if getattr(completion, "search_hits", None) is not None:
                receipt_patch["search_hits"] = completion.search_hits
            for field in REQUEST_TIMES:
                # Between created_at and settled_at: the provider's part and ours.
                if isinstance(getattr(completion, field, None), datetime):
                    receipt_patch[field] = getattr(completion, field)
            review_round = getattr(completion, "review_round", None)
            if isinstance(review_round, str) and review_round:
                # A reviewer's call: live, final, repair or hedge.
                receipt_patch["round"] = review_round
            charged = agent_quota.measured_charge(usage)
            if charged is not None:
                # What the account was charged, in micro-euros.
                receipt_patch["quota_charged"] = charged
            if estimate is not None:
                # Bounded uncertainty: the ledger now carries this estimate. Only a provider
                # generation id makes later measurement possible.
                receipt_patch.update(
                    quota_estimate=estimate,
                    quota_reconcile="pending" if completion.generation_id else "final",
                    quota_reconcile_attempts=0,
                )
            tx.update(receipt_ref, receipt_patch)
            delegated = self._delegated_settlement(root_data, step, status, usage)
            if delegated:
                tx.update(root_ref, delegated)
            return True

        return self._agent_transaction(uid, operation)

    def hand_over(self, uid, chat_id, turn_id, *, run_token, completion):
        """The answer is fixed and only its review is left: the chat is free for its next message.
        The turn stays ``pending`` until the reviewers are done but marks ``agent_answer_fixed_at``
        and already carries what the next message reads of it; the chat's lock and the run's
        capacity slot end. False when the run no longer holds the chat."""
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

    def save_history_summary(self, uid, chat_id, turn_id, *, run_token, summary=None, failed=None):
        """The history summary this turn's first step wrote, saved at once so later messages start
        with it also when this one fails; or with ``failed`` the mark that makes the next wait for
        more history. False when the run no longer holds the turn."""
        root_ref, turn_ref = self.receipt_ref(uid, chat_id, turn_id), self._turn_ref(uid, chat_id, turn_id)

        def operation(tx):
            tombstone, root, turn = self._read_all(tx, (persistence_guard.deletion_ref(self.db, uid), root_ref, turn_ref))
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx, snapshot=tombstone)
            data = root.to_dict() or {}
            if (not run_token or data.get("run_token") != run_token or data.get("run_status") != "running"
                    or not turn.exists or (turn.to_dict() or {}).get("status") != "pending"):
                return False
            tx.update(turn_ref, {"agent_history_summary": summary} if failed is None
                      else {"agent_history_summary_failed": failed})
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
            # The review ends below as the reviewers left it.
            review = (turn.to_dict() or {}).get("agent_review")
            closed = {"run_status": status, "finished_at": firestore.SERVER_TIMESTAMP}
            if not chat.exists or (chat.to_dict() or {}).get("status") != "active":
                # A chat deleted while the run still wrote: the texts its deletion took from this
                # receipt do not come back.
                from app.services.chat_store import RUN_RECEIPT_TEXT_FIELDS
                closed.update({name: firestore.DELETE_FIELD for name in RUN_RECEIPT_TEXT_FIELDS if name in data})
            tx.update(root_ref, closed)
            leases = dict((active.to_dict() or {}).get("leases") or {})
            leases.pop(root_ref.id, None)
            tx.set(active_ref, {"leases": leases})
            chat_data, turn_data = chat.to_dict() or {}, turn.to_dict() or {}
            if chat.exists and turn.exists and chat_data.get("status") == "active" and turn_data.get("status") == "pending":
                # An answer that already stands stays the answer when its reviewers' run ends
                # otherwise (the reaper after a hard kill): the user may have gone on. Only its
                # review ends unfinished.
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
                    # The message's checkpoint and the commands' run time.
                    patch["agent_vm"] = completion.vm
                if getattr(completion, "work_record", None):
                    # What the next message is told this one did.
                    patch["agent_work_record"] = completion.work_record
                if getattr(completion, "holds", None):
                    # The turn's pauses: kind, decision and seconds, no reasons.
                    patch["agent_holds"] = completion.holds
                if isinstance(getattr(completion, "wrap_up", None), dict):
                    # Which limit ended its work: reason code, steps and seconds, no text.
                    patch["agent_wrap_up"] = completion.wrap_up
                if status == "succeeded" or fixed:
                    patch.update(assistant_response=completion.text or (turn_data.get("assistant_response") or "" if fixed else ""),
                                 completed_at=firestore.SERVER_TIMESTAMP,
                                 differences="", differences_data=None, included_models=[])
                    if status == "succeeded" and review and review.get("mode") == "audit" and review.get("status") in {"required", "running"}:
                        # A finished answer never keeps "reviewing".
                        patch["agent_review"] = {**review, "status": "failed"}
                if status != "succeeded":
                    if not fixed:
                        patch.update(error_code="cancelled" if status == "cancelled" else "agent_failed", failed_at=firestore.SERVER_TIMESTAMP)
                        patch["agent_failure"] = getattr(completion, "failure", None) or {
                            "code": "cancelled" if status == "cancelled" else "agent_failed",
                            "error": "Response stopped. Available results have been saved." if status == "cancelled" else "The response could not be completed. Available results have been saved."}
                        # Comparisons only advise; the answer is the agent's own.
                        if completion.text:
                            patch["assistant_response"] = completion.text
                    if review:
                        # A crash or stop cannot leave a saved review looking live, but a review
                        # that had finished keeps its result: a later failure must not relabel a
                        # reviewed answer as unreviewed.
                        review = dict(review)
                        if review.get("status") not in {"succeeded", "partial", "off"}:
                            review["status"] = ("cancelled" if status == "cancelled" else
                                                "missing" if review.get("status") == "required" else "failed")
                        for comparison in review.get("comparisons", []):
                            if comparison.get("status") == "running":
                                comparison["status"] = "cancelled" if status == "cancelled" else "failed"
                        audit = review.get("audit")
                        if isinstance(audit, dict) and isinstance(audit.get("reviewers"), list):
                            # Reviewers a crash or the reaper left at work: none still is.
                            review["audit"] = {**audit, "reviewers": [
                                {**row, "status": "failed", "failure": {"code": "run_interrupted"}}
                                if isinstance(row, dict) and row.get("status") in {"waiting", "running"} else row
                                for row in audit["reviewers"]]}
                        # A pasted text's check from an older review shape, ended by the reaper.
                        passage = review.get("passage_check")
                        if isinstance(passage, dict) and passage.get("status") in {"waiting", "running"}:
                            review["passage_check"] = {**passage, "status": "cancelled" if status == "cancelled" else "failed"}
                        # A page read the run ended during.
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
                # A chat that already runs its next message keeps that message's state.
                owner = chat_data.get("agent_turn_id") == turn_id
                if owner and isinstance(getattr(completion, "workspace_used", None), bool):
                    # Whether the chat's next message starts with the workspace open.
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
