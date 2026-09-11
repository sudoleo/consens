"""Background source checking: persistent packages, bounded active work.

User API keys only live in this process. After restart an own-key job pauses
until its authenticated owner supplies the key again; it never switches to a
developer key. Shared caches are tenant-scoped and contain no credentials.
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
import threading
import time
import uuid
from collections import deque
from contextlib import contextmanager
from dataclasses import asdict, replace

from app.core.background_tasks import task_succeeded
from app.core.observability import correlation_scope, record_metric, safe_exception
from app.services.source_check_repository import (
    SourceCheckRepository, SourceCheckNotFound, SourceCheckResourceGone, SourceCheckQueueMismatch,
    compact, digest, utcnow,
)
from app.services.persistence_guard import AccountDeletionInProgress

_context = contextvars.ContextVar('source_check_context', default=None)
_keys = {}
_keys_lock = threading.Lock()
_active_owners = set()
_active_lock = threading.Lock()
_repository = None
WORKER_ID = uuid.uuid4().hex
_heartbeat_lock = threading.Lock()
_heartbeats = {}
_scan_lock = threading.Lock()
_scans = {}


def repository():
    global _repository
    if _repository is None:
        from app.core.security import db_firestore
        _repository = SourceCheckRepository(db_firestore)
    return _repository


@contextmanager
def source_check_context(uid, run_key, *, own_keys=False, references=(), origin='interactive'):
    token = _context.set(dict(uid=uid, run_key=run_key, own_keys=own_keys,
                             references=list(references), origin=origin))
    try:
        yield
    finally:
        _context.reset(token)


def current_context():
    return _context.get()


def remember_key(job_id, uid, key):
    if not key or len(key) > 4096:
        raise ValueError('Invalid API key')
    purge_expired_keys()
    with _keys_lock:
        _keys[job_id] = (uid, key, time.monotonic() + 24 * 3600)


def purge_expired_keys():
    with _keys_lock:
        now = time.monotonic()
        for job_id in [key for key, value in _keys.items() if value[2] <= now]:
            _keys.pop(job_id, None)


def forget_key(job_id):
    with _keys_lock:
        _keys.pop(job_id, None)


def _refresh_worker(repo, *, force=False):
    # The independent heartbeat clears idle credentials even without another
    # submission, and before any database failure can interrupt the refresh.
    purge_expired_keys()
    with _heartbeat_lock:
        last = _heartbeats.get((id(repo), WORKER_ID), float('-inf'))
        if force or time.monotonic() - last >= 10:
            repo.heartbeat_worker(WORKER_ID)
            _heartbeats[(id(repo), WORKER_ID)] = time.monotonic()


def resume_source_check(job_id, uid, key):
    repo = repository()
    job = repo.get(job_id, uid)
    if job.get('credential_mode') != 'own':
        return job
    if not repo.owns_queue(job):
        raise SourceCheckQueueMismatch('Source check belongs to a different worker queue')
    _refresh_worker(repo, force=True)
    remember_key(job_id, uid, key)
    resumed = repo.resume(job_id, uid, worker_id=WORKER_ID)
    # A running package retains its credential process until the lease ends.
    # A POST served by another node must not interrupt that in-flight call.
    if resumed.get('credential_worker_id') != WORKER_ID or resumed['status'] in ('complete', 'partial', 'skipped', 'failed'):
        forget_key(job_id)
    return resumed


def submit_source_check(*, question, consensus, sources, keys, resolved_question='', context=None,
                        differences_data=None, model_answers=None, model_sources=None, run_id=''):
    from app.services.source_verification import Limits, plan_source_verification
    from app.services.llm.credentials import openrouter_api_key
    context = context or current_context()
    if not context or not context.get('uid'):
        raise ValueError('Source check requires an owner context')
    if context.get('origin', 'interactive') != 'interactive':
        return None
    limits = Limits.configured()
    plan = plan_source_verification(question=question, consensus=consensus, sources=sources,
        resolved_question=resolved_question, limits=limits, differences_data=differences_data,
        model_answers=model_answers, model_sources=model_sources, run_id=str(context['run_key']))
    if not plan['packages']:
        return plan['snapshot']
    from app.services.llm.mock_llm import mock_llm_enabled
    if mock_llm_enabled():
        from app.services.source_verification import verify_sources
        return verify_sources(question=question, consensus=consensus, sources=sources,
            keys={}, resolved_question=resolved_question,
            differences_data=differences_data, model_answers=model_answers,
            model_sources=model_sources, run_id=str(context['run_key']),
            fetch=lambda *_: (_ for _ in ()).throw(ValueError('mock_unavailable')))
    plan['limits'] = asdict(limits)
    # Admission accepts the entire bounded plan atomically, before any paid work.
    repo = repository()
    if context.get('own_keys'):
        _refresh_worker(repo, force=True)
    job = repo.create(uid=context['uid'], run_key=context['run_key'], plan=plan,
        credential_mode='own' if context.get('own_keys') else 'server',
        references=context.get('references', ()), origin=context.get('origin', 'interactive'),
        credential_worker_id=WORKER_ID if context.get('own_keys') else None)
    if context.get('own_keys') and job['status'] not in ('complete', 'partial', 'skipped'):
        key = openrouter_api_key(keys)
        if key:
            job = resume_source_check(job['job_id'], context['uid'], key)
    record_metric('source_check', 'accepted', processed=job['package_count'])
    # The response is a small durable reference. The paginated endpoint exposes
    # every planned pair, including ones that are still waiting for a worker.
    return {**job['snapshot'], 'findings': [], 'documents': [], 'sources': []}


def unavailable_snapshot(consensus, code='persistence_error', *, check_type='source_evidence', run_id=''):
    from app.services.source_verification import answer_version, collect_claims, PROMPT_VERSION
    if check_type == 'contradiction_evidence':
        from app.services.contradiction_verification import PROMPT_VERSION as contradiction_prompt_version
        return dict(schema_version=4, check_type=check_type, prompt_version=contradiction_prompt_version,
            run_id=run_id, answer_version=answer_version(consensus), status='failed',
            findings=[], documents=[], sources=[], reason_code=code,
            scope={'contradictions': 0, 'checked_contradictions': 0, 'omitted_contradictions': 0,
                   'unavailable_contradictions': 0}, runtime={'error_code': code})
    claims = collect_claims(consensus, [])
    pairs = sum(len(c['source_ids']) for c in claims)
    return dict(schema_version=3, check_type='source_evidence', prompt_version=PROMPT_VERSION,
        answer_version=answer_version(consensus), status='failed', findings=[], documents=[], sources=[],
        scope={'pairs': pairs, 'checked_pairs': 0, 'processed_pairs': 0}, runtime={'error_code': code})


def disabled_snapshot(consensus):
    result = unavailable_snapshot(consensus, 'disabled', check_type='contradiction_evidence')
    result.update(status='disabled', runtime={})
    return result


def submit_advisory(**kwargs):
    try:
        return submit_source_check(**kwargs)
    except (AccountDeletionInProgress, SourceCheckResourceGone):
        raise
    except Exception as exc:
        logging.warning('Source check persistence failed category=%s', safe_exception(exc))
        record_metric('source_check', 'persistence', outcome='failure')
        context = kwargs.get('context') or current_context() or {}
        return unavailable_snapshot(kwargs['consensus'],
            check_type='contradiction_evidence' if kwargs.get('differences_data') is not None else 'source_evidence',
            run_id=str(context.get('run_key') or ''))


def _cache_rpc_fits(bounded):
    if not bounded:
        return True
    from app.services.llm.provider_runtime import current_analysis_budget
    from app.services.source_check_repository import RPC_SECONDS
    budget = current_analysis_budget()
    return budget is None or budget.deadline - time.monotonic() > RPC_SECONDS + .1


def _cache_write(uid, repo, key, value, seconds, *, bounded=False, deferred=None):
    from app.services.llm.provider_runtime import current_analysis_budget
    if bounded and current_analysis_budget() is not None:
        # A guarded cache transaction spans several RPCs/retries. It cannot be
        # bounded by the per-RPC timeout, so execute it only after result commit.
        if deferred is not None:
            deferred.append((key, value, seconds))
        return
    try:
        repo.cache_put(uid, key, value, seconds=seconds)
    except Exception:
        record_metric('source_cache', 'write', outcome='failure')


def _cached_fetch(uid, repo, *, bounded=False, deferred=None):
    from app.services.source_documents import fetch_document
    def fetch(url, limits):
        key = ['document-v3', url, limits.max_bytes]
        try:
            cached = repo.cache_get(uid, key) if _cache_rpc_fits(bounded) else None
            if cached is not None:
                record_metric('source_cache', 'document_hit')
                return cached
        except Exception:
            record_metric('source_cache', 'read', outcome='failure')
        if bounded:
            from app.services.llm.provider_runtime import current_analysis_budget
            budget = current_analysis_budget()
            if budget:
                budget.check()
                limits = replace(limits, fetch_seconds=min(limits.fetch_seconds,
                    max(.01, budget.deadline - time.monotonic())))
        value = fetch_document(url, limits)
        _cache_write(uid, repo, key, value, limits.cache_seconds, bounded=bounded, deferred=deferred)
        return value
    return fetch


def _cached_judge(uid, repo, *, deferred=None):
    from app.services.source_verification import judge_sources, SYSTEM, PROMPT_VERSION
    def judge(payload, keys, limits):
        # Includes applicability date/question and model/prompt contract. Cached
        # raw output is still validated against this package's exact passages.
        contradiction = payload.get('check_type') == 'contradiction_evidence'
        if contradiction:
            from app.services.contradiction_verification import judge_contradictions, SYSTEM as system, PROMPT_VERSION as prompt_version
            call = judge_contradictions
        else:
            call, system, prompt_version = judge_sources, SYSTEM, PROMPT_VERSION
        key = ['verdict-dispatch-v1', 'v4' if contradiction else 'v3', prompt_version, system, limits.model, limits.fallback_model,
               payload, limits.output_tokens]
        try:
            cached = repo.cache_get(uid, key) if _cache_rpc_fits(contradiction) else None
            if cached is not None:
                record_metric('source_cache', 'judge_hit')
                return cached['output'], {**cached.get('provenance', {}), 'calls': 0, 'cache_hit': True}
        except Exception:
            record_metric('source_cache', 'read', outcome='failure')
        raw, usage = call(payload, keys, limits)
        if not usage.get('output_truncated'):
            provenance = {k: usage[k] for k in ('model', 'fallback_used', 'model_attempts') if k in usage}
            _cache_write(uid, repo, key, {'output': raw, 'provenance': provenance}, 3600,
                         bounded=contradiction, deferred=deferred)
        return raw, usage
    return judge


def interrupted_package(plan, package, failure=None):
    code = 'worker_interrupted'
    if isinstance(failure, dict) and failure.get('reason_code') in (
            'worker_preparation_failed', 'worker_execution_failed', 'result_persistence_failed'):
        code = failure['reason_code']
    if package.get('mode') == 'contradiction_evidence':
        from app.services.contradiction_verification import package_failure_snapshot
        return package_failure_snapshot(plan, package, code)
    from app.services.source_verification import _snapshot, _pending, _finish_snapshot, _now
    result = _snapshot(plan['snapshot']['answer_version'], package['pairs'], package.get('sources', []),
                       model=plan['snapshot'].get('model'))
    result.update(package_id=package['id'], checked_at=_now(),
                  findings=[{**_pending(pair, code), 'checked_at': _now()}
                            for pair in package['pairs']],
                  runtime={'calls': 0, 'duration_ms': 0, 'error_code': code})
    return _finish_snapshot(result)


def _retryable_fetch_only(result):
    """Retry transient retrieval only; never repeat a paid/uncertain judge call."""
    if result.get('check_type') == 'contradiction_evidence':
        # One admitted v4 package is the total fetch/call/time budget; a failed
        # side remains visible instead of multiplying that budget on retry.
        return False
    transient = {'fetch_timeout', 'rate_limited', 'upstream_error', 'network_error',
                 'dns_busy', 'incomplete_document'}
    findings = result.get('findings') or []
    return (bool(findings) and result.get('runtime', {}).get('calls', 0) == 0
            and all(not f.get('checked') and f.get('reason_code') in transient for f in findings))


def _due_candidates(repo):
    """Rotate bounded batches; foreign own-key jobs cannot hide later ready work."""
    fetched = False
    for _ in range(24):
        with _scan_lock:
            state = _scans.setdefault((id(repo), WORKER_ID), {'cursor': None, 'pending': deque(), 'cutoff': None})
            if not state['pending']:
                if fetched:
                    return
                if state['cursor'] is None:
                    state['cutoff'] = utcnow()
                rows, cursor = repo.due_page(limit=24, cursor=state['cursor'], now=state['cutoff'])
                state['cursor'] = cursor
                state['pending'].extend(rows)
                fetched = True
                if not state['pending']:
                    return
            candidate = state['pending'].popleft()
        yield candidate


def process_one(repo=None):
    from app.services.source_verification import Limits, execute_source_package
    from app.services.llm.credentials import resolve_developer_api_keys
    repo = repo or repository()
    try:
        _refresh_worker(repo)
    except Exception as exc:
        logging.warning('Source worker heartbeat failed category=%s', safe_exception(exc))
        record_metric('source_queue', 'heartbeat', outcome='failure')
        return False
    for candidate in _due_candidates(repo):
        uid = candidate['uid']
        with _active_lock:
            if uid in _active_owners:
                continue
            _active_owners.add(uid)
        claimed = None
        failure_code = 'worker_preparation_failed'
        try:
            claimed = repo.claim(candidate['job_id'], worker_id=WORKER_ID)
            if not claimed:
                continue
            if claimed['credential_mode'] == 'own':
                with _keys_lock:
                    saved = _keys.get(claimed['job_id'])
                if not saved or saved[0] != uid or saved[2] <= time.monotonic():
                    repo.pause_credentials(claimed)
                    return True
                keys = {'OpenRouter': saved[1]}
            else:
                keys = resolve_developer_api_keys()
            plan = repo.get_plan(claimed['job_id'])
            # The accepted plan owns its model for its entire lifetime. Legacy
            # plans already recorded the actual model in their snapshot.
            plan_limits = dict(plan['limits'])
            plan_limits['model'] = plan['snapshot'].get('model') or plan_limits.get('model') or Limits().model
            # Jobs admitted before the fallback option remain single-model jobs.
            plan_limits.setdefault('fallback_model', '')
            package = plan['packages'][claimed['completed_packages']]
            contradiction = package.get('mode') == 'contradiction_evidence'
            cache_writes = []
            with correlation_scope(prefix='source'):
                if claimed.get('attempts', 0) > (1 if contradiction else 3):
                    failure = claimed.get('last_failure') or {}
                    if failure.get('package_index') != claimed['completed_packages']:
                        failure = None
                    result = interrupted_package(plan, package, failure)
                else:
                    limits = Limits(**plan_limits)
                    failure_code = 'worker_execution_failed'
                    result = execute_source_package(package=package,
                        question=plan['question'], resolved_question=plan.get('resolved_question', ''),
                        answer_version=plan['snapshot']['answer_version'], keys=keys,
                        limits=limits,
                        fetch=_cached_fetch(uid, repo, bounded=contradiction, deferred=cache_writes),
                        judge=_cached_judge(uid, repo, deferred=cache_writes))
                if claimed.get('attempts', 0) < 3 and _retryable_fetch_only(result):
                    # Wait past the local negative-cache TTL before trying this
                    # document again. Other owners/jobs can use this worker meanwhile.
                    repo.retry(claimed, delay=31)
                    record_metric('source_queue', 'fetch_retry', retries=1)
                    return True
                failure_code = 'result_persistence_failed'
                if repo.finish_package(claimed, result):
                    record_metric('source_queue', 'package', processed=len(result.get('findings', [])))
                    for key, value, seconds in cache_writes:
                        _cache_write(uid, repo, key, value, seconds)
            if claimed['completed_packages'] + 1 == claimed['package_count']:
                forget_key(claimed['job_id'])
            return True
        except (AccountDeletionInProgress, SourceCheckResourceGone):
            # Cleanup is idempotent and intentionally bypasses owner fences.
            repo.delete(candidate['job_id'])
            forget_key(candidate['job_id'])
        except Exception as exc:
            logging.warning('Source worker failed job=%s phase=%s category=%s',
                            candidate['job_id'], failure_code, safe_exception(exc))
            record_metric('source_queue', 'worker', outcome='failure')
            if claimed:
                # Retry infrastructure failures, bounded by the persisted attempt
                # counter. Retried v4 work reports an uncertain prior outcome;
                # it must not issue another paid call after a failed commit.
                repo.retry(claimed, delay=15, failure={
                    'reason_code': failure_code,
                    'package_index': claimed['completed_packages']})
            return False
        finally:
            with _active_lock:
                _active_owners.discard(uid)
    return False


async def source_check_worker_loop():
    from app.services.llm.mock_llm import mock_llm_enabled
    async def worker():
        while True:
            if not mock_llm_enabled():
                worked = await asyncio.to_thread(process_one)
                task_succeeded('source-check-workers')
            else:
                worked = False
            await asyncio.sleep(.1 if worked else 2)
    # No unbounded executor queue: each loop submits at most one package.
    async def heartbeat():
        while True:
            if not mock_llm_enabled():
                try:
                    await asyncio.to_thread(_refresh_worker, repository())
                except Exception as exc:
                    logging.warning('Source worker heartbeat failed category=%s', safe_exception(exc))
                    record_metric('source_queue', 'heartbeat', outcome='failure')
            await asyncio.sleep(10)
    workers = [asyncio.create_task(worker()) for _ in range(4)]
    # Independent liveness continues while every package worker awaits a model.
    workers.append(asyncio.create_task(heartbeat()))
    try:
        await asyncio.gather(*workers)
    finally:
        for item in workers:
            item.cancel()
        await asyncio.gather(*workers, return_exceptions=True)


def retain_source_check(snapshot, uid, path, db=None):
    if not isinstance(snapshot, dict) or not snapshot.get('job_id'):
        return
    repo = SourceCheckRepository(db) if db is not None else repository()
    repo.retain(snapshot['job_id'], uid, path)
