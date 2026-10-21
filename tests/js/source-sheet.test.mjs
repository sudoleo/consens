import {describe, it, expect} from 'vitest';
import {loadScripts} from './helpers/appWindow.mjs';

// Apple audit F6: what a pill announces can be opened, on every device.
const sources = [
  {id: 'S1', title: 'UCI regulations', url: 'https://www.uci.org/rules', snippet: 'Article 2.3'},
  {id: 'S2', title: 'Analysis', url: 'https://example.org/analysis'},
  {id: 'S3', title: 'Race report', url: 'https://news.example.com/report'},
];

function boot(text = 'The race starts in Monaco [S1][S2][S3]. Watch the traffic [S2].', {markup} = {}) {
  const env = loadScripts(['static/js/sources.js'], {body: markup || '<div id="consensusAnswerBody"></div>'});
  const body = env.document.getElementById('consensusAnswerBody');
  body.textContent = text;
  env.window.linkifySourceTags(body, sources);
  const [group, single] = body.querySelectorAll('.src-ref');
  // jsdom has no PointerEvent: a pointerdown that says which pointer it was.
  const press = (target, pointerType) => {
    const down = new env.window.MouseEvent('pointerdown', {bubbles: true});
    Object.defineProperty(down, 'pointerType', {value: pointerType});
    target.dispatchEvent(down);
    const click = new env.window.MouseEvent('click', {bubbles: true, cancelable: true, button: 0});
    target.dispatchEvent(click);
    return click;
  };
  return {...env, body, group, single, press, sheet: () => env.document.getElementById('sourceSheet')};
}

describe('source sheet', () => {
  it('opens every source of a pill at the first tap, and no tab', () => {
    const env = boot();
    const click = env.press(env.group, 'touch');
    expect(click.defaultPrevented).toBe(true);
    const sheet = env.sheet();
    expect(sheet.hidden).toBe(false);
    expect(sheet.querySelector('.source-sheet-heading').textContent).toBe('3 sources');
    const links = [...sheet.querySelectorAll('a.source-sheet-link')];
    expect(links.map(a => a.href)).toEqual(['https://www.uci.org/rules', 'https://example.org/analysis', 'https://news.example.com/report']);
    expect(links.every(a => a.target === '_blank' && a.rel === 'noopener noreferrer')).toBe(true);
    expect(env.group.getAttribute('aria-expanded')).toBe('true');
    // A single source on touch: the same sheet, with its excerpt.
    env.window.App.sourceSheet.close();
    env.press(env.single, 'touch');
    expect(env.sheet().querySelector('.source-sheet-heading').textContent).toBe('Source');
    expect(env.sheet().querySelectorAll('a.source-sheet-link')).toHaveLength(1);
    env.dom.window.close();
  });

  it('with a mouse lists a grouped pill and leaves a single pill a link', () => {
    const env = boot();
    expect(env.press(env.single, 'mouse').defaultPrevented).toBe(false);
    expect(env.sheet()?.hidden ?? true).toBe(true);
    expect(env.press(env.group, 'mouse').defaultPrevented).toBe(true);
    expect(env.sheet().hidden).toBe(false);
    expect(env.sheet().classList.contains('is-modal')).toBe(false);
    expect(env.document.activeElement.classList.contains('source-sheet-link')).toBe(true);
    env.sheet().dispatchEvent(new env.window.KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
    expect(env.sheet().hidden).toBe(true);
    expect(env.document.activeElement).toBe(env.group);
    expect(env.group.hasAttribute('aria-expanded')).toBe(false);
    env.dom.window.close();
  });
});

describe('source sheet in the answer reader', () => {
  // Review 5: the reader is a modal <dialog>; a list on <body> lay under it,
  // inert and out of sight, so a tap on a pill there did nothing at all.
  it('opens inside the open dialog of its pill, and on the page again for a pill there', () => {
    const env = boot('Monaco [S1][S2][S3].', {markup:
      '<dialog id="reader" class="answer-reader-dialog" open><div id="consensusAnswerBody"></div></dialog><p id="page" class="consensus-answer-body">Elsewhere [S1][S2].</p>'});
    const page = env.document.getElementById('page');
    env.window.linkifySourceTags(page, sources);
    const pagePill = page.querySelector('.src-ref');
    expect(pagePill).not.toBeNull();
    env.press(env.group, 'touch');
    const sheet = env.sheet();
    expect(sheet.hidden).toBe(false);
    expect(sheet.parentElement.id).toBe('reader');
    expect(env.document.querySelector('.source-sheet-backdrop').parentElement.id).toBe('reader');
    env.window.App.sourceSheet.close();
    // With a mouse a grouped pill lists at the pill, in the window's frame.
    env.press(env.group, 'mouse');
    expect(sheet.parentElement.id).toBe('reader');
    expect(sheet.style.position).toBe('fixed');
    env.window.App.sourceSheet.close();
    // A pill on the page takes the list back to <body>.
    env.press(pagePill, 'touch');
    expect(sheet.parentElement).toBe(env.document.body);
    expect(sheet.style.position).toBe('');
    env.dom.window.close();
  });
});
