"""Contradiction evidence in the real app shell, with isolated fixture data only."""
import pytest
from playwright.sync_api import expect
from test_phase4_frontend import _real_firebase_page, phase4_server  # noqa: F401
from test_model_answer_reader import seed_insights, reader_screenshot


@pytest.mark.parametrize('width', [1440, 390])
def test_contradiction_evidence_reader(browser, phase4_server, width):
    context, page = _real_firebase_page(browser, phase4_server)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({'width': width, 'height': 1000})
        seed_insights(page)
        page.evaluate("""() => {
          const ctx = App.runRegistry.visible();
          const diff = ctx.consensus.differencesData.differences[0];
          ctx.consensus.differencesData.differences.splice(1);
          Object.assign(diff, {consensus_anchor: ctx.consensus.text,
            factual_check:{checkable:true,question:'Does the participant total count registrations or finishers?'}});
          const finding = {contradiction_id:'fixture-contradiction',difference_index:0,
            run_id:ctx.runId,answer_version:'fixture-answer',positions_version:'fixture-positions',
            question:diff.factual_check.question,consensus_anchor:diff.consensus_anchor,
            positions:diff.positions.map((pos,index)=>({...pos,id:'P'+(index+1),summary:pos.stance})),
            checked:true,state:'checked',verdict:'conditions_explain',
            reason:'The registration list and finishers list count different groups. Both totals can be accurate for their stated scope.',
            coverage_limited:true,
            evidence:[{source_id:'Dregistration',position_id:'P1',quote:'The registration list records 2,000 registered participants across all age groups. Registration totals include competitors who did not start or did not finish the event.',date:'2026-09-01',scope:'Registered participants',limitations:'Registration does not establish participation or completion.'},
              {source_id:'Dresults',position_id:'P2',quote:'The final results contain 1,800 finishers who completed the full course. Withdrawals and non-starters are excluded from this total.',date:'2026-09-07',scope:'Finishers only',limitations:'Provisional timing corrections may change the result.'}]};
          ctx.consensus.sourceVerification = {schema_version:4,check_type:'contradiction_evidence',
            run_id:ctx.runId,answer_version:'fixture-answer',status:'complete',
            scope:{contradictions:1,checked_contradictions:1},findings:[finding],sources:[
              {id:'Dregistration',url:'https://registration.example.invalid/participants',title:'Official participant registration list'},
              {id:'Dresults',url:'https://results.example.invalid/report',title:'Official race results and finishing times'}]};
          App.runRegistry.renderVisible();
        }""")
        page.locator('#consensusDifferencesTab').click()
        inspector = page.locator('#answerReaderInspector')
        result = inspector.locator('.contradiction-source-check')
        expect(result).to_be_visible()
        expect(result).to_contain_text('Different conditions explain the disagreement')
        expect(result.locator('blockquote')).to_have_count(2)
        expect(result.locator('a')).to_have_count(2)
        expect(result).to_contain_text('Some sources were omitted')
        expect(page.locator('#consensusSourcesTab')).to_have_attribute('data-check-state', '')
        result.locator('.contradiction-source-evidence-details > summary').click()
        result.scroll_into_view_if_needed()
        assert result.evaluate('el => el.scrollWidth <= el.clientWidth + 1')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        reader_screenshot(page, f'contradiction-evidence-{width}')
        page.evaluate("""() => {
          const ctx=App.runRegistry.visible();
          const check=ctx.consensus.sourceVerification;
          check.findings[0]={...check.findings[0],checked:false,state:'unavailable',reason_code:'evidence_mismatch',evidence:[],reason:''};
          check.scope={contradictions:1,checked_contradictions:0,unavailable_contradictions:1};
          App.sourceVerification.renderCurrent(check,{differencesData:ctx.consensus.differencesData});
        }""")
        expect(result).to_contain_text('Evidence quotes could not be verified')
        expect(result.locator('blockquote')).to_have_count(0)
        expect(result).not_to_contain_text('Different conditions explain')
        reader_screenshot(page, f'contradiction-evidence-unavailable-{width}')
        assert not errors
    finally:
        context.close()


@pytest.mark.parametrize('check_sources', [True, False])
def test_new_consensus_stream_preserves_claims_and_checks_only_major_contradiction(browser, phase4_server, check_sources):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script="localStorage.setItem('consensio.consensusHighlightMode.v1','all')")
    errors=[]
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.evaluate("""enabled => {
          const registry=App.runRegistry;
          const source={id:'S1',url:'https://example.invalid/prices',title:'Original source'};
          const run=registry.create({question:'What does the plan cost?',config:{agentMode:true,checkSources:enabled,
            consensusModel:'Gemini',providers:[{provider:'OpenAI',modelLabel:'OpenAI'},{provider:'Gemini',modelLabel:'Gemini'}]}});
          run.chatSession=null;run.evidenceSources=[source];
          run.modelResults={OpenAI:{status:'complete',text:'20 euros [S1]',sources:[source]},Gemini:{status:'complete',text:'30 euros [S1]',sources:[source]}};
          registry.setStatus(run.runId,'running');window.__v4Run=run;
          window.__v4Text='The plan costs 20 euros. The list contains [1]. Both models describe a monthly subscription.';
          const diff={claim:'The plan price',consensus_anchor:'The plan costs 20 euros.',type:'contradiction',severity:'major',
            factual_check:{checkable:true,question:'What is the monthly price?'},positions:[
              {models:['OpenAI'],stance:'20 euros',quote:'20 euros'},{models:['Gemini'],stance:'30 euros',quote:'30 euros'}]};
          window.__v4Differences={models_compared:['OpenAI','Gemini'],claims:[{anchor:'Both models describe a monthly subscription.',agree:['OpenAI','Gemini'],dissent:[],coverage:'supported'}],differences:[diff,
            {claim:'Different emphasis',type:'emphasis',positions:[{models:['OpenAI'],stance:'Cost focus'},{models:['Gemini'],stance:'Flexibility focus'}]}]};
          window.__v4Finding={contradiction_id:'v4-test',run_id:run.runId,answer_version:'v4-answer',positions_version:'v4-positions',difference_index:0,
            question:diff.factual_check.question,consensus_anchor:diff.consensus_anchor,
            positions:diff.positions.map((pos,i)=>({...pos,id:'P'+(i+1),summary:pos.stance})),checked:true,state:'checked',verdict:'supports_position',supported_position_id:'P1',reason:'The current price list gives this monthly price.',
            evidence:[{source_id:'Dprice',position_id:'P1',quote:'The monthly price is 20 euros.',scope:'Monthly plan'}]};
          window.__v4Snapshot={schema_version:4,check_type:'contradiction_evidence',run_id:run.runId,answer_version:'v4-answer',status:enabled?'queued':'disabled',
            ...(enabled?{job_id:'v4-source-job',revision:0,credential_mode:'server'}:{}),scope:{contradictions:enabled?1:0,checked_contradictions:0},findings:[],sources:[{id:'Dprice',url:source.url,title:source.title}]};
          const originalFetch=window.fetch;
          window.__v4Resolvers=[];
          window.fetch=(url,options)=>{
            if(String(url).includes('/api/source-checks/v4-source-job')) return new Promise(resolve=>window.__v4Resolvers.push(resolve));
            if(url==='/consensus')return Promise.resolve(new Response(new ReadableStream({start(controller){window.__v4Stream=controller;}}),{headers:{'content-type':'text/event-stream'}}));
            return originalFetch(url,options);
          };
          window.__v4Send=(name,data)=>window.__v4Stream.enqueue(new TextEncoder().encode('event: '+name+'\\ndata: '+JSON.stringify(data)+'\\n\\n'));
          window.__v4Completion=App.executeConsensusRun(run);
        }""", check_sources)
        page.wait_for_function('Boolean(window.__v4Stream)')
        page.evaluate("""() => {
          __v4Send('consensus.final',{text:__v4Text});
          __v4Send('differences.final',{differences:'Price disagreement and different emphasis.',differences_data:__v4Differences});
        }""")
        expect(page.locator('#consensusAnswerBody .cx-claim')).to_have_count(2)
        expect(page.locator('.diff-card')).to_have_count(2)
        expect(page.locator('#consensusAnswerBody .src-ref')).to_have_count(0)
        expect(page.locator('#consensusAnswerBody')).to_contain_text('[1]')
        page.evaluate("""() => {
          window.__v4Claim=document.querySelector('#consensusAnswerBody .cx-claim');
          window.__v4Cards=[...document.querySelectorAll('.diff-card')];
          __v4Send('sources.final',{source_verification:__v4Snapshot});
          __v4Send('final',{consensus_response:__v4Text,differences:'Price disagreement and different emphasis.',differences_data:__v4Differences,source_verification:__v4Snapshot,chat_replayed:true});
          __v4Stream.close();
        }""")
        page.wait_for_function("window.__v4Run.status === 'succeeded'")
        assert page.evaluate("__v4Claim===document.querySelector('#consensusAnswerBody .cx-claim') && __v4Cards.every((card,index)=>card===document.querySelectorAll('.diff-card')[index])")
        assert page.evaluate("__v4Run.modelResults.OpenAI.text")=='20 euros [S1]'
        if check_sources:
            page.wait_for_function('__v4Resolvers.length===1')
            page.evaluate("""() => {
              const checked={...__v4Snapshot,revision:1,status:'complete',scope:{contradictions:1,checked_contradictions:1},findings:[__v4Finding]};
              __v4Resolvers.shift()(new Response(JSON.stringify({source_verification:checked,next_cursor:null}),{headers:{'content-type':'application/json'}}));
            }""")
            expect(page.locator('.is-major .contradiction-source-check')).to_have_count(1)
            expect(page.locator('.is-emphasis .contradiction-source-check')).to_have_count(0)
            assert page.evaluate("__v4Claim===document.querySelector('#consensusAnswerBody .cx-claim') && __v4Cards.every((card,index)=>card===document.querySelectorAll('.diff-card')[index])")
        else:
            expect(page.locator('#sourceVerificationReport')).to_contain_text('Contradiction source checks disabled')
            expect(page.locator('.contradiction-source-check')).to_have_count(0)
        assert not errors
    finally:
        context.close()
