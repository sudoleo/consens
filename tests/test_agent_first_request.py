"""From Send to the agent's first model request (since 2026-11-01).

Prod 2026-11-01: a casual question ("wo ist Zach Bryan aufgewachsen?") had
its answer after 9 s, of which the model took 6. Before its request left, the
server had made about 25 Firestore round trips one after another (the turn
read twice, the chat four times, the memory, the bookmark, the history with
every earlier answer's activity, the files, the claim, the allowance for the
browser) and copied OpenRouter's whole model catalog (about 550 models) some
45 times: 2-3 s before a model saw the question, on every message.

These tests count what lies on that path, not the wall clock: a change that
puts a read, a transaction or a catalog copy back between Send and the first
request fails here, with the place that added it.
"""
import collections
import threading
import traceback

import pytest

import test_chat_history as fakes
from app.services import agent_budget_config
from app.services.llm import agent_client
from app.services.llm.agent_client import AgentCompletion
from test_agent_runs import AUTH, api, receipt, store  # noqa: F401

pytestmark = pytest.mark.usefixtures("deepseek_default_agent")

# The turn's creation (one batched read, the commit) and the first step's
# claim (one batched read, the commit). Everything else is read beside them
# (run_agent's _turn_reads) or after the request left (the allowance).
ROUND_TRIPS_BEFORE_THE_REQUEST = 4
COMPARISON_MODELS = {"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}


class Trips:
    """Every round trip of the fake database: thread and the app's call site."""

    def __init__(self):
        self.rows, self.nested = [], threading.local()
        self.first_request = None

    def wrap(self, owner, name):
        original = getattr(owner, name)
        trips = self

        def counted(this, *args, **kwargs):
            # A transaction's commit applies its writes through the
            # documents: one round trip, not one per write.
            if getattr(trips.nested, "on", False):
                return original(this, *args, **kwargs)
            trips.nested.on = True
            try:
                if trips.first_request is None:
                    frames = [f for f in traceback.extract_stack()[:-1] if "app" in f.filename.replace("\\", "/").split("/")]
                    site = " < ".join(f"{f.name}:{f.lineno}" for f in reversed(frames[-3:]))
                    trips.rows.append((threading.current_thread().name, f"{name} {site}"))
                return original(this, *args, **kwargs)
            finally:
                trips.nested.on = False
        return counted

    def on_path(self):
        """The request's own threads: the route's and the run's. The reads
        beside them (agent-turn-read) and the reviewers' do not hold it up."""
        return [site for thread, site in self.rows
                if not thread.startswith(("agent-turn-read", "agent-review", "agent-work-log", "agent-allowance"))]


@pytest.fixture
def trips(monkeypatch):
    found = Trips()
    for owner, names in ((fakes.FakeDocumentRef, ("get", "set", "update", "delete")),
                         (fakes.FakeTransaction, ("get", "get_all", "commit")),
                         (fakes.FakeQuery, ("stream",)), (fakes.FakeCollectionRef, ("stream",)),
                         (fakes.FakeChatDatabase, ("get_all",)), (fakes.FakeAggregation, ("get",))):
        for name in names:
            monkeypatch.setattr(owner, name, found.wrap(owner, name))
    # Allowance enough for the first step's full search: an admission that
    # has to shrink its reservation claims again, by design.
    for tier in ("pro", "admin"):
        monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, tier, 50_000_000)
    return found


def send(api, trips, monkeypatch, question, request_id, chat_id=None):  # noqa: F811
    client, _, calls = api
    original = AgentCompletion.stream

    def stream(self, **kwargs):
        if self.step_id == "completion:0" and trips.first_request is None:
            trips.first_request = len(trips.rows)
        yield from original(self, **kwargs)
    monkeypatch.setattr(AgentCompletion, "stream", stream)
    chat_id = chat_id or client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]["id"]
    trips.rows.clear()
    trips.first_request = None
    response = client.post("/agent", json={"chat_id": chat_id, "question": question, "client_request_id": request_id,
                                           "bookmark_id": "agent_test", "comparison_models": COMPARISON_MODELS},
                           headers=AUTH)
    assert response.status_code == 200 and "event: final" in response.text, response.text
    assert trips.first_request is not None
    return chat_id


def test_a_message_reaches_its_model_after_four_round_trips(api, trips, monkeypatch):  # noqa: F811
    chat_id = send(api, trips, monkeypatch, "Hi", "first")
    # The second message of a chat: its history is read beside the turn too.
    send(api, trips, monkeypatch, "Wer hat gestern gewonnen?", "second", chat_id)
    path = trips.on_path()
    assert len(path) <= ROUND_TRIPS_BEFORE_THE_REQUEST, "\n".join(path)
    # The chat's earlier messages came with the reads beside the turn, as
    # the fields the conversation needs (AgentRunStore.history_page).
    beside = [site for thread, site in trips.rows if thread.startswith("agent-turn-read")]
    assert sum("history_page" in site for site in beside) == 1, beside


def test_the_history_read_ahead_is_read_again_when_a_turn_changed_in_between(store):  # noqa: F811
    from test_agent_runs import pending
    chat_id, first = pending(store, request_id="one")
    page = store.history_page("agent-user", chat_id, checked=True)
    # The first turn finished after the page was read and before the next
    # turn was created: the page shows it pending.
    store._turn_ref("agent-user", chat_id, first["id"]).update({"status": "completed", "assistant_response": "Done"})
    store._chat_ref("agent-user", chat_id).update({"agent_lock_until": None})
    _, second = pending(store, chat_id=chat_id, request_id="two", question="Question two")
    assert not store.history_current(page, second)
    messages = store.messages("agent-user", chat_id, second, first_page=page)
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[2]["content"] == "Done"


def test_a_run_builds_the_model_catalog_once(api, trips, monkeypatch):  # noqa: F811
    from app.services import agent_delegation
    built = collections.Counter()
    real = agent_client.agent_models

    def counted(**kwargs):
        if trips.first_request is None:
            built[threading.current_thread().name.split("_")[0]] += 1
        return real(**kwargs)
    monkeypatch.setattr(agent_client, "agent_models", counted)
    monkeypatch.setattr(agent_delegation, "agent_models", counted)
    send(api, trips, monkeypatch, "Hi", "catalog")
    # The route resolves the chat model and the reviewers' models; the loop
    # builds its worker catalog once (until 2026-11-01: twice per model).
    assert sum(built.values()) <= 1 + 1 + len(COMPARISON_MODELS), built


def test_a_chat_that_gained_google_data_after_the_first_read_keeps_its_rules(api, monkeypatch):  # noqa: F811
    """Review 2026-11-01: the route reads the chat before the turn exists. A
    turn in another tab may import mail in between and end; the turn's
    creation sees the chat as it is, and its rules hold for this message."""
    from app.services.chat_store import ChatStore
    client, store, calls = api
    chat_id = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]["id"]
    sweep = ChatStore.sweep_abandoned_turns

    def mail_arrives(self, uid, chat):
        sweep(self, uid, chat)
        self._chat_ref(uid, chat).update({"google_data": True})
    monkeypatch.setattr(ChatStore, "sweep_abandoned_turns", mail_arrives)
    response = client.post("/agent", json={"chat_id": chat_id, "question": "Hi", "client_request_id": "mail",
                                           "bookmark_id": "agent_test", "comparison_models": COMPARISON_MODELS},
                           headers=AUTH)
    assert response.status_code == 422 and "consent" in response.text
    assert not calls
    turns = store.list_turns("agent-user", chat_id)["turns"]
    assert [turn["status"] for turn in turns] == ["failed"]


def test_a_refused_message_sweeps_nothing(api, monkeypatch):  # noqa: F811
    """Review 2026-11-01: the sweep of abandoned turns may fail a turn, so it
    runs only for a message that passed the route's checks."""
    from app.api.routers import agent as route
    from app.services.chat_store import ChatStore
    client, store, calls = api
    monkeypatch.setattr(route, "is_user_pro", lambda uid: False)
    swept = threading.Event()
    monkeypatch.setattr(ChatStore, "sweep_abandoned_turns", lambda self, uid, chat: swept.set())
    chat_id = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]["id"]
    premium = next(iter(sorted(route.cfg.PREMIUM_MODELS)))
    response = client.post("/agent", json={"chat_id": chat_id, "question": "Hi", "client_request_id": "premium",
                                           "bookmark_id": "agent_test", "model_id": premium}, headers=AUTH)
    assert response.status_code in {403, 422} and not calls
    # The reads beside the route run on their own threads: give a sweep
    # among them the time to show.
    assert not swept.wait(.5)
