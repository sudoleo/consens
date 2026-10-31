"""read_source: the agent reads a page through OpenRouter's web_fetch.

Only for the agent: a source a comparison answer cited, a result of its own
search, a source of an earlier message, a link the user wrote, or, while
reviewers follow the work, any public page (test_agent_gate.py). Bounded,
metered, given to the agent only as the read_source tool result (it writes
the answer itself, agent_answer_mode), kept with the review, and never for
comparison models, reviewers or Google-data chats. On unless
AGENT_READ_SOURCES=0. The loops here have no reviewers that start
(agent_reviewers.py): a page nothing in the chat names stays unread.
"""
import json

import pytest

from app.services import agent_read_source
from app.services.agent_comparison import comparison_selection
from app.services.agent_costs import FETCH_COST_NANOS, RunCosts, fetch_bounds
from app.services.agent_delegation import DelegationLoop
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.agent_read_source import (READ_CONTENT_TOKENS, READS_PER_MESSAGE, READS_PER_STEP, UNTRUSTED_NOTE,
                                            AuditReadSourceArgs, PageFetch, resolve_redirect, url_key, user_urls)
from app.services.llm.agent_client import AgentCompletion, measured_usage, resolve_agent_model
from app.services.llm.engines import web_fetch_tool
from app.services.llm.provider_runtime import ProviderCancellation
from app.services.prompt_defaults import AGENT_AUDIT_ANSWER_SECTION, AGENT_AUDIT_SYSTEM_PROMPT
from agent_reviewers import without_reviewers
from test_agent_runs import UID, pending, store  # noqa: F401  (fixture)

CITED = "https://example.org/report"
# The refusal of a page nothing in the chat names (SourceReader.read).
UNCITED = "only a public http(s) address"
PAGE = "Annual report 2026. The first option costs 100 euros per month, VAT included."
ANSWER = "The first option costs 100 euros per month."


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("AGENT_READ_SOURCES", "1")


@pytest.fixture(autouse=True)
def offline_source_pages(monkeypatch):
    """A comparison result fetches cited pages for its excerpts
    (agent_source_evidence): never over the network here, and never with the
    page text, which must reach the agent only through read_source."""
    from app.services import agent_source_evidence

    def fetch(url, limits):
        raise ValueError("offline")
    monkeypatch.setattr(agent_source_evidence, "fetch_document", fetch)


def compare():
    return "compare_models", {"question": "What does option one cost?", "context": ""}


def read_call(url=CITED):
    return "read_source", {"url": url}


class Plan:
    """Scripted agent steps (lists of tool calls); the step after them writes
    the answer as plain text (the agent writes it itself, agent_answer_mode).
    ``texts``: text a step writes alongside its tool calls; ``searches``:
    sources of a step's own web search. Every other call is a comparison
    answer citing ``cited``. Records every step."""

    def __init__(self, steps=None, cited=(CITED, "https://example.net/other"), *, answer=ANSWER, texts=None,
                 searches=None):
        self.script = steps if steps is not None else [[compare()], [read_call()]]
        self.cited, self.answer = cited, answer
        self.texts, self.searches = texts or {}, searches or {}
        self.steps = []
        self.answer_messages = None

    def factory(self):
        plan = self

        class Completion(AgentCompletion):
            def stream(self, *, model, messages, **kwargs):
                tools = kwargs.get("tools") or []
                names = [t.get("function", {}).get("name") or t.get("type") for t in tools]
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                if self.step_id.startswith("completion:"):
                    index = int(self.step_id.split(":")[-1])
                    if index in plan.searches:
                        self.sources = plan.searches[index]
                    if index < len(plan.script) and kwargs.get("allow_tool_calls") is not False:
                        plan.steps.append(("routing", names))
                        if index in plan.texts:
                            self.text = plan.texts[index]
                            yield {"type": "delta", "text": self.text}
                        self.tool_calls = [{"id": f"call_{index}_{n}", "type": "function",
                                            "function": {"name": name, "arguments": json.dumps(args)}}
                                           for n, (name, args) in enumerate(plan.script[index])]
                        self.finish_reason = "tool_calls"
                        return
                    # The answer: the agent's plain text without tool calls.
                    plan.steps.append(("answer", names))
                    plan.answer_messages = list(messages)
                    self.text = plan.answer
                else:
                    plan.steps.append(("comparison", names))
                    self.text = "The first option costs 100 euros per month."
                    self.sources = [{"url": url, "title": "Report"} for url in plan.cited]
                self.finish_reason = "stop"
                yield {"type": "delta", "text": self.text}
        return Completion()


def fake_fetch(monkeypatch, *, page=PAGE, status="completed", error="", fail_models=()):
    calls = []

    class Fetch(PageFetch):
        def stream(self, *, model, messages, tools=None, **kwargs):
            calls.append({"model": model.model, "messages": messages, "tools": tools,
                          "reasoning": (model.request_config or {}).get("reasoning")})
            if model.model.split("/")[0] in fail_models:
                raise RuntimeError("provider down")
            self.usage = measured_usage({"input_tokens": 1200, "output_tokens": 4, "cost": .0002}, model)
            yield self.event("usage", "usage", usage=self.usage)
            url = messages[0]["content"].rsplit("URL: ", 1)[-1]
            self._take({"type": "openrouter:web_fetch", "status": status, "url": url, "title": "Report",
                        "content": page if status == "completed" else "", "httpStatus": None if error else 200,
                        "error": error})
            self.text, self.finish_reason = "OK", "stop"
    monkeypatch.setattr(agent_read_source, "PageFetch", Fetch)
    return calls


def chat_loop(store, plan, *, google_selection=None, google_data=False, policy=None, conversation=None,
              chat_sources=None):
    """A chat turn of the agent whose reviewers never start (agent_reviewers.py)."""
    chat, turn = pending(store)
    config = {**defaults(), "enabled": False}
    return without_reviewers(DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"),
        messages=[{"role": "system", "content": AGENT_AUDIT_SYSTEM_PROMPT},
                  *(conversation or [{"role": "user", "content": "Price?"}])],
        api_key="test", cancellation=ProviderCancellation(), policy=policy or AgentPolicy.for_chat(config),
        delegation_config=config, completion_factory=plan.factory,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}),
        google_selection=google_selection, google_data=google_data, chat_sources=chat_sources))


def run(store, plan, **kwargs):
    loop = chat_loop(store, plan, **kwargs)
    events = list(loop.run())
    return loop, events, store.get_turn(UID, loop.chat_id, loop.turn_id)


def tool_events(events, name="read_source"):
    return [e for e in events if e.get("kind") == "tool" and e.get("name") == name]


def results(loop):
    """read_source results the orchestrator received, in order."""
    ids = {call["id"] for m in loop.messages if m.get("role") == "assistant"
           for call in m.get("tool_calls") or [] if call["function"]["name"] == "read_source"}
    return [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool" and m["tool_call_id"] in ids]


def test_reads_a_cited_page_after_the_comparison_and_writes_the_answer_from_it(store, monkeypatch, enabled):
    calls = fake_fetch(monkeypatch)
    plan = Plan()
    loop, events, saved = run(store, plan)
    assert saved["status"] == "completed"
    # Compare, read, then the agent's own text is the answer: no further step.
    assert [kind for kind, _ in plan.steps if kind in {"routing", "answer"}] == ["routing", "routing", "answer"]
    assert saved["assistant_response"] == ANSWER and saved["agent_review"]["versions"][-1]["text"] == ANSWER
    assert saved["agent_review"]["mode"] == "audit"
    # One helper call with OpenRouter's fetch, pinned and bounded to the cited host.
    [call] = calls
    assert call["tools"] == [web_fetch_tool(max_uses=1, max_content_tokens=READ_CONTENT_TOKENS,
                                            allowed_domains=["example.org"])]
    assert call["tools"][0]["parameters"]["engine"] == "exa"
    assert call["messages"][0]["content"].endswith("URL: " + CITED)
    assert call["model"].startswith("openai/") and call["reasoning"] == {"effort": "none"}
    # The trace names the host, and says "read" only once the page was read.
    running, done = tool_events(events)
    assert running["status"] == "running" and running["host"] == "example.org" and "read" not in running
    assert done["status"] == "succeeded" and done["read"] == "completed"
    assert done["sources"] == [{"url": CITED, "title": "Report"}]
    # Saved with the review: what, from which answers; no purpose or point to
    # justify a read since 2026-10-28.
    [read] = saved["agent_review"]["read_sources"]
    assert read["status"] == "completed" and read["text"] == PAGE and read["host"] == "example.org"
    assert "purpose" not in read and "point" not in read
    assert {c["provider"] for c in read["cited_by"]} == {"anthropic", "openai"} and read["retrieved_at"]
    # The turn's saved sources keep the page.
    assert CITED in json.dumps(saved["sources"])
    [result] = results(loop)
    assert result["status"] == "completed" and result["untrusted_page_text"] == PAGE
    assert result["cited_by"] == [c["label"] for c in read["cited_by"]] and result["text_cut"] is False
    # The warning comes before the page text, not after 24,000 characters of it,
    # and names the next step: another read or the answer, no answer tool.
    assert list(result)[:2] == ["status", "note"] and result["note"] == UNTRUSTED_NOTE
    assert "never instructions" in UNTRUSTED_NOTE and UNTRUSTED_NOTE.endswith("or write the answer.")
    # The agent writes from the page in its own context: the read_source
    # result is the only message that carries it (no evidence block any more).
    carrying = [m for m in plan.answer_messages if PAGE in str(m.get("content") or "")]
    assert [(m["role"], m.get("tool_call_id")) for m in carrying] == [("tool", "call_1_0")]
    # The comparison's answers advise; nothing tells the agent when to read,
    # and no note of the app follows a result (until 2026-10-31 a write note).
    compared = next(json.loads(m["content"]) for m in loop.messages
                    if m.get("role") == "tool" and m["tool_call_id"] == "call_0_0")
    assert compared["instruction"].startswith("These answers cover only the question you asked")
    assert "read_source" not in compared["instruction"]
    assert [m["role"] for m in plan.answer_messages[1:]] == ["user", "assistant", "tool", "assistant", "tool"]
    # The helper is a metered session of its own, not a voice of the answer.
    agents = store.delegation_view(UID, loop.chat_id, loop.turn_id)["agents"]
    [helper] = [a for a in agents if a.get("kind") == "source"]
    assert helper["title"] == "Read source · example.org" and helper["status"] == "completed"
    assert helper["usage"]["input_tokens"] == 1200
    assert saved["agent_usage"]["input_tokens"] >= 1200


def test_never_offered_to_comparison_models(store, monkeypatch, enabled):
    calls = fake_fetch(monkeypatch)
    plan = Plan()
    run(store, plan)
    # Every step of the agent, the one that writes the answer included, lists
    # the same tools (prompt cache), read_source among them.
    own = [names for kind, names in plan.steps if kind in {"routing", "answer"}]
    assert len(own) == 3 and all("read_source" in names and names == own[0] for names in own)
    others = [names for kind, names in plan.steps if kind not in {"routing", "answer"}]
    assert {kind for kind, _ in plan.steps} == {"routing", "answer", "comparison"}
    assert not any("read_source" in names or "openrouter:web_fetch" in names for names in others)
    # The fetch tool exists only in the helper call.
    assert [t["type"] for c in calls for t in c["tools"]] == ["openrouter:web_fetch"]


class Selection:
    """Google access enabled for this message, without calendar or Gmail tools."""
    calendar = gmail = False

    def model_dump(self):
        return {"calendar": False, "gmail": False}


def test_on_unless_switched_off(monkeypatch):
    """Off by default until 2026-10-11, when the Agent told users it could not
    read any source."""
    monkeypatch.delenv("AGENT_READ_SOURCES", raising=False)
    assert agent_read_source.enabled()
    for value, on in (("0", False), (" 0 ", False), ("1", True), ("", True)):
        monkeypatch.setenv("AGENT_READ_SOURCES", value)
        assert agent_read_source.enabled() is on, value


@pytest.mark.parametrize("case", ["off", "google_selection", "google_data", "bounded"])
def test_absent_when_switched_off_in_google_chats_and_bounded_runs(store, monkeypatch, case):
    monkeypatch.setenv("AGENT_READ_SOURCES", "0" if case == "off" else "1")
    kwargs = ({"google_selection": Selection()} if case == "google_selection"
              else {"google_data": True} if case == "google_data" else {})
    if case == "bounded":
        kwargs["policy"] = AgentPolicy.from_config({**defaults(), "enabled": True})
    loop = chat_loop(store, Plan(), **kwargs)
    assert "read_source" not in loop.registry.tools and loop.comparison.reader is None
    # The pictures of the web come with reading (the server fetches them alike).
    assert not {"find_pictures", "show_image"} & set(loop.registry.tools)


def test_the_tool_says_what_it_reads_and_the_prompt_adds_no_rules(store, enabled):
    """Since 2026-10-28 the tool's description says what it opens, not when
    to read; the prompt holds no block about reading (until 2026-10-31
    comparison mode had one)."""
    loop = chat_loop(store, Plan())
    content = loop.messages[0]["content"]
    tool = loop.registry.tools["read_source"]
    assert "public web page" in tool.description and f"At most {READS_PER_MESSAGE} per message" in tool.description
    assert set(tool.schema()["function"]["parameters"]["properties"]) == {"url"}
    assert "READING SOURCES" not in content and content.count(AGENT_AUDIT_ANSWER_SECTION) == 1
    # No answer tool and no answer step any more.
    assert "call answer" not in content and "answer step" not in content
    assert "answer" not in loop.registry.tools


def test_the_tool_list_is_the_same_with_and_without_reading_except_read_source(store, monkeypatch):
    """No planning field any more (next_step): the agent decides on a read
    itself. The pictures of the web come with reading."""
    monkeypatch.setenv("AGENT_READ_SOURCES", "0")
    off = chat_loop(store, Plan())
    monkeypatch.setenv("AGENT_READ_SOURCES", "1")
    on = chat_loop(store, Plan())
    assert set(on.registry.tools) - set(off.registry.tools) == {"read_source", "find_pictures", "show_image"}
    assert on.registry.tools["compare_models"].schema() == off.registry.tools["compare_models"].schema()
    assert "next_step" not in on.registry.tools["compare_models"].schema()["function"]["parameters"]["properties"]


def comparison_ready(store, *, urls=(CITED,)):
    """A loop whose comparison has answers citing `urls`, without running it."""
    loop = chat_loop(store, Plan())
    sources = [{"url": url, "title": url} for url in urls]
    loop.comparison.comparisons.append({"id": "c1", "question": "Price?", "context": "", "answers": [
        {"provider": "openai", "provider_label": "OpenAI", "text": "100", "sources": sources},
        {"provider": "anthropic", "provider_label": "Claude", "text": "120", "sources": sources[:1]}],
        "failed_models": []})
    return loop


def read(loop, url=CITED):
    args = AuditReadSourceArgs.model_validate({"url": url})
    return loop.comparison.reader.read(args, cancellation=loop.cancellation)


def refused(result, match):
    assert result["status"] == "refused" and match in result["reason"] and "error" not in result, result


def test_refused_for_uncited_urls_and_after_the_answer(store, monkeypatch, enabled):
    calls = fake_fetch(monkeypatch)
    # Before any comparison nothing is cited yet: only chat sources and user links.
    refused(read(chat_loop(store, Plan())), UNCITED)
    loop = comparison_ready(store)
    for url in ("https://evil.example/steal?data=1", "ftp://example.org/report", "javascript:alert(1)",
                "https://example.org/report/deeper", "https://user@example.org/report"):
        refused(read(loop, url), UNCITED)
    loop.comparison.text = "The fixed answer."
    refused(read(loop), "already written")
    assert calls == [] and loop.comparison.reader.reads == []


def test_user_urls_are_the_links_the_user_wrote():
    conversation = [
        {"role": "user", "content": "Check https://example.org/a. And (https://example.org/b), ok?"},
        {"role": "assistant", "content": "see **https://example.org/c**; also javascript:alert(1)"},
        {"role": "system", "content": "https://example.org/never"},
        {"role": "user", "content": "kannst du das nachlesen? https://www.tri247.com/live-kona?x=1. Und https://example.org/a"},
    ]
    # Latest message first, each page once, punctuation and the link's ")" cut;
    # answer text and system messages never count.
    assert user_urls(conversation) == ["https://www.tri247.com/live-kona?x=1", "https://example.org/a",
                                       "https://example.org/b"]
    assert user_urls([{"role": "user", "content": "https://en.wikipedia.org/wiki/Kona_(Hawaii)."}]) == [
        "https://en.wikipedia.org/wiki/Kona_(Hawaii)"]
    assert user_urls([{"role": "user", "content": "[x](https://example.org/a_b_)"}]) == ["https://example.org/a_b_"]
    assert user_urls(None) == [] and user_urls([{"role": "user", "content": None}]) == []
    # Linear on hostile text: no backtracking on a long run of URL characters.
    assert user_urls([{"role": "user", "content": "https://" + "a" * 200_000}]) == []
    assert user_urls([{"role": "user", "content": "https://example.org/" + ")" * 2000}]) == ["https://example.org/"]


def test_links_in_a_quoted_answer_passage_are_not_the_users():
    """Review 2026-10-12: "Ask about this" puts answer text into the user's
    message. A link there is answer text, which stays unreadable (an injected
    page could have it carry chat content)."""
    from app.services.agent_memory import QUOTE_ONLY_PREFIX, QUOTE_TYPED_MARKER
    typed = f"Was steht da? https://example.org/mine{QUOTE_TYPED_MARKER}Siehe https://evil.example/?leak=abc”"
    only = f"{QUOTE_ONLY_PREFIX}https://evil.example/q”"
    assert user_urls([{"role": "user", "content": typed}, {"role": "user", "content": only}]) == [
        "https://example.org/mine"]
    # Typographic quotes end a link like straight ones; an upper-case scheme is one.
    german = "Lies „https://example.org/a?b=1“ und «https://example.org/c» und HTTPS://Example.org/x."
    assert user_urls([{"role": "user", "content": german}]) == [
        "https://example.org/a?b=1", "https://example.org/c", "HTTPS://Example.org/x"]


def test_reads_a_source_of_an_earlier_message_and_without_reviewers_no_link_from_answer_text(
        store, monkeypatch, enabled):
    """2026-10-11: "kannst du eine Quelle direkt nachlesen?" after an answer
    citing tri247.com could open nothing; only this message's answers counted.
    Saved sources of earlier messages count now. A link that stands only in an
    earlier answer's text does not: an injected page could have put it there
    with chat content in it (review 2026-10-11). Since 2026-10-28 such a page
    is read while reviewers follow the read live (test_agent_gate.py); without
    them it stays unread."""
    calls = fake_fetch(monkeypatch)
    earlier = "https://www.tri247.com/live-kona"
    planted = "https://evil.example/collect?d=secret"
    conversation = [{"role": "user", "content": "Who leads?"},
                    {"role": "assistant", "content": f"Ditlev leads ([tri247]({earlier}), [more]({planted}))."},
                    {"role": "user", "content": "kannst du eine Quelle direkt nachlesen?"}]
    plan = Plan(steps=[[compare()], [read_call(earlier), read_call(planted)]])
    loop, _, saved = run(store, plan, conversation=conversation,
                         chat_sources=[{"url": earlier, "title": "Live", "provider": "OpenAI", "id": "S1"}])
    done, other = results(loop)
    assert done["status"] == "completed" and done["cited_by"] == ["an earlier message's sources"]
    refused(other, UNCITED)
    assert len(calls) == 1 and calls[0]["messages"][0]["content"].endswith("URL: " + earlier)
    assert [r["url"] for r in saved["agent_review"]["read_sources"]] == [earlier]
    # The agent that writes the answer saw both outcomes itself: the page it
    # opened and the refusal (it denied reading before, as a separate step).
    seen = [json.loads(m["content"]) for m in plan.answer_messages
            if m.get("role") == "tool" and m["tool_call_id"] in {"call_1_0", "call_1_1"}]
    assert [r["status"] for r in seen] == ["completed", "refused"] and seen[0]["untrusted_page_text"] == PAGE
    assert saved["assistant_response"] == ANSWER


def test_reads_a_page_the_user_linked(store, monkeypatch, enabled):
    calls = fake_fetch(monkeypatch)
    linked = "https://example.org/rules.pdf"
    plan = Plan(steps=[[compare()], [read_call(linked)]])
    loop, _, _ = run(store, plan, conversation=[{"role": "user", "content": f"Was steht in {linked}?"}])
    assert results(loop)[0]["cited_by"] == ["your message"] and len(calls) == 1


def test_text_sent_with_a_read_is_no_answer_the_read_runs_first(store, monkeypatch, enabled):
    """Review 2026-10-12: [answer, read_source] in one step decided the answer
    before the read and still paid for it. The agent's text next to a
    read_source call is a preamble: the read runs, and its next message,
    written with the page in view, is the answer."""
    calls = fake_fetch(monkeypatch)
    linked = "https://example.org/linked"
    plan = Plan(steps=[[read_call(linked)]], texts={0: "It costs 90 euros."})
    loop, events, saved = run(store, plan, conversation=[{"role": "user", "content": f"Was steht auf {linked}?"}])
    assert len(calls) == 1 and [r["status"] for r in results(loop)] == ["completed"]
    assert [kind for kind, _ in plan.steps] == ["routing", "answer"]
    assert saved["assistant_response"] == ANSWER and "90 euros" not in json.dumps(saved["agent_review"])
    assert not any(e.get("type") == "delta" and "90 euros" in e.get("text", "") for e in events)
    assert any(m.get("role") == "tool" and PAGE in m["content"] for m in plan.answer_messages)


def test_the_store_hands_earlier_sources_to_the_loop(store):
    from test_agent_runs import AgentModel, receipt
    chat, first = pending(store, question="Who leads?")
    assert store.claim(UID, chat, first["id"], AgentModel())
    store.settle(UID, chat, first["id"], completion=receipt(), status="succeeded")
    store._turn_ref(UID, chat, first["id"]).update({
        "sources": [{"url": "https://www.tri247.com/live-kona", "title": "Live", "id": "S1"}, "junk"]})
    _, second = pending(store, chat_id=chat, request_id="two", question="Lies nach")
    collected = []
    messages = store.messages(UID, chat, second, sources=collected)
    assert collected == [{"url": "https://www.tri247.com/live-kona", "title": "Live", "id": "S1"}]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]


def test_refused_in_a_chat_that_holds_google_data(store, monkeypatch, enabled):
    calls = fake_fetch(monkeypatch)
    loop = comparison_ready(store)
    store._chat_ref(UID, loop.chat_id).update({"google_data": True})
    refused(read(loop), "Google data")
    assert calls == []


def test_a_refused_call_before_the_comparison_costs_nothing_and_the_run_goes_on(store, monkeypatch, enabled):
    calls = fake_fetch(monkeypatch)
    loop, events, saved = run(store, Plan(steps=[[read_call()], [compare()]]))
    refused(results(loop)[0], UNCITED)
    assert calls == [] and saved["status"] == "completed"
    running, done = tool_events(events)
    # No host for a URL nobody cited, and a refusal is no tool error.
    assert "host" not in running and done["status"] == "succeeded" and done["read"] == "refused"


def test_refusals_never_end_the_turn_as_invalid_tool_rounds(store, monkeypatch, enabled):
    """Three tool errors in a row end a turn; refused or failed reads must not."""
    calls = fake_fetch(monkeypatch, status="incomplete", error="HTTP 403: Forbidden")
    steps = [[compare()], [read_call("https://example.org/guess-1")], [read_call("https://example.org/guess-2")],
             [read_call()], [read_call()]]
    loop, _, saved = run(store, Plan(steps=steps))
    outcome = [r["status"] for r in results(loop)]
    assert outcome == ["refused", "refused", "failed", "refused"]
    assert saved["status"] == "completed" and saved["assistant_response"] == ANSWER
    # The failed page is not fetched a second time.
    assert len(calls) == 1


def test_a_comparison_may_follow_a_read(store, monkeypatch, enabled):
    """Until 2026-10-31 no comparison was possible after a read (the models
    had to answer independently of what the agent wrote into the task). The
    models see only the agent's question, and the reviewers read both."""
    fake_fetch(monkeypatch)
    loop, _, saved = run(store, Plan(steps=[[compare()], [read_call()], [compare()]]))
    again = next(json.loads(m["content"]) for m in loop.messages
                 if m.get("role") == "tool" and m["tool_call_id"] == "call_2_0")
    assert again["answers"] and "error" not in again
    assert len(saved["agent_review"]["comparisons"]) == 2 and saved["status"] == "completed"
    assert saved["assistant_response"] == ANSWER


def test_after_its_own_search_and_a_read_a_long_answer_stands_at_once(store, monkeypatch, enabled):
    """Review 2026-10-11: search, then read, then answer looped between two
    refusals of comparison mode. The agent's own research carries the answer:
    a long answer after it stands, with no app rule pushing a comparison."""
    calls = fake_fetch(monkeypatch)
    linked = "https://example.org/linked"
    long_answer = " ".join([ANSWER] * 30)
    plan = Plan(steps=[[read_call(linked)]], answer=long_answer,
                searches={0: [{"url": "https://example.org/found", "title": "Found"}]})
    loop, events, saved = run(store, plan, conversation=[{"role": "user", "content": f"Was steht auf {linked}?"}])
    assert any(e.get("kind") == "tool" and e.get("name") == "web_search" for e in events)
    assert len(calls) == 1 and [r["status"] for r in results(loop)] == ["completed"]
    assert [kind for kind, _ in plan.steps] == ["routing", "answer"]
    assert not any(m.get("role") == "user" and "App rule" in str(m.get("content")) for m in loop.messages)
    assert saved["status"] == "completed" and saved["assistant_response"] == long_answer
    assert not loop.comparison.comparisons and saved["agent_review"]["versions"][-1]["text"] == long_answer


def test_reads_a_page_the_user_points_to_and_answers_without_a_comparison(store, monkeypatch, enabled):
    """2026-10-11: "Lies die erste Quelle nach und sag mir die Siegerzeit" ran
    six models on a page they could not see. Now: read, then answer."""
    calls = fake_fetch(monkeypatch)
    earlier = "https://www.tri247.com/live-kona"
    conversation = [{"role": "user", "content": "Who won?"},
                    {"role": "assistant", "content": f"Vincent Luis ([tri247]({earlier}))."},
                    {"role": "user", "content": "Lies die Quelle nach und sag mir die Siegerzeit."}]
    plan = Plan(steps=[[read_call(earlier)]])
    loop, events, saved = run(store, plan, conversation=conversation,
                              chat_sources=[{"url": earlier, "title": "Live"}])
    assert len(calls) == 1 and not loop.comparison.comparisons
    assert saved["status"] == "completed" and saved["assistant_response"] == ANSWER
    # Saved with the read page and reviewed like any answer, without checks.
    review = saved["agent_review"]
    assert review["mode"] == "audit" and not review["comparisons"] and review["read_sources"][0]["url"] == earlier
    assert review["answer_hash"] and not review.get("checks")
    assert not any(step[0] == "comparison" for step in plan.steps)
    # One read, then the agent's own text: two calls of the agent, the page as
    # the last tool result.
    assert [kind for kind, _ in plan.steps] == ["routing", "answer"]
    last = plan.answer_messages[-1]
    assert last["role"] == "tool" and json.loads(last["content"])["untrusted_page_text"] == PAGE


@pytest.mark.parametrize("cited", [(), (CITED,)])
def test_a_comparison_result_never_tells_the_agent_when_to_read(store, monkeypatch, enabled, cited):
    fake_fetch(monkeypatch)
    loop, _, _ = run(store, Plan(steps=[[compare()]], cited=cited))
    compared = next(json.loads(m["content"]) for m in loop.messages
                    if m.get("role") == "tool" and m["tool_call_id"] == "call_0_0")
    assert "read_source" not in compared["instruction"]


def test_a_different_page_than_the_cited_one_is_not_accepted(store, monkeypatch, enabled):
    class Fetch(PageFetch):
        def stream(self, *, model, messages, tools=None, **kwargs):
            self._take({"type": "openrouter:web_fetch", "status": "completed", "url": "https://example.org/other",
                        "title": "Other", "content": "Something else entirely.", "httpStatus": 200})
            self.usage = measured_usage({"input_tokens": 900, "output_tokens": 3}, model)
            yield self.event("usage", "usage", usage=self.usage)
            self.text, self.finish_reason = "OK", "stop"
    monkeypatch.setattr(agent_read_source, "PageFetch", Fetch)
    loop, _, saved = run(store, Plan())
    [result] = results(loop)
    assert result["status"] == "failed" and "different page" in result["reason"]
    assert "Something else" not in json.dumps(saved["agent_review"])
    # Exa's normalised spelling of the same page is the same page.
    assert agent_read_source._same_page("http://www.example.org/report/", CITED)
    assert agent_read_source._same_page("", CITED)


def test_cited_spelling_variants_and_a_second_read_fetch_once(store, monkeypatch, enabled):
    calls = fake_fetch(monkeypatch)
    loop, _, saved = run(store, Plan(steps=[[compare()], [read_call("http://Example.org/report/"), read_call()]]))
    first, again = results(loop)
    assert first["status"] == "completed" and again["status"] == "already_read" and "text" not in again
    assert len(calls) == 1 and len(saved["agent_review"]["read_sources"]) == 1


def test_reads_stop_at_the_message_and_step_limits(store, monkeypatch, enabled):
    calls = fake_fetch(monkeypatch)
    urls = [f"https://example.org/page-{i}" for i in range(READS_PER_MESSAGE + 2)]
    # One read too many in the first step, then full steps up to the limit.
    rest = urls[READS_PER_STEP + 1:READS_PER_MESSAGE + 1]
    steps = [[compare()], [read_call(u) for u in urls[:READS_PER_STEP + 1]],
             *[[read_call(u) for u in rest[i:i + READS_PER_STEP]] for i in range(0, len(rest), READS_PER_STEP)],
             [read_call(urls[-1])]]
    loop, _, saved = run(store, Plan(steps=steps, cited=urls))
    outcome = [r["reason"] if r["status"] == "refused" else r["status"] for r in results(loop)]
    assert outcome[:READS_PER_STEP] == ["completed"] * READS_PER_STEP
    assert outcome[READS_PER_STEP].startswith(f"At most {READS_PER_STEP} sources per step")
    assert outcome[READS_PER_STEP + 1:-1] == ["completed"] * (READS_PER_MESSAGE - READS_PER_STEP)
    assert outcome[READS_PER_STEP].endswith("Continue with what you have.")
    assert outcome[-1] == (f"This message already read {READS_PER_MESSAGE} sources, the maximum. Continue with what "
                           "you have: write the answer.")
    assert len(calls) == READS_PER_MESSAGE == len(saved["agent_review"]["read_sources"])
    assert saved["status"] == "completed" and saved["assistant_response"] == ANSWER


def test_a_failed_fetch_is_saved_as_failed_not_as_content(store, monkeypatch, enabled):
    calls = fake_fetch(monkeypatch, status="incomplete", error="HTTP 404: Page not found")
    plan = Plan()
    loop, events, saved = run(store, plan)
    [result] = results(loop)
    assert result["status"] == "failed" and "untrusted_page_text" not in result and "404" in result["reason"]
    assert "error" not in result  # a result, not a tool error (see read)
    [record] = saved["agent_review"]["read_sources"]
    assert record["status"] == "failed" and "text" not in record
    # The agent writes the answer knowing the page was not read: the failure
    # is its last tool result, and no page text is anywhere in its context.
    last = json.loads(plan.answer_messages[-1]["content"])
    assert last == result and saved["assistant_response"] == ANSWER
    assert not any("untrusted_page_text" in str(m.get("content") or "") for m in plan.answer_messages)
    # The helper's session says why.
    helper = next(a for a in store.delegation_view(UID, loop.chat_id, loop.turn_id)["agents"] if a.get("kind") == "source")
    assert helper["status"] == "failed" and "404" in helper["failure"]["error"]
    done = tool_events(events)[-1]
    assert done["read"] == "failed" and "sources" not in done
    # A page that failed at the source is not retried with the second helper.
    assert len(calls) == 1


def test_a_provider_failure_tries_the_second_helper(store, monkeypatch, enabled):
    calls = fake_fetch(monkeypatch, fail_models=("openai",))
    loop, _, saved = run(store, Plan())
    assert [c["model"].split("/")[0] for c in calls] == ["openai", "google"]
    assert results(loop)[0]["status"] == "completed"
    helpers = [a for a in store.delegation_view(UID, loop.chat_id, loop.turn_id)["agents"] if a.get("kind") == "source"]
    assert sorted(a["status"] for a in helpers) == ["completed", "failed"]


def hanging_fetch(monkeypatch, on_start=None):
    """A fetch that hangs until its cancellation fires, like a stalled provider."""
    import time
    from app.services.llm.provider_runtime import ProviderCancelled, current_provider_cancellation

    class Fetch(PageFetch):
        def stream(self, *, model, messages, tools=None, **kwargs):
            if on_start:
                on_start()
            while not current_provider_cancellation().cancelled:
                time.sleep(.01)
            raise ProviderCancelled("provider stream cancelled")
            yield
    monkeypatch.setattr(agent_read_source, "PageFetch", Fetch)


def test_a_read_that_runs_out_of_time_fails_alone_and_the_turn_goes_on(store, monkeypatch, enabled):
    monkeypatch.setattr(agent_read_source, "READ_SECONDS", .3)
    hanging_fetch(monkeypatch)
    loop, _, saved = run(store, Plan())
    [result] = results(loop)
    assert result["status"] == "failed" and "timeout" in result["reason"]
    assert saved["status"] == "completed" and saved["agent_review"]["read_sources"][0]["error"] == "timeout"


def test_a_server_side_stop_during_a_read_is_no_timeout(store, monkeypatch, enabled):
    """A stop raised by the store (cancel requested elsewhere) before the turn's
    own token is cancelled ends the turn; only the read's timer means timeout."""
    from app.services.llm.provider_runtime import ProviderCancelled

    class Fetch(PageFetch):
        def stream(self, **kwargs):
            raise ProviderCancelled("stop requested")
            yield
    monkeypatch.setattr(agent_read_source, "PageFetch", Fetch)
    loop = chat_loop(store, Plan())
    with pytest.raises(ProviderCancelled):
        list(loop.run())
    assert loop.comparison.reader.reads[0]["error"] == "stopped"


def test_a_stop_during_a_read_stops_the_turn(store, monkeypatch, enabled):
    from app.services.llm.provider_runtime import ProviderCancelled
    plan = Plan()
    loop = chat_loop(store, plan)
    hanging_fetch(monkeypatch, on_start=loop.cancellation.cancel)
    # Only the first save goes through: the stored review keeps the read as
    # "running", as after a failed final save; the run's end must fix it.
    reader, saves = loop.comparison.reader, []
    first = reader._checkpoint
    reader._checkpoint = lambda: saves or (saves.append(1), first())
    with pytest.raises(ProviderCancelled):
        list(loop.run())
    [record] = reader.reads
    assert record["status"] == "failed" and record["error"] == "stopped"
    [stored] = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]["read_sources"]
    assert stored["status"] == "failed" and stored["error"] == "stopped"


def test_admission_gives_up_when_a_page_read_cannot_fit(store, monkeypatch, enabled):
    """The read's tokens do not shrink with its output allowance: a short
    allowance must refuse the read at once, not retry the same claim forever."""
    from dataclasses import replace
    from types import SimpleNamespace
    from app.services.agent_quota import AgentTokenBudgetExceeded
    from app.services.agent_tools import ToolRegistry
    loop = chat_loop(store, Plan())
    claims = []

    def claim(*args, reservation, **kwargs):
        claims.append(reservation)
        if len(claims) > 5:
            raise AssertionError("admission spins")
        raise AgentTokenBudgetExceeded(3000, reservation[0])
    monkeypatch.setattr(loop.store, "claim", claim)
    model = replace(resolve_agent_model("claude-haiku-4-5"), max_output_tokens=agent_read_source.FETCH_OUTPUT_TOKENS)
    tool = web_fetch_tool(max_uses=1, max_content_tokens=READ_CONTENT_TOKENS, allowed_domains=["example.org"])
    admission = loop._admit_chat_step(model, [{"role": "user", "content": "Read " + CITED}], "agent:x:0", ToolRegistry(),
                                      loop.cancellation, 0, {}, SimpleNamespace(kind="source"), None, server_tools=[tool])
    with pytest.raises(AgentTokenBudgetExceeded):
        while True:
            next(admission)
    assert 1 <= len(claims) <= 2


def test_a_full_review_trims_saved_page_texts_before_it_fails(store, monkeypatch, enabled):
    loop = comparison_ready(store)
    saved = []
    monkeypatch.setattr(loop.store, "save_review", lambda *args: saved.append(args[4]))
    reader = loop.comparison.reader
    reader.reads = [{"id": i, "status": "completed", "url": f"https://example.org/{i}", "title": "t",
                     "text": "x" * 140_000, "point": "p", "cited_by": []} for i in range(5)]
    loop.comparison.checkpoint()
    assert all(len(r["text"]) == agent_read_source.READ_TRIM_CHARS and r["text_trimmed"]
               for r in saved[-1]["read_sources"])
    # The agent keeps the full text (only the saved copy is trimmed).
    assert len(reader.reads[0]["text"]) == 140_000


def test_no_read_starts_close_to_the_answer_deadline(store, monkeypatch, enabled):
    calls = fake_fetch(monkeypatch)
    loop = comparison_ready(store)
    loop.answer_time_left = lambda: agent_read_source.READ_MIN_SECONDS - 1
    result = read(loop)
    refused(result, "no time left")
    assert "call answer" not in json.dumps(result).lower()
    assert calls == [] and loop.comparison.reader.reads == []


def test_gemini_grounding_redirects_are_read_as_the_page_they_point_to(store, monkeypatch, enabled):
    redirect = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AbC123"
    monkeypatch.setattr(agent_read_source, "resolve_redirect", lambda url: CITED if url == redirect else url)
    calls = fake_fetch(monkeypatch)
    loop, events, saved = run(store, Plan(steps=[[compare()], [read_call(redirect), read_call(redirect)]],
                                          cited=(redirect,)))
    assert calls[0]["tools"][0]["parameters"]["allowed_domains"] == ["example.org"]
    [record] = saved["agent_review"]["read_sources"]
    assert record["url"] == CITED and record["cited_url"] == redirect and record["host"] == "example.org"
    running, done, *_ = tool_events(events)
    assert "host" not in running and done["host"] == "example.org"
    # The redirect it was cited by counts as read too.
    assert results(loop)[1]["status"] == "already_read" and len(calls) == 1


def test_resolve_redirect_reads_only_the_location_of_googles_redirect(monkeypatch):
    import httpx
    requested = []

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
        def get(self, url, headers=None):
            requested.append(url)
            return httpx.Response(302, headers={"location": "https://www.bund.de/page"})
    monkeypatch.setattr(httpx, "Client", Client)
    redirect = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/x"
    assert resolve_redirect(redirect) == "https://www.bund.de/page"
    assert resolve_redirect(CITED) == CITED and requested == [redirect]


def test_mock_llm_reads_without_a_provider_call(store, monkeypatch, enabled):
    class Forbidden(PageFetch):
        def stream(self, **kwargs):
            raise AssertionError("no provider call under MOCK_LLM")
            yield
    monkeypatch.setattr(agent_read_source, "PageFetch", Forbidden)
    plan = Plan()
    loop = chat_loop(store, plan)
    original = loop.comparison.reader._call

    def mocked(*args, **kwargs):
        # MOCK_LLM only during the helper call: the scripted steps stay scripted.
        loop.mock_answer = "Agent test answer: Price?"
        try:
            return original(*args, **kwargs)
        finally:
            loop.mock_answer = None
    loop.comparison.reader._call = mocked
    list(loop.run())
    [result] = results(loop)
    assert result["status"] == "completed" and "1889" in result["untrusted_page_text"]


def test_reservation_includes_the_page_tokens_and_fee():
    model = resolve_agent_model("claude-haiku-4-5")
    costs = RunCosts(AgentPolicy.for_chat({**defaults(), "enabled": False}))
    messages = [{"role": "user", "content": "Read " + CITED}]
    tool = web_fetch_tool(max_uses=1, max_content_tokens=READ_CONTENT_TOKENS, allowed_domains=["example.org"])
    plain_tokens, plain_cost = costs.estimate(model, messages, [])
    tokens, cost = costs.estimate(model, messages, [tool])
    assert fetch_bounds([tool]) == (1, int(READ_CONTENT_TOKENS * 1.25))
    # The page joins the input of the continuation that reads it.
    assert tokens - plain_tokens >= READ_CONTENT_TOKENS
    assert cost - plain_cost >= FETCH_COST_NANOS
    assert fetch_bounds([{"type": "openrouter:web_search", "parameters": {"max_uses": 3}}]) == (0, 0)


class Lines:
    def __init__(self, events):
        self.lines = [line for event in events for line in (f"data: {json.dumps(event)}", "")]
        self.closed = False

    def __iter__(self):
        return iter(self.lines)

    def close(self):
        self.closed = True


def test_page_fetch_reads_the_page_and_usage_from_the_responses_stream(monkeypatch):
    sent = {}
    usage = {"input_tokens": 4063, "output_tokens": 36, "cost": 0.00052335,
             "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 3962},
             "output_tokens_details": {"reasoning_tokens": 0},
             "server_tool_use_details": {"tool_calls_requested": 1, "tool_calls_executed": 1}}
    item = {"type": "openrouter:web_fetch", "id": "st_1", "status": "completed", "url": CITED,
            "title": "Report", "content": PAGE, "httpStatus": 200}
    lines = Lines([
        {"type": "response.created", "response": {"id": "gen-123", "status": "in_progress"}},
        {"type": "response.output_item.added", "item": {"type": "openrouter:web_fetch", "status": "in_progress"}},
        {"type": "response.output_item.done", "item": item},
        {"type": "response.output_text.delta", "delta": "OK"},
        {"type": "response.completed", "response": {"output": [item], "usage": usage}},
    ])

    def fake_lines(url, *, json, headers, progress=None):
        sent.update(url=url, payload=json)
        return lines
    monkeypatch.setattr(agent_read_source, "cancellable_sse_lines", fake_lines)
    model = resolve_agent_model("claude-haiku-4-5")
    tool = web_fetch_tool(max_uses=1, max_content_tokens=READ_CONTENT_TOKENS, allowed_domains=["example.org"])
    completion = PageFetch()
    events = list(completion.stream(model=model, messages=[{"role": "user", "content": "x"}], api_key="k", tools=[tool]))
    assert sent["url"].endswith("/api/v1/responses")
    assert sent["payload"]["provider"] == {"sort": "throughput", "data_collection": "deny"} and sent["payload"]["tools"] == [tool]
    assert sent["payload"]["input"] == [{"role": "user", "content": "x"}] and sent["payload"]["stream"] is True
    assert completion.page["status"] == "completed" and completion.page["text"] == PAGE
    assert completion.page["title"] == "Report" and completion.page["http_status"] == 200
    assert completion.finish_reason == "stop" and completion.text == "OK" and lines.closed
    assert completion.generation_id == "gen-123"
    assert completion.usage["input_tokens"] == 4063 and completion.usage["output_tokens"] == 36
    # OpenRouter's cost plus Exa's fee for the page, which that cost leaves out.
    assert completion.usage["estimated_cost_nano_usd"] == 523_350 + FETCH_COST_NANOS
    assert completion.usage["cost_source"] == "provider"
    assert [e["kind"] for e in events] == ["usage"]


def test_page_fetch_marks_a_refused_page_and_raises_on_a_failed_response(monkeypatch):
    refused = {"type": "openrouter:web_fetch", "status": "incomplete", "url": CITED,
               "error": "URL domain is not allowed by domain filtering rules."}
    monkeypatch.setattr(agent_read_source, "cancellable_sse_lines", lambda *a, **k: Lines([
        {"type": "response.output_item.done", "item": refused},
        {"type": "response.completed", "response": {"output": [], "usage": {"input_tokens": 10, "output_tokens": 2}}}]))
    model = resolve_agent_model("claude-haiku-4-5")
    completion = PageFetch()
    list(completion.stream(model=model, messages=[], api_key="k", tools=[]))
    assert completion.page["status"] == "failed" and "domain filtering" in completion.page["error"]
    monkeypatch.setattr(agent_read_source, "cancellable_sse_lines", lambda *a, **k: Lines([
        {"type": "response.failed", "response": {"error": {"code": 502, "message": "upstream"}}}]))
    with pytest.raises(Exception) as caught:
        list(PageFetch().stream(model=model, messages=[], api_key="k", tools=[]))
    assert getattr(caught.value, "status_code", None) == 502


def test_cited_urls_match_canonically_and_only_http():
    assert url_key("http://Example.org/report/") == url_key("https://example.org/report")
    assert url_key("https://example.org/report?a=1#x") == "https://example.org/report?a=1"
    assert url_key("ftp://example.org/x") == "" and url_key("javascript:alert(1)") == ""
    # Exa's domain filter gets an IDN host in its ASCII form.
    assert agent_read_source._ascii_host("https://bücher.de/x") == "xn--bcher-kva.de"
    # A redirect target follows the rules of a cited URL.
    assert not agent_read_source._safe_url("https://user:pw@example.org/") and not agent_read_source._safe_url(
        "https://example.org/a b") and agent_read_source._safe_url(CITED)


def test_an_empty_allowance_fails_only_the_read(store, monkeypatch, enabled):
    from app.services.agent_quota import AgentTokenBudgetExceeded
    calls = []

    class Fetch(PageFetch):
        def stream(self, *, model, **kwargs):
            calls.append(model.model)
            raise AgentTokenBudgetExceeded(0, 7000)
            yield
    monkeypatch.setattr(agent_read_source, "PageFetch", Fetch)
    loop, _, saved = run(store, Plan())
    [result] = results(loop)
    assert result["status"] == "failed" and "allowance" in result["reason"]
    # No second helper for an empty account; the turn still answers.
    assert len(calls) == 1 and saved["status"] == "completed"
