"""Supported sample/experiment entry points with real runner and local data."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
import json, runpy, socket, sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
target, root, scenario = sys.argv[1:4]
root = Path(root)
from benchmark import config, dataset, runner
if scenario == 'mutate-budget-guard':
    from benchmark import cli_validation
    cli_validation.validate_execution_arguments = lambda parser, args: args
from app.services import prompt_config
from app.services.llm import credentials
class EmptyDb:
    def collection(self, *a): return self
    def document(self, *a): return self
    def get(self, **k): return SimpleNamespace(exists=False)
prompt_config._runtime_store = prompt_config.PromptConfigStore(EmptyDb())
config.RUNS_DIR = root / 'runs'
config.EXPERIMENT_MANIFEST = root / 'manifest.json'
config.EXPERIMENT_MANIFEST.write_text(json.dumps({'question_ids':[1]}))
records = [{'question_id':1,'question':'Test question?', 'options':['One','Two'], 'answer':'B','answer_index':1,'category':'test'}]
events=[]
def dataset_read():
    events.append('dataset')
    return records
dataset.load_dataframe = dataset_read
dataset.records_from_dataframe = lambda rows: rows
credentials.resolve_developer_api_keys = lambda *a: {'OpenRouter':'dummy-test-key'}
credentials.missing_credentials = lambda *a: ['OpenRouter'] if scenario == 'missing' else []
def transport(*a, **k):
    events.append('provider')
    return {'text':'FINAL_ANSWER: B','sources':[], 'usage':{'prompt':2,'completion':3,'total':5},
            'raw':{},'status':200,'latency_ms':1,'error':None,'error_code':None}
def consensus(**k):
    events.append('consensus')
    return 'FINAL_ANSWER: B'
original_run = runner.BenchmarkRunner.run
def run(self, *a, **k):
    return original_run(self, *a, **k, transport_execute=transport, consensus_fn=consensus)
runner.BenchmarkRunner.run = run
def forbidden(*a, **k): raise AssertionError('unexpected network')
base = ['--manifest',str(config.EXPERIMENT_MANIFEST),'--run-id','sample'] if target.endswith('run_sample') else []
args = json.loads(sys.argv[4])
codes=[]
with patch.object(socket.socket, 'connect', forbidden), patch('socket.create_connection', forbidden):
    for call in args:
        sys.argv=[target,*base,*call]
        try: runpy.run_module(target,run_name='__main__')
        except SystemExit as exc: codes.append(exc.code)
print('RESULT:'+json.dumps({'codes':codes,'events':events}))
'''


def call(tmp_path, module, calls, scenario='normal'):
    env = {k: os.environ[k] for k in ('PATH','SYSTEMROOT') if k in os.environ}
    env.update(UNIT_TEST_MODE='1', PYTHONUTF8='1', OPENROUTER_API_KEY='unit-dummy-key')
    proc = subprocess.run([sys.executable,'-X','utf8','-c',HARNESS,module,str(tmp_path),scenario,json.dumps(calls)],
                          cwd=ROOT, env=env, capture_output=True, encoding='utf-8', timeout=30)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads(proc.stdout.rsplit('RESULT:',1)[1])


@pytest.mark.parametrize('module',['benchmark.run_sample','benchmark.run_experiment'])
@pytest.mark.parametrize('args', [['--live'], ['--live','--budget','-1'], ['--live','--budget','nan'],
                                  ['--live','--budget','inf'], ['--live','--budget','0'], ['--live','--dry-run','--budget','1']])
def test_invalid_execution_args_stop_before_dataset_or_provider(tmp_path,module,args):
    value=call(tmp_path,module,[args])
    assert value == {'codes':[2], 'events':[]}
    assert not (tmp_path/'runs').exists()


@pytest.mark.parametrize('run_id',['../escape','/absolute','C:\\outside','..'])
def test_sample_run_id_cannot_escape_output_root(tmp_path,run_id):
    value=call(tmp_path,'benchmark.run_sample',[['--run-id',run_id]])
    assert value == {'codes':[2], 'events':[]}


@pytest.mark.parametrize('module',['benchmark.run_sample','benchmark.run_experiment'])
def test_dry_run_then_live_then_resume_uses_real_runner_without_duplicate_calls(tmp_path,module):
    value=call(tmp_path,module,[['--dry-run'],['--live','--budget','10'],['--live','--budget','10','--resume']])
    assert value['codes'] == [0,0,0]
    assert value['events'].count('provider') == 7  # six models and synth-alone control
    assert value['events'].count('consensus') == 1
    runs=list((tmp_path/'runs').iterdir())
    assert len(runs) == 1
    records=[json.loads(line) for line in (runs[0]/'calls.jsonl').read_text().splitlines()]
    assert len(records) == 8
    assert sorted(row['role'] for row in records) == ['consensus', *['model']*6, 'synth_alone']
    assert all(row['correct'] for row in records)
    assert (runs[0]/'results.json').is_file()


@pytest.mark.parametrize('module',['benchmark.run_sample','benchmark.run_experiment'])
def test_missing_credential_never_starts_provider(tmp_path,module):
    value=call(tmp_path,module,[['--live','--budget','10']],scenario='missing')
    assert value['codes'] == [2]
    assert value['events'] == ['dataset']


def test_argument_boundary_oracle_detects_removed_finite_budget_guard(tmp_path):
    value=call(tmp_path,'benchmark.run_sample',[['--live','--budget','nan']],scenario='mutate-budget-guard')
    with pytest.raises(AssertionError):
        assert value == {'codes':[2], 'events':[]}
    assert 'provider' in value['events']
