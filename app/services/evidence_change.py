"""Evidence-aware comparison of a new consensus check with the standing answer.

Shared by Consensus Watches and Topics (contract: ``docs/watch-evidence-model.md``).
The Change Judge sees both answers *and* both source lists and names a cause;
this module prepares those lists and then checks the Judge's claims
deterministically, because a cause the server cannot verify must not move a
public record:

* cited source IDs must exist in the new check, otherwise they are dropped;
* ``new_evidence`` needs at least one cited source whose URL the standing
  answer did not cite -- otherwise it is a ``reassessment``;
* a reassessment after the answering line-up changed is a ``model_change``;
* a goal match the owner already rejected never counts as meeting the goal.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from app.services import drift_signal
from app.services.source_catalog import canonical_source_url

MAX_PROMPT_SOURCES = 40
MAX_EVIDENCE_SOURCES = 4


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def _catalog(sources) -> list[dict]:
    """Citable entries ``{id, url, key, title, host}``; IDs stay as cited."""
    catalog, used = [], set()
    for index, source in enumerate(sources or []):
        if not isinstance(source, dict):
            continue
        key = canonical_source_url(source.get("url"))
        if not key:
            continue
        source_id = str(source.get("id") or source.get("source_id") or "").strip()
        if not source_id or source_id in used:
            # Uncited extras still count for "seen before"; they get an ID the
            # consensus text cannot contain, so they are never confused with one.
            source_id = f"X{index + 1}"
        used.add(source_id)
        title = str(source.get("title") or "").strip()
        catalog.append({
            "id": source_id,
            "url": str(source.get("url") or ""),
            "key": key,
            "title": title if title and not title.isdigit() else _host(key),
            "host": _host(key),
        })
    return catalog


def source_keys(sources) -> set[str]:
    """Canonical URLs of a source list (e.g. the matches an owner rejected)."""
    return {
        key for key in (
            canonical_source_url(item.get("url"))
            for item in sources or [] if isinstance(item, dict)
        ) if key
    }


def prompt_sources(previous_sources, new_sources,
                   ruled_out=frozenset()) -> tuple[list[dict], list[dict]]:
    """The two source lists exactly as the Judge receives them.

    A NEW source the owner already rejected as a goal match is marked
    ``ruled_out``; without rejections the lists are unchanged.
    """
    previous = _catalog(previous_sources)
    seen = {item["key"] for item in previous}
    old_view = [
        {"id": item["id"], "site": item["host"], "title": item["title"][:160]}
        for item in previous[:MAX_PROMPT_SOURCES]
    ]
    new_view = [
        {
            "id": item["id"],
            "site": item["host"],
            "title": item["title"][:160],
            "seen_before": item["key"] in seen,
            **({"ruled_out": item["key"] in ruled_out} if ruled_out else {}),
        }
        for item in _catalog(new_sources)[:MAX_PROMPT_SOURCES]
    ]
    return old_view, new_view


def _cited(ids, catalog_by_id: dict) -> list[dict]:
    found = []
    for value in ids or []:
        item = catalog_by_id.get(str(value or "").strip())
        if item and item not in found:
            found.append(item)
    return found


def _public(items) -> list[dict]:
    return [
        {"id": item["id"], "title": item["title"][:240], "url": item["url"]}
        for item in items[:MAX_EVIDENCE_SOURCES]
    ]


def assess(standing_consensus: str, new_consensus: str, keys: dict, engine: str, *,
           condition: str = "", requirements: str = "", rejected_sources=(),
           previous_sources=(), new_sources=(),
           previous_models=(), new_models=()) -> dict:
    """Judge a new check against the standing answer and verify the verdict.

    ``requirements`` and ``rejected_sources`` belong to the goal: the details
    a match must fit and the matches the owner already turned down.
    """
    from app.services.llm.consensus_engine import query_consensus_change

    change = query_consensus_change(
        standing_consensus, new_consensus, keys, engine, condition=condition,
        requirements=requirements, ruled_out=source_keys(rejected_sources),
        old_sources=previous_sources, new_sources=new_sources,
    )
    return verify(
        change, previous_sources=previous_sources, new_sources=new_sources,
        previous_models=previous_models, new_models=new_models,
        rejected_sources=rejected_sources,
    )


def first_check(new_consensus: str, keys: dict, engine: str, *, condition: str = "",
                new_sources=(), requirements: str = "", rejected_sources=()) -> dict:
    """The verdict for a check that establishes the baseline.

    There is nothing to compare with, so it never counts as movement; a goal
    is still judged against the new answer alone.
    """
    change = {
        "changed": False,
        "severity": "minor",
        "cause": drift_signal.CAUSE_NONE,
        "change_summary": "First consensus established.",
        "held_summary": "",
        "evidence_sources": [],
    }
    if condition:
        judged = assess(
            new_consensus, new_consensus, keys, engine, condition=condition,
            requirements=requirements, rejected_sources=rejected_sources,
            previous_sources=new_sources, new_sources=new_sources,
        )
        change.update({
            key: judged[key]
            for key in (
                "condition_status", "condition_reason", "condition_verified",
                "condition_sources",
            )
            if key in judged
        })
    return change


RULED_OUT_REASON = "The only match found is one you already ruled out."


def verify(change: dict, *, previous_sources, new_sources,
           previous_models=(), new_models=(), rejected_sources=()) -> dict:
    """Return ``change`` with a verified ``cause`` and resolved evidence lists."""
    result = dict(change or {})
    new_catalog = _catalog(new_sources)
    by_id = {item["id"]: item for item in new_catalog}
    seen = {item["key"] for item in _catalog(previous_sources)}

    cause = drift_signal.normalize_cause(result.get("cause"))
    evidence = _cited(result.get("evidence"), by_id)
    if not result.get("changed"):
        cause = drift_signal.CAUSE_NONE
    elif not cause or cause == drift_signal.CAUSE_NONE:
        cause = drift_signal.CAUSE_REASSESSMENT
    if cause == drift_signal.CAUSE_NEW_EVIDENCE and not any(
        item["key"] not in seen for item in evidence
    ):
        cause = drift_signal.CAUSE_REASSESSMENT
    if cause == drift_signal.CAUSE_REASSESSMENT and previous_models and new_models and (
        set(map(str, previous_models)) != set(map(str, new_models))
    ):
        cause = drift_signal.CAUSE_MODEL_CHANGE
    result["cause"] = cause
    # Only the sources that carry the change are shown with it; for a held or
    # reassessed answer the citations would suggest evidence that is not there.
    result["evidence_sources"] = (
        _public([item for item in evidence if item["key"] not in seen])
        if cause == drift_signal.CAUSE_NEW_EVIDENCE else []
    )
    result.pop("evidence", None)

    if "condition_status" in result:
        ruled_out = source_keys(rejected_sources)
        cited = _cited(result.get("condition_evidence"), by_id)
        condition_evidence = [item for item in cited if item["key"] not in ruled_out]
        if result.get("condition_status") == "met" and cited and not condition_evidence:
            # Every cited match is one the owner turned down: not a match.
            result["condition_status"] = "not_met"
            result["condition_reason"] = RULED_OUT_REASON
        result["condition_verified"] = bool(
            result.get("condition_status") == "met" and condition_evidence
        )
        result["condition_sources"] = (
            _public(condition_evidence) if result["condition_status"] == "met" else []
        )
        result.pop("condition_evidence", None)
    return result
