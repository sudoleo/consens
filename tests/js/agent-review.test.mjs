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
it('explains the recorded comparison in the duration disclosure and opens its original evidence', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'), details = d.createElement('div');
  body.dataset.markdown = 'Exact answer.';
  const review = snapshot();
  review.comparisons[0].reason = '<img src=x> Compare costs';
  review.checks[0].differences_data.differences = [{type:'contradiction',claim:'Whether five seats are included'}];
  review.checks[0].source_verification = {answer_version:'answer-hash',run_id:'c1',basis_hash:'b1',
    scope:{checked_contradictions:1,contradictions:1},status:'complete'};
  // Activity renders before the answer's reader contexts are registered.
  w.App.agentReview.renderActivity(details, review, body.dataset.markdown);
  w.App.agentReview.render(body, review);
  expect(details.hidden).toBe(false);
  expect(details.textContent).toContain('Comparison 1 · 1 model answer');
  expect(details.textContent).toContain('Models: GPT');
  expect(details.textContent).toContain('Disagreement: Whether five seats are included');
  expect(details.textContent).toContain('Source checks: 1 of 1 disagreements checked.');
  expect(details.querySelector('img')).toBeNull();
  details.querySelector('button').click();
  expect(w.App.answerReader.openContext).toHaveBeenLastCalledWith(expect.objectContaining({key:'agent-evidence:c1'}),
    expect.objectContaining({section:'answers'}));
  // An equivalent saved snapshot still shares usable reader contexts.
  const saved = structuredClone(review);
  w.App.agentReview.renderActivity(details, saved, body.dataset.markdown);
  w.App.agentReview.render(body, saved);
  details.querySelectorAll('button')[1].click();
  expect(w.App.answerReader.openContext).toHaveBeenLastCalledWith(expect.objectContaining({key:'agent-evidence:c1'}),
    expect.objectContaining({section:'differences'}));
  dom.window.close();
});
it('shows the live comparison purpose while its answers and checks are still pending', () => {
  const {window: w, document: d, dom} = setup();
  const host = d.createElement('div');
  w.App.agentReview.renderActivity(host, {status:'required',comparisons:[{id:'c1',status:'running',
    question:'Which plan fits?',reason:'Compare cost and flexibility',answers:[]}]}, '');
  expect(host.hidden).toBe(false);
  expect(host.textContent).toContain('Collecting answers…');
  expect(host.textContent).toContain('Compare cost and flexibility');
  expect([...host.querySelectorAll('button')].every(b => b.disabled)).toBe(true);
  expect(host.textContent).not.toContain('Comparison checked');
  dom.window.close();
});
it('keeps partial and stale reviews honest in activity insights and clears them for another turn', () => {
  const {window: w, document: d, dom} = setup();
  const details = d.createElement('div'), review = snapshot();
  review.checks[0].status = 'partial';
  review.checks[0].issues = [{code:'coverage_unavailable'}];
  review.checks[0].differences_data.differences = [{type:'contradiction',claim:'A recorded disagreement'}];
  w.App.agentReview.renderActivity(details, review, 'Exact answer.');
  expect(details.textContent).toContain('Partly checked');
  expect(details.textContent).toContain('The coverage check could not run');
  w.App.agentReview.renderActivity(details, review, 'Changed answer.');
  expect(details.textContent).toContain('Review pending');
  expect(details.textContent).not.toContain('A recorded disagreement');
  expect(details.textContent).not.toContain('Comparison checked');
  review.comparisons[0].basis_hash = 'changed';
  w.App.agentReview.renderActivity(details, review, 'Exact answer.');
  expect(details.querySelector('.agent-activity-insight').textContent).not.toContain('A recorded disagreement');
  w.App.agentReview.renderActivity(details, null, 'Another answer.');
  expect(details.hidden).toBe(true);
  expect(details.childElementCount).toBe(0);
  dom.window.close();
});
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
  expect(d.body.textContent).toContain("Review pending");
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

function partialReview() {
  const review = snapshot();
  review.status = 'partial'; review.comparisons = review.comparisons.slice(0, 1); review.checks = review.checks.slice(0, 1);
  review.comparisons[0].status = 'partial';
  review.comparisons[0].failed_models = [{label: 'GPT Luna', model: 'openai/test',
    failure: {code: 'provider_rate_limited', error: 'This model is temporarily rate limited.'}}];
  const check = review.checks[0]; check.status = 'partial';
  check.differences_data.judges = {differences: {provider: 'Gemini'}, coverage: {missing: 0}};
  return review;
}
it('explains a missing model without reporting a failed check, including older saved reviews', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = partialReview();
  for (const persistedIssues of [undefined, [{code: 'models_unavailable', count: 1}]]) {
    review.checks[0].issues = persistedIssues;
    w.App.agentReview.render(body, review);
    // A missing model does not change how far the marks can be trusted, so
    // the line under the answer stays silent; the reader panel explains it.
    expect(d.querySelector('.agent-review-status').textContent).toBe('');
    expect(d.querySelector('.agent-review-status').hidden).toBe(true);
    expect(d.querySelector('.agent-review-summary').hidden).toBe(true);
    expect(d.querySelector('.agent-review-status').dataset.state).toBe('partial');
    expect(d.querySelector('[data-section="answers"]').textContent).toBe('Answers1');
    d.querySelector('[data-section="differences"]').click();
    const context = w.App.answerReader.openContext.mock.calls.at(-1)[0];
    const panel = context.renderPanel('differences');
    expect(panel.textContent).toContain('1 of 2 models returned complete answers');
    expect(panel.textContent).toContain('GPT Luna: no answer, the provider was busy.');
    expect(panel.textContent).toContain('differences and coverage checks completed');
    expect(context.answers.at(-1).error).toContain('the provider was busy');
  }
  dom.window.close();
});
it.each([
  ['coverage', 'The coverage check could not run', 'Partly checked'],
  ['sentences', '2 sentences could not be checked', ''],
  ['sources', 'Some contradiction source checks did not finish', '']
])('keeps %s failures distinct from unavailable comparison models', (kind, reason, line) => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = partialReview(); const check = review.checks[0];
  if (kind === 'coverage') delete check.differences_data.judges.coverage;
  if (kind === 'sentences') check.differences_data.judges.coverage.missing = 2;
  if (kind === 'sources') check.source_verification = {answer_version: 'answer-hash', run_id: 'c1', basis_hash: 'b1', status: 'partial'};
  w.App.agentReview.render(body, review);
  // Only a missing check speaks under the answer; minor gaps stay in the panel.
  expect(d.querySelector('.agent-review-status').textContent).toBe(line);
  d.querySelector('[data-section="differences"]').click();
  const panel = w.App.answerReader.openContext.mock.calls.at(-1)[0].renderPanel('differences');
  expect(panel.textContent).toContain(reason);
  expect(panel.textContent).not.toContain('differences and coverage checks completed');
  dom.window.close();
});

it('adds no note under a checked answer and one calm sentence otherwise', () => {
  const {window: w, dom} = setup();
  const note = w.App.agentReview.failureNote;
  const failure = {code: 'provider_error', error: 'The model provider could not finish this request. Trying again in a moment usually works.'};
  const review = {status: 'succeeded', answer_version: 1, answer_hash: 'h', versions: [{id: 1, text: 'Checked answer.', hash: 'h'}]};
  expect(note(failure, review, 'Checked answer.')).toBe('');
  expect(note(failure, {...review, status: 'failed'}, 'Checked answer.')).toMatch(/^This answer may be incomplete/);
  expect(note(failure, review, 'Another text.')).toMatch(/^This answer may be incomplete/);
  expect(note(failure, null, '')).toBe(failure.error);
  dom.window.close();
});

it.each([
  [[{code: 'insufficient_answers'}], 'Not compared · fewer than two models answered'],
  [[{code: 'differences_unavailable'}], 'Disagreements not checked'],
  [[{code: 'models_unavailable', count: 2}, {code: 'truncated_answers', count: 1}], ''],
])('speaks under the answer only when the check itself is limited (%j)', (issues, text) => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = partialReview();
  review.checks[0].issues = issues;
  w.App.agentReview.render(body, review);
  const status = d.querySelector('.agent-review-status');
  expect(status.textContent).toBe(text);
  expect(status.hidden).toBe(!text);
  dom.window.close();
});
it('names an output limit as the reason a comparison model gave no answer', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = partialReview();
  review.comparisons[0].failed_models[0].failure = {code: 'output_limit'};
  w.App.agentReview.render(body, review);
  d.querySelector('[data-section="differences"]').click();
  const context = w.App.answerReader.openContext.mock.calls.at(-1)[0];
  expect(context.answers.at(-1).error).toContain('whole output allowance');
  expect(context.answers.at(-1).error).not.toContain('did not respond');
  dom.window.close();
});
it('keeps Copy in the evidence row across re-renders and hands it back when the row goes away', async () => {
  const {window: w, document: d, dom} = setup();
  // Load the actions module into the same window.
  const script = d.createElement('script');
  script.textContent = (await import('node:fs')).readFileSync('static/js/agent-answer-actions.js', 'utf8');
  d.body.append(script);
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = snapshot();
  w.App.agentReview.render(body, review);
  w.App.agentAnswerActions.render(body, {key: 'k', text: 'Exact answer.'});
  const host = body._agentReview;
  const bar = d.querySelector('.agent-answer-actions');
  expect(bar.parentElement).toBe(host);
  review.checks[1].differences_data.differences = [{type: 'contradiction', claim: 'Changed'}];
  w.App.agentReview.render(body, review);
  expect(d.querySelectorAll('.agent-answer-actions')).toHaveLength(1);
  expect(d.querySelector('.agent-answer-actions').parentElement).toBe(body._agentReview);
  body.dataset.markdown = 'Plain answer.';
  w.App.agentReview.render(body, null, {});
  expect(body._agentReview).toBe(null);
  expect(body.nextElementSibling).toBe(bar);
  dom.window.close();
});
it('strokes the marks on once, in reading order, when a live answer is first checked', () => {
  vi.useFakeTimers();
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer');
  body.dataset.markdown = 'Exact answer.';
  w.matchMedia = () => ({ matches: false });
  w.renderStoredConsensusClaims = vi.fn(el => {
    el.innerHTML = '<span class="cx-claim is-unanimous">One.</span> <span class="claim-badge">2/2</span>'
      + ' <span class="cx-claim is-major">Two.</span>';
  });
  const review = snapshot();
  w.App.agentReview.render(body, review, { reveal: true });
  expect(body.classList.contains('is-marks-revealing')).toBe(true);
  const [first, badge, second] = body.querySelectorAll('.cx-claim, .claim-badge');
  expect(first.style.getPropertyValue('--cx-reveal-delay')).toBe('0ms');
  expect(parseInt(badge.style.getPropertyValue('--cx-reveal-delay'))).toBeGreaterThan(0);
  expect(parseInt(second.style.getPropertyValue('--cx-reveal-delay'))).toBeGreaterThan(0);
  vi.runAllTimers();
  expect(body.classList.contains('is-marks-revealing')).toBe(false);
  expect(first.getAttribute('style') || '').not.toContain('--cx-reveal-delay');
  // The same answer re-rendered (fresh DOM at the end of the run) shows its
  // marks at once instead of replaying the reveal.
  body._agentRenderSerial = 1;
  w.App.agentReview.render(body, review, { reveal: true });
  expect(w.renderStoredConsensusClaims).toHaveBeenCalledTimes(2);
  expect(body.classList.contains('is-marks-revealing')).toBe(false);
  vi.useRealTimers();
  dom.window.close();
});
it('shows marks without animation for saved answers and reduced motion', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer');
  body.dataset.markdown = 'Exact answer.';
  w.renderStoredConsensusClaims = vi.fn(el => { el.innerHTML = '<span class="cx-claim is-unanimous">One.</span>'; });
  w.App.agentReview.render(body, snapshot());
  expect(body.classList.contains('is-marks-revealing')).toBe(false);
  const other = snapshot(); other.answer_hash = other.versions[0].hash = 'other-hash';
  other.checks.forEach(c => { c.answer_hash = 'other-hash'; });
  w.matchMedia = () => ({ matches: true });
  w.App.agentReview.render(body, other, { reveal: true });
  expect(body.querySelector('.cx-claim')).not.toBeNull();
  expect(body.classList.contains('is-marks-revealing')).toBe(false);
  dom.window.close();
});
