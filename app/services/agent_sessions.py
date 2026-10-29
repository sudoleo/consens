"""Owner-bound delegation journal. Public messages are separate from turn traces.

The root receipt fences a producer, all paid steps and ordered event writes.
There is deliberately no resume path for paid steps after process loss.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from firebase_admin import firestore

from app.services import persistence_guard
from app.services import agent_quota, agent_budget_config
from app.services.agent_costs import USAGE_FIELDS, aggregate_usage, remaining_reservation
from app.services.agent_runtime import AgentCapacityExceeded
from app.services.agent_provider_limits import AgentRunInterrupted
from app.services.chat_store import ChatNotFound, TurnStatusConflict
from app.services.llm.provider_runtime import AnalysisBudgetExceeded, ProviderCancelled


PRODUCER_LEASE_SECONDS = 120
PRODUCER_RENEW_BEFORE_SECONDS = 90
# Size contract of the per-turn root receipt (R29). Running steps always stay
# in the root maps; only settled steps beyond this window are folded into
# `compacted_usage`/`compacted_steps`. Each step keeps its own immutable
# llm_calls receipt, so compaction loses neither usage nor history.
ROOT_SETTLED_STEP_WINDOW = 32
ROOT_MAX_RUNNING_STEPS = 64
ROOT_MAX_BYTES = 256_000
TECHNICAL_STEP_LIMIT = ("This response reached a technical limit for one agent turn. "
                        "The available results have been saved; send a follow-up message to continue.")
# Messages the user sends into a running response (add_user_note), on its root
# receipt, which the run's watcher reads every few seconds anyway.
USER_NOTES_MAX = 10
USER_NOTE_CHARS = 4000
HOLD_NOT_DENIABLE = "This pause cannot be declined. Let it continue, write to the agent or stop it."


class NotesFull(TurnStatusConflict):
    """A message into the run would exceed USER_NOTES_MAX (decide_hold)."""


class HoldActionRefused(ValueError):
    """"deny" on a hold it is no answer to (decide_hold, deniable)."""


def deniable(hold):
    """Whether "deny" answers ``hold``: a domain the agent asked for
    (agent_domains.py) or the agent's own question to allow a step or to give
    a key (agent_ask.py). A reviewer's halt or a gate goes on, gets a
    message or stops; before 2026-10-29 a "deny" there went on like
    "continue", and a gated update_memory ran."""
    hold = hold or {}
    return bool(hold.get("domain")) or hold.get("ask") in {"confirm", "secret"}


def root_usage(root):
    """Turn usage including compacted steps, for every reader of root maps."""
    usages = list((root.get("step_usage") or {}).values())
    if root.get("compacted_steps"):
        usages.insert(0, root.get("compacted_usage"))
    return aggregate_usage(usages)


def _step_index(step):
    return int(step.rsplit(":", 1)[1])


def compact_root(patch, data):
    """Fold the oldest settled steps out of the root maps, keeping the window."""
    states = dict(patch.get("step_states", data.get("step_states") or {}))
    settled = sorted((step for step, state in states.items() if state != "running"),
                     key=lambda step: (_step_index(step), step), reverse=True)
    evicted = settled[ROOT_SETTLED_STEP_WINDOW:]
    if not evicted:
        return patch
    usage = dict(patch.get("step_usage", data.get("step_usage") or {}))
    reservations = dict(patch.get("reservations", data.get("reservations") or {}))
    folded = [usage.pop(step, None) for step in evicted]
    for step in evicted:
        states.pop(step, None)
        reservations.pop(step, None)
    previous = data.get("compacted_usage") if data.get("compacted_steps") else None
    compacted = aggregate_usage([previous, *folded] if previous is not None else folded)
    if compacted is None:
        # Every folded step was unmetered: keep a count-only aggregate, or the
        # next fold would drop these calls and report a complete usage.
        compacted = {**{field: None for field in USAGE_FIELDS}, "web_search_requests": None,
                     "complete": False, "cost_complete": False, "measured_calls": 0,
                     "unmetered_calls": len(folded), "cost_source": "catalog", "source": "provider",
                     "billing_mode": "simulation", "currency": "USD"}
    return {**patch, "step_states": states, "step_usage": usage, "reservations": reservations,
            "compacted_usage": compacted, "compacted_steps": data.get("compacted_steps", 0) + len(evicted)}


def _serialized_size(value):
    import json
    return len(json.dumps(value, default=str, ensure_ascii=False).encode("utf-8"))
class AgentSessionStore:
    @staticmethod
    def _read_all(tx, refs):
        """``refs`` read in one round trip of transaction ``tx`` (Firestore's
        get_all), in their order; a missing document is a snapshot that does
        not exist. Until 2026-10-21 each read was its own round trip: a claim
        read nine documents one after another while every other call of the
        account waited for the account lock (agent_journal)."""
        get_all = getattr(tx, "get_all", None)
        if get_all is None:
            return [ref.get(transaction=tx) for ref in refs]
        # The root receipt of a first step is that step's receipt: asked once.
        unique = list({ref.path: ref for ref in refs}.values())
        found = {snapshot.reference.path: snapshot for snapshot in get_all(unique)}
        return [found[ref.path] for ref in refs]

    def _agent_transaction(self, uid, operation):
        # Shared with the pipeline's usage transactions: both write the same
        # token-account document.
        with agent_quota.account_lock(uid):
            return self._transaction(operation)

    def agent_ref(self, uid, chat_id, turn_id, agent_id):
        import re
        if not re.fullmatch(r"[a-f0-9]{32}", agent_id):
            raise ValueError("Invalid agent identity")
        return self._turn_ref(uid, chat_id, turn_id).collection("agents").document(agent_id)

    def _claim_delegated(self, uid, chat_id, turn_id, model, *, step, run_token, policy, reservation, overdraft=False):
        root_ref = self.receipt_ref(uid, chat_id, turn_id)
        receipt_ref = self.receipt_ref(uid, chat_id, turn_id, step)
        chat_ref, turn_ref = self._chat_ref(uid, chat_id), self._turn_ref(uid, chat_id, turn_id)
        user_ref, active_ref = self.db.collection("users").document(uid), self.active_ref(uid)
        agent_id = step.split(":")[1] if step.startswith("agent:") else "orchestrator"
        index = int(step.split(":")[-1])
        budget_config = agent_budget_config.get_config(self.db)
        token_limit = agent_budget_config.limit_for(budget_config, agent_quota.account_tier(uid))

        day = agent_quota.period_key(budget_config)
        daily_ref = agent_quota.quota_ref(self.db, uid, day)
        agent_refs = [self.agent_ref(uid, chat_id, turn_id, agent_id)] if agent_id != "orchestrator" else []

        def operation(tx):
            tombstone, receipt, root, chat, turn, user, active, daily_snapshot, *agent = self._read_all(tx, (
                persistence_guard.deletion_ref(self.db, uid), receipt_ref, root_ref, chat_ref, turn_ref, user_ref,
                active_ref, daily_ref, *agent_refs))
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx, snapshot=tombstone)
            agent = agent[0] if agent else None
            if receipt.exists:
                return False
            now = datetime.now(timezone.utc)
            data, chat_data, turn_data = root.to_dict() or {}, chat.to_dict() or {}, turn.to_dict() or {}
            if not chat.exists or not turn.exists or chat_data.get("status") != "active":
                raise ChatNotFound("Chat not found")
            if (turn_data.get("status") != "pending" or chat_data.get("execution_mode") != "agent"
                    or turn_data.get("execution_mode") != "agent" or chat_data.get("agent_turn_id") != turn_id):
                raise TurnStatusConflict("Agent turn is no longer runnable")
            leases = {key: value for key, value in ((active.to_dict() or {}).get("leases") or {}).items()
                      if isinstance(value, datetime) and value > now}
            if not root.exists:
                if chat_data.get("agent_lock_until", now) <= now:
                    raise AgentRunInterrupted("The response could not start before its chat reservation expired. Send a new message to try again.")
                if step != "completion:0" or not run_token or not policy or not policy.get("delegation"):
                    raise TurnStatusConflict("Delegation root is missing")
                if len(leases) >= 2:
                    raise AgentCapacityExceeded("Two agent responses are already running.")
                data = {"run_token": run_token, "run_status": "running", "policy": policy,
                        "lease_until": now + timedelta(seconds=PRODUCER_LEASE_SECONDS if policy.get("account_budget_only") else policy["seconds"] + 30),
                        "step_states": {}, "step_usage": {}, "reservations": {}, "event_seq": 0,
                        "reserved_tokens": 0, "reserved_cost": 0}
                leases[root_ref.id] = data["lease_until"]
            elif (data.get("run_token") != run_token or data.get("run_status") != "running"
                    or data.get("lease_until", now) <= now or data.get("cancel_requested") or root_ref.id not in leases):
                if data.get("run_token") == run_token and data.get("cancel_requested"):
                    raise ProviderCancelled("Agent run stopped")
                raise TurnStatusConflict("Delegation producer is no longer authorized")
            limits = data["policy"]
            states = dict(data["step_states"])
            prefix = "completion" if agent_id == "orchestrator" else f"agent:{agent_id}"
            previous_step = f"{prefix}:{index - 1}"
            previous_state = states.get(previous_step)
            if index and previous_state is None and data.get("compacted_steps"):
                # Compacted out of the root: its own receipt is authoritative.
                previous_receipt = self.receipt_ref(uid, chat_id, turn_id, previous_step).get(transaction=tx)
                previous_state = (previous_receipt.to_dict() or {}).get("status")
            if index and previous_state != "succeeded":
                raise TurnStatusConflict("Previous model step has not succeeded")
            if sum(state == "running" for state in states.values()) >= ROOT_MAX_RUNNING_STEPS:
                raise AnalysisBudgetExceeded(TECHNICAL_STEP_LIMIT)
            if agent is not None and (not agent.exists or (agent.to_dict() or {}).get("status") in {"stopped", "failed"}):
                raise TurnStatusConflict("Worker session is not runnable")
            tokens, cost = reservation
            daily = daily_snapshot.to_dict() or {}
            # Review/synthesis can spend this run's protected budget; workers
            # and comparisons cannot consume it.
            protected = data.get("review_hold", 0)
            previous_daily_ref = None
            if data.get("quota_day") and data["quota_day"] != day:
                previous_daily_ref = agent_quota.quota_ref(self.db, uid, data["quota_day"])
                previous_daily = previous_daily_ref.get(transaction=tx).to_dict() or {}
                previous_daily = agent_quota.release(previous_daily, protected)
                daily = agent_quota.reserve(daily, protected, limit=token_limit)
            kind = (agent.to_dict() or {}).get("kind") if agent else None
            can_spend = agent_id == "orchestrator" or kind == "judge"
            spend = min(protected, tokens) if can_spend else 0
            cost_hold = data.get("review_cost_hold", 0)
            cost_spend = min(cost_hold, cost) if can_spend else 0
            # An audit reviewer's call holds and takes its weight of the
            # allowance (agent_quota.receipt_weight); the run's own budgets
            # below keep counting its tokens in full.
            quota_tokens = agent_quota.weighted(tokens, agent_quota.receipt_weight({"session_kind": kind}))
            daily = agent_quota.reserve(daily, quota_tokens - spend, limit=token_limit,
                                        overdraft=overdraft if limits.get("account_budget_only") else False)
            if not limits.get("account_budget_only") and (len(states) + data.get("compacted_steps", 0) >= limits["max_calls"] or data["reserved_tokens"] + tokens > limits["max_tokens"]
                    or data["reserved_cost"] + cost + cost_hold - cost_spend > limits["max_cost_nano_usd"]):
                raise AnalysisBudgetExceeded("The shared agent budget was reached.")
            states[step] = "running"
            reservations = {**data["reservations"], step: list(reservation)}
            patch = {**data, "step_states": states, "reservations": reservations,
                     "quota_day": day, "review_hold": protected - spend,
                     "review_cost_hold": cost_hold - cost_spend,
                     "reserved_tokens": data["reserved_tokens"] + tokens, "reserved_cost": data["reserved_cost"] + cost}
            if agent_id == "orchestrator":
                patch["last_step"] = step
            patch = compact_root(patch, data)
            if _serialized_size(patch) > ROOT_MAX_BYTES:
                raise AnalysisBudgetExceeded(TECHNICAL_STEP_LIMIT)
            record = {"schema_version": 3, "purpose": "agent", "step": step, "agent_id": agent_id,
                      "quota_day": day, "quota_reserved": quota_tokens,
                      "chat_id": chat_id, "turn_id": turn_id, "status": "running",
                      "model": model.snapshot(), "created_at": firestore.SERVER_TIMESTAMP}
            if kind:
                # The session's kind outlives the chat (scripts/audit_report.py).
                record["session_kind"] = kind
            if root.exists:
                tx.update(root_ref, patch)
                tx.set(receipt_ref, record)
            else:
                tx.set(root_ref, {**record, **patch})
                tx.update(chat_ref, {"agent_lock_until": data["lease_until"]})
            totals = dict((user.to_dict() or {}).get("agent_usage") or {})
            totals.update(calls=totals.get("calls", 0) + 1, unsettled_calls=totals.get("unsettled_calls", 0) + 1,
                          currency="USD", billing_mode="simulation")
            tx.set(active_ref, {"leases": leases})
            tx.set(daily_ref, daily)
            if previous_daily_ref:
                tx.set(previous_daily_ref, previous_daily)
            if user.exists:
                tx.update(user_ref, {"agent_usage": totals})
            else:
                tx.set(user_ref, {"agent_usage": totals})
            return True
        return self._agent_transaction(uid, operation)

    def protect_review(self, uid, chat_id, turn_id, run_token, tokens, cost=0):
        """Atomically protect synthesis/judges from all other concurrent runs."""
        ref = self.receipt_ref(uid, chat_id, turn_id)
        budget_config = agent_budget_config.get_config(self.db)
        token_limit = agent_budget_config.limit_for(budget_config, agent_quota.account_tier(uid))
        day = agent_quota.period_key(budget_config)
        daily_ref = agent_quota.quota_ref(self.db, uid, day)
        def operation(tx):
            tombstone, root, daily = self._read_all(tx, (persistence_guard.deletion_ref(self.db, uid), ref, daily_ref))
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx, snapshot=tombstone)
            root, daily = root.to_dict() or {}, daily.to_dict() or {}
            if root.get("run_token") != run_token or root.get("run_status") != "running":
                raise TurnStatusConflict("Agent run is closed")
            protected = root.get("review_hold", 0)
            previous_ref = None
            if root["quota_day"] != day:
                previous_ref = agent_quota.quota_ref(self.db, uid, root["quota_day"])
                previous = previous_ref.get(transaction=tx).to_dict() or {}
                previous = agent_quota.release(previous, protected)
                extra = max(tokens, protected)
            else:
                extra = max(0, tokens - protected)
            daily = agent_quota.reserve(daily, extra, limit=token_limit)
            protected_cost = max(cost, root.get("review_cost_hold", 0))
            if not root["policy"].get("account_budget_only") and root["reserved_cost"] + protected_cost > root["policy"]["max_cost_nano_usd"]:
                raise AnalysisBudgetExceeded("Not enough cost budget for synthesis and review")
            tx.set(daily_ref, daily)
            if previous_ref:
                tx.set(previous_ref, previous)
            tx.update(ref, {"quota_day": day, "review_hold": max(tokens, protected), "review_cost_hold": protected_cost})
        self._agent_transaction(uid, operation)

    def save_review(self, uid, chat_id, turn_id, run_token, review, text):
        """Checkpoint exact text and review state before expensive work."""
        root_ref = self.receipt_ref(uid, chat_id, turn_id)
        turn_ref, chat_ref = self._turn_ref(uid, chat_id, turn_id), self._chat_ref(uid, chat_id)
        def operation(tx):
            tombstone, *snapshots = self._read_all(tx, (persistence_guard.deletion_ref(self.db, uid), root_ref, turn_ref, chat_ref))
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx, snapshot=tombstone)
            root, turn, chat = (snapshot.to_dict() or {} for snapshot in snapshots)
            if (root.get("run_token") != run_token or root.get("run_status") != "running"
                    or chat.get("status") != "active" or turn.get("status") != "pending"):
                raise TurnStatusConflict("Agent review is closed")
            tx.update(turn_ref, {"agent_review": review, "assistant_response": text})
        self._agent_transaction(uid, operation)

    def save_work_log(self, uid, chat_id, turn_id, entries, *, expires_at, incomplete=False):
        """Append work log entries of the run (agent_work_log.WorkLog).

        Its own transaction, never behind the account lock: no model step
        waits for the log. It reads neither the root receipt nor anything
        else a claim, settlement or session update writes in a hurry: a
        server transaction locks what it reads, so a log write must never
        make those wait. The fence: the account is not being deleted, the
        chat is active and the turn still runs (``pending``; finish_run ends
        that, so nothing is written after the run). The turn carries the
        log's expiry for retention and, once an entry was lost,
        ``work_log_incomplete``."""
        turn_ref, chat_ref = self._turn_ref(uid, chat_id, turn_id), self._chat_ref(uid, chat_id)
        def operation(tx):
            tombstone, *snapshots = self._read_all(tx, (persistence_guard.deletion_ref(self.db, uid), turn_ref, chat_ref))
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx, snapshot=tombstone)
            turn, chat = (snapshot.to_dict() for snapshot in snapshots)
            if not turn or turn.get("status") != "pending" or (chat or {}).get("status") != "active":
                raise TurnStatusConflict("Agent work log is closed")
            for entry in entries:
                tx.set(turn_ref.collection("work_log").document(f"{entry['seq']:06d}"), entry)
            patch = {}
            if turn.get("work_log_expires_at") is None:
                patch["work_log_expires_at"] = expires_at
            if incomplete and not turn.get("work_log_incomplete"):
                patch["work_log_incomplete"] = True
            if patch:
                tx.update(turn_ref, patch)
        self._transaction(operation)

    def _work_log_turn(self, uid, chat_id, turn_id):
        """The turn's own stored fields (not its client view), owner-bound by
        path, of an active chat."""
        chat, turn = self._chat_ref(uid, chat_id).get(), self._turn_ref(uid, chat_id, turn_id).get()
        if not chat.exists or (chat.to_dict() or {}).get("status") != "active" or not turn.exists:
            raise ChatNotFound("Chat not found")
        return turn.to_dict() or {}

    def read_work_log(self, uid, chat_id, turn_id, *, after=0, limit=100):
        """The turn's work log entries after ``after``, in order."""
        turn = self._work_log_turn(uid, chat_id, turn_id)
        query = (self._turn_ref(uid, chat_id, turn_id).collection("work_log").order_by("seq")
                 .start_after({"seq": after}).limit(limit + 1))
        entries = [snapshot.to_dict() for snapshot in query.stream()]
        return {"entries": entries[:limit], "has_more": len(entries) > limit,
                "incomplete": bool(turn.get("work_log_incomplete")), "status": turn.get("status")}

    def work_log_entry(self, uid, chat_id, turn_id, seq):
        """One entry with its whole content (agent_work_log.entry_content)."""
        from app.services.agent_work_log import entry_content
        self._work_log_turn(uid, chat_id, turn_id)
        snapshot = self._turn_ref(uid, chat_id, turn_id).collection("work_log").document(f"{seq:06d}").get()
        if not snapshot.exists:
            raise ChatNotFound("Work log entry not found")
        entry = snapshot.to_dict()
        from app.services.agent_files import FileUnavailable
        try:
            return {**entry, "content": entry_content(entry)}
        except FileUnavailable:
            # The object store no longer holds it (expired, or not configured
            # here): the saved beginning is all there is.
            return {**entry, "content_unavailable": True}

    @staticmethod
    def _delegated_settlement(data, step, status, usage):
        if not (data.get("policy") or {}).get("delegation"):
            return {}
        reserved = data["reservations"][step]
        tokens, cost = remaining_reservation(reserved, usage)
        return compact_root({"step_states": {**data["step_states"], step: status},
                "step_usage": {**data["step_usage"], step: usage},
                "reserved_tokens": data["reserved_tokens"] + tokens - reserved[0],
                "reserved_cost": data["reserved_cost"] + cost - reserved[1]}, data)

    def publish_agent(self, uid, chat_id, turn_id, *, run_token, agent_id, patch=None, message=None, event_id=None):
        """Atomically mutate a session and append one deduplicated event/message."""
        [result] = self.publish_agents(uid, chat_id, turn_id, run_token=run_token,
                                       updates=[(agent_id, patch, message, event_id or uuid4().hex)])
        if isinstance(result, Exception):
            raise result
        return result

    def publish_agents(self, uid, chat_id, turn_id, *, run_token, updates):
        """Several session updates of one run in one transaction (agent_journal).

        ``updates``: ``(agent_id, patch, message, event_id)`` in the order
        their events get their sequence numbers. Returns one entry per update:
        its event, or the exception that refused this update alone (a limit,
        a missing assignment, a stopped run for a status that does not end
        its session); the others are saved all the same, as if written one
        by one. An event id saved before (a retried ambiguous commit) returns
        its first commit. A deleted account, chat or closed run refuses the
        whole call. Until 2026-10-22 every update was its own transaction:
        six comparison answers starting together queued six writes behind
        the account lock, each before its model call could be claimed."""
        root_ref = self.receipt_ref(uid, chat_id, turn_id)
        turn_ref, chat_ref = self._turn_ref(uid, chat_id, turn_id), self._chat_ref(uid, chat_id)
        agent_refs = [self.agent_ref(uid, chat_id, turn_id, agent_id) for agent_id, *_ in updates]
        event_refs = [turn_ref.collection("agent_events").document(event_id) for *_, event_id in updates]
        def operation(tx):
            tombstone, root, chat, turn, *snapshots = self._read_all(tx, (
                persistence_guard.deletion_ref(self.db, uid), root_ref, chat_ref, turn_ref, *agent_refs, *event_refs))
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx, snapshot=tombstone)
            data = root.to_dict() or {}
            if not chat.exists or not turn.exists or (chat.to_dict() or {}).get("status") != "active":
                raise ChatNotFound("Chat not found")
            if data.get("run_token") != run_token:
                raise TurnStatusConflict("Agent session is closed")
            seq, agents, messages = data.get("event_seq", 0), data.get("agent_count", 0), data.get("message_count", 0)
            # Sessions as this call leaves them: one updated twice reads its own first update.
            sessions = {}
            results = []
            for (agent_id, patch, message, event_id), agent_ref, event_ref, agent, event in zip(
                    updates, agent_refs, event_refs, snapshots[:len(updates)], snapshots[len(updates):]):
                if event.exists:
                    results.append(event.to_dict())
                    continue
                current = sessions[agent_id] if agent_id in sessions else agent.to_dict() if agent.exists else None
                try:
                    if data.get("run_status") != "running":
                        raise TurnStatusConflict("Agent session is closed")
                    ending = (patch or {}).get("status") in {"stopped", "failed"}
                    if (data.get("cancel_requested") or data["lease_until"] <= datetime.now(timezone.utc)) and not ending:
                        raise ProviderCancelled("Agent run stopped")
                    if not data["policy"].get("account_budget_only") and seq + 1 > 1024:
                        raise AnalysisBudgetExceeded("Agent event limit reached")
                    session = {**(current or {}), **(patch or {}), "id": agent_id, "seq": seq + 1,
                               "updated_at": datetime.now(timezone.utc).isoformat()}
                    if current is None:
                        if not data["policy"].get("account_budget_only") and agents >= 64:
                            raise AnalysisBudgetExceeded("Agent limit reached")
                        if not session.get("assignment"):
                            raise TurnStatusConflict("Agent assignment is missing")
                    if message:
                        if not data["policy"].get("account_budget_only") and messages + 1 > data["policy"]["max_messages"]:
                            raise AnalysisBudgetExceeded("Agent message limit reached")
                        if len(message["text"]) > max(data["policy"]["message_chars"], data["policy"]["result_chars"]):
                            raise ValueError("Agent message is too long")
                except (TurnStatusConflict, ProviderCancelled, AnalysisBudgetExceeded, ValueError) as exc:
                    results.append(exc)
                    continue
                seq += 1
                agents += current is None
                if message:
                    messages += 1
                    tx.set(agent_ref.collection("messages").document(event_id),
                           {**message, "id": event_id, "seq": seq, "created_at": session["updated_at"]})
                    session["message_seq"] = seq
                public = {key: value for key, value in session.items() if key != "assignment"}
                result = {"type": "delegation", "version": 1, "id": event_id, "seq": seq,
                          "run_id": root_ref.id, "chat_id": chat_id, "turn_id": turn_id, "agent": public}
                tx.set(agent_ref, session)
                tx.set(event_ref, result)
                sessions[agent_id] = session
                results.append(result)
            if seq != data.get("event_seq", 0):
                tx.update(root_ref, {"event_seq": seq, "agent_count": agents, "message_count": messages})
            return results
        return self._agent_transaction(uid, operation)

    def check_delegation(self, uid, chat_id, turn_id, run_token):
        chat = self.get_chat(uid, chat_id)
        ref = self.receipt_ref(uid, chat_id, turn_id)
        root = ref.get().to_dict() or {}
        if (chat.get("status") != "active" or root.get("run_token") != run_token
                or root.get("run_status") != "running" or root.get("cancel_requested")):
            raise ProviderCancelled("Agent run stopped")
        # The root as read: the caller takes the user's notes from it.
        if not (root.get("policy") or {}).get("account_budget_only"):
            return root
        now = datetime.now(timezone.utc)
        if root["lease_until"] > now + timedelta(seconds=PRODUCER_RENEW_BEFORE_SECONDS):
            return root
        # Renew all three fences together, only while this producer still owns
        # a live lease. A crashed or superseded producer can never resume work.
        chat_ref, active_ref = self._chat_ref(uid, chat_id), self.active_ref(uid)
        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            data, current_chat, active = (r.get(transaction=tx).to_dict() or {} for r in (ref, chat_ref, active_ref))
            stamp = datetime.now(timezone.utc)
            leases = dict(active.get("leases") or {})
            if (data.get("cancel_requested") or current_chat.get("status") != "active"):
                raise ProviderCancelled("Agent run stopped")
            if (data.get("run_token") != run_token or data.get("run_status") != "running"
                    or current_chat.get("agent_turn_id") != turn_id
                    or data.get("lease_until", stamp) <= stamp or leases.get(ref.id, stamp) <= stamp):
                raise AgentRunInterrupted("The response lost its active connection to saved chat state. Reopen the saved conversation to see the available results.")
            until = stamp + timedelta(seconds=PRODUCER_LEASE_SECONDS)
            leases[ref.id] = until
            tx.update(ref, {"lease_until": until})
            tx.update(chat_ref, {"agent_lock_until": until})
            tx.set(active_ref, {"leases": leases})
        self._agent_transaction(uid, operation)
        return root

    def set_hold(self, uid, chat_id, turn_id, hold, *, replaces=None):
        """The run's open hold (a reviewer paused it, agent_audit.AnswerAudit.halt)
        or None once decided: the decision endpoint checks against it.
        ``replaces``: clear only while that hold is the stored one, so a
        late clear never removes a newer hold written in between."""
        ref = self.receipt_ref(uid, chat_id, turn_id)

        def operation(tx):
            data = ref.get(transaction=tx).to_dict() or {}
            if data.get("run_status") != "running":
                raise TurnStatusConflict("This response is no longer running.")
            if replaces is not None and (data.get("hold") or {}).get("id") != replaces:
                return
            tx.update(ref, {"hold": hold})
        return self._agent_transaction(uid, operation)

    def open_hold(self, uid, chat_id, turn_id):
        """The run's open hold (set_hold), or None once it is over or decided."""
        data = self.receipt_ref(uid, chat_id, turn_id).get().to_dict() or {}
        hold = data.get("hold") or None
        if (data.get("run_status") != "running" or data.get("cancel_requested") or not hold
                or (data.get("hold_decision") or {}).get("id") == hold.get("id")):
            return None
        return hold

    def decide_hold(self, uid, chat_id, turn_id, hold_id, action, text=""):
        """The user's decision on an open hold: "continue", "stop" or "steer"
        (continue with ``text`` as their message into the run, like a note).
        The run's watcher reads it from the root (DelegationLoop._receive_hold);
        returns the fields saved, for a run in this process (DelegationLoop.receive)."""
        from uuid import uuid4
        ref = self.receipt_ref(uid, chat_id, turn_id)

        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            data = ref.get(transaction=tx).to_dict() or {}
            if data.get("run_status") != "running" or data.get("cancel_requested"):
                raise TurnStatusConflict("This response is no longer running.")
            if (data.get("hold") or {}).get("id") != hold_id or (data.get("hold_decision") or {}).get("id") == hold_id:
                raise TurnStatusConflict("This pause is already over.")
            if action == "deny" and not deniable(data.get("hold")):
                raise HoldActionRefused(HOLD_NOT_DENIABLE)
            update = {"hold_decision": {"id": hold_id, "action": action}}
            if action == "steer":
                notes = list(data.get("user_notes") or [])
                if len(notes) >= USER_NOTES_MAX:
                    # Nothing decided: the pause stays open for another answer.
                    raise NotesFull("This response already has the most messages it takes while it runs.")
                update["user_notes"] = [*notes, {"id": uuid4().hex[:12], "text": text[:USER_NOTE_CHARS],
                                                 "at": datetime.now(timezone.utc).isoformat()}]
            tx.update(ref, update)
            return update
        return self._agent_transaction(uid, operation)

    def add_user_note(self, uid, chat_id, turn_id, text):
        """A message of the user into the running response (DelegationLoop
        takes it before its next step). At most USER_NOTES_MAX per response."""
        from uuid import uuid4
        ref = self.receipt_ref(uid, chat_id, turn_id)

        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            data = ref.get(transaction=tx).to_dict() or {}
            if data.get("run_status") != "running" or data.get("cancel_requested"):
                raise TurnStatusConflict("This response is no longer running. Send your message as a new one.")
            notes = list(data.get("user_notes") or [])
            if len(notes) >= USER_NOTES_MAX:
                raise TurnStatusConflict("This response already has the most messages it takes while it runs.")
            note = {"id": uuid4().hex[:12], "text": text[:USER_NOTE_CHARS],
                    "at": datetime.now(timezone.utc).isoformat()}
            tx.update(ref, {"user_notes": [*notes, note]})
            return note
        return self._agent_transaction(uid, operation)

    def stop_delegation(self, uid, chat_id, turn_id):
        self.get_turn(uid, chat_id, turn_id)
        ref = self.receipt_ref(uid, chat_id, turn_id)
        chat_ref, turn_ref = self._chat_ref(uid, chat_id), self._turn_ref(uid, chat_id, turn_id)
        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            root = ref.get(transaction=tx).to_dict() or {}
            chat, turn = (r.get(transaction=tx).to_dict() or {} for r in (chat_ref, turn_ref))
            if root.get("run_status") == "running":
                tx.update(ref, {"cancel_requested": True})
            elif (not root and chat.get("status") == "active" and turn.get("status") == "pending"
                    and chat.get("execution_mode") == "agent" and turn.get("execution_mode") == "agent"):
                # Fence admission in the SAME transaction, even before the
                # first receipt. Otherwise a claim between two writes loses Stop.
                tx.update(turn_ref, {"status": "failed", "error_code": "cancelled",
                    "agent_failure": {"code": "cancelled", "error": "Response stopped before a model call started."},
                    "updated_at": firestore.SERVER_TIMESTAMP})
                if chat.get("agent_turn_id") == turn_id:
                    tx.update(chat_ref, {"agent_lock_until": datetime.now(timezone.utc)})
        self._agent_transaction(uid, operation)

    def delegation_view(self, uid, chat_id, turn_id, *, agent_id=None, after=0, limit=50):
        turn = self.get_turn(uid, chat_id, turn_id)
        root = self.reap_delegation(uid, chat_id, turn_id)
        if not root:
            turn = self.get_turn(uid, chat_id, turn_id)
        if agent_id:
            ref = self.agent_ref(uid, chat_id, turn_id, agent_id)
            agent = ref.get()
            if not agent.exists:
                raise ChatNotFound("Agent not found")
            page = list(ref.collection("messages").order_by("seq").start_after({"seq": after}).limit(limit + 1).stream())
            return {"agent": agent.to_dict(), "messages": [s.to_dict() for s in page[:limit]],
                    "has_more": len(page) > limit}
        agents = [s.to_dict() for s in self._turn_ref(uid, chat_id, turn_id).collection("agents").stream()]
        now = datetime.now(timezone.utc)
        if root.get("run_status") == "running":
            for agent in agents:
                if agent.get("status") in {"waiting", "working", "question", "rework"}:
                    agent["duration_ms"] = max(agent.get("duration_ms", 0), self._observed_duration(agent, now))
        return {"agents": [{k: v for k, v in a.items() if k != "assignment"} for a in agents],
                "seq": root.get("event_seq", 0), "status": root.get("run_status", turn["status"]),
                "usage": root_usage(root) or turn.get("agent_usage")}

    def _worker_receipt_usage(self, uid, chat_id, turn_id, agent_id):
        usages = []
        for index in range(100_000):
            receipt = self.receipt_ref(uid, chat_id, turn_id, f"agent:{agent_id}:{index}").get()
            if not receipt.exists:
                break
            usages.append((receipt.to_dict() or {}).get("usage"))
        return usages

    @staticmethod
    def _observed_duration(agent, observed_at):
        try:
            started = datetime.fromisoformat(agent["created_at"])
            if isinstance(observed_at, str):
                observed_at = datetime.fromisoformat(observed_at)
            return max(0, int((observed_at - started).total_seconds() * 1000))
        except (KeyError, ValueError, TypeError):
            return 0

    def reap_delegation(self, uid, chat_id, turn_id):
        """Close expired producers, preserving trustworthy saved usage when possible."""
        from app.services.llm.agent_client import AgentCompletion
        ref = self.receipt_ref(uid, chat_id, turn_id)
        root = ref.get().to_dict() or {}
        if not root:
            self.release_unclaimed(uid, chat_id, turn_id, expired_only=True, failure={
                "code": "run_interrupted", "error": "The response ended before a model call started. Send a new message to try again."})
            return root
        if (root.get("run_status") != "running" or not (root.get("policy") or {}).get("delegation")
                or root["lease_until"] > datetime.now(timezone.utc)):
            return root
        def fence_expired(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            current = ref.get(transaction=tx).to_dict() or {}
            # A renewal can commit after the initial read. Check expiration and
            # fence the producer atomically before recovering any of its calls.
            if (current.get('run_status') != 'running' or not (current.get('policy') or {}).get('delegation')
                    or current['lease_until'] > datetime.now(timezone.utc)):
                return current, False, False
            chat = self._chat_ref(uid, chat_id).get(transaction=tx)
            turn = self._turn_ref(uid, chat_id, turn_id).get(transaction=tx)
            deleted = not chat.exists or not turn.exists or (chat.to_dict() or {}).get('status') != 'active'
            tx.update(ref, {'cancel_requested': True})
            return current, True, deleted
        root, expired, deleted = self._agent_transaction(uid, fence_expired)
        if not expired:
            return root
        # Billing receipts survive chat deletion; never recreate the chat.
        agents = list(self._turn_ref(uid, chat_id, turn_id).collection('agents').stream())
        sessions = {snap.id: snap.to_dict() for snap in agents}
        for step, state in root["step_states"].items():
            if state == "running":
                value = AgentCompletion()
                if step.startswith('agent:') and step.endswith(':0'):
                    aid = step.split(':')[1]
                    session = sessions.get(aid) or {}
                    usage = session.get('usage') or {}
                    steps = [key for key in root['step_states'] if key.startswith(f'agent:{aid}:')]
                    # A single terminal call's saved session is an exact receipt.
                    # Never distribute a multi-call aggregate across missing steps.
                    if (len(steps) == 1 and session.get('status') in {'completed', 'failed', 'stopped'}
                            and usage.get('complete') is True and usage.get('measured_calls') == 1
                            and not usage.get('unmetered_calls') and agent_quota.measured_tokens(usage) is not None):
                        value.usage = {**usage, 'source': 'saved_agent'}
                        value.finish_reason = session.get('finish_reason') or ''
                self.settle(uid, chat_id, turn_id, completion=value, status="cancelled", step=step, final=False)
        settled = ref.get().to_dict()
        for snap in agents:
            data = snap.to_dict()
            if not deleted and data["status"] not in {"completed", "failed", "stopped"}:
                usage = aggregate_usage([value for step, value in settled.get("step_usage", {}).items()
                                         if step.startswith(f"agent:{snap.id}:")])
                if settled.get("compacted_steps"):
                    # Earlier steps may be compacted out of the root; each
                    # step's own immutable receipt is authoritative.
                    usage = aggregate_usage(self._worker_receipt_usage(uid, chat_id, turn_id, snap.id))
                # A dead process cannot report its final monotonic duration.
                # Preserve the last durable measurement as an explicit lower bound.
                observed = data.get("updated_at") or data.get("created_at")
                self.publish_agent(uid, chat_id, turn_id, run_token=root["run_token"], agent_id=snap.id,
                                   patch={"status": "stopped", "usage": usage,
                                          "duration_ms": max(data.get("duration_ms", 0), self._observed_duration(data, observed)),
                                          "duration_incomplete": True,
                                          "ended_at": datetime.now(timezone.utc).isoformat()},
                                   event_id="reaped-" + snap.id)
        value = AgentCompletion()
        value.failure = {"code": "run_interrupted", "error": "The server connection ended before the response finished. The available results have been saved."}
        data = ref.get().to_dict()
        value.usage = root_usage(data)
        self.finish_run(uid, chat_id, turn_id, completion=value, status="cancelled", run_token=root["run_token"])
        return ref.get().to_dict() or {}
