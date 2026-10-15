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
rows = []
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
