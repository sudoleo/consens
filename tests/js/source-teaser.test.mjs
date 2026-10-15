import {describe, it, expect} from 'vitest';
import {loadScripts} from './helpers/appWindow.mjs';

const source = {id: 'S1', title: 'Plan prices', url: 'https://prices.example', snippet: 'Public price list'};
const claim = 'The plan costs 20 euros.';
function boot(text = `${claim} [S1] Another claim. [S1]`, sources = [source]) {
  const env = loadScripts(['static/js/sources.js'], {body: '<div id="consensusAnswerBody"></div>'});
  const body = env.document.getElementById('consensusAnswerBody');
  body.textContent = text;
  env.window.linkifySourceTags(body, sources);
  const ref = body.querySelector('.src-ref');
  const hover = (target = ref) => target.dispatchEvent(new env.window.Event('pointerover', {bubbles: true}));
  return {...env, body, ref, hover};
}

describe('source teaser', () => {
  it('names the source and its snippet, without a native title or a check line', () => {
    const env = boot();
    env.ref.setAttribute('title', 'Legacy source title');
    env.hover();
    const popup = env.document.getElementById('sourceTeaser');
    expect(popup.classList.contains('is-visible')).toBe(true);
    expect(popup.textContent).toContain('Plan prices');
    expect(popup.textContent).toContain('Public price list');
    expect(popup.textContent).not.toContain('checked');
    expect(env.ref.hasAttribute('title')).toBe(false);
    expect(env.ref.getAttribute('aria-label')).toBe('Source: prices.example');
    env.dom.window.close();
  });

  it('lists every source behind a grouped pill', () => {
    const env = boot(`${claim} [S1, S2]`, [source, {id: 'S2', title: 'Second list', url: 'https://second.example'}]);
    const pills = env.body.querySelectorAll('.src-ref');
    expect(pills).toHaveLength(1);
    const pill = pills[0];
    expect(pill.dataset.sourceNumbers).toBe('1 2');
    expect(pill.querySelector('.src-ref-more').textContent).toBe('+1');
    expect(pill.getAttribute('aria-label')).toBe('Source: prices.example (and 1 more)');
    env.hover(pill);
    const rows = env.document.querySelectorAll('#sourceTeaser .source-teaser-item');
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain('Plan prices');
    expect(rows[1].textContent).toContain('Second list');
    env.dom.window.close();
  });

  it('keeps the source of an earlier turn that reuses the same source ID', () => {
    const env = boot();
    const history = env.document.createElement('div');
    history.className = 'consensus-answer-body';
    history.textContent = `${claim} [S1]`;
    env.document.body.append(history);
    env.window.linkifySourceTags(history, [{...source, title: 'Archived source'}]);
    env.window.currentEvidenceSources = [{...source, title: 'New live source'}];
    env.hover(history.querySelector('.src-ref'));
    const popup = env.document.getElementById('sourceTeaser');
    expect(popup.textContent).toContain('Archived source');
    expect(popup.textContent).not.toContain('New live source');
    env.dom.window.close();
  });

  it('opens the same tooltip on keyboard focus and dismisses with Escape without stealing focus', () => {
    const env = boot();
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
