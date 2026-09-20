"""Failure paths that cross admission, transport, persistence and recovery."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from app.api.routers import agent
from app.services import agent_quota
from app.services.agent_provider_limits import AgentRunInterrupted
from app.services.agent_tools import ToolRegistry
from app.services.agent_comparison import comparison_selection
from app.core import config as cfg
from app.services.chat_store import TurnStatusConflict
from app.services.llm import agent_client, provider_runtime as runtime
from app.services.llm.agent_client import AgentCompletion, AgentModel
from test_agent_runs import UID, AUTH, api, store, pending, totals
from test_agent_continuation import chat_loop
from test_agent_comparison import Script, make_loop
from test_agent_admission import Completion, exhaust


def test_legacy_receipts_cannot_hide_recoverable_token_reservations(store):
    calls = store.db.collection('users').document(UID).collection('llm_calls')
    for index in range(25):
        calls.document(f'000-legacy-{index}').set({'run_status':'running', 'status':'succeeded', 'policy':{}})
    loop = chat_loop(store, Completion)
    store.claim(UID, loop.chat_id, loop.turn_id, loop.model, run_token=loop.run_token,
        policy=loop.policy.snapshot(), reservation=(500, 1))
    store.receipt_ref(UID, loop.chat_id, loop.turn_id).update({
        'lease_until':datetime.now(timezone.utc)-timedelta(seconds=1)})
    budget = agent_quota.snapshot(store.db, UID)
    assert budget['reserved'] == 0 and budget['unknown'] == 500
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)['status'] == 'failed'


def test_api_comparison_selection_uses_the_same_six_family_cap_as_the_picker():
    choices = {key: next(iter(provider.models)) for key, provider in cfg.PROVIDERS.items()}
    with pytest.raises(ValueError, match='between two and 6'):
        comparison_selection(choices)


def test_admission_cannot_wait_when_even_released_tokens_cannot_fit(store, monkeypatch):
    loop = chat_loop(store, Completion)
    ref = agent_quota.quota_ref(store.db, UID, agent_quota.day_key())
    ref.set({"used": 249800, "reserved": 100})
    monkeypatch.setattr(loop.condition, "wait", lambda *_: pytest.fail("Impossible admission must not wait"))
    with pytest.raises(agent_quota.AgentTokenBudgetExceeded):
        exhaust(loop._step(loop.model, loop.messages, "completion:0", ToolRegistry(), loop.cancellation, searches_enabled=False))
    assert ref.get().to_dict() == {"used": 249800, "reserved": 100}
    assert loop.costs.calls == 0


def test_stop_before_first_claim_fences_later_admission(store):
    loop = chat_loop(store, Completion)
    store.stop_delegation(UID, loop.chat_id, loop.turn_id)
    list_failed = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert list_failed["agent_failure"]["code"] == "cancelled"
    with pytest.raises(TurnStatusConflict, match="no longer runnable"):
        list(loop.run())
    assert not store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().exists
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_failure"]["code"] == "cancelled"


def test_agent_status_and_stop_cannot_fail_a_consensus_turn(store):
    chat = store.create_chat(UID)['id']
    turn = store.create_turn(UID, chat, question='Ordinary consensus', mode='Standard', deep_search=False,
        selected_models=['OpenAI'], consensus_model='OpenAI', client_request_id='consensus')['id']
    assert store.delegation_view(UID, chat, turn)['status'] == 'pending'
    store.stop_delegation(UID, chat, turn)
    assert store.get_turn(UID, chat, turn)['status'] == 'pending'


@pytest.mark.parametrize("superseded", [False, True])
def test_expired_pre_admission_recovers_without_unlocking_a_new_turn(store, superseded):
    chat, turn = pending(store)
    store._chat_ref(UID, chat).update({"agent_lock_until": datetime.now(timezone.utc) - timedelta(seconds=1)})
    if superseded:
        _, newer = pending(store, chat_id=chat, request_id="new")
        before = store.get_chat(UID, chat)
    assert store.delegation_view(UID, chat, turn["id"])["status"] == "failed"
    assert store.get_turn(UID, chat, turn["id"])["agent_failure"]["code"] == "run_interrupted"
    if superseded:
        assert store.get_chat(UID, chat) == before
        assert store.get_turn(UID, chat, newer["id"])["status"] == "pending"


def test_live_pre_admission_is_not_reaped_but_expired_producer_cannot_start(store):
    loop = chat_loop(store, Completion)
    assert store.delegation_view(UID, loop.chat_id, loop.turn_id)["status"] == "pending"
    store._chat_ref(UID, loop.chat_id).update({"agent_lock_until": datetime.now(timezone.utc) - timedelta(seconds=1)})
    with pytest.raises(AgentRunInterrupted):
        list(loop.run())
    assert not store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().exists


def test_stop_between_status_event_and_provider_dispatch_is_known_zero(store):
    loop = chat_loop(store, Completion)
    source = loop.run()
    assert next(source)["type"] == "started"
    assert next(source)["status"] == "working"
    loop.cancellation.cancel()
    with pytest.raises(runtime.ProviderCancelled):
        list(source)
    budget = agent_quota.snapshot(store.db, UID)
    assert budget["reserved"] == budget["used"] == budget["unknown"] == 0
    assert store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()["usage"]["source"] == "not_started"


@pytest.mark.parametrize("ending", ["length", "timeout", "stop"])
def test_partial_synthesis_survives_after_comparisons(store, ending):
    script = Script()
    base = type(script.factory())
    class Interrupted(base):
        def stream(self, **kwargs):
            if self.step_id == "completion:1":
                self.text = "The synthesis available so far."
                yield {"type": "delta", "text": self.text}
                if ending == "timeout":
                    raise httpx.ReadTimeout("private provider details")
                if ending == "stop":
                    raise runtime.ProviderCancelled()
                self.finish_reason = "length"
                return
            yield from super().stream(**kwargs)
    loop = make_loop(store, script)
    loop.factory = Interrupted
    with pytest.raises((runtime.AnalysisBudgetExceeded, httpx.ReadTimeout, runtime.ProviderCancelled)):
        list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["consensus"] == "The synthesis available so far."
    assert saved["agent_review"]["versions"][-1]["text"] == saved["consensus"]
    assert saved["status"] == "failed"
    assert agent_quota.snapshot(store.db, UID)["reserved"] == 0
    assert totals(store)["unsettled_calls"] == 0


def test_loop_initialization_failure_unlocks_chat_and_releases_capacity(api, monkeypatch):
    client, store, calls = api
    from app.services.agent_runtime import AgentCapacity
    capacity = AgentCapacity(1)
    monkeypatch.setattr(agent, "agent_capacity", capacity)
    def fail(**kwargs):
        raise ValueError("Unavailable worker configuration")
    monkeypatch.setattr(agent, "DelegationLoop", fail)
    chat = store.create_chat(UID, execution_mode="agent")["id"]
    result = client.post('/agent', headers=AUTH, json={"chat_id": chat, "question": "Hi",
        "client_request_id": "init", "bookmark_id": "initialization"})
    assert result.status_code == 422 and not calls
    assert store.list_turns(UID, chat)["turns"][0]["status"] == "failed"
    capacity.acquire().release()
    assert pending(store, chat_id=chat, request_id="next")[1]["status"] == "pending"


def test_comparison_checkpoints_finished_answer_while_peer_is_still_running(store):
    script = Script()
    base = type(script.factory())
    saved, finish = threading.Event(), threading.Event()
    class SlowPeer(base):
        def stream(self, *, model, **kwargs):
            if self.step_id.startswith('agent:') and model.model.startswith('anthropic'):
                assert finish.wait(5)
            yield from super().stream(model=model, **kwargs)
    loop = make_loop(store, script)
    loop.factory = SlowPeer
    checkpoint = loop.comparison.checkpoint
    def observe(*args, **kwargs):
        checkpoint(*args, **kwargs)
        comparisons = loop.comparison.comparisons
        if comparisons and comparisons[0]['status'] == 'running' and len(comparisons[0]['answers']) == 1:
            saved.set()
    loop.comparison.checkpoint = observe
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(lambda: list(loop.run()))
        try:
            assert saved.wait(5)
            review = store.get_turn(UID, loop.chat_id, loop.turn_id)['agent_review']
            assert len(review['comparisons'][0]['answers']) == 1
            assert review['comparisons'][0]['answers'][0]['provider'] == 'openai'
        finally:
            finish.set()
        future.result(timeout=5)
    final = store.get_turn(UID, loop.chat_id, loop.turn_id)['agent_review']['comparisons'][0]
    assert len(final['answers']) == 2 and final['status'] == 'succeeded'


@pytest.mark.parametrize("heartbeat", [True, False])
def test_real_provider_socket_stall_releases_receipt_and_preserves_partial_text(store, monkeypatch, heartbeat):
    closed, requests = [], []
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"choices":[{"delta":{"content":"Partial answer"}}]}\n\n'
            while True:
                await asyncio.sleep(.015)
                if heartbeat:
                    yield b': OPENROUTER PROCESSING\n\n'
        async def aclose(self):
            closed.append(True)
    client_type = httpx.AsyncClient
    def respond(request):
        requests.append(request)
        return httpx.Response(200, stream=Body())
    monkeypatch.setattr(runtime.httpx, "AsyncClient", lambda **kwargs:
        client_type(transport=httpx.MockTransport(respond), **kwargs))
    monkeypatch.setattr(runtime, "_bounded_env_float", lambda *args: .08)
    loop = chat_loop(store, AgentCompletion)
    with pytest.raises(TimeoutError, match="no progress"):
        list(loop.run())
    assert len(requests) == 1 and closed
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["consensus"] == "Partial answer" and saved["agent_failure"]["code"] == "provider_timeout"
    assert agent_quota.snapshot(store.db, UID)["reserved"] == 0


def test_productive_stream_can_outlive_the_stall_interval(monkeypatch):
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            for text in ["Long ", "answer ", "with ", "progress."]:
                await asyncio.sleep(.04)
                yield ('data: ' + json.dumps({"choices": [{"delta": {"content": text}}]}) + '\n\n').encode()
            yield b'data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":4}}\n\n'
            yield b'data: [DONE]\n\n'
    client_type = httpx.AsyncClient
    monkeypatch.setattr(runtime.httpx, "AsyncClient", lambda **kwargs:
        client_type(transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=Body())), **kwargs))
    monkeypatch.setattr(runtime, "_bounded_env_float", lambda *args: .12)
    value = AgentCompletion()
    with runtime.bind_analysis_budget(runtime.AnalysisBudget(unlimited=True)):
        list(value.stream(model=AgentModel(), messages=[], api_key="test"))
    assert value.text == "Long answer with progress." and agent_quota.measured_tokens(value.usage) == 14
