"""Built UI: explicit data selection and confirmation. No real Google requests."""
import json
import pytest
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json
from test_agent_chat_frontend import CATALOG, _choose_mode, _snapshot


@pytest.mark.parametrize("width",[1280,390,320])
def test_selected_calendar_and_exact_confirmation(browser,phase4_server,width):
    context,page=_real_firebase_page(browser,phase4_server,has_touch=width<700)
    cid,chat,aid="a"*32,"b"*32,"c"*32
    confirmed=[];requests=[];visible=[]
    action={"id":aid,"hash":"d"*64,"kind":"calendar_event","status":"pending","account":"owner@example.org","approval_until":"2099-01-01T00:00:00Z",
        "preview":{"operation":"Create event","calendar":"primary","target":"single","before":{},"after":{"summary":"Review vendor offers","start":{"dateTime":"2026-10-20T09:00:00+02:00","timeZone":"Europe/Copenhagen"},"end":{"dateTime":"2026-10-20T10:00:00+02:00","timeZone":"Europe/Copenhagen"},"attendees":[{"email":"reviewer@example.org"}]},"attendees":["reviewer@example.org"],"invitations":"Google will notify all affected attendees."}}
    try:
        page.set_viewport_size({"width":width,"height":900})
        page.route('**/user_status',lambda r:_json(r,{'tier':'pro','is_pro':True,'agent_access':True}))
        page.route('**/usage',lambda r:_json(r,{'is_pro':True,'remaining':100,'total_limit':100}))
        page.route('**/agent/models',lambda r:_json(r,CATALOG))
        page.route('**/agent/budget',lambda r:_json(r,{'token_budget':{'remaining':250000,'limit':250000}}))
        page.route('**/agent/google/connections',lambda r:_json(r,{'configured':True,'connections':[{'id':cid,'email':'owner@example.org','status':'connected','capabilities':['calendar_read','calendar_write']}]}))
        page.route('**/calendars?*',lambda r:_json(r,{'calendars':[{'id':'primary','summary':'Personal calendar','timeZone':'Europe/Copenhagen'}]}))
        page.route('**/chats',lambda r:_json(r,{'chat':{'id':chat}}))
        page.route('**/files',lambda r:_json(r,{'files':[]}))
        page.route('**/actions',lambda r:_json(r,{'actions':visible}))
        def execute(route):
            confirmed.append(route.request.post_data_json);action['status']='succeeded';action['result']={'event_id':'saved'}
            _json(route,{'action':action})
        page.route('**/confirm',execute)
        def agent(route):
            payload=route.request.post_data_json;requests.append(payload);visible.append(action)
            turn={'id':'e'*32,'question':payload['question'],'execution_mode':'agent','status':'completed','consensus':'The proposed meeting is ready for review.'}
            route.fulfill(content_type='text/event-stream',body='event: final\ndata: '+json.dumps({'chat_id':chat,'turn_id':turn['id'],'turn':turn,'response':turn['consensus'],'bookmark_meta':{'id':payload['bookmark_id'],'chat_id':chat,'execution_mode':'agent','query':payload['question']}})+'\n\n')
        page.route('**/agent',agent)
        page.evaluate("async()=>await window.__switchE2EUser('account-a')")
        _choose_mode(page,'agent')
        page.locator('#agentGoogleControls summary').click()
        page.get_by_label('Google account',exact=True).select_option(cid)
        page.get_by_label('Personal calendar · Europe/Copenhagen',exact=True).check()
        page.get_by_label('Use selected calendars',exact=True).check()
        page.get_by_label('I agree to share relevant selected Google information with my chosen models for this request.',exact=True).check()
        page.locator('#questionInput').fill('Prepare a meeting to review the offers')
        page.locator('#sendButton').click()
        expect(page.locator('#agentGoogleActions')).to_contain_text('reviewer@example.org')
        assert requests[0]['google_selection']['calendar_ids']==['primary'] and requests[0]['google_data_consent'] is True
        button=page.get_by_role('button',name='Confirm and execute',exact=True)
        expect(button).to_be_disabled();assert not confirmed
        _snapshot(page,f'calendar-preview-{width}')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        page.get_by_label('I have reviewed this exact change and its recipients.',exact=True).check()
        button.click()
        expect(page.locator('#agentGoogleActions')).to_contain_text('Google confirmed this action.')
        assert confirmed==[{'expected_hash':'d'*64}]
    finally:context.close()


def test_oauth_callback_popup_uses_real_csp_and_authenticated_finish(browser,phase4_server):
    context,page=_real_firebase_page(browser,phase4_server)
    finish=[]
    try:
        page.route('**/user_status',lambda r:_json(r,{'tier':'pro','is_pro':True,'agent_access':True}))
        page.route('**/usage',lambda r:_json(r,{'is_pro':True,'remaining':100,'total_limit':100}))
        page.route('**/agent/models',lambda r:_json(r,CATALOG))
        page.route('**/agent/budget',lambda r:_json(r,{'token_budget':{'remaining':250000,'limit':250000}}))
        page.route('**/agent/google/connections',lambda r:_json(r,{'configured':True,'connections':[]}))
        page.route('**/agent/google/connect',lambda r:_json(r,{'state':'state'*10,'url':phase4_server+'/agent/google/callback?code=fake-code&state='+'state'*10}))
        def complete(route):
            finish.append(route.request.post_data_json);assert route.request.headers.get('authorization','').startswith('Bearer ')
            _json(route,{'connection':{'id':'a'*32,'email':'owner@example.org'}})
        page.route('**/agent/google/finish',complete)
        page.evaluate("async()=>await window.__switchE2EUser('account-a')")
        _choose_mode(page,'agent');page.locator('#agentGoogleControls summary').click()
        with page.expect_response('**/agent/google/finish'):
            page.get_by_role('button',name='Connect Google Calendar',exact=True).click()
        assert finish==[{'state':'state'*10,'code':'fake-code'}]
    finally:context.close()
