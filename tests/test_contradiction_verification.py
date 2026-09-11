import copy
from dataclasses import replace

import pytest

from app.services import source_verification as sv
from app.services import contradiction_verification as cv


CONSENSUS = 'The plan costs 20 euros per month.'
SOURCES = {'OpenAI': [{'id': 'S1', 'url': 'https://example.com/a', 'title': 'Plan price'}],
           'Anthropic': [{'id': 'S2', 'url': 'https://example.com/b', 'title': 'Plan price'}]}
ANSWERS = {'OpenAI': 'The plan costs 20 euros. [S1]', 'Anthropic': 'The plan costs 30 euros. [S2]'}


def differences():
    return {'differences': [{'type': 'contradiction', 'severity': 'major',
        'consensus_anchor': CONSENSUS, 'consensus_anchor_validated': True,
        'factual_check': {'checkable': True, 'question': 'Does the plan cost 20 or 30 euros?'},
        'positions': [{'stance': '20 euros', 'models': ['OpenAI'], 'quote_models': ['OpenAI'],
                       'quote': 'The plan costs 20 euros.'},
                      {'stance': '30 euros', 'models': ['Anthropic'], 'quote_models': ['Anthropic'],
                       'quote': 'The plan costs 30 euros.'}]}]}


def plan(**kwargs):
    options = dict(question='Price?', consensus=CONSENSUS, sources=SOURCES,
                   differences_data=differences(), model_answers=ANSWERS, run_id='run-1')
    options.update(kwargs)
    return sv.plan_source_verification(**options)


def doc(url, *_):
    text = 'The plan costs 20 euros.' if url.endswith('/a') else 'The plan costs 30 euros.'
    return {'url': url, 'text': text, 'title': 'Plan price', 'dates': [], 'content_hash': sv.answer_version(text)}


def judge(payload, *_):
    return {'findings': [{'contradiction_id': dispute['contradiction_id'], 'verdict': 'sources_conflict',
        'supported_position_id': None, 'reason': 'The published amounts conflict.',
        'evidence': [{'source_id': pos['sources'][0]['source_id'], 'position_id': pos['id'],
            'quote': next(d['text'] for d in payload['documents'] if d['source_id'] == pos['sources'][0]['source_id'])}
            for pos in dispute['positions']]} for dispute in payload['disputes']]}, {}


def run(**kwargs):
    options = dict(question='Price?', consensus=CONSENSUS, sources=SOURCES, differences_data=differences(),
                   model_answers=ANSWERS, run_id='run-1', keys={}, fetch=doc, judge=judge)
    options.update(kwargs)
    return sv.verify_sources(**options)


def test_separate_mode_has_no_consensus_citations_and_preserves_inputs():
    data = differences()
    before = copy.deepcopy(data)
    result = run(differences_data=data)
    assert result['schema_version'] == 4
    assert result['check_type'] == cv.MODE
    assert result['status'] == 'complete'
    assert result['findings'][0]['verdict'] == 'sources_conflict'
    assert len(result['findings'][0]['evidence']) == 2
    assert data == before
    assert sv.stored_verification(result, CONSENSUS) == result
    assert sv.stored_verification(result, CONSENSUS + ' Changed') is None


@pytest.mark.parametrize('path,value', [('type', 'emphasis'), ('severity', 'minor'),
    ('consensus_anchor_validated', False), ('consensus_anchor', 'Hallucinated anchor'),
    ('factual_check', {'checkable': False, 'question': 'Which style is better?'}), ('factual_check', None)])
def test_ineligible_differences_never_schedule(path, value):
    data = differences()
    data['differences'][0][path] = value
    result = plan(differences_data=data)
    assert result['packages'] == []
    expected = 'contradiction_inputs_unavailable' if path in ('consensus_anchor_validated', 'consensus_anchor') or value is None else 'no_checkable_contradictions'
    assert result['snapshot']['reason_code'] == expected


def test_unverified_model_position_never_drops_one_side_into_judge():
    data = differences()
    data['differences'][0]['positions'][1]['quote_models'] = []
    assert not plan(differences_data=data)['packages']
    assert not plan(model_answers={'OpenAI': ANSWERS['OpenAI'], 'Anthropic': 'Other text'})['packages']


def test_missing_original_quotes_are_explicit_exclusions_not_absent_contradictions():
    data = differences()
    data['differences'][0]['positions'][1].update(quote='', quote_models=[])
    result = plan(differences_data=data)
    snapshot = result['snapshot']
    assert result['packages'] == []
    assert snapshot['findings'] == []
    assert snapshot['reason_code'] == 'contradiction_inputs_unavailable'
    assert snapshot['scope']['detected_contradictions'] == 1
    assert snapshot['scope']['excluded_contradictions'] == 1
    exclusion = snapshot['exclusions'][0]
    assert exclusion['reason_codes'] == ['unverified_model_positions']
    assert exclusion['positions'] == data['differences'][0]['positions']
    assert exclusion['exclusion_id'] == plan(differences_data=data)['snapshot']['exclusions'][0]['exclusion_id']
    assert exclusion['exclusion_id'] != plan(differences_data=data, run_id='other')['snapshot']['exclusions'][0]['exclusion_id']
    assert cv.finish_snapshot(snapshot)['reason_code'] == 'contradiction_inputs_unavailable'


def test_mixed_checks_keep_excluded_dispute_and_all_exclusion_causes():
    data = differences()
    excluded = copy.deepcopy(data['differences'][0])
    excluded['factual_check'] = {'checkable': False, 'question': 'Has the event happened?', 'reason': 'The analysis assumed fiction.'}
    excluded['positions'][0].update(quote='', quote_models=[])
    data['differences'].append(excluded)
    result = run(differences_data=data)
    assert result['scope']['checked_contradictions'] == 1
    assert result['scope']['detected_contradictions'] == 2
    assert result['scope']['excluded_contradictions'] == 1
    assert len(result['findings']) == 1
    assert result['exclusions'][0]['reason_codes'] == ['not_factual', 'unverified_model_positions']
    assert result['exclusions'][0]['reason'] == 'The analysis assumed fiction.'
    assert sv.stored_verification(result, CONSENSUS) == result


def test_identity_binds_run_answer_positions_and_question():
    base = plan()['snapshot']['findings'][0]
    assert base['contradiction_id'] == plan()['snapshot']['findings'][0]['contradiction_id']
    assert base['contradiction_id'] != plan(run_id='other')['snapshot']['findings'][0]['contradiction_id']
    assert base['contradiction_id'] != plan(consensus=CONSENSUS + ' More.')['snapshot']['findings'][0]['contradiction_id']
    data = differences()
    data['differences'][0]['positions'][0]['stance'] = 'Exactly 20 euros'
    changed = plan(differences_data=data)['snapshot']['findings'][0]
    assert base['contradiction_id'] != changed['contradiction_id']
    assert base['positions_version'] != changed['positions_version']


def test_direct_references_select_both_sides_and_ignore_unrelated_catalog():
    sources = copy.deepcopy(SOURCES)
    sources['OpenAI'].append({'id': 'S3', 'url': 'https://example.com/unrelated', 'title': 'Other'})
    result = plan(sources=sources)
    assert {s['url'] for s in result['snapshot']['sources']} == {'https://example.com/a', 'https://example.com/b'}
    for pos in result['snapshot']['findings'][0]['positions']:
        assert pos['sources'][0]['origin'] == 'reference'


def test_reference_from_next_sentence_is_not_borrowed():
    answers = {**ANSWERS, 'OpenAI': 'The plan costs 20 euros. Other issue. [S1]'}
    result = plan(model_answers=answers)
    assert result['snapshot']['findings'][0]['positions'][0]['sources'][0]['origin'] == 'catalog_fallback'


def test_shared_url_fetched_once_preserves_both_passages():
    sources = copy.deepcopy(SOURCES)
    sources['Anthropic'][0]['url'] = sources['OpenAI'][0]['url']
    calls = []
    left, right = 'Students pay 20 euros in 2025.', 'Other customers pay 30 euros in 2025.'
    def fetch(url, *_):
        calls.append(url)
        return {'url': url, 'text': left + '\n' + ('irrelevant filler\n' * 900) + right, 'dates': []}
    data = differences()
    data['differences'][0]['positions'][0].update(stance=left, quote=left)
    data['differences'][0]['positions'][1].update(stance=right, quote=right)
    def inspect(payload, *_):
        assert len(payload['documents']) == 1
        assert left in payload['documents'][0]['text']
        assert right in payload['documents'][0]['text']
        dispute = payload['disputes'][0]
        return {'findings': [{'contradiction_id': dispute['contradiction_id'], 'verdict': 'conditions_explain',
            'reason': 'Student pricing explains the difference.', 'supported_position_id': None,
            'evidence': [{'source_id': payload['documents'][0]['source_id'], 'position_id': 'P1', 'quote': left},
                         {'source_id': payload['documents'][0]['source_id'], 'position_id': 'P2', 'quote': right}]}]}, {}
    result = run(sources=sources, differences_data=data, model_answers={'OpenAI': left + ' [S1]', 'Anthropic': right + ' [S2]'}, fetch=fetch, judge=inspect)
    assert result['status'] == 'complete'
    assert len(calls) == 1
    assert set(result['sources'][0]['providers']) == {'OpenAI', 'Anthropic'}
    assert set(result['sources'][0]['original_source_ids']) == {'S1', 'S2'}
    assert {(r['id'], tuple(r['providers'])) for r in result['sources'][0]['catalog_references']} == {
        ('S1', ('OpenAI',)), ('S2', ('Anthropic',))}


@pytest.mark.parametrize('change', ['invented_quote', 'wrong_source', 'wrong_position', 'one_side', 'duplicate'])
def test_original_evidence_validation_rejects_invented_or_incomplete_verdicts(change):
    def bad_judge(payload, *_):
        raw, usage = judge(payload)
        finding = raw['findings'][0]
        if change == 'invented_quote':
            finding['evidence'][0]['quote'] = 'The plan is free.'
        elif change == 'wrong_source':
            finding['evidence'][0]['source_id'] = finding['evidence'][1]['source_id']
        elif change == 'wrong_position':
            finding['evidence'][0]['position_id'] = 'P7'
        elif change == 'one_side':
            finding['evidence'].pop()
        else:
            raw['findings'].append(copy.deepcopy(finding))
        return raw, usage
    result = run(judge=bad_judge)
    assert not result['findings'][0]['checked']
    assert result['findings'][0]['reason_code'] in ('evidence_mismatch', 'invalid_output')


def test_missing_evidence_can_only_be_insufficient_not_refutation():
    def insufficient(payload, *_):
        return {'findings': [{'contradiction_id': payload['disputes'][0]['contradiction_id'],
            'verdict': 'insufficient_evidence', 'reason': 'No relevant documentary passage.',
            'supported_position_id': None, 'evidence': []}]}, {}
    result = run(judge=insufficient)
    assert result['findings'][0]['verdict'] == 'insufficient_evidence'
    assert result['findings'][0]['checked']


def test_fetch_errors_never_call_judge_or_refute():
    def fail(*_):
        raise ValueError('fetch_timeout')
    result = run(fetch=fail, judge=lambda *_: pytest.fail('No evidence'))
    finding = result['findings'][0]
    assert finding['state'] == 'unavailable'
    assert finding['verdict'] == 'insufficient_evidence'
    assert finding['reason_code'] == 'fetch_timeout'


def test_global_contradiction_budget_records_omissions():
    data = differences()
    data['differences'] *= 3
    result = run(differences_data=data, limits=replace(sv.Limits(), max_contradictions=1))
    assert result['scope']['checked_contradictions'] == 1
    assert result['scope']['omitted_contradictions'] == 2
    assert result['runtime']['calls'] == 1
    assert all(f['reason_code'] == 'contradiction_limit' for f in result['findings'][1:])


def test_url_budget_never_picks_only_one_side():
    result = run(limits=replace(sv.Limits(), max_urls=1), judge=lambda *_: pytest.fail('One-sided budget'))
    assert result['findings'][0]['reason_code'] == 'url_limit'
    assert result['findings'][0]['state'] == 'omitted'


def test_input_token_budget_is_global_and_explicit():
    result = run(limits=replace(sv.Limits(), input_tokens=100),
        fetch=lambda *_: pytest.fail('Over-budget metadata must not fetch'), judge=lambda *_: pytest.fail('Input limit'))
    assert result['findings'][0]['state'] == 'omitted'
    assert result['findings'][0]['reason_code'] == 'input_limit'


def test_runtime_budget_omits_unfinished_check(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(cv.time, 'monotonic', lambda: now[0])
    def slow(url, limits):
        now[0] += 2
        return doc(url)
    result = run(limits=replace(sv.Limits(), total_seconds=1), fetch=slow, judge=lambda *_: pytest.fail('Time limit'))
    assert result['findings'][0]['reason_code'] == 'time_limit'
    assert result['findings'][0]['state'] == 'omitted'


def test_merge_rejects_run_and_position_tampering():
    original = plan()['snapshot']
    result = run()
    tampered = copy.deepcopy(result)
    tampered['run_id'] = 'other'
    with pytest.raises(ValueError, match='version_mismatch'):
        sv.merge_source_verification(original, tampered)
    tampered = copy.deepcopy(result)
    tampered['findings'][0]['positions'][0]['summary'] = 'Changed'
    with pytest.raises(ValueError, match='positions_version_mismatch'):
        sv.merge_source_verification(original, tampered)


def test_legacy_citation_mode_keeps_schema_three():
    legacy = sv.plan_source_verification(question='Price?', consensus='20 euros. [S1]', sources=SOURCES)
    assert legacy['snapshot']['schema_version'] == 3
    assert legacy['snapshot']['check_type'] == 'source_evidence'


def test_large_v4_reference_preserves_mode_run_and_scope():
    result = plan()['snapshot']
    result.update(job_id='a' * 64, status='disabled', huge='x' * 300001)
    stored = sv.stored_verification(result, CONSENSUS)
    assert stored['schema_version'] == 4
    assert stored['check_type'] == cv.MODE
    assert stored['run_id'] == 'run-1'
    assert stored['scope']['contradictions'] == 1
    assert stored['findings'] == []


def test_direct_background_start_uses_disputes_without_citations(monkeypatch):
    monkeypatch.setattr('app.services.llm.mock_llm.mock_llm_enabled', lambda: False)
    future = sv.start_source_verification(question='Price?', consensus=CONSENSUS, sources=SOURCES,
        differences_data=differences(), model_answers=ANSWERS, run_id='run-1', keys={}, fetch=doc, judge=judge)
    result = future.result(timeout=5)
    assert result['schema_version'] == 4
    assert result['status'] == 'complete'


def test_failed_background_start_keeps_v4_mode(monkeypatch):
    monkeypatch.setattr(sv, '_start_source_verification', lambda **_: (_ for _ in ()).throw(ValueError('bad')))
    result = sv.start_source_verification(consensus=CONSENSUS, differences_data=differences()).result()
    assert result['schema_version'] == 4
    assert result['check_type'] == cv.MODE
    assert result['status'] == 'failed'


def test_one_side_retrieval_failure_does_not_promote_surviving_side():
    def partly(url, *_):
        if url.endswith('/b'):
            raise ValueError('fetch_timeout')
        return doc(url)
    def supports(payload, *_):
        source = payload['documents'][0]
        return {'findings': [{'contradiction_id': payload['disputes'][0]['contradiction_id'],
            'verdict': 'supports_position', 'supported_position_id': 'P1', 'reason': '20 euros documented.',
            'evidence': [{'position_id': 'P1', 'source_id': source['source_id'], 'quote': source['text']}]}]}, {}
    result = run(fetch=partly, judge=supports)
    assert result['findings'][0]['verdict'] == 'insufficient_evidence'
    assert result['findings'][0]['supported_position_id'] is None
    assert result['retrieval_errors'][0]['reason_code'] == 'fetch_timeout'


def test_invented_applicability_date_is_rejected():
    def bad(payload, *_):
        raw, usage = judge(payload)
        raw['findings'][0]['evidence'][0]['date'] = '2027-01-01'
        return raw, usage
    result = run(judge=bad)
    assert result['findings'][0]['reason_code'] == 'evidence_mismatch'


def test_passage_selection_never_validates_an_artificial_join():
    finding = plan()['snapshot']['findings'][0]
    source_id = finding['positions'][0]['sources'][0]['source_id']
    documents = {source_id: {'text': 'The plan costs\n20 euros.',
                             '_original_text': 'The plan costs 30 euros.\nStudent prices are 20 euros.'}}
    raw = {'findings': [{'contradiction_id': finding['contradiction_id'], 'verdict': 'supports_position',
        'supported_position_id': 'P1', 'reason': 'The amount matches.',
        'evidence': [{'source_id': source_id, 'position_id': 'P1', 'quote': 'The plan costs\n20 euros.'}]}]}
    rejected = {}
    assert cv.validate_findings(raw, [finding], documents, rejected=rejected) == []
    assert rejected[finding['contradiction_id']] == 'evidence_mismatch'


def test_only_sources_for_metadata_within_budget_are_fetched():
    data = differences()
    extra = copy.deepcopy(data['differences'][0])
    extra['factual_check']['question'] = 'An unreasonably large question ' * 3000
    extra['positions'][0].update(quote='The annual plan costs 200 euros.', stance='200 euros annually')
    extra['positions'][1].update(quote='The annual plan costs 300 euros.', stance='300 euros annually')
    data['differences'].insert(0, extra)
    sources = copy.deepcopy(SOURCES)
    sources['OpenAI'].append({'id': 'S3', 'url': 'https://example.com/c'})
    sources['Anthropic'].append({'id': 'S4', 'url': 'https://example.com/d'})
    answers = {'OpenAI': ANSWERS['OpenAI'] + '\nThe annual plan costs 200 euros. [S3]',
               'Anthropic': ANSWERS['Anthropic'] + '\nThe annual plan costs 300 euros. [S4]'}
    fetched = []
    def fetch(url, limits):
        fetched.append(url)
        return doc(url, limits)
    result = run(differences_data=data, sources=sources, model_answers=answers, fetch=fetch)
    assert result['findings'][0]['reason_code'] == 'input_limit'
    assert result['findings'][1]['checked']
    assert set(fetched) == {'https://example.com/a', 'https://example.com/b'}
