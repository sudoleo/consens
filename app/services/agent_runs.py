"""Agent turn orchestration and idempotent shadow accounting.

Each paid step has a durable llm_calls receipt. Claims are never re-executed,
even after a process crash. Receipts contain no prompts or answers. Account
totals and settlement commit together; chat deletion cannot erase incurred
usage and account tombstones prevent resurrecting a deleted user.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import re

from firebase_admin import firestore

from app.services import persistence_guard, prompt_config
from app.services.agent_runtime import AgentCapacityExceeded
from app.services.chat_store import ChatStore, ChatNotFound, TurnStatusConflict, TURN_PAGE_SIZE_MAX
from app.services.llm.agent_client import AgentModel
from app.services.llm.base import get_date_context
from app.services.prompt_defaults import AGENT_SYSTEM_PROMPT


CONTEXT_CHAR_LIMIT = 120_000
OWNER_CONCURRENT_RUNS = 2
RUN_LEASE_SECONDS = 300


def get_agent_system_prompt(model=None):
    config = prompt_config.get_config()
    prompt = f"{config['prompts']['agent']}\n\n{get_date_context(config['reference_timezone'])}"
    if model is not None:
        prompt += f"\nSelected model for this response: {model.label} ({model.model})."
    return prompt


class AgentRunStore(ChatStore):
    def active_ref(self, uid):
        return self.db.collection("users").document(uid).collection("chat_state").document("agent_runs")

    def receipt_ref(self, uid, chat_id, turn_id, step="completion:0"):
        if not re.fullmatch(r"completion:[0-2]", step):
            raise ValueError("Invalid agent step")
        key = hashlib.sha256(f"agent\0{chat_id}\0{turn_id}\0{step}".encode()).hexdigest()
        return self.db.collection("users").document(uid).collection("llm_calls").document(key)

    def messages(self, uid, chat_id, target, model=None):
        system_prompt = get_agent_system_prompt(model)
        messages = [{"role": "system", "content": system_prompt}]
        cursor = ""
        chars = len(system_prompt) + len(target["question"])
        while True:
            # Agent answers live on the turn itself. Do not issue an empty
            # model_answers subcollection query for every message in history.
            page = self._list_turn_snapshots(uid, chat_id, cursor=cursor, limit=TURN_PAGE_SIZE_MAX)
            for snapshot in page["snapshots"]:
                turn = snapshot.to_dict() or {}
                if turn["position"] >= target["position"] or turn["status"] != "completed":
                    continue
                question, answer = turn["question"], turn.get("assistant_response", turn.get("consensus", ""))
                chars += len(question) + len(answer)
                if chars > CONTEXT_CHAR_LIMIT:
                    raise ValueError("This conversation is too long. Start a new chat.")
                messages.extend([{"role": "user", "content": question},
                                 {"role": "assistant", "content": answer}])
            cursor = page.get("next_cursor") or ""
            if not cursor:
                break
        messages.append({"role": "user", "content": target["question"]})
        # Conservative byte bound for models with smaller windows. Actual
        # token counting and compaction are separate follow-up work.
        if model and sum(len(m["content"].encode("utf-8")) + 16 for m in messages) + model.max_output_tokens > model.context_length:
            raise ValueError("This conversation is too long for the selected model. Choose a model with a larger context or start a new chat.")
        return messages

    def claim(self, uid, chat_id, turn_id, model: AgentModel, *, step="completion:0", run_token="", policy=None):
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

        return self._transaction(operation)

    def settle(self, uid, chat_id, turn_id, *, completion, status, step="completion:0", final=True):
        if status not in {"succeeded", "failed", "cancelled"}:
            raise ValueError("Invalid agent settlement status")
        receipt_ref = self.receipt_ref(uid, chat_id, turn_id, step)
        chat_ref, turn_ref = self._chat_ref(uid, chat_id), self._turn_ref(uid, chat_id, turn_id)
        user_ref = self.db.collection("users").document(uid)
        active_ref = self.active_ref(uid)

        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            receipt = receipt_ref.get(transaction=tx)
            user = user_ref.get(transaction=tx)
            chat, turn = chat_ref.get(transaction=tx), turn_ref.get(transaction=tx)
            active = active_ref.get(transaction=tx)
            if not receipt.exists or not user.exists:
                raise ChatNotFound("Agent receipt not found")
            if (receipt.to_dict() or {}).get("status") != "running":
                return False
            usage = completion.usage
            totals = dict((user.to_dict() or {}).get("agent_usage") or {})
            totals["unsettled_calls"] = max(0, totals.get("unsettled_calls", 0) - 1)
            key = "measured_calls" if usage is not None and usage.get("input_tokens") is not None else "unmetered_calls"
            totals[key] = totals.get(key, 0) + 1
            if usage is not None and not usage.get("complete", True):
                totals["incomplete_calls"] = totals.get("incomplete_calls", 0) + 1
            if usage is not None and usage.get("estimated_cost_nano_usd") is not None:
                cost_key = "provider_cost_nano_usd" if usage.get("cost_source") == "provider" else "catalog_cost_nano_usd"
                totals[cost_key] = totals.get(cost_key, 0) + usage["estimated_cost_nano_usd"]
            for field in ("input_tokens", "output_tokens", "cached_input_tokens", "cache_write_tokens", "reasoning_tokens", "estimated_cost_nano_usd"):
                if usage is not None and usage.get(field) is not None:
                    totals[field] = totals.get(field, 0) + usage[field]
            totals["updated_at"] = firestore.SERVER_TIMESTAMP
            tx.update(user_ref, {"agent_usage": totals})
            leases = dict((active.to_dict() or {}).get("leases") or {})
            if final:
                leases.pop(self.receipt_ref(uid, chat_id, turn_id).id, None)
                tx.set(active_ref, {"leases": leases})
            tx.update(receipt_ref, {
                "status": status, "usage": usage,
                "usage_status": "unavailable" if usage is None else "measured" if usage.get("complete", True) else "partial",
                "generation_id": completion.generation_id, "finish_reason": completion.finish_reason,
                "settled_at": firestore.SERVER_TIMESTAMP,
            })
            chat_data = chat.to_dict() or {}
            if final and chat.exists and turn.exists and chat_data.get("status") == "active":
                if (turn.to_dict() or {}).get("status") == "pending":
                    patch = {"status": "completed" if status == "succeeded" else "failed",
                             "updated_at": firestore.SERVER_TIMESTAMP}
                    patch.update(agent_activity=completion.activity, agent_usage=usage,
                                 agent_finish_reason=completion.finish_reason,
                                 agent_reasoning_truncated=completion.reasoning_truncated)
                    if status == "succeeded":
                        # Legacy history/rendering contract; execution_mode is
                        # authoritative and no consensus computation took place.
                        patch.update(assistant_response=completion.text, completed_at=firestore.SERVER_TIMESTAMP,
                                     differences="", differences_data=None, sources=[], included_models=[])
                    else:
                        patch["error_code"] = "cancelled" if status == "cancelled" else "agent_failed"
                        patch["failed_at"] = firestore.SERVER_TIMESTAMP
                    tx.update(turn_ref, patch)
                if chat_data.get("agent_turn_id") == turn_id:
                    tx.update(chat_ref, {"agent_lock_until": datetime.now(timezone.utc),
                                         "updated_at": firestore.SERVER_TIMESTAMP})
            return True

        return self._transaction(operation)

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
            if last.get("status") == "running" or (status == "succeeded" and last.get("status") != "succeeded"):
                raise TurnStatusConflict("Agent step has not settled")
            tx.update(root_ref, {"run_status": status, "finished_at": firestore.SERVER_TIMESTAMP})
            leases = dict((active.to_dict() or {}).get("leases") or {})
            leases.pop(root_ref.id, None)
            tx.set(active_ref, {"leases": leases})
            chat_data, turn_data = chat.to_dict() or {}, turn.to_dict() or {}
            if chat.exists and turn.exists and chat_data.get("status") == "active" and turn_data.get("status") == "pending":
                patch = {"status": "completed" if status == "succeeded" else "failed", "updated_at": firestore.SERVER_TIMESTAMP,
                         "agent_activity": completion.activity, "agent_usage": completion.usage,
                         "agent_finish_reason": completion.finish_reason,
                         "agent_reasoning_truncated": completion.reasoning_truncated}
                if status == "succeeded":
                    patch.update(assistant_response=completion.text, completed_at=firestore.SERVER_TIMESTAMP,
                                 differences="", differences_data=None, sources=[], included_models=[])
                else:
                    patch.update(error_code="cancelled" if status == "cancelled" else "agent_failed", failed_at=firestore.SERVER_TIMESTAMP)
                tx.update(turn_ref, patch)
                if chat_data.get("agent_turn_id") == turn_id:
                    tx.update(chat_ref, {"agent_lock_until": datetime.now(timezone.utc), "updated_at": firestore.SERVER_TIMESTAMP})
            return True

        return self._transaction(operation)

    def release_unclaimed(self, uid, chat_id, turn_id):
        """Failures before the provider claim consume neither tokens nor quota."""
        chat_ref, turn_ref = self._chat_ref(uid, chat_id), self._turn_ref(uid, chat_id, turn_id)
        receipt_ref = self.receipt_ref(uid, chat_id, turn_id)
        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            chat, turn, receipt = chat_ref.get(transaction=tx), turn_ref.get(transaction=tx), receipt_ref.get(transaction=tx)
            if receipt.exists or not chat.exists or not turn.exists:
                return
            data = chat.to_dict() or {}
            if data.get("status") != "active" or data.get("agent_turn_id") != turn_id:
                return
            tx.update(turn_ref, {"status": "failed", "error_code": "agent_failed", "updated_at": firestore.SERVER_TIMESTAMP})
            tx.update(chat_ref, {"agent_lock_until": datetime.now(timezone.utc)})
        self._transaction(operation)
