import {describe, it, expect} from 'vitest';
import {loadScripts} from './helpers/appWindow.mjs';

const source = {id: 'S1', title: 'Plan prices', url: 'https://prices.example', snippet: 'Public price list'};
const claim = 'The plan costs 20 euros.';
function boot() {
  const env = loadScripts(['static/js/sources.js', 'static/js/consensus-anchor.js', 'static/js/source-verification.js'], {
    body: '<div id="consensusAnswerBody"></div><div id="report"></div>'
  });
  const body = env.document.getElementById('consensusAnswerBody');
  const report = env.document.getElementById('report');
  body.textContent = `${claim} [S1] Another claim. [S1]`;
  env.window.linkifySourceTags(body, [source]);
  const ref = body.querySelector('.src-ref');
  const render = (finding = {}, status = 'complete') => env.window.App.sourceVerification.render(body, report, {
    schema_version: 3, status, scope: {pairs: 1, checked_pairs: finding.checked === false ? 0 : 1},
    findings: [{source_id: 'S1', sentence_id: 1, claim, anchor_occurrence: 0,
      checked: true, support: 'supported', topical: 'relevant', temporal: 'suitable', ...finding}]
  });
  const hover = (target = ref) => target.dispatchEvent(new env.window.Event('pointerover', {bubbles: true}));
  return {...env, body, report, ref, render, hover};
}

describe('source teaser check disclosure', () => {
  it.each([
    [{}, 'supports this statement'],
    [{support: 'partial'}, 'only partly supports this statement'],
    [{support: 'contradicted'}, 'contradicts this statement'],
    [{support: 'unknown'}, 'support for this statement is unclear'],
    [{temporal: 'outdated'}, 'topic or time needs attention'],
    [{checked: false, reason_code: 'access_denied'}, 'could not be checked']
  ])('shows the bound result and safe reason for %j', (finding, text) => {
    const env = boot();
    env.render({...finding, reason: '<img src=x onerror=alert(1)> Reason from the check.'});
    env.hover();
    const popup = env.document.getElementById('sourceTeaser');
    expect(popup.textContent).toContain('Plan prices');
    expect(popup.querySelector('.source-teaser-check').textContent).toContain(text);
    expect(popup.querySelector('.source-teaser-check-detail').textContent).toContain('<img src=x');
    expect(popup.querySelector('.source-teaser-check-detail img')).toBeNull();
    expect(env.ref.hasAttribute('title')).toBe(false);
    env.dom.window.close();
  });

  it('keeps a hovered popup current through pending, checked, rerender and clearing without native titles', () => {
    const env = boot();
    env.ref.setAttribute('title', 'Legacy source title');
    env.render({checked: false, reason_code: 'pending'}, 'running');
    env.hover();
    const popup = env.document.getElementById('sourceTeaser');
    expect(popup.textContent).toContain('waiting to be checked');
    env.render();
    expect(popup.textContent).toContain('supports this statement');
    env.render({support: 'contradicted'});
    expect(popup.textContent).toContain('contradicts this statement');
    expect(env.ref.hasAttribute('title')).toBe(false);
    env.window.App.sourceVerification.clear(env.body, env.report);
    expect(popup.textContent).toContain('has not been checked');
    expect(popup.textContent).not.toContain('contradicts');
    expect(env.ref.hasAttribute('title')).toBe(false);
    expect(env.ref.getAttribute('aria-label')).toBe('Source: prices.example');
    env.dom.window.close();
  });

  it('binds one verdict per source to a grouped pill and shows the most severe one', () => {
    const env = loadScripts(['static/js/sources.js', 'static/js/consensus-anchor.js', 'static/js/source-verification.js'], {
      body: '<div id="consensusAnswerBody"></div><div id="report"></div>'
    });
    const body = env.document.getElementById('consensusAnswerBody');
    const sources = [source, {id: 'S2', title: 'Second list', url: 'https://second.example'}];
    body.textContent = `${claim} [S1, S2]`;
    env.window.linkifySourceTags(body, sources);
    const pills = body.querySelectorAll('.src-ref');
    expect(pills).toHaveLength(1);
    const pill = pills[0];
    expect(pill.dataset.sourceNumbers).toBe('1 2');
    expect(pill.querySelector('.src-ref-more').textContent).toBe('+1');
    const finding = {sentence_id: 1, claim, anchor_occurrence: 0, checked: true, topical: 'relevant', temporal: 'suitable'};
    env.window.App.sourceVerification.render(body, env.document.getElementById('report'), {
      schema_version: 3, status: 'complete', scope: {pairs: 2, checked_pairs: 2},
      findings: [{...finding, source_id: 'S1', support: 'supported'}, {...finding, source_id: 'S2', support: 'contradicted'}]
    });
    expect(pill.dataset.sourceCheck).toBe('contradicted');
    expect(pill.getAttribute('aria-label')).toBe('Source: prices.example (and 1 more). Source checked: contradicts this statement.');
    pill.dispatchEvent(new env.window.Event('pointerover', {bubbles: true}));
    const rows = env.document.querySelectorAll('#sourceTeaser .source-teaser-item');
    expect(rows).toHaveLength(2);
    expect(rows[0].querySelector('.source-teaser-check').textContent).toContain('supports this statement');
    expect(rows[1].querySelector('.source-teaser-check').textContent).toContain('contradicts this statement');
    env.window.App.sourceVerification.clear(body, env.document.getElementById('report'));
    expect(pill.hasAttribute('data-source-check')).toBe(false);
    expect(pill.getAttribute('aria-label')).toBe('Source: prices.example (and 1 more)');
    env.dom.window.close();
  });

  it('does not borrow the verdict of another statement or turn using the same source ID', () => {
    const env = boot();
    env.render();
    env.hover(env.body.querySelectorAll('.src-ref')[1]);
    expect(env.document.getElementById('sourceTeaser').textContent).toContain('No check result is available for this citation');
    const history = env.document.createElement('div');
    history.className = 'consensus-answer-body';
    history.textContent = `${claim} [S1]`;
    env.document.body.append(history);
    env.window.linkifySourceTags(history, [{...source, title: 'Archived source'}]);
    env.window.currentEvidenceSources = [{...source, title: 'New live source'}];
    env.hover(history.querySelector('.src-ref'));
    const popup = env.document.getElementById('sourceTeaser');
    expect(popup.textContent).toContain('Archived source');
    expect(popup.textContent).toContain('has not been checked');
    expect(popup.textContent).not.toContain('supports this statement');
    env.dom.window.close();
  });

  it('opens the same tooltip on keyboard focus and dismisses with Escape without stealing focus', () => {
    const env = boot();
    env.render();
    env.ref.setAttribute('aria-describedby', 'existing-description');
    env.ref.focus();
    const popup = env.document.getElementById('sourceTeaser');
    expect(popup.classList.contains('is-visible')).toBe(true);
    expect(env.ref.getAttribute('aria-describedby')).toBe('existing-description sourceTeaser');
    env.ref.dispatchEvent(new env.window.KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
    expect(popup.classList.contains('is-visible')).toBe(false);
    expect(env.document.activeElement).toBe(env.ref);
    expect(env.ref.getAttribute('aria-describedby')).toBe('existing-description');
    expect(env.ref.hasAttribute('title')).toBe(false);
    env.dom.window.close();
  });
});
