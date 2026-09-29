"""Durable exact-content approvals. Agent tools can prepare, never confirm.

An external write is claimed once before I/O. Lost results remain unknown and
can only be reconciled by reads; neither a model retry nor a browser reload sends
again. Confirmation is a separate authenticated, user-facing API operation.
"""
import copy
from datetime import timedelta
import re

from app.services.agent_documents import digest
from app.services.agent_files import AgentFiles, ID_PATTERN
from app.services.google_connections import GoogleConnections, GoogleError, now


def public_action(data):
    return {key: data[key] for key in ("id", "kind", "status", "hash", "preview", "connection_id", "account", "turn_id",
        "created_at", "approval_until", "result", "error", "replaces") if key in data}


class AgentActions:
    def __init__(self, db, *, connections=None, files=None):
        self.db = db
        self.connections = connections or GoogleConnections(db)
        self.files = files or AgentFiles(db)

    def ref(self, uid, chat, action_id):
        if not re.fullmatch(ID_PATTERN, action_id):
            raise GoogleError("Invalid action ID.")
        return self.files.chats._chat_ref(uid, chat).collection("actions").document(action_id)

    def intent_ref(self, uid, data):
        return self.db.collection("users").document(uid).collection("google_write_intents").document(data.get("intent_hash") or data["hash"])

    def get(self, uid, chat, action_id):
        self.files.chats.get_chat(uid, chat)
        data = self.ref(uid, chat, action_id).get().to_dict()
        if not data or data["expires_at"] <= now().isoformat():
            raise GoogleError("Action not found or expired.", 404)
        return data

    def list(self, uid, chat):
        self.files.chats.get_chat(uid, chat)
        # Oldest first, so a revision never renders above its predecessor.
        # Action IDs are hashes; only created_at carries the real order.
        current = now().isoformat()
        snapshots = self.files.chats._chat_ref(uid, chat).collection("actions").order_by("created_at").limit(100).stream()
        return [public_action(data) for data in (s.to_dict() or {} for s in snapshots) if data.get("expires_at", "") > current]

    def prepare(self, uid, chat, turn, kind, connection_id, capability, payload, preview, *, replaces=None, require_capability=True):
        connection = self.connections.get(uid, connection_id, capability if require_capability else None)
        hashed = digest({"kind": kind, "connection": connection_id, "revision": connection["revision"], "payload": payload, "preview": preview})
        excluded = {"message_id"} if kind == "gmail_send" else ({"event_id"} if not payload.get("update") else set())
        intent = digest([kind, connection_id, {k: v for k, v in payload.items() if k not in excluded}])
        action_id = digest([turn, hashed, replaces])[:32]
        ref = self.ref(uid, chat, action_id)
        data = {"id": action_id, "kind": kind, "status": "pending", "hash": hashed, "payload": payload, "preview": preview,
            "connection_id": connection_id, "connection_revision": connection["revision"], "account": connection["email"],
            "capability": capability, "turn_id": turn, "created_at": now().isoformat(), "approval_until": (now() + timedelta(minutes=30)).isoformat(),
            "expires_at": (now() + timedelta(days=30)).isoformat(), "replaces": replaces}
        data["intent_hash"] = intent
        # Bound resource growth even for deliberately repeated preparation.
        for snapshot in self.files.chats._chat_ref(uid, chat).collection("actions").limit(100).stream():
            previous = snapshot.to_dict()
            if previous.get("intent_hash") == intent and previous.get("status") in {"executing", "unknown"}:
                raise GoogleError("An equivalent action has an unknown or pending provider result. Check its status before preparing another.", 409)
        def save(tx):
            self.files.guard(uid, chat, tx)
            current_connection = self.connections.get(uid, connection_id, capability if require_capability else None, tx)
            existing = ref.get(transaction=tx).to_dict()
            chat_ref = self.files.chats._chat_ref(uid, chat)
            chat_data = chat_ref.get(transaction=tx).to_dict() or {}
            old = self.ref(uid, chat, replaces).get(transaction=tx).to_dict() if replaces else None
            if current_connection["revision"] != connection["revision"]:
                raise GoogleError("The Google connection changed. Prepare again.", 409)
            if existing:
                return existing
            count = chat_data.get("agent_action_count", 0)
            if count >= 100:
                raise GoogleError("Action history is full. Start a new chat.")
            if replaces and (not old or old.get("status") not in {"pending", "rejected", "failed"}):
                raise GoogleError("That action can no longer be revised. Check its status.", 409)
            if replaces and (old.get("kind") != kind or old.get("connection_id") != connection_id):
                raise GoogleError("A revision must use the same action type and Google account.", 409)
            if replaces:
                tx.update(self.ref(uid, chat, replaces), {"status": "superseded"})
            tx.set(ref, data)
            tx.update(chat_ref, {"agent_action_count": count + 1})
            return data
        return public_action(self.files.chats._transaction(save))

    def renew(self, uid, chat, action_id, expected_hash, *, remove_recipients=()):
        """Prepare the displayed proposal again without a model call.

        Used after an approval expired, after the user granted a missing
        permission, or to drop a flagged email recipient. The content can only
        shrink, never grow. The result is a new action under the current
        connection revision that supersedes the old one and needs a fresh
        review; nothing is sent here.
        """
        old = self.get(uid, chat, action_id)
        if old.get("hash") != expected_hash:
            raise GoogleError("The action changed. Review the current version.", 409)
        if old.get("status") not in {"pending", "rejected", "failed"}:
            raise GoogleError("This action can no longer be prepared again. Check its status.", 409)
        payload, preview = copy.deepcopy(old["payload"]), copy.deepcopy(old["preview"])
        if old["kind"] == "gmail_send":
            from app.services.agent_gmail import renew_draft
            connection = self.connections.get(uid, old["connection_id"])
            payload, preview = renew_draft(payload, preview, connection, remove_recipients, old["id"], old["turn_id"])
            require_capability = False
        elif remove_recipients:
            raise GoogleError("Only email recipients can be removed here.")
        else:
            require_capability = True
            if payload.get("update"):
                # The stored "before" must still describe the live event.
                self.handler(old).ensure_unchanged(uid, old)
        return self.prepare(uid, chat, old["turn_id"], old["kind"], old["connection_id"], old["capability"], payload, preview,
            replaces=old["id"], require_capability=require_capability)

    def reject(self, uid, chat, action_id, expected_hash):
        ref = self.ref(uid, chat, action_id)
        def reject(tx):
            self.files.guard(uid, chat, tx)
            data = ref.get(transaction=tx).to_dict() or {}
            if data.get("hash") != expected_hash or data.get("status") != "pending":
                raise GoogleError("The action changed or is already being processed.", 409)
            tx.update(ref, {"status": "rejected"})
        self.files.chats._transaction(reject)
        return public_action(self.get(uid, chat, action_id))

    def handler(self, data):
        if data["kind"] == "calendar_event":
            from app.services.agent_calendar import CalendarActions
            return CalendarActions(self.connections)
        if data["kind"] == "gmail_send":
            from app.services.agent_gmail import GmailActions
            return GmailActions(self.connections)
        raise GoogleError("This action is not supported.")

    def confirm(self, uid, chat, action_id, expected_hash):
        ref = self.ref(uid, chat, action_id)
        def claim(tx):
            self.files.guard(uid, chat, tx)
            data = ref.get(transaction=tx).to_dict() or {}
            if data.get("hash") != expected_hash:
                raise GoogleError("The action content changed. Review the current preview.", 409)
            if data.get("expires_at", "") <= now().isoformat():
                raise GoogleError("Action not found or expired.", 404)
            if data.get("status") in {"succeeded", "executing", "unknown"}:
                return data, False
            if data.get("status") != "pending" or data["approval_until"] <= now().isoformat():
                raise GoogleError("This proposal is no longer confirmable. Prepare a new version.", 409)
            connection = self.connections.get(uid, data["connection_id"], data["capability"], tx)
            if connection["revision"] != data["connection_revision"]:
                raise GoogleError("Google authorization changed. Prepare and review a new proposal.", 409)
            if digest({"kind": data["kind"], "connection": data["connection_id"], "revision": data["connection_revision"],
                "payload": data["payload"], "preview": data["preview"]}) != expected_hash:
                raise GoogleError("Action integrity check failed.", 409)
            intent_ref = self.intent_ref(uid, data)
            intent = intent_ref.get(transaction=tx).to_dict() or {}
            if intent.get("status") in {"executing", "unknown"} and intent.get("action_id") != action_id and intent.get("expires_at", "") > now().isoformat():
                raise GoogleError("An equivalent action has an unresolved result in another chat. Check it before sending again.", 409)
            tx.update(ref, {"status": "executing", "confirmed_at": now().isoformat()})
            tx.set(intent_ref, {"action_id": action_id, "chat_id": chat, "status": "executing", "expires_at": data["expires_at"]})
            return {**data, "status": "executing"}, True
        data, claimed = self.files.chats._transaction(claim)
        if not claimed:
            return public_action(data)
        try:
            result = self.handler(data).execute(uid, data, self.files, chat)
            patch = {"status": "succeeded", "result": result, "error": None}
        except GoogleError as exc:
            patch = {"status": "unknown" if exc.uncertain else "failed", "error": str(exc)}
        except Exception:
            # Includes process/transport adapter failures after the durable claim.
            patch = {"status": "unknown", "error": "The provider result is unknown. Check status; do not create a duplicate action."}
        self.finish(uid, chat, ref, data["hash"], patch)
        return public_action(self.get(uid, chat, action_id))

    def finish(self, uid, chat, ref, expected_hash, patch):
        def finish(tx):
            self.files.guard(uid, chat, tx)
            current = ref.get(transaction=tx).to_dict() or {}
            intent_ref = self.intent_ref(uid, current) if current else None
            intent = intent_ref.get(transaction=tx).to_dict() if intent_ref else None
            if current.get("hash") == expected_hash and current.get("status") in {"executing", "unknown"}:
                tx.update(ref, patch)
                if intent and intent.get("action_id") == current["id"]:
                    tx.update(intent_ref, {"status": patch["status"]})
        self.files.chats._transaction(finish)

    def reconcile(self, uid, chat, action_id):
        data = self.get(uid, chat, action_id)
        if data["status"] not in {"executing", "unknown"}:
            return public_action(data)
        if data["status"] == "executing" and data.get("confirmed_at", "") > (now() - timedelta(seconds=60)).isoformat():
            return public_action(data)
        result = self.handler(data).reconcile(uid, data)
        patch = {"status": "succeeded", "result": result, "error": None} if result else {"status": "unknown", "error": "No conclusive provider result yet. Nothing was sent again."}
        self.finish(uid, chat, self.ref(uid, chat, action_id), data["hash"], patch)
        return public_action(self.get(uid, chat, action_id))
