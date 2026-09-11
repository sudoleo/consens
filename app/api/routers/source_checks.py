"""Owner-bound source-check pages and authenticated own-key resumption."""
from __future__ import annotations
import logging
import re
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from app.core.rate_limit import limiter
from app.core.security import extract_id_token, verify_user_token
from app.core.observability import safe_exception
from app.services import source_check_jobs as jobs
from app.services.source_check_repository import SourceCheckNotFound, SourceCheckRevisionChanged

router = APIRouter()


def require_uid(request):
    token = extract_id_token(request, {})
    if not token:
        raise HTTPException(401, 'Authentication failed')
    try:
        return verify_user_token(token)
    except Exception:
        raise HTTPException(401, 'Authentication failed') from None


def _check_binding(actual, expected):
    if expected is None:
        return
    fields = ('answer_version',)
    if expected.get('check_type') == 'contradiction_evidence':
        fields += ('schema_version', 'check_type', 'prompt_version', 'run_id')
    if any(actual.get(field) != expected.get(field) for field in fields):
        raise SourceCheckNotFound('Source check version mismatch')


def check_page(job_id, *, uid, cursor, revision, after_revision=None, expected_snapshot=None):
    try:
        if cursor == 0 and after_revision is not None:
            job = jobs.repository().get(job_id, uid)
            _check_binding(job['snapshot'], expected_snapshot)
            if job['revision'] == after_revision:
                return JSONResponse({'source_verification': job['snapshot'],
                    'unchanged': True, 'next_cursor': None}, headers={'Cache-Control': 'private, no-store'})
        value = jobs.repository().page(job_id, uid=uid, cursor=cursor, revision=revision)
        _check_binding(value['source_verification'], expected_snapshot)
        return JSONResponse(value, headers={'Cache-Control': 'private, no-store'})
    except SourceCheckNotFound:
        raise HTTPException(404, 'Source check not found') from None
    except SourceCheckRevisionChanged:
        raise HTTPException(409, 'Source check changed; reload first page') from None
    except ValueError:
        raise HTTPException(400, 'Invalid source-check cursor') from None
    except Exception as exc:
        logging.warning('Source check read failed category=%s', safe_exception(exc))
        raise HTTPException(503, 'Source check temporarily unavailable') from None


@router.get('/api/source-checks/{job_id}')
@limiter.limit('1200/minute')
def get_source_check(request: Request, job_id: str,
                     cursor: int = Query(0, ge=0), revision: int | None = Query(None, ge=0),
                     after_revision: int | None = Query(None, ge=0)):
    return check_page(job_id, uid=require_uid(request), cursor=cursor, revision=revision, after_revision=after_revision)


class ResumeBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    openrouter_key: str = Field(min_length=1, max_length=4096)


@router.post('/api/source-checks/{job_id}/resume')
@limiter.limit('30/minute')
def resume_source_check(request: Request, job_id: str, data: ResumeBody):
    uid = require_uid(request)
    try:
        job = jobs.repository().get(job_id, uid)
        if job['credential_mode'] != 'own':
            raise HTTPException(409, 'This check does not use an own API key')
        resumed = jobs.resume_source_check(job_id, uid, data.openrouter_key)
        return JSONResponse({'source_verification': resumed['snapshot']},
                            headers={'Cache-Control': 'private, no-store'})
    except SourceCheckNotFound:
        raise HTTPException(404, 'Source check not found') from None


@router.get('/api/share/{share_id}/source-check')
@limiter.limit('300/minute')
def get_shared_source_check(request: Request, share_id: str,
        version: str = Query('', max_length=64), cursor: int = Query(0, ge=0),
        revision: int | None = Query(None, ge=0), after_revision: int | None = Query(None, ge=0)):
    from app.services import share_snapshots as shares
    from app.services.source_verification import answer_version
    # Live access check on every page; the job ID alone is never a public grant.
    data = shares.get_share(share_id)
    if not data or data.get('status') != 'active':
        raise HTTPException(404, 'Shared source check not found')
    if data.get('visibility', 'public') == 'private' and require_uid(request) != data.get('owner_uid'):
        raise HTTPException(404, 'Shared source check not found')
    if version and version != 'original':
        if not re.fullmatch(r'[A-Za-z0-9]{8,64}', version):
            raise HTTPException(404, 'Version not found')
        snapshot = shares.get_watch_version(share_id, version)
        if not snapshot:
            raise HTTPException(404, 'Version not found')
    else:
        snapshot = data
    verification = snapshot.get('source_verification') or {}
    if not verification.get('job_id') or verification.get('answer_version') != answer_version(snapshot.get('consensus_md', '')):
        raise HTTPException(404, 'Shared source check not found')
    if (version and version != 'original' and verification.get('check_type') == 'contradiction_evidence'
            and verification.get('run_id') != 'watch:' + version):
        raise HTTPException(404, 'Shared source check not found')
    return check_page(verification['job_id'], uid=data['owner_uid'], cursor=cursor, revision=revision,
                      after_revision=after_revision, expected_snapshot=verification)


@router.get('/api/topics/{slug}/source-check')
@limiter.limit('300/minute')
def get_topic_source_check(request: Request, slug: str,
        version: str = Query('', max_length=64), cursor: int = Query(0, ge=0),
        revision: int | None = Query(None, ge=0), after_revision: int | None = Query(None, ge=0)):
    from app.services import topics
    from app.services.source_verification import answer_version
    topic, _ = topics.resolve_topic_by_slug(slug)
    if not topic or topic.get('status') not in ('active', 'paused'):
        raise HTTPException(404, 'Topic not found')
    run_id = version or topic.get('latest_run_id', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', run_id):
        raise HTTPException(404, 'Version not found')
    run = topics.get_run(topic['id'], run_id)
    snapshot = (run or {}).get('source_verification') or {}
    if not snapshot.get('job_id') or snapshot.get('answer_version') != answer_version((run or {}).get('consensus_md', '')):
        raise HTTPException(404, 'Source check not found')
    if snapshot.get('check_type') == 'contradiction_evidence' and snapshot.get('run_id') != 'topic:' + run_id:
        raise HTTPException(404, 'Source check not found')
    try:
        job = jobs.repository().get(snapshot['job_id'])
    except SourceCheckNotFound:
        raise HTTPException(404, 'Source check not found') from None
    if job.get('origin') != 'topic' or f"topics/{topic['id']}" not in job.get('references', []):
        raise HTTPException(404, 'Source check not found')
    return check_page(job['job_id'], uid=job['uid'], cursor=cursor, revision=revision,
                      after_revision=after_revision, expected_snapshot=snapshot)
