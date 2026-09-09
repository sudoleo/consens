"""Bounded public-document retrieval. No cookies, proxies, search or JS execution."""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import re
import copy
import socket
import time
import zlib
from collections import OrderedDict
from datetime import datetime, timezone
from threading import Lock, BoundedSemaphore
from concurrent.futures import ThreadPoolExecutor, Future
from urllib.parse import urlsplit, urlunsplit, urljoin

import httpx
from bs4 import BeautifulSoup

_cache = OrderedDict()
_inflight = {}


def fetch_failure_code(exc):
    """Only categorical errors leave the retrieval boundary."""
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return "fetch_timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (401, 403):
            return "access_denied"
        if status == 404:
            return "not_found"
        if status == 429:
            return "rate_limited"
        return "upstream_error"
    if isinstance(exc, ValueError) and str(exc) in {"unsafe_url", "unsafe_address", "dns_busy",
            "unsupported_document", "unsupported_encoding", "incomplete_document", "redirect_limit",
            "fetch_timeout", "access_denied", "not_found", "rate_limited", "upstream_error", "network_error"}:
        return str(exc)
    return "network_error"


def _metric(name, **kwargs):
    from app.core.observability import record_metric
    record_metric("source_documents", name, **kwargs)
_lock = Lock()
_dns_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='source-dns')
_dns_slots = BoundedSemaphore(4)


def public_address(value):
    address = ipaddress.ip_address(value.split('%')[0])
    return address.is_global and not (address.is_multicast or address.is_reserved
                                    or getattr(address, 'is_site_local', False)
                                    or (address.version == 6 and (address in ipaddress.ip_network('64:ff9b::/96')
                                                                 or address in ipaddress.ip_network('64:ff9b:1::/48')))
                                    or getattr(address, 'ipv4_mapped', None)
                                    or getattr(address, 'sixtofour', None)
                                    or getattr(address, 'teredo', None))


async def pinned_target(url):
    parts = urlsplit(url)
    if (parts.scheme not in ('https', 'http') or not parts.hostname
            or parts.username is not None or parts.password is not None
            or '%' in parts.netloc or parts.port not in (None, 80, 443)):
        raise ValueError('unsafe_url')
    hostname = parts.hostname.encode('idna').decode('ascii')
    port = parts.port or (443 if parts.scheme == 'https' else 80)
    if not _dns_slots.acquire(blocking=False):
        raise ValueError('dns_busy')
    future = _dns_pool.submit(socket.getaddrinfo, hostname, port, 0, socket.SOCK_STREAM)
    future.add_done_callback(lambda _: _dns_slots.release())
    addresses = await asyncio.wrap_future(future)
    if not addresses or any(not public_address(item[4][0]) for item in addresses):
        raise ValueError('unsafe_address')
    ip = addresses[0][4][0]
    authority = f'[{ip}]' if ':' in ip else ip
    target = urlunsplit((parts.scheme, f'{authority}:{port}', parts.path or '/', parts.query, ''))
    host = f'[{hostname}]' if ':' in hostname else hostname
    # The connection authority is the pinned IP, but HTTP virtual hosting must
    # see the original URL's canonical authority. Adding an implicit :443/:80
    # makes some origins repeatedly redirect to the same canonical URL.
    default_port = 443 if parts.scheme == 'https' else 80
    host_header = f'{host}:{port}' if port != default_port else host
    return target, host_header, hostname


async def _download(url, limits):
    # Connecting to the validated IP prevents DNS rebinding. TLS still verifies
    # the original hostname via httpcore's sni_hostname extension.
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False,
                                 timeout=limits.fetch_seconds) as client:
        for _ in range(4):
            target, host, hostname = await pinned_target(url)
            async with client.stream('GET', target,
                    headers={'Host': host, 'Accept-Encoding': 'gzip, deflate',
                             'User-Agent': 'consens.io source verification/1'},
                    extensions={'sni_hostname': hostname}) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    url = urljoin(url, response.headers.get('location', ''))
                    continue
                response.raise_for_status()
                kind = response.headers.get('content-type', '').split(';')[0].lower()
                if kind not in ('text/html', 'application/xhtml+xml', 'text/plain'):
                    raise ValueError('unsupported_document')
                encoding = response.headers.get('content-encoding', 'identity').strip().lower()
                if encoding not in ('identity', 'gzip', 'deflate'):
                    raise ValueError('unsupported_encoding')
                decoder = zlib.decompressobj(16 + zlib.MAX_WBITS if encoding == 'gzip' else zlib.MAX_WBITS) if encoding != 'identity' else None
                content = bytearray()
                truncated = False
                wire_bytes = 0
                # Stream RAW bytes: bound both compressed input and decoded
                # output before allocating it (including compression bombs).
                async for chunk in response.aiter_raw(chunk_size=8192):
                    wire_bytes += len(chunk)
                    remaining = limits.max_bytes - len(content)
                    decoded = decoder.decompress(chunk, remaining) if decoder else chunk[:remaining]
                    content.extend(decoded)
                    if wire_bytes >= limits.max_bytes or len(content) >= limits.max_bytes:
                        truncated = True
                        break
                if decoder and not truncated and not decoder.eof:
                    raise ValueError('incomplete_document')
                return url, bytes(content), kind, dict(response.headers), truncated
        raise ValueError('redirect_limit')


def extract_document(url, content, kind, headers, truncated, limits):
    decoded = content.decode('utf-8', errors='replace')
    dates = []
    title = ''
    if kind != 'text/plain':
        soup = BeautifulSoup(decoded, 'html.parser')
        title = soup.title.get_text(' ', strip=True)[:300] if soup.title else ''
        for node in soup.find_all('meta'):
            name = str(node.get('property') or node.get('name') or '').lower()
            if name in ('article:published_time', 'article:modified_time', 'date',
                        'datepublished', 'datemodified', 'dc.date', 'dcterms.modified'):
                dates.append({'value': str(node.get('content') or '')[:160], 'origin': 'meta:' + name})
        for node in soup.find_all('time', datetime=True)[:12]:
            dates.append({'value': str(node['datetime'])[:160],
                          'origin': 'time:' + node.get_text(' ', strip=True)[:160]})
        for node in soup.find_all('script', type='application/ld+json')[:8]:
            try:
                data = json.loads(node.get_text())
                queue = [data]
                for _ in range(100):
                    if not queue:
                        break
                    item = queue.pop(0)
                    if isinstance(item, dict):
                        for key in ('datePublished', 'dateModified', 'validFrom', 'validThrough', 'version'):
                            if isinstance(item.get(key), (str, int)):
                                dates.append({'value': str(item[key])[:160], 'origin': 'json-ld:' + key})
                        queue.extend(item.values())
                    elif isinstance(item, list):
                        queue.extend(item[:30])
            except (ValueError, TypeError, RecursionError):
                pass
        for node in soup(['script', 'style', 'nav', 'footer', 'noscript', 'svg', 'form']):
            node.decompose()
        # Prefer the article body, retaining its tables and headings.
        bodies = soup.find_all(['main', 'article'])
        if bodies:
            body = max(bodies, key=lambda n: len(n.get_text(' ', strip=True)))
            if len(body.get_text(' ', strip=True)) >= 80:
                soup = body
        # Preserve heading/paragraph/row boundaries and neighboring context.
        for node in soup.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'li', 'tr', 'section', 'br']):
            node.insert_before('\n')
            node.insert_after('\n')
        decoded = soup.get_text(' ', strip=False)
    text = '\n'.join(' '.join(line.split()) for line in decoded.splitlines() if line.strip())
    if headers.get('last-modified'):
        dates.append({'value': headers['last-modified'][:160], 'origin': 'http:last-modified'})
    return {'url': url, 'title': title, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'dates': dates[:24], 'text': text[:limits.max_bytes],
            'truncated': truncated or len(text) > limits.max_bytes,
            'content_hash': hashlib.sha256(content).hexdigest()}


def select_passages(document, claims, question, max_chars):
    """Select original spans from the whole bounded body; never synthesize evidence."""
    body = str(document.get('text') or '')
    if len(body) <= max_chars:
        return {**document, 'text': body, 'selection': 'full_document'}
    # Offsets retain exact original strings, including table rows and numbers.
    spans = [(m.start(), m.end()) for m in re.finditer(r'[^\n]+', body)]
    chunks = []
    for start, end in spans:
        while end - start > 700:
            stop = body.rfind(' ', start + 350, start + 700)
            stop = stop if stop > start else start + 700
            chunks.append((start, stop))
            start = stop
        chunks.append((start, end))
    queries = [question] + [str(c.get('claim', c)) if isinstance(c, dict) else str(c) for c in claims]
    stopwords = {'the', 'and', 'for', 'that', 'with', 'this', 'what', 'does', 'from', 'are', 'was', 'has', 'have',
                 'der', 'die', 'das', 'und', 'mit', 'eine', 'einer', 'ist', 'sind', 'von', 'auf', 'den'}
    token_sets = [{w for w in re.findall(r'[\w€$%]+', q.lower()) if (len(w) > 2 or w.isdigit()) and w not in stopwords} for q in queries]
    scores = []
    for i, (a, b) in enumerate(chunks):
        words = set(re.findall(r'[\w€$%]+', body[a:b].lower()))
        score = max((sum(3 if w.isdigit() else 1 for w in tokens & words) / max(1, len(tokens)) for tokens in token_sets), default=0)
        scores.append((score, i))
    selected, used = set(), 0
    # Include the strongest match first and neighboring qualifications while space remains.
    for _, index in sorted(scores, key=lambda row: (-row[0], row[1])):
        for nearby in (index, index - 1, index + 1):
            if nearby < 0 or nearby >= len(chunks) or nearby in selected:
                continue
            a, b = chunks[nearby]
            size = b - a + (1 if selected else 0)
            if used + size <= max_chars:
                selected.add(nearby)
                used += size
    text = '\n'.join(body[chunks[i][0]:chunks[i][1]] for i in sorted(selected))
    if not text and max_chars > 0:
        best = sorted(scores, key=lambda row: (-row[0], row[1]))[0][1] if scores else 0
        a = chunks[best][0] if chunks else 0
        text = body[a:a + max_chars]
    return {**document, 'text': text, 'truncated': True, 'selection': 'relevant_passages'}


def fetch_document(url, limits):
    url = urlunsplit(urlsplit(url)._replace(fragment=''))
    cache_key = (url, limits.max_bytes)
    with _lock:
        cached = _cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < (min(30, limits.cache_seconds) if cached[2] else limits.cache_seconds):
            _cache.move_to_end(cache_key)
            _metric('negative_cache_hit' if cached[2] else 'cache_hit')
            if cached[2]:
                raise ValueError(cached[2])
            return copy.deepcopy(cached[1])
        future = _inflight.get(cache_key)
        owner = future is None
        if owner:
            future = _inflight[cache_key] = Future()
    if not owner:
        _metric('singleflight_wait')
        try:
            return copy.deepcopy(future.result(timeout=limits.fetch_seconds))
        except Exception as exc:
            raise ValueError(fetch_failure_code(exc)) from None

    started = time.monotonic()
    async def fetch():
        return await asyncio.wait_for(_download(url, limits), timeout=limits.fetch_seconds)
    try:
        final_url, content, kind, headers, truncated = asyncio.run(fetch())
        result = extract_document(final_url, content, kind, headers, truncated, limits)
        with _lock:
            _cache[cache_key] = (time.monotonic(), result, '')
        future.set_result(result)
        _metric('fetch', duration_ms=(time.monotonic() - started) * 1000, processed=1)
        return copy.deepcopy(result)
    except Exception as exc:
        code = fetch_failure_code(exc)
        with _lock:
            _cache[cache_key] = (time.monotonic(), None, code)
        future.set_exception(ValueError(code))
        _metric(code, outcome='timeout' if code == 'fetch_timeout' else 'failure')
        raise ValueError(code) from None
    finally:
        with _lock:
            _inflight.pop(cache_key, None)
            while len(_cache) > 128:
                _cache.popitem(last=False)
