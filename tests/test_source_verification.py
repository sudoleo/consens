import asyncio
import json
import socket
import threading
from dataclasses import replace

import httpx
import pytest

from app.services import source_documents as docs
from app.services import source_verification as sv

TEXT = 'The plan costs 20 euros.[S1]'
SOURCES = [{'id': 'S1', 'url': 'https://example.com/prices', 'title': 'Prices'}]


def document(text='The plan costs 20 euros.', **extra):
    return {'text': text, 'url': SOURCES[0]['url'], 'title': 'Prices', 'dates': [],
            'retrieved_at': '2026-09-09T12:00:00Z', 'content_hash': sv.answer_version(text),
            'truncated': False, **extra}


def verdict(payload, topical='relevant', temporal='not_relevant', quotes=None, support='supported'):
    return {'findings': [dict(sentence_id=p['sentence_id'], source_id=p['source_id'],
        support='unknown' if topical == 'unknown' else support, topical=topical, temporal=temporal, reason='Document comparison.',
        quotes=quotes if quotes is not None else ['The plan costs 20 euros.']) for p in payload['pairs']]}


def run(text=TEXT, sources=SOURCES, fetch=None, judge=None, **kwargs):
    return sv.verify_sources(question='What does the plan cost?', consensus=text,
        sources=sources, keys={}, fetch=fetch or (lambda *_: document()),
        judge=judge or (lambda payload, *_: (verdict(payload), {})), **kwargs)


def test_relevant_and_immutable_input():
    sources = json.loads(json.dumps(SOURCES))
    result = run(sources=sources)
    assert result['status'] == 'complete'
    assert result['scope']['checked_statements'] == 1
    assert result['findings'][0]['topical'] == 'relevant'
    assert sources == SOURCES
    assert result['answer_version'] == sv.answer_version(TEXT)
    assert sv.stored_verification(result, TEXT) == result
    assert sv.stored_verification(result, TEXT + ' changed') is None


@pytest.mark.parametrize('topical,temporal,passage', [
    ('relevant', 'not_relevant', 'The plan costs 20 euros only for students.'),
    ('relevant', 'not_relevant', 'The plan costs 30 euros.'),
    ('relevant', 'outdated', 'The plan costs 20 euros until 2024-12-31.'),
    ('relevant', 'suitable', 'In 2024 the plan costs 20 euros.'),
    ('relevant', 'unknown', 'The plan costs 20 euros.'),
    ('unknown', 'unknown', 'This excerpt does not describe prices.'),
    ('off_topic', 'unknown', 'This article explains how to grow roses.'),
])
def test_separate_topical_and_time_results(topical, temporal, passage):
    result = run(fetch=lambda *_: document(passage), judge=lambda p, *_:
        (verdict(p, topical, temporal, [passage] if topical != 'unknown' else []), {}))
    assert result['findings'][0]['topical'] == topical
    assert result['findings'][0]['temporal'] == temporal


def test_copyright_and_retrieval_date_cannot_establish_currency():
    result = run(fetch=lambda *_: document('The plan costs 20 euros.\nCopyright 2026'),
                 judge=lambda p, *_: (verdict(p, temporal='suitable'), {}))
    assert result['findings'][0]['topical'] == 'relevant'
    assert result['findings'][0]['temporal'] == 'unknown'


def test_multiple_sources_keep_individual_outcomes_and_deduplicate_fetches():
    fetched = []
    sources = SOURCES + [dict(SOURCES[0], id='S2')]
    def judge(payload, *_):
        result = verdict(payload)
        result['findings'][1].update(support='unknown', topical='unknown', temporal='unknown', quotes=[])
        return result, {}
    result = run(text='The plan costs 20 euros.[S1, S2]', sources=sources,
                 fetch=lambda url, _: fetched.append(url) or document(), judge=judge)
    assert len(fetched) == 1
    assert [p['topical'] for p in result['findings']] == ['relevant', 'unknown']
    assert result['scope']['statements'] == 1


def test_ambiguous_provider_local_source_ids_stay_unchecked():
    sources = sv.source_records({'OpenAI': SOURCES, 'Mistral': [dict(SOURCES[0], url='https://example.org/other')]})
    result = run(sources=sources, fetch=lambda *_: pytest.fail('ambiguous IDs must not be fetched'))
    assert result['scope']['checked_pairs'] == 0


@pytest.mark.parametrize('mutation', [
    {'sentence_id': 77}, {'sentence_id': True}, {'source_id': 'S999'},
    {'claim': 'Invented claim'}, {'quotes': ['Fabricated passage']},
    {'topical': 'false'}, {'temporal': 'current'}, {'quotes': ['x' * 201]}, {'reason': 'x' * 601},
])
def test_invalid_judge_output_stays_unchecked(mutation):
    def judge(payload, *_):
        data = verdict(payload)
        data['findings'][0].update(mutation)
        return data, {}
    result = run(judge=judge)
    assert result['status'] == 'partial'
    assert result['scope']['checked_pairs'] == 0
    assert result['findings'][0]['checked'] is False


@pytest.mark.parametrize('length', [121, 600])
def test_reason_soft_prompt_target_does_not_discard_valid_evidence(length):
    reason = 'Explanation: ' + 'x' * (length - len('Explanation: '))
    def judge(payload, *_):
        data = verdict(payload, support='partial')
        data['findings'][0]['reason'] = reason
        return data, {}
    result = run(judge=judge)
    assert result['findings'][0]['checked'] is True
    assert result['findings'][0]['reason'] == reason


@pytest.mark.parametrize('opening,closing', [('"', '"'), ("'", "'"), ('“', '”'), ('„', '“')])
def test_cosmetic_quote_wrapper_preserves_only_exact_original_span(opening, closing):
    passage = 'The plan costs 20 euros.'
    result = run(judge=lambda p, *_: (verdict(p, quotes=[opening + passage + closing]), {}))
    assert result['findings'][0]['checked'] is True
    assert result['findings'][0]['quotes'] == [passage]


@pytest.mark.parametrize('quote', ["'Fabricated passage'", "'the plan costs 20 euros.'",
    "'The plan  costs 20 euros.'", "' The plan costs 20 euros. '", '"The plan costs 20 euros.\''])
def test_quote_wrapper_cannot_repair_nonverbatim_evidence(quote):
    result = run(judge=lambda p, *_: (verdict(p, quotes=[quote]), {}))
    assert result['findings'][0]['checked'] is False


@pytest.mark.parametrize('length,checked', [(200, True), (201, True), (400, True), (401, False)])
def test_wrapped_quote_has_bounded_formatting_tolerance(length, checked):
    passage = 'x' * length
    result = run(fetch=lambda *_: document(passage),
                 judge=lambda p, *_: (verdict(p, quotes=["'" + passage + "'"]), {}))
    assert result['findings'][0]['checked'] is checked
    if checked:
        assert result['findings'][0]['quotes'] == [passage]


@pytest.mark.parametrize('count', [3, 4])
def test_extra_exact_quotes_preserve_all_evidence_within_hard_limits(count):
    quotes = ['Exact evidence passage %d.' % i for i in range(count)]
    result = run(fetch=lambda *_: document('\n'.join(quotes)),
                 judge=lambda p, *_: (verdict(p, quotes=quotes, support='partial'), {}))
    finding = result['findings'][0]
    assert finding['checked'] is True
    assert finding['support'] == 'partial'
    assert finding['quotes'] == quotes


@pytest.mark.parametrize('quotes', [
    ['a' * 400, 'b' * 400],
    ['a' * 200, 'b' * 200, 'c' * 200, 'd' * 200],
])
def test_combined_quote_budget_accepts_exact_boundary(quotes):
    result = run(fetch=lambda *_: document('\n'.join(quotes)),
                 judge=lambda p, *_: (verdict(p, quotes=quotes), {}))
    assert result['findings'][0]['checked'] is True
    assert result['findings'][0]['quotes'] == quotes


@pytest.mark.parametrize('quotes', [
    ['Exact evidence.'] * 5,
    ['a' * 400, 'b' * 400, 'c'],
    [123], [None], 'Exact evidence.',
])
def test_quote_structure_and_total_budget_remain_hard_limits(quotes):
    result = run(fetch=lambda *_: document('Exact evidence.\n' + 'a' * 400 + '\n' + 'b' * 400 + '\nc'),
                 judge=lambda p, *_: (verdict(p, quotes=quotes), {}))
    finding = result['findings'][0]
    assert finding['checked'] is False
    assert finding['reason_code'] == 'invalid_output'


@pytest.mark.parametrize('support', ['supported', 'partial', 'contradicted', 'unknown'])
def test_nonverbatim_evidence_is_explicitly_unverified_without_partial_acceptance(support):
    # Reproduces the Gemini failure: one quote capitalizes an original lowercase
    # word. Other correct quotes must not promote a subset into a valid verdict.
    result = run(fetch=lambda *_: document('A plan is available. Also the plan costs 20 euros. In 2026.'),
        judge=lambda p, *_: (verdict(p, support=support, temporal='suitable',
            quotes=['A plan is available.', 'The plan costs 20 euros.']), {}))
    finding = result['findings'][0]
    assert finding['checked'] is False
    assert finding['state'] == 'unavailable'
    assert finding['reason_code'] == 'evidence_mismatch'
    assert [finding[k] for k in ('support', 'topical', 'temporal')] == ['unknown'] * 3
    assert finding['quotes'] == []
    assert result['runtime']['calls'] == 1


def test_exact_evidence_must_also_exist_in_original_document():
    pairs = [{'sentence_id': 1, 'source_id': 'S1', 'claim': TEXT}]
    raw = verdict({'pairs': pairs})
    rejected = {}
    findings = sv.validate_findings(raw, pairs,
        {'S1': {'text': 'The plan costs 20 euros.', '_original_text': 'Different document.'}},
        rejected=rejected)
    assert findings == []
    assert rejected == {(1, 'S1'): 'evidence_mismatch'}


def test_duplicate_invalid_evidence_remains_schema_failure():
    def judge(payload, *_):
        data = verdict(payload, quotes=['Invented evidence.'])
        data['findings'].append(dict(data['findings'][0]))
        return data, {}
    result = run(judge=judge)
    assert result['findings'][0]['checked'] is False
    assert result['findings'][0]['reason_code'] == 'invalid_output'


def test_duplicate_output_is_not_last_write_wins():
    def judge(payload, *_):
        data = verdict(payload)
        data['findings'] *= 2
        return data, {}
    assert run(judge=judge)['scope']['checked_pairs'] == 0


def test_topic_only_judgment_without_evidence_cannot_establish_support():
    def judge(payload, *_):
        data = verdict(payload, quotes=[])
        data['findings'][0]['reason'] = ''
        return data, {}
    result = run(judge=judge)
    assert result['status'] == 'partial'
    assert result['schema_version'] == 3
    assert result['check_type'] == 'source_evidence'
    assert result['findings'][0]['claim'] == sv.collect_claims(TEXT, SOURCES)[0]['claim']
    assert result['findings'][0]['support'] == 'unknown'


def test_truncated_provider_response_retains_only_complete_validated_pairs(monkeypatch):
    requests = []
    complete = {'sentence_id': 1, 'source_id': 'S1', 'support': 'supported', 'topical': 'relevant',
                'temporal': 'not_relevant', 'reason': '', 'quotes': ['The plan costs 20 euros.']}
    def response(*_, **kwargs):
        requests.append(kwargs['json'])
        return {'choices': [{'finish_reason': 'length', 'message': {'content':
            '{"findings":[' + json.dumps(complete) + ',{"sentence_id":2,"source_id":"S1"'}}],
            'usage': {'completion_tokens': 3000}}
    monkeypatch.setattr(sv, 'cancellable_post_json', response)
    result = run(text=TEXT + ' Another plan costs 30 euros.[S1]',
                 judge=lambda p, _, limits: sv.judge_sources(p, {'OpenRouter': 'fake-test-key'}, limits))
    assert result['status'] == 'partial'
    assert result['scope']['checked_pairs'] == 1
    assert [f['checked'] for f in result['findings']] == [True, False]
    assert result['runtime']['error_code'] == 'output_limit'
    assert len(requests) == 1
    assert requests[0]['model'] == sv.cfg.get_source_verification_model()
    assert 'reasoning' not in requests[0]


def test_invalid_or_empty_cutoff_response_is_not_repaired():
    with pytest.raises(sv.SourceCheckError, match='invalid_output'):
        sv._parse_judge_output('{"findings":[{"sentence_id":1}')
    with pytest.raises(sv.SourceCheckError, match='output_limit'):
        sv._parse_judge_output('{"findings":[{"sentence_id":', truncated=True)


def test_slow_fetches_reserve_time_for_the_judge(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(sv.time, 'monotonic', lambda: clock[0])
    sources = [dict(SOURCES[0], id=f'S{i}', url=f'https://example.com/{i}') for i in range(1, 7)]
    fetched = []
    def fetch(url, limits):
        fetched.append(url)
        clock[0] += limits.fetch_seconds
        return document()
    def judge(payload, *_):
        assert sv.current_analysis_budget().deadline - clock[0] >= 45
        return verdict(payload), {}
    result = run(text='The plan costs 20 euros.[S1,S2,S3,S4,S5,S6]', sources=sources, fetch=fetch, judge=judge)
    assert result['status'] == 'complete'
    assert len(fetched) == 6
    assert result['scope']['checked_pairs'] == 6


def test_timeout_is_reported_without_leaking_provider_details(caplog):
    def fail(*_):
        raise TimeoutError('private provider details')
    result = run(judge=fail)
    assert result['runtime']['error_code'] == 'timeout'
    assert 'private provider details' not in caplog.text


@pytest.mark.parametrize('topical,temporal', [('off_topic', 'unknown'), ('relevant', 'outdated')])
def test_negative_fit_requires_short_verifiable_evidence(topical, temporal):
    result = run(judge=lambda p, *_: (verdict(p, topical, temporal, []), {}))
    assert result['scope']['checked_pairs'] == 0


def test_only_visible_consensus_citations_reach_fetch_judge_and_snapshot():
    fetched, sent = [], []
    sources = [dict(SOURCES[0], id=f'S{i}', url=f'https://example.com/source-{i}') for i in range(1, 5)]
    text = '```\nThe plan costs 20 euros.[S1]\n```\nThe plan costs 20 euros.[S3] '
    text += 'The literal example is `[S2]`, not a citation.'
    def judge(payload, *_):
        sent.append(payload)
        return verdict(payload), {}
    result = run(text=text, sources=sources,
                 fetch=lambda url, _: fetched.append(url) or document(), judge=judge)
    assert fetched == ['https://example.com/source-3']
    assert {p['source_id'] for p in sent[0]['pairs']} == {'S3'}
    assert [s['id'] for s in result['sources']] == ['S3']
    assert {f['source_id'] for f in result['findings']} == {'S3'}
    assert result['scope']['pairs'] == 1


def test_uncited_available_sources_never_trigger_a_check():
    result = run(text='No references appear in this consensus.',
                 fetch=lambda *_: pytest.fail('uncited source fetched'),
                 judge=lambda *_: pytest.fail('uncited source judged'))
    assert result['status'] == 'skipped'
    assert result['sources'] == []


def test_cost_budget_sends_each_excerpt_and_claim_once_without_context_or_offsets():
    sent = []
    sources = SOURCES + [dict(SOURCES[0], id='S2')]
    def judge(payload, *_):
        sent.append(payload)
        return verdict(payload), {}
    run(text='The plan costs 20 euros.[S1, S2]', sources=sources, judge=judge,
        fetch=lambda *_: document('The plan costs 20 euros. ' * 1000))
    payload = sent[0]
    assert len(sent) == 1
    assert len(payload['claims']) == 1
    assert len(payload['documents']) == 1
    assert set(payload['documents'][0]['source_ids']) == {'S1', 'S2'}
    assert 3000 <= len(payload['documents'][0]['text']) <= 4000
    assert payload['documents'][0]['truncated'] is True
    assert set(payload['claims'][0]) == {'sentence_id', 'claim'}
    assert set(payload['pairs'][0]) == {'sentence_id', 'source_id'}
    assert sv.Limits().input_chars == 32000
    assert sv.Limits().output_tokens == 3000
    assert 'Topic agreement alone NEVER establishes support' in sv.SYSTEM
    assert 'numbers, units, exceptions' in sv.SYSTEM


def test_fetch_error_and_limits_do_not_call_judge_without_text():
    def fail(*_):
        raise OSError('unavailable')
    result = run(fetch=fail, judge=lambda *_: pytest.fail('must not judge a title/URL'))
    assert result['status'] == 'partial'
    assert result['scope']['checked_pairs'] == 0
    result = run(text='The plan costs 20 euros.[S1] The second plan costs 20 euros.[S1]',
                 limits=replace(sv.Limits(), max_pairs=1))
    assert result['status'] == 'complete'
    assert result['scope']['pairs'] == 2
    assert result['scope']['checked_pairs'] == 2


def test_missing_output_and_failure_are_advisory():
    assert run(judge=lambda *_: ({}, {}))['status'] == 'partial'
    def fail(*_):
        raise ValueError('invalid JSON')
    assert run(judge=fail)['status'] == 'partial'
    result = run(text='A statement without citations.', judge=fail, fetch=fail)
    assert result['status'] == 'skipped'


def test_setup_failure_cannot_escape_into_consensus(monkeypatch):
    def fail(*_):
        raise ValueError('bad source input')
    monkeypatch.setattr(sv, 'collect_claims', fail)
    result = sv.start_source_verification(question='Price?', consensus=TEXT, sources=SOURCES, keys={}).result()
    assert result['status'] == 'failed'


def test_hard_input_limit_is_explicit_and_claim_target_does_not_skip_sources():
    result = run(limits=replace(sv.Limits(), input_chars=10),
                 judge=lambda *_: pytest.fail('input exceeds configured limit'))
    assert result['status'] == 'partial' and result['scope']['checked_pairs'] == 0
    result = run(limits=replace(sv.Limits(), claim_chars=3))
    assert result['status'] == 'complete' and result['scope']['checked_pairs'] == 1


def test_sentence_ids_repeated_text_tables_and_uncited_scope():
    text = 'The plan costs 20 euros.[S1] The plan costs 20 euros.[S2]\nAn uncited statement here.'
    claims = sv.collect_claims(text, [])
    assert [c['sentence_id'] for c in claims] == [1, 2]
    assert [c['source_ids'] for c in claims] == [['S1'], ['S2']]
    assert [c['anchor_occurrence'] for c in claims] == [0, 1]
    assert all(text[c['start']:c['end']] == c['claim'] for c in claims)
    table = '| Plan | Price |\n| --- | --- |\n| Basic | 20 euros[S1] |'
    assert sv.collect_claims(table, [])[0]['source_ids'] == ['S1']


def test_pipeline_starts_verification_after_successful_differences(monkeypatch):
    from app.services import consensus_pipeline as pipeline
    events = []
    saved_result = run()
    def verify(**kwargs):
        assert events == ['differences']
        assert kwargs['differences_data'] is differences
        assert kwargs['model_answers']['openai'] == 'A'
        assert kwargs['consensus'] == 'The plan costs 20 euros.'
        events.append('sources')
        return saved_result
    monkeypatch.setattr(sv, 'verify_sources', verify)
    monkeypatch.setattr('app.services.llm.mock_llm.mock_llm_enabled', lambda: False)
    differences = {'agreement': {'score': 91}, 'differences': []}
    def judge(*args, **kwargs):
        assert events == []
        assert args[1] == 'The plan costs 20 euros.'
        events.append('differences')
        return 'unchanged', differences
    result = pipeline.analyze_provider_answers(question='Price?',
        answers={'openai': 'A', 'mistral': 'B'}, consensus_model='OpenAI', keys={},
        verification_sources=SOURCES, synthesize=lambda *_, **__: TEXT, judge=judge,
        verification_submit=verify)
    assert result.consensus == 'The plan costs 20 euros.'
    assert events == ['differences', 'sources']
    assert result.differences_data is differences
    assert result.agreement == {'score': 91}
    assert result.source_verification['status'] == 'complete'


@pytest.mark.parametrize('address', ['127.0.0.1', '10.0.0.1', '169.254.169.254',
    '192.168.0.1', '::1', 'fe80::1', '::ffff:127.0.0.1', '224.0.0.1', '100.64.0.1'])
def test_private_addresses_blocked(address):
    assert not docs.public_address(address)


def test_dns_mixed_answers_fail_closed(monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *_: [
        (2, 1, 6, '', ('93.184.216.34', 443)), (2, 1, 6, '', ('127.0.0.1', 443))])
    with pytest.raises(ValueError, match='unsafe_address'):
        asyncio.run(docs.pinned_target('https://example.com/a'))


def test_fetch_pins_ip_and_checks_redirect_again(monkeypatch):
    original_client = httpx.AsyncClient
    calls = []
    def resolve(host, *_):
        return [(2, 1, 6, '', ('127.0.0.1' if host == 'internal.test' else '93.184.216.34', 443))]
    def respond(request):
        calls.append(request)
        assert request.url.host == '93.184.216.34'
        assert request.headers['host'] == 'example.com'
        assert request.extensions['sni_hostname'] == 'example.com'
        return httpx.Response(302, headers={'location': 'http://internal.test/admin'})
    monkeypatch.setattr(socket, 'getaddrinfo', resolve)
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original_client(**kw, transport=httpx.MockTransport(respond)))
    with pytest.raises(ValueError, match='unsafe_address'):
        docs.fetch_document('https://example.com/redirect', sv.Limits())
    assert len(calls) == 1


@pytest.mark.parametrize('url,expected_host,expected_port', [
    ('https://example.com/path', 'example.com', 443),
    ('http://example.com/path', 'example.com', 80),
    ('https://example.com:443/path', 'example.com', 443),
    ('http://example.com:80/path', 'example.com', 80),
    ('https://example.com:80/path', 'example.com:80', 80),
    ('http://example.com:443/path', 'example.com:443', 443),
    ('https://[2606:4700:4700::1111]/path', '[2606:4700:4700::1111]', 443),
])
def test_pinned_target_preserves_canonical_host_and_tls_name(monkeypatch, url, expected_host, expected_port):
    lookups = []
    def resolve(hostname, port, *_):
        lookups.append((hostname, port))
        return [(socket.AF_INET6, 1, 6, '', ('2606:4700:4700::1111', port, 0, 0))]
    monkeypatch.setattr(socket, 'getaddrinfo', resolve)
    target, host, tls_name = asyncio.run(docs.pinned_target(url))
    assert target == f'{url.split(":", 1)[0]}://[2606:4700:4700::1111]:{expected_port}/path'
    assert host == expected_host
    assert tls_name == ('2606:4700:4700::1111' if '[' in url else 'example.com')
    assert lookups == [(tls_name, expected_port)]


@pytest.mark.parametrize('url', ['http://example.com:8080/', 'https://example.com:8443/'])
def test_pinned_target_rejects_nonstandard_ports_before_dns(monkeypatch, url):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *_: pytest.fail('unsafe URL reached DNS'))
    with pytest.raises(ValueError, match='unsafe_url'):
        asyncio.run(docs.pinned_target(url))


def test_fetch_follows_canonical_redirect_without_default_port_loop(monkeypatch):
    original_client = httpx.AsyncClient
    calls, lookups = [], []
    def resolve(hostname, port, *_):
        lookups.append((hostname, port))
        return [(socket.AF_INET, 1, 6, '', ('93.184.216.34', port))]
    def respond(request):
        calls.append(request)
        assert request.url.host == '93.184.216.34'
        assert request.extensions['sni_hostname'] == 'example.com'
        # Model a canonicalizing origin: a synthesized default port causes an
        # endless redirect even when the redirect URL already is canonical.
        if request.url.scheme == 'http' or request.headers['host'] != 'example.com':
            return httpx.Response(301, headers={'location': 'https://example.com/'})
        return httpx.Response(200, headers={'content-type': 'text/plain'},
                              stream=httpx.ByteStream(b'Canonical source body.'))
    monkeypatch.setattr(socket, 'getaddrinfo', resolve)
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original_client(**kw, transport=httpx.MockTransport(respond)))
    result = asyncio.run(docs._download('http://example.com/', sv.Limits()))
    assert result[:2] == ('https://example.com/', b'Canonical source body.')
    assert [request.headers['host'] for request in calls] == ['example.com', 'example.com']
    assert lookups == [('example.com', 80), ('example.com', 443)]


def test_compressed_body_is_bounded_before_expansion_and_cached(monkeypatch):
    import gzip
    original_client = httpx.AsyncClient
    calls = []
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *_: [(2, 1, 6, '', ('93.184.216.34', 443))])
    def respond(request):
        calls.append(request)
        return httpx.Response(200, headers={'content-type': 'text/plain', 'content-encoding': 'gzip'},
                              stream=httpx.ByteStream(gzip.compress(b'x' * 1000000)))
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original_client(**kw, transport=httpx.MockTransport(respond)))
    limits = replace(sv.Limits(), max_bytes=1000)
    first = docs.fetch_document('https://example.com/compressed', limits)
    assert first['truncated'] and len(first['text']) == 1000
    assert docs.fetch_document('https://example.com/compressed', limits) == first
    assert len(calls) == 1


def test_metadata_provenance_context_and_no_invented_date():
    html = b'<title>Plans</title><meta property="article:published_time" content="2024-02-01"><h2>Student plans</h2><p>Only for students.</p><p>20 euros.</p><footer>Copyright 2026</footer>'
    doc = docs.extract_document('https://example.com', html, 'text/html', {}, False, sv.Limits())
    assert doc['dates'] == [{'value': '2024-02-01', 'origin': 'meta:article:published_time'}]
    assert 'Student plans' in doc['text'] and 'Only for students.' in doc['text']
    assert 'Copyright' not in doc['text']
    assert docs.extract_document('https://example.com', b'<p>No date.</p>', 'text/html', {}, False, sv.Limits())['dates'] == []


def test_source_result_arrives_while_differences_are_blocked():
    from concurrent.futures import Future
    release = threading.Event()
    future = Future()
    def differences():
        assert release.wait(2)
        yield {'type': 'final', 'text': 'Unchanged differences'}
    iterator = sv.interleave_verification(differences(), future)
    future.set_result({'status': 'complete'})
    assert next(iterator) == {'type': 'source_verification', 'data': {'status': 'complete'}}
    release.set()
    assert list(iterator) == [{'type': 'final', 'text': 'Unchanged differences'}]


def test_pending_share_and_bookmark_rehydration_preserve_snapshot():
    from app.services import share_snapshots as shares
    result = run()
    pending = shares.build_pending_result('owner', 'Price?', TEXT, {}, '', SOURCES,
        ['OpenAI', 'Mistral'], {}, 'OpenAI', source_verification=result)
    assert pending['source_verification'] == result
    share = shares.public_share_payload(pending)
    assert share['source_verification'] == result
    # No quoted source prompt is duplicated in persistence.
    assert all('text' not in d for d in result['documents'])


@pytest.mark.parametrize('support,passage', [
    ('supported', 'The plan costs 20 euros.'),
    ('partial', 'The plan costs 20 euros only for students.'),
    ('contradicted', 'The plan costs 30 euros.'),
    ('unknown', 'We offer several plans.')])
def test_evidence_verdicts_are_distinct_and_quoted(support, passage):
    result = run(fetch=lambda *_: document(passage),
        judge=lambda p, *_: (verdict(p, quotes=[passage] if support != 'unknown' else [], support=support), {}))
    finding = result['findings'][0]
    assert finding['checked'] and finding['support'] == support
    assert finding['state'] == 'checked' and finding['reason_code'] is None


@pytest.mark.parametrize('support', ['supported', 'partial', 'contradicted'])
def test_each_evidence_judgment_requires_original_passages(support):
    result = run(judge=lambda p, *_: (verdict(p, quotes=[], support=support), {}))
    assert result['findings'][0]['state'] == 'unavailable'
    assert result['findings'][0]['reason_code'] == 'evidence_mismatch'


def test_all_cited_sources_and_pairs_survive_many_bounded_packages():
    sources = [dict(SOURCES[0], id=f'S{i}', url=f'https://example.com/{i}') for i in range(1, 71)]
    fetched, calls = [], []
    text = 'The plan costs 20 euros.[' + ','.join(s['id'] for s in sources) + ']'
    def judge(payload, *_):
        calls.append(payload)
        return verdict(payload), {}
    result = run(text=text, sources=sources, fetch=lambda url, _: fetched.append(url) or document(),
                 judge=judge, limits=replace(sv.Limits(), max_sources=1, max_pairs=2))
    assert result['status'] == 'complete'
    assert len(result['findings']) == result['scope']['checked_pairs'] == 70
    assert len(fetched) == len(set(fetched)) == 70
    assert result['scope']['processed_sources'] == result['scope']['checked_sources'] == 70
    assert all(len(payload['pairs']) <= 2 for payload in calls)


def test_same_source_many_statements_fetches_once_and_splits_output_budget():
    calls, fetched = [], []
    def judge(payload, *_):
        calls.append(payload)
        return verdict(payload), {}
    result = run(text=' '.join('The plan costs 20 euros.[S1]' for _ in range(35)),
        fetch=lambda url, _: fetched.append(url) or document(), judge=judge,
        limits=replace(sv.Limits(), max_pairs=3))
    assert result['status'] == 'complete'
    assert len(fetched) == 1 and len(calls) == 12
    assert result['scope']['checked_pairs'] == result['scope']['checked_statements'] == 35


def test_serializable_plan_and_idempotent_incremental_merge():
    plan = sv.plan_source_verification(question='Price?', consensus=TEXT, sources=SOURCES)
    assert plan == json.loads(json.dumps(plan))
    assert plan['packages'] == sv.plan_source_verification(question='Price?', consensus=TEXT, sources=SOURCES)['packages']
    initial = plan['snapshot']
    assert initial['findings'][0]['state'] == 'pending'
    assert initial['findings'][0]['reason_code'] is None
    partial = sv.execute_source_package(package=plan['packages'][0], question='Price?',
        answer_version=plan['answer_version'], keys={}, fetch=lambda *_: document(),
        judge=lambda p, *_: (verdict(p), {'cost': .01}))
    merged = sv.merge_source_verification(initial, partial)
    again = sv.merge_source_verification(merged, partial)
    assert merged == again and merged['runtime']['cost'] == .01
    assert merged['status'] == 'complete'
    assert initial['status'] == 'queued'


def test_content_version_ignores_retrieval_time_but_changes_with_document():
    first = run(fetch=lambda *_: document(retrieved_at='2026-01-01'))
    second = run(fetch=lambda *_: document(retrieved_at='2026-09-01'))
    third = run(fetch=lambda *_: document('The plan costs 20 euros. Changed.'))
    assert first['source_version'] == second['source_version']
    assert first['source_version'] != third['source_version']


def test_transient_and_permanent_fetch_failures_keep_explicit_records():
    for exc, expected in [(TimeoutError('secret'), 'fetch_timeout'),
                           (ValueError('unsupported_document'), 'unsupported_document'),
                           (ValueError('unsafe_address'), 'unsafe_address')]:
        def fail(*_):
            raise exc
        result = run(fetch=fail)
        finding = result['findings'][0]
        assert finding['state'] == 'unavailable' and finding['reason_code'] == expected
        assert result['scope']['processed_pairs'] == 1
        assert result['scope']['checked_pairs'] == 0
        assert 'secret' not in json.dumps(result)


def test_relevance_selection_finds_late_evidence_and_adjacent_qualification():
    body = '\n'.join(['Corporate history and generic marketing information.'] * 250)
    body += '\nOnly for university students.\nThe plan costs 20 euros.\nOther customers pay 30 euros.'
    selected = docs.select_passages(document(body), [{'claim': 'The plan costs 20 euros.'}], 'Price?', 1000)
    assert 'The plan costs 20 euros.' in selected['text']
    assert 'Only for university students.' in selected['text']
    assert 'Other customers pay 30 euros.' in selected['text']
    assert len(selected['text']) <= 1000 and selected['truncated']
    sent = []
    run(fetch=lambda *_: document(body), judge=lambda p, *_: sent.append(p) or (verdict(p), {}))
    assert 'Only for university students.' in sent[0]['documents'][0]['text']


@pytest.mark.parametrize('quote', ['Alpha\nBeta', "'Alpha\nBeta'"])
def test_artificial_excerpt_join_cannot_become_an_original_quote(quote):
    pair = sv.collect_claims(TEXT, SOURCES)[0]
    pair = {**pair, 'source_id': 'S1'}
    raw = {'findings': [{'sentence_id': 1, 'source_id': 'S1', 'support': 'supported',
                        'topical': 'relevant', 'temporal': 'not_relevant', 'reason': '', 'quotes': [quote]}]}
    assert sv.validate_findings(raw, [pair], {'S1': {'text': 'Alpha\nBeta', '_original_text': 'Alpha OTHER Beta'}}) == []


def test_main_content_extraction_retains_tables_and_removes_navigation():
    html = b'<html><nav>Navigation unrelated prices 999</nav><main><h1>Pricing</h1><p>Only available to enrolled students at participating universities.</p><table><tr><td>Basic plan</td><td>20 euros</td></tr></table><p>This is the full applicable price schedule.</p></main><aside>Unrelated promotion</aside></html>'
    result = docs.extract_document('https://example.com/main', html, 'text/html', {}, False, sv.Limits())
    assert '20 euros' in result['text'] and 'enrolled students' in result['text']
    assert 'Navigation' not in result['text'] and 'Unrelated' not in result['text']


def test_document_singleflight_and_defensive_cache_copies(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    started, release = threading.Event(), threading.Event()
    calls = []
    async def download(url, limits):
        calls.append(url)
        started.set()
        assert release.wait(2)
        return url, b'Original body', 'text/plain', {}, False
    monkeypatch.setattr(docs, '_download', download)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(docs.fetch_document, 'https://example.com/singleflight-v3', sv.Limits())
        assert started.wait(2)
        second = pool.submit(docs.fetch_document, 'https://example.com/singleflight-v3', sv.Limits())
        release.set()
        one, two = first.result(), second.result()
    one['dates'].append({'value': 'Injected'})
    assert two['dates'] == [] and len(calls) == 1


def test_short_negative_cache_prevents_failure_storm(monkeypatch):
    calls = []
    async def download(url, limits):
        calls.append(url)
        raise TimeoutError('private host details')
    monkeypatch.setattr(docs, '_download', download)
    for _ in range(3):
        with pytest.raises(ValueError, match='fetch_timeout'):
            docs.fetch_document('https://example.com/negative-v3', sv.Limits())
    assert len(calls) == 1



def test_legacy_v2_snapshot_remains_readable_without_new_evidence_claim():
    legacy = {'schema_version': 2, 'check_type': 'source_fit', 'answer_version': sv.answer_version(TEXT),
              'status': 'complete', 'findings': [{'sentence_id': 1, 'source_id': 'S1',
                  'checked': True, 'topical': 'relevant', 'temporal': 'not_relevant'}]}
    assert sv.stored_verification(legacy, TEXT) == legacy
    assert 'support' not in sv.stored_verification(legacy, TEXT)['findings'][0]


def test_large_durable_snapshot_preserves_bounded_reference_and_summary():
    result = run()
    result.update(job_id='a' * 64, revision=7, credential_mode='own')
    result['findings'][0]['reason'] = 'Large hydrated evidence. ' * 20000
    result['scope']['unexpected'] = {'unbounded': 'x' * 300000}
    result['scope']['unknown_pairs'] = {'unbounded': 'x' * 300000}
    stored = sv.stored_verification(result, TEXT)
    assert stored['job_id'] == result['job_id']
    assert stored['answer_version'] == result['answer_version']
    assert stored['revision'] == 7 and stored['status'] == 'complete'
    assert stored['schema_version'] == 3 and stored['credential_mode'] == 'own'
    assert stored['scope']['checked_pairs'] == 1
    assert 'unexpected' not in stored['scope'] and 'unknown_pairs' not in stored['scope']
    assert stored['findings'] == stored['documents'] == stored['sources'] == []
    assert len(json.dumps(stored).encode()) < 2000
    assert result['findings'][0]['reason'].startswith('Large hydrated evidence.')


@pytest.mark.parametrize('override', [
    {'answer_version': 'b' * 64}, {'job_id': '../invalid'}, {'job_id': 'a' * 63},
    {'schema_version': 2}, {'check_type': 'source_fit'},
])
def test_large_snapshot_without_valid_durable_identity_is_rejected(override):
    result = run()
    result['job_id'] = 'a' * 64
    result.update(override)
    result['findings'][0]['reason'] = 'x' * 300001
    assert sv.stored_verification(result, TEXT) is None


def test_supported_without_applicable_time_cannot_reassure():
    result = run(judge=lambda p, *_: (verdict(p, temporal='unknown'), {}))
    assert result['findings'][0]['support'] == 'unknown'
    assert result['findings'][0]['checked']


def test_evaluation_dataset_has_complete_v3_expected_verdicts():
    from scripts.evaluate_source_verification import CASES
    assert all(len(case) == 7 for case in CASES)
    expected = {case[0]: case[-1] for case in CASES}
    assert expected['contradiction'] == expected['untrusted_instructions'] == 'contradicted'
    assert expected['missing_condition'] == 'partial'



def test_long_original_claim_is_judged_without_soft_target_truncation():
    claim = 'The plan costs 20 euros ' + 'under the stated published contractual conditions ' * 32 + '.'
    seen = []
    def judge(payload, *_):
        seen.extend(payload['claims'])
        return verdict(payload), {}
    result = run(text=claim + '[S1]', judge=judge)
    assert result['status'] == 'complete'
    assert seen[0]['claim'].startswith(claim) and len(claim) > sv.Limits().claim_chars


def test_even_unjudgeably_large_claim_attempts_its_cited_document():
    fetched = []
    claim = 'The plan costs 20 euros ' + 'under contractual conditions ' * 1500 + '.'
    result = run(text=claim + '[S1]', fetch=lambda url, _: fetched.append(url) or document(),
                 judge=lambda *_: pytest.fail('oversize payload'))
    assert len(fetched) == 1
    assert result['findings'][0]['reason_code'] == 'input_limit'
    assert result['findings'][0]['claim'].startswith(claim)


def test_cached_judge_verdict_is_revalidated_and_does_not_count_a_paid_call():
    result = run(judge=lambda p, *_: (verdict(p), {'cache_hit': True, 'calls': 0}))
    assert result['status'] == 'complete'
    assert result['runtime']['calls'] == 0 and result['runtime']['cache_hits'] == 1
