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
