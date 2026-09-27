/* Offline review probes. Run after npm ci: node docs/code-review/repro/frontend.cjs.
 * Assertions describe baseline behavior; convert to desired behavior when fixing.
 */
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assert = require('node:assert/strict');
const { JSDOM } = require('jsdom');
const root = path.resolve(__dirname, '../../..');
const source = name => fs.readFileSync(path.join(root, name), 'utf8');
const results = [];
function between(file, from, to) {
  const s = source(file); const a = s.indexOf(from); const b = s.indexOf(to, a + from.length);
  assert(a >= 0 && b > a); return s.slice(a, b);
}
(async () => {
  const dom = new JSDOM('<div id="topicStrip"><a class="topic-strip-cell" data-date="2026-09-26"></a></div><p id="topicStripRead">Initial</p>', {url:'https://example.test', runScripts:'outside-only'});
  const cell = dom.window.document.querySelector('a');
  // Server escaping is undone by HTML attribute parsing. The DOM sink parses again.
  cell.setAttribute('data-note', '<span id="review-injected">not plain text</span>');
  dom.window.eval(source('static/js/topic-page.js'));
  dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));
  cell.dispatchEvent(new dom.window.Event('focus'));
  assert(dom.window.document.getElementById('review-injected'));
  results.push({probe:'R01-topic-html', injected_element:true});
  dom.window.close();

  const context = vm.createContext({URL});
  vm.runInContext(between('static/js/sources.js','function normalizeEvidenceUrl(', '// Pure run-local merge.'), context);
  const a = context.normalizeEvidenceUrl('https://example.test/Report?key=AbC');
  const b = context.normalizeEvidenceUrl('https://example.test/report?key=abc');
  assert.equal(a,b);
  results.push({probe:'R31-source-url', distinct_urls_have_same_key:true});

  let form={title:'Topic A'}; const calls=[];
  const admin = vm.createContext({
    selectedTopicId:'A', renderAdminTopicList(){}, topicAdminStatus(){},
    document:{getElementById:()=>({disabled:false})},
    adminTopicPayload:()=>({...form}), fillAdminTopic:topic=>{form=topic;},
    loadAdminTopics:async()=>{},
    shareAdminRequest:async(method,url,payload)=>{
      calls.push({method,url,payload});
      if(method==='GET') throw new Error('Loading B failed');
      return {topic:{id:'B'}};
    }
  });
  vm.runInContext(between('static/js/admin.js','async function selectAdminTopic(', 'async function loadAdminTopics('), admin);
  vm.runInContext(between('static/js/admin.js','async function saveAdminTopic(', 'async function runAdminTopic('), admin);
  await admin.selectAdminTopic('B'); await admin.saveAdminTopic();
  assert.equal(calls[1].url,'/api/admin/topics/B');
  assert.equal(calls[1].payload.title,'Topic A');
  results.push({probe:'R20-admin-selection', save:calls[1]});
  // Run the entire attachment module; pause only the browser FileReader.
  const attDom = new JSDOM('<div class="chat-input-container"><button id="attachTrigger"></button><div id="attachMenu"></div><button id="attachUploadOption"></button><input id="attachFileInput" type="file"><div id="attachmentBar"></div><textarea id="questionInput"></textarea></div>', {url:'https://example.test', runScripts:'outside-only'});
  attDom.window.App = {};
  attDom.window.isUserPlus = true;
  let reader;
  attDom.window.FileReader = class { readAsDataURL() { reader = this; } };
  attDom.window.eval(source('static/js/attachments.js'));
  const picker = attDom.window.document.getElementById('attachFileInput');
  Object.defineProperty(picker, 'files', {value:[new attDom.window.File(['old draft'], 'draft-a.txt', {type:'text/plain'})]});
  picker.dispatchEvent(new attDom.window.Event('change'));
  await new Promise(setImmediate);
  assert(reader);
  attDom.window.showBookmarkAttachments([]);
  assert.equal(attDom.window.pendingAttachments.length, 0);
  reader.result = 'data:text/plain;base64,b2xkIGRyYWZ0'; reader.onload();
  await new Promise(setImmediate);
  assert.equal(attDom.window.pendingAttachments[0].name, 'draft-a.txt');
  results.push({probe:'R21-late-attachment', pending_after_bookmark_switch:'draft-a.txt'});
  attDom.window.close();

  // Full Memory edit module, actual UI events, synthetic auth + offline HTTP.
  const memDom = new JSDOM('<textarea id="questionInput">Account A preference</textarea>', {url:'https://example.test', runScripts:'outside-only'});
  const w = memDom.window;
  w.requestAnimationFrame = fn => fn();
  w.auth = {currentUser:{uid:'A', getIdToken:async()=> 'token-A'}};
  let reloadUid; const requests=[];
  w.App = {userMemory:{load:async()=> {reloadUid=w.auth.currentUser.uid;}}};
  let resolveFetch;
  w.fetch = (url, options) => {
    requests.push({url, options});
    return new Promise(resolve=>{resolveFetch=resolve;});
  };
  w.eval(source('static/js/memory-edit.js'));
  w.document.dispatchEvent(new w.Event('DOMContentLoaded'));
  const question = w.document.getElementById('questionInput');
  question.setSelectionRange(0, question.value.length);
  question.dispatchEvent(new w.KeyboardEvent('keyup', {key:'Shift', bubbles:true}));
  w.document.querySelector('[data-memory-intent="add"]').click();
  assert.equal(w.document.getElementById('memoryEditBackdrop').hidden, false);
  w.auth.currentUser = {uid:'B', getIdToken:async()=> 'token-B'};
  w.dispatchEvent(new w.CustomEvent('consensio:auth-state', {detail:{uid:'B'}}));
  assert.equal(w.document.getElementById('memoryEditBackdrop').hidden, false);
  w.document.querySelector('.memory-edit-submit').click();
  await new Promise(setImmediate);
  assert.equal(requests[0].options.headers.Authorization, 'Bearer token-B');
  assert.equal(JSON.parse(requests[0].options.body).selected_text, 'Account A preference');
  results.push({probe:'R23-selection-owner', selected_from:'A', sent_with_token_for:'B'});
  // The same B request finishes after another switch to C.
  w.auth.currentUser = {uid:'C', getIdToken:async()=> 'token-C'};
  w.dispatchEvent(new w.CustomEvent('consensio:auth-state', {detail:{uid:'C'}}));
  resolveFetch({ok:true, json:async()=>({status:'applied', revision_id:'revision-B'})});
  await new Promise(setImmediate);
  assert.equal(reloadUid, 'C');
  assert.equal(w.document.getElementById('memoryEditToast').hidden, false);
  results.push({probe:'R23-late-response', request_for:'B', reload_for:'C', old_undo_visible:true});
  memDom.window.close();

  console.log(JSON.stringify(results,null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
