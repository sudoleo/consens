/* Offline review probes. Run after npm ci: node docs/code-review/repro/frontend.cjs.
 * Assertions describe baseline bugs; convert to desired behavior when fixing.
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
  console.log(JSON.stringify(results,null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
