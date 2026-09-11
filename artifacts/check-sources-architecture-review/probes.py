"""Offline architecture probes; no network calls or production writes.

Run from the repository root with venv/Scripts/python.exe and this file.
These assertions document current behavior, not desired product behavior.
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ['UNIT_TEST_MODE'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services import consensus_pipeline as pipeline
from app.services import source_documents as docs
from app.services import source_verification as sv
from app.services.llm.provider_transport import ProviderAnswer


def document(url, text='The plan cost 30 euros throughout 2024.'):
    return dict(url=url, title='2024 pricing', text=text, dates=[],
                retrieved_at='2026-09-09T00:00:00Z', truncated=False,
                content_hash=sv.answer_version(text))


def fit_judge(payload, *_):
    return {'findings': [dict(**pair, topical='relevant', temporal='suitable',
                             reason='', quotes=[]) for pair in payload['pairs']]}, {}


source = dict(id='S1', url='https://example.com/pricing', title='Pricing')
claim = 'In 2024 the plan cost 20 euros.[S1]'
observations = {}

# The actual server orchestration passes colliding provider-local IDs through.
captured = {}
fetches = []


def synthesize(*args, **kwargs):
    captured['source_ids'] = [s['id'] for sources in kwargs['model_sources'].values()
                              for s in sources]
    return claim


def start(**kwargs):
    from concurrent.futures import Future
    future = Future()
    result = sv.verify_sources(**kwargs,
        fetch=lambda url, _: fetches.append(url) or document(url), judge=fit_judge)
    future.set_result(result)
    return future


with patch.object(pipeline, 'start_source_verification', start):
    result = pipeline.analyze_provider_answers(
        question='What did it cost in 2024?', keys={}, consensus_model='OpenAI',
        answers={
            'openai': ProviderAnswer('OpenAI', 'test', claim, [source]),
            'mistral': ProviderAnswer('Mistral', 'test', claim,
                [dict(source, url='https://example.org/pricing')]),
        }, synthesize=synthesize,
        judge=lambda *a, **kw: ('Differences', {'agreement': {'score': 75}}))
assert captured['source_ids'] == ['S1', 'S1']
assert result.source_verification['scope']['checked_pairs'] == 0
assert not fetches
observations['server_source_id_collision'] = dict(
    **captured, status=result.source_verification['status'],
    checked_pairs=0, fetches=fetches)

# A positive fit classification is allowed for an explicitly contradictory price.
result = sv.verify_sources(question='What did it cost in 2024?', consensus=claim,
    sources=[source], keys={}, fetch=lambda url, _: document(url), judge=fit_judge)
assert result['status'] == 'complete'
assert result['findings'][0]['topical'] == 'relevant'
assert result['findings'][0]['quotes'] == []
assert 'text' not in result['documents'][0]
observations['fit_is_not_support'] = dict(status=result['status'],
    topical=result['findings'][0]['topical'], temporal=result['findings'][0]['temporal'],
    stored_quotes=result['findings'][0]['quotes'],
    note='Injected policy-compatible judge; this does not measure model accuracy.')

# The extractor keeps the prefix rather than selecting a claim-relevant passage.
html = ('<html><title>Pricing</title><body><article><p>' +
        'Company background. ' * 300 +
        '</p><h2>Current price</h2><p>UNIQUE_PRICE_FACT: 20 euros.</p></article></body></html>')
extracted = docs.extract_document(source['url'], html.encode(), 'text/html', {},
                                  False, sv.Limits())
assert extracted['truncated'] and 'UNIQUE_PRICE_FACT' not in extracted['text']
observations['prefix_extraction'] = dict(retained_chars=len(extracted['text']),
    truncated=True, relevant_passage_retained=False)

# All four slots occupied: immediate partial, without a capacity-specific reason.
class Busy:
    def acquire(self, **kwargs):
        return False


with patch.object(sv, '_slots', Busy()), patch(
        'app.services.llm.mock_llm.mock_llm_enabled', return_value=False):
    result = sv.start_source_verification(question='Price?', consensus=claim,
        sources=[source], keys={}).result()
assert result['status'] == 'partial' and result['scope']['checked_pairs'] == 0
assert 'error_code' not in result['runtime']
observations['capacity_exhaustion'] = dict(status=result['status'],
    scope=result['scope'], runtime=result['runtime'])

# Source order determines which source loses the six-document budget.
many_sources = [dict(source, id=f'S{i}', url=f'https://example.com/{i}') for i in range(1, 8)]
fetches = []
result = sv.verify_sources(question='What applied in 2024?',
    consensus=' '.join(f'In 2024 finding number {i} applied.[S{i}]' for i in range(1, 8)),
    sources=many_sources, keys={},
    fetch=lambda url, _: fetches.append(url) or document(url), judge=fit_judge)
assert len(fetches) == 6 and result['scope']['checked_pairs'] == 6
assert result['findings'][-1]['source_id'] == 'S7'
assert not result['findings'][-1]['checked']
observations['source_selection_order'] = dict(scope=result['scope'],
    last_source_checked=False, fetches=fetches)

output = Path(__file__).with_name('probe-results.json')
output.write_text(json.dumps(observations, indent=2), encoding='utf-8')
print(json.dumps(observations, indent=2))
