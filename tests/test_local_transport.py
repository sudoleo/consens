"""Real loopback sockets/TLS through provider and source HTTP adapters."""
import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import ssl
import threading
from types import SimpleNamespace

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import httpx
import openai
import pytest

from app.services import source_documents as sources
from app.services.llm import provider_runtime as runtime


@contextmanager
def server(callback, tls=None):
    state = SimpleNamespace(requests=[], seen=threading.Event(), closed=threading.Event(), sni=[])
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def log_message(self, *args): pass
        def do_GET(self): self.respond()
        def do_POST(self): self.respond()
        def respond(self):
            self.connection.settimeout(5)
            self.rfile.read(int(self.headers.get('Content-Length', '0')))
            state.requests.append((self.path, self.headers.get('Host')))
            state.seen.set()
            try:
                callback(self, state)
            except (ConnectionError, OSError):
                state.closed.set()
        def send_body(self, body, status=200, **headers):
            self.send_response(status)
            self.send_header('Content-Length', str(len(body)))
            for key, value in headers.items(): self.send_header(key.replace('_','-'), value)
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
    httpd=ThreadingHTTPServer(('127.0.0.1',0), Handler)
    if tls:
        tls.set_servername_callback(lambda socket, name, context: state.sni.append(name))
        httpd.socket=tls.wrap_socket(httpd.socket, server_side=True)
    thread=threading.Thread(target=httpd.serve_forever, kwargs={'poll_interval':0.05}, daemon=True)
    thread.start()
    state.url=f"{'https' if tls else 'http'}://127.0.0.1:{httpd.server_port}"
    try: yield state
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(2)
        assert not thread.is_alive()


@pytest.mark.parametrize('phase',['headers','body'])
def test_cancellation_closes_real_idle_provider_socket_without_retry(phase):
    def respond(handler, state):
        if phase == 'body':
            handler.send_response(200)
            handler.send_header('Content-Type','text/event-stream')
            handler.send_header('Content-Length','100000')
            handler.end_headers()
            handler.wfile.write(b'data: {"delta":"first"}\n\n')
            handler.wfile.flush()
        if handler.connection.recv(1) == b'': state.closed.set()
    cancellation=runtime.ProviderCancellation()
    errors=[]
    with server(respond) as state:
        def worker():
            try:
                with runtime.bind_provider_cancellation(cancellation):
                    list(runtime.cancellable_sse_lines(state.url, json={}, headers={}))
            except Exception as error: errors.append(error)
        thread=threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            assert state.seen.wait(3), 'request never reached local server'
            cancellation.cancel()
            thread.join(3)
            assert not thread.is_alive(), 'producer survived cancellation'
            assert len(errors) == 1 and isinstance(errors[0], runtime.ProviderCancelled)
            assert state.closed.wait(3), 'server socket stayed open'
            assert len(state.requests) == 1
        finally:
            cancellation.cancel()
            thread.join(3)


def test_sdk_read_deadline_closes_real_socket_and_does_not_retry():
    def respond(handler, state):
        handler.send_response(200)
        handler.send_header('Content-Length','100000')
        handler.send_header('Content-Type','application/json')
        handler.end_headers()
        handler.wfile.flush()
        if handler.connection.recv(1) == b'': state.closed.set()
    with server(respond) as state:
        with runtime.openai_client(api_key='dummy', base_url=state.url+'/v1', timeout_seconds=0.2) as client:
            with pytest.raises(openai.APITimeoutError):
                client.chat.completions.create(model='test', messages=[{'role':'user','content':'test'}])
        assert state.closed.wait(3)
        assert len(state.requests) == 1


@pytest.mark.parametrize('mutated', [False, True])
def test_http_failure_has_one_attempt_and_oracle_detects_enabled_sdk_retry(monkeypatch, mutated):
    def respond(handler,state):
        handler.send_body(b'{"error":{"message":"unavailable"}}',status=503,Content_Type='application/json')
    if mutated:
        monkeypatch.setattr(runtime,'PROVIDER_SDK_MAX_RETRIES',1)
    with server(respond) as state:
        with runtime.openai_client(api_key='dummy',base_url=state.url+'/v1',timeout_seconds=1) as client:
            with pytest.raises(openai.APIStatusError):
                client.chat.completions.create(model='test',messages=[{'role':'user','content':'test'}])
        def one_attempt():
            assert len(state.requests) == 1
        if mutated:
            with pytest.raises(AssertionError): one_attempt()
            assert len(state.requests) == 2
        else:
            one_attempt()


@pytest.fixture
def tls_contexts(tmp_path):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'source.test')])
    now=datetime.now(timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1))
          .not_valid_after(now+timedelta(days=1))
          .add_extension(x509.SubjectAlternativeName([x509.DNSName('source.test')]),critical=False)
          .sign(key,hashes.SHA256()))
    cert_path=tmp_path/'cert.pem'; key_path=tmp_path/'key.pem'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    serving=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    serving.load_cert_chain(str(cert_path),str(key_path))
    trusting=ssl.create_default_context(cafile=str(cert_path))
    return serving,trusting


def source_adapter(monkeypatch, state, trust):
    original_target=sources.pinned_target
    async def local_target(url):
        if url.startswith('https://source.test/'):
            return state.url+url.removeprefix('https://source.test'), 'source.test', 'source.test'
        return await original_target(url)
    original_client=httpx.AsyncClient
    monkeypatch.setattr(sources, 'pinned_target', local_target)
    monkeypatch.setattr(sources.httpx, 'AsyncClient', lambda **kw: original_client(**kw,verify=trust))


def test_source_tls_preserves_host_sni_redirect_and_bounds_gzip(monkeypatch,tls_contexts):
    def respond(handler,state):
        if handler.path == '/redirect':
            handler.send_body(b'',status=302,Location='https://source.test/gzip')
        else:
            handler.send_body(gzip.compress(b'x'*1_000_000),Content_Type='text/plain',Content_Encoding='gzip')
    with server(respond,tls_contexts[0]) as state:
        source_adapter(monkeypatch,state,tls_contexts[1])
        value=asyncio.run(sources._download('https://source.test/redirect',SimpleNamespace(fetch_seconds=2,max_bytes=1024)))
        assert value[0] == 'https://source.test/gzip'
        assert value[1] == b'x'*1024
        assert value[4] is True
        assert state.requests == [('/redirect','source.test'),('/gzip','source.test')]
        assert state.sni and set(state.sni) == {'source.test'}


def test_source_revalidates_redirect_before_connecting_private_target(monkeypatch,tls_contexts):
    def respond(handler,state):
        handler.send_body(b'',status=302,Location='http://127.0.0.1/private')
    with server(respond,tls_contexts[0]) as state:
        source_adapter(monkeypatch,state,tls_contexts[1])
        with pytest.raises(ValueError,match='unsafe_address'):
            asyncio.run(sources._download('https://source.test/redirect',SimpleNamespace(fetch_seconds=2,max_bytes=1024)))
        assert state.requests == [('/redirect','source.test')]


@pytest.mark.parametrize('url',['http://127.0.0.1/', 'https://localhost:8443/', 'http://user:pass@example.test/'])
def test_real_source_policy_keeps_loopback_and_credentials_forbidden(url):
    with pytest.raises(ValueError,match='unsafe_'):
        asyncio.run(sources.pinned_target(url))
