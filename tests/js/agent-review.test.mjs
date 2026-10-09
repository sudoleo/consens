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
    // One quiet line; the missing model is detail on demand behind it.
    const status = panel.querySelector('.agent-evidence-status');
    expect(status.tagName).toBe('DETAILS');
    expect(status.open).toBe(false);
    expect(status.querySelector('summary').textContent).toBe('1 of 2 models answered · Checked');
    expect(status.querySelector('.agent-evidence-status-detail').textContent).toBe('GPT Luna: no answer, the provider was busy.');
    expect(panel.firstElementChild).toBe(status);
    expect(panel.querySelectorAll(':scope > p.agent-review-note')).toHaveLength(0);
    expect(panel.textContent).not.toContain('Comparison checked');
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
  const status = panel.querySelector('.agent-evidence-status');
  expect(status.querySelector('summary').textContent).toBe('1 of 2 models answered · Partly checked');
  // A missing check changes how the panel reads and stays visible; smaller
  // gaps are listed behind the status line with the missing model.
  const detail = status.querySelector('.agent-evidence-status-detail').textContent;
  if (kind === 'coverage') {
    expect(panel.querySelector('.agent-evidence-limit').textContent).toContain(reason);
    expect(detail).not.toContain(reason);
  } else {
    expect(detail).toContain(reason);
    expect(panel.querySelector('.agent-evidence-limit')).toBeNull();
  }
  dom.window.close();
});
it('keeps a fully answered check to one line and the source report below the findings', () => {
  const {window: w, document: d, dom} = setup();
  w.App.sourceVerification = {render: vi.fn()};
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = snapshot();
  review.checks[0].source_verification = {answer_version: 'answer-hash', run_id: 'c1', basis_hash: 'b1', status: 'complete'};
  w.App.agentReview.render(body, review);
  d.querySelector('[data-section="differences"]').click();
  const panel = w.App.answerReader.openContext.mock.calls.at(-1)[0].renderPanel('differences');
  const status = panel.querySelector('.agent-evidence-status');
  expect(status.tagName).toBe('P');
  expect(status.textContent).toBe('1 model answered · Checked');
  const order = [...panel.children].map(child => child.className);
  expect(order).toEqual(['agent-evidence-status', 'agent-evidence-differences', 'agent-evidence-footer']);
  const footer = panel.querySelector('.agent-evidence-footer');
  expect(footer.querySelector('.agent-source-check')).not.toBeNull();
  // One quiet line at most: no standing disclaimers or context toggle.
  expect(footer.textContent).not.toContain('Model agreement is not independent fact checking.');
  expect(footer.querySelector('.agent-evidence-context')).toBeNull();
  expect(w.App.sourceVerification.render.mock.calls[0][3]).toMatchObject({compact: true});
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
it('shows a model stopped mid-answer as a marked, readable incomplete answer, and a cut-off one as marked', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = partialReview();
  review.comparisons[0].failed_models[0] = {...review.comparisons[0].failed_models[0],
    failure: {code: 'late_cutoff'}, partial_text: 'First half of an answer'};
  review.comparisons[0].answers[0].truncated = true;
  w.App.agentReview.render(body, review);
  d.querySelector('[data-section="differences"]').click();
  const context = w.App.answerReader.openContext.mock.calls.at(-1)[0];
  const stopped = context.answers.at(-1);
  expect(stopped.status).toBe('incomplete');
  expect(stopped.text).toBe('First half of an answer');
  expect(stopped.error).toContain('Not used for the answer or its check');
  expect(context.answers[0]).toMatchObject({status: 'complete', badge: 'Cut off'});
  const panel = context.renderPanel('differences');
  expect(panel.textContent).toContain('GPT Luna: stopped before it finished, it was still writing when the answer was checked.');
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
  let now = 1000;
  w.performance.now = () => now;
  const review = snapshot();
  w.App.agentReview.render(body, review, { reveal: true });
  expect(body.classList.contains('is-marks-revealing')).toBe(true);
  // A live update with the same text and check keeps the marked DOM.
  const span = body.querySelector('.cx-claim');
  w.App.agentReview.render(body, { ...review, comparisons: review.comparisons.map(c => ({ ...c })) }, { reveal: true, events: [{}] });
  expect(body.querySelector('.cx-claim')).toBe(span);
  // A fresh DOM mid-reveal continues the stroke instead of restarting it.
  now = 1400; body._agentRenderSerial = 1;
  w.App.agentReview.render(body, review, { reveal: true });
  expect(parseInt(body.querySelector('.cx-claim').style.getPropertyValue('--cx-reveal-delay'))).toBe(-400);
  const [first, badge, second] = body.querySelectorAll('.cx-claim, .claim-badge');
  const delay = el => parseInt(el.style.getPropertyValue('--cx-reveal-delay'));
  expect(delay(first)).toBe(-400);
  expect(delay(badge)).toBeGreaterThan(delay(first));
  expect(delay(second)).toBeGreaterThan(delay(first));
  // So does a rebuild from a render that does not ask for the reveal itself
  // (a settled source check repaints with reveal: false).
  now = 1500; body._agentRenderSerial = 3;
  w.App.agentReview.render(body, review, {});
  expect(delay(body.querySelector('.cx-claim'))).toBe(-500);
  expect(body.classList.contains('is-marks-revealing')).toBe(true);
  vi.runAllTimers();
  expect(body.classList.contains('is-marks-revealing')).toBe(false);
  // The hand-over to the plain mark colour runs without a transition and
  // leaves no switch behind.
  expect(body.classList.contains('is-marks-settling')).toBe(false);
  expect(body.querySelector('.cx-claim').getAttribute('style') || '').not.toContain('--cx-reveal-delay');
  // After the reveal a re-rendered answer shows its marks at once.
  now = 9000; body._agentRenderSerial = 2;
  w.App.agentReview.render(body, review, { reveal: true });
  expect(w.renderStoredConsensusClaims).toHaveBeenCalledTimes(4);
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
it('leaves marks hidden by the highlight setting out of the reveal', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer');
  body.dataset.markdown = 'Exact answer.';
  w.matchMedia = () => ({ matches: false });
  w.renderStoredConsensusClaims = vi.fn(el => {
    el.innerHTML = '<span class="cx-claim is-unanimous is-marker-filtered">Green.</span> <span class="cx-claim is-major">Red.</span>';
  });
  w.App.agentReview.render(body, snapshot(), { reveal: true });
  const [green, red] = body.querySelectorAll('.cx-claim');
  expect(green.style.getPropertyValue('--cx-reveal-delay')).toBe('');
  expect(red.style.getPropertyValue('--cx-reveal-delay')).toBe('0ms');
  // With all highlights off nothing animates at all.
  const other = snapshot(); other.answer_hash = other.versions[0].hash = 'hidden-hash';
  other.checks.forEach(c => { c.answer_hash = 'hidden-hash'; });
  body.classList.remove('is-marks-revealing');
  d.body.classList.add('consensus-markers-hidden');
  w.App.agentReview.render(body, other, { reveal: true });
  expect(body.classList.contains('is-marks-revealing')).toBe(false);
  dom.window.close();
});

it('leads the evidence row with a quiet agreement score of the comparison it shows', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer');
  body.dataset.markdown = 'Exact answer.';
  const review = snapshot();
  review.checks[0].differences_data.agreement = { score: 72, coverage_status: 'sufficient' };
  review.checks[1].differences_data.agreement = { score: 31, coverage_status: 'sufficient' };
  w.App.agentReview.render(body, review);
  const score = () => body._agentReview.querySelector(':scope > .agent-agreement');
  expect(score().textContent).toBe('72/100 agreementStrong agreement');
  expect(score().dataset.tone).toBe('calm');
  expect(score().title).toContain('not independent fact checking');
  // Switching the evidence basis switches the number with it.
  const picker = body._agentReview.querySelector('.agent-evidence-focus select');
  picker.value = 'agent-evidence:c2'; picker.dispatchEvent(new w.Event('change'));
  expect(body._agentReview.querySelectorAll('.agent-agreement')).toHaveLength(1);
  expect(score().dataset.tone).toBe('alert');
  expect(score().querySelector('.agent-agreement-level').textContent).toBe('Low agreement');
  // Too little overlap to score, or a stale check: no number at all.
  const thin = snapshot();
  thin.checks[0].differences_data.agreement = { score: 90, coverage_status: 'insufficient' };
  w.App.agentReview.render(body, thin);
  expect(score()).toBeNull();
  dom.window.close();
});
it('follows a queued contradiction job after the turn and repaints the answer evidence as it settles', () => {
  const {window: w, document: d, dom} = setup();
  const watches = [];
  w.auth = {currentUser: {uid: 'owner'}};
  w.App.sourceVerification = {render: vi.fn(), observe: vi.fn(options => { const stop = vi.fn(); watches.push({options, stop}); return stop; })};
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = snapshot(); review.check_sources = true;
  review.checks[0].differences_data.differences = [{type: 'contradiction', claim: 'Price'}];
  const queued = {job_id: 'job-1', status: 'queued', revision: 0, schema_version: 4, check_type: 'contradiction_evidence',
    answer_version: 'answer-hash', run_id: 'c1', basis_hash: 'b1', findings: []};
  review.checks[0].source_verification = queued;
  w.App.agentReview.render(body, review, {key: 'turn-1'});
  // One watcher per pending job, bound to its reference and the owner.
  expect(watches).toHaveLength(1);
  expect(watches[0].options.snapshot).toBe(queued);
  expect(watches[0].options.auth.uid).toBe('owner');
  expect(watches[0].options.isActive()).toBe(true);
  w.App.agentReview.render(body, review, {key: 'turn-1'});
  expect(watches).toHaveLength(1);
  w.App.answerReader.refreshContext.mockClear();
  // The poll returns the job snapshot; the reference keeps its basis.
  const {basis_hash, ...settledJob} = {...queued, status: 'complete', revision: 1, findings: [{contradiction_id: 'x', checked: true}]};
  watches[0].options.onUpdate(settledJob);
  expect(review.checks[0].source_verification).toMatchObject({status: 'complete', basis_hash: 'b1', revision: 1});
  expect(w.App.answerReader.refreshContext).toHaveBeenCalledWith(expect.objectContaining({key: 'agent-evidence:c1'}));
  expect(watches[0].stop).toHaveBeenCalled();
  d.querySelector('[data-section="differences"]').click();
  const panel = w.App.answerReader.openContext.mock.calls.at(-1)[0].renderPanel('differences');
  expect(w.App.sourceVerification.render).toHaveBeenLastCalledWith(panel.querySelector('.agent-evidence-differences'),
    panel.querySelector('.agent-source-check'), review.checks[0].source_verification, expect.anything());
  // A saved copy of the turn still names the queued job: it shows the settled
  // snapshot at once instead of starting over.
  const saved = structuredClone(review);
  saved.checks[0].source_verification = {...queued};
  w.App.agentReview.render(body, saved, {key: 'turn-1'});
  expect(saved.checks[0].source_verification.status).toBe('complete');
  expect(watches).toHaveLength(1);
  dom.window.close();
});
it('starts a dead observer again instead of showing a queued job forever', () => {
  // Without a signed-in user at the first paint (or after the page left the
  // back/forward cache) the observer ended at once and the job read
  // "Contradiction source check queued" until a reload.
  const {window: w, document: d, dom} = setup();
  const observers = [];
  w.App.sourceVerification = {render: vi.fn(), observe: vi.fn(options => {
    let ended = !options.auth.user;
    const stop = Object.assign(vi.fn(() => { ended = true; }), {stopped: () => ended});
    observers.push({options, stop});
    return stop;
  })};
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = snapshot();
  review.checks[0].source_verification = {job_id: 'job-1', status: 'queued', answer_version: 'answer-hash', run_id: 'c1', basis_hash: 'b1'};
  w.App.agentReview.render(body, review);
  expect(observers).toHaveLength(1);
  w.auth = {currentUser: {uid: 'owner'}};
  w.dispatchEvent(new w.Event('consensio:auth-state'));
  expect(observers).toHaveLength(2);
  expect(observers[1].options.auth.uid).toBe('owner');
  // A live observer is kept; one that ended on pagehide comes back on pageshow.
  w.dispatchEvent(new w.Event('pageshow'));
  expect(observers).toHaveLength(2);
  observers[1].stop();
  w.dispatchEvent(new w.Event('pageshow'));
  expect(observers).toHaveLength(3);
  dom.window.close();
});
it('stops following a job when its answer leaves the page or shows another review', () => {
  const {window: w, document: d, dom} = setup();
  const stops = [];
  w.auth = {currentUser: {uid: 'owner'}};
  w.App.sourceVerification = {render: vi.fn(), observe: vi.fn(() => { const stop = vi.fn(); stops.push(stop); return stop; })};
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = snapshot();
  review.checks[1].source_verification = {job_id: 'job-2', status: 'running', answer_version: 'answer-hash', run_id: 'c2', basis_hash: 'b2'};
  w.App.agentReview.render(body, review);
  const options = w.App.sourceVerification.observe.mock.calls[0][0];
  w.App.agentReview.render(body, snapshot());
  expect(stops[0]).toHaveBeenCalled();
  expect(options.isActive()).toBe(false);
  dom.window.close();
});
it('marks and scores the answer of a checked pasted text like any answer', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = snapshot();
  review.checks[0].differences_data.agreement = { score: 72, coverage_status: 'sufficient' };
  review.passage_check = { status: 'succeeded', comparison_id: 'c1', text: 'Pasted.', claims: [] };
  w.App.agentReview.render(body, review);
  // The answer gives a verdict and the correct information: its own
  // statements are judged and shown as usual; the card covers the text.
  expect(body._agentReview.querySelector('.agent-evidence-focus select').value).toBe('agent-evidence:c1');
  expect(w.renderStoredConsensusClaims).toHaveBeenCalledTimes(1);
  expect(body._agentReview.querySelector('.agent-agreement')).not.toBeNull();
  dom.window.close();
});
it('does not redraw an unchanged answer without claims, and draws a redrawn one again', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = snapshot();
  review.comparisons = review.comparisons.slice(0, 1);
  review.checks = review.checks.slice(0, 1);
  review.checks[0].differences_data.claims = [];
  w.App.agentReview.render(body, review);
  const injected = w.injectMarkdown.mock.calls.length;
  review.comparisons[0].reason = 'Another reason';
  w.App.agentReview.render(body, review);
  expect(w.injectMarkdown.mock.calls.length).toBe(injected);
  body.textContent = 'Streamed text';
  review.comparisons[0].reason = 'Yet another reason';
  w.App.agentReview.render(body, review);
  expect(w.injectMarkdown.mock.calls.length).toBe(injected + 1);
  expect(body.textContent).toBe('Exact answer.');
  dom.window.close();
});
it('marks and scores the answer as usual when the check of the pasted text failed', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = snapshot();
  review.comparisons = review.comparisons.slice(0, 1);
  review.checks = review.checks.slice(0, 1);
  review.checks[0].differences_data.agreement = { score: 72, coverage_status: 'sufficient' };
  // The server runs the answer's own checks then: they are the evidence.
  review.passage_check = { status: 'failed', comparison_id: 'c1', text: 'Pasted.', issues: [{ code: 'coverage_unavailable' }] };
  w.App.agentReview.render(body, review);
  expect(w.renderStoredConsensusClaims).toHaveBeenCalledTimes(1);
  expect(body._agentReview.querySelector('.agent-agreement')).not.toBeNull();
  dom.window.close();
});
it('puts the inline model row of an earlier turn above the card of a checked text', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  body.classList.add('thread-history-answer-body');
  const card = d.createElement('section'); body.before(card); body._passageCard = card;
  w.App.agentReview.render(body, snapshot());
  expect(card.previousElementSibling.classList.contains('agent-history-models')).toBe(true);
  expect(card.nextElementSibling).toBe(body);
  dom.window.close();
});
it('explains a comparison whose answer check was skipped because it checked a pasted text', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = snapshot();
  review.comparisons = review.comparisons.slice(0, 1);
  review.checks = [{ comparison_id: 'c1', basis_hash: 'b1', answer_hash: 'answer-hash', status: 'succeeded',
    differences_data: null, issues: [], skipped: 'passage_checked',
    source_verification: { answer_version: 'answer-hash', run_id: 'c1', basis_hash: 'b1', check_type: 'contradiction_evidence',
      status: 'skipped', reason_code: 'passage_checked', scope: { contradictions: 0, checked_contradictions: 0 } } }];
  review.check_sources = true;
  review.passage_check = { status: 'succeeded', comparison_id: 'c1', text: 'Pasted.', claims: [] };
  const details = d.createElement('div');
  w.App.agentReview.renderActivity(details, review, body.dataset.markdown);
  w.App.agentReview.render(body, review);
  const note = 'This comparison checked your text sentence by sentence; the result is shown above the answer.';
  expect(details.querySelector('.agent-activity-check').textContent).toBe(note);
  expect(details.textContent).not.toContain('Source checks:');
  expect(details.textContent).not.toContain('Partly checked');
  const status = body._agentReview.querySelector('.agent-review-status');
  expect(status.dataset.state).toBe('succeeded');
  expect(w.renderStoredConsensusClaims).not.toHaveBeenCalled();
  const context = w.App.agentReview.contextFor(review, 'c1');
  const panel = context.renderPanel('differences');
  expect(panel.textContent).toContain(note);
  expect(panel.textContent).not.toContain('no completed check');
  expect(panel.textContent).not.toMatch(/did not complete|pending/);
  dom.window.close();
});
it('opens a turn saved with a skipped answer check on the comparison that has marks', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = snapshot();
  review.checks[0] = { ...review.checks[0], differences_data: null, skipped: 'passage_checked' };
  review.passage_check = { status: 'succeeded', comparison_id: 'c1', text: 'Pasted.', claims: [] };
  w.App.agentReview.render(body, review);
  expect(body._agentReview.querySelector('.agent-evidence-focus select').value).toBe('agent-evidence:c2');
  expect(w.renderStoredConsensusClaims).toHaveBeenCalledTimes(1);
  dom.window.close();
});
