"""WP-29: Chromium → built AppFirebase → real HTTP → native Firestore.

Only Firebase identity SDK and external model/messaging services are replaced.
No browser route interception of application APIs and no injected UI answers.
"""
import json
import html
import re
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

import pytest
from playwright.sync_api import expect

from app.core.e2e_profile import E2E_PROJECT_ID, assert_safe_e2e_environment
from test_phase4_frontend import FIREBASE_APP_STUB, FIREBASE_AUTH_STUB, FIRESTORE_STUB

FIRESTORE_GUARD = FIRESTORE_STUB
for operation in ('setDoc', 'addDoc', 'deleteDoc', 'getDoc'):
    FIRESTORE_GUARD = re.sub(r'export async function ' + operation + r'\(\) \{[^\n]*\}',
        'export async function ' + operation + '() { throw new Error("Unexpected browser Firestore access"); }',
        FIRESTORE_GUARD)


@pytest.fixture(scope='module')
def journey_server():
    port = int(os.environ.get('E2E_JOURNEY_PORT', '8044'))
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', port)) != 0, f'Journey port {port} is occupied'
    secret = uuid.uuid4().hex
    env = os.environ.copy()
    env.update(E2E_TEST_MODE='1', FIRESTORE_EMULATOR_HOST='127.0.0.1:8085',
        GOOGLE_CLOUD_PROJECT=E2E_PROJECT_ID, GCLOUD_PROJECT=E2E_PROJECT_ID,
        FIREBASE_PROJECT_ID=E2E_PROJECT_ID, MOCK_LLM='1', MOCK_AUTH='0',
        DISABLE_RATE_LIMIT='1', OPENROUTER_API_KEY='journey-provider-key',
        JOURNEY_CONTROL_SECRET=secret, MOCK_LLM_DELAY_MS='0', WATCH_UNSUBSCRIBE_SECRET=secret)
    env.pop('GOOGLE_APPLICATION_CREDENTIALS', None)
    assert_safe_e2e_environment(env)
    base = f'http://127.0.0.1:{port}'
    output = Path('test-results/journey-server.log')
    output.parent.mkdir(exist_ok=True)
    with output.open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'tests.e2e.journey_server:app',
            '--host', '127.0.0.1', '--port', str(port), '--log-level', 'warning'],
            cwd=Path(__file__).resolve().parents[2], env=env, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                assert process.poll() is None, output.read_text(encoding='utf-8')
                try:
                    with urllib.request.urlopen(base + '/app', timeout=2) as response:
                        if response.status == 200:
                            break
                except (urllib.error.URLError, OSError):
                    time.sleep(.1)
            else:
                pytest.fail(output.read_text(encoding='utf-8'))
            yield base, secret
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


class Journey:
    def __init__(self, browser, server):
        self.base, self.secret = server
        self.uid = 'journey-' + uuid.uuid4().hex
        self.context = browser.new_context(viewport={'width': 1440, 'height': 950})
        self.context.add_init_script('window.__E2E_INITIAL_UID = sessionStorage.getItem("journey_uid") || ' + json.dumps(self.uid))
        for name, source in [('app', FIREBASE_APP_STUB), ('auth', FIREBASE_AUTH_STUB), ('firestore', FIRESTORE_GUARD)]:
            self.context.route(f'https://www.gstatic.com/firebasejs/9.22.0/firebase-{name}.js',
                lambda route, request, source=source: route.fulfill(content_type='application/javascript', body=source))
        self.context.route('https://cloud.umami.is/**', lambda r: r.fulfill(body='/* analytics disabled */'))
        self.context.tracing.start(screenshots=True, snapshots=True, sources=True)
        self.page = self.context.new_page()
        self.api = self.context.request
        self.control('seed', {'gate': False})

    def control(self, action, data=None):
        url = f'{self.base}/_journey/{self.uid}/{action}'
        kwargs = {'headers': {'X-Journey-Secret': self.secret, 'Connection': 'close'}}
        response = self.api.get(url, **kwargs) if data is None and action == 'state' else self.api.post(url, data=data or {}, **kwargs)
        assert response.ok, response.text()
        return response.json()

    def request(self, method, path, data=None, uid=None):
        return self.api.fetch(self.base + path, method=method,
            headers={'Authorization': 'Bearer token-' + (uid or self.uid), 'Connection': 'close'}, data=data)

    def settled(self):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            state = self.control('state')
            turns = [turn['data'] for chat in state['collections'].get('chats', {}).values()
                     for turn in chat['children'].get('turns', {}).values()]
            if turns and all(turn['status'] != 'pending' for turn in turns):
                return state
            time.sleep(.05)
        pytest.fail('Native turn did not reach terminal state: ' + json.dumps(state))

    def open(self):
        self.page.goto(self.base + '/app', wait_until='domcontentloaded')
        self.page.wait_for_function('uid => window.__consensioAuthState?.uid === uid && window.App?.state.get("isUserPro") === true', arg=self.uid)

    def producer_finished(self):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            streams = self.control('state')['streams']
            if streams and all(s['lease'] == 'released' and s['response_ended'] for s in streams):
                return streams
            time.sleep(.05)
        pytest.fail('Real agent producer/response did not finish: ' + json.dumps(streams))

    def run(self, question):
        self.page.fill('#questionInput', question)
        self.page.click('#sendButton')
        self.page.wait_for_function('q => window.App.runRegistry.list().some(r => r.question === q && r.status === "succeeded")', arg=question, timeout=60000)
        self.page.wait_for_function('q => window.App.runRegistry.list().some(r => r.question === q && r.persistence?.status === "saved")', arg=question, timeout=30000)
        return self.page.evaluate('q => {const r=window.App.runRegistry.list().find(r => r.question === q); return {run:r.runId, chat:r.chatSession.activeChatId, turn:r.chatSession.activeTurnId, bookmark:r.bookmark.id, result:r.consensus.resultId};}', question)

    def close(self):
        self.control('release', {})
        Path(f'test-results/{self.uid}-state.json').write_text(json.dumps(self.control('state'), indent=2), encoding='utf-8')
        diagnostic = self.page.evaluate('() => ({runs:window.App?.runRegistry?.list(), body:document.body.innerText})')
        Path(f'test-results/{self.uid}-browser.json').write_text(json.dumps(diagnostic, indent=2), encoding='utf-8')
        self.context.tracing.stop(path=f'test-results/{self.uid}.zip')
        self.control('cleanup', {})
        self.context.close()


@pytest.fixture()
def journey(browser, journey_server):
    value = Journey(browser, journey_server)
    try:
        yield value
    finally:
        value.close()


def test_j01_saved_consensus_reload_followup_keeps_native_identity_and_context(journey):
    j = journey
    j.open()
    first = j.run('When was the Eiffel Tower completed? ' + j.uid)
    saved = j.request('GET', '/bookmarks/' + first['bookmark'])
    assert saved.ok, saved.text()
    assert j.request('GET', '/bookmarks/' + first['bookmark'], uid='journey-'+'f'*32).status == 404
    j.page.reload()
    j.page.wait_for_function('() => typeof window.openBookmark === "function" && window.__consensioAuthState?.known')
    j.page.evaluate('id => window.openBookmark(id)', first['bookmark'])
    expect(j.page.locator('#consensusResponse')).to_contain_text('Mock consensus', timeout=15000)
    expect(j.page.locator('#questionInput')).to_have_attribute('placeholder', 'Ask a follow-up question')
    second = j.run('How tall is it? ' + j.uid)
    assert second['chat'] == first['chat'] and second['turn'] != first['turn']
    assert second['bookmark'] == first['bookmark']
    native = j.control('state')
    Path(f'test-results/{j.uid}-state.json').write_text(json.dumps(native, indent=2), encoding='utf-8')
    turns = native['collections']['chats'][first['chat']]['children']['turns']
    assert len(turns) == 2
    assert all(v['data']['status'] == 'completed' for v in turns.values())
    context_id = turns[second['turn']]['data']['context_version_id']
    context = native['collections']['chats'][first['chat']]['children']['context_versions'][context_id]['data']
    assert context['target_turn_id'] == second['turn']
    assert context['recent_turn_id'] == first['turn']
    assert context['target_position'] == 2 and context['status'] == 'ready'
    assert turns[first['turn']]['data'].get('context_version_id') is None
    assert j.page.evaluate('id => window.bookmarksData.find(b => b.id === id).has_consensus', first['bookmark']) is True
    receipts = [record['data'] for record in native['collections']['usage_runs'].values()]
    assert len(receipts) == 2
    assert all(r['kind'] == 'regular' and r['status'] == 'consumed' for r in receipts)
    assert all(len([op for op in r['booked_operations'] if op == 'consensus']) == 1 for r in receipts)
    budget = j.request('POST', '/usage', {'id_token': 'token-' + j.uid}).json()['token_budget']
    assert budget['used'] == sum(op['measured'] + op['estimated'] for r in receipts for op in r['booked_operations'].values())
    assert budget['reserved'] == 0


def test_j02_stop_reload_recover_preserves_partial_and_charges_only_started_step(journey):
    j = journey
    j.control('seed', {'gate': True})
    j.open()
    j.page.locator('#attachTrigger').click()
    j.page.locator('#runModeControl [data-value="agent"]').click()
    j.page.fill('#questionInput', 'JOURNEY_STOP ' + j.uid)
    with j.page.expect_request(lambda r: r.url == j.base + '/agent' and r.method == 'POST') as started:
        j.page.click('#sendButton')
    original_request = started.value.post_data_json
    expect(j.page.locator('#agentAnswerBody')).to_contain_text('Saved partial answer', timeout=30000)
    # The composer stop cancels its SSE request. The server observes disconnect;
    # the native receipt/settlement, rather than a fabricated /stop reply, proves it.
    j.page.wait_for_function('() => Date.now() - App.runRegistry.visible().startedAt > 800')
    j.page.locator('#sendButton').click()
    j.page.wait_for_function('() => App.runRegistry.visible()?.status === "canceled"')
    j.control('release', {})
    state = j.settled()
    Path(f'test-results/{j.uid}-state.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
    assert len(state['calls']) == 8  # orchestrator + six comparison providers + partial synthesis
    chat_id, chat = next(iter(state['collections']['chats'].items()))
    turn_id, turn = next(iter(chat['children']['turns'].items()))
    assert turn['data']['status'] == 'failed'
    assert turn['data']['agent_failure']['code'] == 'cancelled'
    budget = j.request('POST', '/usage', {'id_token': 'token-' + j.uid}).json()['token_budget']
    assert budget['used'] == 8 * 150 and budget['reserved'] == 0
    j.page.reload()
    j.page.wait_for_function('() => window.__consensioAuthState?.known && window.openBookmark')
    bookmark_id = next(iter(state['collections']['bookmarks']))
    j.page.evaluate('id => window.openBookmark(id)', bookmark_id)
    expect(j.page.locator('#agentAnswerBody')).to_contain_text('Saved partial answer', timeout=15000)
    expect(j.page.locator('#agentAnswerError')).to_contain_text('This answer may be incomplete')
    recover = j.request('POST', '/agent', {**original_request,
        'chat_id': chat_id, 'recover_only': True})
    assert recover.ok, recover.text()
    assert 'Saved partial answer' in recover.text()
    after = j.control('state')
    assert after['calls'] == state['calls']
    assert j.request('POST', '/usage', {'id_token': 'token-' + j.uid}).json()['token_budget']['used'] == 8 * 150


def test_j03_historical_source_job_resumes_and_pages_a_native_revision(journey):
    j = journey
    j.open()
    run = j.run('Historical source comparison ' + j.uid)
    snapshot = j.control('legacy-source', run)
    job_id = snapshot['job_id']
    j.page.evaluate('() => localStorage.setItem("openrouterKey", "journey-own-source-key")')
    j.page.reload()
    j.page.wait_for_function('() => window.__consensioAuthState?.known && window.openBookmark')
    with j.page.expect_response(lambda r: r.url.endswith(f'/api/source-checks/{job_id}/resume')) as resumed:
        j.page.evaluate('id => window.openBookmark(id)', run['bookmark'])
    assert resumed.value.ok, resumed.value.text()
    assert j.request('GET', f'/api/source-checks/{job_id}', uid='journey-'+'f'*32).status == 404
    old = j.request('GET', f'/api/source-checks/{job_id}').json()
    completion = j.control('source-finish', {'job_id': job_id})
    assert completion['worker'] == {'provider_calls': 9, 'fetch_calls': 1,
        'stale_commits_rejected': 9, 'own_key_only': True, 'key_forgotten': True, 'replay_worked': False}
    finished = completion['snapshot']
    assert finished['status'] == 'complete' and finished['scope']['checked_pairs'] == 9
    assert finished['runtime']['calls'] == 9
    assert finished['runtime']['prompt_tokens'] == 900 and finished['runtime']['completion_tokens'] == 450
    assert j.request('GET', f'/api/source-checks/{job_id}?cursor=1&revision={old["source_verification"]["revision"]}').status == 409
    # The actual bookmark observer gathers every page before publishing a revision.
    j.page.wait_for_function('() => {const v=window.App.runRegistry.getSelectedConversationBasis()?.currentTurn?.source_verification; return v?.status === "complete" && v.findings.length === 9;}', timeout=20000)
    expect(j.page.locator('.source-verification-status').first).to_have_text('Source check complete')
    expect(j.page.locator('body')).to_contain_text('9/9 checked')
    j.page.reload()
    j.page.wait_for_function('() => window.__consensioAuthState?.known && window.openBookmark')
    j.page.evaluate('id => window.openBookmark(id)', run['bookmark'])
    expect(j.page.locator('.source-verification-status').first).to_have_text('Source check complete', timeout=20000)
    expect(j.page.locator('body')).to_contain_text('9/9 checked')
    assert 'journey-own-source-key' not in json.dumps(j.control('state'))


def test_j04_app_share_follow_watch_versions_bind_to_saved_native_result(journey):
    j = journey
    j.open()
    run = j.run('Watch the Eiffel Tower completion year ' + j.uid)
    # MOCK_LLM suppresses live pending publication by design. Reopening uses
    # the real saved-bookmark adapter to create the owner-bound pending result.
    j.page.reload()
    j.page.wait_for_function('() => window.__consensioAuthState?.known && window.openBookmark')
    j.page.evaluate('id => window.openBookmark(id)', run['bookmark'])
    # Use the real app share adapter/dialog, including its prepared saved result.
    j.page.locator('#consensusResponse').get_by_text('Share', exact=True).click()
    with j.page.expect_response(lambda r: r.url == j.base + '/api/share' and r.request.method == 'POST') as published:
        j.page.get_by_role('button', name=re.compile('Create.*link|Create share|Publish', re.I)).click()
    assert published.value.ok, published.value.text()
    share = published.value.json()
    native = j.control('state')
    pending = next(iter(native['global_owned']['pending_results'].values()))['data']
    assert pending['owner_uid'] == j.uid and 'Mock consensus' in pending['consensus_md']
    assert native['global_owned']['shares'][share['share_id']]['data']['owner_uid'] == j.uid
    wid_response = j.request('POST', '/api/watch', {'share_id': share['share_id'],
        'interval': 'daily', 'visibility': 'public', 'email_enabled': True})
    assert wid_response.ok, wid_response.text()
    wid = wid_response.json()['watch']['id']
    assert j.request('DELETE', '/api/share/' + share['share_id'], {}, uid='journey-'+'f'*32).status == 403
    j.page.goto(j.base + share['path'])
    expect(j.page.locator('#consensusView .share-md')).to_contain_text('Mock consensus')
    j.page.locator('#shareFollowForm input[type=email]').fill(j.uid + '@example.invalid')
    j.page.locator('#shareFollowForm button[type=submit]').click()
    expect(j.page.locator('#shareFollowDone')).to_contain_text('Check your inbox')
    mail = j.control('state')['messages'][-1]['text']
    token = re.search(r'/watch/follow/confirm\?token=([^\s]+)', mail).group(1)
    confirmation = j.request('GET', '/watch/follow/confirm?token=' + token)
    assert confirmation.ok and "You're following this question" in html.unescape(confirmation.text())
    advanced = j.control('watch-run', {'watch_id': wid})
    version = advanced['run']['run_id']
    assert version and advanced['share']['latest_watch_run_id'] == version
    j.page.goto(j.base + share['path'] + '?version=' + version)
    expect(j.page.locator(f'.watch-version-link[href$="?version={version}"]').locator('xpath=ancestor::li')).to_have_class(re.compile('is-selected'))
    expect(j.page.locator('#consensusView .share-md')).to_contain_text('Mock consensus')
    expect(j.page.locator('#consensusView .share-md')).to_contain_text('Watch revision ' + version)
    j.page.goto(j.base + share['path'] + '?version=original')
    expect(j.page.locator('#consensusView').get_by_role('heading', name='Original consensus', exact=True)).to_be_visible()
    expect(j.page.locator('#consensusView .share-md')).not_to_contain_text('Watch revision ' + version)
    history = j.control('state')['global_owned']['shares'][share['share_id']]['children']['watch_history']
    assert version in history and 'Watch revision ' + version in history[version]['data']['consensus_md']


def test_j05_delete_during_agent_work_fences_late_writes_and_owner_switch(journey, browser, journey_server):
    j = journey
    other = Journey(browser, journey_server)
    try:
        other.open()
        control = other.run('Untouched control answer ' + other.uid)
        control_budget = other.request('POST', '/usage', {'id_token': 'token-' + other.uid}).json()['token_budget']['used']
        j.control('seed', {'gate': True})
        revision = j.request('GET', '/api/my/memory').json()['revision']
        memory = j.request('PUT', '/api/my/memory', {'enabled': True, 'role': 'Original owner memory', 'expected_revision': revision})
        assert memory.ok, memory.text()
        j.open()
        j.page.locator('#attachTrigger').click()
        j.page.locator('#runModeControl [data-value="agent"]').click()
        j.page.fill('#questionInput', 'JOURNEY_DELETE ' + j.uid)
        j.page.click('#sendButton')
        expect(j.page.locator('#agentAnswerBody')).to_contain_text('Saved partial answer', timeout=30000)
        deleted = j.request('POST', '/delete_account', {'id_token': 'token-' + j.uid})
        assert deleted.status == 200, deleted.text()
        assert deleted.json()['status'] == 'deleted'
        assert j.control('state')['streams'] == [{'lease': 'running', 'response_ended': False}]
        j.page.evaluate('async uid => {sessionStorage.setItem("journey_uid", uid); await window.__switchE2EUser(uid);}', other.uid)
        j.control('release', {})
        # The real stream_events finally releases capacity only after the
        # producer and its settlement/cleanup stack have unwound.
        assert j.producer_finished() == [{'lease': 'released', 'response_ended': True}]
        expect(j.page.locator('#agentAnswerBody')).to_be_hidden()
        assert j.page.evaluate('() => window.__consensioAuthState.uid') == other.uid
        j.page.reload()
        j.page.wait_for_function('uid => window.__consensioAuthState?.uid === uid', arg=other.uid)
        j.page.evaluate('id => window.openBookmark(id)', control['bookmark'])
        expect(j.page.locator('#consensusResponse')).to_contain_text('Mock consensus', timeout=15000)
        assert j.request('GET', '/api/my/memory').status == 401
        assert j.request('GET', '/bookmarks/' + control['bookmark']).status == 401
        assert other.request('GET', '/bookmarks/' + control['bookmark']).ok
        native = j.control('state')
        assert native['user'] is None and native['collections'] == {}
        assert native['tombstone']['status'] == 'completed'
        assert other.control('state')['user']['tier'] == 'pro'
        assert other.request('POST', '/usage', {'id_token': 'token-' + other.uid}).json()['token_budget']['used'] == control_budget
    finally:
        other.close()


def test_persistence_quota_failure_keeps_answer_visible_and_never_claims_saved(journey):
    j = journey
    # A real persisted exhausted storage counter, not a mocked error response.
    j.control('seed', {'storage_full': True})
    j.open()
    question = 'Storage exhausted ' + j.uid
    j.page.fill('#questionInput', question)
    j.page.click('#sendButton')
    j.page.wait_for_function('() => App.runRegistry.visible()?.status === "succeeded"', timeout=60000)
    j.page.wait_for_function('() => App.runRegistry.visible()?.persistence.status === "error"', timeout=30000)
    expect(j.page.locator('#consensusResponse')).to_contain_text('Mock consensus')
    expect(j.page.locator('body')).to_contain_text(re.compile('bookmark.*(limit|save)|could not.*sav', re.I))
    native = j.control('state')
    assert native['collections'].get('bookmarks', {}) == {}
    turns = [t['data'] for c in native['collections']['chats'].values() for t in c['children']['turns'].values()]
    assert len(turns) == 1 and turns[0]['status'] == 'completed'
    assert 'Mock consensus' in turns[0]['consensus']
    assert j.page.evaluate('() => App.runRegistry.visible().bookmark.latestMeta?.has_consensus') is not True
