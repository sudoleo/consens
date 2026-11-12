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
