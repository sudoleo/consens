"""WP-29: Chromium → built AppFirebase → real HTTP → native Firestore.

Only Firebase identity SDK and external model/messaging services are replaced.
No browser route interception of application APIs and no injected UI answers.
"""
import json
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
from test_phase4_frontend import FIREBASE_APP_STUB, FIREBASE_AUTH_STUB



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
    # uid: a second device of an existing journey account (close it with
    # context.close(); the account's own journey cleans up).
    def __init__(self, browser, server, uid=None):
        self.base, self.secret = server
        self.uid = uid or 'journey-' + uuid.uuid4().hex
        self.context = browser.new_context(viewport={'width': 1440, 'height': 950})
        self.context.add_init_script('window.__E2E_INITIAL_UID = sessionStorage.getItem("journey_uid") || ' + json.dumps(self.uid))
        # Agent is the default since 2026-10-02; these journeys start from a
        # Compare run (the browser runs no Consensus since 2026-10-25) and
        # pick Agent explicitly where they need it. Seeded once per tab so a
        # reload keeps the mode the journey chose.
        self.context.add_init_script(
            "if (!sessionStorage.getItem('journeyRunModeSeeded')) {"
            " localStorage.setItem('runMode', 'compare');"
            " localStorage.setItem('consensio.settingsReset', '2026-10-12');"
            " sessionStorage.setItem('journeyRunModeSeeded', '1'); }")
        for name, source in [('app', FIREBASE_APP_STUB), ('auth', FIREBASE_AUTH_STUB)]:
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
        return self.page.evaluate('q => {const r=window.App.runRegistry.list().find(r => r.question === q); return {run:r.runId, bookmark:r.bookmark.id};}', question)

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


def test_j01_saved_comparison_reloads_and_the_next_question_is_a_new_chat(journey):
    """Compare: the answers are saved to their own bookmark, reopen after a
    reload, and the next question starts a comparison of its own (it
    continues no chat and asks for no consensus)."""
    j = journey
    j.open()
    first = j.run('When was the Eiffel Tower completed? ' + j.uid)
    saved = j.request('GET', '/bookmarks/' + first['bookmark'])
    assert saved.ok, saved.text()
    assert j.request('GET', '/bookmarks/' + first['bookmark'], uid='journey-'+'f'*32).status == 404
    j.page.reload()
    j.page.wait_for_function('() => typeof window.openBookmark === "function" && window.__consensioAuthState?.known')
    j.page.evaluate('id => window.openBookmark(id)', first['bookmark'])
    expect(j.page.locator('.is-direct .answer-reader-body').first).to_contain_text('mock answer', timeout=15000)
    expect(j.page.locator('#consensusOutput')).to_be_hidden()
    second = j.run('How tall is it? ' + j.uid)
    assert second['bookmark'] != first['bookmark']
    native = j.control('state')
    Path(f'test-results/{j.uid}-state.json').write_text(json.dumps(native, indent=2), encoding='utf-8')
    assert native['collections'].get('chats', {}) == {}
    assert set(native['collections']['bookmarks']) == {first['bookmark'], second['bookmark']}
    receipts = [record['data'] for record in native['collections']['usage_runs'].values()]
    assert len(receipts) == 2
    assert all(r['status'] == 'consumed' for r in receipts)
    assert all('consensus' not in r['booked_operations'] for r in receipts)
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
    # The composer stop sends the explicit request Stop (a closed connection no
    # longer ends a turn); the native receipt/settlement proves it took effect.
    j.page.wait_for_function('() => Date.now() - App.runRegistry.visible().startedAt > 800')
    j.page.locator('#sendButton').click()
    j.page.wait_for_function('() => App.runRegistry.visible()?.status === "canceled"')
    j.control('release', {})
    state = j.settled()
    Path(f'test-results/{j.uid}-state.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
    # Comparison call + the three providers of Daily (since 2026-10-28) +
    # the agent's partial answer.
    assert len(state['calls']) == 5
    chat_id, chat = next(iter(state['collections']['chats'].items()))
    turn_id, turn = next(iter(chat['children']['turns'].items()))
    assert turn['data']['status'] == 'failed'
    assert turn['data']['agent_failure']['code'] == 'cancelled'
    budget = j.request('POST', '/usage', {'id_token': 'token-' + j.uid}).json()['token_budget']
    assert budget['used'] == 5 * 150 and budget['reserved'] == 0
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
    assert j.request('POST', '/usage', {'id_token': 'token-' + j.uid}).json()['token_budget']['used'] == 5 * 150


def test_j02b_agent_turn_survives_a_reload_and_is_followed_to_its_answer(journey):
    j = journey
    j.control('seed', {'gate': True})
    j.open()
    j.page.locator('#attachTrigger').click()
    j.page.locator('#runModeControl [data-value="agent"]').click()
    question = 'Survives reload ' + j.uid
    j.page.fill('#questionInput', question)
    j.page.click('#sendButton')
    expect(j.page.locator('#agentAnswerBody')).to_contain_text('Saved partial answer', timeout=30000)
    # The reload closes the stream; the turn keeps running on the server.
    j.page.reload(wait_until='domcontentloaded')
    j.page.wait_for_function('uid => window.__consensioAuthState?.uid === uid', arg=j.uid)
    j.page.wait_for_function('q => App.runRegistry.list().some(r => r.question === q && r.status === "running")',
                             arg=question, timeout=30000)
    expect(j.page.locator('#agentAnswerBody')).to_contain_text('Saved partial answer', timeout=15000)
    [stream] = j.control('state')['streams'][:1]
    assert stream['lease'] == 'running'
    j.control('release', {})
    j.page.wait_for_function('q => App.runRegistry.list().some(r => r.question === q && r.status === "succeeded")',
                             arg=question, timeout=60000)
    state = j.settled()
    chat_id, chat = next(iter(state['collections']['chats'].items()))
    [turn] = chat['children']['turns'].values()
    assert turn['data']['status'] == 'completed'
    assert state['collections']['bookmarks']
    # Followed, never sent again: every model step ran exactly once.
    steps = [call['step'] for call in state['calls']]
    assert steps and len(steps) == len(set(steps)), steps
    assert j.page.evaluate("() => sessionStorage.length === 0 || !Object.keys(sessionStorage).some(k => k.startsWith('agent_pending_runs_'))")


def test_j04_app_share_follow_watch_versions_bind_to_saved_native_result(journey):
    """A saved Agent answer is shared, followed and watched; each Watch
    version binds to the share (the Watch runs the server's pipeline)."""
    j = journey
    j.open()
    j.page.locator('#attachTrigger').click()
    j.page.locator('#runModeControl [data-value="agent"]').click()
    question = 'Watch the Eiffel Tower completion year ' + j.uid
    j.page.fill('#questionInput', question)
    j.page.click('#sendButton')
    j.page.wait_for_function('q => App.runRegistry.list().some(r => r.question === q && r.status === "succeeded")',
                             arg=question, timeout=180000)
    j.producer_finished()
    j.settled()
    # Use the real app share adapter/dialog, including its prepared saved result.
    j.page.locator('#agentAnswer .agent-share-pill').click()
    confirm = j.page.locator('#shareConfirmBtn')
    expect(confirm).to_have_text('Create public link', timeout=15000)
    with j.page.expect_response(lambda r: r.url == j.base + '/api/share' and r.request.method == 'POST') as published:
        confirm.click()
    assert published.value.ok, published.value.text()
    share = published.value.json()
    native = j.control('state')
    pending = next(iter(native['global_owned']['pending_results'].values()))['data']
    answer = 'Saved partial answer for ' + j.uid
    assert pending['owner_uid'] == j.uid and answer in pending['consensus_md']
    assert native['global_owned']['shares'][share['share_id']]['data']['owner_uid'] == j.uid
    wid_response = j.request('POST', '/api/watch', {'share_id': share['share_id'],
        'interval': 'daily', 'visibility': 'public', 'email_enabled': True})
    assert wid_response.ok, wid_response.text()
    wid = wid_response.json()['watch']['id']
    assert j.request('DELETE', '/api/share/' + share['share_id'], {}, uid='journey-'+'f'*32).status == 403
    j.page.goto(j.base + share['path'])
    # With a Watch the share renders the Watch page (watch_share.html).
    expect(j.page.locator('.wp-answer .share-md')).to_contain_text(answer)
    j.page.locator('#shareFollowForm input[type=email]').fill(j.uid + '@example.invalid')
    j.page.locator('#shareFollowForm button[type=submit]').click()
    expect(j.page.locator('#shareFollowDone')).to_contain_text('Check your inbox')
    mail = j.control('state')['messages'][-1]['text']
    token = re.search(r'/watch/follow/confirm\?token=([^\s]+)', mail).group(1)
    # The mail link only asks (mail scanners open every link); its button confirms.
    j.page.goto(j.base + '/watch/follow/confirm?token=' + token)
    j.page.get_by_role('button', name='Confirm and follow').click()
    expect(j.page.locator('h1')).to_have_text("You're following this question")
    advanced = j.control('watch-run', {'watch_id': wid})
    version = advanced['run']['run_id']
    assert version and advanced['share']['latest_watch_run_id'] == version
    j.page.goto(j.base + share['path'] + '?version=' + version)
    expect(j.page.locator('.wp-version.is-current')).to_have_text('Shown above')
    expect(j.page.locator('.wp-answer .share-md')).to_contain_text('Mock consensus')
    expect(j.page.locator('.wp-answer .share-md')).to_contain_text('Watch revision ' + version)
    j.page.goto(j.base + share['path'] + '?version=original')
    expect(j.page.locator('#wpAnswerHeading')).to_have_text('The answer then')
    expect(j.page.locator('.wp-answer .share-md')).not_to_contain_text('Watch revision ' + version)
    history = j.control('state')['global_owned']['shares'][share['share_id']]['children']['watch_history']
    assert version in history and 'Watch revision ' + version in history[version]['data']['consensus_md']


def test_j04b_agent_answer_shares_from_under_it_and_from_the_chat_list(journey):
    """An Agent answer (the default since October) gets a public page: the
    Share pill under the answer and Share in the chat menu publish the saved
    turn, both the same link, and the page shows the answer."""
    j = journey
    j.open()
    j.page.locator('#attachTrigger').click()
    j.page.locator('#runModeControl [data-value="agent"]').click()
    question = 'Is the James Webb telescope still working ' + j.uid
    j.page.fill('#questionInput', question)
    j.page.click('#sendButton')
    # Comparison, answer and both judges: on a busy machine over a minute.
    j.page.wait_for_function('q => App.runRegistry.list().some(r => r.question === q && r.status === "succeeded")',
                             arg=question, timeout=180000)
    j.producer_finished()
    state = j.settled()
    assert len(state['collections']['chats']) == 1
    [bookmark_id] = state['collections']['bookmarks']
    pill = j.page.locator('#agentAnswer .agent-share-pill')
    expect(pill).to_be_visible()
    j.page.locator('#agentAnswer').screenshot(path='test-results/agent-share-pill.png')
    pill.click()
    confirm = j.page.locator('#shareConfirmBtn')
    expect(confirm).to_have_text('Create public link', timeout=15000)
    with j.page.expect_response(lambda r: r.url == j.base + '/api/share' and r.request.method == 'POST') as published:
        confirm.click()
    assert published.value.ok, published.value.text()
    share = published.value.json()
    expect(j.page.locator('#shareModalTitle')).to_have_text('Public link created')
    stored = j.control('state')['global_owned']['shares'][share['share_id']]['data']
    assert stored['answer_mode'] == 'agent' and stored['indexed'] is False
    assert 'Saved partial answer for ' + j.uid in stored['consensus_md']
    j.page.keyboard.press('Escape')

    # From the chat list, in a fresh page: the same answer, the same link.
    j.page.reload(wait_until='domcontentloaded')
    j.page.wait_for_function('() => window.__consensioAuthState?.known && window.openBookmark')
    j.page.evaluate("() => { const sidebar = document.querySelector('.sidebar');"
                    " if (sidebar?.classList.contains('collapsed')) document.getElementById('toggleSidebarButton').click(); }")
    row = j.page.locator(f'.bookmark[data-id="{bookmark_id}"]')
    row.hover()
    row.locator('.bookmark-menu-button').click()
    j.page.locator('.bookmark-menu-item[data-action="share"]').click()
    expect(j.page.locator('#agentAnswerBody')).to_contain_text('Saved partial answer for ' + j.uid, timeout=15000)
    expect(confirm).to_have_text('Create public link', timeout=15000)
    expect(j.page.locator('#shareDialogError')).to_be_hidden()
    with j.page.expect_response(lambda r: r.url == j.base + '/api/share' and r.request.method == 'POST') as again:
        confirm.click()
    assert again.value.ok, again.value.text()
    assert again.value.json()['share_id'] == share['share_id'] and again.value.json()['created'] is False
    pending = j.control('state')['global_owned']['pending_results']
    assert len(pending) == 1 and next(iter(pending.values()))['data']['answer_mode'] == 'agent'

    j.page.goto(j.base + share['path'])
    expect(j.page.locator('.share-header .eyebrow')).to_have_text('Shared answer')
    expect(j.page.locator('#consensusView .share-md')).to_contain_text('Saved partial answer for ' + j.uid)
    # The agent's one mode (since 2026-10-31): the share names who answered
    # and shows no comparison, also where the agent asked other models
    # (share_snapshots._agent_share_basis); its reviewers instead, when they
    # finished (_agent_review_notes, tests/e2e/test_share_review_notes.py).
    expect(j.page.get_by_text('Models compared')).to_have_count(0)
    expect(j.page.locator('#shareAboutHeading')).to_have_text('About this answer')
    assert '<b>0</b>' not in j.page.content()
    j.page.screenshot(path='test-results/agent-share-page.png', full_page=True)


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
        # Deletion finished while the producer is still inside the gated
        # provider step, so everything it writes after release is a late
        # write. Whether the HTTP response already ended is timing: the run
        # watcher polls saved state every 3 s, sees the deleted account and
        # cancels the shared stream, while the producer only unwinds (and
        # releases its lease) once the gate opens.
        [stream] = j.control('state')['streams']
        assert stream['lease'] == 'running'
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
        expect(j.page.locator('.is-direct .answer-reader-body').first).to_contain_text('mock answer', timeout=15000)
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


def test_settings_follow_the_account_to_another_device(journey, browser, journey_server):
    j = journey
    settings = lambda: j.control('state')['collections']['settings']['app']['data']['values']
    j.open()
    # A new account receives this browser's choices once (journeys start in Compare).
    j.page.wait_for_function('() => App.userSettings.status().loaded && !App.userSettings.status().pending.length')
    assert settings()['run_mode'] == 'compare'
    # A change on this device reaches the account.
    j.page.locator('#attachTrigger').click()
    j.page.locator('#runModeControl [data-value="agent"]').click()
    j.page.evaluate('() => App.userSettings.flush()')
    assert settings()['run_mode'] == 'agent'
    # Another device of the same account starts from it, over its own stored mode.
    device = Journey(browser, journey_server, uid=j.uid)
    try:
        device.open()
        assert device.page.evaluate("localStorage.getItem('runMode')") in ('compare', 'agent')
        device.page.wait_for_function('() => App.runMode.preference() === "agent"')
        expect(device.page.locator('#runModeSelect')).to_have_value('agent')
        # Signing out takes the account's settings out of this browser.
        device.page.evaluate('() => window.__switchE2EUser(null)')
        device.page.wait_for_function("() => localStorage.getItem('runMode') === null")
        assert device.page.evaluate('() => App.runMode.preference()') == 'agent'
        assert settings()['run_mode'] == 'agent'
    finally:
        device.context.close()


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
    expect(j.page.locator('.is-direct .answer-reader-body').first).to_contain_text('mock answer')
    # The notice line names the limit in the chat's own words (Apple-Audit H3).
    expect(j.page.locator('#appToasts')).to_contain_text(re.compile('chats are full|chat storage is full|couldn.t be saved', re.I))
    native = j.control('state')
    assert native['collections'].get('bookmarks', {}) == {}
    # A comparison keeps no chat of its own.
    assert native['collections'].get('chats', {}) == {}
