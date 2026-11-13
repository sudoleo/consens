"""findings_to_agent held to Max' bar ("sehr solide, kein Overhead"): the
reviewers stay independent, a correction never breaks the answer, and every
path ends in a clean state (agent_review_feedback.py). The feature's own
flow is test_agent_review_feedback."""
import json
import time

import pytest

from app.services import agent_review_feedback as fb
from test_agent_audit import ANSWER, RATES, Audit, round_entries
from test_agent_review_feedback import FIXED, _marks_kept, agent_side, correction_request, feedback_loop, log_entries
from test_agent_runs import UID, pending, store  # noqa: F401  (fixtures)


@pytest.fixture(autouse=True)
def _admin_allowance(monkeypatch):
    from app.services import agent_budget_config
    monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, "pro", 5_000_000)


def fix_tickets(findings):
    return json.dumps({"findings": [{"id": f["id"], "sentence": FIXED} for f in findings
                                    if "Tickets" in f["sentence"]]})


def raw_turn(store, loop):
    """The turn as stored, every field (get_turn leaves some out)."""
    return store._turn_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()


# --- The reviewers stay independent ------------------------------------------------

def test_the_reviewers_never_read_what_the_agent_was_told(store):
    """A reviewer that read another's notes would no longer judge on its own,
    and its echo would pass for a second voice: it reads only that the agent
    got findings, about which entries."""
    rounds = {}

    def make_flag(family):
        def flag(messages):
            if correction_request(messages) is not None:
                # The agent's own correction pass (its model is Anthropic's too).
                return json.dumps({"findings": []})
            rounds.setdefault(family, []).append(list(messages))
            user = [m for m in messages if m["role"] == "user"]
            entries, _ = round_entries(user[-1])
            steps = [e["seq"] for e in entries or [] if e["kind"] == "step"]
            marks = [{"entry": steps[-1], "kind": "doubtful", "note": "NOTE-BY-" + family}] if steps else []
            return json.dumps({"marks": marks})
        return flag

    def both_marked(_):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if any(f["hard"] for f in script.loop.comparison.auditor.feedback.findings.values()):
                return
            time.sleep(.01)

    script = Audit(tool_steps=3, live={"anthropic": make_flag("anthropic"), "openai": make_flag("openai")},
                   on_lookup=both_marked)
    loop = feedback_loop(store, script)
    list(loop.run())
    assert any(fb.FINDINGS_OPEN in str(m.get("content")) for m in loop.messages)
    finals = {family: messages for family, messages in script.prompts.items() if correction_request(messages) is None}
    for family in ("anthropic", "openai"):
        other = "NOTE-BY-" + ("anthropic" if family == "openai" else "openai")
        read = "\n".join(str(m["content"]) for messages in [*rounds[family], finals.get(family, [])]
                         for m in messages if m["role"] == "user")
        assert len(rounds[family]) >= 2 and other not in read, family
    # The admin's log keeps what the agent got.
    assert "NOTE-BY-" in json.dumps(log_entries(store, loop, "findings_delivered"))


def test_the_next_messages_reviewers_read_only_that_findings_were_passed_on():
    from app.services.agent_audit import review_entry
    context = fb.open_findings_context({"turn_id": "t", "total": 7, "findings": [
        {"on": "answer", "kind": "wrong", "reviewers": 2, "quote": "q", "note": "SECRET-NOTE", "source": RATES}]})
    question = "[consens.io context for this message]\nIt is Friday.\n" + context + "\n[end of app context]\n\nWhy?"
    entry = {"seq": 3, "actor": "agent", "kind": "context", "name": "conversation", "data": "user", "format": "json"}
    seen = json.dumps(review_entry(entry, json.dumps([{"role": "user", "content": question}])))
    assert "SECRET-NOTE" not in seen and "further open findings" not in seen
    assert "It is Friday." in seen and "Why?" in seen and fb.REDACTED_CONTEXT in seen
    live = fb.FINDINGS_OPEN + "\n" + json.dumps([{"kind": "wrong", "notes": [{"note": "SECRET-NOTE"}]}])
    entry = {"seq": 9, "actor": "agent", "kind": "context", "name": "conversation", "data": "app", "format": "text"}
    seen = json.dumps(review_entry(entry, live))
    assert "SECRET-NOTE" not in seen and fb.REDACTED_LIVE in seen
    app = {"seq": 10, "actor": "app", "kind": "app", "name": "findings_delivered", "format": "json"}
    seen = review_entry(app, json.dumps({"phase": "work", "findings": [
        {"id": "e4", "kind": "wrong", "reviewers": 2, "notes": [{"note": "SECRET-NOTE", "source": RATES}]}]}))
    assert seen["content"]["entries"] == [4]
    assert "SECRET-NOTE" not in json.dumps(seen) and RATES not in json.dumps(seen)
    # Text without findings is read as it always was.
    plain = {"seq": 2, "actor": "agent", "kind": "context", "name": "conversation", "format": "text"}
    assert review_entry(plain, "Hello")["content"] == "Hello"


# --- Only places that can be replaced safely ----------------------------------------

LIST = ("Intro paragraph with enough words here.\n\n"
        "- The first item says the tower is 330 metres tall.\n"
        "- The second item says it opened in 1889 for visitors.\n\n"
        "Closing sentence with enough words too.")


def _finding_on(answer, *words):
    spans = fb.sentence_spans(answer)
    numbers = [i for i, (start, end) in enumerate(spans, 1) if any(w in answer[start:end] for w in words)]
    assert numbers, words
    return {"id": "s1", "sentences": numbers}


@pytest.mark.parametrize("answer, words", [
    (LIST, ("330 metres", "opened in 1889")),
    ("| Year | Height |\n|---|---|\n| 1889 | The tower was 300 metres tall. |", ("300 metres",)),
    ("Text **bold starts here. It ends** after it.", ("bold starts",)),
    ("Word " * 400 + "end.", ("end.",)),
], ids=["two-list-items", "table-row", "open-bold", "too-long"])
def test_a_place_that_is_not_one_plain_line_keeps_its_mark(answer, words):
    assert fb.correction_items(answer, [_finding_on(answer, *words)]) == {}


def test_a_list_item_alone_can_be_corrected_and_the_list_stands():
    items = fb.correction_items(LIST, [_finding_on(LIST, "330 metres")])
    [(start, end, before)] = items.values()
    assert "\n" not in before and "330 metres" in before
    results = fb.read_corrections(json.dumps({"findings": [
        {"id": "s1", "sentence": before.replace("tall.", "tall with its antennas.")}]}), items)
    fixed = fb.corrected_answer(LIST, items, results)
    assert fixed.count("\n- ") == 2 and "with its antennas." in fixed and fixed.endswith("enough words too.")
    # The agent gets the sentence exactly as it stands.
    message = fb.correction_message([{"id": "s1", "kind": "wrong", "voices": {"A"}, "notes": []}], items)
    assert json.dumps(before)[1:-1] in message


@pytest.mark.parametrize("after", [
    "costs 36.10",
    "Tickets to the top cost 36.10 euros, see [rates](https://example.org/rates).",
    "Tickets to the top cost **36.10 euros.",
    "Tickets to the top cost 36.10 euros\nand more.",
    "Tickets to the top cost 36.10 euros as of 2026 and the lift",
], ids=["fragment", "new-link", "open-bold", "new-line", "no-sentence"])
def test_a_reply_that_is_no_safe_sentence_changes_nothing(after):
    items = {"s1": (0, 33, "Tickets to the top cost 14 euros.")}
    assert fb.read_corrections(json.dumps({"findings": [{"id": "s1", "sentence": after}]}), items) == {}


def test_a_sentence_keeps_its_link_and_its_picture():
    before = "The [official site](https://www.toureiffel.paris/en) counts 7 million visitors picture:p1."
    items = {"s1": (0, len(before), before)}
    kept = before.replace("7 million", "6.3 million")
    assert fb.read_corrections(json.dumps({"findings": [{"id": "s1", "sentence": kept}]}), items)["s1"][0] \
        == "corrected"
    for broken in (kept.replace("(https://www.toureiffel.paris/en)", ""), kept.replace(" picture:p1", "")):
        assert fb.read_corrections(json.dumps({"findings": [{"id": "s1", "sentence": broken}]}), items) == {}


# --- State: clean on every path --------------------------------------------------

def test_a_kept_correction_marks_turn_and_chat_with_one_revision(store):
    loop = feedback_loop(store, Audit(live={"anthropic": agent_side(fix_tickets)}))
    list(loop.run())
    raw, chat = raw_turn(store, loop), store._chat_ref(UID, loop.chat_id).get().to_dict()
    assert FIXED in raw["assistant_response"]
    assert chat["agent_answer_corrected"] == f"{loop.turn_id}:{raw['agent_answer_revision']}"
    assert "agent_correcting" not in raw


@pytest.mark.parametrize("path", ["stop", "newer", "disputed"])
def test_no_path_leaves_a_mark_on_the_turn_for_later_messages(store, monkeypatch, path):
    from app.services.llm.provider_runtime import ProviderCancelled
    if path == "newer":
        begin = type(store).begin_correction

        def newer_meanwhile(self, uid, chat_id, turn_id, **kwargs):
            started = begin(self, uid, chat_id, turn_id, **kwargs)
            self._chat_ref(uid, chat_id).update({"agent_turn_id": "newer"})
            return started
        monkeypatch.setattr(type(store), "begin_correction", newer_meanwhile)

    def reply(findings):
        if path == "stop":
            script.loop.cancellation.cancel()
            raise ProviderCancelled("stopped")
        if path == "disputed":
            return json.dumps({"findings": [{"id": f["id"], "stands": "It holds."} for f in findings]})
        return fix_tickets(findings)
    script = Audit(live={"anthropic": agent_side(reply)})
    loop = feedback_loop(store, script)
    try:
        list(loop.run())
    except ProviderCancelled:
        pass
    raw = raw_turn(store, loop)
    assert "agent_correcting" not in raw and "agent_answer_revision" not in raw
    assert raw["assistant_response"] == ANSWER
    feedback = raw["agent_review"]["audit"]["feedback"]
    assert feedback["status"] == "done" and not any(f["state"] == "checking" for f in feedback["findings"])


def test_a_failure_after_the_answer_was_rewritten_puts_it_back(store, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("placement broke")
    monkeypatch.setattr(fb, "corrected_out", boom)
    loop = feedback_loop(store, Audit(live={"anthropic": agent_side(fix_tickets)}))
    list(loop.run())
    raw = raw_turn(store, loop)
    review = raw["agent_review"]
    assert raw["status"] == "completed" and raw["assistant_response"] == ANSWER and loop.completion.text == ANSWER
    assert len(review["versions"]) == 1 and review["answer_hash"] == review["versions"][0]["hash"]
    feedback = review["audit"]["feedback"]
    assert feedback["status"] == "done" and feedback["skipped"] == "failed"
    assert {f["state"] for f in feedback["findings"] if f["on"] == "answer"} == {"open"}
    assert _marks_kept(review)


def test_without_its_hand_over_the_chat_never_waits_for_a_pass(store, monkeypatch):
    monkeypatch.setattr(type(store), "hand_over", lambda self, *a, **k: False)
    asked = []
    loop = feedback_loop(store, Audit(live={"anthropic": agent_side(lambda f: asked.append(f) or "{}")}))
    list(loop.run())
    assert asked == []
    assert raw_turn(store, loop)["agent_review"]["audit"]["feedback"]["skipped"] == "busy"


# --- The real request: its time, its admission, its minimum ---------------------

def test_a_pass_past_its_time_ends_quietly(store, monkeypatch):
    from app.services.agent_audit import CORRECTION_STOPPED
    from app.services.llm.provider_runtime import ProviderCancelled, current_provider_cancellation
    monkeypatch.setattr(fb, "CORRECTION_SECONDS", .3)

    def slow(findings):
        stop = current_provider_cancellation()
        while not stop.cancelled:
            time.sleep(.01)
        raise ProviderCancelled("overtime")
    loop = feedback_loop(store, Audit(live={"anthropic": agent_side(slow)}))
    list(loop.run())
    raw = raw_turn(store, loop)
    assert raw["status"] == "completed" and raw["assistant_response"] == ANSWER
    review = raw["agent_review"]
    assert review["audit"]["feedback"]["skipped"] == "no_time" and _marks_kept(review)
    view = store.delegation_view(UID, loop.chat_id, loop.turn_id)
    session = next(a for a in view["agents"] if a.get("kind") == "correction")
    assert session["status"] == "stopped" and (session.get("failure") or {}).get("code") == "no_time"
    assert CORRECTION_STOPPED not in json.dumps(view)


def test_a_pass_the_allowance_refuses_ends_quietly(store, monkeypatch):
    from app.services.agent_quota import AgentTokenBudgetExceeded
    claim = type(store).claim

    def refuse_the_pass(self, uid, chat_id, turn_id, model, *, step="completion:0", **kwargs):
        if step.startswith("agent:") and getattr(loop.comparison.auditor.feedback, "status", "") == "checking":
            raise AgentTokenBudgetExceeded(0, 100)
        return claim(self, uid, chat_id, turn_id, model, step=step, **kwargs)
    monkeypatch.setattr(type(store), "claim", refuse_the_pass)
    asked = []
    loop = feedback_loop(store, Audit(live={"anthropic": agent_side(lambda f: asked.append(f) or "{}")}))
    list(loop.run())
    raw = raw_turn(store, loop)
    assert asked == [] and raw["status"] == "completed" and raw["assistant_response"] == ANSWER
    assert raw["agent_review"]["audit"]["feedback"]["skipped"] == "allowance" and _marks_kept(raw["agent_review"])


def test_no_pass_starts_without_the_time_for_it(store, monkeypatch):
    asked = []
    loop = feedback_loop(store, Audit(live={"anthropic": agent_side(lambda f: asked.append(f) or "{}")}))
    original = type(loop)._hard_stop_left

    def little_left(self):
        if self.comparison.finalized:
            return fb.CORRECTION_MIN_SECONDS - 1
        return original(self)
    monkeypatch.setattr(type(loop), "_hard_stop_left", little_left)
    list(loop.run())
    assert asked == []
    assert raw_turn(store, loop)["agent_review"]["audit"]["feedback"]["skipped"] == "no_time"


def test_the_pass_reads_the_runs_files_where_its_steps_had_them(store):
    """The request continues the agent's conversation: the message's files sit
    where the agent's steps had them, so the prompt cache holds."""
    loop = feedback_loop(store, Audit(live={"anthropic": agent_side(fix_tickets)}))
    seen = {}

    class Files:
        def selection(self):
            return ["f1"]

        def messages(self, messages, model, *, file_ids, query, anchor):
            if correction_request(messages) is not None:
                seen.setdefault("anchors", []).append((file_ids, anchor))
            return messages
    loop.file_context = Files()
    list(loop.run())
    assert seen["anchors"] == [(["f1"], loop.turn_start)]


# --- Bounded -------------------------------------------------------------------

def test_the_register_stays_within_its_bounds():
    register = fb.Findings()
    for round_ in range(30):
        for reviewer in ("A", "B", "C"):
            register.live(reviewer, [{"entry": entry, "kind": "doubtful", "note": f"note {round_} {entry}"}
                                     for entry in range(round_ * 5, round_ * 5 + 5) if entry])
            register.live(reviewer, [{"entry": 1, "kind": "doubtful", "note": f"again {round_}"}])
    assert len(register.findings) <= fb.MAX_FINDINGS
    assert all(len(f["notes"]) <= fb.NOTES_PER_FINDING for f in register.findings.values())
    # The soft findings about the work stay in the marks on the work.
    soft = fb.Findings()
    soft.live("A", [{"entry": 3, "kind": "doubtful", "note": "Maybe."}])
    assert soft.snapshot()["findings"] == []


def test_the_storage_budget_shortens_the_trace_too():
    from app.services.agent_audit import TRIMMED_NOTE_CHARS, trim_marks
    audit = {"claims": [], "feedback": {"findings": [{"id": "s1", "reason": "r" * 900,
                                                      "notes": [{"note": "n" * 900}]}]}}
    trim_marks(audit)
    finding = audit["feedback"]["findings"][0]
    assert len(finding["notes"][0]["note"]) <= TRIMMED_NOTE_CHARS and len(finding["reason"]) <= TRIMMED_NOTE_CHARS


def test_off_the_agent_reads_the_setting_as_it_is(store):
    """read_settings names the setting in both states (its text is the one
    change off brings), and says truthfully that it is off in this message."""
    from app.services.agent_settings import ELSEWHERE, SettingsTools
    loop = feedback_loop(store, Audit(), findings=False)
    about = SettingsTools(loop)._about()
    assert about["findings_to_agent"] == "off in this message"
    assert "Pass findings to the agent: Off (the default) or On" in about["reviewers"]
    assert "whether their findings reach you" in ELSEWHERE
    on = feedback_loop(store, Audit(), findings=True)
    assert SettingsTools(on)._about()["findings_to_agent"] == "on in this message"


def test_a_watch_run_reads_the_setting_with_the_reviewers_in_one_read(store):
    from app.services import agent_watches
    store.db.collection("users").document(UID).collection("settings").document("app").set(
        {"values": {"reviewers": "always", "findings_to_agent": True}, "revision": 1,
         "field_revisions": {"reviewers": 1, "findings_to_agent": 1}})
    assert agent_watches._review_settings(UID, store.db) == ("always", True)
    assert agent_watches._reviewers(UID, store.db) == "always"


# --- What real models replied (live probe 2026-11-13, GPT-6.1 Terra and Claude Opus 5.5) -----------

DESTATIS = "https://www.destatis.de/DE/Themen/Gesellschaft-Umwelt/Bevoelkerung/Bevoelkerungsstand/_inhalt.html"
PRESS = "https://www.destatis.de/DE/Presse/Pressemitteilungen/2025/06/PD25_208_124.html"
POPULATION = (f"Laut [Statistischem Bundesamt]({DESTATIS}) lebten Ende 2024 **rund 85 Millionen Menschen** "
              "in Deutschland.")


def test_a_link_may_point_to_the_source_the_reviewer_named_instead():
    """Both models corrected the figure and linked the reviewer's source:
    a good correction the app turned down while links had to stay as they were."""
    items = {"s1": (0, len(POPULATION), POPULATION)}
    after = POPULATION.replace(DESTATIS, PRESS).replace("85 Millionen", "83,6 Millionen")
    reply = json.dumps({"findings": [{"id": "s1", "sentence": after}]})
    assert fb.read_corrections(reply, items) == {}
    assert fb.read_corrections(reply, items, {"s1": {PRESS}}) == {"s1": ("corrected", after)}
    assert fb.new_links({"s1": ("corrected", after)}, items) == {"s1": [PRESS]}
    # Any other address, or a link less, still leaves the sentence as it was.
    other = after.replace(PRESS, "https://example.org/population")
    assert fb.read_corrections(json.dumps({"findings": [{"id": "s1", "sentence": other}]}), items,
                               {"s1": {PRESS}}) == {}
    dropped = "Ende 2024 lebten **rund 83,6 Millionen Menschen** in Deutschland."
    assert fb.read_corrections(json.dumps({"findings": [{"id": "s1", "sentence": dropped}]}), items,
                               {"s1": {PRESS}}) == {}


def test_a_correction_takes_at_most_one_sentence_more():
    before = "Die Abgabefrist für die Steuererklärung 2025 ist der 31. Juli 2026."
    items = {"s1": (0, len(before), before)}
    opus = ("Wer die Erklärung selbst erstellt, musste sie bis zum 31. Juli 2026 abgeben, und diese Frist ist bereits "
            "abgelaufen. Wer einen Steuerberater oder Lohnsteuerhilfeverein beauftragt, hat länger Zeit: regulär bis "
            "Ende Februar 2027. Da der 28. Februar 2027 ein Sonntag ist, verschiebt sich die Frist auf Montag, den "
            "1. März 2027.")
    assert fb.read_corrections(json.dumps({"findings": [{"id": "s1", "sentence": opus}]}), items) == {}
    two = ("Die Abgabefrist für die Steuererklärung 2025 ist der 31. Juli 2026. Mit Steuerberater gilt sie bis "
           "zum 1. März 2027.")
    assert fb.read_corrections(json.dumps({"findings": [{"id": "s1", "sentence": two}]}), items)["s1"][0] == "corrected"
    # Figures with points are no sentence ends.
    everest = "Er ist 8.611 Meter hoch und liegt auf der Grenze zwischen Nepal und China."
    fixed = ("Er ist 8.849 Meter hoch (gemeinsame Vermessung von China und Nepal 2020) und liegt auf der Grenze "
             "zwischen Nepal und China.")
    assert fb.read_corrections(json.dumps({"findings": [{"id": "s1", "sentence": fixed}]}),
                               {"s1": (0, len(everest), everest)})["s1"][0] == "corrected"


def test_a_reviewers_source_that_leads_nowhere_keeps_the_sentence(store, monkeypatch):
    from app.services import agent_answer_links

    async def gone(url, **kwargs):
        return 404 if url == PRESS else None

    async def public(url):
        return "127.0.0.1" not in url
    monkeypatch.setattr(agent_answer_links, "link_gone", gone)
    monkeypatch.setattr(fb, "_public", public)
    assert not fb.links_found([PRESS])
    assert fb.links_found(["https://www.destatis.de/DE/Home/_inhalt.html"])
    # An address the check never opens (not public) is no link to add.
    assert not fb.links_found(["http://127.0.0.1:8000/page"])


def test_the_pass_takes_the_reviewers_source_where_its_page_exists(store, monkeypatch):
    from app.services import agent_answer_links
    from app.services.llm.provider_runtime import ProviderCancelled  # noqa: F401
    answer = ("Deutschland ist das bevölkerungsreichste Land der EU. " + POPULATION
              + " Das Wachstum der letzten Jahre geht fast nur auf Zuwanderung zurück.")
    reviews = {"anthropic": json.dumps({"marks": [{"quote": "lebten Ende 2024 rund 85 Millionen Menschen",
                                                   "kind": "wrong", "note": "Laut Destatis 83,6 Millionen.",
                                                   "source": PRESS}]}),
               "openai": json.dumps({"marks": []})}
    after = POPULATION.replace(DESTATIS, PRESS).replace("85 Millionen", "83,6 Millionen")

    def correct(findings):
        return json.dumps({"findings": [{"id": f["id"], "sentence": after} for f in findings]})

    async def public(url):
        return True
    monkeypatch.setattr(fb, "_public", public)
    for status, kept in ((None, True), (404, False)):
        async def gone(url, **kwargs):
            return status
        monkeypatch.setattr(agent_answer_links, "link_gone", gone)
        loop = feedback_loop(store, Audit(reviews, answer=answer, live={"anthropic": agent_side(correct)}))
        list(loop.run())
        assert (after in raw_turn(store, loop)["assistant_response"]) is kept, status


def test_the_pass_goes_to_the_agents_endpoint_with_its_reasoning(store):
    """The agent's earlier steps leave reasoning that only the endpoint that
    wrote it can read (OpenRouter's HTTP 400 reasoning_pinned): Prod's first
    pass on Muse Ember, on a session of its own, was refused. The pass
    continues the agent's conversation on the agent's session, its tool step
    and the reasoning replayed as they were."""
    seen = {}
    script = Audit(tool_steps=1, live={"anthropic": agent_side(fix_tickets)})
    factory = script.factory

    def recording():
        value = factory()
        stream = value.stream

        def wrapped(*, model, messages, **kwargs):
            if correction_request(messages) is not None:
                seen.update(session=kwargs.get("session_id"), history_end=value.history_end, messages=messages,
                            tools=[tool["function"]["name"] for tool in kwargs.get("tools") or []
                                   if tool.get("type") == "function"],
                            allow=kwargs.get("allow_tool_calls"))
            return stream(model=model, messages=messages, **kwargs)
        value.stream = wrapped
        return value
    script.factory = recording
    loop = feedback_loop(store, script)
    loop.factory = recording
    list(loop.run())
    assert seen["session"] == loop.provider_session and seen["history_end"] == loop.history_end
    # The agent's tool step stands in the request as the agent sent it, its tools listed and not callable.
    assert any(m.get("role") == "assistant" and m.get("tool_calls") for m in seen["messages"])
    assert any(m.get("role") == "tool" for m in seen["messages"])
    assert "lookup" in seen["tools"] and seen["allow"] is False
    # The reviewers' own sessions are theirs.
    assert FIXED in raw_turn(store, loop)["assistant_response"]


def test_a_refused_pass_logs_why_without_any_text(store, caplog):
    from app.services.llm.engines import _ProviderHTTPStatusError

    def refused(findings):
        raise _ProviderHTTPStatusError(400, diagnostic="provider=Google reason=reasoning_pinned")
    loop = feedback_loop(store, Audit(live={"anthropic": agent_side(refused)}))
    with caplog.at_level("WARNING"):
        list(loop.run())
    assert "diagnostic=provider=Google reason=reasoning_pinned" in caplog.text
    review = raw_turn(store, loop)["agent_review"]
    assert review["audit"]["feedback"]["skipped"] == "failed" and _marks_kept(review)
