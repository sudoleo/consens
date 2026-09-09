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
    expect(env.ref.getAttribute('aria-label')).toBe('Source 1: Plan prices');
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
