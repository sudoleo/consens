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
