"""Offline tokenizer initialization under concurrent cold requests."""
from concurrent.futures import ThreadPoolExecutor
import threading

from app.services import agent_tokens


def test_concurrent_cold_estimates_build_one_encoding_and_cache_can_be_cleared(monkeypatch):
    start = threading.Barrier(8)
    another_builder = threading.Event()
    built = []
    lock = threading.Lock()

    class Encoding:
        def encode_ordinary(self, _text):
            return [1, 2, 3]

    def build(**_kwargs):
        value = Encoding()
        with lock:
            built.append(value)
            first = len(built) == 1
        if first:
            # Keep the first cache miss open while the other cold callers
            # reach it. A single initializer never needs a second builder.
            another_builder.wait(1)
        else:
            another_builder.set()
        return value

    def estimate():
        start.wait(timeout=3)
        result = agent_tokens.input_estimate([{"role": "user", "content": "Offline"}])
        return result, agent_tokens.encoding()

    monkeypatch.setattr(agent_tokens.tiktoken, "Encoding", build)
    agent_tokens.encoding.cache_clear()
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(estimate) for _ in range(8)]
            results = [future.result(timeout=5) for future in futures]
        assert len(built) == 1
        assert all(result == 276 and encoder is built[0] for result, encoder in results)
        assert agent_tokens.encoding() is built[0]
        agent_tokens.encoding.cache_clear()
        assert agent_tokens.encoding() is not built[0]
        assert len(built) == 2
    finally:
        agent_tokens.encoding.cache_clear()
