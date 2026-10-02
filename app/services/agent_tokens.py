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
import re
import threading

import tiktoken


# Conservative visual allowance for a native PDF. Scanned pages cost roughly
# 1.5k to 3k input tokens with the providers PDFs are routed to; the cap keeps a
# malformed page count from reserving more than a large model can hold.
PDF_TOKENS_PER_PAGE = 3_000
PDF_MAX_VISUAL_TOKENS = 200_000
IMAGE_VISUAL_TOKENS = 16_000


def pdf_visual_tokens(raw: bytes) -> int:
    pages = len(re.findall(rb"/Type\s*/Page(?![A-Za-z])", raw))
    return min(PDF_MAX_VISUAL_TOKENS, max(1, pages) * PDF_TOKENS_PER_PAGE)


def _data_url_tokens(value: str) -> int:
    if not value.startswith("data:application/pdf"):
        return IMAGE_VISUAL_TOKENS
    try:
        raw = base64.b64decode(value.split(";base64,", 1)[1], validate=False)
    except (ValueError, IndexError):
        return PDF_MAX_VISUAL_TOKENS
    return pdf_visual_tokens(raw)


_encoding_lock = threading.Lock()


@lru_cache(maxsize=1)
def _cached_encoding():
    data = gzip.decompress((Path(__file__).parent / "llm/tokenizer_data/cl100k_base.tiktoken.gz").read_bytes())
    if hashlib.sha256(data).hexdigest() != "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7":
        raise RuntimeError("Invalid bundled agent tokenizer vocabulary")
    ranks = {base64.b64decode(token): int(rank) for token, rank in (line.split() for line in data.splitlines())}
    return tiktoken.Encoding(name="agent_cl100k", mergeable_ranks=ranks, special_tokens={},
        pat_str=r"'(?i:[sdmt]|ll|ve|re)|[^\r\n\p{L}\p{N}]?+\p{L}++|\p{N}{1,3}+| ?[^\s\p{L}\p{N}]++[\r\n]*+|\s++$|\s*[\r\n]|\s+(?!\S)|\s")


def encoding():
    # lru_cache alone permits concurrent cold misses to build this vocabulary
    # repeatedly. Serialize the cache lookup as well as its initialization.
    with _encoding_lock:
        return _cached_encoding()


def _clear_encoding_cache():
    with _encoding_lock:
        _cached_encoding.cache_clear()


encoding.cache_clear = _clear_encoding_cache


def input_estimate(messages, tools=(), request_config=None):
    # Include signed reasoning, tool arguments/results and structured-output
    # schemas. No prompt-text cache: private conversations must not be retained.
    visual_tokens = 0
    def without_binary(value):
        nonlocal visual_tokens
        if isinstance(value, dict):
            return {key: without_binary(item) for key, item in value.items()}
        if isinstance(value, list):
            return [without_binary(item) for item in value]
        if isinstance(value, str) and value.startswith("data:") and ";base64," in value:
            visual_tokens += _data_url_tokens(value)
            return "[private visual input]"
        return value
    payload = [without_binary(messages), tools, (request_config or {}).get("response_format")]
    count = len(encoding().encode_ordinary(json.dumps(payload, ensure_ascii=False, separators=(",", ":"))))
    return (count * 5 + 3) // 4 + 256 + 16 * len(messages) + visual_tokens


def minimum_output(model):
    reasoning = model.request_config.get("reasoning") or {}
    explicit = reasoning.get("max_tokens")
    # Explicit thinking budgets need room for the visible response as well.
    return max(256, explicit + 256 if type(explicit) is int else 0)
