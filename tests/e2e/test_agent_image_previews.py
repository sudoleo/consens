"""Every image of a sent Agent message shows its own preview tile.

All APIs mocked, no external writes. Pasted screenshots all arrive as
"image.png", so names alone never identify a picture.
"""
import base64
import json
import struct
import zlib

from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json  # noqa: F401 (fixture)
from test_agent_chat_frontend import CATALOG, _choose_mode

CHAT = 'a' * 32
IDS = ['c' * 32, 'd' * 32]


def _png(rgb, size=4):
    """A tiny valid PNG of one colour (stays below the shrink threshold)."""
    raw = b''.join(b'\x00' + bytes(rgb) * size for _ in range(size))
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


IMAGES = [_png((200, 30, 30)), _png((30, 160, 40), 5)]


def _thumbs(page, selector):
    return page.evaluate("""sel => [...document.querySelectorAll(sel + ' .attachment-chip')].map(chip => {
        const img = chip.querySelector('img.attachment-chip-thumb');
        return img && img.complete && img.naturalWidth > 0 ? 'tile' : chip.querySelector('.attachment-chip-icon') ? 'icon' : 'loading';
    })""", selector)


def test_each_image_of_a_message_gets_its_own_preview_also_after_reopening(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    stored, errors, file_gets = [], [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        page.route('**/user_status', lambda r: _json(r, {'tier': 'pro', 'is_pro': True, 'agent_access': True}))
        page.route('**/agent/models', lambda r: _json(r, CATALOG))
        page.route('**/agent/budget', lambda r: _json(r, {'token_budget': {'limit': 250000, 'remaining': 249000}}))
        page.route('**/chats', lambda r: _json(r, {'chat': {'id': CHAT}}))
        page.route(f'**/agent/chats/{CHAT}/actions', lambda r: _json(r, {'actions': [], 'evidence': []}))

        def files(route):
            if route.request.method == 'POST':
                body = route.request.post_data_json
                index = len(stored)
                raw = base64.b64decode(body['data'])
                stored.append({'id': IDS[index], 'name': body['name'], 'mime': 'image/png', 'size': len(raw),
                               'status': 'ready', 'warnings': [], 'created_at': '2026-10-08T10:00:00Z',
                               'expires_at': '2099-10-29T10:00:00Z'})
                _json(route, {'file': stored[-1]})
            else:
                _json(route, {'files': stored})
        page.route(f'**/agent/chats/{CHAT}/files', files)

        def file_bytes(route):
            file_id = route.request.url.rsplit('/', 1)[-1]
            file_gets.append(file_id)
            route.fulfill(body=IMAGES[IDS.index(file_id)], content_type='image/png')
        for file_id in IDS:
            page.route(f'**/agent/chats/{CHAT}/files/{file_id}', file_bytes)

        turns, bookmarks = [], []

        def answer(route):
            payload = route.request.post_data_json
            turn = {'id': 'b' * 32, 'question': payload['question'], 'consensus': 'Two pictures.',
                    'execution_mode': 'agent', 'status': 'completed', 'attachments': list(stored),
                    'agent_settings': {'file_ids': [f['id'] for f in stored]}}
            turns.append(turn)
            bookmark = {'id': payload['bookmark_id'], 'chat_id': CHAT, 'turn_id': turn['id'], 'execution_mode': 'agent',
                        'mode': 'Agent', 'query': payload['question'], 'title': payload['question'], 'has_consensus': True,
                        'responses': {'consensus': turn['consensus']}}
            bookmarks.append(bookmark)
            result = {'chat_id': CHAT, 'turn_id': turn['id'], 'turn': turn, 'response': turn['consensus'], 'bookmark_meta': bookmark}
            route.fulfill(content_type='text/event-stream', body='event: final\ndata: ' + json.dumps(result) + '\n\n')
        page.route('**/agent', answer)
        page.route('**/bookmarks?*', lambda r: _json(r, {'bookmarks': bookmarks, 'next_cursor': None}))
        page.route('**/bookmarks/*/conversation*', lambda r: _json(r, {'chat_id': CHAT, 'turns': turns, 'has_more': False}))
        page.route('**/bookmarks/*', lambda r: _json(r, {'bookmark': bookmarks[0]}))

        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, 'agent')
        page.locator('#attachFileInput').set_input_files([
            {'name': 'image.png', 'mimeType': 'image/png', 'buffer': image} for image in IMAGES])
        expect(page.locator('#attachmentBar .attachment-chip')).to_have_count(2)
        page.locator('#questionInput').fill('What do these two screenshots show?')
        page.locator('#sendButton').click()
        expect(page.locator('#agentAnswerBody')).to_contain_text('Two pictures.')
        page.wait_for_function("() => document.querySelectorAll('#threadAskAttachments img.attachment-chip-thumb').length === 2"
                               " && [...document.querySelectorAll('#threadAskAttachments img.attachment-chip-thumb')].every(i => i.complete && i.naturalWidth > 0)")
        assert _thumbs(page, '#threadAskAttachments') == ['tile', 'tile']
        sources = page.evaluate("() => [...document.querySelectorAll('#threadAskAttachments img.attachment-chip-thumb')].map(i => i.src)")
        assert len(set(sources)) == 2, 'every tile shows its own picture'

        # Reopen the saved chat: the tiles come from the stored files now.
        page.reload(wait_until='domcontentloaded')
        page.wait_for_function('() => typeof window.openBookmark === "function" && window.__consensioAuthState?.uid')
        page.evaluate('id => window.openBookmark(id)', bookmarks[0]['id'])
        expect(page.locator('#agentAnswerBody')).to_contain_text('Two pictures.')
        page.wait_for_function("() => [...document.querySelectorAll('#threadAskAttachments .attachment-chip')].length === 2"
                               " && [...document.querySelectorAll('#threadAskAttachments .attachment-chip')].every(c => !c.classList.contains('is-thumb-loading'))",
                               timeout=15000)
        assert _thumbs(page, '#threadAskAttachments') == ['tile', 'tile'], file_gets
        assert sorted(set(file_gets)) == sorted(IDS)
        reopened = page.evaluate("() => [...document.querySelectorAll('#threadAskAttachments img.attachment-chip-thumb')].map(i => i.src)")
        # data: URLs (the CSP allows no blob: images), one picture per tile.
        assert len(set(reopened)) == 2 and all(src.startswith('data:image/png;base64,') for src in reopened)
        assert not errors
    finally:
        context.close()
