import base64
import io
from datetime import datetime, timedelta, timezone
from dataclasses import replace
import pytest
from PIL import Image
from pypdf import PdfWriter
from app.services.agent_files import AgentFiles, FileContext, FileUnavailable, ReadFileArgs, extract_isolated
from app.services.chat_store import ChatNotFound, ChatStore
from app.services.llm.agent_client import AgentModel
from app.services.llm.provider_runtime import ProviderCancellation
from test_agent_runs import Database


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('AGENT_FILES_LOCAL_DIR', str(tmp_path))
    db = Database()
    files = AgentFiles(db)
    chat = files.chats.create_chat('owner', execution_mode='agent')['id']
    return files, chat


def upload(files, chat, text='Price: 42 EUR\nDelivery: 2 weeks'):
    return files.upload('owner', chat, {'name': 'offer.txt', 'data': base64.b64encode(text.encode()).decode()})


def test_real_extraction_storage_download_and_owner_isolation(setup):
    files, chat = setup
    meta = upload(files, chat)
    data, raw = files.download('owner', chat, meta['id'])
    assert raw.startswith(b'Price: 42')
    assert data['parts'][0]['locator'] == 'lines 1-2'
    assert 'object_key' not in meta and 'parts' not in meta
    assert all(not isinstance(v, bytes) for doc in files.db.documents.values() for v in doc.values())
    for action in [lambda: files.list('other', chat), lambda: files.get('other', chat, meta['id']),
                   lambda: files.download('other', chat, meta['id']), lambda: files.delete('other', chat, meta['id'])]:
        with pytest.raises(ChatNotFound): action()
    assert files.download('owner', chat, meta['id'])[1] == raw


def test_followup_reads_saved_excerpts_without_reextracting(setup, monkeypatch):
    files, chat = setup
    meta = upload(files, chat)
    monkeypatch.setattr('app.services.agent_files.extract_isolated', lambda *_: pytest.fail('must not reextract'))
    ctx = FileContext(AgentFiles(files.db), 'owner', chat, [])
    result = ctx.read(ReadFileArgs(file_id=meta['id'], query='Delivery'), cancellation=ProviderCancellation())
    assert '2 weeks' in result['excerpts'][0]['text']
    assert result['trust'] == 'untrusted'
    assert ctx.catalog()[0]['id'] == meta['id']


def test_wrong_chat_expiration_deletion_and_quota(setup):
    files, chat = setup
    meta = upload(files, chat)
    other = files.chats.create_chat('owner', execution_mode='agent')['id']
    with pytest.raises(FileUnavailable): files.get('owner', other, meta['id'])
    ref = files.ref('owner', chat, meta['id'])
    key = ref.get().to_dict()['object_key']
    ref.update({'expires_at': (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()})
    with pytest.raises(FileUnavailable, match='expired'): files.download('owner', chat, meta['id'])
    files.expire('owner', chat)
    assert files.quota_ref('owner').get().to_dict() == {'count': 0, 'bytes': 0}
    with pytest.raises(FileUnavailable): files.objects.get(key)
    files.delete('owner', chat, meta['id'])


def test_chat_deletion_removes_objects_and_account_fence_blocks_upload(setup):
    files, chat = setup
    meta = upload(files, chat)
    key = files.get('owner', chat, meta['id'])['object_key']
    files.chats.delete_chat('owner', chat)
    with pytest.raises(FileUnavailable): files.objects.get(key)
    with pytest.raises(ChatNotFound): upload(files, chat)


def test_malformed_and_scanned_pdf_limits(setup):
    files, chat = setup
    for raw in [b'%PDF-1.7\ninvalid', b'\x89PNG\r\n\x1a\n' + b'0' * 30]:
        with pytest.raises(FileUnavailable):
            files.upload('owner', chat, {'name': 'bad', 'data': base64.b64encode(raw).decode()})
    writer = PdfWriter(); writer.add_blank_page(600, 800)
    out = io.BytesIO(); writer.write(out)
    result = extract_isolated(out.getvalue(), 'application/pdf')
    assert result['status'] == 'partial' and not result['parts']
    assert 'OCR' in result['warnings'][0]


def test_images_are_capability_aware_and_private(setup, monkeypatch):
    files, chat = setup
    out = io.BytesIO(); Image.new('RGB', (100, 100)).save(out, 'PNG')
    meta = files.upload('owner', chat, {'name': 'photo.png', 'data': base64.b64encode(out.getvalue()).decode()})
    ctx = FileContext(files, 'owner', chat, [meta['id']])
    monkeypatch.setattr('app.services.llm.agent_model_metadata.snapshot', lambda: {})
    plain = ctx.messages([], AgentModel())[-1]['content']
    assert all(p['type'] == 'text' for p in plain)
    monkeypatch.setattr('app.services.llm.agent_model_metadata.snapshot', lambda: {AgentModel().model: {'architecture': {'input_modalities': ['image']}}})
    visual = ctx.messages([], AgentModel())[-1]['content']
    assert visual[-1]['type'] == 'image_url'
    assert visual[-1]['image_url']['url'].startswith('data:image/png;base64,')


def test_cancelled_upload_and_concurrent_delete_do_not_leave_bytes(setup):
    files, chat = setup
    cancellation = ProviderCancellation()
    original = files.objects.put
    keys = []
    def put(key, raw, mime):
        original(key, raw, mime); keys.append(key); cancellation.cancel()
    files.objects.put = put
    from app.services.llm.provider_runtime import ProviderCancelled
    with pytest.raises(ProviderCancelled):
        files.save('owner', chat, raw=b'text', name='x', mime='text/plain', extraction={'status':'ready','parts':[], 'warnings':[]}, cancellation=cancellation)
    assert not files.list('owner', chat)
    with pytest.raises(FileUnavailable): files.objects.get(keys[0])


def test_file_endpoints_validate_auth_and_return_private_download(setup, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.routers import agent_files as router
    from app.core.rate_limit import limiter
    files, chat = setup
    monkeypatch.setattr(router, 'db_firestore', files.db)
    monkeypatch.setattr(router, '_chat_uid', lambda request: request.headers.get('X-User', 'owner'))
    monkeypatch.setattr(router, 'require_agent_access', lambda uid: None)
    monkeypatch.setattr(limiter, "enabled", False)
    app = FastAPI(); app.include_router(router.router)
    client = TestClient(app)
    response = client.post(f'/agent/chats/{chat}/files', json={'name': 'offer.txt', 'data': base64.b64encode(b'Private price 42').decode()})
    assert response.status_code == 200
    file_id = response.json()['file']['id']
    path = f'/agent/chats/{chat}/files/{file_id}'
    assert client.get(path, headers={'X-User': 'other'}).status_code == 404
    assert client.delete(path, headers={'X-User': 'other'}).status_code == 404
    response = client.get(path)
    assert response.content == b'Private price 42'
    assert response.headers['cache-control'] == 'private, no-store'
    assert response.headers['content-disposition'].startswith('attachment;')
    assert client.post(f'/agent/chats/{chat}/files', json={'name':'evil','data':'$bad'}).status_code == 400
    assert client.delete(path).status_code == 200
    assert client.get(path).status_code == 422


def test_storage_quota_is_atomic_and_parser_times_out(setup, monkeypatch):
    import subprocess
    files, chat = setup
    files.quota_ref('owner').set({'count':100,'bytes':1})
    with pytest.raises(FileUnavailable, match='limit'):
        upload(files, chat)
    assert not files.list('owner', chat)
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired('parser',15)))
    result = extract_isolated(b'anything','text/plain')
    assert result['status'] == 'failed' and 'safety limits' in result['warnings'][0]


def test_docx_tables_preserve_cell_boundaries_and_paragraph_locators():
    import zipfile
    out = io.BytesIO()
    xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Offer</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Vendor A</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>42 EUR</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'
    with zipfile.ZipFile(out,'w') as archive: archive.writestr('word/document.xml',xml)
    result = extract_isolated(out.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    assert result['parts'] == [{'locator':'paragraph 1','text':'Offer'}, {'locator':'table at block 2','text':'Vendor A | 42 EUR'}]


def test_visual_admission_does_not_tokenize_base64_as_prose():
    from app.services.agent_tokens import input_estimate
    image = {'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/png;base64,' + 'A'*1000000}}]}
    assert 16000 < input_estimate([image]) < 17000


def test_real_comparison_loop_receives_same_saved_file_evidence(setup):
    from app.services.agent_runs import AgentRunStore
    from test_agent_comparison import Script, make_loop
    from test_agent_runs import UID
    files, _ = setup
    store = AgentRunStore(files.db)
    script = Script()
    loop = make_loop(store, script)
    meta = files.upload(UID, loop.chat_id, {'name':'offer.txt','data':base64.b64encode(b'Independent source price 42 EUR').decode()})
    loop.file_context = FileContext(files, UID, loop.chat_id, [meta['id']])
    list(loop.run())
    assert len(script.prompts) == 2
    evidence = [messages[-1]['content'] for messages in script.prompts]
    assert evidence[0] == evidence[1]
    assert 'Independent source price 42 EUR' in evidence[0][0]['text']
    assert 'lines 1-1' in evidence[0][0]['text']
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)['status'] == 'completed'


def test_account_tombstone_prevents_recreation_during_upload(setup):
    from app.services.persistence_guard import AccountDeletionInProgress
    files, chat = setup
    files.db.collection('account_deletion_jobs').document('owner').set({'status':'pending'})
    with pytest.raises(AccountDeletionInProgress): upload(files, chat)
    assert not files.list('owner', chat)


def test_native_pdf_transport_never_selects_paid_ocr(monkeypatch):
    import json
    from app.services.llm.agent_client import AgentCompletion
    captured = {}
    def stream(url, **kwargs):
        captured.update(kwargs['json'])
        yield 'data: ' + json.dumps({'choices':[{'delta':{'content':'Read file'},'finish_reason':'stop'}]})
        yield ''
        yield 'data: [DONE]'
        yield ''
    monkeypatch.setattr('app.services.llm.agent_client.cancellable_sse_lines', stream)
    value = AgentCompletion()
    list(value.stream(model=AgentModel(), messages=[{'role':'user','content':[{'type':'file','file':{'filename':'scan.pdf','file_data':'data:application/pdf;base64,AA=='}}]}], api_key='test'))
    assert captured['plugins'] == [{'id':'file-parser','pdf':{'engine':'native'}}]
    assert captured['provider']['zdr'] is True


def test_missing_storage_fails_before_metadata_and_chat_deletion_still_works(setup, monkeypatch):
    from app.services.agent_files import StorageNotConfigured
    files, chat = setup
    monkeypatch.delenv('AGENT_FILES_LOCAL_DIR')
    monkeypatch.delenv('AGENT_FILES_BUCKET', raising=False)
    bare = AgentFiles(files.db)
    with pytest.raises(StorageNotConfigured):
        upload(bare, chat)
    assert not bare.list('owner', chat)
    assert not bare.quota_ref('owner').get().exists
    # A record left over from an environment that once had storage must not
    # block chat (and therefore account) deletion.
    bare.ref('owner', chat, 'a' * 32).set({'id': 'a' * 32, 'object_key': 'agent-files/x', 'size': 3, 'status': 'ready'})
    bare.chats.delete_chat('owner', chat)
    assert not bare.ref('owner', chat, 'a' * 32).get().exists


def test_missing_storage_returns_503(setup, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.routers import agent_files as router
    from app.core.rate_limit import limiter
    files, chat = setup
    monkeypatch.delenv('AGENT_FILES_LOCAL_DIR')
    monkeypatch.delenv('AGENT_FILES_BUCKET', raising=False)
    monkeypatch.setattr(router, 'db_firestore', files.db)
    monkeypatch.setattr(router, '_chat_uid', lambda request: 'owner')
    monkeypatch.setattr(router, 'require_agent_access', lambda uid: None)
    monkeypatch.setattr(limiter, "enabled", False)
    app = FastAPI(); app.include_router(router.router)
    response = TestClient(app).post(f'/agent/chats/{chat}/files', json={'name': 'a.txt', 'data': base64.b64encode(b'x').decode()})
    assert response.status_code == 503


def test_failed_upload_cleanup_surfaces_original_error(setup):
    files, chat = setup
    def put(*_):
        raise RuntimeError('storage write failed')
    def delete(*_):
        raise RuntimeError('storage delete failed')
    files.objects.put, files.objects.delete = put, delete
    with pytest.raises(RuntimeError, match='write failed'):
        upload(files, chat)
    # The record stays in "deleting" with an elapsed deadline, so retention retries it.
    remaining = [doc for path, doc in files.db.documents.items() if 'files' in path]
    assert [doc['status'] for doc in remaining] == ['deleting']


class _Snapshot:
    def __init__(self, path):
        self.reference = type('Ref', (), {'path': path})()


class _PagedQuery:
    def __init__(self, paths, page_size, start=0):
        self.paths, self.page_size, self.start = paths, page_size, start

    def where(self, filter=None):
        return self

    def order_by(self, field):
        return self

    def limit(self, value):
        return _PagedQuery(self.paths, value, self.start)

    def start_after(self, snapshot):
        return _PagedQuery(self.paths, self.page_size, self.paths.index(snapshot.reference.path) + 1)

    def stream(self):
        return [_Snapshot(p) for p in self.paths[self.start:self.start + self.page_size]]


def test_retention_pages_past_failures(monkeypatch):
    from app.services import agent_files as module
    monkeypatch.setenv('AGENT_FILES_LOCAL_DIR', '/unused')
    paths = [f'users/u/chats/{"c" * 32}/files/{i:032x}' for i in range(7)]
    db = type('DB', (), {'collection_group': lambda self, name: _PagedQuery(paths, 200)})()
    deleted = []
    def delete(self, uid, chat_id, file_id, *, cleanup=False):
        if file_id == f'{0:032x}':
            raise RuntimeError('transient storage error')
        deleted.append(file_id)
    monkeypatch.setattr(module.AgentFiles, 'delete', delete)
    monkeypatch.setattr(module, 'ChatStore', lambda db: None)
    # Two fields are swept; each sees the stuck first item and still reaches the rest.
    assert module.cleanup_expired_files(db, page_size=2) == 12
    assert len(set(deleted)) == 6


def test_native_pdf_only_when_it_fits_the_model_window(setup, monkeypatch):
    from app.services.agent_tokens import pdf_visual_tokens
    files, chat = setup
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(600, 800)
    out = io.BytesIO(); writer.write(out)
    assert pdf_visual_tokens(out.getvalue()) == 9_000
    meta = files.upload('owner', chat, {'name': 'scan.pdf', 'data': base64.b64encode(out.getvalue()).decode()})
    ctx = FileContext(files, 'owner', chat, [meta['id']])
    model = AgentModel()
    monkeypatch.setattr('app.services.llm.agent_model_metadata.snapshot', lambda: {model.model: {'architecture': {'input_modalities': ['file']}}})
    assert ctx.messages([], replace(model, context_length=200_000))[-1]['content'][-1]['type'] == 'file'
    small = ctx.messages([], replace(model, context_length=20_000))[-1]['content'][-1]
    assert small['type'] == 'text' and 'too large' in small['text']


def test_model_reads_never_evict_the_user_selection(setup):
    files, chat = setup
    out = io.BytesIO(); Image.new('RGB', (10, 10)).save(out, 'PNG')
    selected = [upload(files, chat, f'note {i}')['id'] for i in range(5)]
    image = files.upload('owner', chat, {'name': 'p.png', 'data': base64.b64encode(out.getvalue()).decode()})
    ctx = FileContext(files, 'owner', chat, selected)
    ctx.read(ReadFileArgs(file_id=image['id']), cancellation=ProviderCancellation())
    assert ctx.selection() == selected
    ctx.file_ids = selected[:2]
    assert ctx.selection() == [*selected[:2], image['id']]
