"""Files picked in Google's Drive picker: ordinary chat attachments that carry
Google provenance, so the chat they are sent in follows the Google rules."""
import base64
import json
import pytest
from test_agent_runs import api, store  # noqa: F401  (fixtures)

PICKER = {"GOOGLE_INTEGRATIONS_ENABLED": "1", "GOOGLE_CLIENT_ID": "client.apps.googleusercontent.com",
          "GOOGLE_PICKER_API_KEY": "AIzaSyExampleExampleExample0123", "GOOGLE_PROJECT_NUMBER": "123456789012",
          "GOOGLE_TEST_USERS": "*"}


def files_client(db, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.routers import agent_files as router
    from app.core.rate_limit import limiter
    monkeypatch.setattr(router, 'db_firestore', db)
    monkeypatch.setattr(router, '_chat_uid', lambda request: request.headers.get('X-User', 'owner'))
    monkeypatch.setattr(router, 'require_agent_access', lambda uid: None)
    monkeypatch.setattr(router, 'require_uploads', lambda uid: None)
    monkeypatch.setattr(limiter, "enabled", False)
    app = FastAPI(); app.include_router(router.router)
    return TestClient(app)


def body(text='Offer: 42 EUR'):
    return base64.b64encode(text.encode()).decode()


def test_drive_upload_stores_provenance_only_when_drive_is_configured(tmp_path, monkeypatch):
    from app.services.agent_files import AgentFiles
    from test_agent_runs import Database
    monkeypatch.setenv('AGENT_FILES_LOCAL_DIR', str(tmp_path))
    for key in PICKER:
        monkeypatch.delenv(key, raising=False)
    files = AgentFiles(Database())
    chat = files.chats.create_chat('owner', execution_mode='agent')['id']
    client = files_client(files.db, monkeypatch)
    picked = {'name': 'Offer.docx.txt', 'data': body(), 'drive_file_id': '1AbCdEfGhIjKlMnOp'}
    assert client.post(f'/agent/chats/{chat}/files', json=picked).status_code == 403
    for key, value in PICKER.items():
        monkeypatch.setenv(key, value)
    assert client.post(f'/agent/chats/{chat}/files', json={**picked, 'drive_file_id': '../etc'}).status_code == 422
    meta = client.post(f'/agent/chats/{chat}/files', json=picked).json()['file']
    assert meta['kind'] == 'drive_file' and meta['origin'] == {'source': 'google_drive', 'file_id': '1AbCdEfGhIjKlMnOp'}
    # An ordinary upload stays an upload.
    plain = client.post(f'/agent/chats/{chat}/files', json={'name': 'notes.txt', 'data': body('x')}).json()['file']
    assert plain['kind'] == 'upload' and 'origin' not in plain


def test_drive_file_puts_the_chat_under_google_rules_with_one_consent_per_chat(api, tmp_path, monkeypatch):
    from test_agent_runs import AUTH, UID
    from app.services.agent_files import AgentFiles
    client, store, calls = api
    monkeypatch.setenv('AGENT_FILES_LOCAL_DIR', str(tmp_path))
    for key, value in PICKER.items():
        monkeypatch.setenv(key, value)
    chat = client.post('/chats', json={'execution_mode': 'agent'}, headers=AUTH).json()['chat']['id']
    files = AgentFiles(store.db)
    drive = files.upload(UID, chat, {'name': 'offer.txt', 'data': body()},
                         extra={'kind': 'drive_file', 'origin': {'source': 'google_drive', 'file_id': '1AbCdEfGhIjKlMnOp'}})
    payload = {'chat_id': chat, 'question': 'Is this offer fair?', 'client_request_id': 'drive-1',
               'bookmark_id': 'drive_chat', 'file_ids': [drive['id']]}
    refused = client.post('/agent', json=payload, headers=AUTH)
    assert refused.status_code == 422 and 'Google' in refused.json()['detail'] and not calls
    response = client.post('/agent', json={**payload, 'google_data_consent': True}, headers=AUTH)
    assert response.status_code == 200 and 'event: final' in response.text, response.text
    final = json.loads(response.text.split('event: final\ndata: ', 1)[1].split('\n', 1)[0])
    assert final['google_data'] is True and final['google_consent'] is True
    # The saved message keeps saying the file came from Google Drive.
    assert final['turn']['attachments'][0]['source'] == 'google_drive'
    chat_doc = store._chat_ref(UID, chat).get().to_dict()
    assert chat_doc['google_data'] is True and chat_doc['google_consent'] is True
    # Every call of that chat: zero retention, no prompt collection, no web search.
    provider = calls[0]['model'].request_config['provider']
    assert provider['zdr'] is True and provider['data_collection'] == 'deny'
    assert not calls[0].get('native_searches')
    # A follow-up without new Google data still needs the (remembered) consent.
    follow = {'chat_id': chat, 'question': 'And the delivery time?', 'client_request_id': 'drive-2', 'bookmark_id': 'drive_chat'}
    assert client.post('/agent', json=follow, headers=AUTH).status_code == 422
    assert client.post('/agent', json={**follow, 'google_data_consent': True}, headers=AUTH).status_code == 200


def test_chat_without_google_data_keeps_its_normal_routing(api, monkeypatch):
    from test_agent_runs import AUTH
    client, store, calls = api
    chat = client.post('/chats', json={'execution_mode': 'agent'}, headers=AUTH).json()['chat']['id']
    payload = {'chat_id': chat, 'question': 'Hi', 'client_request_id': 'plain', 'bookmark_id': 'plain_chat'}
    response = client.post('/agent', json=payload, headers=AUTH)
    final = json.loads(response.text.split('event: final\ndata: ', 1)[1].split('\n', 1)[0])
    assert final['google_data'] is False and final['google_consent'] is False
    assert 'data_collection' not in (calls[0]['model'].request_config.get('provider') or {})
