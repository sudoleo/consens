import { describe, it, expect, vi } from 'vitest';
import { loadScripts } from './helpers/appWindow.mjs';

// The app's sanitizer and Markdown renderer, as on the page (markdown-stream.js).
const MARKDOWN = ['static/vendor/marked/12.0.2/marked.min.js', 'static/vendor/dompurify/3.4.17/dist/purify.min.js',
  'static/js/markdown-stream.js'];
function boot({ before } = {}) {
  return loadScripts([...MARKDOWN, 'static/js/file-viewer.js'], { body: '<main><button id="card">card</button></main>', before(window) {
    // App.t as in English (app-text.js): the values go into the sentence.
    window.App = { t: (text, params) => String(text).replace(/\{(\w+)\}/g, (all, name) => (params && name in params ? String(params[name]) : all)),
      showPopup: vi.fn() };
    // jsdom has no TextDecoder; every browser does.
    window.TextDecoder = TextDecoder;
    before?.(window);
  } });
}
const text = (body, mime = 'text/plain') => async () => ({ blob: new Blob([body], { type: mime }), mime });
const settle = () => new Promise(resolve => setTimeout(resolve, 0));

describe('file preview (file-viewer.js)', () => {
  it('knows how each file shows and what it is called', () => {
    const { window, dom } = boot();
    const viewer = window.App.fileViewer;
    expect(viewer.describe({ name: 'Der_Weg_zur_AGI.pptx' })).toEqual({ view: 'pdf', family: 'presentation', label: 'PowerPoint' });
    expect(viewer.describe({ name: 'plan.xlsx' })).toMatchObject({ view: 'pdf', family: 'spreadsheet', label: 'Excel' });
    expect(viewer.describe({ name: 'scan', mime: 'application/pdf' })).toMatchObject({ view: 'pdf', label: 'PDF' });
    expect(viewer.describe({ name: 'analysis.py', mime: 'application/octet-stream' })).toMatchObject({ view: 'code', label: 'Python' });
    expect(viewer.describe({ name: 'Dockerfile' })).toMatchObject({ view: 'code', label: 'Dockerfile' });
    expect(viewer.describe({ name: 'notes.md' })).toMatchObject({ view: 'markdown' });
    expect(viewer.describe({ name: 'data.csv' })).toMatchObject({ view: 'table', label: 'CSV' });
    expect(viewer.describe({ name: 'chart.png', mime: 'image/png' }).view).toBe('image');
    // An Office file only with the PDF made of it; a Word file the user sent as its text.
    expect(viewer.previews({ name: 'deck.pptx', kind: 'vm_file' })).toBe(false);
    expect(viewer.previews({ name: 'deck.pptx', kind: 'vm_file', preview: { mime: 'application/pdf' } })).toBe(true);
    expect(viewer.previews({ name: 'offer.docx' })).toBe(true);
    expect(viewer.previews({ name: 'brief.docx', kind: 'vm_file' })).toBe(false);
    expect(viewer.previews({ name: 'archive.zip' })).toBe(false);
    expect(viewer.previews({ name: 'chart.png', mime: 'image/png' })).toBe(false);
    expect(viewer.countText('presentation', 1)).toBe('1 slide');
    expect(viewer.countText('page', 12)).toBe('12 pages');
    dom.window.close();
  });

  it('shows code with its line numbers and gives the focus back when it closes', async () => {
    const { window, document, dom } = boot();
    const card = document.getElementById('card');
    card.focus();
    const run = vi.fn();
    window.App.fileViewer.open({ key: 'a', name: 'analysis.py', mime: 'text/x-python',
      load: text('import math\n\ndef area(r):\n    return math.pi * r ** 2\n'), downloads: [{ label: 'PY', run }] });
    await settle(); await settle();
    const panel = document.getElementById('fileViewer');
    expect(panel.hidden).toBe(false);
    expect(panel.getAttribute('aria-label')).toBe('Preview of analysis.py');
    expect(panel.querySelector('.file-viewer-gutter').textContent).toBe('1\n2\n3\n4');
    expect(panel.querySelector('.file-viewer-source').textContent).toContain('return math.pi');
    expect(panel.querySelector('.file-viewer-source').closest('[data-i18n-skip]')).not.toBeNull();
    expect(panel.querySelector('.file-viewer-count').textContent).toBe('4 lines');
    // No pages: no rail, no zoom, nothing to present.
    expect(panel.querySelector('.file-viewer-rail').hidden).toBe(true);
    expect(panel.querySelector('.file-viewer-zoom').parentElement.hidden).toBe(true);
    expect(panel.querySelector('.file-viewer-tool-play').hidden).toBe(true);
    panel.querySelector('.file-viewer-tool-download').click();
    await settle();
    expect(run).toHaveBeenCalledTimes(1);
    panel.querySelector('.file-viewer-stage').dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(panel.hidden).toBe(true);
    expect(document.activeElement).toBe(card);
    dom.window.close();
  });

  it('reads a CSV as a table and keeps Markdown from reaching out', async () => {
    const { window, document, dom } = boot();
    const viewer = window.App.fileViewer;
    viewer.open({ key: 'c', name: 'data.csv', load: text('name,"value, with comma"\nalpha,1\nbeta,"say ""hi"""\n') });
    await settle(); await settle();
    const rows = [...document.querySelectorAll('.file-viewer-table tr')].map(row => [...row.cells].map(cell => cell.textContent));
    expect(rows).toEqual([['', 'name', 'value, with comma'], ['2', 'alpha', '1'], ['3', 'beta', 'say "hi"']]);
    // Through the answer's own renderer: a remote picture is a note, never a request.
    viewer.open({ key: 'm', name: 'plan.md', load: text('# Plan\n\n![tracker](https://evil.example/p.png)\n\n'
      + '<style>body{}</style>\n\n<form><input></form>\n\n[bad](javascript:alert(1)) [ok](https://example.com)') });
    await vi.waitFor(() => expect(document.querySelector('.file-viewer-markdown h1')).not.toBeNull());
    const sheet = document.querySelector('.file-viewer-markdown');
    expect(sheet.querySelector('h1').textContent).toBe('Plan');
    expect(sheet.querySelector('img, style, form, input')).toBeNull();
    expect(sheet.querySelector('.blocked-remote-image')).not.toBeNull();
    const links = [...sheet.querySelectorAll('a')];
    expect(links.some(link => /^javascript:/i.test(link.getAttribute('href') || ''))).toBe(false);
    expect(links.find(link => link.textContent === 'ok')?.getAttribute('href'), sheet.innerHTML).toBe('https://example.com');
    // A file that is no text says so, with its download.
    viewer.open({ key: 'b', name: 'blob.txt', load: async () => ({ blob: new Blob([new Uint8Array([0x00, 0x01, 0x00, 0x02])]), mime: 'text/plain' }),
      downloads: [{ label: 'TXT', run: vi.fn() }] });
    await vi.waitFor(() => expect(document.querySelector('.file-viewer-notice')).not.toBeNull());
    expect(document.querySelector('.file-viewer-notice').textContent).toContain('There is no preview of this file.');
    expect([...document.querySelectorAll('.file-viewer-notice button')].map(b => b.textContent)).toEqual(['Download']);
    dom.window.close();
  });

  it('draws a Mermaid block of a Markdown file, whose code the sheet hides', async () => {
    // A stand-in for diagram-render.js: the drawing itself needs a browser.
    const drawn = [];
    const { window, document, dom } = boot({ before(window) {
      window.ConsensusDiagram = { key: source => `k${source.length}`, warm() {},
        render(root) { root.querySelectorAll('.md-diagram[data-diagram]').forEach(place => drawn.push(place)); } };
    } });
    window.App.fileViewer.open({ key: 'd', name: 'flow.md', load: text('# Flow\n\n```mermaid\nflowchart LR\n  A --> B\n```\n') });
    await vi.waitFor(() => expect(document.querySelector('.file-viewer-markdown .md-diagram')).not.toBeNull());
    // diagram.css hides the code inside a diagram's place: only its drawing shows the block.
    expect(drawn).toEqual([document.querySelector('.file-viewer-markdown .md-diagram')]);
    dom.window.close();
  });

  it('reads a German Excel CSV and UTF-16 text, and says where a long table stops', async () => {
    const { window, document, dom } = boot();
    const viewer = window.App.fileViewer;
    const bytes = values => async () => ({ blob: new Blob([new Uint8Array(values)]), mime: 'text/csv' });
    // "Größe;Preis\nÄpfel;2\n" in Windows-1252, as a German Excel saves it.
    viewer.open({ key: 'w', name: 'preise.csv', load: bytes([0x47, 0x72, 0xf6, 0xdf, 0x65, 0x3b, 0x50, 0x72, 0x65, 0x69, 0x73, 0x0a,
      0xc4, 0x70, 0x66, 0x65, 0x6c, 0x3b, 0x32, 0x0a]) });
    await vi.waitFor(() => expect(document.querySelector('.file-viewer-table')).not.toBeNull());
    expect([...document.querySelectorAll('.file-viewer-table th')].map(cell => cell.textContent)).toEqual(['', 'Größe', 'Preis']);
    expect(document.querySelector('.file-viewer-table td:nth-child(2)').textContent).toBe('Äpfel');
    // UTF-16 with its byte order mark.
    const utf16 = [0xff, 0xfe, ...[...'a,b\n1,2\n'].flatMap(char => [char.charCodeAt(0), 0])];
    viewer.open({ key: 'u', name: 'werte.csv', load: bytes(utf16) });
    await vi.waitFor(() => expect(document.querySelector('.file-viewer-table th:nth-child(2)')?.textContent).toBe('a'));
    expect(document.querySelector('.file-viewer-sheet-note')).toBeNull();
    // 1,000 rows show; the rest is the download's, and the preview says so.
    const long = ['n,v', ...Array.from({ length: 1200 }, (_, i) => `${i},x`)].join('\n');
    viewer.open({ key: 'l', name: 'lang.csv', load: text(long) });
    await vi.waitFor(() => expect(document.querySelector('.file-viewer-sheet-note')).not.toBeNull());
    expect(document.querySelectorAll('.file-viewer-table tbody tr').length).toBe(1000);
    expect(document.querySelector('.file-viewer-sheet-note').textContent).toBe('Showing the first 1000 rows. Download the file for the rest.');
    dom.window.close();
  });
});
