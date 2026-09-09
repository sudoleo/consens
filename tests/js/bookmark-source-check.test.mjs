import {readFileSync} from 'node:fs';
import path from 'node:path';
import {describe, it, expect, vi} from 'vitest';
import {loadScripts, ROOT} from './helpers/appWindow.mjs';

function boot() {
  const env = loadScripts([]);
  const source = readFileSync(path.join(ROOT, 'static/firebase.js'), 'utf8');
  const start = source.indexOf('function observeBookmarkSourceCheck(');
  const end = source.indexOf('function loadSingleBookmarkUI(', start);
  const user = {uid: 'owner'};
  env.window.App = {sourceVerification: {observe: vi.fn(() => vi.fn()), renderCurrent: vi.fn()},
    runRegistry: {getSelectedConversationBasis: () => ({bookmarkId: 'bookmark', currentTurn: {}}), selectConversationBasis: vi.fn()}};
  const helper = Function('window', 'auth', 'authState', `let bookmarkViewEpoch=1; ${source.slice(start, end)}
    return {observeBookmarkSourceCheck, changeView(){bookmarkViewEpoch += 1;}};`)(env.window, {currentUser: user}, {generation: 2});
  return {...env, ...helper, user};
}

describe('reopened bookmark source checks', () => {
  it('hydrates even a terminal empty stub and updates only its saved turn and basis', () => {
    const {window, document, observeBookmarkSourceCheck, user} = boot();
    const body = document.createElement('div'); document.body.append(body);
    const stub = {job_id: 'job', status: 'complete', findings: []};
    const bookmark = {responses: {source_verification: stub}};
    const sourceBookmark = {id: 'bookmark', responses: {source_verification: stub}};
    const continuationTurn = {source_verification: stub}, differencesData = {claims: [{sentence_id: 1}]};
    observeBookmarkSourceCheck({bookmark, sourceBookmark, continuationTurn, body, differencesData});
    const binding = window.App.sourceVerification.observe.mock.calls[0][0];
    expect(binding.auth).toEqual({user, uid: 'owner', generation: 2});
    expect(binding.snapshot).toBe(stub);
    expect(binding.isActive()).toBe(true);
    const hydrated = {...stub, findings: [{sentence_id: 1, source_id: 'S1'}]};
    binding.onUpdate(hydrated);
    expect(sourceBookmark.responses.source_verification).toBe(hydrated);
    expect(continuationTurn.source_verification).toBe(hydrated);
    expect(window.App.runRegistry.selectConversationBasis.mock.calls[0][0].currentTurn.source_verification).toBe(hydrated);
    expect(window.App.sourceVerification.renderCurrent).toHaveBeenCalledWith(hydrated, {differencesData});
  });
  it('invalidates the old observer when another bookmark or live run replaces its view', () => {
    const {window, document, observeBookmarkSourceCheck, changeView} = boot();
    const body = document.createElement('div'); document.body.append(body);
    const bookmark = {responses: {source_verification: {job_id: 'first', status: 'queued'}}};
    observeBookmarkSourceCheck({bookmark, sourceBookmark: {id: 'bookmark'}, body});
    const binding = window.App.sourceVerification.observe.mock.calls[0][0];
    expect(binding.isActive()).toBe(true);
    changeView();
    expect(binding.isActive()).toBe(false);
  });
});
