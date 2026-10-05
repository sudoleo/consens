"""Built Agent workspace on desktop and mobile; all APIs mocked, no external writes."""
import json
import os
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json
from test_agent_chat_frontend import CATALOG, _choose_mode

SHOTS = os.environ.get('AGENT_SCREENSHOTS')
CHAT, TURN_ONE, TURN_TWO, DOC = 'a' * 32, '1' * 32, '2' * 32, '9' * 32


def _shot(page, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(SHOTS) / f'{name}.png'))


def _routes(page, files):
    page.route('**/user_status', lambda r: _json(r, {'tier':'pro','is_pro':True,'agent_access':True}))
    page.route('**/usage', lambda r: _json(r, {'is_pro':True,'remaining':100,'total_limit':100,'deep_remaining':10,'deep_total_limit':10}))
    page.route('**/agent/models', lambda r: _json(r, CATALOG))
    page.route('**/agent/budget', lambda r: _json(r, {'token_budget':{'limit':250000,'remaining':249000}}))
    page.route('**/chats', lambda r: _json(r, {'chat':{'id':CHAT}}))
    page.route(f'**/agent/chats/{CHAT}/actions', lambda r: _json(r, {'actions': [], 'evidence': []}))


@pytest.mark.parametrize('width', [1280, 390, 320])
def test_upload_restoration_and_private_download(browser, phase4_server, width):
    context, page = _real_firebase_page(browser, phase4_server, has_touch=width < 700)
    files, calls, errors = [], [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    file_id = 'f'*32
    try:
        page.set_viewport_size({'width':width,'height':900})
        _routes(page, files)
        def resource(route):
            if route.request.method == 'POST':
                assert route.request.post_data_json['name'] == 'offer.txt'
                files.append({'id':file_id,'name':'offer.txt','mime':'text/plain','status':'ready','warnings':[], 'size':24,
                              'created_at':'2026-09-29T10:00:00Z','expires_at':'2099-10-29T10:00:00Z'})
                _json(route, {'file':files[0]})
            else: _json(route, {'files':files})
        page.route(f'**/agent/chats/{CHAT}/files', resource)
        page.route(f'**/agent/chats/{CHAT}/files/{file_id}', lambda r: r.fulfill(body='Price 42 EUR',headers={'Content-Disposition':'attachment; filename="offer.txt"'},content_type='text/plain'))
        def answer(route):
            payload=route.request.post_data_json; calls.append(payload)
            turn={'id':'b'*32,'question':payload['question'],'consensus':'Offer costs 42 EUR (offer.txt, lines 1-1).','execution_mode':'agent','status':'completed','attachments':files,'agent_settings':{'file_ids':[file_id]}}
            result={'chat_id':CHAT,'turn_id':turn['id'],'turn':turn,'response':turn['consensus'],'bookmark_meta':{'id':payload['bookmark_id'],'chat_id':CHAT,'execution_mode':'agent','query':payload['question'],'has_consensus':True}}
            route.fulfill(content_type='text/event-stream',body='event: final\ndata: '+json.dumps(result)+'\n\n')
        page.route('**/agent', answer)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page,'agent')
        page.wait_for_function('window.isUserPlus === true')
        page.locator('#attachFileInput').set_input_files({'name':'offer.txt','mimeType':'text/plain','buffer':b'Price 42 EUR'})
        expect(page.locator('#attachmentBar')).to_contain_text('offer.txt')
        page.locator('#questionInput').fill('Compare this offer')
        page.locator('#sendButton').click()
        expect(page.locator('#agentAnswerBody')).to_contain_text('42 EUR')
        # The file stays on the message it was sent with; no chat-wide list.
        expect(page.locator('#agentWorkspace')).to_have_count(0)
        chip = page.locator('#threadAskAttachments .attachment-chip-preview')
        expect(chip).to_contain_text('offer.txt')
        chip.click()
        viewer = page.locator('#attachmentViewerModal')
        expect(viewer.locator('iframe')).to_have_count(1)
        with page.expect_download() as pending:
            viewer.get_by_role('button',name='Download',exact=True).click()
        assert pending.value.suggested_filename == 'offer.txt'
        assert calls[0]['file_ids'] == [file_id] and 'attachments' not in calls[0]
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert not errors
    finally: context.close()


def _version(char, number, turn, ext):
    return {'id': char * 32, 'name': f'Decision brief-v{number}.{ext}', 'title': 'Decision brief', 'kind': 'document', 'document_id': DOC,
            'version': number, 'parent_version': number - 1, 'turn_id': turn, 'status': 'ready', 'size': 41000 + number,
            'mime': 'application/pdf' if ext == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'created_at': f'2026-09-2{number}T10:00:00Z', 'expires_at': '2099-10-29T10:00:00Z', 'warnings': []}


SAVED = [
    {'id': '7' * 32, 'name': 'Supplier offer 2026 (final).pdf', 'mime': 'application/pdf', 'size': 182000, 'status': 'partial',
     'warnings': ['No extractable text on pages 4. Scans require visual reading; OCR is not available.'],
     'created_at': '2026-09-20T10:00:00Z', 'expires_at': '2099-10-29T10:00:00Z'},
    _version('3', 1, TURN_ONE, 'docx'), _version('4', 1, TURN_ONE, 'pdf'), _version('5', 2, TURN_TWO, 'docx'), _version('6', 2, TURN_TWO, 'pdf'),
    {'id': '8' * 32, 'name': 'invoice-attachment.pdf', 'mime': 'application/pdf', 'size': 51000, 'status': 'ready', 'kind': 'mail_attachment', 'turn_id': TURN_TWO,
     'origin': {'message_id': '18c2f0a1b2c3d4e5', 'part_id': '1.2'}, 'origin_subject': 'Offer 2026', 'origin_from': 'Jens <jens@vendor.example>',
     'created_at': '2026-09-23T10:00:00Z', 'expires_at': '2099-10-29T10:00:00Z', 'warnings': []},
]


@pytest.mark.parametrize('width,dark', [(1440, False), (390, True)])
def test_saved_document_versions_follow_the_answer_and_remove_needs_confirmation(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server, has_touch=width < 700)
    files, deleted, errors, gets = list(SAVED), [], [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        page.set_viewport_size({'width': width, 'height': 900})
        _routes(page, files)
        def listing(route):
            gets.append(route.request.method)
            _json(route, {'files': files})
        page.route(f'**/agent/chats/{CHAT}/files', listing)
        def single(route):
            if route.request.method == 'DELETE':
                target = route.request.url.rsplit('/', 1)[1]
                deleted.append(target); files[:] = [f for f in files if f['id'] != target]
                return _json(route, {'status': 'deleted'})
            route.fulfill(body=b'%PDF-1.4\n', content_type='application/pdf')
        page.route(f'**/agent/chats/{CHAT}/files/*', single)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        _choose_mode(page, 'agent')
        expect(page.locator('#agentModelDropdown')).to_be_enabled()
        page.evaluate("""([chat, turn]) => (window.exitHeroMode?.(), App.runRegistry.showSavedView)({type:'bookmark'}, {chatId: chat, turnId: turn,
          executionMode:'agent', question:'Revise the decision brief', consensus:'I revised the decision brief (version 2).',
          currentTurn:{id: turn, status:'completed', execution_mode:'agent', consensus:'I revised the decision brief (version 2).',
          agent_settings:{model_id:'deepseek/deepseek-v4.1-flash', file_ids:['""" + '7' * 32 + """']}}});""", [CHAT, TURN_TWO])
        card = page.locator('#agentAnswerResources .agent-doc-card')
        expect(card).to_have_count(1)
        expect(card).to_contain_text('Decision brief')
        expect(card).to_contain_text('Version 2 · revised from version 1')
        expect(card).not_to_contain_text(DOC)
        expect(page.locator('#agentAnswerResources')).to_contain_text("couldn't be read")
        # The answer starts right away; the card follows it.
        body_box, card_box = page.locator('#agentAnswerBody').bounding_box(), card.bounding_box()
        assert card_box['y'] > body_box['y'] and body_box['y'] < 400
        expect(card.get_by_role('button', name='Download Decision brief-v2.pdf, version 2')).to_be_visible()
        expect(card.locator('.agent-doc-earlier')).not_to_have_attribute('open', '')
        _shot(page, f'workspace-saved-{width}-{"dark" if dark else "light"}')
        expect(page.locator('#agentWorkspace')).to_have_count(0)
        panel = page.locator('#agentAnswerResources')
        # The mail attachment fetched in this turn follows its answer.
        expect(panel).to_contain_text('From email: Offer 2026 (Jens)')
        expect(panel).not_to_contain_text('18c2f0a1b2c3d4e5')
        # Remove sits behind the overflow menu and needs an explicit confirmation.
        more = panel.get_by_role('button', name='More actions for invoice-attachment.pdf')
        more.click()
        page.get_by_role('menuitem', name='Remove…').click()
        expect(page.locator('.agent-files-confirm')).to_contain_text('The agent can no longer use it in this chat.')
        _shot(page, f'workspace-confirm-{width}-{"dark" if dark else "light"}')
        page.get_by_role('button', name='Cancel').click()
        assert not deleted
        more.click()
        page.get_by_role('menuitem', name='Remove…').click()
        page.get_by_role('button', name='Remove file').click()
        expect(panel).not_to_contain_text('invoice-attachment.pdf')
        assert deleted == ['8' * 32]
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        # Re-rendering the saved view does not refetch the list.
        before = len(gets)
        page.evaluate("() => App.agentChat.render()")
        page.wait_for_timeout(400)
        assert len(gets) == before
        assert not errors
    finally:
        context.close()
