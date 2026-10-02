"""Execute maintenance entry points in an isolated, network-forbidden process."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
import copy, json, os, runpy, socket, sys, types
from unittest.mock import patch
case = json.loads(sys.argv[1])
events = []
def module(name, **values):
    item = types.ModuleType(name)
    item.__dict__.update(values)
    sys.modules[name] = item
    return item
def forbidden(*a, **k):
    raise AssertionError("network forbidden")
def event(name, *args):
    events.append([name, *args])
class Ref:
    def __init__(self, path=""):
        self.path = path
    def collection(self, name): return Ref(self.path + "/" + name)
    def document(self, name): return Ref(self.path + "/" + name)
    def get(self): return types.SimpleNamespace(to_dict=lambda: {"used_tokens": 50, "pending_tokens": 0})
    def set(self, value, merge=False):
        assert merge is True
        event("write", self.path, copy.deepcopy(value))
        for row in rows:
            if self.path.endswith('/' + row['id']): row.update(copy.deepcopy(value))
    def close(self): event("close")
db = Ref()
module('dotenv', load_dotenv=lambda *a: None)
module('app.core.security', db_firestore=db)
if case['script'] == 'repair':
    def user(email):
        event('lookup', email)
        return types.SimpleNamespace(uid='selected-account')
    module('firebase_admin', get_app=lambda: types.SimpleNamespace(project_id='synthetic-review-project'),
           auth=types.SimpleNamespace(get_user_by_email=user))
    module('app.services.agent_budget_config', get_config=lambda database: {'period':'test-day'})
    def quota_ref(database, uid, day):
        assert database is db and uid == 'selected-account' and day == 'test-day'
        event('read', uid)
        return Ref()
    def recover(database, uid):
        assert database is db and uid == 'selected-account'
        event('recover', uid)
        return {'used_tokens':50, 'pending_tokens':0}
    module('app.services.agent_quota', period_key=lambda config: config['period'], quota_ref=quota_ref, snapshot=recover)
    filename = 'scripts/repair_agent_allowance.py'
else:
    rows = copy.deepcopy(case['rows'])
    topic = {'id':'selected-topic', 'slug':'selected'}
    def list_runs(tid, db):
        assert tid == 'selected-topic'
        event('list', tid)
        return copy.deepcopy(rows)
    def topic_by_slug(slug):
        event('topic',slug)
        return topic if slug == 'selected' else None
    module('app.services.topics', db_firestore=db, TOPICS_COLLECTION='topics', list_runs=list_runs,
           get_topic_by_slug=topic_by_slug, list_public_topics=lambda: [topic], get_topic=lambda tid: topic)
    module('app.services.topic_runner', KNOWN_CLAIM_RUNS=20,
           known_claims_from_runs=lambda runs: [{'key':'stable'}] if runs else [])
    module('app.services.llm.provider_transport', PROVIDER_ORDER=['fake'], PROVIDER_LABELS={'fake':'Fake'},
           provider_available=lambda p,k: True, developer_keys=lambda: {'fake':'synthetic'})
    def judge(known, labels, keys, engine):
        event('judge', labels)
        return {i:'stable' for i in range(len(labels))}
    module('app.services.llm.consensus_engine', query_claim_identity=judge)
    filename = 'scripts/backfill_claim_keys.py'
codes=[]
with patch.object(socket.socket, 'connect', forbidden), patch('socket.create_connection', forbidden):
    for args in case['calls']:
        sys.argv = [filename, *args]
        try:
            if case.get('mutation'):
                from pathlib import Path
                source = Path(filename).read_text(encoding='utf-8')
                old, new = case['mutation']
                assert old in source
                exec(compile(source.replace(old, new, 1), filename, 'exec'), {'__name__':'__main__', '__file__':str(Path(filename).resolve())})
            else:
                runpy.run_path(filename, run_name='__main__')
            codes.append(0)
        except SystemExit as exc:
            codes.append(exc.code)
print('RESULT:' + json.dumps({'events':events, 'codes':codes, 'rows':globals().get('rows')}))
'''


def execute(case, env=None):
    clean = {k: os.environ[k] for k in ('SYSTEMROOT', 'PATH') if k in os.environ}
    clean.update(env or {})
    result = subprocess.run([sys.executable, '-E', '-S', '-X', 'utf8', '-c', HARNESS, json.dumps(case)],
                            cwd=ROOT, env=clean, capture_output=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    value = json.loads(result.stdout.rsplit('RESULT:', 1)[1])
    return value, result.stdout


def repair(*args, env=None):
    return execute({'script':'repair', 'calls':[['--email','selected@example.invalid', '--project-id','synthetic-review-project', *args]]}, env)[0]


def test_repair_inspect_does_not_apply_but_selected_account_recovery_does():
    inspected = repair()
    assert inspected['codes'] == [0]
    assert inspected['events'] == [['lookup','selected@example.invalid'], ['read','selected-account'], ['close']]
    applied = repair('--apply')
    assert applied['codes'] == [0]
    assert [e for e in applied['events'] if e[0] == 'recover'] == [['recover','selected-account']]


@pytest.mark.parametrize('env', [{'UNIT_TEST_MODE':'1'}, {'FIRESTORE_EMULATOR_HOST':'127.0.0.1:8085'}, {'FIREBASE_AUTH_EMULATOR_HOST':'127.0.0.1:9099'}])
def test_repair_refuses_test_or_emulator_before_lookup_or_write(env):
    value = repair('--apply', env=env)
    assert value['codes'] == [2]
    assert value['events'] == []


def test_repair_refuses_project_mismatch_before_account_lookup():
    value = repair('--apply', '--project-id', 'wrong-project')
    assert value['codes'] == [2]
    assert value['events'] == []


def test_repair_inspection_oracle_detects_removed_apply_guard():
    value, _ = execute({'script':'repair', 'calls':[['--email','selected@example.invalid', '--project-id','synthetic-review-project']],
                        'mutation':['if args.apply:', 'if True:']})
    with pytest.raises(AssertionError):
        assert not [e for e in value['events'] if e[0] == 'recover']


ROWS = [
    {'id':'r1','version':1,'opinion_map':{'other':{'keep':True},'dimensions':[{'label':'one','key':'existing'}, {'label':'two'}]}},
    {'id':'r2','version':2,'opinion_map':{'other':'preserve','dimensions':[{'label':'later'}]}},
    {'id':'empty','opinion_map':{'dimensions':[]}},
]


def backfill(calls, env=None):
    return execute({'script':'backfill', 'rows':ROWS, 'calls':calls}, env)


def test_backfill_dry_run_counts_changes_without_writes_but_runs_judge():
    value, output = backfill([['--slug','selected','--dry-run']])
    assert value['codes'] == [0]
    assert value['rows'] == ROWS
    assert not [e for e in value['events'] if e[0] == 'write']
    assert [e for e in value['events'] if e[0] == 'judge']
    assert 'Would update 2 run(s).' in output


def test_backfill_preserves_partial_keys_and_other_fields_and_is_idempotent():
    value, _ = backfill([['--slug','selected'], ['--slug','selected']])
    writes = [e for e in value['events'] if e[0] == 'write']
    assert len(writes) == 2
    assert all('/selected-topic/' in e[1] for e in writes)
    first, second, empty = value['rows']
    assert first['opinion_map']['other'] == {'keep':True}
    assert first['opinion_map']['dimensions'][0]['key'] == 'existing'
    assert first['opinion_map']['dimensions'][1]['key'] == 'r1-1'
    assert second['opinion_map'] == {'other':'preserve','dimensions':[{'label':'later','key':'stable'}]}
    assert empty == ROWS[2]


def test_force_can_rekey_existing_dimensions_explicitly():
    value, _ = backfill([['--slug','selected'], ['--slug','selected','--force']])
    assert len([e for e in value['events'] if e[0] == 'write']) == 4
    assert value['rows'][0]['opinion_map']['dimensions'][0]['key'] == 'r1-0'


@pytest.mark.parametrize('args,env', [([], {}), (['--slug','selected'], {'MOCK_LLM':'1'})])
def test_backfill_requires_selection_and_refuses_fixture_identity_mode(args, env):
    value, _ = backfill([args], env)
    assert value['codes'] == [2]
    assert value['events'] == []
