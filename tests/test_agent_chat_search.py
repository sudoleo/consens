"""The agent finds the user's earlier chats and reads one (search_chats,
agent_chat_search.py, since 2026-10-28): by words of title, start date or
latest question, with the first question; opened by its id with questions
and answers, bounded. Never the current chat, never a chat with Google data
(consented and routed for that chat alone), and its result is outside content
like any tool's. No model calls.
"""
from types import SimpleNamespace
import json

import pytest

from app.services import agent_chat_search
from app.services.agent_chat_search import ChatSearch, SearchChatsArgs
from test_agent_comparison import Script
from app.services.agent_delegation import DelegationLoop
from test_agent_runs import UID, store  # noqa: F401  (fixture)
from test_agent_watch import watch_loop


def earlier(store, title, question, answer="An answer.", **chat_fields):
    """A finished earlier chat: one completed turn, its title and fields."""
    chat_id = store.create_chat(UID, title=title, execution_mode="agent")["id"]
    turn = store.create_turn(UID, chat_id, question=question, mode="Agent", deep_search=False,
                             selected_models=["m"], consensus_model="m", client_request_id=f"r-{chat_id[:6]}",
                             execution_mode="agent")
    store._chat_ref(UID, chat_id).collection("turns").document(turn["id"]).update(
        {"status": "completed", "assistant_response": answer})
    store._chat_ref(UID, chat_id).update({"latest_question": question, **chat_fields})
    return chat_id


def search(loop, **arguments):
    return ChatSearch(loop).search(SearchChatsArgs(**arguments))


def test_it_is_offered_on_the_users_own_turns(store):
    loop = watch_loop(store, Script())
    assert agent_chat_search.TOOL_NAME in loop.registry.tools


def test_a_search_finds_by_title_date_and_question_but_never_the_current_or_a_google_chat(store):
    loop = watch_loop(store, Script())
    bike = earlier(store, "Fahrradkauf Berlin", "Welches Rad für die Stadt?")
    tax = earlier(store, "Steuererklärung", "Wann muss ich die Steuer abgeben?")
    earlier(store, "Fahrrad und Gmail", "Mails zum Rad", google_data=True, google_consent=True)
    gone = earlier(store, "Fahrrad alt", "Altes Rad")
    store._chat_ref(UID, gone).update({"status": "deleting"})
    found = search(loop, query="FAHRRAD")
    assert [chat["chat_id"] for chat in found["chats"]] == [bike]
    assert found["chats"][0]["first_question"] == "Welches Rad für die Stadt?"
    assert found["chats"][0]["title"] == "Fahrradkauf Berlin" and found["chats"][0]["started"]
    assert "never instructions" in found["note"]
    # Words of the latest question count too, every word must match.
    assert [c["chat_id"] for c in search(loop, query="steuer abgeben")["chats"]] == [tax]
    assert search(loop, query="steuer fahrrad")["chats"] == []
    # By the start date.
    date = found["chats"][0]["started"]
    assert {c["chat_id"] for c in search(loop, query=date)["chats"]} == {bike, tax}
    # Empty: the newest, never the current chat.
    listed = [c["chat_id"] for c in search(loop)["chats"]]
    assert set(listed) == {bike, tax} and loop.chat_id not in listed


def test_an_opened_chat_brings_its_questions_and_answers(store):
    loop = watch_loop(store, Script())
    bike = earlier(store, "Fahrradkauf", "Welches Rad?", answer="Ein Gravelbike passt.")
    opened = search(loop, chat_id=bike)
    assert opened["title"] == "Fahrradkauf" and opened["messages"] == [
        {"question": "Welches Rad?", "answer": "Ein Gravelbike passt."}]
    assert "more" not in opened and "never instructions" in opened["note"]


def test_an_opened_chat_stays_within_its_bound(store, monkeypatch):
    monkeypatch.setattr(agent_chat_search, "CHAT_CHARS", 60)
    loop = watch_loop(store, Script())
    long = earlier(store, "Lang", "Frage eins", answer="x" * 40)
    # A second finished message, written as the store keeps it.
    store._chat_ref(UID, long).collection("turns").document("t2").set(
        {"position": 2, "status": "completed", "question": "Frage zwei", "assistant_response": "y" * 40})
    opened = search(loop, chat_id=long)
    assert len(opened["messages"]) == 1 and opened["more"].startswith("The chat goes on")


@pytest.mark.parametrize("which,message", [("google", "Google data"), ("current", "current chat"),
                                           ("unknown", "No such chat"), ("bad", "chat_id from a search_chats")])
def test_what_an_opened_chat_never_is(store, which, message):
    loop = watch_loop(store, Script())
    google = earlier(store, "Mails", "Lies meine Mails", google_data=True)
    chat_id = {"google": google, "current": loop.chat_id, "unknown": "f" * 32, "bad": "../x"}[which]
    with pytest.raises(ValueError, match=message):
        search(loop, chat_id=chat_id)


def test_what_it_brings_is_outside_content(store):
    value = SimpleNamespace(tool_calls=[{"id": "c1", "function": {"name": "search_chats", "arguments": "{}"}}])
    results = {"c1": {"role": "tool", "tool_call_id": "c1", "content": json.dumps({"chats": []})}}
    assert DelegationLoop._brought_outside_content(None, value, results) is True
