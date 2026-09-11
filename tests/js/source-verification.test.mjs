import { describe, it, expect, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";
function boot() {
  const env = loadScripts(["static/js/consensus-anchor.js", "static/js/source-verification.js"]);
  env.document.body.innerHTML = `<div id="consensusAnswerBody"><p><span class="cx-claim">The plan costs 20 euros.</span> <a class="src-ref" data-source-number="1" title="Original source" href="#src-1">1</a><a class="src-ref" data-source-number="2" href="#src-2">2</a> Another sentence. <a class="src-ref" data-source-number="1" href="#src-1">1</a></p></div><div class="diff-card">Original difference</div><button id="consensusSourcesTab"><span class="consensus-tab-label">Verify sources</span></button><span id="consensusSourceCheckStatus"></span><div hidden><div id="sourceVerificationReport"></div></div>`;
  return { ...env, body: env.document.getElementById("consensusAnswerBody"), report: env.document.getElementById("sourceVerificationReport") };
}
const finding = { sentence_id: 1, source_id: "S1", claim: "The plan costs 20 euros.",
  anchor_occurrence: 0, checked: true, topical: "off_topic", temporal: "unknown",
  reason: "Only for students.", quotes: ["20 euros for students."] };
const result = { status: "complete", scope: { checked_pairs: 2, pairs: 2 },
  findings: [finding, { ...finding, source_id: "S2", topical: "relevant", temporal: "suitable" }],
  documents: [{ source_id: "S1", source_url: "https://example.com", title: "Prices" }] };

describe("independent source verification", () => {
  it('keeps the compact Sources verdict honest across result and run changes', () => {
    const {window, document} = boot();
    const good = {...finding, support: 'supported', topical: 'relevant', temporal: 'suitable'};
    const clean = {schema_version: 3, status: 'complete', findings: [good], scope: {pairs: 1, checked_pairs: 1}};
    const tab = document.getElementById('consensusSourcesTab');
    const cases = [
      [clean, 'supported', '✓'],
      [{...clean, status: 'running'}, 'pending', ''],
      [{...clean, findings: [{...good, support: 'partial'}]}, 'issue', '!'],
      [{...clean, findings: [{...good, support: 'unknown'}]}, 'unknown', '?'],
      [{...clean, status: 'partial', scope: {pairs: 17, checked_pairs: 2}}, 'unknown', '?'],
      [{...clean, findings: [], scope: {pairs: 1, checked_pairs: 1}}, 'unknown', '?'],
      [{...clean, schema_version: 2}, 'unknown', '?'],
      [{...clean, status: 'failed'}, 'unknown', '?'],
      [{...clean, status: 'awaiting_credentials'}, 'unknown', '?'],
      [{...clean, findings: [], scope: {pairs: 0, checked_pairs: 0}}, 'unknown', '?'],
      [{...clean, status: 'skipped'}, '', ''],
      [null, '', ''],
    ];
    for (const [snapshot, state, icon] of cases) {
      window.App.sourceVerification.renderCurrent(snapshot);
      expect(tab.dataset.checkState).toBe(state);
      expect(tab.querySelectorAll('.consensus-source-check-icon')).toHaveLength(1);
      expect(tab.querySelector('.consensus-source-check-icon').textContent).toBe(icon);
      expect(tab.querySelector('.consensus-source-check-icon').getAttribute('aria-hidden')).toBe('true');
    }
    expect(tab.title).toBe('View sources');
  });
  it('keeps overview diagnostics and full statements secondary while every source verdict stays visible', () => {
    const {window, report} = boot();
    const snapshot = {...result, schema_version: 3, status: 'partial', findings: [
      {...finding, support: 'partial'}, {...finding, source_id: 'S2', checked: false, reason_code: 'evidence_mismatch', reason: ''}
    ]};
    window.App.sourceVerification.renderCurrent(snapshot);
    expect(report.querySelector('.source-check-diagnostics').open).toBe(false);
    expect(report.querySelector('.source-check-failure-summary').closest('details')).toBe(report.querySelector('.source-check-diagnostics'));
    expect(report.textContent).toContain('Evidence quotes could not be verified');
    const statement = report.querySelector('.source-check-statement');
    expect(statement.open).toBe(false);
    expect(statement.querySelector('.source-check-claim').textContent).toBe(finding.claim);
    expect(report.querySelectorAll('.source-check-row')).toHaveLength(2);
    report.querySelectorAll('.source-check-row').forEach(row => {
      expect(row.open).toBe(false);
      expect(row.querySelectorAll('.source-check-row-summary .source-check-badge')).toHaveLength(1);
      expect(row.querySelector('.source-check-reference')).not.toBeNull();
    });
    statement.open = true; statement.querySelector('summary').focus();
    window.App.sourceVerification.renderCurrent(snapshot);
    expect(report.querySelector('.source-check-statement').open).toBe(true);
    expect(window.document.activeElement).toBe(report.querySelector('.source-check-statement > summary'));
  });
  it('never presents a single green verdict when topic or time has a problem', () => {
    const {window, report} = boot();
    window.App.sourceVerification.renderCurrent({...result, schema_version: 3, findings: [{...finding, support: 'supported'}]});
    const badge = report.querySelector('.source-check-row-summary .source-check-badge');
    expect(badge.textContent).toBe('Off topic');
    expect(badge.classList.contains('is-match')).toBe(false);
    expect(report.querySelector('.source-check-detail').textContent).toContain('Time unclear');
  });
  it('highlights the exact citation destination, survives updates, retriggers and clears without leaking to another run', () => {
    const {window, body, report} = boot();
    const timers = [];
    vi.spyOn(window, 'setTimeout').mockImplementation((callback, delay) => { timers.push({callback, delay}); return timers.length; });
    const cancel = vi.spyOn(window, 'clearTimeout');
    const scroll = vi.fn(); window.HTMLElement.prototype.scrollIntoView = scroll;
    const snapshot = {...result, schema_version: 3, job_id: 'run-a', findings: [
      {...finding, support: 'partial'}, {...finding, sentence_id: 2, claim: 'Another sentence.', support: 'supported'}
    ]};
    window.App.sourceVerification.renderCurrent(snapshot);
    body.querySelector('.src-ref').click();
    expect(report.querySelector('.source-check-navigation-target').dataset.pair).toBe('1:S1');
    expect(report.querySelector('.source-check-navigation-target').open).toBe(true);
    expect(scroll.mock.instances[0]).toBe(report.querySelector('.source-check-row > summary'));
    expect(timers[0].delay).toBe(2400);
    window.App.sourceVerification.renderCurrent({...snapshot});
    expect(report.querySelector('.source-check-navigation-target').dataset.pair).toBe('1:S1');
    body.querySelectorAll('.src-ref')[2].click();
    expect(cancel).toHaveBeenCalledWith(1);
    expect(report.querySelectorAll('.source-check-navigation-target')).toHaveLength(1);
    expect(report.querySelector('.source-check-navigation-target').dataset.pair).toBe('2:S1');
    timers[1].callback();
    expect(report.querySelector('.source-check-navigation-target')).toBeNull();
    body.querySelector('.src-ref').click();
    window.App.sourceVerification.renderCurrent({...snapshot, job_id: 'run-b'});
    expect(report.querySelector('.source-check-navigation-target')).toBeNull();
    body.querySelector('.src-ref').click();
    window.App.sourceVerification.clear(body, report);
    window.App.sourceVerification.renderCurrent({...snapshot, job_id: 'run-b'});
    expect(report.querySelector('.source-check-navigation-target')).toBeNull();
  });
  it('shows real support, original passages, checked time and bound model evidence without a success tick', () => {
    const {window, report, document} = boot();
    window.App.sourceVerification.renderCurrent({...result, schema_version: 3, findings: [{...finding,
      topical: 'relevant', temporal: 'suitable', support: 'contradicted', checked_at: '2026-09-09T10:00:00Z'}]},
      {differencesData: {claims: [{sentence_id: 1, agree: ['openai', 'gemini'], dissent: [{model: 'anthropic'}]}]}});
    expect(report.textContent).toContain('Statement contradicted');
    expect(report.textContent).toContain('Original source passage');
    expect(report.textContent).toContain('Models: 2 agree · 1 dissent');
    expect(report.querySelector('time').dateTime).toBe('2026-09-09T10:00:00.000Z');
    expect(document.querySelector('.source-check-status-reviewed')).toBeNull();
    expect(report.querySelector('.source-check-done')).toBeNull();
  });
  it('identifies a document cited by multiple providers as shared evidence', () => {
    const {window, report} = boot();
    window.App.sourceVerification.renderCurrent({...result, schema_version: 3,
      sources: [{id: 'S1', providers: ['OpenAI', 'Gemini', 'OpenAI']}]});
    expect(report.textContent).toContain('Cited by: OpenAI, Gemini · Shared source');
    expect(report.textContent).toContain('not independent documents');
  });
  it('keeps completed evidence visible during processing and separates pending from failed work', () => {
    const {window, report} = boot();
    window.App.sourceVerification.renderCurrent({...result, schema_version: 3, status: 'running',
      scope: {source_count: 3, checked_sources: 1, pairs: 3, checked_pairs: 1, processed_pairs: 2}, findings: [
        {...finding, support: 'partial'}, {...finding, source_id: 'S2', checked: false, reason_code: 'fetch_failed'},
        {...finding, source_id: 'S3', checked: false, reason_code: 'pending'}]});
    expect(report.textContent).toContain('1 of 3 sources checked');
    expect(report.textContent).toContain('1 pending · 1 not checked');
    expect(report.textContent).toContain('Partly supported');
    expect(report.textContent).toContain('Source could not be retrieved');
    expect(report.querySelectorAll('.source-check-row')).toHaveLength(3);
  });
  it('does not combine matching text from a different sentence with model evidence', () => {
    const {window, report} = boot();
    window.App.sourceVerification.renderCurrent(result, {differencesData: {claims: [{sentence_id: 2,
      anchor: finding.claim, agree: ['openai'], dissent: []}]}});
    expect(report.querySelector('.source-check-model-evidence')).toBeNull();
  });
  it('preserves expanded passages and keyboard focus during progressive updates', () => {
    const {window, report, document} = boot();
    window.App.sourceVerification.renderCurrent({...result, status: 'running'});
    const row = report.querySelector('.source-check-row'); row.open = true;
    row.querySelector('summary').focus();
    window.App.sourceVerification.renderCurrent({...result, status: 'running'});
    expect(report.querySelector('.source-check-row').open).toBe(true);
    expect(document.activeElement).toBe(report.querySelector('.source-check-row > summary'));
  });
  it("never relabels an old support verdict as thematic fit or repeats its opinion", () => {
    const { window, body, report } = boot();
    const legacy = { ...finding, support: 'mismatch', topical: undefined, temporal: 'suitable', reason: 'The consensus is wrong.' };
    window.App.sourceVerification.renderCurrent({ ...result, schema_version: 1, findings: [legacy] });
    expect(report.textContent).toContain('Topic unchecked');
    expect(report.textContent).not.toContain('The consensus is wrong.');
    expect(report.textContent).not.toContain('Off topic');
    expect(body.querySelector('.source-check-issue')).toBeNull();
  });
  it("only decorates the relevant S reference, preserving claim and difference nodes and handlers", () => {
    const { window, document, body, report } = boot();
    const claim = body.querySelector(".cx-claim"), diff = document.querySelector(".diff-card");
    const text = body.textContent, claimHTML = claim.outerHTML;
    const click = vi.fn(); claim.addEventListener("click", click);
    window.App.sourceVerification.renderCurrent({ status: "pending" });
    window.App.sourceVerification.renderCurrent(result);
    expect(body.querySelector(".cx-claim")).toBe(claim);
    expect(claim.outerHTML).toBe(claimHTML);
    expect(document.querySelector(".diff-card")).toBe(diff);
    expect(body.textContent).toBe(text);
    claim.click(); expect(click).toHaveBeenCalledOnce();
    expect(body.querySelectorAll("[data-source-check]")).toHaveLength(1);
    expect(body.querySelector("[data-source-check]")).toBe(body.querySelector(".src-ref"));
    expect(body.querySelectorAll(".source-check-mark, button")).toHaveLength(0);
    expect(report.textContent).toContain("Topic matches");
    expect(report.querySelector("blockquote").textContent).toBe("20 euros for students.");
    expect(document.getElementById("consensusSourceCheckStatus").textContent).toBe(" · 2/2 checked · 1 issue");
    body.querySelector(".src-ref").click();
    expect(report.querySelector(".source-check-row").open).toBe(true);
    expect(report.parentElement.hidden).toBe(false);
    window.App.sourceVerification.clear(body, report);
    expect(body.querySelector(".src-ref").title).toBe("Original source");
    expect(body.querySelectorAll("[data-source-check]")).toHaveLength(0);
    expect(body.querySelector(".cx-claim")).toBe(claim);
  });
  it("renders unknowns neutrally and restores without accumulating marks", () => {
    const { window, body, report } = boot();
    const snapshot = { ...result, status: "partial", findings: [{ ...finding, topical: "unknown", temporal: "unknown" }] };
    window.App.sourceVerification.renderCurrent(snapshot);
    window.App.sourceVerification.renderCurrent(JSON.parse(JSON.stringify(snapshot)));
    expect(body.querySelectorAll("[data-source-check=unknown]")).toHaveLength(1);
    expect(body.querySelector(".source-check-issue")).toBeNull();
    expect(report.textContent).toContain("2 of 2 citation checks completed");
  });
  it("communicates pending and clean assessments under Verify sources, including a moved reader panel", () => {
    const { window, body, report, document } = boot();
    window.App.sourceVerification.renderCurrent({ status: "pending" });
    expect(report.textContent).toContain("Checking sources");
    expect(report.textContent).toContain("Topic relevance & time period");
    expect(report.getAttribute("aria-busy")).toBe("true");
    expect(report.querySelectorAll(".source-check-skeleton-row")).toHaveLength(3);
    expect(document.querySelector("#consensusSourcesTab .source-check-loading")).not.toBeNull();
    document.body.append(report);
    window.App.sourceVerification.renderCurrent({ ...result, findings: [result.findings[1]] });
    expect(report.textContent).toContain("Source check complete");
    expect(report.textContent).toContain("Topic matches");
    expect(body.querySelectorAll("[data-source-check]")).toHaveLength(0);
    expect(report.hasAttribute("aria-busy")).toBe(false);
    expect(report.querySelector(".skeleton")).toBeNull();
    expect(document.querySelector("#consensusSourcesTab .source-check-loading")).toBeNull();
    expect(report.querySelector(".source-check-row").open).toBe(false);
  });
  it("keeps partial coverage explicit and never gives an unchecked report a checkmark", () => {
    const { window, report, document } = boot();
    const partial = { ...result, status: 'partial', scope: {pairs: 2, checked_pairs: 1},
      findings: [finding, {...finding, source_id: 'S2', checked: false}] };
    window.App.sourceVerification.renderCurrent(partial);
    expect(report.textContent).toContain('1 of 2 citation checks completed · 1 not checked');
    expect(report.querySelectorAll('.is-unchecked')).toHaveLength(1);
    expect(document.getElementById('consensusSourceCheckStatus').getAttribute('aria-label')).toContain('1 not checked');
    window.App.sourceVerification.renderCurrent({...partial, scope: {pairs: 2, checked_pairs: 0},
      findings: partial.findings.map(item => ({...item, checked: false}))});
    expect(report.textContent).toContain('Source check incomplete');
    expect(report.querySelector('.source-check-done')).toBeNull();
    expect(document.querySelector('.source-check-status-reviewed')).toBeNull();
  });
  it("does not turn provider text into HTML or link to unsafe URLs, and contains malformed results", () => {
    const { window, body, report } = boot();
    window.App.sourceVerification.renderCurrent({ ...result,
      findings: [{ ...finding, reason: '<img src=x onerror="alert(1)">' }],
      documents: [{ source_id: "S1", source_url: "javascript:alert(1)" }] });
    expect(report.querySelector("img")).toBeNull();
    expect(report.querySelector("a")).toBeNull();
    const claim = body.querySelector(".cx-claim");
    expect(() => window.App.sourceVerification.renderCurrent({ findings: [null] })).not.toThrow();
    expect(body.querySelector(".cx-claim")).toBe(claim);
    expect(report.textContent).toContain("Source check unavailable");
  });
  it('marks supported citations immediately but keeps a source with pending claims neutral', () => {
    const {window, body, document} = boot();
    const list = document.createElement('ol'); list.id = 'consensusSourcesList';
    list.innerHTML = '<li class="consensus-source-item" data-source-id="S1"><div class="consensus-source-body">Prices</div></li>';
    document.body.append(list);
    const good = {...finding, support: 'supported', topical: 'relevant', temporal: 'suitable'};
    const pending = {...good, sentence_id: 2, claim: 'Another sentence.', checked: false, reason_code: 'pending'};
    const snapshot = {schema_version: 3, status: 'running', scope: {pairs: 2, checked_pairs: 1}, findings: [good, pending]};
    window.App.sourceVerification.renderCurrent(snapshot);
    expect(body.querySelector('[data-source-number="1"]').dataset.sourceCheck).toBe('supported');
    expect(body.querySelectorAll('[data-source-number="1"]')[1].dataset.sourceCheck).toBe('pending');
    expect(list.firstElementChild.dataset.sourceCardCheck).toBe('pending');
    expect(document.getElementById('consensusSourceCheckStatus').textContent).toBe(' · 1/2 checked · 1 pending');
    window.App.sourceVerification.renderCurrent({...snapshot, status: 'complete', scope: {pairs: 2, checked_pairs: 2},
      findings: [good, {...pending, checked: true, reason_code: undefined}]});
    expect(list.firstElementChild.dataset.sourceCardCheck).toBe('supported');
    expect(list.textContent).toContain('✓ Verified support');
    expect(list.querySelectorAll('.source-check-card-status')).toHaveLength(1);
  });
  it('keeps mixed or unclear source evidence out of green while preserving independent citation verdicts', () => {
    const {window, body, document} = boot();
    const list = document.createElement('ol'); list.id = 'consensusSourcesList';
    list.innerHTML = '<li class="consensus-source-item" data-source-id="S1">Prices</li>';
    document.body.append(list);
    const good = {...finding, support: 'supported', topical: 'relevant', temporal: 'not_relevant'};
    for (const support of ['contradicted', 'partial', 'unknown']) {
      window.App.sourceVerification.renderCurrent({schema_version: 3, status: 'complete', findings: [good,
        {...good, sentence_id: 2, claim: 'Another sentence.', support}]});
      expect(body.querySelector('.src-ref').dataset.sourceCheck).toBe('supported');
      expect(list.firstElementChild.dataset.sourceCardCheck).toBe({contradicted: 'contradicted', partial: 'issue', unknown: 'unknown'}[support]);
      expect(list.textContent).not.toContain('Verified support');
    }
  });
  it('applies results to a late source list and removes green marks on reset without leaking into history', () => {
    const {window, body, report, document} = boot();
    const good = {...finding, support: 'supported', topical: 'relevant', temporal: 'suitable'};
    window.App.sourceVerification.renderCurrent({schema_version: 3, status: 'complete', findings: [good]});
    const list = document.createElement('ol');
    list.innerHTML = '<li class="consensus-source-item" data-source-id="S1">Prices</li>';
    document.body.append(list);
    window.App.sourceVerification.applySourceList(list, body);
    expect(list.firstElementChild.dataset.sourceCardCheck).toBe('supported');
    const history = document.createElement('div');
    const historyList = list.cloneNode(true); history.append(historyList); document.body.append(history);
    window.App.sourceVerification.applySourceList(historyList, history);
    expect(historyList.firstElementChild.hasAttribute('data-source-card-check')).toBe(false);
    window.App.sourceVerification.clear(body, report);
    expect(list.querySelector('.source-check-card-status')).toBeNull();
    expect(list.firstElementChild.hasAttribute('data-source-card-check')).toBe(false);
    expect(body.querySelector('[data-source-check="supported"]')).toBeNull();
    window.App.sourceVerification.applySourceList(list, body);
    expect(list.querySelector('.source-check-card-status')).toBeNull();
  });
  it('summarizes unavailable checks with concrete reasons and counts', () => {
    const {window, report, document} = boot();
    window.App.sourceVerification.renderCurrent({schema_version: 3, status: 'partial', scope: {pairs: 2, checked_pairs: 0},
      findings: [{...finding, checked: false, reason_code: 'access_denied'}, {...finding, source_id: 'S2', checked: false, reason_code: 'redirect_limit'}]});
    expect(document.getElementById('consensusSourceCheckStatus').textContent).toBe(' · 0/2 checked · 2 unavailable');
    expect(report.querySelector('.source-check-failure-summary').textContent).toBe('Website denied access (1) · Too many website redirects (1)');
    expect(document.querySelector('[data-source-check="supported"]')).toBeNull();
  });
  it('decorates sparse public source IDs and keeps separate historical turns isolated', () => {
    const {window, document} = boot();
    const good = {...finding, source_id: 'S7', support: 'supported', topical: 'relevant', temporal: 'suitable'};
    const publicBody = document.createElement('div'); publicBody.className = 'share-md';
    publicBody.innerHTML = '<p>The plan costs 20 euros. <a href="#src-7">7</a></p>';
    const publicReport = document.createElement('div');
    const publicCard = document.createElement('li'); publicCard.id = 'src-7'; publicCard.textContent = 'Public source';
    document.body.append(publicBody, publicReport, publicCard);
    window.App.sourceVerification.render(publicBody, publicReport, {schema_version: 3, status: 'complete', findings: [good]});
    expect(publicCard.dataset.sourceCardCheck).toBe('supported');
    expect(publicBody.querySelector('a').dataset.sourceCheck).toBe('supported');
    const turns = [0, 1].map(() => {
      const turn = document.createElement('div'); turn.className = 'thread-history-turn';
      turn.innerHTML = '<div class="answer"><p>The plan costs 20 euros. <a class="src-ref" data-source-number="7">7</a></p></div><div class="panel"><div class="report"></div><ol class="thread-history-sources"><li><a href="https://example.com/history">Source</a></li></ol></div>';
      document.body.append(turn); return turn;
    });
    turns.forEach((turn, index) => window.App.sourceVerification.render(turn.querySelector('.answer'), turn.querySelector('.report'), {
      schema_version: 3, status: index ? 'running' : 'complete', sources: [{id: 'S7', url: 'https://example.com/history'}],
      findings: [{...good, checked: !index, reason_code: index ? 'pending' : undefined}]}));
    expect(turns[0].querySelector('li').dataset.sourceCardCheck).toBe('supported');
    expect(turns[1].querySelector('li').dataset.sourceCardCheck).toBe('pending');
    expect(publicCard.dataset.sourceCardCheck).toBe('supported');
    window.App.sourceVerification.clear(turns[1].querySelector('.answer'), turns[1].querySelector('.report'));
    expect(turns[0].querySelector('li').dataset.sourceCardCheck).toBe('supported');
  });
  it('distinguishes uncited catalogue references from pending checks and compact job stubs', () => {
    const {window, document} = boot();
    const list = document.createElement('ol'); list.id = 'consensusSourcesList';
    list.innerHTML = Array.from({length: 23}, (_, index) => `<li class="consensus-source-item" data-source-id="S${index + 1}">Source ${index + 1}</li>`).join('');
    document.body.append(list);
    const sources = Array.from({length: 5}, (_, index) => ({id: `S${index + 1}`, url: `https://example.com/${index + 1}`}));
    const snapshot = {schema_version: 3, status: 'running', scope: {sources: 5, pairs: 8, checked_pairs: 0},
      sources, findings: sources.map(source => ({...finding, source_id: source.id, checked: false, reason_code: 'pending'}))};
    window.App.sourceVerification.renderCurrent(snapshot);
    expect(list.querySelectorAll('[data-source-card-check="pending"]')).toHaveLength(5);
    expect(list.querySelectorAll('[data-source-card-check="uncited"]')).toHaveLength(18);
    expect(list.querySelector('[data-source-id="S23"]').textContent).toContain('Not cited in consensus');
    expect(list.querySelectorAll('[data-source-card-check="unknown"]')).toHaveLength(0);
    window.App.sourceVerification.renderCurrent({...snapshot, status: 'queued', findings: []});
    expect(list.querySelectorAll('[data-source-card-check="awaiting_details"]')).toHaveLength(5);
    expect(list.querySelectorAll('[data-source-card-check="uncited"]')).toHaveLength(18);
    window.App.sourceVerification.renderCurrent({...snapshot, status: 'queued', findings: [], sources: []});
    expect(list.querySelectorAll('[data-source-card-check="awaiting_details"]')).toHaveLength(23);
    expect(list.querySelectorAll('[data-source-card-check="uncited"]')).toHaveLength(0);
  });
});
