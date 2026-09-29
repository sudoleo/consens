"""Built Agent workspace on desktop and mobile; all APIs mocked, no external writes."""
import json
import pytest
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json
from test_agent_chat_frontend import CATALOG, _choose_mode


@pytest.mark.parametrize('width', [1280, 390, 320])
def test_upload_restoration_and_private_download(browser, phase4_server, width):
    context, page = _real_firebase_page(browser, phase4_server, has_touch=width < 700)
    files, calls, errors = [], [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    chat_id, file_id = 'a'*32, 'f'*32
    try:
        page.set_viewport_size({'width':width,'height':900})
        page.route('**/user_status', lambda r: _json(r, {'tier':'pro','is_pro':True,'agent_access':True}))
        page.route('**/usage', lambda r: _json(r, {'is_pro':True,'remaining':100,'total_limit':100,'deep_remaining':10,'deep_total_limit':10}))
        page.route('**/agent/models', lambda r: _json(r, CATALOG))
        page.route('**/agent/budget', lambda r: _json(r, {'token_budget':{'limit':250000,'remaining':249000}}))
        page.route('**/chats', lambda r: _json(r, {'chat':{'id':chat_id}}))
        def resource(route):
            if route.request.method == 'POST':
                assert route.request.post_data_json['name'] == 'offer.txt'
                files.append({'id':file_id,'name':'offer.txt','mime':'text/plain','status':'ready','warnings':[], 'size':24})
                _json(route, {'file':files[0]})
            else: _json(route, {'files':files})
        page.route(f'**/agent/chats/{chat_id}/files', resource)
        page.route(f'**/agent/chats/{chat_id}/files/{file_id}', lambda r: r.fulfill(body='Price 42 EUR',headers={'Content-Disposition':'attachment; filename="offer.txt"'},content_type='text/plain'))
        def answer(route):
            payload=route.request.post_data_json; calls.append(payload)
            turn={'id':'b'*32,'question':payload['question'],'consensus':'Offer costs 42 EUR (offer.txt, lines 1-1).','execution_mode':'agent','status':'completed','attachments':files,'agent_settings':{'file_ids':[file_id]}}
            result={'chat_id':chat_id,'turn_id':turn['id'],'turn':turn,'response':turn['consensus'],'bookmark_meta':{'id':payload['bookmark_id'],'chat_id':chat_id,'execution_mode':'agent','query':payload['question'],'has_consensus':True}}
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
        expect(page.locator('#agentWorkspace summary')).to_contain_text('Files in this chat (1)')
        page.locator('#agentWorkspace summary').click()
        expect(page.locator('#agentWorkspace')).to_contain_text('offer.txt')
        with page.expect_download() as pending:
            page.get_by_role('button',name='Download',exact=True).click()
        assert pending.value.suggested_filename == 'offer.txt'
        assert calls[0]['file_ids'] == [file_id] and 'attachments' not in calls[0]
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert not errors
    finally: context.close()
