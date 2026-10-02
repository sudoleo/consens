"""Local integration harness: real main lifespan/routes/repositories; external seams only.

Never imported by production. The E2E profile rejects live projects before main
is imported. Control routes bind through the fixture to loopback only, require
an unguessable per-process secret, and accept only test-owned account IDs.
"""
import os
import json
import re
import threading
from contextvars import ContextVar
from datetime import datetime, timezone
from types import SimpleNamespace

from app.core.e2e_profile import assert_safe_e2e_environment

assert_safe_e2e_environment()
assert os.environ.get('E2E_TEST_MODE') == '1'
assert os.environ.get('JOURNEY_CONTROL_SECRET')

from firebase_admin import auth


def identity(token, **_kwargs):
    uid = str(token).removeprefix('token-')
    if not str(token).startswith('token-') or not re.fullmatch(r'journey-[a-f0-9]{32}', uid):
        raise ValueError('Unknown test identity')
    return {'uid': uid, 'sub': uid, 'email': uid + '@example.invalid',
            'email_verified': True, 'auth_time': int(datetime.now(timezone.utc).timestamp())}


auth.verify_id_token = identity
auth.get_user = lambda uid: SimpleNamespace(uid=uid, email=uid+'@example.invalid',
    email_verified=True, provider_data=[], user_metadata=SimpleNamespace(creation_timestamp=0))
auth.delete_user = lambda uid: None
auth.revoke_refresh_tokens = lambda uid: None

from main import app
from fastapi import Header, HTTPException
from app.core.security import db_firestore as db
from app.api.routers import agent
from app.services.llm.agent_client import AgentCompletion, measured_usage
from app.services.llm import mock_llm

gates = {}
calls = []
revision_marker = ContextVar('journey_external_revision', default='')
original_output = mock_llm._mock_engine_output
def external_output(prompt, json_mode):
    value = original_output(prompt, json_mode)
    marker = revision_marker.get()
    return value + '\n\n' + marker if marker and not json_mode else value
mock_llm._mock_engine_output = external_output


class Completion(AgentCompletion):
    def stream(self, *, model, messages, **kwargs):
        content = str(messages)
        owner = re.search(r'journey-[a-f0-9]+', content)
        uid = owner.group() if owner else 'unknown'
        calls.append({'uid': uid, 'model': model.model, 'step': self.step_id})
        self.usage = measured_usage({'prompt_tokens': 100, 'completion_tokens': 50}, model)
        if self.step_id == 'completion:0':
            self.tool_calls = [{'id': 'compare', 'type': 'function', 'function': {
                'name': 'compare_models', 'arguments': json.dumps({'question': 'Compare evidence for ' + uid,
                    'context': 'Use the supplied question.', 'reason': 'Independent perspectives',
                    'depth': 'full', 'next_step': 'answer'})}}]
            self.finish_reason = 'tool_calls'
            return
        self.text = 'Saved partial answer for ' + uid
        yield {'type': 'delta', 'text': self.text}
        if self.step_id.startswith('completion:') and not kwargs.get('tools') and uid in gates and not gates[uid].wait(45):
            raise TimeoutError('Test provider was not released')
        self.finish_reason = 'stop'


# Only replace the external provider dispatch. Admission, delegation, SSE,
# receipts, stop/recover and token settlement remain production code.
agent.AgentCompletion = Completion
agent.mock_llm_enabled = lambda: False

from app.services import mailer
messages = []
mailer.is_configured = lambda: True
async def mail(message):
    messages.append({'to': str(message['To']), 'text': message.get_body(preferencelist=('plain',)).get_content()})
    return True
mailer.send_message = mail


def guard(uid, secret):
    if secret != os.environ['JOURNEY_CONTROL_SECRET'] or not re.fullmatch(r'journey-[a-f0-9]{32}', uid):
        raise HTTPException(403, 'Invalid harness request')


def tree(ref):
    return {snap.id: {'data': snap.to_dict(), 'children': {
        collection.id: tree(collection) for collection in snap.reference.collections()
    }} for snap in ref.stream()}


@app.post('/_journey/{uid}/seed')
def seed(uid: str, body: dict, x_journey_secret: str = Header(default='')):
    guard(uid, x_journey_secret)
    db.collection('users').document(uid).set({'tier': 'pro', 'email': uid+'@example.invalid'})
    if body.get('gate'):
        gates[uid] = threading.Event()
    if body.get('storage_full'):
        from app.services import persistence_guard as guard_service
        db.collection(guard_service.USAGE_COLLECTION).document(guard_service._owner_key('bookmarks', uid)).set({
            'bookmark_count': guard_service.MAX_BOOKMARKS_PER_USER,
            'bookmark_bytes': guard_service.MAX_BOOKMARK_BYTES_PER_USER})
    return {'uid': uid}


@app.post('/_journey/{uid}/release')
def release(uid: str, x_journey_secret: str = Header(default='')):
    guard(uid, x_journey_secret)
    if uid in gates:
        gates[uid].set()
    return {'released': True}


@app.get('/_journey/{uid}/state')
def state(uid: str, x_journey_secret: str = Header(default='')):
    guard(uid, x_journey_secret)
    user = db.collection('users').document(uid)
    from google.cloud.firestore_v1.base_query import FieldFilter
    global_owned = {name: {doc.id: {'data': doc.to_dict(), 'children': {
        col.id: tree(col) for col in doc.reference.collections()}}
        for doc in db.collection(name).where(filter=FieldFilter('owner_uid', '==', uid)).stream()}
        for name in ('pending_results', 'shares', 'watches')}
    return {'user': user.get().to_dict(), 'global_owned': global_owned, 'collections': {
        col.id: tree(col) for col in user.collections()
    }, 'calls': [call for call in calls if call['uid'] == uid],
        'tombstone': db.collection('account_deletion_jobs').document(uid).get().to_dict(),
        'messages': [m for m in messages if uid in m['to']]}


@app.post('/_journey/{uid}/cleanup')
def cleanup(uid: str, x_journey_secret: str = Header(default='')):
    guard(uid, x_journey_secret)
    from app.services.account_deletion import FirestoreAccountDeletion
    if uid in gates:
        gates[uid].set()
    deletion = FirestoreAccountDeletion(db)
    deletion.start(uid, email=uid+'@example.invalid')
    errors = deletion.cleanup_uid(uid)
    assert not errors, errors
    return {'cleaned': uid}


@app.post('/_journey/{uid}/watch-run')
def watch_run(uid: str, body: dict, x_journey_secret: str = Header(default='')):
    guard(uid, x_journey_secret)
    from app.services import watch_service, watch_scheduler, share_snapshots
    wid = body['watch_id']
    owner = db.collection('watches').document(wid).get().to_dict()
    assert owner['owner_uid'] == uid
    watch_service.queue_watch_run(wid, db=db)
    claimed, reason = watch_service.claim_watch(wid, db=db)
    assert reason == 'claimed' and claimed and claimed['owner_uid'] == uid
    baseline = share_snapshots.get_share(claimed['share_id'], db=db)
    claimed['question'] = baseline['question']
    token = revision_marker.set('Watch revision ' + claimed['current_run_id'] + '.')
    try:
        result = watch_scheduler.execute_watch(claimed['question'], standing=baseline, tier='pro')
    finally:
        revision_marker.reset(token)
    committed = watch_service.complete_watch_run(wid, claimed, result, db=db)
    return {'run': committed, 'share': share_snapshots.get_share(claimed['share_id'], db=db)}


@app.post('/_journey/{uid}/legacy-source')
def legacy_source(uid: str, body: dict, x_journey_secret: str = Header(default='')):
    guard(uid, x_journey_secret)
    from app.services import source_check_jobs as jobs
    from app.services.source_verification import answer_version
    repo = jobs.repository()
    bookmark_ref = db.collection('users').document(uid).collection('bookmarks').document(body['bookmark'])
    bookmark = bookmark_ref.get().to_dict()
    assert bookmark and bookmark['chat_id'] == body['chat']
    answer = bookmark['responses']['consensus']
    source = {'id': 'S1', 'url': 'https://example.invalid/history', 'title': 'Historical evidence'}
    packages = [{'id': f'package-{i}', 'pairs': [{'sentence_id': i+1, 'source_id': 'S1', 'claim': f'Historical claim {i+1}.'}],
                 'sources': [source]} for i in range(9)]
    version = answer_version(answer)
    plan = {'question': bookmark['query'], 'answer_version': version, 'packages': packages,
        'snapshot': {'schema_version': 3, 'answer_version': version, 'prompt_version': 'v3',
            'sources': [source], 'findings': [], 'documents': [], 'runtime': {'calls': 0},
            'scope': {'pairs': 9, 'checked_pairs': 0, 'processed_pairs': 0, 'sources': 1}}}
    job = repo.create(uid=uid, run_key=body['turn'], plan=plan, credential_mode='own')
    claimed = repo.claim(job['job_id'])
    assert repo.pause_credentials(claimed)
    snapshot = repo.get(job['job_id'], uid)['snapshot']
    bookmark_ref.update({'responses.source_verification': snapshot, 'sources': [source]})
    db.collection('users').document(uid).collection('chats').document(body['chat']).collection('turns').document(body['turn']).update({'source_verification': snapshot, 'sources': [source]})
    return snapshot


@app.post('/_journey/{uid}/source-finish')
def source_finish(uid: str, body: dict, x_journey_secret: str = Header(default='')):
    guard(uid, x_journey_secret)
    from app.services import source_check_jobs as jobs
    repo = jobs.repository()
    job = repo.get(body['job_id'], uid)
    plan = repo.get_plan(job['job_id'])
    while job['completed_packages'] < job['package_count']:
        claimed = repo.claim(job['job_id'], worker_id=jobs.WORKER_ID)
        assert claimed
        package = plan['packages'][claimed['completed_packages']]
        # External fetch/judge output for an imported historical V3 job.
        result = {'answer_version': plan['answer_version'], 'package_id': package['id'],
            'findings': [{**p, 'checked': True, 'support': 'supported', 'topical': 'relevant',
                'temporal': 'not_relevant', 'state': 'checked', 'quotes': ['Exact historical evidence.']} for p in package['pairs']],
            'documents': [{'source_id': 'S1', 'source_url': package['sources'][0]['url']}], 'runtime': {'calls': 1}}
        assert repo.finish_package(claimed, result)
        assert repo.finish_package(claimed, result) is False  # stale duplicate cannot advance again
        job = repo.get(job['job_id'], uid)
    return job['snapshot']
