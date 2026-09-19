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

it('turns parenthesized paper URLs into numbered references with their original titles', () => {
  const {window: w, dom} = setup();
  const markdown = 'Verwandte Arbeiten: Self-Consistency (https://arxiv.org/abs/2203.07186), FrugalGPT (https://arxiv.org/abs/2305.05176), RouteLLM (https://arxiv.org/abs/2406.18665).';
  const body = render(w, markdown);
  expect(body.textContent.trim()).toBe('Verwandte Arbeiten: Self-Consistency1, FrugalGPT2, RouteLLM.3');
  expect([...body.querySelectorAll('.src-ref')].map(a => a.sourceData.title)).toEqual(['Self-Consistency', 'FrugalGPT', 'RouteLLM']);
  expect(body.querySelectorAll('a:not(.src-ref)')).toHaveLength(0);
  expect([...sourcePanel(w).querySelectorAll('a')].map(a => a.textContent)).toEqual(['Self-Consistency', 'FrugalGPT', 'RouteLLM']);
  expect(body.dataset.markdown).toBe(markdown);
  for (const ref of body.querySelectorAll('.src-ref')) {
    expect(ref.target).toBe('_blank');
    expect(ref.rel).toBe('noopener noreferrer');
    expect(ref.getAttribute('aria-label')).toMatch(/^Source \d: /);
  }
  dom.window.close();
});

it('deduplicates repeated URLs and preserves named link formatting, code, math notation and unsafe links', () => {
  const {window: w, dom} = setup();
  const markdown = 'Read [**the paper**](https://example.org/paper). Again (https://example.org/paper#section). Vector [1].\n\n`https://code.example`\n\n```text\nhttps://block.example\n```\n\n[Account](https://user:secret@example.org/private) [Email](mailto:person@example.org) [Local](#section)';
  const body = render(w, markdown);
  expect([...body.querySelectorAll('.src-ref')].map(a => a.textContent)).toEqual(['1', '1']);
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
  expect(body.querySelector('.src-ref').textContent).toBe('1');
  expect(body.dataset.markdown).toBe(review.versions[0].text);
  expect(w.document.querySelector('.agent-review-status').textContent).toBe('Comparison checked');
  w.injectMarkdown(body, markdown, []);
  w.App.agentReview.render(body, review);
  expect(body.querySelectorAll('.src-ref')).toHaveLength(1);
  dom.window.close();
});
