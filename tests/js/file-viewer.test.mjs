import { describe, it, expect, vi } from 'vitest';
import { loadScripts } from './helpers/appWindow.mjs';

function boot() {
  return loadScripts(['static/js/file-viewer.js'], { body: '<main><button id="card">card</button></main>', before(window) {
    window.App = { t: text => text, showPopup: vi.fn() };
    // jsdom has no TextDecoder; every browser does.
    window.TextDecoder = TextDecoder;
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
    window.marked = { parse: () => '<h1>Plan</h1><img src="/x"><a href="javascript:alert(1)">bad</a><a href="https://example.com">ok</a>' };
    window.DOMPurify = { sanitize: (html, options) => {
      const box = document.createElement('div'); box.innerHTML = html;
      for (const tag of options.FORBID_TAGS) box.querySelectorAll(tag).forEach(el => el.remove());
      return box.innerHTML;
    } };
    const viewer = window.App.fileViewer;
    viewer.open({ key: 'c', name: 'data.csv', load: text('name,"value, with comma"\nalpha,1\nbeta,"say ""hi"""\n') });
    await settle(); await settle();
    const rows = [...document.querySelectorAll('.file-viewer-table tr')].map(row => [...row.cells].map(cell => cell.textContent));
    expect(rows).toEqual([['', 'name', 'value, with comma'], ['2', 'alpha', '1'], ['3', 'beta', 'say "hi"']]);
    viewer.open({ key: 'm', name: 'plan.md', load: text('# Plan') });
    await settle(); await settle();
    const sheet = document.querySelector('.file-viewer-markdown');
    expect(sheet.querySelector('h1').textContent).toBe('Plan');
    expect(sheet.querySelector('img')).toBeNull();
    const links = [...sheet.querySelectorAll('a')];
    expect(links[0].hasAttribute('href')).toBe(false);
    expect(links[1].rel).toContain('noopener');
    // A file that is no text says so, with its download.
    viewer.open({ key: 'b', name: 'blob.txt', load: async () => ({ blob: new Blob([new Uint8Array([0xff, 0xfe, 0xfd])]), mime: 'text/plain' }),
      downloads: [{ label: 'TXT', run: vi.fn() }] });
    await settle(); await settle(); await settle();
    expect(document.querySelector('.file-viewer-notice').textContent).toContain('There is no preview of this file.');
    expect([...document.querySelectorAll('.file-viewer-notice button')].map(b => b.textContent)).toEqual(['Download']);
    dom.window.close();
  });
});
