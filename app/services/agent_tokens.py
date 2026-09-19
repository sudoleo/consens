"""Offline admission estimates. Only provider usage is charged to the ledger.

cl100k is a common baseline, not every provider's tokenizer. The 25% margin and
protocol allowance accommodate differences without treating every byte as a token.
The bundled vocabulary makes cold starts independent of network/cache state.
"""
import base64
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path

import tiktoken


@lru_cache(maxsize=1)
def encoding():
    data = gzip.decompress((Path(__file__).parent / "llm/tokenizer_data/cl100k_base.tiktoken.gz").read_bytes())
    if hashlib.sha256(data).hexdigest() != "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7":
        raise RuntimeError("Invalid bundled agent tokenizer vocabulary")
    ranks = {base64.b64decode(token): int(rank) for token, rank in (line.split() for line in data.splitlines())}
    return tiktoken.Encoding(name="agent_cl100k", mergeable_ranks=ranks, special_tokens={},
        pat_str=r"'(?i:[sdmt]|ll|ve|re)|[^\r\n\p{L}\p{N}]?+\p{L}++|\p{N}{1,3}+| ?[^\s\p{L}\p{N}]++[\r\n]*+|\s++$|\s*[\r\n]|\s+(?!\S)|\s")


def input_estimate(messages, tools=(), request_config=None):
    # Include signed reasoning, tool arguments/results and structured-output
    # schemas. No prompt-text cache: private conversations must not be retained.
    payload = [messages, tools, (request_config or {}).get("response_format")]
    count = len(encoding().encode_ordinary(json.dumps(payload, ensure_ascii=False, separators=(",", ":"))))
    return (count * 5 + 3) // 4 + 256 + 16 * len(messages)


def minimum_output(model):
    reasoning = model.request_config.get("reasoning") or {}
    explicit = reasoning.get("max_tokens")
    # Explicit thinking budgets need room for the visible response as well.
    return max(256, explicit + 256 if type(explicit) is int else 0)
