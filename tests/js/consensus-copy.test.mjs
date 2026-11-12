import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, it, expect, vi } from 'vitest';
import { loadScripts, ROOT } from './helpers/appWindow.mjs';

const DIAGRAM_CSS = readFileSync(path.join(ROOT, 'static/css/diagram.css'), 'utf8');

// jsdom has no innerText. This one reads what a browser shows: the text of
// rendered nodes, a line break around each block, nothing of display:none.
function renderedText(window) {
  const blocks = new Set(['P', 'DIV', 'PRE', 'LI', 'UL', 'OL', 'H1', 'H2', 'H3', 'FIGURE']);
  function read(node) {
    if (node.nodeType === window.Node.TEXT_NODE) return node.data;
    if (node.nodeType !== window.Node.ELEMENT_NODE) return '';
    if (window.getComputedStyle(node).display === 'none') return '';
    const inner = Array.from(node.childNodes).map(read).join('');
    return blocks.has(node.tagName) ? `\n${inner}\n` : inner;
  }
  return function innerText() {
    return read(this).replace(/\n{2,}/g, '\n');
  };
}

function boot(answer) {
  const writeText = vi.fn(() => Promise.resolve());
  const env = loadScripts(['static/js/consensus-actions.js'], {
    body: `<style>${DIAGRAM_CSS}</style>
      <div id="consensusResponse"><div class="consensus-main"><h2>Answer</h2>
        <div id="consensusAnswerBody" class="consensus-answer-body">${answer}</div>
      </div></div>`,
    before(window) {
      Object.defineProperty(window.HTMLElement.prototype, 'innerText', { configurable: true, get: renderedText(window) });
      Object.defineProperty(window.navigator, 'clipboard', { configurable: true, value: { writeText } });
      window.App = {
        consensusBodyEl: scope => (scope || window.document).querySelector('#consensusAnswerBody'),
        showPopup: vi.fn(),
        trackAppEvent: vi.fn(),
      };
    },
  });
  return { ...env, writeText };
}

describe('Copy consensus (consensus-actions.js)', () => {
  it('copies the source of a drawn diagram, which the answer shows as a picture', () => {
    const { document, writeText } = boot(`<p>Before</p>
      <div class="md-diagram is-drawn" data-diagram="k" data-drawn="light">
        <div class="md-diagram-figure"><button type="button" class="md-diagram-open" aria-label="Open diagram"><img alt="Flow"></button></div>
        <pre><code class="language-mermaid">flowchart LR
  A --&gt; B
</code></pre>
      </div>
      <p>After</p>`);
    document.querySelector('.consensus-copy-btn').click();
    expect(writeText).toHaveBeenCalledTimes(1);
    const copied = writeText.mock.calls[0][0];
    expect(copied).toContain('flowchart LR\n  A --> B');
    expect(copied.indexOf('Before')).toBeLessThan(copied.indexOf('flowchart'));
    expect(copied.indexOf('flowchart')).toBeLessThan(copied.indexOf('After'));
    // The answer on the page keeps its picture.
    expect(document.querySelector('#consensusAnswerBody .md-diagram > pre')).not.toBeNull();
  });
});
