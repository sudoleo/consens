"""scripts/agent_speed.py: the tempo of Agent turns from receipts and activity, offline."""
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

from scripts.agent_speed import (aggregate, collect, fetch_generations, generation_stats, percentile, public,
                                 summary_table, timeline, tool_calls, turn_table)

T0 = datetime(2026, 11, 5, 12, 40, tzinfo=timezone.utc)


def at(s):
    return T0 + timedelta(seconds=s)


def receipt(step, start, ttft, end, *, model="openai/gpt-6.1-terra", searches=0, generation=None, turn="t" * 20):
    return {"purpose": "agent", "step": step, "chat_id": "c" * 20, "turn_id": turn, "model": {"model": model},
            "created_at": at(start - .05), "request_started_at": at(start), "first_token_at": at(start + ttft),
            "stream_ended_at": at(end), "settled_at": at(end + .1), "generation_id": generation,
            "usage": {"input_tokens": 1000, "cached_input_tokens": 500, "output_tokens": 80, "reasoning_tokens": 20,
                      "web_search_requests": searches}}


def tool(step, call, name, ms=None, **extra):
    entry = {"id": f"completion:{step}:{call}/tool", "step_id": f"completion:{step}:{call}", "kind": "tool",
             "name": name, "status": "succeeded", **extra}
    if ms is not None:
        entry["duration_ms"] = ms
    return entry


# A turn of three chat steps: the first searches twice, then a measured
# vm_exec, then a write without its own duration; a reviewer's call beside.
RECEIPTS = [
    receipt("completion:0", .2, 2, 10.2, searches=2, generation="gen-0"),
    receipt("completion:1", 11.0, 1.5, 14.0, generation="gen-1"),
    receipt("completion:2", 15.5, 3, 18.0),
    {**receipt("agent:" + "a" * 32 + ":0", 18.5, 1, 20), "model": {"model": "openai/gpt-6-luna"}},
]
ACTIVITY = [
    {"id": "started", "step_id": "completion:0", "kind": "status"},
    tool(0, "web_search", "web_search", count=2, server_tool=True),
    tool(0, "call_a", "vm_exec", 600, command="cat secret.txt", output="private output"),
    tool(1, "call_b", "vm_write_file", path="/home/secret-name.txt"),
    tool(2, "server_audit_answer", "audit_answer"),
]
TURN = {"created_at": T0, "completed_at": at(25), "agent_answer_fixed_at": at(18.4), "status": "completed",
        "agent_activity": ACTIVITY}


def test_tools_per_step_leave_out_searches_inside_the_request():
    calls = tool_calls(ACTIVITY)
    assert calls == {0: [{"name": "vm_exec", "ms": 600}], 1: [{"name": "vm_write_file", "ms": None}],
                     2: [{"name": "audit_answer", "ms": None}]}
    # An entry merged later without its duration keeps the measured one.
    again = tool_calls([tool(3, "x", "browser", 2500), tool(3, "x", "browser")])
    assert again == {3: [{"name": "browser", "ms": 2500}]}
    assert tool_calls(None) == {} and tool_calls([{"kind": "tool", "id": "agent:a:0:x/tool"}]) == {}


def test_timeline_splits_each_gap_into_tools_and_rest():
    turn = timeline("mWKgPUxyz", "c" * 20, "t" * 20, RECEIPTS, TURN)
    first, second, third = turn["step_list"]
    assert (first["at"], first["duration"], first["ttft"], first["searches"]) == (0.2, 10.0, 2.0, 2)
    assert (first["input"], first["cached"], first["output"], first["reasoning"]) == (1000, 500, 80, 20)
    assert round(first["gap"], 3) == .8 and first["tool_s"] == .6 and round(first["rest"], 3) == .2
    assert first["unmeasured"] == 0
    # The write measures no duration: its time stays in the rest.
    assert second["gap"] == 1.5 and second["tool_s"] == 0 and second["rest"] == 1.5 and second["unmeasured"] == 1
    # After the last step there is no gap (the review runs after the answer).
    assert third["gap"] is None and third["tools"] == ["audit_answer"]
    assert (turn["account"], turn["own"], turn["chat"], turn["turn"]) == ("mWKgPU", True, "cccccc", "tttttt")
    assert turn["total"] == 25 and round(turn["answer"], 3) == 18.4 and turn["span"] == 17.8
    assert turn["pre"] == .2 and round(turn["post"], 3) == .4 and round(turn["after_answer"], 3) == 6.6
    assert (turn["steps"], turn["searches"], turn["worker_calls"]) == (3, 2, 1)
    assert (turn["search_s"], turn["other_s"]) == (10.0, 5.5)
    assert round(turn["tool_s"], 3) == .6 and round(turn["rest_s"], 3) == 1.7
    assert turn["models"] == ["openai/gpt-6.1-terra"] and turn["started"] == "2026-11-05 13:40:00"


def test_without_a_turn_document_only_the_receipts_count():
    turn = timeline("guest", "c" * 20, "t" * 20, RECEIPTS[:2], None)
    assert turn["document"] is False and turn["total"] is None and turn["pre"] is None and turn["post"] is None
    # Counted from the first request; no activity, so no tools in the gap.
    assert turn["step_list"][0]["at"] == 0 and turn["span"] == 13.8
    assert turn["step_list"][0]["rest"] == turn["step_list"][0]["gap"]
    # Receipts from before 2026-10-30 lack the request times.
    old = {**RECEIPTS[0]}
    for field in ("request_started_at", "first_token_at", "stream_ended_at"):
        old.pop(field)
    step = timeline("guest", "c", "t", [old], None)["step_list"][0]
    assert step["duration"] is None and step["ttft"] is None and step["at"] is None


def test_percentiles_interpolate_between_ranks():
    assert percentile([], .5) is None
    assert percentile([3, None, 1, 2], .5) == 2
    assert percentile([1, 2, 3, 4], .5) == 2.5
    assert round(percentile(list(range(1, 11)), .9), 3) == 9.1


def test_aggregate_over_turns():
    one = timeline("mWKgPUxyz", "c" * 20, "t" * 20, RECEIPTS, TURN)
    other = timeline("guest", "d" * 20, "u" * 20, [
        receipt("completion:0", 0, 4, 20, model="deepseek/deepseek-v4.1-flash-1017", searches=4, turn="u" * 20),
        receipt("completion:1", 21, 1, 23, model="deepseek/deepseek-v4.1-flash-1017", turn="u" * 20)],
        {"created_at": at(-.5), "completed_at": at(24), "agent_activity": [tool(0, "call_c", "vm_exec", 400)]})
    agg = aggregate([one, other])
    assert (agg["turns"], agg["with_document"], agg["steps"]) == (2, 2, 5)
    assert agg["steps_per_turn"]["p50"] == 2.5 and agg["searches_per_turn"]["sum"] == 6
    assert agg["ttft_by_model"]["openai/gpt-6.1-terra"]["n"] == 3
    assert agg["seconds_per_search_by_model"]["deepseek/deepseek-v4.1-flash-1017"] == {
        "n": 1, "p50": 5.0, "p90": 5.0, "sum": 5.0, "searches": 4}
    # The gap after the unmeasured write is left out of the rest per gap.
    assert agg["rest_per_gap"]["n"] == 2 and agg["rest_per_gap"]["unmeasured_gaps"] == 1
    assert round(agg["rest_per_gap"]["p50"], 3) == .4
    assert set(agg["gaps_by_tool"]) == {"vm_exec", "vm_write_file"}
    assert agg["gaps_by_tool"]["vm_exec"]["n"] == 2 and agg["gaps_by_tool"]["vm_write_file"]["rest_p50"] is None
    shares = agg["shares"]
    assert shares["search steps"]["s"] == 30.0 and round(shares["reviewers after the answer"]["s"], 3) == 6.6
    # The parts add up to the summed time of both turns (created to completed).
    assert round(sum(part["s"] for part in shares.values()), 6) == 25 + 24.5
    assert round(sum(part["share"] for part in shares.values()), 6) == 1
    assert aggregate([])["shares"]["tools"]["share"] is None


def test_openrouter_generation_in_seconds_and_lookup_failures_tolerated():
    data = {"provider_name": "Azure", "latency": 1990, "generation_time": 11800,
            "created_at": "2026-11-05T12:40:00.300Z"}
    assert generation_stats(data, at(.2)) == {"provider": "Azure", "latency": 1.99, "generation": 11.8,
                                              "connection": .1}
    assert generation_stats({}, at(0)) == {"provider": None, "latency": None, "generation": None,
                                           "connection": None}
    turn = timeline("guest", "c" * 20, "t" * 20, RECEIPTS, TURN)
    asked = []

    class Client:
        def get(self, url, *, params, headers):
            asked.append((url, params["id"], headers["Authorization"]))
            if params["id"] == "gen-1":
                raise TimeoutError
            return SimpleNamespace(status_code=200, json=lambda: {"data": data})

    assert fetch_generations([turn], "sk-test", client=Client(), pause=0) == 2
    assert asked == [("https://openrouter.ai/api/v1/generation", "gen-0", "Bearer sk-test"),
                     ("https://openrouter.ai/api/v1/generation", "gen-1", "Bearer sk-test")]
    steps = turn["step_list"]
    assert steps[0]["openrouter"]["provider"] == "Azure" and steps[1]["openrouter"] == {"error": "TimeoutError"}
    assert "openrouter" not in steps[2]
    assert "Azure" in turn_table(turn, openrouter=True) and "lookup failed: TimeoutError" in turn_table(
        turn, openrouter=True)
    agg = aggregate([turn])
    assert agg["openrouter_by_provider"]["openai/gpt-6.1-terra @ Azure"]["latency"]["p50"] == 1.99


def test_output_holds_numbers_and_tool_names_never_content_or_full_ids():
    turn = timeline("mWKgPUxyz", "c" * 20, "t" * 20, RECEIPTS, TURN)
    text = "\n".join([turn_table(turn), summary_table([turn]), json.dumps(public(turn), default=str)])
    for secret in ("secret", "private output", "gen-0", "c" * 7, "t" * 7, "mWKgPUx"):
        assert secret not in text
    assert "vm_exec" in text and "vm_write_file?" in text
    assert all(not key.startswith("_") for step in public(turn)["step_list"] for key in step)


class Query:
    def __init__(self, docs):
        self.docs = docs

    def where(self, *, filter):
        assert (filter.field_path, filter.op_string) == ("created_at", ">=")
        return Query([d for d in self.docs if d["created_at"] >= filter.value])

    def stream(self):
        return [SimpleNamespace(to_dict=lambda d=d: dict(d)) for d in self.docs]


class Ref:
    def __init__(self, data, path=()):
        self.data, self.path = data, path
        self.id = path[-1] if path else ""

    def collection(self, name):
        return Ref(self.data, self.path + (name,))

    def document(self, name):
        return Ref(self.data, self.path + (name,))

    def list_documents(self):
        return [Ref(self.data, self.path + (uid,)) for uid in self.data["users"]]

    def where(self, **kwargs):
        return Query(self.data["docs"].get(self.path, [])).where(**kwargs)

    def get(self, *, field_paths):
        self.data["read_fields"] = field_paths
        doc = self.data["docs"].get(self.path)
        return SimpleNamespace(exists=doc is not None, to_dict=lambda: dict(doc or {}))


def test_collect_reads_recent_chat_turns_and_tolerates_missing_turn_documents():
    old = {**receipt("completion:0", 0, 1, 2, turn="old"), "created_at": T0 - timedelta(days=30)}
    data = {"users": ["mWKgPUown", "guest"], "docs": {
        ("users", "mWKgPUown", "llm_calls"): [receipt("completion:0", 0, 1, 2, turn="own")],
        ("users", "guest", "llm_calls"): [
            receipt("completion:0", 0, 1, 2, turn="kept"), receipt("completion:1", 3, 1, 4, turn="kept"),
            receipt("completion:0", 0, 1, 2, turn="gone", model="deepseek/deepseek-v4.1-flash-1017"),
            # Only a worker's call: no chat step, no turn.
            receipt("agent:" + "a" * 32 + ":0", 0, 1, 2, turn="worker"),
            {**receipt("completion:0", 0, 1, 2, turn="consensus"), "purpose": "consensus"}, old],
        ("users", "guest", "chats", "c" * 20, "turns", "kept"): TURN,
    }}
    since = T0 - timedelta(days=2)
    found = {item[2]: item for item in collect(Ref(data), since, workers=2)}
    assert set(found) == {"own", "kept", "gone"}
    assert len(found["kept"][3]) == 2 and found["kept"][4]["status"] == "completed" and found["gone"][4] is None
    # Only the times, status and activity of the turn, never its answer.
    assert data["read_fields"] == ["created_at", "completed_at", "agent_answer_fixed_at", "status", "agent_activity"]
    assert {item[2] for item in collect(Ref(data), since, exclude_own=True, workers=2)} == {"kept", "gone"}
    assert {item[2] for item in collect(Ref(data), since, model="deepseek", workers=2)} == {"gone"}
    assert {item[2] for item in collect(Ref(data), since, turn_prefix="ke", workers=2)} == {"kept"}
