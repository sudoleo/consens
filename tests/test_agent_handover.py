"""The next message while the reviewers review.

The run hands the chat over once its answer is fixed (agent_runs.hand_over):
the next message starts at once, reads the fixed answer, and the reviewers'
marks still land on the turn they review. Kept until its reviewers were done,
about 10 s after its answer stood, the chat would make a message sent in
between wait in the browser ("Send after this response").
"""
import json
from datetime import datetime, timedelta, timezone

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


def test_the_next_message_s_sweep_leaves_a_long_turn_under_review_alone(store, monkeypatch):  # noqa: F811
    """A two-hour workspace turn is older than the abandoned-turn cutoff
    when its answer stands; the next message's sweep right after the
    hand-over must not fail it while its reviewers work."""
    script = Audit()
    loop = audit_loop(store, script)
    handed_over = AgentRunStore.hand_over
    seen = {}

    def and_send_the_next(self, uid, chat_id, turn_id, **kwargs):
        handed = handed_over(self, uid, chat_id, turn_id, **kwargs)
        self._turn_ref(uid, chat_id, turn_id).update({"created_at": datetime.now(timezone.utc) - timedelta(minutes=40)})
        # What the route does for the next message: sweep, then create.
        self.sweep_abandoned_turns(uid, chat_id)
        seen["after_sweep"] = self._turn_ref(uid, chat_id, turn_id).get().to_dict()
        seen["next"] = next_turn(self, chat_id)
        return handed
    monkeypatch.setattr(AgentRunStore, "hand_over", and_send_the_next)
    list(loop.run())
    assert seen["after_sweep"]["status"] == "pending"
    turn = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert turn["status"] == "completed" and turn["agent_review"]["status"] == "succeeded"
    # Half an hour after the answer stood, a turn nobody finished is retired.
    later = datetime.now(timezone.utc) + timedelta(minutes=31)
    chat_id, stuck = loop.chat_id, seen["next"]["id"]
    store._turn_ref(UID, chat_id, stuck).update({"agent_answer_fixed_at": datetime.now(timezone.utc),
                                                 "created_at": datetime.now(timezone.utc) - timedelta(hours=2)})
    assert store.purge_abandoned_turns(UID, chat_id) == []
    assert store.purge_abandoned_turns(UID, chat_id, now=later) == [stuck]


def test_the_reaper_keeps_an_answer_that_already_stood(store, monkeypatch):  # noqa: F811
    """The process dies during the review (hard kill): the reaper ends the
    run as cancelled, the user already took the answer and may have gone on.
    The turn stays answered, with its sources; only its review is cut off."""
    from app.services.llm.agent_client import AgentCompletion
    script = Audit()
    loop = audit_loop(store, script)
    handed_over = AgentRunStore.hand_over
    seen = {}

    def and_die(self, uid, chat_id, turn_id, **kwargs):
        handed = handed_over(self, uid, chat_id, turn_id, **kwargs)
        self._turn_ref(uid, chat_id, turn_id).update({"sources": [{"url": "https://example.com/a", "title": "A"}]})
        seen["fixed"] = self._turn_ref(uid, chat_id, turn_id).get().to_dict()
        root = self.receipt_ref(uid, chat_id, turn_id).get().to_dict()
        reaped = AgentCompletion()
        reaped.failure = {"code": "run_interrupted", "error": "The server connection ended."}
        self.finish_run(uid, chat_id, turn_id, completion=reaped, status="cancelled", run_token=root["run_token"])
        return handed
    monkeypatch.setattr(AgentRunStore, "hand_over", and_die)
    list(loop.run())
    turn = store._turn_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert turn["status"] == "completed" and "agent_failure" not in turn and "error_code" not in turn
    assert turn["assistant_response"] == seen["fixed"]["assistant_response"] == ANSWER
    assert [source["url"] for source in turn["sources"]] == ["https://example.com/a"]
    assert turn["agent_review"]["status"] not in {"required", "running"}
    assert turn.get("agent_activity") == seen["fixed"].get("agent_activity")


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
