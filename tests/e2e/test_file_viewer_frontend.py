"""The preview beside the chat (file-viewer.js, 2026-11-01): a deck the agent
shared, a created document, code and an uploaded PDF open in it; desktop
docks it beside the chat, a phone shows it over everything. All APIs mocked,
real PDFs drawn by pdf.js."""
import io

import pytest
from playwright.sync_api import expect
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from test_agent_workspace_frontend import CHAT, TURN_TWO, DOC, _routes, _shot
from test_phase4_frontend import phase4_server, _real_firebase_page, _json  # noqa: F401
from test_agent_chat_frontend import _choose_mode

DECK, BRIEF_DOCX, BRIEF_PDF, SCRIPT, UPLOAD = 'e' * 32, '5' * 32, '6' * 32, 'f' * 32, '7' * 32


def _pdf(pages, size):
    out = io.BytesIO()
    page = canvas.Canvas(out, pagesize=size)
    for number in range(1, pages + 1):
        width, height = size
        page.setFillColorRGB(.1, .1, .12)
        page.rect(0, 0, width, height * .18, fill=1, stroke=0)
        page.setFont('Helvetica-Bold', 40)
        page.drawString(48, height - 96, f'Der Weg zur AGI {number}')
        page.showPage()
    page.save()
    return out.getvalue()


DECK_PDF = _pdf(3, landscape(A4))
BRIEF = _pdf(2, A4)
STAMP = {'status': 'ready', 'created_at': '2026-11-01T10:00:00Z', 'expires_at': '2099-10-29T10:00:00Z', 'warnings': []}
FILES = [
    {'id': DECK, 'name': 'Der_Weg_zur_AGI.pptx', 'kind': 'vm_file', 'turn_id': TURN_TWO, 'size': 48213,
     'mime': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
     'preview': {'mime': 'application/pdf', 'size': len(DECK_PDF)}, 'origin': {'source': 'vm', 'path': '/x.pptx'}, **STAMP},
    {'id': BRIEF_DOCX, 'name': 'Decision brief-v1.docx', 'title': 'Decision brief', 'kind': 'document', 'document_id': DOC,
     'version': 1, 'parent_version': 0, 'turn_id': TURN_TWO, 'size': 41000,
     'mime': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', **STAMP},
    {'id': BRIEF_PDF, 'name': 'Decision brief-v1.pdf', 'title': 'Decision brief', 'kind': 'document', 'document_id': DOC,
     'version': 1, 'parent_version': 0, 'turn_id': TURN_TWO, 'size': len(BRIEF), 'mime': 'application/pdf', **STAMP},
    {'id': SCRIPT, 'name': 'analysis.py', 'kind': 'vm_file', 'turn_id': TURN_TWO, 'size': 64, 'mime': 'text/x-python',
     'origin': {'source': 'vm', 'path': '/analysis.py'}, **STAMP},
]
BODIES = {DECK: (DECK_PDF, 'application/pdf'), BRIEF_PDF: (BRIEF, 'application/pdf'),
          BRIEF_DOCX: (b'PK docx', 'application/octet-stream'),
          SCRIPT: (b'import math\n\n\ndef area(r):\n    return math.pi * r ** 2\n', 'text/x-python'),
          UPLOAD: (BRIEF, 'application/pdf')}


def _open_answer(browser, server, width, *, dark=False):
    context, page = _real_firebase_page(browser, server, has_touch=width < 700)
    errors, requests = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    # The mocked session's own 401s are no fault of the preview.
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' and 'status of 401' not in m.text else None)
    page.set_viewport_size({'width': width, 'height': 860})
    _routes(page, FILES)
    page.route(f'**/agent/chats/{CHAT}/files', lambda r: _json(r, {'files': FILES}))

    def single(route):
        url = route.request.url
        file_id = url.split('?')[0].rsplit('/', 1)[1]
        requests.append(url.rsplit('/', 1)[1])
        body, mime = BODIES[file_id]
        route.fulfill(body=body, content_type=mime)
    page.route(f'**/agent/chats/{CHAT}/files/*', single)
    page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
    page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
    _choose_mode(page, 'agent')
    expect(page.locator('#agentModelDropdown')).to_be_enabled()
    page.evaluate("""([chat, turn, upload]) => (window.exitHeroMode?.(), App.runRegistry.showSavedView)({type:'bookmark'}, {chatId: chat, turnId: turn,
      executionMode:'agent', question:'Mach mir eine kurze Präsentation über den Weg zur AGI', consensus:'Hier ist die Präsentation.',
      currentTurn:{id: turn, status:'completed', execution_mode:'agent', consensus:'Hier ist die Präsentation.',
      agent_settings:{model_id:'deepseek/deepseek-v4.1-flash', file_ids:[]}}});""", [CHAT, TURN_TWO, UPLOAD])
    return context, page, errors, requests


@pytest.mark.parametrize('width,dark', [(1440, False), (1440, True)])
def test_a_shared_deck_shows_its_first_slide_and_opens_beside_the_chat(browser, phase4_server, width, dark):
    context, page, errors, requests = _open_answer(browser, phase4_server, width, dark=dark)
    try:
        panel = page.locator('#agentAnswerBody ~ .agent-answer-documents')
        deck = panel.locator('.agent-file-row.can-preview', has_text='Der_Weg_zur_AGI.pptx')
        # The card says what it is and that it opens: its first slide, its
        # type and slides, the word Preview.
        expect(deck.locator('.agent-file-thumb canvas')).to_have_count(1)
        expect(deck.locator('.agent-file-kind')).to_have_text('PowerPoint · 3 slides')
        expect(deck.locator('.agent-file-preview-hint')).to_have_text('Preview')
        doc = panel.locator('.agent-doc-card')
        expect(doc.locator('.agent-doc-meta')).to_have_text('Document · 2 pages')
        _shot(page, f'file-viewer-cards-{"dark" if dark else "light"}')
        chat_before = page.locator('.container').first.bounding_box()['width']
        deck.locator('.agent-file-open').click()
        viewer = page.locator('#fileViewer')
        expect(viewer).to_be_visible()
        assert page.evaluate("document.body.classList.contains('file-viewer-docked')")
        # Measured once the preview has slid in and the chat has narrowed:
        # both move, and a busy machine measured them halfway (2026-11-01).
        for moving in (viewer, page.locator('.container').first):
            moving.evaluate("el => Promise.all(el.getAnimations().map(a => a.finished.catch(() => {})))")
        expect(viewer.locator('.file-viewer-name')).to_have_text('Der_Weg_zur_AGI.pptx')
        expect(viewer.locator('.file-viewer-rail-count')).to_have_text('3 slides')
        expect(viewer.locator('.file-viewer-thumb')).to_have_count(3)
        expect(viewer.locator('.file-viewer-page.is-drawn').first).to_be_visible()
        expect(viewer.locator('.file-viewer-thumb[aria-current="true"]')).to_have_attribute('data-page', '1')
        # Beside the chat, which narrows and stays readable.
        # At the right edge (the body is its frame: its scrollbar stays outside).
        box, edge = viewer.bounding_box(), page.evaluate('document.body.clientWidth')
        assert box['x'] > 400 and abs(box['x'] + box['width'] - edge) <= 1, (box, edge)
        chat_after = page.locator('.container').first.bounding_box()
        assert chat_after['x'] + chat_after['width'] <= box['x'] + 1 and chat_after['width'] < chat_before
        # A slide fits whole; the PDF is the preview, never the .pptx itself.
        page_box = viewer.locator('.file-viewer-page').first.bounding_box()
        stage = viewer.locator('.file-viewer-stage').bounding_box()
        assert page_box['height'] <= stage['height'] and page_box['width'] <= stage['width']
        assert f'{DECK}?preview=1' in requests and DECK not in requests
        _shot(page, f'file-viewer-deck-{"dark" if dark else "light"}')
        viewer.locator('.file-viewer-thumb[data-page="3"]').click()
        expect(viewer.locator('.file-viewer-thumb[aria-current="true"]')).to_have_attribute('data-page', '3')
        expect(viewer.locator('.file-viewer-count')).to_have_text('3 / 3')
        # Zoom: 100 % is the printed size.
        viewer.locator('.file-viewer-zoom').click()
        page.get_by_role('menuitemradio', name='100%').click()
        expect(viewer.locator('.file-viewer-zoom-label')).to_have_text('100%')
        width_100 = viewer.locator('.file-viewer-page').first.evaluate('el => el.getBoundingClientRect().width')
        assert abs(width_100 - landscape(A4)[0] * 96 / 72) < 2
        # Present: one slide on the whole screen, the arrows go on, Escape ends.
        viewer.get_by_role('button', name='Present').click()
        show = page.locator('.file-viewer-present')
        expect(show).to_be_visible()
        expect(show.locator('.file-viewer-present-count')).to_have_text('3 / 3')
        page.keyboard.press('ArrowLeft')
        expect(show.locator('.file-viewer-present-count')).to_have_text('2 / 3')
        page.keyboard.press('Escape')
        expect(show).to_have_count(0)
        expect(viewer).to_be_visible()
        # Full screen takes the window; closing gives the chat its lane back.
        viewer.get_by_role('button', name='Full screen').click()
        assert abs(viewer.bounding_box()['x']) <= 1
        viewer.get_by_role('button', name='Exit full screen').click()
        viewer.get_by_role('button', name='Close preview').click()
        expect(viewer).to_be_hidden()
        assert not page.evaluate("document.body.classList.contains('file-viewer-docked')")
        expect(deck.locator('.agent-file-open')).to_be_focused()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert not errors, errors
    finally:
        context.close()


def test_a_document_offers_both_formats_and_code_shows_its_lines(browser, phase4_server):
    context, page, errors, requests = _open_answer(browser, phase4_server, 1280)
    try:
        panel = page.locator('#agentAnswerBody ~ .agent-answer-documents')
        panel.locator('button.agent-doc-main').click()
        viewer = page.locator('#fileViewer')
        expect(viewer.locator('.file-viewer-name')).to_have_text('Decision brief')
        expect(viewer.locator('.file-viewer-rail-count')).to_have_text('2 pages')
        expect(viewer.get_by_role('button', name='Present')).to_be_hidden()
        viewer.get_by_role('button', name='Download').click()
        expect(page.get_by_role('menuitem')).to_have_text(['Download DOCX', 'Download PDF'])
        page.keyboard.press('Escape')
        # A shared script: its lines, numbered; another file replaces the preview.
        script = panel.locator('.agent-file-row.can-preview', has_text='analysis.py')
        expect(script.locator('.agent-file-kind')).to_have_text('Python')
        script.locator('.agent-file-open').click()
        expect(viewer.locator('.file-viewer-name')).to_have_text('analysis.py')
        expect(viewer.locator('.file-viewer-source')).to_contain_text('return math.pi * r ** 2')
        expect(viewer.locator('.file-viewer-gutter')).to_have_text('1\n2\n3\n4\n5')
        expect(viewer.locator('.file-viewer-count')).to_have_text('5 lines')
        expect(viewer.locator('nav.file-viewer-rail')).to_be_hidden()
        _shot(page, 'file-viewer-code')
        page.keyboard.press('Escape')
        expect(viewer).to_be_hidden()
        assert not errors, errors
    finally:
        context.close()


def test_on_a_phone_the_preview_covers_the_screen(browser, phase4_server):
    context, page, errors, requests = _open_answer(browser, phase4_server, 390, dark=True)
    try:
        deck = page.locator('#agentAnswerBody ~ .agent-answer-documents .agent-file-row.can-preview', has_text='Der_Weg_zur_AGI.pptx')
        expect(deck.locator('.agent-file-thumb canvas')).to_have_count(1)
        _shot(page, 'file-viewer-phone-card-dark')
        deck.locator('.agent-file-open').click()
        viewer = page.locator('#fileViewer')
        expect(viewer.locator('.file-viewer-page.is-drawn').first).to_be_visible()
        box = viewer.bounding_box()
        assert box['x'] == 0 and abs(box['width'] - page.evaluate('document.body.clientWidth')) <= 1, box
        assert page.evaluate("document.body.classList.contains('file-viewer-covers')")
        # No room for thumbnails: the pages alone, as wide as the screen allows.
        expect(viewer.locator('nav.file-viewer-rail')).to_be_hidden()
        expect(viewer.locator('.file-viewer-count')).to_be_hidden()
        assert viewer.locator('.file-viewer-page').first.bounding_box()['width'] > 300
        expect(page.locator('#attachmentViewerModal')).not_to_have_attribute('open', '')
        _shot(page, 'file-viewer-phone-dark')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        viewer.get_by_role('button', name='Close preview').click()
        expect(viewer).to_be_hidden()
        assert not errors, errors
    finally:
        context.close()
