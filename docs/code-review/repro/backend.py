"""Offline-Befundproben; assertiert den beschriebenen Ist-Zustand, nicht das Sollverhalten.
Aus Repo-Root: python docs/code-review/repro/backend.py (Backend-Abhaengigkeiten).
Keine Provider-/Datenbankzugriffe. Nicht als gruene Regressionstests uebernehmen.
"""
import os
os.environ['UNIT_TEST_MODE'] = '1'
os.environ['FIRESTORE_EMULATOR_HOST'] = '127.0.0.1:1'
import ast, asyncio, copy, difflib, json, pathlib, socket, sys, threading
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import patch
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
def blocked(*a, **k):
    raise AssertionError('Network access forbidden in review probes')
socket.socket.connect = blocked
socket.create_connection = blocked
results = []
def record(name, **data):
    results.append({'probe': name, **data})

def extracted(path, name, namespace):
    tree = ast.parse((ROOT / path).read_text())
    node = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), path, 'exec'), namespace)
    return namespace[name]

from fastapi import HTTPException
from fastapi.responses import JSONResponse
handler = extracted('main.py', 'handle_http_exception', {'HTTPException': HTTPException, 'JSONResponse': JSONResponse})
response = asyncio.run(handler(None, HTTPException(429, 'busy', headers={'Retry-After':'15'})))
assert 'retry-after' not in response.headers
record('R04-http-headers', status=response.status_code, retry_after=response.headers.get('retry-after'))

from app.services import agent_quota, opinion_map, topic_runner, seo_data
q = agent_quota.settle(agent_quota.reserve({}, 100, limit=100), 100, None)
p = agent_quota.public(q, limit=100)
assert p['remaining'] == 100 and p['used'] == 0
record('R07-unknown-agent-usage', **p)

source = topic_runner.evidence_from_sources([{'url':'https://news.example.com/article', 'title':'Industry reporting'}], {'allowed_types':['primary']})
assert source[0]['type'] == 'primary'
record('R14-source-relabel', result=source[0]['type'])

label = 'Current annual subscription price'
def dimension(stance):
    return {'label':label, 'positions':[{'stance':stance, 'models':['OpenAI']}]}
previous = {'schema_version':1, 'dimensions':[dimension('The plan costs 20 euros per month')], 'models':[]}
current = [dimension('The plan costs 90 euros per month')]
views, score, label = opinion_map._movement_view(current, previous, consensus_changed=True)
assert score == 0 and not views[0]['moved']
record('R15-numeric-movement', score=score, label=label)

from app.services.llm import streaming, consensus_engine
for name, chunks in [('eof',[{'type':'delta','text':'This is an unfinished answer'}]), ('length',[{'type':'delta','text':'This is an unfinished answer'},{'type':'finish','reason':'length'}])]:
    with patch.object(streaming, '_iter_openrouter_chunks', return_value=iter(chunks)):
        events = list(streaming._stream_openrouter_chat_completion(api_key='offline', payload={}, provider='openai'))
    assert events[-1]['type']=='final' and not events[-1]['result'].get('error')
    record('R06-stream-'+name, result=events[-1]['result'])
original = 'The annual operating cost for this complete configuration is 400 euros.'
forged = original.replace('400', '4000')
data = {'differences':[{'positions':[{'models':['OpenAI'],'quote':forged}]}]}
consensus_engine._verify_differences_data(data, '', {'OpenAI':original})
position = data['differences'][0]['positions'][0]
assert position['quote_models'] == ['OpenAI'] and position['quote'] != forged
record('R08-fuzzy-quote', submitted=forged, accepted=position)

class BrokenRepo:
    def create_run(self, *a): raise RuntimeError('simulated database outage')
svc = seo_data.SeoDataService(repository=BrokenRepo())
svc._collection_lock = threading.Lock()
try: svc.collect()
except RuntimeError: pass
assert svc._collection_lock.locked()
try: svc.collect()
except seo_data.CollectionAlreadyRunning: record('R22-seo-lock', second_attempt='CollectionAlreadyRunning')
else: raise AssertionError('Expected stuck collector')

# Real repository methods with a minimal in-memory transactional adapter.
# This demonstrates sequential business transitions, not Firestore isolation.
class DB:
    def __init__(self): self.data = {}
    def collection(self, name): return Ref(self, name)
class Ref:
    def __init__(self, db, path): self.db,self.path,self.id=db,path,path.split('/')[-1]
    def document(self, name): return Ref(self.db,self.path+'/'+name)
    collection = document
    def get(self, **kwargs):
        value = copy.deepcopy(self.db.data.get(self.path))
        return SimpleNamespace(exists=value is not None, id=self.id, to_dict=lambda:value)
class TX:
    def __init__(self, db): self.db=db
    def set(self, ref, data, merge=False): self.db.data[ref.path]={**(self.db.data.get(ref.path,{}) if merge else {}),**copy.deepcopy(data)}
    def update(self, ref, data): self.set(ref,data,merge=True)
    def delete(self, ref): self.db.data.pop(ref.path,None)
from app.services import api_consensus_runner as runner
from app.services.api_run_repository import FirestoreApiRunRepository
from app.services.usage_repository import FirestoreUsageRepository, RunKind, UsageLimits, UsageRunExpired
memory = DB(); tx = TX(memory)
api = FirestoreApiRunRepository(memory, transaction_runner=lambda fn:fn(tx))
usage = FirestoreUsageRepository(memory, transaction_runner=lambda fn:fn(tx))
args = dict(uid='review', api_key_id='review', idempotency_key='same-key', request_payload={'question':'Same question'}, model_plan={}, tier='free')
executions=[]
with patch.object(runner,'api_run_repository',api), patch.object(runner,'usage_repository',usage), patch.object(runner.api_account_cleanup,'ensure_active'), patch.object(runner,'execute_consensus_pipeline',side_effect=lambda r:executions.append(r['run_id']) or {'consensus':'offline'}):
    for i in range(2):
        run, created = api.create_or_get(**args)
        assert created
        reserved, receipt = runner.reserve_run(run)
        runner.execute_persisted_run(run['run_id'])
        assert api.get(run['run_id'])['status']=='succeeded'
        api.delete_terminal_for_uid(run['run_id'], 'review')
assert len(executions)==2
snap=usage.snapshot('review', UsageLimits(100,100))
assert snap.total.consumed==1
record('R03-delete-recreate-quota', provider_pipeline_executions=len(executions), charged_runs=snap.total.consumed)

key='midnight'; before=datetime(2026,9,26,23,59,59,tzinfo=timezone.utc)
usage.reserve('review',key,RunKind.REGULAR,UsageLimits(100,100),now=before)
try: usage.reserve('review',key,RunKind.REGULAR,UsageLimits(100,100),now=before+timedelta(seconds=2))
except UsageRunExpired: record('R05-midnight-receipt', after_two_seconds='expired')
else: raise AssertionError('Expected day-bound expiry')
# Counter-review: state changes between admission and completion. The adapter
# supplies sequential transactions; this does not simulate Firestore retries.
from app.services import chat_context, user_memory, memory_edit, watch_service, topics
ref_db = DB(); ref_tx = TX(ref_db)
ref_db.run_transaction = lambda fn: fn(ref_tx)
ctx = chat_context.FirestoreChatContextRepository(ref_db, transaction_runner=ref_db.run_transaction)
now = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)
ref_tx.set(ctx._chat_ref('review', 'a'*32), {'status':'active'})
turn = ctx._turn_ref('review', 'a'*32, 'b'*32)
ref_tx.set(turn, {'status':'pending', 'question':'Original?', 'position':2})
_, nonce, _ = ctx.claim_version('review', 'a'*32, 'b'*32, 'c'*32, {}, now=now)
ref_tx.update(turn, {'status':'completed', 'consensus':'Answer already saved'})
ctx.finalize_version('review', 'a'*32, 'b'*32, 'c'*32, nonce, {'resolved_question':'Changed interpretation?'}, now=now)
saved = turn.get().to_dict()
assert saved['status'] == 'completed' and saved['resolved_question'] == 'Changed interpretation?'
record('R10-late-context', turn_status=saved['status'], context_written_after_completion=True)

profiles = user_memory.FirestoreUserMemoryRepository(ref_db, transaction_runner=ref_db.run_transaction)
profiles.save('review', {'role':'Original', 'notes':'Original'})
stale = {k:v for k,v in profiles._profile_ref('review').get().to_dict().items() if k not in {'revision','updated_at'}}
profiles.save('review', {'role':'Newer', 'notes':'Newer'})
profiles.save('review', stale)
saved = profiles._profile_ref('review').get().to_dict()
assert saved['role']=='Original' and saved['revision']==3
record('R12-stale-memory-save', role=saved['role'], revision=saved['revision'])

edits = memory_edit.FirestoreMemoryEditRepository(ref_db)
config = {'memory_free_ai_edits_daily':10, 'memory_ai_edits_per_minute':3,
          'memory_global_calls_daily':100, 'memory_free_chars':2000}
args_edit = dict(client_request_id='review-request', fingerprint='same', tier='free', config=config)
first = edits.reserve('review', **args_edit, now=now)
late = edits.reserve('review', **args_edit, now=now+timedelta(days=1))
assert not first['existing'] and late['existing'] and late['record']['status']=='reserved'
record('R13-expired-memory-edit', after_one_day=late['record']['status'])

watch_id = 'review-watch'
wref = ref_db.collection(watch_service.WATCHES_COLLECTION).document(watch_id)
claimed = {'owner_uid':'review', 'status':'active', 'current_run_id':'old-run',
           'interval':'weekly', 'share_id':'review-share', 'model_tier':'pro'}
ref_tx.set(wref, claimed)
owner = watch_service._owner_state_ref(ref_db, 'review')
ref_tx.set(owner, {'active_count':1})
with patch.object(watch_service, '_run_transaction', side_effect=lambda db,fn:fn(ref_tx)), \
     patch.object(watch_service, '_ensure_watch_indexes'), \
     patch.object(watch_service.share_snapshots, 'get_share', return_value={}), \
     patch.object(watch_service, '_serialize_watch', side_effect=lambda wid,data,share:data):
    paused = watch_service.update_watch('review', watch_id, {'status':'paused'}, 'pro', db=ref_db)
    assert paused['status']=='paused' and owner.get().to_dict()['active_count']==0
    watch_service.fail_watch_run(watch_id, claimed, now=now, db=ref_db)
assert wref.get().to_dict()['status']=='active'
assert owner.get().to_dict()['active_count']==0
record('R16-pause-then-failure', final_status='active', active_count=0)

# Direct writes are used only by release_worker_lease / config persistence.
Ref.update = lambda self,data: TX(self.db).update(self,data)
Ref.set = lambda self,data,**kw: TX(self.db).set(self,data,**kw)
Ref.delete = lambda self: TX(self.db).delete(self)
lease = ref_db.collection(watch_service.RUNTIME_COLLECTION).document('global_worker')
assert watch_service._worker_lease_transaction(ref_tx, lease, now)
after_expiry = now+timedelta(minutes=watch_service.WORKER_LEASE_MINUTES, seconds=1)
assert watch_service._worker_lease_transaction(ref_tx, lease, after_expiry)  # B
assert not watch_service._worker_lease_transaction(ref_tx, lease, after_expiry)  # C correctly refused
watch_service.release_worker_lease(db=ref_db)  # delayed release by A
assert watch_service._worker_lease_transaction(ref_tx, lease, after_expiry)  # C now admitted
record('R30-global-lease', old_release_allows_third_worker=True)

cfg_ref = ref_db.collection('config').document('models')
cfg_ref.set({'revision':'X'})
def activation_failure():
    cfg_ref.set({'revision':'B'})  # independent process commits after A's write
    raise RuntimeError('Activation in A failed')
activate = extracted('app/api/routers/admin.py', '_persist_and_activate_models', {
    '_MODEL_CONFIG_UPDATE_LOCK':threading.Lock(),
    'load_models_from_db':lambda **kw:activation_failure(),
})
try: activate(cfg_ref, {'revision':'A'})
except RuntimeError: pass
assert cfg_ref.get().to_dict()=={'revision':'X'}
record('R25-config-rollback', newer_B_replaced_with='X')

classified = topics.classify_evidence(source[0]['url'], source[0]['type'])
assert classified['role']=='primary' and classified['quality']=='high'
record('R14-public-classification', role=classified['role'], quality=classified['quality'])

print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
