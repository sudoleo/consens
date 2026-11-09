"""web_search: the agent's own web search as a tool on Exa (agent_web_search.py).

Registered for the agent's own steps of a chat run while Exa is available;
those steps then carry no search of the provider. Its hits are the app's:
the tool's result, the work log the reviewers read, what read_source counts
as found, the timeline. Each search is charged to the day's allowance with a
receipt of its own. Exa itself is a stub here (tests/test_exa.py has the client).
"""
import json
import threading
import time

import pytest

from app.services import agent_quota, agent_web_search, exa
from app.services.agent_audit import (ENTRY_CHARS, REVIEW_SEARCH_INSIDE, REVIEW_SEARCH_TOOL, SEARCH_ENTRY_CHARS,
                                      review_entry, review_system_prompt, tool_brief)
from app.services.agent_costs import aggregate_usage, service_usage
from app.services.agent_delegation import CONCURRENT_TOOLS, OWN_CONTENT_TOOLS
from app.services.agent_sessions import root_usage
from app.services.agent_tools import SEARCH_RESULT_CHARACTERS, SEARCH_RESULTS, ToolRegistry
from app.services.agent_web_search import QUERIES_PER_CALL, UNTRUSTED_NOTE, WebSearch, WebSearchArgs, site
from app.services.agent_work_log import TOOL_DATA, UNTRUSTED_DATA
from app.services.llm.provider_runtime import ProviderCancellation, ProviderCancelled
from app.services.prompt_defaults import AGENT_PROVIDER_SEARCH_FACT
from test_agent_runs import UID, store  # noqa: F401  (fixture)
from test_agent_web_fetch import Plan, chat_loop, tool_events

ANSWER = "The first option costs 100 euros per month."


def hit(url, title="Report", text="The first option costs 100.", published="2026-11-03"):
    return {"url": url, "title": title, **({"published": published} if published else {}), "excerpts": [text]}


@pytest.fixture
def searches(monkeypatch):
    """Exa with a key; exa.search answers from ``searches.found`` (query ->
    hits or an exception) and records every call."""
    class Searches:
        found, calls, lock = {}, [], threading.Lock()
        cost = 7_000_000

    def search(query, **options):
        with Searches.lock:
            Searches.calls.append((query, options))
        outcome = Searches.found.get(query, [hit(f"https://example.org/{len(query)}")])
        if isinstance(outcome, Exception):
            raise outcome
        return {"hits": outcome, "cost_nanos": Searches.cost, "notes": []}

    Searches.found, Searches.calls = {}, []
    monkeypatch.setenv(exa.KEY_ENV, "key")
    monkeypatch.setattr(exa, "search", search)
    exa.reset()
    yield Searches
    exa.reset()


def search_call(*queries, **more):
    return "web_search", {"queries": list(queries), **more}


def results(loop):
    ids = {call["id"] for m in loop.messages if m.get("role") == "assistant"
           for call in m.get("tool_calls") or [] if call["function"]["name"] == "web_search"}
    return [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool" and m["tool_call_id"] in ids]


def run(store, plan, **kwargs):
    loop = chat_loop(store, plan, **kwargs)
    events = list(loop.run())
    return loop, events, store.get_turn(UID, loop.chat_id, loop.turn_id)


# --- The run -----------------------------------------------------------------

def test_the_agent_searches_with_its_tool_and_answers_from_the_hits(store, searches):
    searches.found = {"price option one": [hit("https://example.org/report"), hit("https://example.net/other", "")],
                      "option one 2026": [hit("https://example.org/report"), hit("https://example.com/news", "News")]}
    plan = Plan([[search_call("price option one", "option one 2026")]], answer=ANSWER)
    loop, events, turn = run(store, plan)
    assert turn["status"] == "completed" and turn["assistant_response"] == ANSWER
    # The agent's requests carry the tool, and no search of the provider.
    assert plan.steps[0][0] == "routing" and "web_search" in plan.steps[0][1]
    assert all("openrouter:web_search" not in names for kind, names in plan.steps if kind in {"routing", "answer"})
    # Every search with the same bounds, side by side.
    assert sorted(query for query, _ in searches.calls) == ["option one 2026", "price option one"]
    assert all(options == {"results": SEARCH_RESULTS, "characters": SEARCH_RESULT_CHARACTERS, "domains": (),
                           "since": ""} for _, options in searches.calls)
    [result] = results(loop)
    assert result == {"note": UNTRUSTED_NOTE, "searches": [
        {"query": "price option one", "results": [hit("https://example.org/report"), hit("https://example.net/other", "")]},
        # A page found again is listed once.
        {"query": "option one 2026", "results": [hit("https://example.com/news", "News")],
         "also_above": ["https://example.org/report"]}]}
    # The timeline: what was searched for, how many searches ran, the pages
    # (the first of every search before the second of any).
    running, done = tool_events(events, "web_search")
    assert running["status"] == "running" and running["queries"] == ["price option one", "option one 2026"]
    assert done["status"] == "succeeded" and done["count"] == 2 and "outcome" not in done
    assert [source["url"] for source in done["sources"]] == [
        "https://example.org/report", "https://example.com/news", "https://example.net/other"]
    assert done["sources"][2]["title"] == "example.net"
    # Found by this message: read_source says so, and the turn keeps the pages.
    assert [source["url"] for source in loop.search_sources] == [
        "https://example.org/report", "https://example.net/other", "https://example.com/news"]
    assert {"https://example.org/report", "https://example.com/news"} <= {s["url"] for s in turn["sources"]}
    # Web content is in view from here on (a settings change needs the user's words).
    assert loop.outside_in_view


def test_each_search_is_charged_with_a_receipt_of_its_own_and_shows_in_the_turns_usage(store, searches):
    plan = Plan([[search_call("a", "b", "c")]], answer=ANSWER)
    loop, events, turn = run(store, plan)
    receipts = [r.to_dict() for r in store.db.collection("users").document(UID).collection("llm_calls").stream()]
    [service] = [r for r in receipts if str(r.get("step")).startswith("service:")]
    assert service["service"] == "exa" and service["operation"] == "search" and service["requests"] == 3
    assert service["status"] == "succeeded" and service["quota_reserved"] == 0
    assert service["usage"]["estimated_cost_nano_usd"] == 3 * searches.cost
    assert service["usage"]["web_search_requests"] == 3
    assert service["quota_charged"] == agent_quota.measured_charge(service["usage"]) > 0
    # The day's allowance took the searches beside the two model steps.
    ledger = agent_quota.quota_ref(store.db, UID, service["quota_day"]).get().to_dict()
    steps = [r for r in receipts if str(r.get("step")).startswith("completion:")]
    assert ledger["used"] == service["quota_charged"] + sum(r["quota_charged"] for r in steps)
    assert ledger["reserved"] == 0 and ledger["agent_usage"]["service_calls"] == 1
    # The turn's usage counts the searches and their price, and stays complete.
    usage = turn["agent_usage"]
    assert usage["web_search_requests"] == 3 and usage["complete"] and usage["measured_calls"] == 2
    assert usage["estimated_cost_nano_usd"] == 3 * searches.cost + sum(
        r["usage"]["estimated_cost_nano_usd"] for r in steps)
    # A reader of the root (the reaper after a hard kill) sees them too.
    root = store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert root_usage(root)["estimated_cost_nano_usd"] == usage["estimated_cost_nano_usd"]
    assert "running" not in root["step_states"].values()


def test_a_booking_is_written_once_and_never_fails_the_search(store, searches, monkeypatch, caplog):
    plan = Plan([[search_call("a")]], answer=ANSWER)
    loop = chat_loop(store, plan)
    usage = service_usage(7_000_000, searches=1)
    list(loop.run())
    args = UID, loop.chat_id, loop.turn_id
    call = "0" * 32
    booked = dict(run_token=loop.run_token, call=call, service="exa", operation="search", usage=usage)
    ledger = agent_quota.quota_ref(store.db, UID, agent_quota.period_key({})).get
    before = ledger().to_dict()["used"]
    assert store.book_service(*args, **booked) is True
    assert store.book_service(*args, **booked) is False
    assert ledger().to_dict()["used"] == before + agent_quota.measured_charge(usage)
    with pytest.raises(ValueError):
        store.book_service(*args, **{**booked, "call": "not-a-call"})
    # The store down: the search's result stands, the loss is logged.
    loop = chat_loop(store, Plan([[search_call("a")]], answer=ANSWER))

    def down(*args, **kwargs):
        raise RuntimeError("store down")
    monkeypatch.setattr(store, "book_service", down)
    list(loop.run())
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["status"] == "completed"
    assert results(loop)[0]["searches"][0]["results"]
    assert "Agent service call not booked operation=search" in caplog.text


def test_a_search_that_fails_is_part_of_the_result_and_the_others_stand(store, searches):
    searches.found = {"down": exa.ExaError("server", "HTTP 503"), "busy": exa.ExaError("busy", "HTTP 429"),
                      "odd": exa.ExaError("rejected", "HTTP 400"), "broken": RuntimeError("bug")}
    plan = Plan([[search_call("fine", "down", "busy", "odd", "broken")]], answer=ANSWER)
    loop, events, turn = run(store, plan)
    [result] = results(loop)
    assert [entry.get("failed") for entry in result["searches"]] == [
        None, agent_web_search.FAILED, agent_web_search.FAILURES["busy"], agent_web_search.FAILURES["rejected"],
        agent_web_search.FAILED]
    assert result["searches"][0]["results"] and "error" not in result
    done = tool_events(events, "web_search")[-1]
    assert done["count"] == 1 and len(done["sources"]) == 1
    # Only the search that ran is charged.
    [service] = [r.to_dict() for r in store.db.collection("users").document(UID).collection("llm_calls").stream()
                 if str(r.to_dict().get("step")).startswith("service:")]
    assert service["requests"] == 1 and service["usage"]["estimated_cost_nano_usd"] == searches.cost


def test_a_service_that_is_down_costs_nothing_and_never_ends_the_turn(store, searches):
    searches.found = {query: exa.ExaError("unreachable", "ConnectTimeout") for query in "abc"}
    plan = Plan([[search_call("a")], [search_call("b")], [search_call("c")]], answer=ANSWER)
    loop, events, turn = run(store, plan)
    # Three failed searches in a row are no three invalid tool rounds.
    assert turn["status"] == "completed" and turn["assistant_response"] == ANSWER and turn.get("agent_wrap_up") is None
    assert all(result == {"searches": [{"query": query, "failed": agent_web_search.FAILED}]}
               for result, query in zip(results(loop), "abc"))
    assert [event["outcome"] for event in tool_events(events, "web_search") if event["status"] == "succeeded"] == ["failed"] * 3
    assert not [r for r in store.db.collection("users").document(UID).collection("llm_calls").stream()
                if str(r.to_dict().get("step")).startswith("service:")]
    assert turn["agent_usage"]["web_search_requests"] in (0, None)


def test_the_searches_of_a_call_run_side_by_side_and_a_stop_does_not_wait_for_them(store, searches, monkeypatch):
    barrier = threading.Barrier(3, timeout=5)

    def together(query, **options):
        barrier.wait()
        return {"hits": [hit(f"https://example.org/{query}")], "cost_nanos": 1, "notes": []}
    monkeypatch.setattr(exa, "search", together)
    loop, events, turn = run(store, Plan([[search_call("a", "b", "c")]], answer=ANSWER))
    assert [entry["results"][0]["url"][-1] for entry in results(loop)[0]["searches"]] == ["a", "b", "c"]
    # A search under way when the user stops: the call ends at once.
    release = threading.Event()

    def hanging(query, **options):
        release.wait(5)
        return {"hits": [], "cost_nanos": 1, "notes": []}
    monkeypatch.setattr(exa, "search", hanging)
    loop = chat_loop(store, Plan([[search_call("a")]], answer=ANSWER))
    tool = loop.registry.tools["web_search"]
    cancellation = ProviderCancellation()
    threading.Timer(.2, cancellation.cancel).start()
    started = time.monotonic()
    with pytest.raises(ProviderCancelled):
        tool.execute(WebSearchArgs(queries=["a"]), cancellation=cancellation)
    assert time.monotonic() - started < 2
    release.set()


def test_a_search_runs_beside_the_steps_other_reads_and_its_result_is_outside_content():
    assert "web_search" in CONCURRENT_TOOLS
    # Its result is web content: outside content for the app, data for the reviewers.
    assert "web_search" not in OWN_CONTENT_TOOLS and TOOL_DATA["web_search"] in UNTRUSTED_DATA


# --- The tool ----------------------------------------------------------------

def tool_of(store, **kwargs):
    loop = chat_loop(store, Plan([], answer=ANSWER), **kwargs)
    return loop, loop.registry.tools.get("web_search")


def test_the_tool_says_what_it_does_and_takes_few_fields(store, searches):
    loop, tool = tool_of(store)
    schema = tool.schema()["function"]
    assert f"up to {QUERIES_PER_CALL} searches per call" in schema["description"]
    assert "read_source reads a page in full" in schema["description"]
    assert list(schema["parameters"]["properties"]) == ["queries", "domains", "since"]
    assert schema["parameters"]["required"] == ["queries"]
    registry = ToolRegistry([tool])

    def refused(arguments):
        with pytest.raises(ValueError) as refusal:
            registry.validate({"function": {"name": "web_search", "arguments": json.dumps(arguments)}})
        return str(refusal.value)
    assert "queries" in refused({"query": "one string"})
    assert "queries" in refused({"queries": []})
    assert "queries" in refused({"queries": ["q"] * (QUERIES_PER_CALL + 1)})
    assert "since" in refused({"queries": ["q"], "since": "last week"})
    # The search words and the site as a model writes them.
    result = tool.execute(WebSearchArgs(queries=[" q ", "q"], domains=["https://www.Europa.eu/", "europa.eu"],
                                        since="2026-01-01"), cancellation=ProviderCancellation())
    assert searches.calls == [("q", {"results": SEARCH_RESULTS, "characters": SEARCH_RESULT_CHARACTERS,
                                     "domains": ("europa.eu",), "since": "2026-01-01"})]
    assert [entry["query"] for entry in result["searches"]] == ["q"]
    with pytest.raises(ValueError, match="is no site"):
        tool.execute(WebSearchArgs(queries=["q"], domains=["not a site"]), cancellation=ProviderCancellation())


@pytest.mark.parametrize("value, expected", [("europa.eu", "europa.eu"), ("HTTP://WWW.Example.org/docs/", "example.org/docs"),
                                             ("*.gov.uk", "*.gov.uk"), ("sub.example.co.uk", "sub.example.co.uk")])
def test_a_site_is_a_host_with_or_without_its_address_around_it(value, expected):
    assert site(value) == expected


@pytest.mark.parametrize("value", ["", "localhost", "two words.com", "europa", "site:europa.eu"])
def test_what_is_no_site_is_refused(value):
    with pytest.raises(ValueError):
        site(value)


def test_no_search_close_to_the_answers_deadline_or_with_google_data(store, searches, monkeypatch):
    loop, tool = tool_of(store)
    monkeypatch.setattr(loop, "answer_time_left", lambda: agent_web_search.SEARCH_MIN_SECONDS - 1)
    result = tool.execute(WebSearchArgs(queries=["q"]), cancellation=ProviderCancellation())
    assert result["status"] == "refused" and "no time left" in result["reason"]
    assert tool.activity(WebSearchArgs(queries=["q"]), result) == {"queries": ["q"], "outcome": "failed"}
    monkeypatch.setattr(loop, "answer_time_left", lambda: None)
    monkeypatch.setattr(loop, "_chat_google_data", lambda: True)
    result = tool.execute(WebSearchArgs(queries=["q"]), cancellation=ProviderCancellation())
    assert result["status"] == "refused" and "Google data" in result["reason"]
    assert not searches.calls


# --- When the agent has it ------------------------------------------------------

class Selection:
    calendar, gmail = True, False

    def model_dump(self):
        return {"calendar": True, "gmail": False}


def test_without_exa_the_agents_steps_search_inside_the_request_as_before(store, monkeypatch):
    from app.services.agent_audit import AGENT_SEARCH_ROUNDS
    exa.reset()
    monkeypatch.delenv(exa.KEY_ENV, raising=False)
    sent = []
    plan = Plan([], answer=ANSWER)
    loop = chat_loop(store, plan)
    assert loop.web_search is None and "web_search" not in loop.registry.tools
    real = loop.factory

    def factory():
        completion = real()
        stream = completion.stream

        def recording(**kwargs):
            sent.append(kwargs["native_searches"])
            return stream(**kwargs)
        completion.stream = recording
        return completion
    loop.factory = factory
    list(loop.run())
    assert sent == [AGENT_SEARCH_ROUNDS] and "openrouter:web_search" in plan.steps[0][1]
    # What the app then has of a search is only what the provider reports.
    assert AGENT_PROVIDER_SEARCH_FACT in loop.messages[0]["content"]


def test_with_exa_the_agent_is_not_told_of_hits_that_never_reach_the_app(store, searches):
    loop, tool = tool_of(store)
    assert tool is not None and AGENT_PROVIDER_SEARCH_FACT not in loop.messages[0]["content"]
    # Before read_source, which its description names.
    names = list(loop.registry.tools)
    assert names.index("web_search") < names.index("read_source")


@pytest.mark.parametrize("case", ["google_selection", "google_data", "set_aside", "switched_off"])
def test_absent_in_google_chats_and_while_exa_is_set_aside(store, searches, monkeypatch, case):
    kwargs = {}
    if case == "google_selection":
        from app.services import google_connections
        monkeypatch.setattr(google_connections, "GoogleConnections", lambda db: None)
        kwargs = {"google_selection": Selection()}
    elif case == "google_data":
        kwargs = {"google_data": True}
    elif case == "set_aside":
        monkeypatch.setattr(exa, "available", lambda: False)
    else:
        monkeypatch.setenv(exa.ENABLED_ENV, "0")
    loop, tool = tool_of(store, **kwargs)
    assert tool is None and loop.web_search is None


# --- The reviewers ---------------------------------------------------------------

def test_the_reviewers_read_every_page_of_a_search_and_know_how_the_agent_searches():
    many = {"note": UNTRUSTED_NOTE, "searches": [
        {"query": f"search {number}", "results": [hit(f"https://example.org/{number}/{rank}", text="x" * 2000)
                                                  for rank in range(5)]} for number in range(5)]}
    entry = {"seq": 7, "actor": "agent", "kind": "tool", "name": "web_search", "data": "web", "format": "text"}
    read = review_entry(entry, json.dumps(many))
    # As its structure, every excerpt shortened alike: no search hides the others.
    assert read["data"] == "web" and isinstance(read["content"], dict)
    assert [search["query"] for search in read["content"]["searches"]] == [f"search {n}" for n in range(5)]
    assert all(len(search["results"]) == 5 for search in read["content"]["searches"])
    assert ENTRY_CHARS < len(json.dumps(read["content"])) <= SEARCH_ENTRY_CHARS
    # In a tight round it gives way like every entry.
    assert len(json.dumps(review_entry(entry, json.dumps(many), limit=1500)["content"])) <= 1500 + 200
    assert REVIEW_SEARCH_TOOL in review_system_prompt("UTC", own_search=True)
    assert REVIEW_SEARCH_INSIDE not in review_system_prompt("UTC", own_search=True)
    assert REVIEW_SEARCH_INSIDE in review_system_prompt("UTC") and REVIEW_SEARCH_TOOL not in review_system_prompt("UTC")
    assert any("web_search" in line for line in tool_brief(["web_search"]))


def test_a_service_call_adds_its_price_to_a_sum_without_counting_as_a_model_call():
    step = {"input_tokens": 100, "output_tokens": 20, "cached_input_tokens": 0, "cache_write_tokens": 0,
            "reasoning_tokens": 0, "estimated_cost_nano_usd": 500, "web_search_requests": 0, "complete": True,
            "cost_complete": True, "cost_source": "provider"}
    total = aggregate_usage([step, service_usage(7_000_000, searches=2), service_usage(1_000_000)])
    assert total["estimated_cost_nano_usd"] == 8_000_500 and total["web_search_requests"] == 2
    assert total["input_tokens"] == 100 and total["complete"] and total["cost_complete"]
    assert (total["measured_calls"], total["unmetered_calls"]) == (1, 0) and total["cost_source"] == "provider"
    ledger = agent_quota.book_service({"used": 10, "agent_usage": {"calls": 3}}, service_usage(7_000_000, searches=2))
    assert ledger["used"] == 10 + agent_quota.measured_charge(service_usage(7_000_000)) and ledger["revision"] == 1
    assert ledger["agent_usage"] == {"calls": 3, "service_calls": 1, "estimated_cost_nano_usd": 7_000_000,
                                     "provider_cost_nano_usd": 7_000_000}
