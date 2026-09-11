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
    expect(result.querySelector('details').open).toBe(false);
    result.querySelector('details').open=true;
    window.App.sourceVerification.renderCurrent(snapshot, options);
    expect(document.querySelector('.contradiction-source-check details').open).toBe(true);
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
    const {window,document}=boot(); window.App.sourceVerification.renderCurrent({...snapshot,...changes},changes.status === 'skipped' ? {differencesData:{differences:[]}} : options);
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


describe('excluded contradiction visibility', () => {
  const excluded = {exclusion_id:'excluded-one',difference_index:0,run_id:snapshot.run_id,answer_version:snapshot.answer_version,
    consensus_anchor:diff.consensus_anchor,positions:diff.positions,question:diff.factual_check.question,
    reason_code:'unverified_model_positions',reason_codes:['unverified_model_positions']};
  const unchecked = {...snapshot,status:'skipped',findings:[],scope:{contradictions:0,checked_contradictions:0,detected_contradictions:1,excluded_contradictions:1},
    reason_code:'contradiction_inputs_unavailable',exclusions:[excluded]};
  it('shows a technical exclusion on the red card and never claims no contradictions exist', () => {
    const {window,document}=boot();const before=JSON.stringify(unchecked);
    window.App.sourceVerification.renderCurrent(unchecked,options);
    const section=document.querySelector('.diff-card .contradiction-source-check');
    expect(section.textContent).toContain('Not checked');
    expect(section.textContent).toContain('Original model passages could not be matched');
    expect(section.querySelector('details')).toBeNull();
    expect(document.querySelector('#consensusSourceCheckStatus').textContent).toContain('Contradiction source checks unavailable');
    expect(document.body.textContent).not.toContain('No checkable contradictions detected');
    expect(JSON.stringify(unchecked)).toBe(before);
  });
  it('counts excluded contradictions in the displayed total for a mixed result', () => {
    const {window,document}=boot();
    window.App.sourceVerification.renderCurrent({...snapshot,exclusions:[excluded],
      scope:{contradictions:1,checked_contradictions:1,detected_contradictions:2,excluded_contradictions:1}},options);
    expect(document.querySelector('#consensusSourceCheckStatus').textContent).toContain('1 of 2 contradictions checked');
  });
  it('shows classification and technical reasons together without turning them into a source verdict', () => {
    const {window,document}=boot();
    window.App.sourceVerification.renderCurrent({...unchecked,exclusions:[{...excluded,reason_code:'not_factual',
      reason_codes:['not_factual','unverified_model_positions'],reason:'The two models recommend different workflows.'}]},options);
    const section=document.querySelector('.contradiction-source-check');
    expect(section.textContent).toContain('Not selected for source checking');
    expect(section.textContent).toContain('The analysis classified this dispute as not fact-checkable.');
    expect(section.textContent).toContain('Original model passages could not be matched.');
    expect(section.textContent).toContain('different workflows');
    expect(section.textContent).not.toContain('Sources support');
  });
  it('derives only display explanations for old terminal v4 snapshots with missing quote matches', () => {
    const {window,document}=boot();const legacy={...unchecked};delete legacy.exclusions;
    const before=JSON.stringify(legacy);
    window.App.sourceVerification.renderCurrent(legacy,options);
    expect(document.querySelector('.contradiction-source-check').textContent).toContain('Original model passages could not be matched');
    expect(JSON.stringify(legacy)).toBe(before);
    expect(legacy.exclusions).toBeUndefined();
    window.App.sourceVerification.renderCurrent({...legacy,status:'queued'},options);
    expect(document.querySelector('.contradiction-source-check')).toBeNull();
    window.App.sourceVerification.renderCurrent({...legacy,status:'disabled'},options);
    expect(document.querySelector('.contradiction-source-check')).toBeNull();
  });
  it('does not attach exclusions to different raw positions, question, anchor, or answer', () => {
    const {window,document}=boot();
    for(const changed of [
      {...excluded,positions:[{...diff.positions[0],quote_models:['Different model']},diff.positions[1]]},
      {...excluded,question:'Other question'}, {...excluded,consensus_anchor:'Other anchor'}, {...excluded,answer_version:'Other version'}
    ]) {
      window.App.sourceVerification.renderCurrent({...unchecked,exclusions:[changed]},options);
      expect(document.querySelector('.contradiction-source-check')).toBeNull();
    }
  });
  it('explains an excluded contradiction in the public fallback when no Differences panel exists', () => {
    const {window,document}=boot();
    document.getElementById('differencesCards').remove();
    window.App.sourceVerification.renderCurrent(unchecked,options);
    expect(document.querySelector('#sourceVerificationReport .diff-card .contradiction-source-check').textContent).toContain('Not checked');
  });
});


describe('precise source-judge rejection diagnostics', () => {
  const rejection = {...finding,checked:false,state:'unavailable',reason_code:'evidence_mismatch',evidence:[],reason:'',
    validation_errors:[{code:'quote_not_in_original',evidence_index:1,source_id:'S1',position_id:'P2'}]};
  it('shows the exact safe rejection reason with its known source and model position', () => {
    const {window,document}=boot();
    const value={...snapshot,findings:[rejection]};const before=JSON.stringify(value);
    window.App.sourceVerification.renderCurrent(value,options);
    const result=document.querySelector('.contradiction-source-check');
    expect(result.textContent).toContain('Why this check was rejected:');
    expect(result.textContent).toContain('Passage 2: The cited text could not be matched to the original source document.');
    expect(result.textContent).toContain('Position: Anthropic.');
    expect(result.querySelector('a').href).toBe('https://example.com/prices');
    expect(result.querySelector('a').rel).toBe('noopener noreferrer');
    expect(result.querySelector('blockquote, details')).toBeNull();
    expect(JSON.stringify(value)).toBe(before);
  });
  it('never displays rejected quotes, explanations or a positive verdict even with contradictory checked metadata', () => {
    const {window,document}=boot();
    window.App.sourceVerification.renderCurrent({...snapshot,findings:[{...finding,validation_errors:rejection.validation_errors}]},options);
    const result=document.querySelector('.contradiction-source-check');
    expect(result.dataset.checkState).toBe('unavailable');
    expect(result.textContent).not.toContain(finding.reason);
    expect(result.textContent).not.toContain(finding.evidence[0].quote);
    expect(result.textContent).not.toContain('Different conditions explain');
    expect(result.querySelector('blockquote, details')).toBeNull();
  });
  it.each([
    ['quote_not_in_passages','could not be found in the passages supplied to the judge'],
    ['date_not_in_source','evidence date could not be found in the source'],
    ['source_position_mismatch','source was not assigned to that model position'],
    ['missing_required_evidence','lacked the original evidence required'],
    ['duplicate_finding','more than one result for this contradiction'],
    ['missing_finding','did not return a result for this contradiction'],
    ['invalid_reason','did not provide a valid explanation'],
    ['quote_total_limit','combined evidence passages exceeded'],
  ])('explains %s without inventing quote content', (code,text) => {
    const {window,document}=boot();
    window.App.sourceVerification.renderCurrent({...snapshot,findings:[{...rejection,validation_errors:[{code}]}]},options);
    expect(document.querySelector('.contradiction-source-validation').textContent).toContain(text);
  });
  it('does not create links for unknown, ambiguous or unsafe source identities and ignores raw diagnostics', () => {
    const {window,document}=boot();
    for(const sources of [snapshot.sources,[{id:'S1',url:'javascript:alert(1)'}],[...snapshot.sources,...snapshot.sources]]) {
      const errors=[{code:'invalid_source',source_id:sources===snapshot.sources?'unplanned':'S1',position_id:'<script>',quote:'REJECTED PRIVATE QUOTE',message:'UNTRUSTED MESSAGE'},
        {code:'<script>alert(1)</script>',evidence_index:-1}];
      window.App.sourceVerification.renderCurrent({...snapshot,sources,findings:[{...rejection,validation_errors:errors}]},options);
      const result=document.querySelector('.contradiction-source-check');
      expect(result.querySelector('a,script')).toBeNull();
      expect(result.textContent).not.toContain('REJECTED PRIVATE QUOTE');
      expect(result.textContent).not.toContain('UNTRUSTED MESSAGE');
      expect(result.textContent).not.toContain('alert(1)');
      expect(result.textContent).toContain('no more specific explanation is available');
    }
  });
  it('keeps legacy evidence_mismatch honest when no detailed rejection was saved', () => {
    const {window,document}=boot();const legacy={...rejection};delete legacy.validation_errors;
    window.App.sourceVerification.renderCurrent({...snapshot,findings:[legacy]},options);
    const result=document.querySelector('.contradiction-source-check');
    expect(result.textContent).toContain('Evidence quotes could not be verified');
    expect(result.textContent).toContain('No more specific rejection reason was saved');
    expect(result.querySelector('.contradiction-source-validation-errors')).toBeNull();
  });
  it('bounds rejection diagnostics and reports fallback provenance without claiming successful verification', () => {
    const {window,document}=boot();
    window.App.sourceVerification.renderCurrent({...snapshot,status:'failed',runtime:{model:'provider/fallback-model',fallback_used:true,
      model_attempts:[{model:'provider/primary',status:'failed',error_code:'timeout'},{model:'provider/fallback-model',status:'succeeded'}]},
      findings:[{...rejection,validation_errors:Array.from({length:20},()=>({code:'invalid_reason'}))}]},options);
    const result=document.querySelector('.contradiction-source-check');
    expect(result.querySelectorAll('.contradiction-source-validation-errors li')).toHaveLength(12);
    expect(result.textContent).toContain('Source-check model: provider/fallback-model (fallback)');
    expect(result.textContent).not.toContain('Checked with');
    window.App.sourceVerification.renderCurrent({...snapshot,runtime:{model:'provider/primary',fallback_used:false},findings:[rejection]},options);
    expect(document.querySelector('.contradiction-source-check').textContent).not.toContain('Source-check model:');
  });
});
