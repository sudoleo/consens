"""Offline-Befundproben; assertiert den Review-Baselinefehler, nicht das Sollverhalten.
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
        api._delete(run['run_id'], expected_uid='review', allowed_statuses={'succeeded'})
assert len(executions)==2
snap=usage.snapshot('review', UsageLimits(100,100))
assert snap.total.consumed==1
record('R03-delete-recreate-quota', provider_pipeline_executions=len(executions), charged_runs=snap.total.consumed)

key='midnight'; before=datetime(2026,9,26,23,59,59,tzinfo=timezone.utc)
usage.reserve('review',key,RunKind.REGULAR,UsageLimits(100,100),now=before)
try: usage.reserve('review',key,RunKind.REGULAR,UsageLimits(100,100),now=before+timedelta(seconds=2))
except UsageRunExpired: record('R05-midnight-receipt', after_two_seconds='expired')
else: raise AssertionError('Expected day-bound expiry')
print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
