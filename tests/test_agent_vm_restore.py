"""Restoring the VM from the app (since 2026-10-26, admins): the checkpoint
each message takes before its first VM call (VMSession.ready) brings the VM
back to how it was before that message (routers/agent.py restore_agent_vm),
never while a response runs, and the next message is told. Sprites is
httpx.MockTransport, the VM FakeVM; no provider is called.
"""
import json

import httpx
import pytest

from app.api.routers import agent as agent_router
from app.services import agent_vm
from app.services.agent_vm import SpritesBackend, VMUnavailable
from test_agent_runs import AUTH, UID, api, pending, store  # noqa: F401  (fixtures)
from test_agent_vm import _admin_allowance, fake_vm  # noqa: F401  (fixtures)


def sprites(handler):
    return SpritesBackend("token", transport=httpx.MockTransport(handler))


def test_sprites_restores_a_checkpoint_and_waits_for_completion():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        lines = [{"type": "info", "data": "Restoring filesystem..."}, {"type": "complete", "data": "Restored to v3"}]
        return httpx.Response(200, content="\n".join(json.dumps(line) for line in lines))
    sprites(handler).restore("consens-x", "v3")
    assert seen == [("POST", "/v1/sprites/consens-x/checkpoints/v3/restore")]

    def failing(request):
        return httpx.Response(200, content=json.dumps({"type": "error", "error": "disk full"}))
    with pytest.raises(VMUnavailable):
        sprites(failing).restore("consens-x", "v3")
    with pytest.raises(VMUnavailable):
        sprites(lambda request: httpx.Response(500)).restore("consens-x", "v3")
    with pytest.raises(VMUnavailable):
        sprites(lambda request: httpx.Response(200, content=json.dumps({"type": "info"}))).restore("consens-x", "v3")


def vm_turn(store, *, checkpoint="v3", status="completed", name=None, taken=None):
    """A message whose first VM call took ``checkpoint`` in the account's
    workspace (VMSession.summary: its name and when)."""
    from datetime import datetime, timezone
    from app.services import agent_workspace
    from uuid import uuid4
    chat, turn = pending(store, request_id=f"r-{checkpoint}-{status}-{uuid4().hex[:8]}")
    workspace = agent_vm.workspace_name(UID)
    if not agent_workspace.ref(store.db, UID).get().exists:
        agent_workspace.ref(store.db, UID).set({"provider": "fake", "name": workspace})
    store._transaction(lambda tx: tx.update(store._chat_ref(UID, chat), {"agent_vm": {
        "provider": "fake", "name": workspace, "workspace": True}}))
    taken = taken or datetime.now(timezone.utc).isoformat()
    store._transaction(lambda tx: tx.update(store._turn_ref(UID, chat, turn["id"]), {"status": status, "agent_vm": {
        "provider": "fake", "name": name or workspace, "checkpoint": checkpoint, "checkpoint_at": taken}}))
    name = workspace
    if status != "pending":
        store._transaction(lambda tx: tx.update(store._chat_ref(UID, chat), {"agent_lock_until": None}))
    return chat, turn["id"], name


@pytest.fixture
def admin_api(api, monkeypatch):
    # The VM: admins, or every account with AGENT_VM_ACCESS=all (routers/agent.py vm_allowed).
    monkeypatch.setattr(agent_router, "vm_allowed", lambda uid: True)
    return api


def test_an_admin_restores_the_vm_to_before_a_message(admin_api, fake_vm):
    client, store, _ = admin_api
    chat, turn_id, name = vm_turn(store)
    response = client.post(f"/agent/chats/{chat}/turns/{turn_id}/vm-restore", headers=AUTH)
    assert response.status_code == 200 and response.json() == {"status": "restored", "checkpoint": "v3"}
    assert ("restore", name, "v3") in fake_vm.calls and fake_vm.calls[-1] == ("close",)
    restored = store._chat_ref(UID, chat).get().to_dict()["agent_vm"]["restored"]
    assert restored["checkpoint"] == "v3" and restored["turn_id"] == turn_id and "told" not in restored


def test_restore_is_refused_while_a_response_runs_without_a_checkpoint_or_for_others(api, admin_api, fake_vm,
                                                                                      monkeypatch):
    client, store, _ = admin_api
    chat, turn_id, _ = vm_turn(store, status="pending")
    running = client.post(f"/agent/chats/{chat}/turns/{turn_id}/vm-restore", headers=AUTH)
    assert running.status_code == 409 and running.json()["code"] == "running"
    chat, turn_id, _ = vm_turn(store, checkpoint=None)
    missing = client.post(f"/agent/chats/{chat}/turns/{turn_id}/vm-restore", headers=AUTH)
    assert missing.status_code == 409 and missing.json()["code"] == "no_checkpoint"
    chat, turn_id, _ = vm_turn(store, checkpoint="v9")
    fake_vm.fail.add("restore")
    failed = client.post(f"/agent/chats/{chat}/turns/{turn_id}/vm-restore", headers=AUTH)
    assert failed.status_code == 503 and failed.json()["code"] == "vm_unavailable"
    assert not [call for call in fake_vm.calls if call[0] == "restore" and call[2] != "v9"]
    monkeypatch.setattr(agent_router, "vm_allowed", lambda uid: False)
    assert client.post(f"/agent/chats/{chat}/turns/{turn_id}/vm-restore", headers=AUTH).status_code == 403


def test_the_workspace_is_restored_only_while_no_chat_uses_it_and_every_chat_hears_of_it(admin_api, fake_vm):
    """Since 2026-10-27 the VM is the account's workspace: restoring it
    reaches every chat's folder, so no other chat's message may be running,
    and the other chats' next messages are told too (agent_workspace)."""
    from datetime import datetime, timedelta, timezone
    from app.services import agent_workspace
    client, store, _ = admin_api
    chat, turn_id, _ = vm_turn(store)
    other, _ = pending(store, request_id="other-chat")
    agent_workspace.claim(store, UID, chat, "earlier", provider="fake")
    agent_workspace.release(store, UID, "earlier")
    agent_workspace.claim(store, UID, other, "running", provider="fake")
    busy = client.post(f"/agent/chats/{chat}/turns/{turn_id}/vm-restore", headers=AUTH)
    assert busy.status_code == 409 and busy.json()["code"] == "running"
    agent_workspace.ref(store.db, UID).update({"lease": {
        "chat_id": other, "turn_id": "running", "until": datetime.now(timezone.utc) - timedelta(seconds=1)}})
    # A lease that ran out while its chat's response still runs (its run
    # lock): not under the running agent (runtime audit 2026-10-30, A2).
    still = client.post(f"/agent/chats/{chat}/turns/{turn_id}/vm-restore", headers=AUTH)
    assert still.status_code == 409 and still.json()["code"] == "running"
    # A run that died: its lock ran out too.
    store._chat_ref(UID, other).update({"agent_lock_until": datetime.now(timezone.utc) - timedelta(seconds=1)})
    done = client.post(f"/agent/chats/{chat}/turns/{turn_id}/vm-restore", headers=AUTH)
    assert done.status_code == 200 and ("restore", agent_vm.workspace_name(UID), "v3") in fake_vm.calls
    assert agent_workspace.record(store.db, UID)["restores"] == 1
    assert agent_workspace.claim(store, UID, other, "next", provider="fake").restored is True


def test_the_next_message_is_told_once(admin_api, fake_vm):
    client, store, _ = admin_api
    chat, turn_id, _ = vm_turn(store)
    assert client.post(f"/agent/chats/{chat}/turns/{turn_id}/vm-restore", headers=AUTH).status_code == 200
    contexts = []
    for request_id in ("after-1", "after-2"):
        payload = {"chat_id": chat, "question": "Go on.", "client_request_id": request_id, "bookmark_id": "agent_test"}
        assert client.post("/agent", json=payload, headers=AUTH).status_code == 200
        turn = store._turn_ref(UID, chat, agent_router._idempotent_turn_id(chat, request_id)).get().to_dict()
        contexts.append(turn["app_context"])
    assert agent_vm.VM_RESTORED_NOTE in contexts[0] and agent_vm.VM_RESTORED_NOTE not in contexts[1]
    assert store._chat_ref(UID, chat).get().to_dict()["agent_vm"]["restored"]["told"] is True


def test_only_a_recent_checkpoint_of_the_workspace_after_the_last_sign_out_goes_back(admin_api, fake_vm):
    """Security audit 2026-10-27: a chat's checkpoint from its own VM went to
    the workspace, and a restore brought back sign-ins after "Log out
    everywhere" and folders of deleted chats. Now a checkpoint must be the
    workspace's, at most RESTORE_DAYS old and taken after the last sign-out
    everywhere or chat deletion (agent_workspace.restorable)."""
    from datetime import datetime, timedelta, timezone
    from app.services import agent_workspace
    client, store, _ = admin_api
    old = (datetime.now(timezone.utc) - timedelta(days=agent_workspace.RESTORE_DAYS + 1)).isoformat()
    for kwargs in ({"name": agent_vm.vm_name(UID, "legacy")}, {"taken": old}, {"taken": "not a time"}):
        chat, turn_id, _ = vm_turn(store, **kwargs)
        refused = client.post(f"/agent/chats/{chat}/turns/{turn_id}/vm-restore", headers=AUTH)
        assert refused.status_code == 409 and refused.json()["code"] == "expired", kwargs
    chat, turn_id, _ = vm_turn(store, checkpoint="v7")
    agent_workspace.raise_restore_floor(store, UID)
    after_sign_out = client.post(f"/agent/chats/{chat}/turns/{turn_id}/vm-restore", headers=AUTH)
    assert after_sign_out.status_code == 409 and after_sign_out.json()["code"] == "expired"
    assert not [call for call in fake_vm.calls if call[0] == "restore"]
    # A checkpoint taken after the sign-out goes back. Stated a second later:
    # taken in the same instant as the floor it tied with it, by the clock alone.
    later = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
    chat, turn_id, _ = vm_turn(store, checkpoint="v8", taken=later)
    assert client.post(f"/agent/chats/{chat}/turns/{turn_id}/vm-restore", headers=AUTH).status_code == 200
    assert ("restore", agent_vm.workspace_name(UID), "v8") in fake_vm.calls
