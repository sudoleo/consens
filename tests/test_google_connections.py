from datetime import timedelta
import json
from urllib.parse import parse_qs, urlparse
from cryptography.fernet import Fernet
import pytest
from app.services.google_connections import GoogleConnections, GoogleError, SCOPES, TOKEN_URL, now, sha
from test_agent_runs import Database


class FakeWire:
    def __init__(self):
        self.calls, self.handler = [], lambda method, url, kwargs: {}
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.handler(method, url, kwargs)


@pytest.fixture
def google(monkeypatch):
    # Writing back is off by default; these fixtures keep the dormant write
    # path covered. The read-only installation has its own tests below.
    for key, value in {"GOOGLE_INTEGRATIONS_ENABLED":"1", "GOOGLE_CLIENT_ID":"test-client", "GOOGLE_CLIENT_SECRET":"secret-client",
        "GOOGLE_REDIRECT_URI":"https://consens.example/agent/google/callback", "GOOGLE_TOKEN_KEYS":Fernet.generate_key().decode(),
        "GOOGLE_WRITES_ENABLED":"1"}.items():
        monkeypatch.setenv(key, value)
    return GoogleConnections(Database(), FakeWire())


def connection(service, uid="owner", *, expired=False, caps=None):
    identifier=sha("google-subject")[:32]
    capabilities=caps or ["calendar_read","calendar_write"]
    value={"access_token":"private-access", "refresh_token":"private-refresh", "expires_at":(now()+timedelta(seconds=-1 if expired else 3600)).isoformat()}
    service.ref(uid,identifier).set({"id":identifier,"email":"owner@example.org","status":"connected","revision":"revision-one",
        "credentials":service.seal(uid,identifier,value),"scopes":[scope for cap in capabilities for scope in SCOPES[cap]],"capabilities":capabilities})
    return identifier


def test_oauth_state_pkce_browser_owner_and_incremental_scopes(google, monkeypatch):
    data,browser=google.start("owner",["calendar_read"])
    query=parse_qs(urlparse(data["url"]).query)
    assert query["include_granted_scopes"]==["true"] and query["code_challenge_method"]==["S256"]
    assert "gmail" not in query["scope"][0] and "calendar.events" not in query["scope"][0]
    for uid,cookie in [("other",browser),("owner","wrong-browser")]:
        with pytest.raises(GoogleError,match="session"):
            google.finish(uid,data["state"],"code",cookie)
    token={"access_token":"new-access", "refresh_token":"new-refresh", "id_token":"signed", "scope":" ".join(SCOPES["calendar_read"]),"expires_in":3600}
    google.wire.handler=lambda *_:token
    monkeypatch.setattr(google,"identity",lambda *_:{"sub":"google-subject","email":"owner@example.org"})
    result=google.finish("owner",data["state"],"code",browser)
    assert result["capabilities"]==["calendar_read"]
    assert "new-access" not in json.dumps(list(google.db.documents.values())) and "new-refresh" not in json.dumps(result)
    sent=google.wire.calls[-1][2]["data"]
    import base64,hashlib
    assert base64.urlsafe_b64encode(hashlib.sha256(sent["code_verifier"].encode()).digest()).decode().rstrip("=")==query["code_challenge"][0]
    with pytest.raises(GoogleError): google.finish("owner",data["state"],"code",browser)


def test_refresh_preserves_refresh_token_and_hides_credentials(google):
    identifier=connection(google,expired=True)
    google.wire.handler=lambda method,url,kwargs: {"access_token":"fresh-access","expires_in":3600} if url==TOKEN_URL else {"items":[]}
    assert google.api("owner",identifier,"calendar_read","GET","/calendar/v3/users/me/calendarList")=={"items":[]}
    assert len(google.wire.calls)==2
    encrypted=google.ref("owner",identifier).get().to_dict()["credentials"]
    assert google.unseal("owner",identifier,encrypted)["refresh_token"]=="private-refresh"
    assert "credentials" not in google.list("owner")[0]
    with pytest.raises(GoogleError): google.get("other",identifier)
    with pytest.raises(GoogleError): google.unseal("other",identifier,encrypted)
    with pytest.raises(GoogleError): google.api("owner",identifier,"gmail_send","GET","/calendar/v3/users/me/calendarList")


def test_revoked_refresh_and_api_credentials_require_reauthorization(google):
    identifier=connection(google,expired=True)
    google.wire.handler=lambda *_: (_ for _ in ()).throw(GoogleError("revoked",401))
    with pytest.raises(GoogleError): google.access_token("owner",identifier,"calendar_read")
    assert google.ref("owner",identifier).get().to_dict()["status"]=="reauthorize"
    assert not google.ref("owner",identifier).get().to_dict()["credentials"]
    connection(google)
    with pytest.raises(GoogleError): google.api("owner",identifier,"calendar_read","GET","/calendar/v3/users/me/calendarList")
    assert google.list("owner")[0]["status"]=="reauthorize"


def test_disconnect_during_refresh_never_restores_access(google):
    identifier=connection(google,expired=True)
    def refresh(method,url,kwargs):
        google.ref("owner",identifier).set({"id":identifier,"email":"owner@example.org","status":"disconnected","revision":"new","capabilities":[]})
        return {"access_token":"fresh","expires_in":3600}
    google.wire.handler=refresh
    with pytest.raises(GoogleError): google.access_token("owner",identifier,"calendar_read")
    assert google.list("owner")[0]["status"]=="disconnected"


def test_disconnect_invalidates_pending_oauth_and_account_fence(google,monkeypatch):
    identifier=connection(google)
    data,browser=google.start("owner",["calendar_write"],connection_id=identifier)
    google.disconnect("owner",identifier)
    assert not (google.ref("owner",identifier).get().to_dict() or {}).get("credentials")
    google.wire.handler=lambda *_:{"access_token":"x","refresh_token":"y","id_token":"z","scope":" ".join(SCOPES["calendar_write"])}
    monkeypatch.setattr(google,"identity",lambda *_:{"sub":"google-subject","email":"owner@example.org"})
    with pytest.raises(GoogleError,match="changed"):
        google.finish("owner",data["state"],"code",browser)
    google.db.collection("account_deletion_jobs").document("owner").set({"status":"pending"})
    from app.services.persistence_guard import AccountDeletionInProgress
    with pytest.raises(AccountDeletionInProgress): google.start("owner",["calendar_read"])


def test_real_signed_identity_rejects_wrong_nonce_and_audience(google):
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    public=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()));public["kid"]="test"
    google.wire.handler=lambda *_:{"keys":[public]}
    claims={"iss":"https://accounts.google.com","aud":"test-client","sub":"user","email":"a@example.org","email_verified":True,"nonce":"expected","exp":int((now()+timedelta(minutes=5)).timestamp())}
    encoded=jwt.encode(claims,key,algorithm="RS256",headers={"kid":"test"})
    assert google.identity(encoded,"expected")["sub"]=="user"
    with pytest.raises(GoogleError): google.identity(encoded,"wrong")
    claims["azp"]="other-client"
    with pytest.raises(GoogleError): google.identity(jwt.encode(claims,key,algorithm="RS256",headers={"kid":"test"}),"expected")
    del claims["azp"]
    claims["aud"]="other-app"
    with pytest.raises(GoogleError): google.identity(jwt.encode(claims,key,algorithm="RS256",headers={"kid":"test"}),"expected")


def test_api_daily_quota_and_oauth_access_log_redaction(google):
    identifier=connection(google)
    google.db.collection("users").document("owner").collection("chat_state").document("google_quota").set({"day":now().date().isoformat(),"count":500})
    with pytest.raises(GoogleError,match="limit"):
        google.api("owner",identifier,"calendar_read","GET","/calendar/v3/users/me/calendarList")
    assert not google.wire.calls
    import logging
    from app.core.observability import OAuthAccessFilter
    record=logging.LogRecord("uvicorn.access",20,"",0,'%s %s %s',("GET","/agent/google/callback?code=private-code&state=private-state","200"),None)
    OAuthAccessFilter().filter(record)
    assert "private-code" not in record.getMessage() and "private-state" not in record.getMessage()


def test_model_routing_requires_zdr_without_collection_and_keeps_optional_allowlists(google,monkeypatch):
    from dataclasses import replace
    from app.services.google_connections import restricted_model
    from app.services.llm.agent_client import AgentModel
    model=AgentModel()
    # Default: every model, but each call needs a zero-retention endpoint that
    # never collects prompts; existing provider routing is kept, not dropped.
    pinned=replace(model,request_config={**model.request_config,'provider':{'order':['azure'],'zdr':False,'data_collection':'allow'}})
    assert restricted_model(pinned).request_config['provider']=={'order':['azure'],'zdr':True,'data_collection':'deny'}
    assert restricted_model(model).request_config['provider']=={'zdr':True,'data_collection':'deny'}
    # Operators can narrow it: a model list fails closed, a host list pins hosting.
    monkeypatch.setenv('GOOGLE_ALLOWED_MODEL_IDS','other/model')
    with pytest.raises(GoogleError,match="not approved"): restricted_model(model)
    monkeypatch.setenv('GOOGLE_ALLOWED_MODEL_IDS',model.model)
    monkeypatch.setenv('GOOGLE_ALLOWED_PROVIDERS','reviewed-host')
    restricted=restricted_model(model)
    assert restricted.request_config['provider']=={'zdr':True,'data_collection':'deny','only':['reviewed-host'],'allow_fallbacks':False}


def test_google_routing_reaches_comparison_synthesis_and_judges(google,monkeypatch):
    from test_agent_comparison import Script, make_loop
    from app.services.agent_runs import AgentRunStore
    from app.services.llm.agent_client import agent_models
    from test_agent_runs import UID
    monkeypatch.setenv('GOOGLE_ALLOWED_MODEL_IDS',','.join(model.model for model,_ in agent_models()))
    monkeypatch.setenv('GOOGLE_ALLOWED_PROVIDERS','reviewed-host')
    script=Script();original=script.factory;calls=[]
    def factory():
        completion=original();stream=completion.stream
        def recorded(**kwargs):
            calls.append(kwargs)
            yield from stream(**kwargs)
        completion.stream=recorded
        return completion
    script.factory=factory
    loop=make_loop(AgentRunStore(google.db),script)
    loop.google_data_consent=True
    loop.store._chat_ref(UID,loop.chat_id).update({'google_data':True})
    list(loop.run())
    assert len(calls)>=6
    assert all(call['model'].request_config['provider']['only']==['reviewed-host'] for call in calls)
    assert all(all(tool.get('type')=='function' for tool in call['tools']) for call in calls)


def test_api_401_keeps_sealed_grant_so_disconnect_can_revoke(google):
    identifier=connection(google)
    google.wire.handler=lambda *_: (_ for _ in ()).throw(GoogleError("unauthorized",401))
    with pytest.raises(GoogleError):
        google.api("owner",identifier,"calendar_read","GET","/calendar/v3/users/me/calendarList")
    stored=google.ref("owner",identifier).get().to_dict()
    assert stored["status"]=="reauthorize" and stored["credentials"]
    with pytest.raises(GoogleError): google.access_token("owner",identifier,"calendar_read")
    google.wire.handler=lambda *_: {}
    assert google.disconnect("owner",identifier)["provider_revoked"] is True
    assert google.wire.calls[-1][2]["data"]["token"]=="private-refresh"


def test_account_deletion_revokes_google_grants_before_deleting_them(google, monkeypatch):
    from app.services import account_deletion
    identifier=connection(google)
    monkeypatch.setattr("app.services.google_connections.Wire", lambda: google.wire)
    google.db.collection("account_deletion_jobs").document("owner").set({"status":"pending"})
    account_deletion.FirestoreAccountDeletion(google.db)._delete_user_subcollections("owner")
    assert any(url=="https://oauth2.googleapis.com/revoke" and kwargs["data"]["token"]=="private-refresh"
               for _,url,kwargs in google.wire.calls)
    assert not google.ref("owner",identifier).get().exists


def test_chat_deletion_removes_proposed_actions(google):
    chat=google.chats.create_chat("owner",execution_mode="agent")["id"]
    action=google.chats._chat_ref("owner",chat).collection("actions").document("a"*32)
    action.set({"id":"a"*32,"payload":{"summary":"private meeting","attendees":["x@example.org"]}})
    google.chats.delete_chat("owner",chat)
    assert not action.get().exists


def test_non_agent_users_can_list_and_disconnect_but_not_connect(google, monkeypatch):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from app.api.routers import agent_google as router
    from app.core.rate_limit import limiter
    identifier=connection(google)
    monkeypatch.setattr(router,"db_firestore",google.db)
    monkeypatch.setattr(router,"_chat_uid",lambda request:"owner")
    def denied(uid): raise HTTPException(403,"Agent requires Pro")
    monkeypatch.setattr(router,"require_agent_access",denied)
    monkeypatch.setattr(router,"GoogleConnections",lambda db: google)
    monkeypatch.setattr(limiter,"enabled",False)
    app=FastAPI(); app.include_router(router.router)
    client=TestClient(app)
    assert client.get("/agent/google/connections").json()["connections"][0]["id"]==identifier
    assert client.post("/agent/google/connect",json={"capabilities":["calendar_read"]}).status_code==403
    assert client.delete(f"/agent/google/connections/{identifier}").status_code==200
    assert not google.ref("owner",identifier).get().exists


def test_failed_finish_still_clears_the_oauth_cookie(google, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.routers import agent_google as router
    from app.core.rate_limit import limiter
    monkeypatch.setattr(router,"db_firestore",google.db)
    monkeypatch.setattr(router,"_chat_uid",lambda request:"owner")
    monkeypatch.setattr(router,"require_agent_access",lambda uid:None)
    monkeypatch.setattr(limiter,"enabled",False)
    app=FastAPI(); app.include_router(router.router)
    client=TestClient(app)
    client.cookies.set("consens_google_oauth","browser-secret",path="/agent/google")
    response=client.post("/agent/google/finish",json={"state":"s"*40,"code":"c"})
    assert response.status_code==401
    assert 'consens_google_oauth=""' in response.headers["set-cookie"]


def test_httpx_request_urls_are_not_logged_at_info():
    import logging
    from app.core.observability import configure_logging
    configure_logging()
    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)


# ---- Read-only installation (default since 2026-10-03) -------------------

def test_read_only_installation_never_requests_prepares_or_executes_writes(google, monkeypatch):
    from queue import Queue
    from types import SimpleNamespace
    from app.services.agent_actions import AgentActions
    from app.services.agent_calendar import CalendarTools, GoogleSelection
    from app.services.agent_files import AgentFiles
    from app.services.agent_gmail import GmailTools
    identifier=connection(google,caps=["calendar_read","calendar_write","gmail_read","gmail_send"])
    files=AgentFiles(google.db)
    chat=files.chats.create_chat("owner",execution_mode="agent")["id"]
    actions=AgentActions(google.db,connections=google,files=files)
    # A proposal saved while writing was still allowed ...
    saved=actions.prepare("owner",chat,"turn","calendar_event",identifier,"calendar_write",
        {"calendar_id":"primary","event_id":"e"*32,"update":False,"fields":{"summary":"x"}},{"operation":"Create event"})
    monkeypatch.delenv("GOOGLE_WRITES_ENABLED")
    # ... can be discarded, but never confirmed, and nothing reaches Google.
    google.wire.calls.clear()
    with pytest.raises(GoogleError,match="only reads") as denied:
        actions.confirm("owner",chat,saved["id"],saved["hash"])
    assert denied.value.status==403 and not google.wire.calls
    assert actions.get("owner",chat,saved["id"])["status"]=="pending"
    assert actions.reject("owner",chat,saved["id"],saved["hash"])["status"]=="rejected"
    with pytest.raises(GoogleError,match="only reads"):
        actions.prepare("owner",chat,"turn","calendar_event",identifier,"calendar_write",{"update":False},{})
    # Write scopes are never requested and stored write grants look unusable.
    for capability in ("calendar_write","gmail_send"):
        with pytest.raises(GoogleError,match="only reads"): google.start("owner",[capability])
    assert google.list("owner")[0]["capabilities"]==["calendar_read","gmail_read"]
    # The agent only gets read tools.
    file_context=SimpleNamespace(files=files)
    loop=SimpleNamespace(uid="owner",chat_id=chat,turn_id="t",outgoing=Queue(),google_evidence=[],file_context=file_context)
    selection=GoogleSelection(connection_id=identifier,calendar_ids=["primary"],calendar=True,gmail=True,consent=True)
    assert [t.name for t in CalendarTools(loop,google,actions,selection).tools()]==["calendar_read"]
    assert [t.name for t in GmailTools(loop,google,actions,selection).tools()]==["gmail_read","import_gmail_attachment"]
    monkeypatch.setenv("GOOGLE_WRITES_ENABLED","1")
    assert "prepare_calendar_event" in [t.name for t in CalendarTools(loop,google,actions,selection).tools()]


def test_plain_http_redirect_only_on_a_local_checkout(google, monkeypatch):
    from app.services.google_connections import configuration
    monkeypatch.setenv("UNIT_TEST_MODE", "0")
    monkeypatch.delenv("RENDER_SERVICE_NAME", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8044/agent/google/callback")
    assert configuration()["REDIRECT_URI"].startswith("http://localhost")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://consens.example/agent/google/callback")
    with pytest.raises(GoogleError, match="redirect"): configuration()
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8044/agent/google/callback")
    monkeypatch.setenv("RENDER_SERVICE_NAME", "consensio")
    with pytest.raises(GoogleError, match="redirect"): configuration()


def test_drive_picker_configuration_is_public_and_complete_or_absent(monkeypatch):
    from app.services.google_connections import drive_picker
    for key in ("GOOGLE_INTEGRATIONS_ENABLED","GOOGLE_CLIENT_ID","GOOGLE_PICKER_API_KEY","GOOGLE_PROJECT_NUMBER"):
        monkeypatch.delenv(key,raising=False)
    assert drive_picker() is None
    monkeypatch.setenv("GOOGLE_INTEGRATIONS_ENABLED","1")
    monkeypatch.setenv("GOOGLE_CLIENT_ID","client.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_PICKER_API_KEY","AIzaSyExampleExampleExample0123")
    assert drive_picker() is None
    monkeypatch.setenv("GOOGLE_PROJECT_NUMBER","not-a-number")
    assert drive_picker() is None
    monkeypatch.setenv("GOOGLE_PROJECT_NUMBER","123456789012")
    # No server secret is needed or exposed for Drive.
    assert drive_picker()=={"client_id":"client.apps.googleusercontent.com","api_key":"AIzaSyExampleExampleExample0123","app_id":"123456789012"}
    monkeypatch.setenv("GOOGLE_INTEGRATIONS_ENABLED","0")
    assert drive_picker() is None


def test_connections_endpoint_reports_writes_and_drive(google, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.routers import agent_google as router
    from app.core.rate_limit import limiter
    monkeypatch.setattr(router,"db_firestore",google.db)
    monkeypatch.setattr(router,"_chat_uid",lambda request:"owner")
    monkeypatch.setattr(limiter,"enabled",False)
    monkeypatch.delenv("GOOGLE_WRITES_ENABLED")
    app=FastAPI(); app.include_router(router.router)
    body=TestClient(app).get("/agent/google/connections").json()
    assert body["configured"] is True and body["writes"] is False and body["drive"] is None
    monkeypatch.setenv("GOOGLE_PICKER_API_KEY","AIzaSyExampleExampleExample0123")
    monkeypatch.setenv("GOOGLE_PROJECT_NUMBER","123456789012")
    assert TestClient(app).get("/agent/google/connections").json()["drive"]["app_id"]=="123456789012"
