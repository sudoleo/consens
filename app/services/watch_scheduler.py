"""Sequential, Firestore-leased background runner for Consensus Watch."""

from __future__ import annotations

import asyncio
import logging
import time

import app.core.config as cfg
from app.core import security
from app.core.background_tasks import task_succeeded
from app.core.entitlements import TIER_FREE
from app.core.observability import correlation_scope, record_metric, safe_exception
from app.services.consensus_pipeline import run_consensus_pipeline
from app.services import (
    drift_signal, mailer, notification_delivery, notification_outbox, opinion_map,
    share_snapshots, watch_brief, watch_followers, watch_service,
)
from app.services.llm import provider_transport
from app.services.llm.consensus_engine import (
    query_consensus,
    query_consensus_change,
    query_differences,
)
from app.services.llm.mock_llm import mock_llm_enabled


TICK_SECONDS = 30 * 60
WATCH_LEASE_HEARTBEAT_SECONDS = 5 * 60
# The global worker lease lasts WORKER_LEASE_MINUTES; renew well before that
# between watches so a long tick keeps it, and stop when it was taken over.
WORKER_LEASE_RENEW_SECONDS = 5 * 60
_scheduler_wake_event: asyncio.Event | None = None
# Preserve the established Watch engine preference. Topic/API use the shared
# canonical display order, while Watch historically preferred Gemini before
# Anthropic when both earlier engines failed.
_WATCH_ENGINE_PREFERENCE = ("openai", "mistral", "gemini", "anthropic", "deepseek", "grok")
PROVIDER_ORDER = tuple(dict.fromkeys(
    [provider for provider in _WATCH_ENGINE_PREFERENCE if provider in cfg.PROVIDERS]
    + list(cfg.PROVIDERS)
))
PROVIDER_LABELS = provider_transport.PROVIDER_LABELS


def _developer_keys() -> dict:
    return provider_transport.developer_keys()


def _selected_models(keys: dict, tier,
                     model_overrides=None) -> list[tuple[str, str]]:
    """Every provider the tier configures, minus the ones with no credential.

    A missing server key is the only reason a configured provider can drop out
    of a run. There is deliberately no second, invisible filter on top of the
    Admin configuration.
    """
    configured = (
        dict(model_overrides)
        if isinstance(model_overrides, dict)
        else cfg.get_watch_models(tier)
    )
    if mock_llm_enabled():
        return [
            (provider, configured[provider])
            for provider in PROVIDER_ORDER
            if configured.get(provider)
        ]
    return [
        (provider, configured[provider]) for provider in PROVIDER_ORDER
        if configured.get(provider)
        and provider_transport.provider_available(provider, keys)
    ]


def _provider_answer(provider: str, model: str, question: str, keys: dict,
                     tier, deep_think: bool = False):
    return provider_transport.query_provider(
        provider, model, question, keys, tier, deep_think
    )


def _configured_consensus_engine(keys: dict, tier) -> str | None:
    """Return the configured Watch engine when its provider can be called."""
    chosen = cfg.get_watch_consensus_model(tier)
    resolved = cfg.get_consensus_model_config(chosen)
    if not resolved or not resolved.provider:
        return None
    if not provider_transport.provider_available(resolved.provider, keys):
        return None
    return chosen


def execute_watch(question: str, previous_consensus: str, condition: str = "",
                  previous_opinion_map=None, tier=TIER_FREE,
                  baseline_consensus: str = "",
                  model_overrides=None) -> dict:
    """Run the configured tier models; never touches usage counters."""
    keys = _developer_keys()
    selected_models = _selected_models(
        keys, tier, model_overrides=model_overrides
    )
    configured_engine = _configured_consensus_engine(keys, tier)
    if mock_llm_enabled():
        for provider, _model in selected_models:
            keys[PROVIDER_LABELS[provider]] = "mock"
        if configured_engine:
            provider = cfg.get_consensus_model_config(configured_engine).provider
            keys[PROVIDER_LABELS[provider]] = "mock"
    provider_models = dict(selected_models)

    def first_successful_engine(answers) -> str:
        provider = next(name for name, _model in selected_models if name in answers)
        return PROVIDER_LABELS[provider]

    pipeline = run_consensus_pipeline(
        question=question,
        provider_models=provider_models,
        consensus_model=configured_engine or first_successful_engine,
        keys=keys,
        tier=tier,
        deep_think=False,
        provider_order=PROVIDER_ORDER,
        provider_call=_provider_answer,
        synthesize=query_consensus,
        judge=query_differences,
        log_context="Consensus Watch",
    )
    engine = configured_engine or first_successful_engine({
        provider: True
        for provider, _model in selected_models
        if any(
            item["provider"] == PROVIDER_LABELS[provider]
            for item in pipeline["model_answers"]
        )
    })
    consensus = pipeline["consensus_response"]
    differences = pipeline["differences_data"]
    agreement = pipeline["agreement"]
    model_answers = pipeline["model_answers"]
    model_sources = {
        item["provider"]: item.get("sources") or []
        for item in model_answers if item.get("sources")
    }
    if str(previous_consensus or "").strip():
        change = query_consensus_change(
            previous_consensus, consensus, keys, engine, condition=condition,
        )
    else:
        # A query-first Watch intentionally has no manual Consensus baseline.
        # Its first scheduled result establishes that baseline and must not be
        # reported as a material change merely because the old text was empty.
        change = {
            "changed": False,
            "severity": "minor",
            "change_summary": "First consensus established.",
        }
        if condition:
            condition_result = query_consensus_change(
                consensus, consensus, keys, engine, condition=condition,
            )
            change.update({
                key: condition_result[key]
                for key in ("condition_status", "condition_reason")
                if key in condition_result
            })
    baseline = str(baseline_consensus or previous_consensus or "")
    if baseline.strip() and baseline.strip() != str(previous_consensus or "").strip():
        baseline_change = query_consensus_change(baseline, consensus, keys, engine)
    else:
        baseline_change = change
    position_map = opinion_map.build_opinion_map(
        differences,
        previous_opinion_map,
        consensus_changed=bool(change.get("changed")),
    )
    included_providers = [item["provider"] for item in model_answers]
    model_labels = {
        item["provider"]: item["model"] for item in model_answers
    }
    return {
        "consensus": consensus,
        "agreement_score": agreement["score"],
        "verdict": agreement.get("level") or "",
        "opinion_map": position_map,
        "differences_data": differences,
        "differences_text": pipeline["differences"],
        "sources": share_snapshots.sanitize_sources(model_sources),
        "included_models": share_snapshots.build_included_models(
            included_providers, model_labels,
        ),
        "consensus_model": engine,
        "baseline_changed": bool(baseline_change.get("changed")),
        "baseline_severity": baseline_change.get("severity") or "minor",
        "baseline_summary": baseline_change.get("change_summary") or "",
        **change,
    }


def should_notify(old_score, new_score, changed: bool, severity: str,
                  previous_scores=None) -> bool:
    """The mail bar, and since the drift rule was unified, the page bar too.

    ``previous_scores`` is the band of the recent checks; without it the
    predecessor alone forms the band, which is what a two-point history means
    anyway.
    """
    if previous_scores is None:
        previous_scores = [old_score] if isinstance(old_score, (int, float)) else []
    return drift_signal.is_material(changed, severity, new_score, previous_scores)


def _recent_scores(watch: dict) -> list:
    points = watch.get("history_points")
    return drift_signal.recent_scores(points if isinstance(points, list) else [])


def notification_kind(watch: dict, result: dict) -> str | None:
    email_mode = watch.get("email_mode") or "changes_only"
    if email_mode == "every_run":
        return "every_run"
    if email_mode == "condition":
        current_hash = watch_service.condition_hash(watch.get("condition") or "")
        previous_is_same_condition = watch.get("last_condition_hash") == current_hash
        if (result.get("condition_status") == "met"
                and (watch.get("last_condition_status") != "met"
                     or not previous_is_same_condition)):
            return "condition"
        return None
    if should_notify(
        watch.get("last_agreement_score"), result.get("agreement_score"),
        bool(result.get("changed")), result.get("severity") or "minor",
        _recent_scores(watch) or None,
    ):
        return "change"
    return None


def run_notification_builder(watch_id: str, result: dict, follower_ids, *,
                             now, mail_ready: bool, evaluated_condition: str = ""):
    """Outbox items for one successful run, evaluated against the CURRENT watch.

    ``complete_watch_run`` calls the builder inside its result transaction
    with the claim merged with the current configuration, so alert rule,
    channels and condition edited during the run are honoured (R16) and the
    items commit atomically with the result (R17).
    """
    evaluated_hash = watch_service.condition_hash(evaluated_condition or "")

    def build(effective: dict) -> list:
        items = []
        alert = notification_kind(effective, result)
        if alert == "condition" and (
            watch_service.condition_hash(effective.get("condition") or "") != evaluated_hash
        ):
            # The run judged a condition the owner has replaced meanwhile.
            alert = None
        if alert:
            items.extend(notification_outbox.watch_alert_items(
                watch_id, effective, result, alert, now=now, email=mail_ready,
            ))
        if follower_ids and should_notify(
            effective.get("last_agreement_score"), result.get("agreement_score"),
            bool(result.get("changed")), result.get("severity") or "minor",
            _recent_scores(effective) or None,
        ):
            items.extend(notification_outbox.watch_follower_items(
                watch_id, effective, result, follower_ids, now=now,
            ))
        return items

    return notification_outbox.StagedIds(build)


def paused_notification_builder(watch_id: str, *, now, mail_ready: bool):
    return notification_outbox.StagedIds(
        lambda effective: notification_outbox.watch_paused_items(
            watch_id, effective, now=now, email=mail_ready,
        )
    )


async def _follower_ids(claimed: dict, result: dict, mail_ready: bool) -> list:
    """Confirmed page followers, read only when a follower mail is possible."""
    if not mail_ready or str(claimed.get("visibility") or "public") == "private":
        return []
    if not should_notify(
        claimed.get("last_agreement_score"), result.get("agreement_score"),
        bool(result.get("changed")), result.get("severity") or "minor",
        _recent_scores(claimed) or None,
    ):
        return []
    followers = await asyncio.to_thread(watch_followers.list_followers, claimed["share_id"])
    return [follower["id"] for follower in followers if follower.get("id")]


async def _renew_worker_lease_until_stopped(
    owner: str, stop: asyncio.Event, lost: asyncio.Event
) -> None:
    """Keep the global lease while this worker owns it; flag its loss."""
    while True:
        try:
            await asyncio.wait_for(stop.wait(), timeout=WORKER_LEASE_RENEW_SECONDS)
            return
        except asyncio.TimeoutError:
            try:
                renewed = await asyncio.to_thread(
                    watch_service.renew_worker_lease, owner,
                    now=watch_service.utcnow(),
                )
            except Exception as exc:
                logging.warning(
                    "Consensus Watch worker lease renewal failed category=%s",
                    safe_exception(exc),
                )
                continue
            if not renewed:
                lost.set()
                return


async def _renew_watch_lease_until_stopped(
    watch_id: str, run_id: str, stop: asyncio.Event
) -> None:
    while True:
        try:
            await asyncio.wait_for(
                stop.wait(), timeout=WATCH_LEASE_HEARTBEAT_SECONDS
            )
            return
        except asyncio.TimeoutError:
            renewed = await asyncio.to_thread(
                watch_service.renew_watch_lease,
                watch_id,
                run_id,
                now=watch_service.utcnow(),
            )
            if not renewed:
                logging.warning("Consensus Watch lease lost for %s", watch_id)
                return


async def _deliver_now(item_ids) -> None:
    """First attempt right after the commit; the outbox pass retries the rest."""
    if not item_ids:
        return
    try:
        await notification_delivery.deliver_many(item_ids)
    except Exception as exc:
        logging.error(
            "Consensus Watch notification delivery failed category=%s",
            safe_exception(exc),
        )


async def run_watch_tick() -> int:
    # MOCK_LLM instances share the production Firestore: a mock tick would take
    # the worker lease from the live deployment and persist fixture answers as
    # real watch runs. execute_watch itself stays mockable for the test suite.
    if mock_llm_enabled():
        return 0
    now = watch_service.utcnow()
    lease_owner = await asyncio.to_thread(watch_service.acquire_worker_lease, now=now)
    if not lease_owner:
        return 0
    worker_stop = asyncio.Event()
    worker_lost = asyncio.Event()
    worker_heartbeat = asyncio.create_task(
        _renew_worker_lease_until_stopped(lease_owner, worker_stop, worker_lost)
    )
    completed = 0
    try:
        due_ids = await asyncio.to_thread(watch_service.list_due_watch_ids, now=now)
        for watch_id in due_ids:
            if worker_lost.is_set():
                # Another worker owns the global lease now; running on would
                # put two schedulers side by side (R30).
                logging.warning("Consensus Watch worker lease lost; stopping tick")
                break
            claimed, reason = await asyncio.to_thread(
                watch_service.claim_watch,
                watch_id,
                now=watch_service.utcnow(),
            )
            if reason == "budget":
                break
            if not claimed:
                continue
            lease_stop = asyncio.Event()
            lease_heartbeat = asyncio.create_task(
                _renew_watch_lease_until_stopped(
                    watch_id,
                    str(claimed.get("current_run_id") or ""),
                    lease_stop,
                )
            )
            staged_ids = []
            try:
                share = await asyncio.to_thread(share_snapshots.get_share, claimed["share_id"])
                if not share or share.get("status") != "active":
                    raise RuntimeError("Watch share is unavailable.")
                claimed["question"] = share.get("question") or ""
                claimed["share_slug"] = share.get("slug") or ""
                claimed["initial_watch_run"] = bool(
                    share.get("awaiting_first_watch_run")
                    and not claimed.get("last_successful_run_id")
                )
                account_tier = await asyncio.to_thread(
                    security.get_user_tier, claimed["owner_uid"]
                )
                # Scheduled Publisher pages are deliberately pinned to the
                # Admin-configured Free Watch providers. All ordinary watches
                # continue to follow the owner's live account tier.
                # Plus faehrt hier ohnehin die Free-Modelle (siehe
                # cfg.get_watch_models) -- mehr Watches, gleiche Kosten.
                tier = TIER_FREE if claimed.get("model_tier") == "free" else account_tier
                try:
                    history = await asyncio.to_thread(
                        share_snapshots.list_watch_history, claimed["share_id"], max_items=1,
                    )
                except Exception as exc:
                    logging.warning(
                        "Consensus Watch position baseline unavailable category=%s",
                        safe_exception(exc),
                    )
                    history = []
                previous_position_map = (
                    history[-1].get("opinion_map") if history
                    else opinion_map.build_opinion_map(share.get("differences_data") or {})
                )
                previous_version = None
                previous_run_id = str(claimed.get("last_successful_run_id") or "")
                try:
                    if previous_run_id:
                        previous_version = await asyncio.to_thread(
                            share_snapshots.get_watch_version,
                            claimed["share_id"], previous_run_id,
                        )
                except Exception as exc:
                    logging.warning(
                        "Consensus Watch text baseline unavailable category=%s",
                        safe_exception(exc),
                    )
                original_consensus = share.get("consensus_md") or ""
                previous_consensus = (
                    previous_version.get("consensus_md")
                    if previous_version else original_consensus
                )
                result = await asyncio.to_thread(
                    execute_watch, claimed["question"], previous_consensus,
                    claimed.get("condition") if claimed.get("email_mode") == "condition" else "",
                    previous_position_map,
                    tier,
                    baseline_consensus=original_consensus,
                )
                mail_ready = mailer.is_configured()
                follower_ids = await _follower_ids(claimed, result, mail_ready)
                completed_at = watch_service.utcnow()
                staged = run_notification_builder(
                    watch_id, result, follower_ids, now=completed_at, mail_ready=mail_ready,
                    evaluated_condition=(
                        claimed.get("condition") or ""
                        if claimed.get("email_mode") == "condition" else ""
                    ),
                )
                # Result, schedule, condition state and the outbox items
                # commit in one transaction; a crash after it loses nothing.
                persisted = await asyncio.to_thread(
                    watch_service.complete_watch_run, watch_id, claimed, result,
                    now=completed_at, notifications=staged,
                )
                if persisted is None:
                    logging.warning(
                        "Consensus Watch completion fenced out for %s", watch_id
                    )
                    continue
                staged_ids = list(staged.ids)
            except Exception as exc:
                logging.error(
                    "Consensus Watch run failed for %s category=%s",
                    watch_id,
                    safe_exception(exc),
                )
                paused_staged = paused_notification_builder(
                    watch_id, now=watch_service.utcnow(), mail_ready=mailer.is_configured(),
                )
                try:
                    paused = await asyncio.to_thread(
                        watch_service.fail_watch_run, watch_id, claimed,
                        now=watch_service.utcnow(), notifications=paused_staged,
                    )
                except Exception as fail_exc:
                    logging.error(
                        "Consensus Watch failure bookkeeping failed for %s category=%s",
                        watch_id,
                        safe_exception(fail_exc),
                    )
                    paused = None
                if paused:
                    staged_ids = list(paused_staged.ids)
            else:
                completed += 1
            finally:
                lease_stop.set()
                await lease_heartbeat
            await _deliver_now(staged_ids)
    finally:
        worker_stop.set()
        await worker_heartbeat
        try:
            released = await asyncio.to_thread(
                watch_service.release_worker_lease, lease_owner
            )
            if not released:
                logging.warning(
                    "Consensus Watch worker lease was already taken over; not released"
                )
        except Exception as exc:
            logging.error(
                "Consensus Watch worker lease release failed category=%s",
                safe_exception(exc),
            )
    return completed


async def run_brief_tick() -> int:
    """Claim due Morning Briefs and deliver them through the durable outbox.

    The claim advances the schedule and stages the Brief's outbox item in the
    same transaction. A crash after the claim no longer skips the digest: the
    outbox pass retries it (within ``BRIEF_DELIVER_WITHIN``), re-checking the
    Brief subscription before every attempt. At-least-once, not exactly-once.
    """
    if mock_llm_enabled() or not mailer.is_configured():
        return 0
    now = watch_brief.utcnow()
    try:
        due_uids = await asyncio.to_thread(watch_brief.list_due_brief_uids, now=now)
    except Exception as exc:
        logging.error(
            "Morning brief due-scan failed category=%s", safe_exception(exc)
        )
        return 0
    sent = 0
    for uid in due_uids:
        try:
            claimed = await asyncio.to_thread(watch_brief.claim_brief, uid, now=now)
            item_id = (claimed or {}).get("outbox_id")
            if not item_id:
                continue
            status = await notification_delivery.deliver(item_id)
            sent += int(status == notification_outbox.SENT)
        except Exception as exc:
            logging.error(
                "Morning brief delivery failed category=%s", safe_exception(exc)
            )
    return sent


async def run_notification_outbox_tick() -> dict:
    """Retry pass for every due outbox item (Watch, follower, Topic, Brief)."""
    if mock_llm_enabled():
        return {}
    try:
        return await notification_delivery.run_outbox_tick()
    except Exception as exc:
        logging.error(
            "Notification outbox pass failed category=%s", safe_exception(exc)
        )
        return {}


def wake_watch_scheduler():
    """Wake the in-process scheduler so newly queued work starts promptly."""
    if _scheduler_wake_event is not None:
        _scheduler_wake_event.set()


async def watch_scheduler_loop():
    global _scheduler_wake_event
    wake_event = asyncio.Event()
    _scheduler_wake_event = wake_event
    try:
        while True:
            # Clear before the tick so a wake-up arriving during a long run is
            # retained and causes another immediate scan afterwards.
            wake_event.clear()
            started = time.monotonic()
            with correlation_scope(prefix="watch-tick"):
                try:
                    watches_ran = await run_watch_tick()
                    briefs_sent = await run_brief_tick()
                    outbox_counts = await run_notification_outbox_tick()
                except Exception:
                    record_metric(
                        "scheduler", "consensus-watch",
                        duration_ms=(time.monotonic() - started) * 1000,
                        outcome="failure",
                    )
                    raise
                record_metric(
                    "scheduler", "consensus-watch",
                    duration_ms=(time.monotonic() - started) * 1000,
                    processed=int(watches_ran or 0) + int(briefs_sent or 0),
                )
            task_succeeded(
                "consensus-watch-scheduler",
                watches_ran=watches_ran,
                briefs_sent=briefs_sent,
                notifications=outbox_counts,
            )
            try:
                await asyncio.wait_for(wake_event.wait(), timeout=TICK_SECONDS)
            except asyncio.TimeoutError:
                pass
    finally:
        if _scheduler_wake_event is wake_event:
            _scheduler_wake_event = None
