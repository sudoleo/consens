"""Built Agent composer: a file from Google Drive, end to end in the browser.

Google's scripts (Identity Services, Picker) and the Drive API are stubbed at
the network edge; the app's own CSP, menu, attachments, consent and upload run
as built. No request leaves the test machine.
"""
import json
import pytest
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json
from test_agent_chat_frontend import CATALOG, _choose_mode, _snapshot

CHAT, FILE = 'a' * 32, 'f' * 32
DRIVE = {'client_id': 'client.apps.googleusercontent.com', 'api_key': 'AIzaSyExampleExampleExample0123', 'app_id': '123456789012'}
DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

GIS = """window.google = window.google || {};
window.google.accounts = {oauth2: {
  initTokenClient: config => { window.__drive = {config, requests: 0};
    const client = {callback: config.callback, requestAccessToken: options => { window.__drive.requests++; window.__drive.prompt = options.prompt;
      setTimeout(() => client.callback({access_token: 'drive-token', expires_in: 3599, scope: config.scope}), 10); }};
    return client; },
  hasGrantedAllScopes: (response, scope) => response.scope === scope}};"""

PICKER = """window.google = window.google || {};
window.gapi = {load: (name, options) => {
  const builder = {}; let callback = null;
  for (const name of ['addView','setOAuthToken','setDeveloperKey','setAppId','setOrigin','setTitle','enableFeature','setMaxItems'])
    builder[name] = (...args) => { (window.__picker = window.__picker || {})[name] = args; return builder; };
  builder.setCallback = fn => { callback = fn; return builder; };
  builder.build = () => ({setVisible: () => setTimeout(() => callback({action: 'picked', docs: [
    {id: '1AbCdEfGhIjKlMnOp', name: 'Supplier offers', mimeType: 'application/vnd.google-apps.document'}]}), 10)});
  class DocsView { setMimeTypes() { return this; } setIncludeFolders() { return this; } setSelectFolderEnabled() { return this; } setMode() { return this; } }
  window.google.picker = {PickerBuilder: function () { return builder; }, DocsView, ViewId: {DOCS: 'all'}, DocsViewMode: {LIST: 'list'},
    Feature: {MULTISELECT_ENABLED: 'multi'}, Response: {ACTION: 'action', DOCUMENTS: 'docs'}, Action: {PICKED: 'picked'},
    Document: {ID: 'id', NAME: 'name', MIME_TYPE: 'mimeType'}};
  options.callback(); }};"""


@pytest.mark.parametrize('width', [1280, 390])
def test_drive_file_becomes_an_attachment_with_one_consent_per_chat(browser, phase4_server, width):
    context, page = _real_firebase_page(browser, phase4_server, has_touch=width < 700)
    uploads, runs, drive_calls, errors = [], [], [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        page.set_viewport_size({'width': width, 'height': 900})
        page.route('**/user_status', lambda r: _json(r, {'tier': 'pro', 'is_pro': True, 'agent_access': True}))
        page.route('**/usage', lambda r: _json(r, {'is_pro': True, 'remaining': 100, 'total_limit': 100}))
        page.route('**/agent/models', lambda r: _json(r, CATALOG))
        page.route('**/agent/budget', lambda r: _json(r, {'token_budget': {'remaining': 250000, 'limit': 250000}}))
        page.route('**/chats', lambda r: _json(r, {'chat': {'id': CHAT}}))
        page.route(f'**/agent/chats/{CHAT}/actions', lambda r: _json(r, {'actions': [], 'evidence': [], 'google_data': bool(runs), 'google_consent': bool(runs), 'writes': False}))
        # Drive works without Gmail/Calendar being set up on the installation.
        page.route('**/agent/google/connections', lambda r: _json(r, {'configured': False, 'writes': False, 'drive': DRIVE, 'connections': []}))
        page.route('https://accounts.google.com/gsi/client', lambda r: r.fulfill(body=GIS, content_type='text/javascript'))
        page.route('https://apis.google.com/js/api.js', lambda r: r.fulfill(body=PICKER, content_type='text/javascript'))
        def drive(route):
            drive_calls.append((route.request.url, route.request.headers.get('authorization')))
            route.fulfill(body=b'PK\x03\x04 exported document', content_type=DOCX)
        page.route('https://www.googleapis.com/drive/v3/files/**', drive)
        def files(route):
            if route.request.method == 'POST':
                body = route.request.post_data_json; uploads.append(body)
                meta = {'id': FILE, 'name': body['name'], 'mime': DOCX, 'size': 24, 'status': 'ready', 'warnings': [], 'kind': 'drive_file',
                        'origin': {'source': 'google_drive', 'file_id': body.get('drive_file_id')},
                        'created_at': '2026-10-03T10:00:00Z', 'expires_at': '2099-11-02T10:00:00Z'}
                _json(route, {'file': meta})
            else:
                _json(route, {'files': []})
        page.route(f'**/agent/chats/{CHAT}/files', files)
        def answer(route):
            payload = route.request.post_data_json; runs.append(payload)
            # As normalize_attachment_meta saves it: metadata plus the Drive source.
            attached = [{'id': FILE, 'name': 'Supplier offers.docx', 'mime': DOCX, 'size': 24, 'source': 'google_drive'}] if payload['file_ids'] else []
            turn = {'id': str(len(runs)) * 32, 'question': payload['question'], 'consensus': 'The second offer is cheaper (Supplier offers.docx).',
                    'execution_mode': 'agent', 'status': 'completed', 'attachments': attached,
                    'agent_settings': {'file_ids': payload['file_ids'], 'google_data': True}}
            result = {'chat_id': CHAT, 'turn_id': turn['id'], 'turn': turn, 'response': turn['consensus'], 'google_data': True,
                      'google_consent': payload['google_data_consent'],
                      'bookmark_meta': {'id': payload['bookmark_id'], 'chat_id': CHAT, 'execution_mode': 'agent', 'query': payload['question']}}
            route.fulfill(content_type='text/event-stream', body='event: final\ndata: ' + json.dumps(result) + '\n\n')
        page.route('**/agent', answer)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, 'agent')
        # The (+) menu offers Drive next to "Add files"; Gmail & Calendar stay
        # away because this installation has not set them up.
        page.locator('#attachTrigger').click()
        option = page.locator('#attachDriveOption')
        expect(option).to_be_visible()
        expect(option).to_contain_text('Add from Google Drive')
        expect(page.locator('#agentGoogleMenuOption')).to_be_hidden()
        _snapshot(page, f'drive-menu-{width}')
        option.click()
        chip = page.locator('#attachmentBar .attachment-chip')
        expect(chip).to_contain_text('Supplier offers.docx')
        expect(chip).to_contain_text('Google Drive')
        assert page.evaluate('window.__drive.prompt') == ''
        assert page.evaluate('window.__picker.setAppId') == [DRIVE['app_id']]
        assert drive_calls == [('https://www.googleapis.com/drive/v3/files/1AbCdEfGhIjKlMnOp/export?mimeType=' + DOCX.replace('.', '.').replace('/', '%2F'), 'Bearer drive-token')]
        # Google data in the message: one consent, for this chat.
        page.locator('#questionInput').fill('Which supplier offer is better?')
        consent = page.locator('#agentGoogleChips').get_by_label('Share with the models in this chat', exact=True)
        expect(consent).to_be_visible()
        assert page.evaluate('App.agentGoogle.blocker().action') == 'google-consent'
        _snapshot(page, f'drive-consent-{width}')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        consent.check()
        page.locator('#sendButton').click()
        expect(page.locator('#agentAnswerBody')).to_contain_text('cheaper')
        assert uploads == [{'name': 'Supplier offers.docx', 'data': uploads[0]['data'], 'drive_file_id': '1AbCdEfGhIjKlMnOp'}]
        assert 'drive-token' not in json.dumps(uploads) and 'drive-token' not in json.dumps(runs)
        assert runs[0]['file_ids'] == [FILE] and runs[0]['google_data_consent'] is True
        # The sent message keeps the file with its origin.
        expect(page.locator('#threadAskAttachments .attachment-chip')).to_contain_text('Google Drive')
        # The follow-up needs no second consent; the chat says why it is private.
        page.locator('#questionInput').fill('And the delivery times?')
        expect(consent).to_be_hidden()
        expect(page.locator('#agentGoogleChips')).to_contain_text('Private chat · Google data')
        assert page.evaluate('App.agentGoogle.blocker()') is None
        _snapshot(page, f'drive-followup-{width}')
        page.locator('#sendButton').click()
        expect(page.locator('#agentAnswerBody')).to_contain_text('cheaper')
        assert runs[1]['google_data_consent'] is True
        assert not errors, errors
    except Exception:
        _snapshot(page, f'drive-failure-{width}')
        raise
    finally:
        context.close()
