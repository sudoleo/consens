"""Clock context reaches all user-facing model stages without a web lookup."""
from datetime import datetime, timezone

import pytest

from app.services import agent_runs
from app.services.llm import base, consensus_engine
from app.services.llm.agent_client import AgentModel, resolve_agent_model
from app.services.llm.engines import build_provider_payload
from test_agent_runs import UID, pending, receipt, store


@pytest.fixture
def clock(monkeypatch):
    class Clock(datetime):
        instant = datetime(2026, 9, 15, 21, 59, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz=None):
            return cls.instant.astimezone(tz) if tz else cls.instant.replace(tzinfo=None)

    monkeypatch.setattr(base, "datetime", Clock)
    return Clock


@pytest.mark.parametrize("instant,expected_date,expected_offset", [
    (datetime(2026, 9, 15, 22, 30, tzinfo=timezone.utc), "Wednesday, 2026-09-16", "+02:00"),
    (datetime(2026, 12, 31, 23, 30, tzinfo=timezone.utc), "Friday, 2027-01-01", "+01:00"),
])
def test_all_answer_stages_share_explicit_local_date_and_dst_offset(clock, instant, expected_date, expected_offset):
    clock.instant = instant
    synthesis = consensus_engine._build_consensus_prompt("What date is it?", {"openai": "An answer"}, [])
    differences = consensus_engine._build_differences_prompt({"openai": "An answer"}, "An answer", [])[0]
    provider = build_provider_payload("openai", question="What date is it?")["payload"]["messages"][0]["content"]
    for prompt in (agent_runs.get_agent_system_prompt(AgentModel()), provider, synthesis, differences):
        assert f"Current date: {expected_date}." in prompt
        assert "Reference time at request start: 00:30:00." in prompt
        assert f"Reference timezone: Europe/Berlin (UTC{expected_offset})." in prompt
        assert "timezone are unknown unless provided" in prompt
        assert prompt.count("Current date:") == 1


def test_agent_followup_refreshes_clock_and_model_without_rewriting_history(store, clock):
    model = AgentModel()
    chat_id, first = pending(store)
    first_messages = store.messages(UID, chat_id, first, model=model)
    assert "Tuesday, 2026-09-15" in first_messages[0]["content"]
    assert "Selected model for this response: DeepSeek V4.1 Flash" in first_messages[0]["content"]
    answer = receipt()
    answer.text = "Today is September 15."
    assert store.claim(UID, chat_id, first["id"], model)
    store.settle(UID, chat_id, first["id"], completion=answer, status="succeeded")

    # The process and chat stay open while Berlin crosses midnight; UTC has not.
    clock.instant = datetime(2026, 9, 15, 22, 1, tzinfo=timezone.utc)
    _, second = pending(store, chat_id=chat_id, request_id="two", question="And today?")
    messages = store.messages(UID, chat_id, second, model=resolve_agent_model("claude-haiku-4-5"))
    assert "Wednesday, 2026-09-16" in messages[0]["content"]
    assert "Reference time at request start: 00:01:00." in messages[0]["content"]
    assert "Selected model for this response: Claude Haiku 4.5 (anthropic/claude-haiku-4.5)." in messages[0]["content"]
    assert "DeepSeek" not in messages[0]["content"]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[2]["content"] == "Today is September 15."
    assert messages[3]["content"] == "And today?"
    # Consensus also builds fresh context rather than caching it at import time.
    assert "Wednesday, 2026-09-16" in base.get_system_prompt()
    assert "Wednesday, 2026-09-16" in consensus_engine._build_consensus_prompt("And today?", {"openai": "A"}, [])
