"""Contradiction evidence in the real app shell, with isolated fixture data only."""
import pytest
from playwright.sync_api import expect
from test_phase4_frontend import _real_firebase_page, phase4_server  # noqa: F401
from test_model_answer_reader import seed_insights, reader_screenshot


def assert_source_check_fits(result):
    assert result.evaluate("""el => {
      const rect=el.getBoundingClientRect(), style=getComputedStyle(el);
      let left=0, right=innerWidth;
      for(let parent=el.parentElement;parent;parent=parent.parentElement) {
        if(['auto','scroll','hidden','clip'].includes(getComputedStyle(parent).overflowX)) {
          const bounds=parent.getBoundingClientRect();
          left=Math.max(left,bounds.left);right=Math.min(right,bounds.right);
        }
      }
      return rect.left>=left-1 && rect.right<=right+1 && el.scrollWidth<=el.clientWidth+1
        && parseFloat(style.paddingLeft)>=14 && parseFloat(style.paddingRight)>=14
        && parseFloat(style.outlineOffset)<=0 && style.boxShadow.includes('inset');
    }""")


@pytest.mark.parametrize('width', [1440, 390, 320])
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
        if width > 640:
            page.locator('#consensusSourceCheckButton').click()
        else:
            # The compact footer hides its status button; verify the same jump
            # in the narrow reader without changing that independent layout.
            page.evaluate('App.sourceVerification.openResults(document.getElementById("consensusSourceCheckButton"))')
        inspector = page.locator('#answerReaderInspector')
        result = inspector.locator('.contradiction-source-check')
        expect(result).to_be_visible()
        expect(result).to_have_class('contradiction-source-check source-check-result-target')
        expect(result).to_be_focused()
        assert_source_check_fits(result)
        expect(result.locator('.contradiction-source-reason')).to_be_in_viewport()
        reader_screenshot(page, f'source-check-jump-{width}')
        page.evaluate("document.body.classList.add('dark-mode')")
        reader_screenshot(page, f'source-check-jump-dark-{width}')
        page.evaluate("document.body.classList.remove('dark-mode')")
        expect(result).not_to_have_class('contradiction-source-check source-check-result-target', timeout=4000)
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
          check.findings[0]={...check.findings[0],checked:false,state:'unavailable',reason_code:'invalid_output',evidence:[],reason:'',coverage_limited:false};
          check.scope={contradictions:1,checked_contradictions:0,unavailable_contradictions:1};
          App.sourceVerification.renderCurrent(check,{differencesData:ctx.consensus.differencesData});
        }""")
        expect(result).to_contain_text('result could not be validated')
        expect(result.locator('.contradiction-source-status')).to_have_text('No conclusion')
        expect(result.locator('.contradiction-source-guidance')).to_contain_text('Neither position is confirmed')
        expect(result.locator('blockquote')).to_have_count(0)
        expect(result).not_to_contain_text('Different conditions explain')
        page.evaluate('App.sourceVerification.openResults(document.getElementById("consensusSourceCheckButton"))')
        expect(result).to_be_focused()
        expect(result.locator('.contradiction-source-guidance')).to_be_in_viewport()
        assert_source_check_fits(result)
        reader_screenshot(page, f'contradiction-evidence-unavailable-{width}')
        page.evaluate("document.body.classList.add('dark-mode')")
        reader_screenshot(page, f'contradiction-evidence-unavailable-dark-{width}')
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


@pytest.mark.parametrize('width', [1440, 390])
def test_excluded_red_contradiction_is_explained_in_reader(browser, phase4_server, width):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({'width':width,'height':1000})
        seed_insights(page)
        page.evaluate("""() => {
          const ctx=App.runRegistry.visible();
          const diff=ctx.consensus.differencesData.differences[0];
          ctx.consensus.differencesData.differences.splice(1);
          diff.consensus_anchor=ctx.consensus.text;
          diff.factual_check={checkable:false,question:'Which participants are included in the total?',reason:'The analysis treated this as a difference in recommendations.'};
          ctx.consensus.sourceVerification={schema_version:4,check_type:'contradiction_evidence',status:'skipped',
            reason_code:'no_checkable_contradictions',scope:{contradictions:0,checked_contradictions:0},findings:[]};
          window.__excludedOriginal=JSON.stringify(ctx.consensus.sourceVerification);
          App.runRegistry.renderVisible();
        }""")
        expect(page.locator('#consensusAnswerBody .cx-claim')).to_have_count(1)
        expect(page.locator('#consensusSourceCheckStatus')).to_contain_text('Contradiction source checks unavailable')
        if width > 640:
            page.locator('#consensusSourceCheckButton').focus()
            page.keyboard.press('Enter')
        else:
            page.evaluate('App.sourceVerification.openResults(document.getElementById("consensusSourceCheckButton"))')
        result=page.locator('#answerReaderInspector .is-major .contradiction-source-check')
        expect(result).to_be_visible()
        expect(result).to_be_focused()
        expect(result).to_have_class('contradiction-source-check source-check-result-target')
        expect(result.locator('.contradiction-source-reason').first).to_be_in_viewport()
        expect(result).to_contain_text('Not selected for source checking')
        expect(result).to_contain_text('The analysis classified this dispute as not fact-checkable.')
        expect(result).to_contain_text('Original model passages could not be matched.')
        expect(result.locator('a, details')).to_have_count(0)
        assert page.evaluate('JSON.stringify(App.runRegistry.visible().consensus.sourceVerification) === __excludedOriginal')
        assert result.evaluate('el => el.scrollWidth <= el.clientWidth + 1')
        reader_screenshot(page,f'excluded-source-{width}')
        page.locator('#answerReaderClose').click()
        page.emulate_media(reduced_motion='reduce', forced_colors='active')
        page.evaluate('App.sourceVerification.openResults(document.getElementById("consensusSourceCheckButton"))')
        expect(result).to_be_focused()
        expect(result).to_have_css('animation-name', 'none')
        expect(result).to_have_css('outline-style', 'solid')
        expect(result).to_have_css('outline-width', '2px')
        expect(result.locator('.contradiction-source-reason').first).to_be_in_viewport()
        expect(result).not_to_have_class('contradiction-source-check source-check-result-target', timeout=4000)
    finally:
        context.close()


@pytest.mark.parametrize('width', [1440, 390])
def test_agent_answer_follows_its_queued_source_check_until_it_settles(browser, phase4_server, width):
    """The Agent turn ends with a job reference; the page polls it and repaints."""
    import hashlib
    from app.services.chat_store import turn_detail
    from test_agent_chat_frontend import CATALOG
    from test_phase4_frontend import _json
    context, page = _real_firebase_page(browser, phase4_server, has_touch=width < 700)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    anchor = 'The smaller plan includes five seats.'
    text = 'For a team of five, start with the smaller plan.\n\n' + anchor
    digest = hashlib.sha256(text.encode()).hexdigest()
    answers = [{'provider': p, 'provider_label': label, 'model': {'model': model, 'label': name},
                'text': f'{name}: {stance}', 'sources': [{'url': f'https://{p}.example.invalid/plan', 'title': 'Plan page'}]}
               for p, label, model, name, stance in [
                   ('openai', 'OpenAI', 'openai/gpt-5.4-mini', 'GPT-5.4 Mini', 'Five seats are included.'),
                   ('gemini', 'Gemini', 'google/gemini-3.5-flash-lite', 'Gemini 3.5 Flash-Lite', 'Three seats are included.')]]
    diff = {'claim': 'Whether the smaller plan includes five seats', 'consensus_anchor': anchor, 'consensus_anchor_validated': True,
            'type': 'contradiction', 'severity': 'major',
            'factual_check': {'checkable': True, 'question': 'How many seats does the smaller plan include?'},
            'positions': [{'models': ['OpenAI'], 'stance': 'Five seats are included.', 'quote': 'Five seats are included.'},
                          {'models': ['Gemini'], 'stance': 'Three seats are included.', 'quote': 'Three seats are included.'}]}
    job_id = 'a' * 64
    queued = {'schema_version': 4, 'check_type': 'contradiction_evidence', 'job_id': job_id, 'revision': 0,
              'status': 'queued', 'credential_mode': 'server', 'run_id': 'c1', 'answer_version': digest, 'basis_hash': 'basis',
              'scope': {'contradictions': 1, 'checked_contradictions': 0}, 'findings': [], 'documents': [], 'sources': []}
    review = {'status': 'succeeded', 'answer_version': 1, 'answer_hash': digest, 'check_sources': True,
              'versions': [{'id': 1, 'text': text, 'hash': digest, 'status': 'succeeded'}],
              'comparisons': [{'id': 'c1', 'basis_hash': 'basis', 'question': 'Which plan fits a team of five?',
                               'reason': 'Compare seat limits', 'status': 'succeeded', 'answers': answers, 'failed_models': []}],
              'checks': [{'comparison_id': 'c1', 'basis_hash': 'basis', 'answer_hash': digest, 'status': 'succeeded',
                          'differences_data': {'claims': [], 'differences': [diff], 'models_compared': ['OpenAI', 'Gemini']},
                          'source_verification': queued}]}
    turn = turn_detail('b' * 32, {'execution_mode': 'agent', 'status': 'completed', 'question': 'Which plan fits a team of five?',
        'assistant_response': text, 'agent_review': review, 'agent_settings': {'model_id': CATALOG['default_model_id']}}, {})
    finding = {'contradiction_id': 'agent-contradiction', 'difference_index': 0, 'run_id': 'c1', 'answer_version': digest,
               'positions_version': 'agent-positions', 'question': diff['factual_check']['question'], 'consensus_anchor': anchor,
               'positions': [{**pos, 'id': f'P{index + 1}', 'summary': pos['stance']} for index, pos in enumerate(diff['positions'])],
               'checked': True, 'state': 'checked', 'verdict': 'supports_position', 'supported_position_id': 'P1',
               'reason': 'The published plan page lists five seats for the smaller plan.',
               'evidence': [{'source_id': 'Dplan', 'position_id': 'P1', 'quote': 'The smaller plan includes five seats.'}]}
    settled = {**queued, 'revision': 1, 'status': 'complete', 'scope': {'contradictions': 1, 'checked_contradictions': 1},
               'findings': [finding], 'sources': [{'id': 'Dplan', 'url': 'https://openai.example.invalid/plan', 'title': 'Plan page'}]}
    polls, release = [], []
    def respond(route):
        polls.append(route.request.url)
        _json(route, {'source_verification': settled if release else queued, 'next_cursor': None})
    try:
        page.set_viewport_size({'width': width, 'height': 900})
        page.route('**/user_status', lambda r: _json(r, {'tier': 'pro', 'is_pro': True, 'agent_access': True}))
        page.route('**/agent/models', lambda r: _json(r, CATALOG))
        page.route(f'**/api/source-checks/{job_id}*', respond)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.evaluate("turn => App.runRegistry.showSavedView({type:'bookmark'}, {chatId:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', turnId:turn.id, executionMode:'agent', question:turn.question, consensus:turn.consensus, currentTurn:turn})", turn)
        page.evaluate('() => window.exitHeroMode()')
        link = page.locator('.agent-evidence-link[data-section="differences"]')
        expect(link).to_contain_text('Contradictions')
        # The saved turn re-observes its pending job instead of starting a check.
        expect(link.locator('.agent-evidence-note')).to_have_text('checking sources')
        for _ in range(50):
            if polls:
                break
            page.wait_for_timeout(100)
        assert polls and all(job_id in url for url in polls)
        link.click()
        inspector = page.locator('#answerReaderInspector')
        expect(inspector.locator('.diff-card')).to_have_count(1)
        # The next poll settles the job: the open reader and the link follow.
        release.append(True)
        result = inspector.locator('.contradiction-source-check')
        expect(result).to_contain_text('The published plan page lists five seats', timeout=15000)
        expect(link.locator('.agent-evidence-note')).to_have_text('1 settled by sources')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        reader_screenshot(page, f'agent-source-check-settled-{width}')
        assert not errors
    finally:
        context.close()
