import { expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";
import { marked } from 'marked';
import DOMPurify from 'dompurify';

function setup() {
  return loadScripts(["static/js/agent-review.js"], { body: '<section><div id="answer"></div></section>', before(w) {
    w.injectMarkdown = vi.fn((el, text) => { el.textContent = text; });
    w.renderStoredConsensusClaims = vi.fn(); w.renderStoredDifferenceCards = vi.fn();
    w.App = { answerReader: { openContext: vi.fn(), refreshContext: vi.fn() } };
    w.marked = marked; w.DOMPurify = DOMPurify(w);
  }});
}
function snapshot() {
  return { status: "succeeded", answer_version: 1, answer_hash: "answer-hash",
    versions: [{ id: 1, text: "Exact answer.", hash: "answer-hash" }],
    comparisons: [1, 2].map(i => ({ id: `c${i}`, basis_hash: `b${i}`, question: `Question ${i}`, reason: "Different perspectives",
      status: "succeeded", answers: [{ provider: "openai", model: { label: "GPT" }, text: "<script>unsafe</script>", sources: [{ url: "javascript:bad()" }, { url: "https://example.org", title: "Source" }] }] })),
    checks: [1, 2].map(i => ({ comparison_id: `c${i}`, basis_hash: `b${i}`, answer_hash: "answer-hash", status: "succeeded", differences_data: { claims: [{ anchor: `claim${i}` }], differences: [] } })) };
}
it("uses the shared markers only for the exact answer and selected comparison basis", () => {
  const { window: w, document: d, dom } = setup();
  const body = d.getElementById("answer"); body.dataset.markdown = "Exact answer.";
  w.App.agentReview.render(body, snapshot());
  expect(w.renderStoredConsensusClaims).toHaveBeenCalledTimes(1);
  const select = d.querySelector('[aria-label="Comparison basis"]');
  select.value = 'agent-evidence:c2'; select.dispatchEvent(new w.Event('change'));
  expect(w.renderStoredConsensusClaims.mock.calls[1][1].claims[0].anchor).toBe("claim2");
  expect(d.querySelectorAll('.agent-basis-select, .agent-comparison')).toHaveLength(0);
  expect(d.querySelector(".agent-review script")).toBeNull();
  d.querySelector('[data-section="sources"]').click();
  const context = w.App.answerReader.openContext.mock.calls[0][0];
  expect(context.renderPanel('sources').querySelectorAll('a')).toHaveLength(1);
  expect(context.answers[0].text).toBe('<script>unsafe</script>');
  w.renderStoredConsensusClaims.mock.calls[1][4].focusDifference(2);
  expect(w.App.answerReader.openContext).toHaveBeenLastCalledWith(context, expect.objectContaining({ section: 'differences', index: 2 }));
  body.dataset.markdown = "Changed answer.";
  w.App.agentReview.render(body, snapshot());
  expect(w.renderStoredConsensusClaims).toHaveBeenCalledTimes(2);
  expect(d.querySelector(".agent-review-status").textContent).toContain("Review pending");
  expect(w.injectMarkdown).toHaveBeenLastCalledWith(body, "Changed answer.", []);
  dom.window.close();
});
it('renders bound source evidence with the shared contradiction cards and rejects stale evidence', () => {
  const {window: w, document: d, dom} = setup();
  w.App.sourceVerification = {render: vi.fn()};
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = snapshot(); review.check_sources = true;
  review.checks[0].source_verification = {answer_version: 'answer-hash', run_id: 'c1', basis_hash: 'b1', status: 'complete'};
  w.App.agentReview.render(body, review);
  d.querySelector('[data-section="differences"]').click();
  let context = w.App.answerReader.openContext.mock.calls.at(-1)[0];
  const panel = context.renderPanel('differences');
  expect(w.App.sourceVerification.render).toHaveBeenCalledWith(panel.querySelector('.agent-evidence-differences'),
    panel.querySelector('.agent-source-check'), review.checks[0].source_verification,
    expect.objectContaining({differenceCards: panel.querySelector('.agent-evidence-differences')}));
  w.App.sourceVerification.render.mockClear();
  review.checks[0].source_verification.basis_hash = 'other';
  w.App.agentReview.render(body, review);
  d.querySelector('[data-section="differences"]').click();
  context = w.App.answerReader.openContext.mock.calls.at(-1)[0];
  expect(context.renderPanel('differences').textContent).toContain('source checks pending');
  expect(w.App.sourceVerification.render).not.toHaveBeenCalled();
  dom.window.close();
});
it('collects chat search, answer links and comparison citations into one source view', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  body.innerHTML = '<a href="https://example.org/chat">Chat citation</a><a href="javascript:bad()">Bad</a>';
  const review = snapshot();
  review.comparisons[0].answers[0].sources = [];
  review.comparisons[0].answers[0].text = 'Read [the comparison](https://example.org/plan).';
  w.App.agentReview.render(body, review, {events: [{sources: [{url: 'https://example.org/search', title: 'Search result'}, {url: 'https://example.org/chat#citation'}]}]});
  d.querySelector('[data-section="sources"]').click();
  const context = w.App.answerReader.openContext.mock.calls[0][0];
  expect([...context.renderPanel('sources').querySelectorAll('a')].map(a => a.href)).toEqual([
    'https://example.org/search', 'https://example.org/chat', 'https://example.org/plan', 'https://example.org/']);
  dom.window.close();
});
it('makes search sources available without a comparison, including saved legacy activities', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer');
  w.App.agentReview.render(body, null, {key: 'saved-turn', events: [{sources: [{url: 'https://example.org/search'}]}]});
  d.querySelector('[data-section="sources"]').click();
  const context = w.App.answerReader.openContext.mock.calls[0][0];
  expect(context.sections).toEqual(['sources']);
  expect(context.renderPanel('sources').querySelector('a').href).toBe('https://example.org/search');
  expect(d.querySelector('.agent-review-status')).toBeNull();
  w.App.agentReview.render(body, null, {key: 'another-turn', question: 'A different question', sources: [{url: 'https://example.org/search'}]});
  d.querySelector('[data-section="sources"]').click();
  expect(w.App.answerReader.openContext.mock.calls.at(-1)[0]).toMatchObject({ key: 'agent-sources:another-turn', question: 'A different question' });
  dom.window.close();
});
it("rejects stale comparison bindings and distinguishes incomplete results", () => {
  const { window: w, document: d, dom } = setup();
  const body = d.getElementById("answer"); body.dataset.markdown = "Exact answer.";
  const review = snapshot(); review.status = "partial"; review.checks[0].basis_hash = "stale";
  w.App.agentReview.render(body, review);
  expect(w.renderStoredConsensusClaims).not.toHaveBeenCalled();
  expect(d.body.textContent).toContain("Some checks unavailable");
  const select = d.querySelector('[aria-label="Comparison basis"]');
  select.value = 'agent-evidence:c2'; select.dispatchEvent(new w.Event('change'));
  expect(w.renderStoredConsensusClaims).toHaveBeenCalledTimes(1);
  w.injectMarkdown.mockClear();
  select.value = 'agent-evidence:c1'; select.dispatchEvent(new w.Event('change'));
  expect(w.injectMarkdown).toHaveBeenCalledWith(body, "Exact answer.", []);
  expect(w.renderStoredConsensusClaims).toHaveBeenCalledTimes(1);
  review.status = "succeeded";
  w.App.agentReview.render(body, review);
  expect(d.querySelector(".agent-review-status").textContent).toContain("Review pending");
  dom.window.close();
});
