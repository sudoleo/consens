"""Shapes an answer draws from plain Markdown (answer-shapes.js), in a real
browser with the app's CSS, while the answer streams in.

Unit tests hold the rules; only a browser shows whether a shape jumps while
the text arrives chunk by chunk, or stands where it first appeared. The page
uses the app's own renderer (markdown-stream.js renderMarkdownStream, then
morphMarkdown for the fixed text, as agent-chat.js does) and the app's
stylesheet, under the app's script policy.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'"
SCRIPTS = ('/static/vendor/marked/12.0.2/marked.min.js', '/static/vendor/dompurify/3.4.17/dist/purify.min.js',
           '/static/js/answer-shapes.js', '/static/js/markdown-stream.js')
# The app's translator, which markdown-stream.js asks for a table's label.
INIT = 'window.App = { t: (text, values = {}) => text.replace(/\\{(\\w+)\\}/g, (_, key) => values[key] ?? "") };'

ANSWER = """Für ein Einfamilienhaus von 1995 ist die **Luft-Wärmepumpe** meist die beste Wahl.

| Anschaffung nach Förderung | Betrieb pro Jahr | Rechnet sich nach |
|---|---|---|
| 17.600 € | 1.380 € | 11 Jahren |

### Was dafür und was dagegen spricht

| Dafür | Dagegen |
|---|---|
| Betriebskosten rund ein Drittel unter Gas | Auch nach Förderung teurer als eine Gasheizung |
| Förderung deckt fast die Hälfte der Anschaffung | Außengerät braucht Platz und ist hörbar |
| Kein Risiko durch einen steigenden CO₂-Preis | |

### Betrieb pro Jahr

| Heizung | Kosten |
|---|---|
| Erd-Wärmepumpe | 1.090 € |
| **Luft-Wärmepumpe** | 1.380 € |
| Pelletheizung | 1.620 € |
| Gas-Brennwert | 2.150 € |

### So geht ihr vor

1. **Heizlast berechnen lassen.** Ein Energieberater prüft, ob 55 °C Vorlauf reichen.
2. **Drei Angebote einholen:** Die Preise streuen stark, auch regional.
3. **Förderung beantragen.** Der Antrag muss vor dem Auftrag gestellt sein.

### Was sich geändert hat

| Jahr | Was passiert ist |
|---|---|
| 2020 | Die Austauschprämie für Ölheizungen startet. |
| 2023 | Das Heizungsgesetz wird beschlossen. |
| 2024 | Die neue Förderung mit bis zu 70 % gilt. |

Am Ende entscheidet die Heizlast, nicht der Prospekt.
"""

# Streams the answer in chunks of five characters. Every block, heading,
# list and shape that stands on the page is followed from then on: it must
# keep its node and its place to the last chunk and through the full render
# of the fixed text. A numbered list must never stand without its rail.
STREAM = """async (text) => {
  const el = document.getElementById("answer");
  const followed = new Map(), problems = [];
  let bareLists = 0;
  const watch = () => el.querySelectorAll(".md-figures, .md-facing, .markdown-table-wrap, ol, h3, p");
  const check = when => {
    for (const [node, top] of followed) {
      if (!node.isConnected) { problems.push(`${when}: replaced ${node.className || node.tagName}`); followed.delete(node); continue; }
      const now = node.getBoundingClientRect().top;
      if (Math.abs(now - top) > 0.5) problems.push(`${when}: ${node.className || node.tagName} moved ${top} -> ${now}`);
      followed.set(node, now);
    }
  };
  for (let end = 1; end <= text.length; end += 5) {
    window.renderMarkdownStream(el, text.slice(0, end));
    await new Promise(requestAnimationFrame);
    check(`chunk ${end}`);
    for (const node of watch()) if (!followed.has(node)) followed.set(node, node.getBoundingClientRect().top);
    bareLists += el.querySelectorAll("ol:not(.md-steps)").length;
  }
  window.renderMarkdownStream(el, text);
  window.morphMarkdown(el, text);
  await new Promise(requestAnimationFrame);
  check("full render");
  return { problems, bareLists, shapes: window.AnswerShapes.present(el) };
}"""


def _page(browser, body, viewport):
    context = browser.new_context(viewport=viewport)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script(INIT)

    def serve(route):
        path = route.request.url.split('answer.test', 1)[1].split('?', 1)[0]
        if path == '/':
            route.fulfill(content_type='text/html', headers={'Content-Security-Policy': CSP}, body=(
                '<!doctype html><html lang="de"><head><meta charset="utf-8">'
                '<link rel="stylesheet" href="/static/style.css">'
                + ''.join(f'<script src="{src}"></script>' for src in SCRIPTS)
                + f'</head><body style="margin:0;height:auto;overflow:visible"><main style="max-width:720px;padding:24px">{body}</main></body></html>'))
            return
        file = ROOT / path.lstrip('/')
        if path.startswith('/static/') and file.is_file():
            kind = {'.css': 'text/css', '.js': 'text/javascript', '.woff2': 'font/woff2'}.get(file.suffix, 'application/octet-stream')
            route.fulfill(body=file.read_bytes(), content_type=kind)
            return
        route.abort()

    context.route('**/*', serve)
    page.goto('https://answer.test/')
    return context, page, errors


@pytest.mark.parametrize('viewport', [{'width': 1280, 'height': 900}, {'width': 390, 'height': 844}])
def test_shapes_stand_where_they_appear_while_the_answer_streams(browser, viewport):
    context, page, errors = _page(browser, '<div id="answer" class="consensus-answer-body markdown-content"></div>', viewport)
    try:
        result = page.evaluate(STREAM, ANSWER)
        assert result['problems'] == []
        # The steps stood on their rail from their first words, never as a plain list first.
        assert result['bareLists'] == 0
        assert result['shapes'] == ['figures', 'facing', 'timeline', 'bars', 'pick', 'steps']
        answer = page.locator('#answer')
        # Every word stays readable and copyable: the shapes rearrange, they drop nothing.
        text = answer.inner_text()
        for words in ('17.600 €', 'Anschaffung nach Förderung', 'Dafür', 'Gasheizung', 'Luft-Wärmepumpe', '1.380 €',
                      'Heizlast berechnen lassen', '2023', 'Das Heizungsgesetz wird beschlossen.'):
            assert words in text
        # The title's closing point is gone, the sentence after it stays.
        assert 'Heizlast berechnen lassen.' not in text
        assert not errors
    finally:
        context.close()


def test_two_sides_stand_beside_each_other_and_one_under_the_other_on_a_phone(browser):
    context, page, errors = _page(browser, '<div id="answer" class="consensus-answer-body markdown-content"></div>',
                                  {'width': 1280, 'height': 900})
    try:
        page.evaluate('text => window.injectMarkdown(document.getElementById("answer"), text, [])', ANSWER)
        sides = page.locator('.md-facing-side')
        first, second = sides.nth(0).bounding_box(), sides.nth(1).bounding_box()
        assert abs(first['y'] - second['y']) < 1 and second['x'] > first['x'] + first['width'] - 1
        # The pick's bar takes the house green, the others stay grey.
        colors = page.evaluate('''() => [...document.querySelectorAll("table.md-bar-rows tr")].slice(1)
            .map(row => getComputedStyle(row.querySelector(".md-bar > i")).backgroundColor)''')
        assert len(set(colors)) == 2 and colors.count(colors[1]) == 1
        page.set_viewport_size({'width': 390, 'height': 844})
        first, second = sides.nth(0).bounding_box(), sides.nth(1).bounding_box()
        assert second['y'] >= first['y'] + first['height'] and abs(first['x'] - second['x']) < 1
        # Nothing wider than the phone but the table that scrolls in its own place.
        assert page.evaluate('document.documentElement.scrollWidth') <= 390
        assert not errors
    finally:
        context.close()


def test_a_public_page_draws_its_server_rendered_answer_with_the_same_file(browser):
    """partials/answer_blocks.html: the script names the answers it draws."""
    context = browser.new_context()
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    html = ('<div class="share-md"><table><thead><tr><th>Dafür</th><th>Dagegen</th></tr></thead><tbody>'
            '<tr><td>Betriebskosten rund ein Drittel unter Gas</td><td>Teurer in der Anschaffung als Gas</td></tr>'
            '<tr><td>Förderung deckt fast die Hälfte</td><td></td></tr></tbody></table></div>')

    def serve(route):
        path = route.request.url.split('share.test', 1)[1]
        if path == '/s/example':
            route.fulfill(content_type='text/html', headers={'Content-Security-Policy': CSP}, body=(
                '<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/static/css/public-pages.css">'
                '<script defer src="/static/js/answer-shapes.js" data-draw-answers=".share-md"></script>'
                f'</head><body>{html}</body></html>'))
            return
        file = ROOT / path.lstrip('/')
        if file.is_file():
            route.fulfill(body=file.read_bytes(), content_type='text/css' if file.suffix == '.css' else 'text/javascript')
            return
        route.abort()

    context.route('**/*', serve)
    try:
        page.goto('https://share.test/s/example')
        page.wait_for_selector('.share-md .md-facing')
        assert page.locator('.md-facing li').count() == 3
        assert page.locator('.share-md table').count() == 0
        assert not errors
    finally:
        context.close()
