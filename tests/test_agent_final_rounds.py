"""The reviewers' final rounds by model and endpoint (agent_final_rounds):
which endpoints count as slow, what the hedge time rests on, and what is
kept across deploys."""
import pytest

from app.services import agent_audit, agent_final_rounds as rounds

NOW = 1_800_000_000.


@pytest.fixture(autouse=True)
def empty(monkeypatch):
    monkeypatch.setattr(rounds, "_rounds", {})


def record(model, endpoint, *seconds, at=NOW):
    for value in seconds:
        rounds.record(model, value, endpoint, now=at)


def test_an_endpoint_far_behind_the_models_fastest_is_slow():
    record("deepseek", "Together", 6, 8, 9, 8, 24)
    record("deepseek", "Fireworks", 21, 29, 33)
    record("deepseek", "Parasail", 23, 60, 89)
    assert rounds.slow_endpoints("deepseek", now=NOW) == ("Parasail", "Fireworks")
    # Another model's rounds say nothing about this one.
    assert rounds.slow_endpoints("haiku", now=NOW) == ()


def test_an_endpoint_a_little_slower_or_barely_seen_is_not():
    record("haiku", "Claude Platform on AWS", 6, 7, 7, 8)
    record("haiku", "Google", 8, 9, 9, 17)
    # Twice as slow, in two rounds only: too few to tell an endpoint from two long answers.
    record("haiku", "Azure", 14, 15)
    assert rounds.slow_endpoints("haiku", now=NOW) == ()
    record("haiku", "Azure", 13)
    assert rounds.slow_endpoints("haiku", now=NOW) == ("Azure",)


def test_fast_rounds_far_apart_in_factor_but_not_in_seconds_condemn_no_endpoint():
    record("lite", "A", 1, 1, 1)
    record("lite", "B", 3, 3, 3)
    assert rounds.slow_endpoints("lite", now=NOW) == ()


def test_one_endpoint_alone_is_never_slow_and_rounds_without_an_endpoint_do_not_count():
    record("luna", "Amazon Bedrock", 30, 40, 50)
    record("luna", "", 2, 2, 2)
    assert rounds.slow_endpoints("luna", now=NOW) == ()


def test_at_most_three_endpoints_are_avoided_the_slowest_first():
    record("m", "fast", 5, 5, 5)
    for index, name in enumerate(("b", "c", "d", "e")):
        record("m", name, *[20 + 10 * index] * 3)
    assert rounds.slow_endpoints("m", now=NOW) == ("e", "d", "c")


def test_old_rounds_run_out_so_an_avoided_endpoint_gets_its_next_chance():
    record("m", "fast", 5, 5, 5, at=NOW)
    record("m", "slow", 30, 30, 30, at=NOW - rounds.MAX_AGE_SECONDS + 60)
    assert rounds.slow_endpoints("m", now=NOW) == ("slow",)
    assert rounds.slow_endpoints("m", now=NOW + 120) == ()
    assert [seconds for _, seconds, _ in rounds.rounds("m", now=NOW + 120)] == [5, 5, 5]


def test_the_hedge_time_leaves_out_rounds_on_endpoints_the_reviewer_avoids(monkeypatch):
    monkeypatch.setattr(rounds.time, "time", lambda: NOW)
    record("deepseek", "Together", 6, 7, 8, 8, 9, 9, 10, 13, 14, 20)
    assert agent_audit.final_hedge_seconds("deepseek") == 14
    record("deepseek", "Parasail", 60, 70, 89)
    # Their rounds run elsewhere now: 89 s says nothing about the next one.
    assert rounds.slow_endpoints("deepseek") == ("Parasail",)
    assert agent_audit.final_hedge_seconds("deepseek") == 14


def test_saved_rounds_join_those_of_the_process_each_once():
    rounds.record("m", 9, "A", now=NOW)
    stored = rounds._stored({"models": [
        {"model": "m", "rounds": [{"at": NOW - 10, "s": 7.5, "e": "B"}, {"at": NOW, "s": 9.0, "e": "A"},
                                  {"at": "yesterday", "s": 3}, {"at": NOW, "s": True}, "junk"]},
        {"model": "old", "rounds": [{"at": NOW - rounds.MAX_AGE_SECONDS - 1, "s": 5, "e": "A"}]},
        {"rounds": [{"at": NOW, "s": 1}]}, "junk"]})
    rounds._merge(stored, now=NOW)
    assert rounds.rounds("m", now=NOW) == [(NOW - 10, 7.5, "B"), (NOW, 9.0, "A")]
    # A model whose rounds have all run out is dropped, so the document stays small.
    assert "old" not in rounds._rounds


def test_only_the_newest_rounds_of_a_model_are_kept():
    for index in range(rounds.ROUNDS + 5):
        rounds.record("m", index, "A", now=NOW + index)
    kept = rounds.rounds("m", now=NOW + rounds.ROUNDS + 5)
    assert len(kept) == rounds.ROUNDS and kept[0][1] == 5


class Document:
    def __init__(self, data=None):
        self.data, self.sets = data, []

    def get(self):
        document = self

        class Snapshot:
            exists = document.data is not None

            def to_dict(self):
                return document.data
        return Snapshot()

    def set(self, data):
        self.sets.append(data)
        self.data = data


def test_a_save_keeps_what_another_instance_saved_meanwhile(monkeypatch):
    monkeypatch.setattr(rounds.time, "time", lambda: NOW)
    document = Document({"models": [{"model": "m", "rounds": [{"at": NOW - 5, "s": 11, "e": "B"}]}]})
    monkeypatch.setattr(rounds, "_document", lambda: document)
    rounds.record("m", 8.123, "A")
    rounds._write()
    assert document.sets[0]["models"] == [{"model": "m", "rounds": [
        {"at": NOW - 5, "s": 11.0, "e": "B"}, {"at": NOW, "s": 8.12, "e": "A"}]}]
    # Read back by the next process.
    monkeypatch.setattr(rounds, "_rounds", {})
    rounds._read()
    assert [entry[2] for entry in rounds.rounds("m")] == ["B", "A"]


def test_a_failed_read_or_write_costs_nothing_and_tests_never_touch_the_database(monkeypatch):
    def broken():
        raise RuntimeError("no database")
    monkeypatch.setattr(rounds, "_document", broken)
    rounds.record("m", 8, "A", now=NOW)
    rounds._read()
    rounds._write()
    assert rounds.rounds("m", now=NOW) == [(NOW, 8.0, "A")]
    # UNIT_TEST_MODE: neither starts a thread.
    monkeypatch.setattr(rounds.threading, "Thread", lambda **kwargs: broken())
    rounds.load()
    rounds.save()
