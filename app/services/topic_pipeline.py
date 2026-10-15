"""Topic-specific projection on top of the neutral Consensus pipeline.

Topics own research/timeline semantics.  They intentionally do not call the
Watch executor or inherit Watch notification, baseline or quota behaviour.
"""

from __future__ import annotations

import functools

from app.core.entitlements import TIER_FREE
from app.services import evidence_change, opinion_map, share_snapshots, source_redirects
from app.services.consensus_pipeline import run_consensus_pipeline
from app.services.llm.consensus_engine import query_differences
from app.services.llm.mock_llm import mock_llm_enabled
from app.services.llm import provider_transport


def execute_topic(
    question: str,
    previous_consensus: str,
    condition: str = "",
    previous_opinion_map=None,
    tier=TIER_FREE,
    baseline_consensus: str = "",
    model_overrides=None,
    previous_sources=None,
    previous_models=None,
) -> dict:
    """One Topic check, compared with the standing answer and its sources."""
    keys = provider_transport.developer_keys()
    configured = dict(model_overrides or {})
    provider_models = {
        provider: configured[provider]
        for provider in provider_transport.PROVIDER_ORDER
        if configured.get(provider)
        and provider_transport.provider_available(provider, keys)
    }
    if mock_llm_enabled():
        for provider in provider_models:
            keys[provider_transport.PROVIDER_LABELS[provider]] = "mock"
    if len(provider_models) < 2:
        raise RuntimeError("Fewer than two Topic provider transports are available")
    def first_successful_engine(answers) -> str:
        provider = next(name for name in provider_models if name in answers)
        return provider_transport.PROVIDER_LABELS[provider]

    pipeline = run_consensus_pipeline(
        question=question,
        provider_models=provider_models,
        consensus_model=first_successful_engine,
        keys=keys,
        tier=tier,
        provider_order=provider_transport.PROVIDER_ORDER,
        # Topic pages are public and English, and the judge's claims are read
        # there ("How the models compared"): English, and statements rather
        # than "Whether ..." questions, whatever language an answer came in.
        judge=functools.partial(
            query_differences, output_language="English", statement_claims=True,
        ),
        log_context="Consensus Topic",
    )
    included = {item["provider"] for item in pipeline["model_answers"]}
    engine = provider_transport.PROVIDER_LABELS[
        next(name for name in provider_models if provider_transport.PROVIDER_LABELS[name] in included)
    ]
    consensus = pipeline["consensus_response"]
    model_answers = pipeline["model_answers"]
    sources = share_snapshots.sanitize_sources({
        item["provider"]: item.get("sources") or []
        for item in model_answers if item.get("sources")
    })
    # Google redirects become the page they point to before the Judge cites
    # them and before they reach the page, where they expire within weeks
    # (source_redirects.py, same as Watches).
    sources = source_redirects.resolve_sources(sources)
    included_models = share_snapshots.build_included_models(
        [item["provider"] for item in model_answers],
        {item["provider"]: item["model"] for item in model_answers},
    )
    if str(previous_consensus or "").strip():
        change = evidence_change.assess(
            previous_consensus, consensus, keys, engine, condition=condition,
            previous_sources=previous_sources or [], new_sources=sources,
            previous_models=previous_models or [], new_models=included_models,
        )
    else:
        change = evidence_change.first_check(
            consensus, keys, engine, condition=condition, new_sources=sources,
        )
    differences = pipeline["differences_data"]
    position_map = opinion_map.build_opinion_map(
        differences,
        previous_opinion_map,
        consensus_changed=bool(change.get("changed")),
    )
    return {
        "consensus": consensus,
        "agreement_score": pipeline["agreement"]["score"],
        "verdict": pipeline["agreement"].get("level") or "",
        "opinion_map": position_map,
        "differences_data": differences,
        "differences_text": pipeline["differences"],
        "sources": sources,
        "included_models": included_models,
        "consensus_model": engine,
        **change,
    }
