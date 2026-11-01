"""Pictures under an answer load as a preview (routers/agent_files.py,
runtime audit 2026-10-30 P2): at most agent_web_images.MAX_SIDE on a side,
the original stays the download."""
import io

import pytest
from PIL import Image

from test_agent_files import setup  # noqa: F401  (fixture)


@pytest.fixture
def client(setup, monkeypatch):  # noqa: F811
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.routers import agent_files as router
    from app.core.rate_limit import limiter
    files, chat = setup
    monkeypatch.setattr(router, 'db_firestore', files.db)
    monkeypatch.setattr(router, '_chat_uid', lambda request: 'owner')
    monkeypatch.setattr(router, 'require_agent_access', lambda uid: None)
    monkeypatch.setattr(router, 'require_uploads', lambda uid: None)
    monkeypatch.setattr(limiter, "enabled", False)
    app = FastAPI()
    app.include_router(router.router)
    return TestClient(app), (files, chat)


def stored(client, where, name, size, fmt, mime):
    """A picture the agent shared from its workspace (vm_share_file saves it so)."""
    files, chat = where
    out = io.BytesIO()
    Image.linear_gradient('L').resize(size).convert('RGB').save(out, fmt)
    meta = files.save('owner', chat, raw=out.getvalue(), name=name, mime=mime,
                      extraction={'status': 'ready', 'parts': [], 'warnings': []}, extra={'kind': 'vm_file'})
    return meta['id'], out.getvalue()


def test_a_large_picture_comes_smaller_as_preview_and_whole_as_download(client):
    client, where = client
    file_id, raw = stored(client, where, 'screen.png', (3200, 1800), 'PNG', 'image/png')
    path = f'/agent/chats/{where[1]}/files/{file_id}'
    preview = client.get(path + '?preview=1')
    assert preview.status_code == 200 and preview.headers['content-type'] == 'image/webp'
    assert preview.headers['cache-control'] == 'private, no-store'
    with Image.open(io.BytesIO(preview.content)) as image:
        assert image.size == (1600, 900)
    assert len(preview.content) < len(raw)
    original = client.get(path)
    assert original.content == raw and original.headers['content-disposition'].startswith('attachment;')


@pytest.mark.parametrize('name,size,fmt,mime', [('small.png', (400, 300), 'PNG', 'image/png'),
                                               ('anim.gif', (2400, 1200), 'GIF', 'image/gif')])
def test_a_small_picture_or_a_gif_comes_as_it_is(client, name, size, fmt, mime):
    client, where = client
    file_id, raw = stored(client, where, name, size, fmt, mime)
    response = client.get(f'/agent/chats/{where[1]}/files/{file_id}?preview=1')
    assert response.status_code == 200 and response.content == raw


def test_an_office_file_previews_as_its_pdf_and_downloads_as_itself(client):
    """file-viewer.js (2026-11-01): the PDF of a shared Office file is a
    second object beside the file; it counts in the account's storage and
    goes with the file."""
    client, (files, chat) = client
    meta = files.save('owner', chat, raw=b'PK slides', name='deck.pptx',
                      mime='application/vnd.openxmlformats-officedocument.presentationml.presentation',
                      extraction={'status': 'ready', 'parts': [], 'warnings': []}, extra={'kind': 'vm_file'},
                      preview=b'%PDF-1.7 slides')
    assert meta['preview'] == {'mime': 'application/pdf', 'size': 15}
    path = f'/agent/chats/{chat}/files/{meta["id"]}'
    preview = client.get(path + '?preview=1')
    assert preview.status_code == 200 and preview.content == b'%PDF-1.7 slides'
    assert preview.headers['content-type'] == 'application/pdf' and preview.headers['content-disposition'] == 'inline'
    assert preview.headers['x-content-type-options'] == 'nosniff'
    original = client.get(path)
    assert original.content == b'PK slides' and original.headers['content-disposition'].startswith('attachment;')
    quota = files.quota_ref('owner').get().to_dict()
    assert quota == {'count': 1, 'bytes': len(b'PK slides') + 15}
    stored = files.ref('owner', chat, meta['id']).get().to_dict()
    files.delete('owner', chat, meta['id'])
    assert files.quota_ref('owner').get().to_dict() == {'count': 0, 'bytes': 0}
    root = files.objects.root
    assert not (root / stored['object_key']).exists() and not (root / (stored['object_key'] + '.preview')).exists()


def test_a_changed_preview_is_refused(client):
    client, (files, chat) = client
    meta = files.save('owner', chat, raw=b'PK', name='a.docx', mime='application/octet-stream',
                      extraction={'status': 'ready', 'parts': [], 'warnings': []}, preview=b'%PDF-1.7 a')
    key = files.ref('owner', chat, meta['id']).get().to_dict()['object_key'] + '.preview'
    (files.objects.root / key).write_bytes(b'%PDF-1.7 b')
    assert client.get(f'/agent/chats/{chat}/files/{meta["id"]}?preview=1').status_code == 422


def test_a_word_file_without_a_pdf_previews_as_its_text_and_a_pdf_as_itself(client):
    client, (files, chat) = client
    docx = files.save('owner', chat, raw=b'PK word', name='offer.docx',
                      mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                      extraction={'status': 'ready', 'warnings': [], 'parts': [
                          {'locator': 'paragraph 1', 'text': 'Offer'}, {'locator': 'table at block 2', 'text': 'a | b'}]})
    response = client.get(f'/agent/chats/{chat}/files/{docx["id"]}?preview=1')
    assert response.text == 'Offer\n\na | b' and response.headers['content-type'] == 'text/plain; charset=utf-8'
    pdf = files.save('owner', chat, raw=b'%PDF-1.4 x', name='a.pdf', mime='application/pdf',
                     extraction={'status': 'ready', 'parts': [], 'warnings': []})
    assert client.get(f'/agent/chats/{chat}/files/{pdf["id"]}?preview=1').content == b'%PDF-1.4 x'
