import {describe, it, expect} from 'vitest';
import {loadScripts} from './helpers/appWindow.mjs';

describe('source citation identity', () => {
  it('resolves sparse IDs by identity and leaves missing citations unresolved', () => {
    const {window} = loadScripts(['static/js/sources.js']);
    const sources = [{id: 'S2', url: 'https://two.example'}, {id: 'S7', url: 'https://seven.example'}];
    const refs = window.getSourceRefs('[S1] [S2] [S7]', sources);
    expect(refs.map(item => item.src?.url || null)).toEqual([null, 'https://two.example', 'https://seven.example']);
  });
  it('normalizes numeric IDs without resolving ambiguous duplicate IDs', () => {
    const {window} = loadScripts(['static/js/sources.js']);
    const refs = window.getSourceRefs('[S2] [S3]', [{id: 2, url: 'https://two.example'},
      {id: 'S3', url: 'https://a.example'}, {id: '3', url: 'https://b.example'}]);
    expect(refs[0].src.url).toBe('https://two.example');
    expect(refs[1].src).toBeNull();
  });
  it('keeps positional lookup solely for legacy entries without an ID', () => {
    const {window} = loadScripts(['static/js/sources.js']);
    const legacy = {url: 'https://legacy.example'};
    expect(window.getSourceRefs('[1] [2]', [legacy, {id: 'S9', url: 'https://nine.example'}]).map(item => item.src)).toEqual([legacy, null]);
  });
});
