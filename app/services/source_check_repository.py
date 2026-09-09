"""Durable, owner-bound source-check packages and leased work.

Only server-created plans enter this repository. Credentials never do. The
small job header is separate from compressed plans and package results so
queue scans and polling do not read an entire research document.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import uuid
import zlib
from datetime import datetime, timedelta, timezone

from google.cloud.firestore_v1.base_query import FieldFilter
from google.api_core.retry import Retry
from firebase_admin import firestore

from app.services import persistence_guard as guard

COLLECTION = 'source_check_jobs'
CACHE_COLLECTION = 'source_check_cache'
WORKER_COLLECTION = 'source_check_workers'
CREDENTIAL_AFFINITY_SECONDS = 30
ACTIVE = {'queued', 'running'}
TERMINAL = {'complete', 'partial', 'failed', 'skipped', 'cancelled'}
LEASE_SECONDS = 300
PAGE_PACKAGES = 4
MAX_PACKED_BYTES = 700_000
_ID = re.compile(r'^[a-f0-9]{64}$')


RPC_SECONDS = 5.0
TRANSACTION_ATTEMPTS = 3
_READ_OPTIONS = {'retry': None, 'timeout': RPC_SECONDS}
# An explicit false predicate also disables the SDK's stream-restart loop;
# retry=None would cause that SDK iterator to dereference None after an error.
_STREAM_OPTIONS = {'retry': Retry(predicate=lambda _: False), 'timeout': RPC_SECONDS}


class SourceCheckNotFound(ValueError):
    pass


class SourceCheckRevisionChanged(ValueError):
    pass


class SourceCheckResourceGone(ValueError):
    pass


def utcnow():
    return datetime.now(timezone.utc)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def pack(value):
    result = base64.b64encode(zlib.compress(json.dumps(value, ensure_ascii=False,
        separators=(',', ':')).encode())).decode('ascii')
    if len(result) > MAX_PACKED_BYTES:
        raise ValueError('source_plan_too_large')
    return result


def unpack(value):
    # Only bounded, server-written compressed plans/results are read here.
    return json.loads(zlib.decompress(base64.b64decode(value)))


def compact(snapshot):
    return {k: v for k, v in snapshot.items() if k not in ('findings', 'documents', 'sources')}


def _complete_result(plan, package, result):
    """Commit exactly one result per planned pair, even for malformed workers."""
    result = result if isinstance(result, dict) else {}
    matches = {}
    valid_version = (result.get('answer_version') == plan['snapshot']['answer_version']
                     and result.get('package_id', package['id']) == package['id'])
    for finding in result.get('findings', []) if isinstance(result.get('findings'), list) else []:
        if isinstance(finding, dict):
            key = (finding.get('sentence_id'), finding.get('source_id'))
            if type(key[0]) is int and isinstance(key[1], str):
                matches.setdefault(key, []).append(finding)
    findings = []
    for pair in package['pairs']:
        rows = matches.get((pair['sentence_id'], pair['source_id']), [])
        if valid_version and len(rows) == 1:
            finding = {**rows[0], **pair}
            checked = finding.get('checked') is True
            finding.update(checked=checked, pending=False, state='checked' if checked else 'unavailable')
        else:
            finding = {**pair, 'checked': False, 'pending': False, 'state': 'unavailable',
                       'support': 'unknown', 'topical': 'unknown', 'temporal': 'unknown',
                       'reason': '', 'reason_code': 'invalid_output', 'quotes': []}
        findings.append(finding)
    ids = {pair['source_id'] for pair in package['pairs']}
    documents = [doc for doc in result.get('documents', []) if isinstance(doc, dict)
                 and isinstance(doc.get('source_id'), str) and doc['source_id'] in ids
                 ] if valid_version and isinstance(result.get('documents'), list) else []
    runtime = result.get('runtime') if isinstance(result.get('runtime'), dict) else {}
    return {**result, 'answer_version': plan['snapshot']['answer_version'], 'package_id': package['id'],
            'findings': findings, 'documents': documents, 'sources': package.get('sources', []), 'runtime': runtime}


class SourceCheckRepository:
    def __init__(self, db):
        self.db = db

    def ref(self, job_id):
        if not _ID.fullmatch(str(job_id)):
            raise SourceCheckNotFound('Source check not found')
        return self.db.collection(COLLECTION).document(job_id)

    def _transaction(self, operation):
        if hasattr(self.db, 'run_transaction'):
            return self.db.run_transaction(operation)
        if not hasattr(self.db, 'transaction'):
            return operation(None)
        # Public SDK APIs bound contention retries. Begin/commit/rollback do not
        # expose per-RPC timeout parameters in this SDK, so this is not a total
        # transaction deadline. Shared owner-tombstone guard reads also retain
        # their existing timeout policy.
        transaction = self.db.transaction(max_attempts=TRANSACTION_ATTEMPTS)
        @firestore.transactional
        def run(tx):
            return operation(tx)
        return run(transaction)

    def _fence(self, tx, job):
        guard.ensure_account_write_allowed(uid=job['uid'], db=self.db, transaction=tx)
        chat_paths = [path for path in job.get('references', []) if '/chats/' in path]
        if chat_paths:
            live = False
            for path in job.get('references', []):
                if self._reference_live(path, transaction=tx):
                    live = True
            if not live:
                raise SourceCheckResourceGone('Source-check parent was deleted')

    def _reference_live(self, path, *, transaction=None):
        # A turn document cannot keep work alive while its chat is deleting.
        parts = path.split('/')
        if 'chats' in parts:
            root_length = parts.index('chats') + 2
            if len(parts) > root_length:
                if not self._reference_live('/'.join(parts[:root_length]), transaction=transaction):
                    return False
        snap = self.db.document(path).get(transaction=transaction, **_READ_OPTIONS)
        return bool(snap.exists and (snap.to_dict() or {}).get('status') not in
                    ('deleting', 'revoked', 'blocked', 'deleted'))

    def create(self, *, uid, run_key, plan, credential_mode='server', references=(), origin='interactive', credential_worker_id=None):
        job_id = digest([uid, run_key, plan['snapshot']['answer_version'],
                         plan['snapshot'].get('prompt_version'), plan.get('sources', plan['snapshot'].get('sources'))])
        ref = self.ref(job_id)
        payload = pack(plan)
        now = utcnow()
        snapshot = compact(plan['snapshot'])
        snapshot.update(job_id=job_id, status='queued' if plan['packages'] else 'skipped',
                        credential_mode=credential_mode, revision=0)
        job = dict(uid=uid, job_id=job_id, origin=origin, credential_mode=credential_mode,
            status=snapshot['status'], snapshot=snapshot, package_count=len(plan['packages']),
            completed_packages=0, revision=0, created_at=now, updated_at=now,
            next_attempt_at=now if plan['packages'] else None, lease_token=None,
            references=list(dict.fromkeys(references)), cleanup_at=now + timedelta(days=30))
        totals, statements = {}, {}
        for package in plan['packages']:
            for pair in package['pairs']:
                sid = pair['source_id']
                totals[sid] = totals.get(sid, 0) + 1
                statement = str(pair['sentence_id'])
                statements[statement] = statements.get(statement, 0) + 1
        if credential_mode == 'own' and credential_worker_id:
            job['credential_worker_id'] = credential_worker_id
        job['source_totals'] = totals
        job['statement_totals'] = statements

        def operation(tx):
            self._fence(tx, job)
            existing = ref.get(transaction=tx, **_READ_OPTIONS)
            if existing.exists:
                data = existing.to_dict()
                if data.get('status') == 'deleting':
                    raise SourceCheckResourceGone('Source check is being deleted')
                return data
            tx.set(ref, job)
            tx.set(ref.collection('data').document('plan'), {'payload': payload})
            return job
        return self._transaction(operation)

    def get(self, job_id, uid=None):
        snap = self.ref(job_id).get(**_READ_OPTIONS)
        job = snap.to_dict() if snap.exists else None
        if not job or (uid is not None and job['uid'] != uid) or job.get('status') == 'deleting':
            raise SourceCheckNotFound('Source check not found')
        return job

    def get_plan(self, job_id):
        snap = self.ref(job_id).collection('data').document('plan').get(**_READ_OPTIONS)
        if not snap.exists:
            raise SourceCheckNotFound('Source check not found')
        return unpack(snap.to_dict()['payload'])

    def due(self, limit=24, now=None):
        return self.due_page(limit=limit, now=now)[0]

    def due_page(self, limit=24, now=None, cursor=None):
        # Snapshot cursors include Firestore's implicit document-ID tie-breaker;
        # no cursor document re-read or additional composite index is needed.
        now = now or utcnow()
        limit = max(1, min(int(limit), 100))
        query = self.db.collection(COLLECTION).where(filter=FieldFilter(
            'next_attempt_at', '>', datetime(2000, 1, 1, tzinfo=timezone.utc))).where(filter=FieldFilter(
            'next_attempt_at', '<=', now)).order_by('next_attempt_at').limit(limit)
        if cursor is not None:
            query = query.start_after(cursor)
        rows = list(query.stream(**_STREAM_OPTIONS))
        jobs = [s.to_dict() for s in rows if (s.to_dict() or {}).get('status') in ACTIVE]
        return jobs, rows[-1] if len(rows) == limit else None

    def heartbeat_worker(self, worker_id, *, now=None):
        # Process identity is a random non-secret epoch, never a credential.
        if not re.fullmatch(r'[a-f0-9]{32}', str(worker_id)):
            raise ValueError('invalid_worker_id')
        now = now or utcnow()
        self.db.collection(WORKER_COLLECTION).document(worker_id).set(
            {'expires_at': now + timedelta(seconds=CREDENTIAL_AFFINITY_SECONDS)}, **_READ_OPTIONS)

    def claim(self, job_id, *, now=None, worker_id=None):
        ref = self.ref(job_id)
        now = now or utcnow()
        token = uuid.uuid4().hex

        def operation(tx):
            snap = ref.get(transaction=tx, **_READ_OPTIONS)
            if not snap.exists:
                return None
            job = snap.to_dict()
            self._fence(tx, job)
            if job['status'] not in ACTIVE or not job.get('next_attempt_at') or job['next_attempt_at'] > now:
                return None
            affinity = job.get('credential_worker_id')
            if job.get('credential_mode') == 'own' and affinity and affinity != worker_id:
                heartbeat = self.db.collection(WORKER_COLLECTION).document(affinity).get(transaction=tx, **_READ_OPTIONS)
                if heartbeat.exists and heartbeat.to_dict().get('expires_at', now) > now:
                    return None
                # The owning process disappeared. Persist an honest pause without
                # spending a package attempt or ever trying a developer credential.
                revision = job['revision'] + 1
                tx.update(ref, dict(status='awaiting_credentials', next_attempt_at=None,
                    lease_token=None, revision=revision, updated_at=now,
                    snapshot={**job['snapshot'], 'status': 'awaiting_credentials', 'revision': revision}))
                return None
            # A crashed package may be replayed; result commits are fenced by
            # this lease token. Already completed packages are never rerun.
            revision = job['revision'] + 1
            update = dict(status='running', lease_token=token, updated_at=now, revision=revision,
                snapshot={**job['snapshot'], 'status': 'running', 'revision': revision},
                attempts=job.get('attempts', 0) + 1,
                next_attempt_at=now + timedelta(seconds=LEASE_SECONDS))
            tx.update(ref, update)
            return {**job, **update}
        return self._transaction(operation)

    def finish_package(self, claimed, result, *, now=None):
        ref = self.ref(claimed['job_id'])
        now = now or utcnow()
        index = claimed['completed_packages']

        def operation(tx):
            snap = ref.get(transaction=tx, **_READ_OPTIONS)
            if not snap.exists:
                return False
            job = snap.to_dict()
            self._fence(tx, job)
            if (job['status'] != 'running' or job.get('lease_token') != claimed['lease_token']
                    or job['completed_packages'] != index):
                return False
            plan_snap = ref.collection('data').document('plan').get(transaction=tx, **_READ_OPTIONS)
            if not plan_snap.exists:
                raise SourceCheckNotFound('Source check plan not found')
            plan = unpack(plan_snap.to_dict()['payload'])
            completed_result = _complete_result(plan, plan['packages'][index], result)
            payload = pack(completed_result)
            old = job['snapshot']
            summary = dict(old)
            scope = dict(old.get('scope') or {})
            findings = completed_result['findings']
            checked = sum(bool(f.get('checked')) for f in findings)
            scope['processed_pairs'] = scope.get('processed_pairs', 0) + len(findings)
            scope['checked_pairs'] = scope.get('checked_pairs', 0) + checked
            # Per-source totals survive multiple packages for the same URL.
            progress = dict(job.get('source_progress') or {})
            statement_progress = dict(job.get('statement_progress') or {})
            for finding in findings:
                sid = finding['source_id']
                counter = dict(progress.get(sid) or {'processed': 0, 'checked': 0})
                counter['processed'] += 1
                counter['checked'] += int(bool(finding.get('checked')))
                progress[sid] = counter
                statement = str(finding['sentence_id'])
                statement_progress[statement] = statement_progress.get(statement, 0) + int(bool(finding.get('checked')))
            for field in ('issues', 'unknown_pairs', 'unavailable_pairs'):
                scope.setdefault(field, 0)
            scope['issues'] += sum(bool(f.get('checked')) and (f.get('support') in ('partial', 'contradicted')
                or f.get('topical') == 'off_topic' or f.get('temporal') == 'outdated') for f in findings)
            scope['unknown_pairs'] += sum(bool(f.get('checked')) and (f.get('support') == 'unknown'
                or f.get('temporal') == 'unknown' or f.get('topical') == 'unknown') for f in findings)
            scope['unavailable_pairs'] += len(findings) - checked
            totals = job.get('source_totals') or {}
            scope['processed_sources'] = sum(progress.get(sid, {}).get('processed', 0) >= count for sid, count in totals.items())
            scope['checked_sources'] = sum(progress.get(sid, {}).get('checked', 0) >= count for sid, count in totals.items())
            scope['checked_statements'] = sum(statement_progress.get(sid, 0) >= count
                                              for sid, count in job.get('statement_totals', {}).items())
            fetched_documents = dict(job.get('fetched_documents') or {})
            for document in completed_result['documents']:
                url = document.get('source_url') or document.get('url')
                if url:
                    key = digest(url)
                    # Content identity excludes access times and other volatile metadata.
                    hashes = list(fetched_documents.get(key, []))
                    content_hash = document.get('content_hash')
                    if isinstance(content_hash, str) and content_hash and content_hash not in hashes:
                        hashes.append(content_hash)
                    fetched_documents[key] = sorted(hashes)
            scope['fetched_sources'] = len(fetched_documents)
            completed = index + 1
            status = 'queued'
            if completed == job['package_count']:
                status = 'complete' if scope['checked_pairs'] == scope.get('pairs', 0) else 'partial'
            revision = job['revision'] + 1
            runtime = dict(summary.get('runtime') or {})
            for name in ('calls', 'duration_ms', 'prompt_tokens', 'completion_tokens', 'cost'):
                value = (completed_result.get('runtime') or {}).get(name)
                if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                    runtime[name] = runtime.get(name, 0) + value
            summary.update(status=status, revision=revision, scope=scope, runtime=runtime,
                           checked_at=now.isoformat(), source_version=digest(sorted(fetched_documents.items())))
            tx.set(ref.collection('packages').document(f'{index:06d}'), {'payload': payload})
            tx.update(ref, dict(status=status, snapshot=summary, revision=revision,
                completed_packages=completed, source_progress=progress, statement_progress=statement_progress,
                fetched_documents=fetched_documents, updated_at=now,
                next_attempt_at=now if status == 'queued' else None, lease_token=None, attempts=0))
            return True
        return self._transaction(operation)

    def set_source_totals(self, job_id, uid, totals):
        ref = self.ref(job_id)
        def operation(tx):
            guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            snap = ref.get(transaction=tx, **_READ_OPTIONS)
            if snap.exists and snap.to_dict()['uid'] == uid and not snap.to_dict().get('source_totals'):
                tx.update(ref, {'source_totals': totals})
        self._transaction(operation)

    def pause_credentials(self, claimed):
        return self._change_claim(claimed, 'awaiting_credentials', None)

    def retry(self, claimed, delay=10):
        return self._change_claim(claimed, 'queued', utcnow() + timedelta(seconds=delay))

    def _change_claim(self, claimed, status, next_at):
        ref = self.ref(claimed['job_id'])
        def operation(tx):
            snap = ref.get(transaction=tx, **_READ_OPTIONS)
            if not snap.exists:
                return False
            job = snap.to_dict()
            self._fence(tx, job)
            if job['status'] != 'running' or job.get('lease_token') != claimed['lease_token']:
                return False
            revision = job['revision'] + 1
            tx.update(ref, dict(status=status, next_attempt_at=next_at, lease_token=None,
                attempts=max(0, job.get('attempts', 0) - int(status == 'awaiting_credentials')),
                revision=revision, updated_at=utcnow(),
                snapshot={**job['snapshot'], 'status': status, 'revision': revision}))
            return True
        return self._transaction(operation)

    def resume(self, job_id, uid, *, worker_id=None):
        ref = self.ref(job_id)
        def operation(tx):
            guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            snap = ref.get(transaction=tx, **_READ_OPTIONS)
            if not snap.exists or snap.to_dict()['uid'] != uid:
                raise SourceCheckNotFound('Source check not found')
            job = snap.to_dict()
            if job.get('status') == 'deleting':
                raise SourceCheckResourceGone('Source check is being deleted')
            self._fence(tx, job)
            if job['credential_mode'] != 'own' or job['status'] not in ('awaiting_credentials', 'queued'):
                return job
            if worker_id is None and job['status'] == 'queued':
                return job
            revision = job['revision'] + 1
            update = dict(status='queued', next_attempt_at=utcnow(), revision=revision,
                snapshot={**job['snapshot'], 'status': 'queued', 'revision': revision})
            if worker_id:
                update['credential_worker_id'] = worker_id
            tx.update(ref, update)
            return {**job, **update}
        return self._transaction(operation)

    def page(self, job_id, *, uid=None, cursor=0, revision=None):
        job = self.get(job_id, uid)
        if revision is not None and job['revision'] != revision:
            raise SourceCheckRevisionChanged('Source check changed; reload first page')
        plan = self.get_plan(job_id)
        count = len(plan['packages'])
        if not 0 <= cursor <= count:
            raise ValueError('Invalid source-check cursor')
        stop = min(cursor + PAGE_PACKAGES, count)
        findings, documents, sources = [], {}, {}
        for index in range(cursor, stop):
            package = plan['packages'][index]
            stored = None
            if index < job['completed_packages']:
                snap = self.ref(job_id).collection('packages').document(f'{index:06d}').get(**_READ_OPTIONS)
                if snap.exists:
                    stored = unpack(snap.to_dict()['payload'])
            if stored:
                findings.extend(stored.get('findings', []))
                for doc in stored.get('documents', []):
                    documents[doc['source_id']] = doc
            else:
                findings.extend({**pair, 'checked': False, 'pending': job['status'] in ACTIVE,
                    'support': 'unknown', 'topical': 'unknown', 'temporal': 'unknown',
                    'reason': '', 'reason_code': 'awaiting_credentials' if job['status'] == 'awaiting_credentials' else 'pending',
                    'quotes': []} for pair in package['pairs'])
            for source in package.get('sources', []):
                sources[source['id']] = source
        # Avoid stitching pages from different versions during a package commit.
        if self.get(job_id, uid)['revision'] != job['revision']:
            raise SourceCheckRevisionChanged('Source check changed; reload first page')
        return {'source_verification': {**job['snapshot'], 'findings': findings,
                    'documents': list(documents.values()), 'sources': list(sources.values())},
                'next_cursor': str(stop) if stop < count else None}

    def retain(self, job_id, uid, path):
        ref = self.ref(job_id)
        def operation(tx):
            guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            snap = ref.get(transaction=tx, **_READ_OPTIONS)
            if not snap.exists or snap.to_dict()['uid'] != uid:
                return
            job = snap.to_dict()
            if job.get('status') == 'deleting':
                raise SourceCheckResourceGone('Source check is being deleted')
            references = list(job.get('references') or [])
            if not self._reference_live(path, transaction=tx):
                raise SourceCheckResourceGone('Source-check reference was deleted')
            if path not in references:
                references.append(path)
                self._fence(tx, {**job, 'references': references})
                tx.update(ref, {'references': references, 'cleanup_at': utcnow() + timedelta(days=30)})
        self._transaction(operation)

    def delete(self, job_id, *, only_if_expired_at=None):
        ref = self.ref(job_id)
        # The marker fences any in-flight worker before deleting descendants.
        def mark(tx):
            snap = ref.get(transaction=tx, **_READ_OPTIONS)
            if snap.exists:
                job = snap.to_dict()
                if only_if_expired_at is not None:
                    if job.get('cleanup_at') is None or job['cleanup_at'] > only_if_expired_at:
                        return False
                    if any(self._reference_live(path, transaction=tx) for path in job.get('references', [])):
                        return False
                tx.update(ref, {'status': 'deleting', 'next_attempt_at': None})
            return True
        if not self._transaction(mark):
            return False
        for name in ('data', 'packages'):
            for snap in ref.collection(name).stream(**_STREAM_OPTIONS):
                snap.reference.delete(**_READ_OPTIONS)
        ref.delete(**_READ_OPTIONS)
        return True

    def delete_owner(self, uid):
        for snap in self.db.collection(COLLECTION).where(filter=FieldFilter('uid', '==', uid)).stream(**_STREAM_OPTIONS):
            self.delete(snap.id)
        for snap in self.db.collection(CACHE_COLLECTION).where(filter=FieldFilter('uid', '==', uid)).stream(**_STREAM_OPTIONS):
            snap.reference.delete(**_READ_OPTIONS)

    def cache_get(self, uid, key):
        snap = self.db.collection(CACHE_COLLECTION).document(digest([uid, key])).get(**_READ_OPTIONS)
        if snap.exists:
            data = snap.to_dict()
            if data['expires_at'] > utcnow():
                return unpack(data['payload'])
        return None

    def cache_put(self, uid, key, value, seconds=3600):
        payload = pack(value)
        ref = self.db.collection(CACHE_COLLECTION).document(digest([uid, key]))
        def operation(tx):
            guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)
            tx.set(ref, dict(uid=uid, payload=payload, expires_at=utcnow() + timedelta(seconds=seconds)))
        self._transaction(operation)

    def cleanup(self, now=None):
        now = now or utcnow()
        deleted = 0
        for snap in self.db.collection(WORKER_COLLECTION).where(filter=FieldFilter('expires_at', '<=', now)).limit(100).stream(**_STREAM_OPTIONS):
            snap.reference.delete(**_READ_OPTIONS)
        for snap in self.db.collection(CACHE_COLLECTION).where(filter=FieldFilter('expires_at', '<=', now)).limit(200).stream(**_STREAM_OPTIONS):
            snap.reference.delete(**_READ_OPTIONS)
        for snap in self.db.collection(COLLECTION).where(filter=FieldFilter('cleanup_at', '<=', now)).limit(100).stream(**_STREAM_OPTIONS):
            job = snap.to_dict()
            retained = any(self._reference_live(path) for path in job.get('references', []))
            if retained:
                self.retain_refresh(job['job_id'])
            else:
                deleted += int(self.delete(job['job_id'], only_if_expired_at=now))
        return deleted

    def retain_refresh(self, job_id):
        ref = self.ref(job_id)
        def operation(tx):
            snap = ref.get(transaction=tx, **_READ_OPTIONS)
            if snap.exists and snap.to_dict().get('status') != 'deleting':
                self._fence(tx, snap.to_dict())
                tx.update(ref, {'cleanup_at': utcnow() + timedelta(days=30)})
        self._transaction(operation)
