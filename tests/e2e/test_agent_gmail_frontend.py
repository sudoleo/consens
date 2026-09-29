"""Built mobile/desktop Gmail flow; all external IO is intercepted."""
import io,json
import pytest
from pypdf import PdfWriter
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server,_real_firebase_page,_json
from test_agent_chat_frontend import CATALOG,_choose_mode,_snapshot


@pytest.mark.parametrize('width',[1280,390,320])
def test_gmail_draft_revision_document_download_and_restoration(browser,phase4_server,width):
    context,page=_real_firebase_page(browser,phase4_server,has_touch=width<700)
    cid,chat='a'*32,'b'*32;confirmed=[];requests=[];actions=[];files=[]
    out=io.BytesIO();pdf=PdfWriter();pdf.add_blank_page(595,842);pdf.write(out);raw=out.getvalue()
    try:
        page.set_viewport_size({'width':width,'height':900})
        for endpoint,data in [('user_status',{'tier':'pro','is_pro':True,'agent_access':True}),('usage',{'is_pro':True,'remaining':100,'total_limit':100}),('agent/models',CATALOG),('agent/budget',{'token_budget':{'remaining':250000,'limit':250000}})]:
            page.route('**/'+endpoint,(lambda payload: lambda r:_json(r,payload))(data))
        page.route('**/agent/google/connections',lambda r:_json(r,{'configured':True,'connections':[{'id':cid,'email':'owner@example.org','status':'connected','capabilities':['gmail_read','gmail_send']}]}))
        page.route('**/chats',lambda r:_json(r,{'chat':{'id':chat}}))
        page.route('**/files',lambda r:_json(r,{'files':files}))
        evidence={'id':'e'*32,'kind':'gmail_message','account':'owner@example.org','message_id':'original1','thread_id':'thread1','headers':{'from':'Supplier <supplier@example.org>','to':'owner@example.org','subject':'Offers <script>untrusted</script>','date':'2026-09-21'}}
        page.route('**/actions',lambda r:_json(r,{'actions':actions,'evidence':[evidence] if actions else []}))
        def download(route):
            assert route.request.headers.get('authorization','').startswith('Bearer ')
            route.fulfill(body=raw,content_type='application/pdf',headers={'Content-Disposition':'attachment; filename="Decision.pdf"'})
        page.route('**/agent/chats/*/files/*',download)
        def execute(route):
            confirmed.append(route.request.post_data_json);actions[-1]['status']='succeeded';actions[-1]['result']={'message_id':'sent1'}
            _json(route,{'action':actions[-1]})
        page.route('**/confirm',execute)
        def run(route):
            payload=route.request.post_data_json;requests.append(payload);version=len(requests)
            file={'id':str(version)*32,'name':f'Decision-v{version}.pdf','mime':'application/pdf','size':len(raw),'status':'ready','kind':'document','document_id':'d'*32,'version':version,'source_file_ids':[],'warnings':[]}
            files.append(file)
            if actions:actions[-1]['status']='superseded'
            actions.append({'id':str(version+3)*32,'hash':str(version+3)*64,'kind':'gmail_send','status':'pending','account':'owner@example.org','approval_until':'2099-01-01T00:00:00Z',
                'preview':{'operation':'Send email','draft_location':'Saved in Consens; not sent','from':'owner@example.org','to':['buyer@example.org'],'cc':[],'bcc':['private@example.org'],'subject':'Re: Offers',
                    'body':'Please review the decision.' if version==1 else 'Please review the revised plan for Monday.','attachments':[file],'send_authorized':True,
                    'reply':{'from':'Supplier <supplier@example.org>','subject':'Offers','message_id':'original1','thread_id':'thread1'}}})
            turn={'id':str(version+6)*32,'question':payload['question'],'execution_mode':'agent','status':'completed','consensus':'The document and unsent email draft are ready for your review.'}
            route.fulfill(content_type='text/event-stream',body='event: final\ndata: '+json.dumps({'chat_id':chat,'turn_id':turn['id'],'turn':turn,'response':turn['consensus'],'bookmark_meta':{'id':payload['bookmark_id'],'chat_id':chat,'execution_mode':'agent','query':payload['question']}})+'\n\n')
        page.route('**/agent',run)
        page.evaluate("async()=>await window.__switchE2EUser('account-a')")
        _choose_mode(page,'agent');page.locator('#agentGoogleControls summary').click()
        page.get_by_label('Google account',exact=True).select_option(cid)
        page.get_by_label('Use Gmail for this request',exact=True).check()
        consent=page.get_by_label('I agree to share relevant selected Google information with my chosen models for this request.',exact=True)
        consent.check();page.locator('#questionInput').fill('Compare the offers, create a decision brief and prepare an email with the PDF.')
        page.locator('#sendButton').click()
        expect(page.locator('#agentGoogleActions')).to_contain_text('Decision-v1.pdf')
        assert requests[0]['google_selection']['gmail'] is True and requests[0]['google_selection']['calendar'] is False
        expect(consent).not_to_be_checked();assert not confirmed
        expect(page.get_by_role('button',name='Confirm and execute',exact=True)).to_be_disabled()
        with page.expect_download() as download_info:page.get_by_role('button',name='Review attachment',exact=True).click()
        assert download_info.value.failure() is None
        page.locator('#questionInput').fill('Revise the plan for Monday and update the email attachment.');consent.check()
        page.locator('#sendButton').click()
        expect(page.locator('#agentGoogleActions')).to_contain_text('Decision-v2.pdf')
        expect(page.get_by_label('Created documents and versions',exact=True)).to_contain_text('version 2')
        expect(page.locator('#agentGoogleActions')).to_contain_text('superseded')
        card=page.locator('.agent-action-card').filter(has_text='revised plan for Monday')
        expect(card.get_by_role('button',name='Confirm and execute',exact=True)).to_be_disabled()
        # A restored card always starts unapproved, even if its saved draft is unchanged.
        page.evaluate("async chat=>{document.getElementById('agentGoogleActions').replaceChildren();await App.agentGoogle.refreshActions(chat,true)}",chat)
        expect(card).to_contain_text('private@example.org')
        page.locator('#agentGoogleActions details summary').click()
        expect(page.locator('#agentGoogleActions')).to_contain_text('supplier@example.org')
        assert page.locator('#agentGoogleActions script').count()==0
        _snapshot(page,f'gmail-preview-{width}')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        card.get_by_label('I have reviewed this exact change and its recipients.',exact=True).check()
        card.get_by_role('button',name='Confirm and execute',exact=True).click()
        expect(card).to_contain_text('Google confirmed this action.')
        assert confirmed==[{'expected_hash':'5'*64}]
    except Exception:
        _snapshot(page,f'gmail-failure-{width}')
        print(page.evaluate("() => ({classes:document.body.className,question:document.getElementById('questionInput').value,hidden:document.getElementById('agentGoogleControls').hidden,open:document.querySelector('#agentGoogleControls details').open,rect:document.getElementById('agentGoogleControls').getBoundingClientRect().toJSON()})"),flush=True)
        raise
    finally:context.close()
