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
                    'context': 'Use the supplied question.', 'status_update': 'Independent perspectives',
                    'depth': 'full'})}}]
            self.finish_reason = 'tool_calls'
            return
        # The agent's next step writes the answer itself (agent_answer_mode).
        # Longer than ANSWER_HOLD_CHARS, so it streams before the gate holds it.
        self.text = 'Saved partial answer for ' + uid + '. ' + 'The evidence agrees on the main point. ' * 8
        yield {'type': 'delta', 'text': self.text}
        if (self.step_id.startswith('completion:') and self.step_id != 'completion:0' and uid in gates
                and not gates[uid].wait(45)):
            raise TimeoutError('Test provider was not released')
        self.finish_reason = 'stop'


# Only replace the external provider dispatch. Admission, delegation, SSE,
# receipts, stop/recover and token settlement remain production code.
agent.AgentCompletion = Completion
agent.mock_llm_enabled = lambda: False

# Observe the actual response and lease without changing producer/settlement
# behavior. ASGI disconnect may finish before the pump, so tests await both.
agent_streams = {}


class ObservedAgentResponse(agent.AgentStreamingResponse):
    async def __call__(self, scope, receive, send):
        token = dict(scope['headers']).get(b'authorization', b'').decode()
        uid = token.removeprefix('Bearer token-')
        assert re.fullmatch(r'journey-[a-f0-9]{32}', uid)
        observed = {'lease': self._lease, 'response_ended': threading.Event()}
        agent_streams.setdefault(uid, []).append(observed)
        try:
            return await super().__call__(scope, receive, send)
        finally:
            observed['response_ended'].set()


agent.AgentStreamingResponse = ObservedAgentResponse


def stream_states(uid):
    result = []
    for observed in agent_streams.get(uid, []):
        with observed['lease']._lock:
            result.append({'lease': observed['lease']._state,
                'response_ended': observed['response_ended'].is_set()})
    return result

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
    }, 'calls': [call for call in calls if call['uid'] == uid], 'streams': stream_states(uid),
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
