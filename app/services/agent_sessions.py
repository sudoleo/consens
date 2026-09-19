"""Owner-bound delegation journal. Public messages are separate from turn traces.

The root receipt fences a producer, all paid steps and ordered event writes.
There is deliberately no resume path for paid steps after process loss.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from firebase_admin import firestore

from app.services import persistence_guard
from app.services import agent_quota, agent_budget_config
from app.services.agent_costs import aggregate_usage, remaining_reservation
from app.services.agent_runtime import AgentCapacityExceeded
from app.services.chat_store import ChatNotFound, TurnStatusConflict
from app.services.llm.provider_runtime import AnalysisBudgetExceeded, ProviderCancelled


class AgentSessionStore:
    def agent_ref(self, uid, chat_id, turn_id, agent_id):
        import re
        if not re.fullmatch(r"[a-f0-9]{32}", agent_id):
            raise ValueError("Invalid agent identity")
        return self._turn_ref(uid, chat_id, turn_id).collection("agents").document(agent_id)

    def _claim_delegated(self, uid, chat_id, turn_id, model, *, step, run_token, policy, reservation):
        root_ref = self.receipt_ref(uid, chat_id, turn_id)
        receipt_ref = self.receipt_ref(uid, chat_id, turn_id, step)
        chat_ref, turn_ref = self._chat_ref(uid, chat_id), self._turn_ref(uid, chat_id, turn_id)
        user_ref, active_ref = self.db.collection("users").document(uid), self.active_ref(uid)
        agent_id = step.split(":")[1] if step.startswith("agent:") else "orchestrator"
        index = int(step.split(":")[-1])
        budget_config = agent_budget_config.get_config(self.db)

        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            receipt, root, chat, turn, user, active = (ref.get(transaction=tx) for ref in
                (receipt_ref, root_ref, chat_ref, turn_ref, user_ref, active_ref))
            agent = self.agent_ref(uid, chat_id, turn_id, agent_id).get(transaction=tx) if agent_id != "orchestrator" else None
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
                if step != "completion:0" or not run_token or not policy or not policy.get("delegation"):
                    raise TurnStatusConflict("Delegation root is missing")
                if len(leases) >= 2:
                    raise AgentCapacityExceeded("Two agent responses are already running.")
                data = {"run_token": run_token, "run_status": "running", "policy": policy,
                        "lease_until": now + timedelta(seconds=policy["seconds"] + 30),
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
            if index and states.get(f"{prefix}:{index - 1}") != "succeeded":
                raise TurnStatusConflict("Previous model step has not succeeded")
            if agent is not None and (not agent.exists or (agent.to_dict() or {}).get("status") in {"stopped", "failed"}):
                raise TurnStatusConflict("Worker session is not runnable")
            tokens, cost = reservation
            day = agent_quota.period_key(budget_config)
            daily_ref = agent_quota.quota_ref(self.db, uid, day)
            daily = daily_ref.get(transaction=tx).to_dict() or {}
            # Review/synthesis can spend this run's protected budget; workers
            # and comparisons cannot consume it.
            protected = data.get("review_hold", 0)
            previous_daily_ref = None
            if data.get("quota_day") and data["quota_day"] != day:
                previous_daily_ref = agent_quota.quota_ref(self.db, uid, data["quota_day"])
                previous_daily = previous_daily_ref.get(transaction=tx).to_dict() or {}
                previous_daily["reserved"] = max(0, previous_daily.get("reserved", 0) - protected)
                daily = agent_quota.reserve(daily, protected, limit=budget_config['daily_token_limit'])
            can_spend = agent_id == "orchestrator" or (agent and (agent.to_dict() or {}).get("kind") == "judge")
            spend = min(protected, tokens) if can_spend else 0
            cost_hold = data.get("review_cost_hold", 0)
            cost_spend = min(cost_hold, cost) if can_spend else 0
            daily = agent_quota.reserve(daily, tokens - spend, limit=budget_config['daily_token_limit'])
            if (len(states) >= limits["max_calls"] or data["reserved_tokens"] + tokens > limits["max_tokens"]
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
            record = {"schema_version": 3, "purpose": "agent", "step": step, "agent_id": agent_id,
                      "quota_day": day, "quota_reserved": tokens,
                      "chat_id": chat_id, "turn_id": turn_id, "status": "running",
                      "model": model.snapshot(), "created_at": firestore.SERVER_TIMESTAMP}
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
        return self._transaction(operation)

    def protect_review(self, uid, chat_id, turn_id, run_token, tokens, cost=0):
        """Atomically protect synthesis/judges from all other concurrent runs."""
        ref = self.receipt_ref(uid, chat_id, turn_id)
        budget_config = agent_budget_config.get_config(self.db)
        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            root = ref.get(transaction=tx).to_dict() or {}
            if root.get("run_token") != run_token or root.get("run_status") != "running":
                raise TurnStatusConflict("Agent run is closed")
            day = agent_quota.period_key(budget_config)
            daily_ref = agent_quota.quota_ref(self.db, uid, day)
            daily = daily_ref.get(transaction=tx).to_dict() or {}
            protected = root.get("review_hold", 0)
            previous_ref = None
            if root["quota_day"] != day:
                previous_ref = agent_quota.quota_ref(self.db, uid, root["quota_day"])
                previous = previous_ref.get(transaction=tx).to_dict() or {}
                previous["reserved"] = max(0, previous.get("reserved", 0) - protected)
                extra = max(tokens, protected)
            else:
                extra = max(0, tokens - protected)
            daily = agent_quota.reserve(daily, extra, limit=budget_config['daily_token_limit'])
            protected_cost = max(cost, root.get("review_cost_hold", 0))
            if root["reserved_cost"] + protected_cost > root["policy"]["max_cost_nano_usd"]:
                raise AnalysisBudgetExceeded("Not enough cost budget for synthesis and review")
            tx.set(daily_ref, daily)
            if previous_ref:
                tx.set(previous_ref, previous)
            tx.update(ref, {"quota_day": day, "review_hold": max(tokens, protected), "review_cost_hold": protected_cost})
        self._transaction(operation)

    def save_review(self, uid, chat_id, turn_id, run_token, review, text):
        """Checkpoint exact text and review state before expensive work."""
        root_ref = self.receipt_ref(uid, chat_id, turn_id)
        turn_ref, chat_ref = self._turn_ref(uid, chat_id, turn_id), self._chat_ref(uid, chat_id)
        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            root, turn, chat = (r.get(transaction=tx).to_dict() or {} for r in (root_ref, turn_ref, chat_ref))
            if (root.get("run_token") != run_token or root.get("run_status") != "running"
                    or chat.get("status") != "active" or turn.get("status") != "pending"):
                raise TurnStatusConflict("Agent review is closed")
            tx.update(turn_ref, {"agent_review": review, "assistant_response": text})
        self._transaction(operation)

    @staticmethod
    def _delegated_settlement(data, step, status, usage):
        if not (data.get("policy") or {}).get("delegation"):
            return {}
        reserved = data["reservations"][step]
        tokens, cost = remaining_reservation(reserved, usage)
        return {"step_states": {**data["step_states"], step: status},
                "step_usage": {**data["step_usage"], step: usage},
                "reserved_tokens": data["reserved_tokens"] + tokens - reserved[0],
                "reserved_cost": data["reserved_cost"] + cost - reserved[1]}

    def publish_agent(self, uid, chat_id, turn_id, *, run_token, agent_id, patch=None, message=None, event_id=None):
        """Atomically mutate a session and append one deduplicated event/message."""
        root_ref = self.receipt_ref(uid, chat_id, turn_id)
        turn_ref, chat_ref = self._turn_ref(uid, chat_id, turn_id), self._chat_ref(uid, chat_id)
        agent_ref = self.agent_ref(uid, chat_id, turn_id, agent_id)
        event_id = event_id or uuid4().hex
        event_ref = turn_ref.collection("agent_events").document(event_id)
        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            root, agent, event, chat, turn = (ref.get(transaction=tx) for ref in (root_ref, agent_ref, event_ref, chat_ref, turn_ref))
            data = root.to_dict() or {}
            if not chat.exists or not turn.exists or (chat.to_dict() or {}).get("status") != "active":
                raise ChatNotFound("Chat not found")
            if data.get("run_token") != run_token:
                raise TurnStatusConflict("Agent session is closed")
            if event.exists:
                return event.to_dict()
            if data.get("run_status") != "running":
                raise TurnStatusConflict("Agent session is closed")
            ending = (patch or {}).get("status") in {"stopped", "failed"}
            if (data.get("cancel_requested") or data["lease_until"] <= datetime.now(timezone.utc)) and not ending:
                raise ProviderCancelled("Agent run stopped")
            seq = data.get("event_seq", 0) + 1
            if seq > 1024:
                raise AnalysisBudgetExceeded("Agent event limit reached")
            session = {**(agent.to_dict() or {}), **(patch or {}), "id": agent_id, "seq": seq,
                       "updated_at": datetime.now(timezone.utc).isoformat()}
            if not agent.exists:
                if data.get("agent_count", 0) >= 64:
                    raise AnalysisBudgetExceeded("Agent limit reached")
                if not session.get("assignment"):
                    raise TurnStatusConflict("Agent assignment is missing")
            if message:
                count = data.get("message_count", 0) + 1
                if count > data["policy"]["max_messages"]:
                    raise AnalysisBudgetExceeded("Agent message limit reached")
                if len(message["text"]) > max(data["policy"]["message_chars"], data["policy"]["result_chars"]):
                    raise ValueError("Agent message is too long")
                tx.set(agent_ref.collection("messages").document(event_id),
                       {**message, "id": event_id, "seq": seq, "created_at": session["updated_at"]})
                session["message_seq"] = seq
            public = {key: value for key, value in session.items() if key != "assignment"}
            result = {"type": "delegation", "version": 1, "id": event_id, "seq": seq,
                      "run_id": root_ref.id, "chat_id": chat_id, "turn_id": turn_id, "agent": public}
            tx.set(agent_ref, session)
            tx.set(event_ref, result)
            tx.update(root_ref, {"event_seq": seq, "agent_count": data.get("agent_count", 0) + int(not agent.exists),
                                "message_count": data.get("message_count", 0) + int(bool(message))})
            return result
        return self._transaction(operation)

    def check_delegation(self, uid, chat_id, turn_id, run_token):
        chat = self.get_chat(uid, chat_id)
        root = self.receipt_ref(uid, chat_id, turn_id).get().to_dict() or {}
        if (chat.get("status") != "active" or root.get("run_token") != run_token
                or root.get("run_status") != "running" or root.get("cancel_requested")):
            raise ProviderCancelled("Agent run stopped")

    def stop_delegation(self, uid, chat_id, turn_id):
        self.get_turn(uid, chat_id, turn_id)
        ref = self.receipt_ref(uid, chat_id, turn_id)
        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            root = ref.get(transaction=tx).to_dict() or {}
            if root.get("run_status") == "running":
                tx.update(ref, {"cancel_requested": True})
        self._transaction(operation)

    def delegation_view(self, uid, chat_id, turn_id, *, agent_id=None, after=0, limit=50):
        turn = self.get_turn(uid, chat_id, turn_id)
        root = self.reap_delegation(uid, chat_id, turn_id)
        if agent_id:
            ref = self.agent_ref(uid, chat_id, turn_id, agent_id)
            agent = ref.get()
            if not agent.exists:
                raise ChatNotFound("Agent not found")
            page = list(ref.collection("messages").order_by("seq").start_after({"seq": after}).limit(limit + 1).stream())
            return {"agent": agent.to_dict(), "messages": [s.to_dict() for s in page[:limit]],
                    "has_more": len(page) > limit}
        agents = [s.to_dict() for s in self._turn_ref(uid, chat_id, turn_id).collection("agents").limit(64).stream()]
        return {"agents": [{k: v for k, v in a.items() if k != "assignment"} for a in agents],
                "seq": root.get("event_seq", 0), "status": root.get("run_status", turn["status"]),
                "usage": aggregate_usage(list(root.get("step_usage", {}).values())) or turn.get("agent_usage")}

    def reap_delegation(self, uid, chat_id, turn_id):
        """Expired process leases become terminal unknown receipts, never retries."""
        from app.services.llm.agent_client import AgentCompletion
        ref = self.receipt_ref(uid, chat_id, turn_id)
        root = ref.get().to_dict() or {}
        if (root.get("run_status") != "running" or not (root.get("policy") or {}).get("delegation")
                or root["lease_until"] > datetime.now(timezone.utc)):
            return root
        self.stop_delegation(uid, chat_id, turn_id)
        for step, state in root["step_states"].items():
            if state == "running":
                self.settle(uid, chat_id, turn_id, completion=AgentCompletion(), status="cancelled", step=step, final=False)
        settled = ref.get().to_dict()
        for snap in self._turn_ref(uid, chat_id, turn_id).collection("agents").limit(64).stream():
            data = snap.to_dict()
            if data["status"] not in {"completed", "failed", "stopped"}:
                usage = aggregate_usage([value for step, value in settled.get("step_usage", {}).items()
                                         if step.startswith(f"agent:{snap.id}:")])
                self.publish_agent(uid, chat_id, turn_id, run_token=root["run_token"], agent_id=snap.id,
                                   patch={"status": "stopped", "usage": usage,
                                          "ended_at": datetime.now(timezone.utc).isoformat()},
                                   event_id="reaped-" + snap.id)
        value = AgentCompletion()
        data = ref.get().to_dict()
        value.usage = aggregate_usage(list(data.get("step_usage", {}).values()))
        self.finish_run(uid, chat_id, turn_id, completion=value, status="cancelled", run_token=root["run_token"])
        return ref.get().to_dict() or {}
