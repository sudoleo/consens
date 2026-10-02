"""Google approval claims in Firestore; only the external write is replaced."""
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet
import uuid
import pytest
from app.services.agent_actions import AgentActions
from app.services.google_connections import GoogleConnections, GoogleError, Wire
from app.services.chat_store import ChatNotFound
from native_support import native_db, race, tree


@pytest.mark.parametrize("kind,capability", [("gmail_send", "gmail_send"), ("calendar_event", "calendar_write")])
def test_native_google_confirmation_one_attempt_and_unknown_never_retries(native_db, monkeypatch, kind, capability):
    db, uid = native_db, native_db.owner()
    for key, value in {"GOOGLE_INTEGRATIONS_ENABLED": "1", "GOOGLE_CLIENT_ID": "fixture-client",
        "GOOGLE_CLIENT_SECRET": "fixture-secret", "GOOGLE_REDIRECT_URI": "https://fixture.invalid/agent/google/callback",
        "GOOGLE_TOKEN_KEYS": Fernet.generate_key().decode()}.items():
        monkeypatch.setenv(key, value)
    connections = GoogleConnections(db)
    connection_id = uuid.uuid4().hex
    connection = connections.ref(uid, connection_id)
    connection.set({"id": connection_id, "status": "connected", "revision": "original",
        "email": "fixture@example.invalid", "capabilities": [capability, "gmail_read", "calendar_read"],
        "credentials": connections.seal(uid, connection_id, {"access_token": "dummy-local-access", "refresh_token": "dummy-local-refresh",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()})})
    actions = AgentActions(db, connections=connections)
    chat = actions.files.chats.create_chat(uid, execution_mode="agent")["id"]
    payload = {"from": "fixture@example.invalid", "to": ["recipient@example.invalid"], "cc": [], "bcc": [],
        "subject": "Approved fixture", "message_id": "<native-fixture@example.invalid>", "reply": None,
        "body": "Explicitly approved text", "attachments": []} if kind == "gmail_send" else {
        "fields": {"summary": "Approved fixture"}, "calendar_id": "primary", "event_id": "nativefixture", "update": False}
    proposal = actions.prepare(uid, chat, "turn-a", kind, connection_id, capability, payload, {"summary": "Exact preview"})
    attempts = []
    def wire(self, method, url, **kwargs):
        if method != "GET":
            attempts.append((method, url, kwargs))
            raise GoogleError("Transport response lost", uncertain=True)
        return {}
    # Only the actual external HTTP edge is replaced; payload construction,
    # sealed token reads, capability/revision guards and quotas all execute.
    monkeypatch.setattr(Wire, "request", wire)
    def confirm():
        return AgentActions(db).confirm(uid, chat, proposal["id"], proposal["hash"])
    results = race(confirm, confirm)
    assert len(attempts) == 1
    assert all(result["status"] in {"executing", "unknown"} for result in results)
    assert confirm()["status"] == "unknown"
    assert actions.reconcile(uid, chat, proposal["id"])["status"] == "unknown"
    assert len(attempts) == 1
    before = tree(db.collection("users").document(uid))
    with pytest.raises((GoogleError, ChatNotFound)):
        AgentActions(db).confirm(db.owner(), chat, proposal["id"], proposal["hash"])
    assert tree(db.collection("users").document(uid)) == before


@pytest.mark.parametrize("change", ["revision", "approval", "hash", "superseded"])
def test_native_google_changed_authority_or_content_performs_no_write(native_db, monkeypatch, change):
    db, uid = native_db, native_db.owner()
    actions = AgentActions(db)
    cid = uuid.uuid4().hex
    ref = actions.connections.ref(uid, cid)
    ref.set({"id": cid, "status": "connected", "revision": "old", "email": "test@example.invalid", "capabilities": ["gmail_send"]})
    chat = actions.files.chats.create_chat(uid, execution_mode="agent")["id"]
    action = actions.prepare(uid, chat, "turn", "gmail_send", cid, "gmail_send", {"text": "Body"}, {"subject": "Preview"})
    if change == "revision":
        ref.update({"revision": "new"})
    elif change == "approval":
        actions.ref(uid, chat, action["id"]).update({"approval_until": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()})
    elif change == "superseded":
        actions.prepare(uid, chat, "turn", "gmail_send", cid, "gmail_send", {"text": "New body"}, {"subject": "New preview"}, replaces=action["id"])
    else:
        action["hash"] = "0" * 64
    monkeypatch.setattr(AgentActions, "handler", lambda *args: pytest.fail("Rejected action reached external provider"))
    before = tree(db.collection("users").document(uid))
    with pytest.raises(GoogleError):
        actions.confirm(uid, chat, action["id"], action["hash"])
    assert tree(db.collection("users").document(uid)) == before
