"""The quiet lines under an answer's blocks, in the built app: a table is
copied as CSV or Markdown, also where a shape was drawn from it, and a
finished HTML block opens as a page that runs on the viewer's stage. The
app's APIs are mocked; the document the page runs in is the route's own
(app/core/html_page.py written_document), under the app's real page policy.
That such a page reaches nothing is test_agent_page_sandbox.py."""
import pytest
from playwright.sync_api import expect

from app.core import html_page
from test_agent_workspace_frontend import CHAT, TURN_TWO, _routes, _shot
from test_phase4_frontend import phase4_server, _real_firebase_page, _json  # noqa: F401
from test_agent_chat_frontend import _choose_mode

FENCE = '```'
ANSWER = f"""Drei Heizungen im Vergleich.

| Heizung | Kosten pro Jahr |
|---|---:|
| **Wärmepumpe** | 1.380 € |
| Gas | 2.050 € |
| Öl, "alt" | 2.300 € |

Nach der Förderung:

| Nach Förderung | Pro Jahr | Rechnet sich nach |
|---|---|---|
| 17.600 € | 1,38 Tsd. € | 11 Jahren |

Und der Rechner als Seite:

{FENCE}html
<!doctype html>
<html lang="de"><head><meta charset="utf-8"><title>Heizkostenrechner</title>
<script src="https://cdn.example.com/chart.js"></script>
<style>body {{ font: 16px system-ui; margin: 24px }}</style></head>
<body><h1>Heizkosten</h1>
<label>Jahre <input id="years" type="range" min="1" max="20" value="10"></label>
<output id="out"></output>
<script>
  const years = document.getElementById('years'), out = document.getElementById('out');
  const show = () => {{ out.textContent = (years.value * 1380) + ' Euro, origin ' + self.origin; }};
  years.addEventListener('input', show); show();
  try {{ top.document.title = 'taken'; }} catch (error) {{}}
</script></body></html>
{FENCE}

Die Wärmepumpe ist am günstigsten.
"""
# Where the blocks of the answer stand, and the page.
PLACES = """() => {
  const top = selector => Math.round(document.querySelector(selector).getBoundingClientRect().top * 10) / 10;
  return { table: top('#agentAnswerBody .markdown-table-wrap'), figures: top('#agentAnswerBody .md-figures'),
           code: top('#agentAnswerBody pre[data-code]'), last: top('#agentAnswerBody > p:last-of-type'), scroll: scrollY };
}"""


def _open(browser, server, width, *, dark=False):
    context, page = _real_firebase_page(browser, server, has_touch=width < 700)
    context.grant_permissions(['clipboard-read', 'clipboard-write'], origin=server)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    # The mocked session's own 401s and the outside script the page's policy
    # keeps out are no fault of the app's page.
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' and 'status of 401' not in m.text
            and 'cdn.example.com' not in m.text else None)
    page.set_viewport_size({'width': width, 'height': 860})
    _routes(page, [])
    page.route(f'**/agent/chats/{CHAT}/files', lambda r: _json(r, {'files': []}))
    page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
    page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
    _choose_mode(page, 'agent')
    expect(page.locator('#agentModelDropdown')).to_be_enabled()
    page.evaluate("""([chat, turn, answer]) => (window.exitHeroMode?.(), App.runRegistry.showSavedView)({type:'bookmark'}, {chatId: chat, turnId: turn,
      executionMode:'agent', question:'Welche Heizung ist am günstigsten?', consensus: answer,
      currentTurn:{id: turn, status:'completed', execution_mode:'agent', consensus: answer,
      agent_settings:{model_id:'deepseek/deepseek-v4.1-flash', file_ids:[]}}});""", [CHAT, TURN_TWO, ANSWER])
    return context, page, errors


@pytest.mark.parametrize('width,dark', [(1440, False), (1440, True), (390, False)])
def test_a_table_is_copied_and_an_html_block_runs_as_a_page(browser, phase4_server, width, dark):
    context, page, errors = _open(browser, phase4_server, width, dark=dark)
    try:
        body = page.locator('#agentAnswerBody')
        # One line under the table and one under the figures drawn from the
        # second table, each right after its block; their words are drawn,
        # not written into the answer.
        expect(body.locator('.markdown-table-wrap + .md-table-tools')).to_have_count(1)
        expect(body.locator('.md-figures + .md-table-tools')).to_have_count(1)
        expect(body.locator('.md-table-tools')).to_have_count(2)
        words = page.evaluate("""() => [...document.querySelectorAll('#agentAnswerBody .md-block-tool')]
          .map(button => getComputedStyle(button, '::after').content)""")
        assert words == ['"CSV"', '"Markdown"', '"CSV"', '"Markdown"', '"View as page"']
        assert 'CSV' not in body.inner_text() and 'View as page' not in body.inner_text()
        # Always there, not only under a pointer.
        for tool in body.locator('.md-block-tool').all():
            expect(tool).to_be_visible()
            assert tool.evaluate('button => getComputedStyle(button).opacity') == '1'

        # Windows hands text back with its own line ends.
        read = r"async () => (await navigator.clipboard.readText()).replace(/\r\n/g, '\n')"

        def copy(line, kind):
            """The clipboard once the button says it copied."""
            button = body.locator('.md-table-tools').nth(line).locator(f'[data-format="{kind}"]')
            button.click()
            expect(button).to_have_class('md-block-tool table-copy is-copied')
            return page.evaluate(read)

        assert copy(0, 'csv') == 'Heizung,Kosten pro Jahr\nWärmepumpe,1.380 €\nGas,2.050 €\n"Öl, ""alt""",2.300 €'
        # A spreadsheet gets the same cells as a table.
        rich = page.evaluate("""async () => {
          const [item] = await navigator.clipboard.read();
          return item.types.includes('text/html') ? await (await item.getType('text/html')).text() : '';
        }""")
        assert '<th>Heizung</th><th>Kosten pro Jahr</th>' in rich and '<td>Öl, "alt"</td><td>2.300 €</td>' in rich
        assert copy(0, 'markdown') == ('| Heizung | Kosten pro Jahr |\n| --- | ---: |\n| **Wärmepumpe** | 1.380 € |\n'
                                       '| Gas | 2.050 € |\n| Öl, "alt" | 2.300 € |')
        # The figures give the cells of the table they were drawn from.
        assert copy(1, 'csv') == 'Nach Förderung,Pro Jahr,Rechnet sich nach\n17.600 €,"1,38 Tsd. €",11 Jahren'

        # The page: on the stage, over the chat, which stays where it is.
        opener = body.locator('pre[data-code] + .md-code-tools .code-page')
        expect(opener).to_have_attribute('aria-label', 'View as page')
        opener.scroll_into_view_if_needed()
        before = page.evaluate(PLACES)
        opener.click()
        dialog = page.locator('#attachmentViewerModal')
        expect(dialog).to_have_class('modal attachment-viewer-dialog is-stage')
        expect(page.locator('#attachmentViewerTitle')).to_have_text('Heizkostenrechner')
        frame = dialog.locator('iframe.attachment-viewer-frame')
        expect(frame).to_have_attribute('sandbox', 'allow-scripts')
        expect(frame).to_have_attribute('src', html_page.WRITTEN_PATH)
        inner = page.frame_locator('#attachmentViewerModal iframe.attachment-viewer-frame').frame_locator('iframe')
        # Its own script ran, in no origin, and did not reach the app's page.
        expect(inner.locator('#out')).to_have_text('13800 Euro, origin null')
        assert page.title() != 'taken'
        inner.locator('#years').focus()
        page.keyboard.press('ArrowRight')
        expect(inner.locator('#out')).to_have_text('15180 Euro, origin null')
        expect(dialog.locator('.attachment-viewer-note')).to_have_text(
            'This page runs without the network. One file it asks for at another address was not loaded.')
        expect(dialog.locator('.attachment-viewer-actions button')).to_have_text(['Download'])
        assert page.evaluate(PLACES) == before
        # A white sheet in both themes, once the stage has come in.
        page.wait_for_function("() => getComputedStyle(document.getElementById('attachmentViewerModal')).opacity === '1'")
        assert frame.evaluate('frame => getComputedStyle(frame).backgroundColor') == 'rgb(255, 255, 255)'
        _shot(page, f'answer-page-{width}-{"dark" if dark else "light"}')
        page.locator('#attachmentViewerClose').click()
        expect(dialog).to_be_hidden()
        assert page.evaluate(PLACES) == before
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        # The tick of a copy was for a moment.
        expect(body.locator('.md-table-tools.is-copied, .table-copy.is-copied')).to_have_count(0)
        _shot(page, f'answer-tools-{width}-{"dark" if dark else "light"}')
        assert not errors, errors
    finally:
        context.close()
