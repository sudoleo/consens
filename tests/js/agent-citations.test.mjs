import {expect, it, vi} from 'vitest';
import {marked} from 'marked';
import DOMPurify from 'dompurify';
import {loadScripts} from './helpers/appWindow.mjs';

function setup() {
  return loadScripts(['static/js/sources.js', 'static/js/markdown-stream.js', 'static/js/agent-review.js'], {
    body: '<section><div id="agentAnswerBody" class="consensus-answer-body"></div></section>',
    before(w) {
      w.marked = marked; w.DOMPurify = DOMPurify(w);
      w.App = {answerReader: {openContext: vi.fn(), refreshContext: vi.fn()}};
    }
  });
}
function render(w, markdown, evidence = {}, review = null) {
  const body = w.document.getElementById('agentAnswerBody');
  body.dataset.markdown = markdown;
  w.injectMarkdown(body, markdown, []);
  w.App.agentReview.render(body, review, evidence);
  return body;
}
function sourcePanel(w) {
  w.document.querySelector('.agent-evidence-link[data-section="sources"]').click();
  return w.App.answerReader.openContext.mock.calls.at(-1)[0].renderPanel('sources');
}

it('turns parenthesized paper URLs into source pills with their original titles', () => {
  const {window: w, dom} = setup();
  const markdown = 'Verwandte Arbeiten: Self-Consistency (https://arxiv.org/abs/2203.07186), FrugalGPT (https://arxiv.org/abs/2305.05176), RouteLLM (https://arxiv.org/abs/2406.18665).';
  const body = render(w, markdown);
  expect(body.textContent.trim()).toBe('Verwandte Arbeiten: Self-Consistencyarxiv.org, FrugalGPTarxiv.org, RouteLLM.arxiv.org');
  expect([...body.querySelectorAll('.src-ref')].map(a => a.dataset.sourceNumber)).toEqual(['1', '2', '3']);
  expect([...body.querySelectorAll('.src-ref')].map(a => a.sourceData.title)).toEqual(['Self-Consistency', 'FrugalGPT', 'RouteLLM']);
  expect(body.querySelectorAll('a:not(.src-ref)')).toHaveLength(0);
  expect([...sourcePanel(w).querySelectorAll('a')].map(a => a.textContent)).toEqual(['Self-Consistency', 'FrugalGPT', 'RouteLLM']);
  expect(body.dataset.markdown).toBe(markdown);
  for (const ref of body.querySelectorAll('.src-ref')) {
    expect(ref.target).toBe('_blank');
    expect(ref.rel).toBe('noopener noreferrer');
    expect(ref.getAttribute('aria-label')).toBe('Source: arxiv.org');
    expect(ref.querySelector('.src-ref-favicon').getAttribute('src')).toBe('/api/topics/favicon?d=arxiv.org');
  }
  dom.window.close();
});

it('deduplicates repeated URLs and preserves named link formatting, code, math notation and unsafe links', () => {
  const {window: w, dom} = setup();
  const markdown = 'Read [**the paper**](https://example.org/paper). Again (https://example.org/paper#section). Vector [1].\n\n`https://code.example`\n\n```text\nhttps://block.example\n```\n\n[Account](https://user:secret@example.org/private) [Email](mailto:person@example.org) [Local](#section)';
  const body = render(w, markdown);
  expect([...body.querySelectorAll('.src-ref')].map(a => a.dataset.sourceNumber)).toEqual(['1', '1']);
  expect([...body.querySelectorAll('.src-ref-label')].map(a => a.textContent)).toEqual(['example.org', 'example.org']);
  expect(body.querySelector('strong').textContent).toBe('the paper');
  expect(body.textContent).toContain('Vector [1]');
  expect(body.querySelector('code').textContent).toBe('https://code.example');
  expect(body.querySelector('pre').textContent).toContain('https://block.example');
  expect(sourcePanel(w).querySelectorAll('a')).toHaveLength(1);
  dom.window.close();
});

it('maps explicit source IDs by identity without turning numeric notation or ambiguous IDs into citations', () => {
  const {window: w, dom} = setup();
  const sources = [{id: 'S7', url: 'https://example.org/seven', title: 'Seven'},
    {id: 'S2', url: 'https://example.org/two', title: 'Two'}, {id: 'S2', url: 'https://other.org/two', title: 'Other'}];
  const body = render(w, 'Fact [S7]. Vector [1]. Ambiguous [S2]. Missing [S9].', {sources});
  expect(body.querySelectorAll('.src-ref')).toHaveLength(1);
  expect(body.querySelector('.src-ref').href).toBe(sources[0].url);
  expect(body.textContent).toContain('Vector [1]. Ambiguous [S2]. Missing [S9].');
  dom.window.close();
});

it('reformats streamed text and updates metadata without borrowing another turn or replacing focused references', () => {
  const {window: w, dom} = setup();
  const url = 'https://example.org/report';
  let body = render(w, `A finding (${url}).`, {key: 'turn-a'});
  const reference = body.querySelector('.src-ref'); reference.focus();
  w.App.agentReview.render(body, null, {key: 'turn-a', sources: [{url, title: 'Published report'}]});
  expect(w.document.activeElement).toBe(reference);
  expect(reference.sourceData.title).toBe('Published report');
  body = render(w, `A finding (${url}). More streamed text.`, {key: 'turn-a', sources: [{url, title: 'Published report'}]});
  expect(body.querySelectorAll('.src-ref')).toHaveLength(1);
  w.currentEvidenceSources = [{id: 'S1', url: 'https://wrong.example'}];
  body = render(w, 'Old answer (https://old.example/original).', {key: 'old-turn'});
  expect(body.querySelector('.src-ref').href).toBe('https://old.example/original');
  expect(sourcePanel(w).querySelectorAll('a')).toHaveLength(1);
  dom.window.close();
});

it('applies citations after review markers without changing the checked answer or its version binding', () => {
  const {window: w, dom} = setup();
  const markdown = 'A claim (https://example.org/evidence).';
  const review = {status: 'succeeded', answer_version: 1, answer_hash: 'hash',
    versions: [{id: 1, text: markdown, hash: 'hash'}],
    comparisons: [{id: 'c1', basis_hash: 'basis', question: 'Question', answers: [], status: 'succeeded'}],
    checks: [{comparison_id: 'c1', basis_hash: 'basis', answer_hash: 'hash', status: 'succeeded', differences_data: {differences: []}}]};
  w.renderStoredConsensusClaims = vi.fn(body => expect(body.textContent).toContain('https://example.org/evidence'));
  const body = render(w, markdown, {}, review);
  expect(w.renderStoredConsensusClaims).toHaveBeenCalledTimes(1);
  expect(body.querySelector('.src-ref').dataset.sourceNumber).toBe('1');
  expect(body.dataset.markdown).toBe(review.versions[0].text);
  // A clean check needs no words under the answer.
  expect(w.document.querySelector('.agent-review-status').hidden).toBe(true);
  w.injectMarkdown(body, markdown, []);
  w.App.agentReview.render(body, review);
  expect(body.querySelectorAll('.src-ref')).toHaveLength(1);
  dom.window.close();
});

it('lets a pill stand in for a link label that only repeats its domain', () => {
  const {window: w, dom} = setup();
  const markdown = '- Plattform (über seine Website [njaped.no](https://njaped.no/)) und Diagnostik.\n'
    + '- Als Profi geführt ([mywhooshinfo.com](https://mywhooshinfo.com/rider/1)).';
  const body = render(w, markdown);
  const [first, second] = body.querySelectorAll('li');
  // The domain is written once — inside the pill — and the prose keeps its place.
  expect(first.textContent).toBe('Plattform (über seine Website njaped.no) und Diagnostik.');
  expect(first.querySelector('.src-ref .src-ref-label').textContent).toBe('njaped.no');
  expect(first.querySelector('.src-ref').classList.contains('is-compact')).toBe(false);
  // A link that is only a citation in brackets loses the brackets and follows the punctuation.
  expect(second.textContent).toBe('Als Profi geführt.mywhooshinfo.com');
  expect(second.querySelector('.src-ref').getAttribute('href')).toBe('https://mywhooshinfo.com/rider/1');
  expect(body.dataset.markdown).toBe(markdown);
  dom.window.close();
});

it('collapses adjacent citations into one pill and lists every source in the teaser', () => {
  const {window: w, dom} = setup();
  const sources = [{url: 'https://uci.org/a', title: 'UCI ranking'}, {url: 'https://pcs.example/b', title: 'Rider profile'},
    {url: 'https://wiki.example/c', title: 'Encyclopedia'}];
  const body = render(w, 'Several reports confirm it [S1][S2], [S3]. Later (https://uci.org/a, https://pcs.example/b).', {sources});
  const pills = body.querySelectorAll('.src-ref');
  expect(pills).toHaveLength(2);
  expect(pills[0].dataset.sourceNumbers).toBe('1 2 3');
  expect(pills[0].querySelector('.src-ref-label').textContent).toBe('uci.org');
  expect(pills[0].querySelector('.src-ref-more').textContent).toBe('+2');
  expect(pills[0].getAttribute('aria-label')).toBe('Source: uci.org (and 2 more)');
  expect(pills[1].dataset.sourceNumbers).toBe('1 2');
  expect(body.textContent.trim()).toBe('Several reports confirm it.uci.org+2 Later.uci.org+1');
  pills[0].dispatchEvent(new w.Event('pointerover', {bubbles: true}));
  const teaser = w.document.getElementById('sourceTeaser');
  expect([...teaser.querySelectorAll('.source-teaser-title')].map(n => n.textContent))
    .toEqual(['UCI ranking', 'Rider profile', 'Encyclopedia']);
  expect(teaser.textContent).toContain('3 sources');
  // Re-rendering the same body keeps the pill element (focus/hover survive).
  w.App.agentReview.render(body, null, {sources});
  expect(body.querySelector('.src-ref')).toBe(pills[0]);
  expect(body.querySelector('.src-ref').dataset.sourceNumbers).toBe('1 2 3');
  expect(sourcePanel(w).querySelectorAll('a')).toHaveLength(3);
  dom.window.close();
});

it('shows only the favicon when the domain is already written before the citation', () => {
  const {window: w, dom} = setup();
  const sources = [{url: 'https://www.example.org/report', title: 'Report'}];
  const body = render(w, 'According to example.org [S1], prices rose. Elsewhere [S1].', {sources});
  const [compact, full] = body.querySelectorAll('.src-ref');
  expect(compact.classList.contains('is-compact')).toBe(true);
  expect(compact.getAttribute('aria-label')).toBe('Source: example.org');
  expect(full.classList.contains('is-compact')).toBe(false);
  expect(w.App.sourceRefs.plainText(compact)).toBe('');
  expect(w.App.sourceRefs.plainText(full)).toBe(' (example.org)');
  dom.window.close();
});

it('replaces a failed favicon with a neutral monogram instead of a broken image', () => {
  const {window: w, dom} = setup();
  const body = render(w, 'A finding (https://njaped.no/page).');
  const icon = body.querySelector('.src-ref-favicon');
  icon.dispatchEvent(new w.Event('error'));
  expect(body.querySelector('.src-ref img')).toBeNull();
  const glyph = body.querySelector('.src-ref .src-ref-glyph');
  expect(glyph.textContent).toBe('N');
  expect(glyph.getAttribute('aria-hidden')).toBe('true');
  dom.window.close();
});
