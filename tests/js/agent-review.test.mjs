import { expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";
import { marked } from 'marked';
import DOMPurify from 'dompurify';

function setup() {
  return loadScripts(["static/js/agent-review.js"], { body: '<section><div id="answer"></div></section>', before(w) {
    w.injectMarkdown = vi.fn((el, text) => { el.textContent = text; });
    w.renderStoredConsensusClaims = vi.fn(); w.renderStoredDifferenceCards = vi.fn(); w.renderStoredAuditMarks = vi.fn();
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
  // Activity renders before the answer's reader contexts are registered.
  w.App.agentReview.renderActivity(details, review, body.dataset.markdown);
  w.App.agentReview.render(body, review);
  expect(details.hidden).toBe(false);
  expect(details.textContent).toContain('Comparison 1 · 1 model answer');
  expect(details.textContent).toContain('Models: GPT');
  expect(details.textContent).toContain('Disagreement: Whether five seats are included');
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
it('marks pages read for an answer without a comparison in its sources', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer');
  body.dataset.markdown = 'The winner finished in 7:47:27.';
  const review = {status: 'direct', comparisons: [], versions: [],
    read_sources: [{url: 'https://www.tri247.com/live', status: 'completed'}]};
  w.App.agentReview.render(body, review, {sources: [{url: 'https://www.tri247.com/live', title: 'Live'}], key: 't1', question: 'Q'});
  const button = d.querySelector('.agent-evidence-link');
  expect(button).not.toBeNull();
  button.click();
  const panel = w.App.answerReader.openContext.mock.calls.at(-1)[0].renderPanel();
  expect(panel.textContent).toContain('Read by the agent');
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
  expect(host.textContent).not.toContain('Checked ·');
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
  expect(details.textContent).toContain('The answer check couldn’t compare each sentence');
  w.App.agentReview.renderActivity(details, review, 'Changed answer.');
  expect(details.textContent).toContain('Answer check pending');
  expect(details.textContent).not.toContain('A recorded disagreement');
  expect(details.textContent).not.toContain('Checked ·');
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
  expect(d.querySelector(".agent-review-status").textContent).toContain("Answer check pending");
  expect(w.injectMarkdown).toHaveBeenLastCalledWith(body, "Changed answer.", []);
  dom.window.close();
});
it('ignores the contradiction source check that older saved turns still carry', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = snapshot(); review.check_sources = true;
  review.checks[0].differences_data.differences = [{type: 'contradiction', claim: 'Start times differ'}];
  review.checks[0].source_verification = {answer_version: 'answer-hash', run_id: 'c1', basis_hash: 'b1', status: 'partial',
    job_id: 'job-1', check_type: 'contradiction_evidence',
    scope: {checked_contradictions: 0, contradictions: 0, detected_contradictions: 1, excluded_contradictions: 1}};
  const details = d.createElement('div');
  w.App.agentReview.renderActivity(details, review, body.dataset.markdown);
  expect(details.textContent).toContain('Disagreement: Start times differ');
  expect(details.textContent).not.toMatch(/source check/i);
  w.App.agentReview.render(body, review);
  const link = d.querySelector('[data-section="differences"]');
  expect(link.getAttribute('aria-label')).toBe('Contradictions 1');
  expect(d.querySelector('.agent-review-status').textContent).toBe('');
  link.click();
  const panel = w.App.answerReader.openContext.mock.calls.at(-1)[0].renderPanel('differences');
  expect(panel.querySelector('.agent-source-check')).toBeNull();
  expect(panel.textContent).not.toMatch(/source check/i);
  expect(panel.querySelector('.agent-evidence-footer').childElementCount).toBe(0);
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
it('marks the sources the agent read itself, only when the read completed', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = snapshot();
  review.comparisons[0].answers[0].sources = [{url: 'https://example.org/report', title: 'Report'},
    {url: 'https://example.org/missing', title: 'Missing'},
    // Another spelling of the read page, and the Google redirect it was cited by.
    {url: 'http://Example.org/report/', title: 'Report again'},
    {url: 'https://vertexaisearch.cloud.google.com/grounding-api-redirect/x', title: 'gov.example'}];
  review.read_sources = [{url: 'https://example.org/report#top', status: 'completed'},
    {url: 'https://example.org/missing', status: 'failed'}, {url: 'javascript:bad()', status: 'completed'},
    {url: 'https://gov.example/page', cited_url: 'https://vertexaisearch.cloud.google.com/grounding-api-redirect/x', status: 'completed'}];
  w.App.agentReview.render(body, review);
  d.querySelector('[data-section="sources"]').click();
  const items = [...w.App.answerReader.openContext.mock.calls[0][0].renderPanel('sources').querySelectorAll('li')];
  const marked = items.filter(li => li.querySelector('.agent-source-read')).map(li => li.querySelector('a').href);
  expect(marked).toEqual(['https://example.org/report', 'http://example.org/report/',
    'https://vertexaisearch.cloud.google.com/grounding-api-redirect/x']);
  expect(items.find(li => li.querySelector('.agent-source-read')).textContent).toContain('Read by the agent');
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
  expect(d.body.textContent).toContain("Answer check pending");
  const select = d.querySelector('[aria-label="Comparison basis"]');
  select.value = 'agent-evidence:c2'; select.dispatchEvent(new w.Event('change'));
  expect(w.renderStoredConsensusClaims).toHaveBeenCalledTimes(1);
  w.injectMarkdown.mockClear();
  select.value = 'agent-evidence:c1'; select.dispatchEvent(new w.Event('change'));
  expect(w.injectMarkdown).toHaveBeenCalledWith(body, "Exact answer.", []);
  expect(w.renderStoredConsensusClaims).toHaveBeenCalledTimes(1);
  review.status = "succeeded";
  w.App.agentReview.render(body, review);
  expect(d.querySelector(".agent-review-status").textContent).toContain("Answer check pending");
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
    expect(status.querySelector('summary').textContent).toBe('1 of 2 models answered');
    expect(status.querySelector('.agent-evidence-status-detail').textContent).toBe('GPT Luna: no answer, the provider was busy.');
    expect(panel.firstElementChild).toBe(status);
    expect(panel.querySelectorAll(':scope > p.agent-review-note')).toHaveLength(0);
    expect(panel.textContent).not.toContain('Checked ·');
    expect(context.answers.at(-1).error).toContain('the provider was busy');
  }
  dom.window.close();
});
it('writes the status line in the page language, one part at a time', () => {
  const {window: w, document: d, dom} = setup();
  // The joined line has no dictionary entry; its parts do (docs/i18n.md).
  const german = {'1 of 2 models answered': '1 von 2 Modellen haben geantwortet', 'Partly checked': 'Teilweise geprüft'};
  w.App.t = text => german[text] ?? text;
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = partialReview(); delete review.checks[0].differences_data.judges.coverage;
  w.App.agentReview.render(body, review);
  d.querySelector('[data-section="differences"]').click();
  const panel = w.App.answerReader.openContext.mock.calls.at(-1)[0].renderPanel('differences');
  expect(panel.querySelector('.agent-evidence-status summary').textContent)
    .toBe('1 von 2 Modellen haben geantwortet · Teilweise geprüft');
  dom.window.close();
});
it.each([
  ['coverage', 'The answer check couldn’t compare each sentence', 'Partly checked'],
  ['sentences', '2 sentences could not be checked', '']
])('keeps %s failures distinct from unavailable comparison models', (kind, reason, line) => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = partialReview(); const check = review.checks[0];
  if (kind === 'coverage') delete check.differences_data.judges.coverage;
  if (kind === 'sentences') check.differences_data.judges.coverage.missing = 2;
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
it('opens a fully answered, finished check on its findings, without a status line', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = snapshot();
  w.App.agentReview.render(body, review);
  d.querySelector('[data-section="differences"]').click();
  const panel = w.App.answerReader.openContext.mock.calls.at(-1)[0].renderPanel('differences');
  // "1 model answered · Checked" said nothing the findings don't (Max 2026-10-23).
  expect(panel.querySelector('.agent-evidence-status')).toBeNull();
  expect(panel.textContent).not.toContain('Checked');
  const order = [...panel.children].map(child => child.className);
  expect(order).toEqual(['agent-evidence-differences', 'agent-evidence-footer']);
  const footer = panel.querySelector('.agent-evidence-footer');
  // No standing disclaimers or context toggle: the footer stays empty.
  expect(footer.textContent).not.toContain('Model agreement is not independent fact checking.');
  expect(footer.querySelector('.agent-evidence-context')).toBeNull();
  expect(footer.childElementCount).toBe(0);
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
  expect(panel.textContent).toContain('GPT Luna: stopped before it finished, it was still writing when the answer was finished.');
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
  // (a repaint with reveal: false).
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

// Provisional marks: Coverage windows that are done while Differences still runs.
function previewSetup() {
  const setupResult = setup();
  const {window: w, document: d} = setupResult;
  const body = d.getElementById('answer');
  body.dataset.markdown = 'Exact answer.';
  w.matchMedia = () => ({ matches: false });
  // The real marker sets one span per anchored claim and a badge behind it;
  // provisional marks are one neutral span each (consensus-insights.js).
  w.renderStoredConsensusClaims = vi.fn((el, data, _fallback, _sources, options = {}) => {
    el.innerHTML = data.claims.map(c => options.provisional ? `<span class="cx-claim is-provisional">${c.anchor}</span>`
      : `<span class="cx-claim is-${c.major ? 'major' : c.coverage === 'split' ? 'split' : 'unanimous'}">${c.anchor}</span>`
      + ' <span class="claim-badge">2/2</span>').join(' ');
  });
  const running = { ...snapshot(), status: 'running' };
  delete running.checks;
  return { ...setupResult, body, running };
}
const claim = (anchor, extra = {}) => ({ anchor, agree: ['GPT'], dissent: [], coverage: 'supported', ...extra });
it('marks the exact answer quietly with the Coverage windows that are done, and takes the marks off without a check', () => {
  const {window: w, dom, body, running} = previewSetup();
  const previews = { c1: { answer_hash: 'answer-hash', comparison_id: 'c1', claims: [claim('One.')], models_compared: ['GPT'] } };
  w.App.agentReview.preview(body, running, previews);
  // Coverage only: no contradictions, no "Key claims" list, no score row,
  // and neutral marks without a verdict (provisional).
  const [marked, data, fallback, sources, options] = w.renderStoredConsensusClaims.mock.lastCall;
  expect(marked).toBe(body);
  expect(JSON.parse(JSON.stringify(data))).toEqual({ claims: [claim('One.')], differences: [], models_compared: ['GPT'] });
  expect(fallback.isConnected).toBe(false);
  expect(Array.isArray(sources)).toBe(true);
  expect(options.provisional).toBe(true);
  expect(body._agentReview).toBeUndefined();
  expect(body.classList.contains('has-provisional-marks')).toBe(true);
  // No marker stroke: the neutral line fades in once.
  expect(body.classList.contains('is-marks-revealing')).toBe(false);
  expect([...body.querySelectorAll('.cx-claim')].every(el => el.classList.contains('is-mark-arriving'))).toBe(true);
  // An unchanged preview keeps the DOM (the page projects every 100 ms).
  const first = body.querySelector('.cx-claim');
  w.App.agentReview.preview(body, structuredClone(running), structuredClone(previews));
  expect(body.querySelector('.cx-claim')).toBe(first);
  // The next window: what the reader saw stays still, only the new mark fades in.
  previews.c1 = { ...previews.c1, claims: [claim('One.'), claim('Two.', { coverage: 'split' })] };
  w.App.agentReview.preview(body, running, previews);
  const [one, two] = body.querySelectorAll('.cx-claim');
  expect(one.classList.contains('is-mark-arriving')).toBe(false);
  expect(two.classList.contains('is-mark-arriving')).toBe(true);
  // A preview of another answer, another text on the page, a finished or
  // stopped review, or no review: the marks come off, and only once.
  for (const [review, list, raw] of [[running, { c1: { ...previews.c1, answer_hash: 'other-hash' } }, 'Exact answer.'],
    [running, previews, 'Changed answer.'], [{ ...running, status: 'cancelled' }, previews, 'Exact answer.'],
    [running, { c2: previews.c1 }, 'Exact answer.'], [null, previews, 'Exact answer.']]) {
    w.App.agentReview.preview(body, running, previews);
    expect(body.querySelectorAll('.cx-claim')).toHaveLength(2);
    body.dataset.markdown = raw;
    w.injectMarkdown.mockClear();
    w.App.agentReview.preview(body, review, list);
    expect(body.querySelectorAll('.cx-claim')).toHaveLength(0);
    expect(body.classList.contains('has-provisional-marks')).toBe(false);
    w.App.agentReview.preview(body, review, list);
    expect(w.injectMarkdown).toHaveBeenCalledTimes(1);
    body.dataset.markdown = 'Exact answer.';
  }
  dom.window.close();
});
it('hands the provisional lines over to the final marks in the same frame, each until its colour strokes on', () => {
  vi.useFakeTimers();
  const {window: w, dom, body, running} = previewSetup();
  w.performance.now = () => 1000;
  w.App.agentReview.preview(body, running, { c1: { answer_hash: 'answer-hash', comparison_id: 'c1',
    claims: [claim('One.'), claim('Two.')], models_compared: ['GPT'] } });
  expect(body.querySelectorAll('.cx-claim.is-provisional')).toHaveLength(2);
  const review = snapshot();
  // Two. turned out to be contested, Three. was checked last.
  review.checks[0].differences_data.claims = [claim('One.'), claim('Two.', { major: true }), claim('Three.')];
  w.App.agentReview.render(body, review, { reveal: true });
  // No moment without marks: the final ones stand in place of the provisional ones.
  expect(body.classList.contains('has-provisional-marks')).toBe(false);
  expect(body.querySelectorAll('.cx-claim.is-provisional')).toHaveLength(0);
  expect(body.classList.contains('is-marks-revealing')).toBe(true);
  const [one, two, three] = body.querySelectorAll('.cx-claim');
  const delay = el => el.style.getPropertyValue('--cx-reveal-delay');
  // The provisional marks had no colour: every coloured mark strokes on, in
  // reading order, and the sentences that had a line keep it until then.
  expect(delay(one)).toBe('0ms');
  expect(parseInt(delay(two))).toBeGreaterThan(0);
  expect(parseInt(delay(three))).toBeGreaterThan(parseInt(delay(two)));
  expect([one, two, three].map(el => el.classList.contains('was-provisional'))).toEqual([true, true, false]);
  vi.runAllTimers();
  // The hand-over leaves no trace.
  expect(body.classList.contains('is-marks-revealing')).toBe(false);
  expect(body.querySelectorAll('.was-provisional')).toHaveLength(0);
  // Without a reveal (reduced motion) the colours stand at once, the lines go.
  w.matchMedia = () => ({ matches: true });
  const same = snapshot();
  same.answer_hash = same.versions[0].hash = 'same-hash';
  same.checks.forEach(c => { c.answer_hash = 'same-hash'; });
  same.checks[0].differences_data.claims = [claim('One.')];
  w.App.agentReview.preview(body, { ...running, answer_hash: 'same-hash', versions: same.versions },
    { c1: { answer_hash: 'same-hash', comparison_id: 'c1', claims: [claim('One.')], models_compared: ['GPT'] } });
  w.App.agentReview.render(body, same, { reveal: true });
  expect(body.querySelector('.cx-claim').className).toBe('cx-claim is-unanimous was-provisional');
  expect(body.classList.contains('is-marks-revealing')).toBe(false);
  vi.runAllTimers();
  expect(body.querySelectorAll('.was-provisional')).toHaveLength(0);
  vi.useRealTimers();
  dom.window.close();
});

// Marks are laid over the text on screen (Apple audit A6): the real
// Markdown renderer, and a marker that wraps its anchor where it stands.
it('keeps the text, and a selection in it, while provisional and final marks arrive', () => {
  const text = 'The first paragraph stays plain.\n\nThe tower is 330 m tall. A ticket costs 29 euros.';
  const { window: w, document: d, dom } = loadScripts([
    "static/vendor/marked/12.0.2/marked.min.js", "static/vendor/dompurify/3.4.17/dist/purify.min.js",
    "static/js/markdown-stream.js", "static/js/agent-review.js"], { body: '<section><div id="answer"></div></section>', before(win) {
    win.App = { answerReader: { openContext: vi.fn(), refreshContext: vi.fn() } };
    win.renderStoredDifferenceCards = vi.fn();
  }});
  w.matchMedia = () => ({ matches: false });
  w.renderStoredConsensusClaims = vi.fn((el, data) => {
    for (const claim of data.claims) {
      const walker = d.createTreeWalker(el, w.NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        const at = node.nodeValue.indexOf(claim.anchor);
        if (at < 0 || node.parentElement.closest('.cx-claim')) continue;
        const words = node.splitText(at); words.splitText(claim.anchor.length);
        const span = d.createElement('span'); span.className = 'cx-claim is-unanimous';
        words.replaceWith(span); span.append(words);
        const badge = d.createElement('button'); badge.className = 'claim-badge'; badge.textContent = '2/2'; span.after(badge);
        break;
      }
    }
  });
  const body = d.getElementById('answer');
  body.dataset.markdown = text;
  w.renderMarkdownStream(body, text);
  const [first, second] = body.querySelectorAll('p');
  const plain = first.firstChild;
  const selection = w.getSelection();
  selection.setBaseAndExtent(second.firstChild, 4, second.firstChild, 16);
  const chosen = selection.toString();
  expect(chosen).toBe('tower is 330');
  const version = { id: 1, text, hash: 'h' };
  const running = { ...snapshot(), status: 'running', answer_hash: 'h', versions: [version] };
  delete running.checks;
  w.App.agentReview.preview(body, running, { c1: { answer_hash: 'h', comparison_id: 'c1',
    claims: [claim('A ticket costs 29 euros.')], models_compared: ['GPT'] } });
  expect(body.querySelectorAll('.cx-claim')).toHaveLength(1);
  expect(body.querySelector('p')).toBe(first);
  expect(plain.isConnected).toBe(true);
  expect(selection.toString()).toBe(chosen);
  // The final review replaces the provisional marks in the same text.
  const review = { ...snapshot(), answer_hash: 'h', versions: [version] };
  review.checks.forEach(check => { check.answer_hash = 'h'; check.differences_data.claims = [claim('The tower is 330 m tall.')]; });
  w.App.agentReview.render(body, review);
  expect([...body.querySelectorAll('.cx-claim')].map(el => el.textContent)).toEqual(['The tower is 330 m tall.']);
  expect(body.querySelector('p')).toBe(first);
  expect(plain.isConnected).toBe(true);
  expect(selection.toString()).toBe(chosen);
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
    differences_data: null, issues: [], skipped: 'passage_checked' }];
  review.passage_check = { status: 'succeeded', comparison_id: 'c1', text: 'Pasted.', claims: [] };
  const details = d.createElement('div');
  w.App.agentReview.renderActivity(details, review, body.dataset.markdown);
  w.App.agentReview.render(body, review);
  const note = 'Your text was checked sentence by sentence; the result is shown above the answer.';
  expect(details.querySelector('.agent-activity-check').textContent).toBe(note);
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
it('offers no Sources link when the answer has no source', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = snapshot();
  for (const comparison of review.comparisons) for (const answer of comparison.answers) delete answer.sources;
  w.App.agentReview.render(body, review);
  expect([...body._agentReview.querySelectorAll('[data-section]')].map(b => b.dataset.section)).toEqual(['differences', 'answers']);
  dom.window.close();
});
it('puts the inline model row of an earlier turn beside its "Thought for" line', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  body.classList.add('thread-history-answer-body');
  const activity = d.createElement('div');
  activity.innerHTML = '<details class="agent-activity"><summary><span class="agent-activity-title">Thought for 29s</span></summary></details>';
  body.before(activity);
  const toggled = vi.fn(); activity.querySelector('summary').addEventListener('click', toggled);
  w.App.agentReview.render(body, snapshot());
  const models = activity.querySelector('summary > .agent-history-models');
  expect(models).not.toBeNull();
  expect(models.tagName).toBe('SPAN');
  expect(body.previousElementSibling).toBe(activity);
  // A mark opens its answer; the activity stays as it is.
  models.querySelector('button').click();
  expect(toggled).not.toHaveBeenCalled();
  // A second render keeps one row.
  w.App.agentReview.render(body, { ...snapshot(), status: 'succeeded' });
  expect(activity.querySelectorAll('.agent-history-models').length).toBe(1);
  dom.window.close();
});
it('says calmly that the answer check is off and offers answers and sources, no review', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = snapshot();
  review.status = 'off';
  review.versions[0].status = 'off';
  review.checks = review.checks.map(check => ({ ...check, status: 'off', differences_data: null }));
  // A model without an answer is listed, but no check "uses the remaining answers".
  review.comparisons[0].failed_models = [{ label: 'Claude', model: 'anthropic/claude', failure: { code: 'provider_timeout' } }];
  const details = d.createElement('div');
  w.App.agentReview.renderActivity(details, review, body.dataset.markdown);
  w.App.agentReview.render(body, review);
  // No line under the answer: the reader switched the check off and the
  // activity says so; "off" under every answer read like a warning.
  const status = body._agentReview.querySelector('.agent-review-status');
  expect(status.dataset.state).toBe('off');
  expect(status.textContent).toBe('');
  expect(status.hidden).toBe(true);
  expect(status.title).not.toMatch(/the check uses/);
  const panel = w.App.agentReview.contextFor(review, 'c1').renderPanel('answers');
  expect(panel.textContent).toContain('Claude: no answer, the provider stopped responding.');
  expect(panel.textContent).not.toMatch(/the check uses|could not/);
  // No marks, no score, no review tab: only answers and sources.
  expect(w.renderStoredConsensusClaims).not.toHaveBeenCalled();
  expect(body._agentReview.querySelector('.agent-agreement')).toBeNull();
  expect([...body._agentReview.querySelectorAll('[data-section]')].map(b => b.dataset.section)).toEqual(['answers', 'sources']);
  const context = w.App.agentReview.contextFor(review, 'c1');
  expect(context.sections).toEqual(['answers', 'sources']);
  expect(details.querySelector('.agent-activity-check').textContent).toBe('Answer check off');
  expect(details.textContent).not.toMatch(/could not|Partly checked|pending/);
  expect([...details.querySelectorAll('.agent-activity-insight-actions button')].map(b => b.textContent))
    .toEqual(['Read model answers', 'Explore sources', 'Read model answers', 'Explore sources']);
  // A run that failed after the answer was fixed needs no note: nothing was left unchecked by accident.
  expect(w.App.agentReview.failureNote({error: 'failed'}, review, 'Exact answer.')).toBe('');
  dom.window.close();
});
it('keeps the comparison cards and their buttons while the answer streams and model answers grow', () => {
  // Rebuilding them on every 100-ms tick swallowed clicks (Apple audit D7).
  const {window: w, document: d, dom} = setup();
  const details = d.createElement('div');
  const review = snapshot();
  w.App.agentReview.renderActivity(details, review, 'Exact');
  const card = details.querySelector('.agent-activity-insight');
  const button = details.querySelector('button');
  const grown = structuredClone(review);
  grown.comparisons[0].answers[0].text += ' And a few more words.';
  grown.checks[0].differences_data.claims.push({ anchor: 'another claim' });
  w.App.agentReview.renderActivity(details, grown, 'Exact answer');
  expect(details.querySelector('.agent-activity-insight')).toBe(card);
  expect(details.querySelector('button')).toBe(button);
  // A click still opens the newest review's evidence.
  const body = d.getElementById('answer');
  body.dataset.markdown = 'Exact answer';
  w.App.agentReview.render(body, grown);
  button.click();
  expect(w.App.answerReader.openContext).toHaveBeenLastCalledWith(expect.objectContaining({key:'agent-evidence:c1'}),
    expect.objectContaining({section:'answers'}));
  // What the cards say rebuilds them: the answer reaching its checked version,
  // a comparison that runs again.
  w.App.agentReview.renderActivity(details, grown, 'Exact answer.');
  expect(details.querySelector('.agent-activity-insight')).not.toBe(card);
  const running = structuredClone(grown);
  running.comparisons[1].status = 'running';
  w.App.agentReview.renderActivity(details, running, 'Exact answer.');
  expect(details.textContent).toContain('Comparison 2 · Collecting answers…');
  dom.window.close();
});
it('parses each answer text for its links once, not on every render', () => {
  // Opening a chat ran marked and DOMPurify over every model answer again
  // for each render and review update (Apple audit D5).
  const {window: w, document: d, dom} = setup();
  const parse = vi.fn(text => marked.parse(text));
  w.marked = { parse };
  const body = d.getElementById('answer');
  body.dataset.markdown = 'Exact answer.';
  const review = snapshot();
  review.comparisons[0].answers[0].text = 'See [the report](https://example.org/report).';
  w.App.agentReview.render(body, review);
  const texts = parse.mock.calls.map(([text]) => text);
  expect(texts.length).toBe(new Set(texts).size);
  w.App.agentReview.render(body, structuredClone(review));
  expect(parse).toHaveBeenCalledTimes(texts.length);
  // The cached links are the same sources as before.
  const context = w.App.agentReview.contextFor(review, 'c1');
  expect(context.answers[0].sources.map(s => s.url)).toContain('https://example.org/report');
  dom.window.close();
});

// --- Audit instead of comparison (admins, since 2026-10-25) --------------------------
function auditReview(status = 'partial') {
  return { mode: 'audit', status, answer_version: 1, answer_hash: 'audit-hash', comparisons: [],
    versions: [{ id: 1, text: 'Exact answer.', hash: 'audit-hash', status, comparison_ids: [] }],
    audit: { reviewers: [
      { provider: 'openai', provider_label: 'OpenAI', model: { label: 'GPT', model: 'openai/gpt' }, status: 'completed', marks: 2 },
      { provider: 'anthropic', provider_label: 'Anthropic', model: { label: 'Claude' }, status: 'completed', marks: 0 },
      { provider: 'google', provider_label: 'Gemini', model: { label: 'Gemini' }, status: 'failed', failure: { code: 'review_unreadable' } }],
      claims: [{ anchor: 'Exact answer.', kind: 'wrong', audit: true, agree: [], dissent: [
        { model: 'OpenAI', kind: 'wrong', note: 'It is not exact.', source: 'https://example.org/proof', target: 'Exact' }] }],
      unplaced: [{ model: 'OpenAI', kind: 'incomplete', note: 'Missing context.', quote: 'Elsewhere' }],
      issues: [{ code: 'reviewers_unavailable', count: 1 }] } };
}
it('marks a reviewed answer with its reviewers\' notes, without a score or differences', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = auditReview();
  w.App.agentReview.render(body, review, { sources: [{ url: 'https://example.org', title: 'Source' }], question: 'Q', key: 't1' });
  expect(w.renderStoredAuditMarks).toHaveBeenCalledTimes(1);
  expect(w.renderStoredAuditMarks.mock.calls[0][1]).toBe(review.audit);
  expect(w.renderStoredConsensusClaims).not.toHaveBeenCalled();
  expect(w.renderStoredDifferenceCards).not.toHaveBeenCalled();
  expect(d.querySelector('.agent-agreement')).toBeNull();
  expect(d.querySelector('.agent-review-status').textContent).toBe('2 of 3 models reviewed the answer');
  const buttons = [...d.querySelectorAll('.agent-evidence-link')];
  expect(buttons.map(b => b.getAttribute('aria-label'))).toEqual(['Notes 2', 'Sources 1']);
  buttons[0].click();
  const [context, options] = w.App.answerReader.openContext.mock.calls.at(-1);
  expect(options.section).toBe('differences');
  expect(context.sections).toEqual(['differences', 'sources']);
  expect(context.labels).toEqual({ differences: 'Notes' });
  const panel = context.renderPanel('differences');
  expect(panel.textContent).toContain('Unmarked text means no objection, not confirmed.');
  expect(panel.textContent).toContain('It is not exact.');
  expect(panel.textContent).toContain('Missing context.');
  expect(panel.textContent).toContain('No objections.');
  expect(panel.textContent).toContain('No review: its review could not be read.');
  expect(panel.querySelector('a.agent-audit-source').href).toBe('https://example.org/proof');
  // Opening the notes from a mark's card leads to the same panel.
  w.renderStoredAuditMarks.mock.calls[0][4].openNotes();
  expect(w.App.answerReader.openContext.mock.calls.at(-1)[1].section).toBe('differences');
  dom.window.close();
});
it('names a reviewer that called a tool or replied empty, never as a provider failure', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = auditReview();
  review.audit.reviewers[1] = { ...review.audit.reviewers[1], status: 'failed', failure: { code: 'review_empty' } };
  review.audit.reviewers[2].failure = { code: 'review_tool_calls' };
  w.App.agentReview.render(body, review, { sources: [], question: 'Q', key: 't1' });
  d.querySelector('.agent-evidence-link').click();
  const panel = w.App.answerReader.openContext.mock.calls.at(-1)[0].renderPanel('differences');
  expect(panel.textContent).toContain('No review: its reply was empty.');
  expect(panel.textContent).toContain('No review: it called a tool instead of giving its review.');
  dom.window.close();
});
it('waits with the marks until every reviewer is done, and never marks another text', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  w.App.agentReview.render(body, auditReview('running'));
  expect(w.renderStoredAuditMarks).not.toHaveBeenCalled();
  expect(d.querySelector('.agent-review').hidden).toBe(true);
  body.dataset.markdown = 'Changed answer.';
  w.App.agentReview.render(body, auditReview('succeeded'));
  expect(w.renderStoredAuditMarks).not.toHaveBeenCalled();
  body.dataset.markdown = 'Exact answer.';
  w.App.agentReview.render(body, auditReview('succeeded'));
  expect(w.renderStoredAuditMarks).toHaveBeenCalledTimes(1);
  expect(d.querySelector('.agent-review-status').hidden).toBe(true);
  dom.window.close();
});
it('shows the review in the duration disclosure and opens its notes', () => {
  const {window: w, document: d, dom} = setup();
  const details = d.createElement('div');
  w.App.agentReview.renderActivity(details, auditReview('running'), 'Exact answer.');
  expect(details.textContent).toContain('Reviewing the answer…');
  // "Read the notes" holds its place, hidden and disabled, so the open
  // history does not grow under the arriving marks (2026-10-26).
  const reserved = details.querySelector('.agent-activity-insight-actions.is-reserved');
  expect(reserved.getAttribute('aria-hidden')).toBe('true');
  expect(reserved.querySelector('button').disabled).toBe(true);
  w.App.agentReview.renderActivity(details, auditReview(), 'Exact answer.');
  expect(details.querySelector('.is-reserved')).toBeNull();
  expect(details.textContent).toContain('Review · 3 models');
  expect(details.textContent).toContain('Models: GPT, Claude, Gemini');
  expect(details.textContent).toContain('No review: Gemini');
  expect(details.textContent).toContain('2 marked passages');
  details.querySelector('button').click();
  const [context, options] = w.App.answerReader.openContext.mock.calls.at(-1);
  expect(context.key).toBe('agent-audit:audit-hash');
  expect(options.section).toBe('differences');
  dom.window.close();
});
it('counts and lists a mark over several sentences once', () => {
  const {window: w, document: d, dom} = setup();
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = auditReview('succeeded');
  const note = { model: 'OpenAI', kind: 'doubtful', note: 'Both sentences.', mark: 7 };
  review.audit.claims = [
    { anchor: 'First one.', kind: 'doubtful', audit: true, agree: [], dissent: [{ ...note, target: 'First one.' }] },
    { anchor: 'Second one.', kind: 'doubtful', audit: true, agree: [], dissent: [{ ...note, target: 'Second' }] }];
  review.audit.unplaced = [];
  w.App.agentReview.render(body, review);
  const buttons = [...d.querySelectorAll('.agent-evidence-link')];
  expect(buttons[0].getAttribute('aria-label')).toBe('Notes 1');
  buttons[0].click();
  const panel = w.App.answerReader.openContext.mock.calls.at(-1)[0].renderPanel('differences');
  expect([...panel.querySelectorAll('.agent-audit-note')].map(n => n.querySelector('q').textContent)).toEqual(['First one. Second']);
  const details = d.createElement('div');
  w.App.agentReview.renderActivity(details, review, 'Exact answer.');
  expect(details.textContent).toContain('1 marked passage');
  dom.window.close();
});
it('lists the notes on the work with their log entry, also those of a failed final round', () => {
  const {window: w, document: d, dom} = setup();
  w.App.agentWorkLog = { KINDS: { step: 'Step', tool: 'Tool' } };
  const body = d.getElementById('answer'); body.dataset.markdown = 'Exact answer.';
  const review = auditReview();
  review.audit.process = [
    { model: 'OpenAI', kind: 'doubtful', note: 'The lookup names no source.', entry: 9, entry_kind: 'tool',
      entry_name: 'read_source', mark: 3 },
    { model: 'Gemini', kind: 'wrong', note: 'The step skipped the file.', entry: 4, entry_kind: 'step',
      entry_name: 'openai/gpt', mark: 4, live: true }];
  w.App.agentReview.render(body, review);
  const buttons = [...d.querySelectorAll('.agent-evidence-link')];
  expect(buttons[0].getAttribute('aria-label')).toBe('Notes 4');
  buttons[0].click();
  const panel = w.App.answerReader.openContext.mock.calls.at(-1)[0].renderPanel('differences');
  const [openai, , gemini] = panel.querySelectorAll('.agent-audit-reviewer');
  expect(openai.querySelector('.agent-audit-work-head').textContent).toBe('On the work');
  const work = openai.querySelectorAll('.agent-audit-notes')[1];
  // The step in the activity's words; the log's number and name for admins only.
  w.App.agentActivity = { toolName: name => ({ read_source: 'Read source' })[name] || 'Tool' };
  const again = w.App.answerReader.openContext.mock.calls.at(-1)[0].renderPanel('differences');
  const entry = again.querySelectorAll('.agent-audit-reviewer')[0].querySelectorAll('.agent-audit-notes')[1]
    .querySelector('.agent-audit-entry');
  expect([...entry.children].map(el => [el.textContent, el.classList.contains('admin-only')])).toEqual([
    ['Read source', false], ['#9', true], ['read_source', true]]);
  // Without the activity's words, the log's kind names it.
  expect(work.querySelector('.agent-audit-entry').firstChild.textContent).toBe('Tool');
  expect(work.textContent).toContain('The lookup names no source.');
  // Its final round failed: its notes from the run stand, marked as such.
  expect(gemini.textContent).toContain('No final review: its review could not be read.');
  expect(gemini.querySelector('.agent-audit-entry').firstChild.textContent).toBe('Agent step');
  expect(gemini.querySelector('.agent-audit-live').textContent).toBe('During the run');
  expect(gemini.textContent).toContain('The step skipped the file.');
  const details = d.createElement('div');
  w.App.agentReview.renderActivity(details, review, 'Exact answer.');
  expect(details.querySelector('.agent-activity-check').textContent).toBe('2 marked passages · 2 notes on the work');
  dom.window.close();
});
it('ends the review in the disclosure when it was stopped or never started, and keeps the answer complete', () => {
  const {window: w, document: d, dom} = setup();
  for (const [status, text] of [['cancelled', 'Review stopped'], ['missing', 'Not reviewed']]) {
    const details = d.createElement('div');
    w.App.agentReview.renderActivity(details, auditReview(status), 'Exact answer.');
    expect(details.textContent).toContain(text);
    expect(details.textContent).not.toContain('Waiting for the reviews.');
    expect(details.textContent).not.toContain('Reviewing the answer…');
    // The reviewers start only once the answer is written: it is complete.
    expect(w.App.agentReview.failureNote({ error: 'stopped' }, auditReview(status), 'Exact answer.')).toBe('');
  }
  expect(w.App.agentReview.failureNote({ error: 'stopped' }, auditReview('running'), 'Exact answer.')).not.toBe('');
  dom.window.close();
});
