"""Agent turn orchestration and idempotent shadow accounting.

Each paid step has a durable llm_calls receipt. Claims are never re-executed,
even after a process crash. Receipts contain no prompts or answers. Account
totals and settlement commit together; chat deletion cannot erase incurred
usage and account tombstones prevent resurrecting a deleted user.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib

from firebase_admin import firestore

from app.services import persistence_guard
from app.services.chat_store import ChatStore, ChatNotFound, TurnStatusConflict, TURN_PAGE_SIZE_MAX
from app.services.llm.agent_client import AgentModel


AGENT_SYSTEM_PROMPT = (
    "You are the helpful assistant in consens.io. Answer the user's question "
    "clearly and accurately, in their language. You have no tools or live web "
    "access in this mode. Do not claim to have searched or consulted other models."
)
CONTEXT_CHAR_LIMIT = 120_000


class AgentRunStore(ChatStore):
    def receipt_ref(self, uid, chat_id, turn_id):
        step_id = hashlib.sha256(f"agent\0{chat_id}\0{turn_id}\0completion:0".encode()).hexdigest()
        return self.db.collection("users").document(uid).collection("llm_calls").document(step_id)

    def messages(self, uid, chat_id, target, model=None):
        messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
        cursor = ""
        chars = len(AGENT_SYSTEM_PROMPT) + len(target["question"])
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

    def claim(self, uid, chat_id, turn_id, model: AgentModel):
        receipt_ref = self.receipt_ref(uid, chat_id, turn_id)
        chat_ref, turn_ref = self._chat_ref(uid, chat_id), self._turn_ref(uid, chat_id, turn_id)
        user_ref = self.db.collection("users").document(uid)

        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            receipt = receipt_ref.get(transaction=tx)
            chat = chat_ref.get(transaction=tx)
            turn = turn_ref.get(transaction=tx)
            user = user_ref.get(transaction=tx)
            if not chat.exists or not turn.exists or (chat.to_dict() or {}).get("status") != "active":
                raise ChatNotFound("Chat not found")
            if receipt.exists:
                return False
            chat_data, turn_data = chat.to_dict() or {}, turn.to_dict() or {}
            if (chat_data.get("execution_mode") != "agent" or turn_data.get("execution_mode") != "agent"
                    or turn_data.get("status") != "pending" or chat_data.get("agent_turn_id") != turn_id
                    or chat_data.get("agent_lock_until") <= datetime.now(timezone.utc)):
                raise TurnStatusConflict("Agent turn is no longer runnable")
            totals = dict((user.to_dict() or {}).get("agent_usage") or {})
            totals["calls"] = totals.get("calls", 0) + 1
            totals["unsettled_calls"] = totals.get("unsettled_calls", 0) + 1
            totals.update(currency="USD", billing_mode="simulation")
            tx.set(receipt_ref, {
                "schema_version": 1, "purpose": "agent", "step": "completion:0",
                "chat_id": chat_id, "turn_id": turn_id, "status": "running",
                "model": model.snapshot(), "created_at": firestore.SERVER_TIMESTAMP,
            })
            if user.exists:
                tx.update(user_ref, {"agent_usage": totals})
            else:
                tx.set(user_ref, {"agent_usage": totals})
            return True

        return self._transaction(operation)

    def settle(self, uid, chat_id, turn_id, *, completion, status):
        if status not in {"succeeded", "failed", "cancelled"}:
            raise ValueError("Invalid agent settlement status")
        receipt_ref = self.receipt_ref(uid, chat_id, turn_id)
        chat_ref, turn_ref = self._chat_ref(uid, chat_id), self._turn_ref(uid, chat_id, turn_id)
        user_ref = self.db.collection("users").document(uid)

        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            receipt = receipt_ref.get(transaction=tx)
            user = user_ref.get(transaction=tx)
            chat, turn = chat_ref.get(transaction=tx), turn_ref.get(transaction=tx)
            if not receipt.exists or not user.exists:
                raise ChatNotFound("Agent receipt not found")
            if (receipt.to_dict() or {}).get("status") != "running":
                return False
            usage = completion.usage
            totals = dict((user.to_dict() or {}).get("agent_usage") or {})
            totals["unsettled_calls"] = max(0, totals.get("unsettled_calls", 0) - 1)
            key = "measured_calls" if usage is not None else "unmetered_calls"
            totals[key] = totals.get(key, 0) + 1
            for field in ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens", "estimated_cost_nano_usd"):
                if usage is not None:
                    totals[field] = totals.get(field, 0) + usage[field]
            totals["updated_at"] = firestore.SERVER_TIMESTAMP
            tx.update(user_ref, {"agent_usage": totals})
            tx.update(receipt_ref, {
                "status": status, "usage": usage, "usage_status": "measured" if usage is not None else "unavailable",
                "generation_id": completion.generation_id, "finish_reason": completion.finish_reason,
                "settled_at": firestore.SERVER_TIMESTAMP,
            })
            chat_data = chat.to_dict() or {}
            if chat.exists and turn.exists and chat_data.get("status") == "active":
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
