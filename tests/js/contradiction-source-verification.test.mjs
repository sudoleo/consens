import {describe, it, expect, vi} from 'vitest';
import {loadScripts} from './helpers/appWindow.mjs';
const positions = [{id:'P1', summary:'20 euros for everyone',models:['OpenAI'],quote:'It costs 20 euros.'},
  {id:'P2',summary:'20 euros for students only',models:['Anthropic'],quote:'Students pay 20 euros.'}];
const diff = {type:'contradiction',severity:'major',claim:'Who pays 20 euros?',consensus_anchor:'Consensus stays unchanged.', factual_check:{checkable:true,question:'Who pays 20 euros?'},positions:positions.map(p => ({...p,stance:p.summary}))};
const finding = {contradiction_id:'c-one', difference_index:0, run_id:'run-one',answer_version:'answer-one',positions_version:'positions-one',
  question:diff.claim,consensus_anchor:diff.consensus_anchor,positions,checked:true,state:'checked',verdict:'conditions_explain',reason:'The student rate explains the difference.',
  evidence:[{source_id:'S1',position_id:'P2',quote:'Students pay 20 euros. [S2] <script>literal</script>',date:'2026-09-11',scope:'Students',limitations:'Annual plan'}]};
const snapshot = {schema_version:4,check_type:'contradiction_evidence',run_id:'run-one',answer_version:'answer-one',job_id:'job-one',
  status:'complete',revision:1,scope:{contradictions:1,checked_contradictions:1},findings:[finding],sources:[{id:'S1',url:'https://example.com/prices',title:'Student pricing'}]};
function boot() {
  return loadScripts(['static/js/source-verification.js'], {body:'<div id="consensusAnswerBody">Consensus stays unchanged.</div><div id="differencesCards"><details class="diff-card"><summary class="diff-card-claim">Who pays 20 euros?</summary><div class="diff-card-body">Original model positions</div></details></div><div id="sourceVerificationReport"></div><button id="consensusSourcesTab" hidden><span class="consensus-tab-label">Sources</span></button><span id="consensusSourceCheckStatus"></span>'});
}
const options={differencesData:{differences:[diff]}};
describe('contradiction evidence presentation', () => {
  it('shows attributed verbatim evidence inside the contradiction, never a verified-answer badge', () => {
    const {window,document}=boot(); const original=JSON.stringify(snapshot);
    window.App.sourceVerification.renderCurrent(snapshot, options);
    const result=document.querySelector('.diff-card .contradiction-source-check');
    expect(result.textContent).toContain('Different conditions explain');
    expect(result.querySelector('blockquote').textContent).toBe(finding.evidence[0].quote);
    expect(result.querySelector('script')).toBeNull();
    expect(result.querySelector('a').href).toBe('https://example.com/prices');
    expect(result.textContent).toContain('Annual plan');
    expect(document.querySelector('#consensusSourcesTab').dataset.checkState).toBe('');
    expect(document.querySelector('#consensusAnswerBody').textContent).toBe('Consensus stays unchanged.');
    expect(JSON.stringify(snapshot)).toBe(original);
  });
  it.each([
    [{status:'skipped',findings:[],scope:{contradictions:0}},'No checkable contradictions detected'],
    [{status:'disabled',findings:[],scope:{contradictions:0}},'Contradiction source checks disabled'],
    [{status:'failed',runtime:{error_code:'differences_failed'},findings:[]},'Differences analysis failed'],
    [{scope:{contradictions:1,checked_contradictions:0,omitted_contradictions:1},findings:[{...finding,checked:false,state:'omitted',reason_code:'url_limit',evidence:[]}]},'Source URL budget reached'],
  ])('distinguishes empty, disabled, failed and budget omissions', (changes,label) => {
    const {window,document}=boot(); window.App.sourceVerification.renderCurrent({...snapshot,...changes},options);
    expect(document.body.textContent).toContain(label);
    expect(document.body.textContent).not.toContain('Answer verified');
    expect(document.querySelector('#consensusSourcesTab').hidden).toBe(false);
  });
  it('does not show a substantive verdict without attributed evidence or for a different answer', () => {
    const {window,document}=boot();
    window.App.sourceVerification.renderCurrent({...snapshot,findings:[{...finding,evidence:[]}]},options);
    expect(document.querySelector('.contradiction-source-verdict').textContent).toBe('Existing evidence is insufficient');
    expect(document.body.textContent).not.toContain(finding.reason);
    window.App.sourceVerification.renderCurrent({...snapshot,findings:[{...finding,answer_version:'another-answer'}]},options);
    expect(document.querySelector('.contradiction-source-check')).toBeNull();
  });
  it('rejects changed positions, anchor or factual question in restored Differences', () => {
    const {window,document}=boot();
    for (const difference of [
      {...diff,positions:[{...diff.positions[0],quote:'Changed quote'},diff.positions[1]]},
      {...diff,consensus_anchor:'Different anchor'},
      {...diff,factual_check:{checkable:true,question:'Different question'}}
    ]) {
      window.App.sourceVerification.renderCurrent(snapshot,{differencesData:{differences:[difference]}});
      expect(document.querySelector('.contradiction-source-check')).toBeNull();
    }
  });
  it('reattaches after streamed Differences rendering, and clears old results on run changes', () => {
    const {window,document}=boot(); const cards=document.querySelector('#differencesCards'); const markup=cards.innerHTML;
    cards.replaceChildren(); window.App.sourceVerification.renderCurrent(snapshot,options);
    cards.innerHTML=markup; window.App.sourceVerification.refreshDifferences(cards);
    expect(cards.querySelectorAll('.contradiction-source-check')).toHaveLength(1);
    window.App.sourceVerification.renderCurrent(snapshot,options);
    expect(cards.querySelectorAll('.contradiction-source-check')).toHaveLength(1);
    window.App.sourceVerification.renderCurrent(null);
    window.App.sourceVerification.refreshDifferences(cards);
    expect(cards.querySelector('.contradiction-source-check')).toBeNull();
  });
  it('keeps evidence on a historical card when the reader moves its container', () => {
    const {window,document}=boot();
    document.body.insertAdjacentHTML('beforeend','<article class="thread-history-turn"><div class="answer">Old answer</div><div class="thread-history-differences"><article class="diff-card"><h3>Who pays 20 euros?</h3></article></div><div class="report"></div></article><aside id="reader"></aside>');
    const turn=document.querySelector('.thread-history-turn'), body=turn.querySelector('.answer'), report=turn.querySelector('.report');
    window.App.sourceVerification.render(body,report,snapshot,options);
    document.querySelector('#reader').append(turn.querySelector('.thread-history-differences'));
    window.App.sourceVerification.render(body,report,{...snapshot,revision:2},options);
    expect(document.querySelectorAll('#reader .contradiction-source-check')).toHaveLength(1);
    expect(document.querySelector('#differencesCards .contradiction-source-check')).toBeNull();
  });
  it('deduplicates paginated findings by contradiction identity and rejects mismatched versions', async () => {
    vi.useFakeTimers();
    try {
      const {window}=boot(); window.setTimeout=(f,ms)=>setTimeout(f,ms);window.clearTimeout=id=>clearTimeout(id);
      window.fetch=vi.fn().mockResolvedValueOnce({ok:true,json:async()=>({source_verification:snapshot,next_cursor:'next'})})
        .mockResolvedValueOnce({ok:true,json:async()=>({source_verification:{...snapshot,findings:[{...finding,contradiction_id:'c-two'}]}})});
      const onUpdate=vi.fn();
      window.App.sourceVerification.watch({jobId:'job-one',expectedSnapshot:snapshot,isActive:()=>true,onUpdate});
      await vi.advanceTimersByTimeAsync(0);
      expect(onUpdate.mock.calls[0][0].findings).toHaveLength(2);
      window.fetch.mockResolvedValue({ok:true,json:async()=>({source_verification:{...snapshot,answer_version:'wrong'}})});
      const second=vi.fn(); const stop=window.App.sourceVerification.watch({jobId:'job-one',expectedSnapshot:snapshot,isActive:()=>true,onUpdate:second});
      await vi.advanceTimersByTimeAsync(0); expect(second).not.toHaveBeenCalled(); stop();
    } finally {vi.useRealTimers();}
  });
});
