"""The next message while the reviewers review (since 2026-11-01).

Until then a chat stayed reserved for a turn until its reviewers were done,
about 10 s after its answer stood: a message sent in between waited in the
browser ("Send after this response"). Now the run hands the chat over once
its answer is fixed (agent_runs.hand_over): the next message starts at once,
reads the fixed answer, and the reviewers' marks still land on the turn they
review.
"""
import json
from datetime import datetime, timezone

from app.services.agent_runs import AgentRunStore
from app.services.llm.agent_client import AgentModel
from test_agent_audit import ANSWER, Audit, audit_loop
from test_agent_first_request import COMPARISON_MODELS
from test_agent_runs import AUTH, UID, api, store  # noqa: F401  (fixtures)


def next_turn(store, chat_id, request_id="next"):
    model = AgentModel()
    return store.create_turn(UID, chat_id, question="And then?", mode="Agent", deep_search=False,
                             selected_models=[model.model], consensus_model=model.model,
                             client_request_id=request_id, execution_mode="agent")


def test_the_next_message_starts_while_the_reviewers_review(store, monkeypatch):  # noqa: F811
    script = Audit()
    loop = audit_loop(store, script)
    seen = {}
    handed_over = AgentRunStore.hand_over

    def and_send_the_next(self, uid, chat_id, turn_id, **kwargs):
        # The user sends the next message the moment the answer stands:
        # before the reviewers' final round claims its first step.
        handed = handed_over(self, uid, chat_id, turn_id, **kwargs)
        chat = self._chat_ref(uid, chat_id).get().to_dict()
        assert chat["agent_lock_until"] <= datetime.now(timezone.utc)
        leases = (self.active_ref(uid).get().to_dict() or {}).get("leases") or {}
        assert self.receipt_ref(uid, chat_id, turn_id).id not in leases
        seen["next"] = next_turn(self, chat_id)
        seen["history"] = self.messages(uid, chat_id, seen["next"])
        return handed
    monkeypatch.setattr(AgentRunStore, "hand_over", and_send_the_next)
    events = list(loop.run())
    assert loop.handed_over is True
    # The browser takes the answer as done there, before the review's end.
    kinds = [e.get("type") for e in events]
    assert kinds.count("handover") == 1
    handover = kinds.index("handover")
    assert "".join(e["text"] for e in events[:handover] if e.get("type") == "delta") == ANSWER
    assert any(e.get("type") == "review" and e["review"]["status"] == "succeeded" for e in events[handover:])
    # The next message read the fixed answer while it was still under review.
    history = seen["history"]
    assert [m["role"] for m in history] == ["system", "user", "assistant", "user"]
    assert history[2]["content"] == ANSWER and history[-1]["content"].endswith("And then?")
    # The reviewers finished on the first turn, with the chat already the next one's.
    turn = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert turn["status"] == "completed" and turn["agent_review"]["status"] == "succeeded"
    assert [(r["provider"], r["status"]) for r in turn["agent_review"]["audit"]["reviewers"]] == [
        ("anthropic", "completed"), ("openai", "completed")]
    assert script.rounds == {"anthropic": ["final"], "openai": ["final"]}
    # Its end left the next message's reservation alone.
    chat = store._chat_ref(UID, loop.chat_id).get().to_dict()
    assert chat["agent_turn_id"] == seen["next"]["id"] and chat["agent_lock_until"] > datetime.now(timezone.utc)


def test_without_a_hand_over_the_chat_stays_reserved_until_the_end(store, monkeypatch):  # noqa: F811
    """A run that no longer holds its chat (stopped, reaped) does not hand it
    over and ends as before."""
    script = Audit()
    loop = audit_loop(store, script)
    monkeypatch.setattr(AgentRunStore, "hand_over", lambda self, *args, **kwargs: False)
    events = list(loop.run())
    assert loop.handed_over is False and not any(e.get("type") == "handover" for e in events)
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["status"] == "completed"


def test_a_turn_under_review_carries_its_answer_for_the_next_message(store):  # noqa: F811
    from test_agent_runs import pending
    chat_id, first = pending(store, request_id="one")
    store._turn_ref(UID, chat_id, first["id"]).update({"agent_answer_fixed_at": datetime.now(timezone.utc),
                                                      "assistant_response": "Fixed"})
    store._chat_ref(UID, chat_id).update({"agent_lock_until": datetime.now(timezone.utc)})
    page = store.history_page(UID, chat_id, checked=True)
    second = next_turn(store, chat_id, "two")
    # A pending turn whose answer stands holds: no second read.
    assert store.history_current(page, second)
    messages = store.messages(UID, chat_id, second, first_page=page)
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"] and messages[2]["content"] == "Fixed"


def test_the_stream_says_handover_with_the_saved_turn_before_its_final_frame(api):  # noqa: F811
    client, store, _ = api
    chat_id = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]["id"]
    response = client.post("/agent", json={"chat_id": chat_id, "question": "Hi", "client_request_id": "handover",
                                           "bookmark_id": "agent_test", "comparison_models": COMPARISON_MODELS},
                           headers=AUTH)
    text = response.text
    assert response.status_code == 200 and text.count("event: handover") == 1
    assert text.index("event: handover") < text.index("event: final")
    frame = json.loads(text.split("event: handover\ndata: ", 1)[1].split("\n", 1)[0])
    # The turn as the final frame names it, its review still running, and
    # the chat entry saved: the browser adopts it like a final answer.
    assert frame["turn"]["consensus"] == "A helpful answer" and frame["turn"]["status"] == "pending"
    assert frame["turn"]["agent_review"]["status"] in {"required", "running"}
    assert frame["bookmark_meta"]["id"] == "agent_test"
