"""The daily chat review's digest (scripts/daily_chat_review.py): what it
reads from a turn's work log and Watch fields, content-free."""
import json

from scripts.daily_chat_review import turn_tools, watch_summary


class Snapshot:
    def __init__(self, data):
        self.data = data

    def to_dict(self):
        return self.data


class TurnRef:
    def __init__(self, *chunks):
        self.chunks = chunks

    def collection(self, name):
        assert name == "work_log"
        return self

    def stream(self):
        return [Snapshot(chunk) for chunk in self.chunks]


def tool(name, result):
    return {"kind": "tool", "name": name, "content": json.dumps(result) if not isinstance(result, str) else result}


def test_tool_calls_name_the_refused_field_but_never_a_value():
    refusal = ("Invalid prepare_watch arguments - task: String should have at most 500 characters. "
               "Expected arguments: {task: string, goal?: string}")
    log = TurnRef(
        {"entries": [{"kind": "step", "content": "Daily bulletin for my portfolio"},
                     tool("web_search", {"error": "Invalid web_search arguments - depth: Extra inputs are not "
                                                  "permitted (allowed here: queries); since: bad. Expected arguments: "
                                                  "{queries: [string]}"}),
                     tool("web_search", {"searches": []})]},
        # An older log keeps one entry per document.
        tool("prepare_watch", {"error": refusal}),
        {"entries": [tool("prepare_watch", {"status": "prepared", "task": "Daily bulletin for my portfolio"}),
                     tool("read_source", {"error": "The page could not be read."}),
                     tool("read_source", '{"status": "completed", "untrusted_page_text": "cut off')]})
    digest = turn_tools(log)
    assert digest == {
        "tools": {"web_search": 2, "prepare_watch": 2, "read_source": 2},
        "refused_calls": {"web_search: depth, since": 1, "prepare_watch: task": 1},
        "tool_errors": {"read_source": 1},
    }
    assert "portfolio" not in json.dumps(digest) and "500" not in json.dumps(digest)


def test_a_turn_without_a_log_adds_nothing():
    assert turn_tools(TurnRef()) == {}


def test_the_watch_a_turn_proposed_and_whether_the_user_started_it():
    proposed = {"agent_watch": {"task": "Check prices daily.", "interval": "daily"}}
    assert watch_summary("t1", proposed, {"t1": "active"}) == {"proposed": "daily", "started": "active"}
    assert watch_summary("t2", proposed, {"t1": "active"}) == {"proposed": "daily", "started": "no"}
    assert watch_summary("t3", {"question": "Hi"}, {}) == {}


def test_a_scheduled_run_is_marked_even_when_it_found_nothing():
    quiet = {"agent_settings": {"watch_run": True}, "status": "completed"}
    assert watch_summary("r1", quiet, {}) == {"scheduled_run": "quiet"}
    found = {**quiet, "agent_watch_run": {"finding": {"summary": "In stock.", "needs_user": False}}}
    assert watch_summary("r2", found, {}) == {"scheduled_run": "finding"}


def at(second):
    from datetime import datetime, timedelta, timezone
    return datetime(2026, 11, 15, 8, 41, 53, tzinfo=timezone.utc) + timedelta(seconds=second)


def receipt(step, start, end, *, agent="", first=None, finish="stop", model="openai/gpt-6.1-terra", status="succeeded"):
    return {"step": step, "agent_id": agent, "created_at": at(start), "settled_at": at(end),
            "first_token_at": at(first) if first is not None else None, "finish_reason": finish,
            "model": {"model": model}, "status": status}


def test_the_flow_tells_the_wait_for_the_answer_from_the_research_after_the_comparison():
    from scripts.daily_chat_review import turn_flow
    agents = {"c1": {"kind": "comparison"}, "c2": {"kind": "comparison"}, "a1": {"kind": "audit"},
              "a2": {"kind": "audit"}}
    steps = [
        receipt("completion:0", 0, 5, first=4, finish="tool_calls"),
        receipt("agent:c1:0", 6, 80, agent="c1", model="moonshotai/kimi-k2.6"),
        receipt("agent:c2:0", 6, 40, agent="c2", model="x-ai/grok-4.3"),
        receipt("completion:1", 93, 100, first=99, finish="tool_calls"),
        receipt("completion:2", 172, 285, first=178),
        receipt("agent:a1:0", 6, 300, agent="a1", model="anthropic/claude-haiku-5.5"),
        receipt("agent:a2:0", 6, 336, agent="a2", model="moonshotai/kimi-k2.6"),
        receipt("agent:a2:1", 290, 400, agent="a2", model="moonshotai/kimi-k2.6", status="cancelled"),
    ]
    flow = turn_flow({"created_at": at(0), "completed_at": at(336)}, steps, agents)
    assert flow["chat_steps"] == 3
    assert flow["comparison_seconds"] == 74 and flow["slowest_model"] == "kimi-k2.6 74s"
    assert flow["after_comparison_seconds"] == 205
    assert flow["answer_started_seconds"] == 178 and flow["answer_seconds"] == 113
    # The check after the answer: the agent's reviewers, without a stopped hedge.
    assert flow["check_after_answer_seconds"] == 51
    assert flow["reviewer_calls"] == 2 and flow["reviewer_models"] == {"claude-haiku-5.5": 1, "kimi-k2.6": 1}
    assert "writer_seconds" not in flow


def test_a_direct_answer_has_its_wait_without_a_comparison():
    from scripts.daily_chat_review import turn_flow
    flow = turn_flow({"created_at": at(0), "completed_at": at(58)},
                     [receipt("completion:0", 0, 10, first=3, finish="tool_calls"), receipt("completion:1", 40, 55)], {})
    assert flow["answer_started_seconds"] == 40 and flow["answer_seconds"] == 15
    assert "comparison_seconds" not in flow and "after_comparison_seconds" not in flow


class Ledgers:
    """users/{uid}/chat_state/{doc} of a fake Firestore, read-only."""

    def __init__(self, docs):
        self.docs, self.path = docs, []

    def collection(self, name):
        self.path.append(name)
        return self

    def document(self, name):
        self.path.append(name)
        return self

    def get(self):
        path, self.path = self.path, []
        return Snapshot(self.docs.get(path[-1]))


def test_the_allowance_an_account_spent_on_each_day_of_the_window():
    from datetime import datetime, timezone
    from scripts.daily_chat_review import allowance_used, utc_days
    config = {"tier_limits": {"free": 1_000_000, "plus": 2_500_000, "pro": 5_000_000, "admin": 5_000_000},
              "reset_epoch": "e1"}
    db = Ledgers({"agent_tokens_2026-11-14_e1_eur": {"used": 250_000},
                  "agent_tokens_2026-11-15_e1_eur": {"used": 900_000, "estimated": 140_000, "pipeline_estimated": 0}})
    days = utc_days(datetime(2026, 11, 14, 7, 0, tzinfo=timezone.utc), datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc))
    assert days == ["2026-11-14", "2026-11-15", "2026-11-16"]
    assert allowance_used(db, "uid", days, config, "free") == [
        {"day": "2026-11-14", "tier": "free", "used_percent": 25},
        {"day": "2026-11-15", "tier": "free", "used_percent": 104},
    ]
    assert allowance_used(db, "uid", days, config, "plus")[1]["used_percent"] == 42
