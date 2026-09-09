"""Assign run-wide citation IDs before synthesis, without losing source identity.

Provider IDs are local namespaces. Browser-supplied turn IDs are global hints,
never authority to overwrite a provider's own source mapping. Unknown or
ambiguous references retain a reserved, unresolvable ID instead of acquiring an
unrelated link. No fetching, persistence, truncation or model calls happen here.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import is_dataclass, replace
import re
from typing import Mapping
from urllib.parse import urlsplit, urlunsplit

import app.core.config as cfg

_ID = re.compile(r"S?([0-9]{1,6})", re.I)
_TAG = re.compile(r"(?<!\\)\[(S?\d{1,6}(?:\s*,\s*S?\d{1,6})*)\]", re.I)
_INLINE = re.compile(r"(?<!`)(`+)(?!`)([\s\S]*?)(?<!`)\1(?!`)")


def canonical_source_url(value: object) -> str:
    """Normalize host/scheme and fragments; preserve path/query case and slashes."""
    raw = str(value or "").strip()
    try:
        parts = urlsplit(raw)
        if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
            return ""
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(),
                           parts.path or "/", parts.query, ""))
    except ValueError:
        return ""


def _id(value: object) -> str:
    match = _ID.fullmatch(str(value or "").strip())
    return "S" + str(int(match[1])) if match and int(match[1]) else ""


def _prose_parts(text: str):
    """Yield (is_prose, text) while preserving fenced, indented and inline code."""
    fence = None
    prose = []

    def flush():
        block = "".join(prose)
        prose.clear()
        cursor = 0
        for match in _INLINE.finditer(block):
            yield True, block[cursor:match.start()]
            yield False, match[0]
            cursor = match.end()
        yield True, block[cursor:]

    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        if not fence and marker and marker[1][0] == "`" and "`" in marker[2]:
            marker = None
        if fence:
            yield False, line
            if (marker and marker[1][0] == fence[0] and
                    len(marker[1]) >= len(fence) and not marker[2].strip()):
                fence = None
        elif marker:
            yield from flush()
            fence = marker[1]
            yield False, line
        elif line.startswith(("    ", "\t")):
            yield from flush()
            yield False, line
        else:
            prose.append(line)
    yield from flush()


def rewrite_source_tags(text: str, id_map: Mapping[str, str]) -> str:
    def rewrite(match):
        return "[" + ", ".join(dict.fromkeys(
            id_map.get(_id(item), _id(item) or item.strip()) for item in match[1].split(",")
        )) + "]"
    return "".join(_TAG.sub(rewrite, part) if prose else part
                   for prose, part in _prose_parts(str(text or "")))


def _label(value: object) -> str:
    value = str(value or "")
    aliases = {str(key).lower(): label for key, label in cfg.PROVIDER_LABEL_BY_ID.items()}
    aliases.update({label.lower(): label for label in cfg.PROVIDER_LABEL_BY_ID.values()})
    aliases["claude"] = "Anthropic"
    return aliases.get(value.lower(), value)


def normalize_source_catalog(answers: Mapping, *, model_sources=None, turn_sources=None):
    """Return (answers, sources_by_provider_label, flat_catalog), without mutation.

    Answers may be ProviderAnswer dataclasses, response dictionaries or strings.
    Mapping keys and answer value types are preserved. The flat catalog includes
    every input source and a ``providers`` list for shared documents. Stable,
    unambiguous input IDs are retained, including browser turn numbering.
    """
    model_sources = model_sources if isinstance(model_sources, dict) else {}
    by_label = {_label(key): value for key, value in model_sources.items()}
    provider_rank = {_label(key): rank for rank, key in enumerate(cfg.PROVIDERS)}
    ordered = sorted(answers, key=lambda key: (provider_rank.get(_label(key), 999), str(key)))
    records = {}
    candidates = defaultdict(set)
    explicit = defaultdict(set)
    local = {}
    answer_info = {}

    def add(source, namespace, index, global_hint=False):
        if not isinstance(source, dict):
            return None
        source_id = _id(source.get("id"))
        # Missing IDs use provider-local list numbering. Explicit malformed IDs
        # do not silently alias a numbered reference.
        if not source.get("id"):
            source_id = "S" + str(index + 1)
        url = canonical_source_url(source.get("url"))
        identity = ("url", url) if url else ("opaque", namespace, index)
        if identity not in records:
            records[identity] = dict(source)
            records[identity]["providers"] = []
        record = records[identity]
        providers = source.get("providers", [])
        providers = providers if isinstance(providers, list) else []
        for provider in [*providers, source.get("provider"), namespace if not global_hint else None]:
            provider = _label(provider)
            if provider and provider not in record["providers"]:
                record["providers"].append(provider)
        if not record.get("provider") and record["providers"]:
            record["provider"] = record["providers"][0]
        if source_id:
            candidates[source_id].add(identity)
            if global_hint:
                explicit[source_id].add(identity)
        return source_id, identity

    for index, source in enumerate(turn_sources if isinstance(turn_sources, list) else []):
        add(source, "turn", index, True)
    for key in ordered:
        answer = answers[key]
        if isinstance(answer, dict):
            label = _label(answer.get("provider") or key)
            text = str(answer.get("response", answer.get("text", "")) or "")
            sources = answer.get("sources", by_label.get(label, []))
        else:
            label = _label(getattr(answer, "provider", key))
            text = str(getattr(answer, "response", answer) or "")
            sources = getattr(answer, "sources", by_label.get(label, []))
        mapping = defaultdict(set)
        identities = []
        for index, source in enumerate(sources if isinstance(sources, list) else []):
            added = add(source, label, index)
            if added:
                source_id, identity = added
                if source_id:
                    mapping[source_id].add(identity)
                if identity not in identities:
                    identities.append(identity)
        local[key] = mapping
        answer_info[key] = label, text, identities

    references = {}
    unresolved = set()
    for key, (_, text, _) in answer_info.items():
        refs = dict.fromkeys(_id(item) for prose, part in _prose_parts(text) if prose
                             for match in _TAG.finditer(part) for item in match[1].split(","))
        references[key] = {}
        for source_id in refs:
            if not source_id:
                continue
            possibilities = local[key].get(source_id) or explicit.get(source_id, set())
            identity = next(iter(possibilities)) if len(possibilities) == 1 else None
            references[key][source_id] = identity
            if identity is not None and identity not in answer_info[key][2]:
                answer_info[key][2].append(identity)
            if identity is None:
                unresolved.add(source_id)

    assigned = {}
    used = set(unresolved)
    # Explicit global hints take precedence over local IDs. Within each class,
    # first appearance is deterministic and permits stable browser numbering.
    for collection in (explicit, candidates):
        for source_id, identities in collection.items():
            if len(identities) == 1 and source_id not in used:
                identity = next(iter(identities))
                if identity not in assigned:
                    assigned[identity] = source_id
                    used.add(source_id)
    next_number = 1
    for identity in records:
        if identity not in assigned:
            while "S" + str(next_number) in used:
                next_number += 1
            assigned[identity] = "S" + str(next_number)
            used.add(assigned[identity])
        records[identity]["id"] = assigned[identity]

    normalized = {}
    normalized_sources = {}
    for key in ordered:
        answer = answers[key]
        label, text, identities = answer_info[key]
        rewritten = rewrite_source_tags(text, {
            source_id: assigned[identity] if identity is not None else source_id
            for source_id, identity in references[key].items()
        })
        sources = [dict(records[identity], provider=label) for identity in identities]
        normalized_sources[label] = sources
        if is_dataclass(answer) and not isinstance(answer, type):
            normalized[key] = replace(answer, response=rewritten, sources=sources)
        elif isinstance(answer, dict):
            field = "response" if "response" in answer or "text" not in answer else "text"
            normalized[key] = dict(answer, **{field: rewritten, "sources": sources})
        else:
            normalized[key] = rewritten
    catalog = sorted(records.values(), key=lambda record: int(record["id"][1:]))
    return normalized, normalized_sources, catalog


def normalize_provider_answers(answers: Mapping):
    """Convenience wrapper for provider fan-out callers."""
    return normalize_source_catalog(answers)[0]
