"""Why the correction pass kept nothing, and its one more request
(agent_review_feedback.read_reply, shape_rule, repair_note;
AnswerAudit._corrections). In Prod 6 of the first 20 passes with findings
ended "unreadable" after a complete reply, and nothing said why: of the
findings whose sentence had a link or a reviewer's source, 13 of 24 stayed
open, of those without, none of 17. The forms here are those: a reviewer's
source added as a link, inline or cited after the sentence's end, a second
link beside the sentence's own, one finding without its list."""
import json

import pytest

from app.services import agent_answer_links, agent_audit_metrics, agent_review_feedback as fb
from test_agent_audit import ANSWER, RATES, TOOL_CALL_REPLY, Audit
from test_agent_review_feedback import _marks_kept, correction_request, feedback_loop, log_entries
from test_agent_review_feedback_robust import raw_turn
from test_agent_runs import UID, pending, store  # noqa: F401  (fixtures)

TICKETS = "Tickets to the top cost 14 euros."
SOURCE = "https://example.org/rates-2026"
OWN = "https://example.org/visits"


@pytest.fixture(autouse=True)
def _admin_allowance(monkeypatch):
    from app.services import agent_budget_config
    monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, "pro", 5_000_000)


@pytest.fixture
def pages_exist(monkeypatch):
    """Every new link's page exists, without a request to the web."""
    async def public(url):
        return True

    async def found(url, **kwargs):
        return None
    monkeypatch.setattr(fb, "_public", public)
    monkeypatch.setattr(agent_answer_links, "link_gone", found)


def one(before, after, sources=(), cell=False):
    """read_reply of a one-finding pass whose reply corrects ``before`` to ``after``."""
    items = {"s1": (0, len(before), before)}
    return fb.read_reply(json.dumps({"findings": [{"id": "s1", "sentence": after}]}), items,
                         {"s1": set(sources)}, {"s1"} if cell else ())


# --- The forms Prod turned down ---------------------------------------------------

@pytest.mark.parametrize("after", [
    f"Tickets to the top cost 36.10 euros, as the [rates page]({SOURCE}) lists.",
    f"Tickets to the top cost 36.10 euros ([rates]({SOURCE})).",
    f"Tickets to the top cost 36.10 euros. [Rates]({SOURCE})",
    f"Tickets to the top cost 36.10 euros. ([Rates]({SOURCE}), [Tower]({SOURCE}))",
], ids=["inline", "in-brackets", "cited-after-the-end", "two-cited-after-the-end"])
def test_a_correction_may_cite_the_reviewers_source(after):
    """The reviewer named a page; the agent corrected the figure and linked
    it. The app took a link only in place of one the sentence had."""
    assert one(TICKETS, after, {SOURCE}) == ({"s1": ("corrected", after)}, {}, None)
    # Any other address stays out, and so does the source where none was named.
    assert one(TICKETS, after.replace(SOURCE, "https://example.org/elsewhere"), {SOURCE})[1] == {"s1": "links"}
    assert one(TICKETS, after)[1] == {"s1": "links"}


def test_a_second_link_beside_the_sentences_own():
    before = f"Fable and Opus are tied on the [coding index]({OWN}): 79.7 versus 79.8."
    after = (f"Fable and Opus are tied on the [coding index]({OWN}) at 79.7 versus 79.8, while the "
             f"[leaderboard]({SOURCE}) lists Fable at 80.8.")
    assert one(before, after, {SOURCE})[0] == {"s1": ("corrected", after)}
    # The sentence's own link may not go, unless the source takes its place.
    assert one(before, after.replace(f"[coding index]({OWN})", "coding index"), {SOURCE})[0] \
        == {"s1": ("corrected", after.replace(f"[coding index]({OWN})", "coding index"))}
    dropped = "Fable and Opus are tied on the coding index at 79.7 versus 79.8."
    assert one(before, dropped, {SOURCE})[1] == {"s1": "links"}


def test_links_cited_after_the_end_end_a_sentence_and_nothing_else_does():
    assert fb._ends_sentence(f"It costs 36.10 euros. [Rates]({SOURCE})")
    assert fb._ends_sentence(f"It costs 36.10 euros. ([Rates]({SOURCE}), [Tower]({OWN}))")
    assert fb._ends_sentence(f"It costs 36.10 euros ([Rates]({SOURCE})).")
    assert not fb._ends_sentence(f"It costs 36.10 euros [Rates]({SOURCE})")
    assert not fb._ends_sentence("It costs 36.10 euros as of 2026 and the lift")
    assert fb._ends_sentence("It is [Foo](https://example.org/Foo_(bar)).")
    assert one(TICKETS, f"Tickets to the top cost 36.10 euros [rates]({SOURCE})", {SOURCE})[1] \
        == {"s1": "sentence_end"}
    # Read once from the end: long runs of links and brackets end at once.
    assert fb._ends_sentence("It costs 36.10 euros. " + "[a](https://example.org/a), " * 200)
    assert not fb._ends_sentence("[a](b) " * 230 + "x") and not fb._ends_sentence(")" * 1600)
    assert not fb._ends_sentence("It costs 36.10 euros. ([a](b), " * 160 + "x")


def test_one_finding_may_come_without_its_list():
    items = {"s1": (0, len(TICKETS), TICKETS)}
    fixed = "Tickets to the top cost 36.10 euros."
    assert fb.read_reply(json.dumps({"id": "s1", "sentence": fixed}), items)[0] == {"s1": ("corrected", fixed)}
    assert fb.read_reply(json.dumps({"findings": {"id": "s1", "stands": "It holds."}}), items)[0] \
        == {"s1": ("disputed", "It holds.")}


# --- Why: the reply as a whole, each finding ----------------------------------------

def test_the_reader_says_why_each_finding_stayed_open():
    first, second = "The tower is 330 metres tall.", "It opened in 1889 for visitors."
    items = {"s1": (0, len(first), first), "s2": (31, 31 + len(second), second), "s3": (0, 4, "Word")}
    reply = json.dumps({"findings": [
        {"id": "s1", "sentence": first},
        {"id": "s2", "sentence": "It opened in 1889.\nFor visitors."},
        {"id": "s9", "sentence": "Unknown."}]})
    assert fb.read_reply(reply, items) == ({}, {"s1": "unchanged", "s2": "line_break", "s3": "missing"}, None)
    assert fb.read_reply(json.dumps({"findings": [{"id": "s1"}]}), items)[1]["s1"] == "empty"
    assert fb.read_reply("I would rather not.", items) == ({}, {}, "not_json")
    assert fb.read_reply(json.dumps({"findings": []}), items) == ({}, {}, "no_findings")
    assert fb.read_reply(json.dumps({"marks": []}), items) == ({}, {}, "no_findings")
    assert fb.read_reply(json.dumps({"findings": [{"id": "x1", "stands": "No."}]}), items) == ({}, {}, "unknown_id")
    # A settled finding is never listed as left.
    settled = json.dumps({"findings": [{"id": "s1", "stands": "Official height."}, {"id": "s1", "sentence": "x"}]})
    assert fb.read_reply(settled, items)[1] == {"s2": "missing", "s3": "missing"}


@pytest.mark.parametrize("after, rule", [
    ("costs 36.10", "too_short"),
    ("Tickets to the top cost 36.10 euros. " * 20, "too_long"),
    ("Tickets cost 36.10 euros. The lift is extra. The stairs are cheaper. Children pay less.", "sentences"),
    ("Tickets to the top cost 36.10 euros as of 2026 and the lift", "sentence_end"),
    ("Tickets to the top cost **36.10 euros.", "markdown"),
    ("Tickets to the top cost 36.10 euros picture:p1.", "pictures"),
    ("Tickets | to the top cost 36.10 euros.", "cell_border"),
])
def test_each_rule_has_its_name(after, rule):
    assert one(TICKETS, after)[1] == {"s1": rule}


def test_the_note_of_one_more_request_names_the_form_only():
    note = fb.repair_note(None, {"s1": "links", "s3": "missing"})
    assert note.startswith("Your previous reply could not be used (s1: a link to an address")
    assert "s3: no entry" in note and note.endswith("one entry per finding.")
    assert "it held no JSON object" in fb.repair_note("not_json", {})
    assert "it called a tool" in fb.repair_note("tool_calls", {})
    assert set(fb.REJECTIONS) >= {"missing", "links", "sentences", "sentence_end", "link_not_found", "place"}


# --- The pass: one more request, and its limits ---------------------------------

def tickets_id(asked):
    return next(item["id"] for item in asked if "Tickets" in item["sentence"])


def corrector(*replies, seen=None):
    """The agent model's correction replies in turn (a text, a dict for a
    tool call, a callable of the findings); its reviewer rounds mark nothing.
    ``seen``: each correction request's last message."""
    queue = list(replies)

    def answer(messages):
        asked = correction_request(messages)
        if asked is None:
            return json.dumps({"marks": []})
        if seen is not None:
            seen.append(messages[-1]["content"])
        reply = queue.pop(0) if len(queue) > 1 else queue[0]
        return reply(asked) if callable(reply) else reply
    return answer


def fix(sentence):
    return lambda asked: json.dumps({"findings": [{"id": tickets_id(asked), "sentence": sentence}]})


def test_a_reply_that_settles_nothing_gets_one_more_request_with_why(store, pages_exist, caplog):
    seen = []
    elsewhere = "Tickets to the top cost 36.10 euros, see [rates](https://example.org/elsewhere)."
    cited = f"Tickets to the top cost 36.10 euros ([rates]({RATES}))."
    loop = feedback_loop(store, Audit(live={"anthropic": corrector(fix(elsewhere), fix(cited), seen=seen)}))
    with caplog.at_level("WARNING"):
        list(loop.run())
    assert len(seen) == 2 and seen[1].startswith(seen[0])
    key = tickets_id(json.loads(seen[0].split("\n", 1)[1].split("\n\nFor each finding", 1)[0])["findings"])
    note = seen[1][len(seen[0]):]
    assert note.startswith("\n\nYour previous reply could not be used (") and f"{key}: a link to an address" in note
    turn = raw_turn(store, loop)
    assert ANSWER.replace(TICKETS, cited) == turn["assistant_response"]
    feedback = turn["agent_review"]["audit"]["feedback"]
    assert "skipped" not in feedback and feedback["counts"]["corrected"] == 1
    first, again = feedback["pass"]["requests"]
    assert first["outcome"] == "rejected" and first["rejected"][key] == "links"
    assert again["outcome"] == "settled" and key not in again.get("rejected", {})
    assert feedback["pass"]["model"] == loop.model.model
    # The run's log and the daily counters say the same, the log line too: codes, never the reply.
    assert log_entries(store, loop, "answer_corrected")[0]["content"]["requests"] == feedback["pass"]["requests"]
    counted = agent_audit_metrics.turn_counters(turn, agent_audit_metrics.capture(loop))["correction"]
    assert counted["passes"] == 1 and counted["first"] == {"rejected": 1} and counted["again"] == {"settled": 1}
    assert counted["rejected"]["links"] == 1
    assert counted["models"] == {agent_audit_metrics.label(loop.model.model): {"settled": 1}}
    assert "request=1 outcome=rejected rejected=" in caplog.text and f"{key}:links" in caplog.text
    assert "elsewhere" not in caplog.text and "36.10" not in caplog.text


def test_a_tool_call_instead_of_the_reply_gets_one_more_request(store):
    seen = []
    loop = feedback_loop(store, Audit(live={"anthropic": corrector(
        TOOL_CALL_REPLY, fix("Tickets to the top cost 36.10 euros."), seen=seen)}))
    list(loop.run())
    turn = raw_turn(store, loop)
    assert len(seen) == 2 and "it called a tool" in seen[1]
    assert "Tickets to the top cost 36.10 euros." in turn["assistant_response"]
    outcomes = [r["outcome"] for r in turn["agent_review"]["audit"]["feedback"]["pass"]["requests"]]
    assert outcomes == ["tool_calls", "settled"]
    session = next(a for a in store.delegation_view(UID, loop.chat_id, loop.turn_id)["agents"]
                   if a.get("kind") == "correction")
    assert session["status"] == "completed"


def test_at_most_one_more_request_and_the_pass_stays_unreadable(store):
    seen = []
    loop = feedback_loop(store, Audit(live={"anthropic": corrector("I would rather not.", seen=seen)}))
    list(loop.run())
    turn = raw_turn(store, loop)
    assert len(seen) == 2 and turn["assistant_response"] == ANSWER
    feedback = turn["agent_review"]["audit"]["feedback"]
    assert feedback["skipped"] == "unreadable" and _marks_kept(turn["agent_review"])
    assert [r["outcome"] for r in feedback["pass"]["requests"]] == ["not_json", "not_json"]


@pytest.mark.parametrize("why", ["no_time", "newer_message"])
def test_no_second_request_without_its_time_or_once_a_newer_message_started(store, monkeypatch, why):
    if why == "no_time":
        monkeypatch.setattr(fb, "CORRECTION_AGAIN_SECONDS", fb.CORRECTION_SECONDS + 1)
    else:
        begin, calls = type(store).begin_correction, []

        def newer_after_the_first(self, *args, **kwargs):
            calls.append(1)
            return begin(self, *args, **kwargs) if len(calls) == 1 else False
        monkeypatch.setattr(type(store), "begin_correction", newer_after_the_first)
    seen = []
    loop = feedback_loop(store, Audit(live={"anthropic": corrector("I would rather not.", seen=seen)}))
    list(loop.run())
    feedback = raw_turn(store, loop)["agent_review"]["audit"]["feedback"]
    assert len(seen) == 1 and feedback["skipped"] == "unreadable"
    assert feedback["pass"]["requests"] == [{"outcome": "not_json", "again": why}]


def test_a_second_request_the_allowance_refuses_leaves_the_pass_as_the_first_left_it(store, monkeypatch):
    from app.services.agent_quota import AgentTokenBudgetExceeded
    claim = type(store).claim

    def refuse_the_second(self, uid, chat_id, turn_id, model, *, step="completion:0", **kwargs):
        if step.startswith("agent:") and step.endswith(":1") and loop.comparison.auditor.feedback.status == "checking":
            raise AgentTokenBudgetExceeded(0, 100)
        return claim(self, uid, chat_id, turn_id, model, step=step, **kwargs)
    monkeypatch.setattr(type(store), "claim", refuse_the_second)
    loop = feedback_loop(store, Audit(live={"anthropic": corrector("I would rather not.")}))
    list(loop.run())
    turn = raw_turn(store, loop)
    feedback = turn["agent_review"]["audit"]["feedback"]
    assert turn["assistant_response"] == ANSWER and feedback["skipped"] == "unreadable"
    assert [r["outcome"] for r in feedback["pass"]["requests"]] == ["not_json", "allowance"]


def test_the_users_stop_during_the_second_request_keeps_the_answer_and_its_marks(store):
    from app.services.llm.provider_runtime import ProviderCancelled

    def stop(asked):
        script.loop.cancellation.cancel()
        raise ProviderCancelled("stopped")
    script = Audit(live={"anthropic": corrector("I would rather not.", stop)})
    loop = feedback_loop(store, script)
    try:
        list(loop.run())
    except ProviderCancelled:
        pass
    turn = raw_turn(store, loop)
    assert turn["assistant_response"] == ANSWER
    review = turn["agent_review"]
    assert review["audit"]["feedback"]["status"] == "done" and _marks_kept(review)


def test_a_provider_failure_gets_no_second_request_and_says_why(store):
    from app.services.llm.engines import _ProviderHTTPStatusError
    seen = []

    def refused(asked):
        seen.append(asked)
        raise _ProviderHTTPStatusError(503, diagnostic="provider=Azure")
    loop = feedback_loop(store, Audit(live={"anthropic": corrector(refused)}))
    list(loop.run())
    feedback = raw_turn(store, loop)["agent_review"]["audit"]["feedback"]
    assert len(seen) == 1 and feedback["skipped"] == "failed"
    assert feedback["pass"]["requests"] == [{"outcome": "provider_unavailable"}]


def test_a_source_whose_page_is_missing_is_named_as_such(store, monkeypatch):
    async def public(url):
        return True

    async def gone(url, **kwargs):
        return 404
    monkeypatch.setattr(fb, "_public", public)
    monkeypatch.setattr(agent_answer_links, "link_gone", gone)
    cited = f"Tickets to the top cost 36.10 euros ([rates]({RATES}))."
    loop = feedback_loop(store, Audit(live={"anthropic": corrector(fix(cited))}))
    list(loop.run())
    feedback = raw_turn(store, loop)["agent_review"]["audit"]["feedback"]
    first, again = feedback["pass"]["requests"]
    assert "link_not_found" in first["rejected"].values() and again["outcome"] == "rejected"
    assert feedback["skipped"] == "unreadable"


FILTERED = ['{"choices":[{"delta":{},"finish_reason":"content_filter"}],'
            '"usage":{"prompt_tokens":10,"completion_tokens":0}}']
FILTERED_LINE = ['{"choices":[{"delta":{"content":"I cannot help with that."}}]}',
                 '{"choices":[{"delta":{},"finish_reason":"content_filter"}],'
                 '"usage":{"prompt_tokens":10,"completion_tokens":7}}']
CALL_ONLY = ['{"choices":[{"delta":{"tool_calls":[{"index":0,"id":"c1","type":"function",'
             '"function":{"name":"lookup","arguments":"{}"}}]}}]}',
             '{"choices":[{"delta":{},"finish_reason":"tool_calls"}],'
             '"usage":{"prompt_tokens":10,"completion_tokens":5}}']


@pytest.mark.parametrize("events, outcome", [(FILTERED, "filtered"), (FILTERED_LINE, "filtered"),
                                             (CALL_ONLY, "tool_calls")],
                         ids=["filter-before-a-word", "filter-after-a-line", "tool-call-only"])
def test_what_the_provider_sent_names_why_a_request_brought_nothing(monkeypatch, events, outcome):
    """The real client on the provider's stream (HTTP mock): the pass's
    tools are listed and not callable, so a filter or a lone tool call ends
    the stream with an error, and its completion says which."""
    import httpx
    from app.services.agent_audit import correction_outcome
    from app.services.llm import provider_runtime as runtime
    from app.services.llm.agent_client import AgentCompletion, AgentModel

    body = "".join(f"data: {line}\n\n" for line in events) + "data: [DONE]\n\n"
    http = runtime.ProviderHTTP(transport=httpx.MockTransport(lambda _: httpx.Response(200, text=body)))
    monkeypatch.setattr(runtime, "_provider_http", http)
    tools = [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}]
    value = AgentCompletion()
    try:
        with runtime.bind_analysis_budget(runtime.AnalysisBudget(unlimited=True)):
            with pytest.raises(Exception) as raised:
                list(value.stream(model=AgentModel(), messages=[{"role": "user", "content": "Q"}], api_key="test",
                                  tools=tools, allow_tool_calls=False))
    finally:
        http.shutdown()
    assert correction_outcome(raised.value, value) == outcome


# --- Counted ---------------------------------------------------------------------

def test_the_counters_keep_codes_and_model_ids_only():
    counters = agent_audit_metrics.correction_counters({
        "skipped": "unreadable", "model": "openai/gpt-6.1-terra", "requests": [
            {"outcome": "rejected", "rejected": {"s1": "links", "s2": "missing"}},
            {"outcome": "not_json", "again": None}]}, {})
    assert counters == {"correction": {
        "skipped": {"unreadable": 1}, "passes": 1, "models": {"openai_gpt-6_1-terra": {"unsettled": 1}},
        "first": {"rejected": 1}, "again": {"not_json": 1}, "rejected": {"links": 1, "missing": 1}}}
    # A pass that never sent a request counts only why.
    assert agent_audit_metrics.correction_counters({"skipped": "no_time"}, {}) == {
        "correction": {"skipped": {"no_time": 1}}}
    held = agent_audit_metrics.correction_counters({"model": "m", "requests": [
        {"outcome": "not_json", "again": "newer_message"}]}, {})
    assert held["correction"]["not_again"] == {"newer_message": 1}
    assert agent_audit_metrics.correction_counters(None, {}) == {}
