"""Explicit, bounded live probe of OpenRouter's ``openrouter:web_fetch`` server tool.

Answers, before any product change (docs/agent-mode.md, "Quellen lesen"):
1. Does the fetched page text reach the client, in which field, also streamed?
2. Which usage field counts the fetches, and what do they cost?
3. Does ``engine: auto`` run under ZDR, and which engine serves it?
4. Are allowed_domains, max_uses and max_content_tokens enforced?
5. Is a PDF readable, and how long does a fetch take?
"coverage" compares it with our own fetcher (source_documents.fetch_document)
on typical source pages.

Every request uses the Agent's payload shape with ``provider.zdr: true``. The
raw provider events are stored without the API key under --output; strings are
cut to keep the files small. Costs a few cents per model.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.openrouter_contract import OPENROUTER_CHAT_COMPLETIONS_URL, openrouter_headers

MODELS = ("anthropic/claude-sonnet-5.5", "openai/gpt-6-luna", "google/gemini-3.5-flash-lite")
# Stable public documents with a phrase the model would not write unprompted.
DOCUMENTS = {
    "html": {"url": "https://peps.python.org/pep-0020/", "domain": "peps.python.org",
             "ask": "Quote verbatim the sentence of the page that starts with 'Long time Pythoneer'."},
    "pdf": {"url": "https://arxiv.org/pdf/1706.03762", "domain": "arxiv.org",
            "ask": "Quote verbatim the first sentence of the abstract."},
}
STRING_CAP = 6000
# Pages answer models typically cite; our own fetcher fails or reads almost
# nothing on several of them (bot walls, consent pages, PDF).
COVERAGE_URLS = (
    "https://en.wikipedia.org/wiki/Heat_pump", "https://www.reuters.com/technology/", "https://www.heise.de/",
    "https://www.bundesregierung.de/breg-de", "https://www.nytimes.com/", "https://www.statista.com/",
    "https://openai.com/index/", "https://www.anthropic.com/news", "https://docs.python.org/3/whatsnew/3.13.html",
    "https://arxiv.org/abs/1706.03762", "https://www.bbc.com/news", "https://www.spiegel.de/",
    "https://www.verbraucherzentrale.de/", "https://www.tagesschau.de/", "https://www.techradar.com/",
    "https://www.theverge.com/", "https://www.investopedia.com/terms/i/inflation.asp", "https://www.who.int/",
    "https://www.bloomberg.com/", "https://www.zeit.de/", "https://arxiv.org/pdf/1706.03762",
)


def _cut(value):
    if isinstance(value, str):
        return value if len(value) <= STRING_CAP else value[:STRING_CAP] + f"...[{len(value)} chars]"
    if isinstance(value, list):
        return [_cut(item) for item in value]
    if isinstance(value, dict):
        return {key: _cut(item) for key, item in value.items()}
    return value


def _paths(value, prefix=""):
    """Every JSON path with the total string length found under it."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _paths(item, f"{prefix}.{key}" if prefix else key)
    elif isinstance(value, list):
        for item in value:
            yield from _paths(item, prefix + "[]")
    else:
        yield prefix, len(value) if isinstance(value, str) else 0


def fetch_tool(*, engine="auto", max_uses=2, max_content_tokens=4000, allowed_domains=None):
    parameters = {"engine": engine, "max_uses": max_uses, "max_content_tokens": max_content_tokens}
    if allowed_domains:
        parameters["allowed_domains"] = allowed_domains
    return {"type": "openrouter:web_fetch", "parameters": parameters}


def run(key, model, prompt, tool, *, stream):
    payload = {"model": model, "messages": [
        {"role": "system", "content": "You can open web pages with the web_fetch tool. Use it when asked to read a URL. "
                                      "Answer briefly."},
        {"role": "user", "content": prompt}],
        "max_tokens": 4096, "provider": {"zdr": True}, "tools": [tool]}
    if stream:
        payload.update(stream=True, stream_options={"include_usage": True})
    started = time.monotonic()
    result = {"model": model, "stream": stream, "tool": tool, "prompt": prompt}
    try:
        response = requests.post(OPENROUTER_CHAT_COMPLETIONS_URL, headers=openrouter_headers(key),
                                 json=payload, timeout=240, stream=stream)
        result["http_status"] = response.status_code
        if response.status_code >= 400:
            result["error_body"] = _cut(response.text)
            return result
        if not stream:
            body = response.json()
            result["raw"] = _cut(body)
            message = ((body.get("choices") or [{}])[0] or {}).get("message") or {}
            result.update(text=message.get("content"), usage=body.get("usage"),
                          message_keys=sorted(message), annotations=_cut(message.get("annotations")),
                          finish_reason=((body.get("choices") or [{}])[0] or {}).get("finish_reason"))
            result["paths"] = dict(Counter(dict(_paths(body))))
            return result
        events, comments, text, first = [], Counter(), "", None
        paths = Counter()
        for raw in response.iter_lines(decode_unicode=True):
            if raw is None or raw == "":
                continue
            if raw.startswith(":"):
                comments[raw[:80]] += 1
                continue
            if not raw.startswith("data:"):
                comments["other:" + raw[:60]] += 1
                continue
            data = raw[5:].strip()
            if data == "[DONE]":
                break
            event = json.loads(data)
            for path, length in _paths(event):
                paths[path] += length or 1
            for choice in event.get("choices") or []:
                chunk = (choice.get("delta") or {}).get("content")
                if chunk:
                    if first is None:
                        first = time.monotonic() - started
                    text += chunk
                if choice.get("finish_reason"):
                    result["finish_reason"] = choice["finish_reason"]
            if event.get("usage"):
                result["usage"] = event["usage"]
            # Keep everything except plain content/reasoning deltas.
            delta_keys = {k for c in event.get("choices") or [] for k in (c.get("delta") or {})}
            if delta_keys - {"content", "role", "reasoning", "reasoning_details"} or set(event) - {
                    "id", "provider", "model", "object", "created", "choices", "system_fingerprint"} or not events:
                events.append(_cut(event))
        result.update(text=text, ttft_s=round(first, 2) if first else None, comments=dict(comments),
                      paths=dict(paths), events=events[:60])
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    finally:
        result["elapsed_s"] = round(time.monotonic() - started, 2)
    return result


def run_responses(key, model, prompt, tool):
    """The Responses API may list server tool calls as output items."""
    payload = {"model": model, "input": [{"role": "user", "content": prompt}], "tools": [tool],
               "max_output_tokens": 4096, "provider": {"zdr": True}}
    started = time.monotonic()
    result = {"model": model, "stream": False, "tool": tool, "prompt": prompt, "api": "responses"}
    try:
        response = requests.post(OPENROUTER_CHAT_COMPLETIONS_URL.replace("/chat/completions", "/responses"),
                                 headers=openrouter_headers(key), json=payload, timeout=240)
        result["http_status"] = response.status_code
        if response.status_code >= 400:
            result["error_body"] = _cut(response.text)
            return result
        body = response.json()
        for item in body.get("output") or []:
            if item.get("type") == "openrouter:web_fetch":
                # The stored copy is cut (STRING_CAP); keep the real length.
                item["content_chars"] = len(item.get("content") or "")
        result.update(raw=_cut(body), usage=body.get("usage"), paths=dict(Counter(dict(_paths(body)))),
                      output_types=[item.get("type") for item in body.get("output") or []])
        result["text"] = "".join(part.get("text", "") for item in body.get("output") or []
                                 if item.get("type") == "message" for part in item.get("content") or [])
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    finally:
        result["elapsed_s"] = round(time.monotonic() - started, 2)
    return result


def summary(result, phrase=None):
    usage = result.get("usage") or {}
    text = result.get("text") or ""
    raw = json.dumps(result.get("raw") or result.get("events") or [], ensure_ascii=False)
    return {k: v for k, v in {
        "model": result["model"], "stream": result["stream"], "engine": result["tool"]["parameters"].get("engine"),
        "http": result.get("http_status"), "error": result.get("error") or (result.get("error_body") or "")[:300] or None,
        "elapsed_s": result.get("elapsed_s"), "ttft_s": result.get("ttft_s"), "finish": result.get("finish_reason"),
        "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
        "cost": usage.get("cost"), "server_tool_use": usage.get("server_tool_use"),
        "usage_keys": sorted(usage), "server_tool_use_details": usage.get("server_tool_use_details"),
        "fetches": [{"status": item.get("status"), "url": item.get("url"), "http": item.get("httpStatus"),
                     "chars": item.get("content_chars", 0), "error": (item.get("error") or "")[:200] or None}
                    for item in (result.get("raw") or {}).get("output") or [] if item.get("type") == "openrouter:web_fetch"]
        if result.get("api") == "responses" else None,
        "phrase_in_answer": bool(phrase and phrase.lower() in text.lower()),
        "phrase_in_raw_outside_answer": bool(phrase and raw.lower().count(phrase.lower()) > text.lower().count(phrase.lower())),
        "text": text[:400],
    }.items() if v is not None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True, help="Authorize the paid requests")
    parser.add_argument("--model", action="append")
    parser.add_argument("--case", action="append", help="basic, stream, responses, engines, limits, coverage (default: all)")
    parser.add_argument("--output", default="artifacts/web-fetch-probe")
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        parser.error("OPENROUTER_API_KEY is required")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    cases = set(args.case or ["basic", "stream", "responses", "engines", "limits", "coverage"])
    phrases = {"html": "succinctly channels", "pdf": "dominant sequence transduction"}
    summaries = []

    def record(name, result, phrase=None):
        (out / f"{name}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        line = {"case": name, **summary(result, phrase)}
        summaries.append(line)
        print(json.dumps(line), flush=True)

    for model in (args.model or MODELS) if cases - {"coverage"} else ():
        slug = model.split("/")[-1]
        for kind, doc in DOCUMENTS.items():
            prompt = f"Read {doc['url']} with the fetch tool. {doc['ask']}"
            if "basic" in cases:
                record(f"{slug}-{kind}-nonstream", run(key, model, prompt, fetch_tool(), stream=False), phrases[kind])
            if "stream" in cases:
                record(f"{slug}-{kind}-stream", run(key, model, prompt, fetch_tool(), stream=True), phrases[kind])
            if "responses" in cases:
                record(f"{slug}-{kind}-responses", run_responses(key, model, prompt, fetch_tool()), phrases[kind])
        if "engines" in cases:
            doc = DOCUMENTS["html"]
            prompt = f"Read {doc['url']} with the fetch tool. {doc['ask']}"
            for engine in ("native", "exa", "openrouter"):
                record(f"{slug}-engine-{engine}", run_responses(key, model, prompt, fetch_tool(engine=engine)),
                       phrases["html"])
        if "limits" in cases:
            # allowed_domains: the page is outside the allowed list.
            doc = DOCUMENTS["html"]
            prompt = f"Read {doc['url']} with the fetch tool. {doc['ask']} If the tool fails, say FETCH_FAILED."
            record(f"{slug}-limit-domain", run_responses(key, model, prompt, fetch_tool(allowed_domains=["example.org"])),
                   phrases["html"])
            # max_uses: three pages asked for, one fetch allowed.
            prompt = ("Read all three pages with the fetch tool, one after another, and give each page's title: "
                      "https://peps.python.org/pep-0020/ https://peps.python.org/pep-0008/ https://peps.python.org/pep-0257/")
            record(f"{slug}-limit-uses", run_responses(key, model, prompt, fetch_tool(max_uses=1)))
            # max_content_tokens: a long page cut to 500 tokens; the phrase sits late in it.
            prompt = ("Read https://peps.python.org/pep-0008/ with the fetch tool. Quote verbatim the last sentence "
                      "you can see of the fetched text, and say whether the text looked cut off.")
            record(f"{slug}-limit-tokens", run_responses(key, model, prompt, fetch_tool(max_content_tokens=500)))
    if "coverage" in cases:
        from app.services.source_documents import fetch_document
        from app.services.source_verification import Limits
        rows = []
        for url in COVERAGE_URLS:
            started = time.monotonic()
            try:
                own = {"status": "completed", "chars": len(fetch_document(url, Limits())["text"])}
            except ValueError as exc:
                own = {"status": "failed", "error": str(exc)}
            own["s"] = round(time.monotonic() - started, 2)
            result = run_responses(key, "openai/gpt-6-luna", f"Read {url} with the fetch tool and reply with only its title.",
                                   fetch_tool())
            items = [item for item in (result.get("raw") or {}).get("output") or []
                     if item.get("type") == "openrouter:web_fetch"]
            rows.append({"url": url, "own": own, "openrouter": {
                "s": result.get("elapsed_s"), "cost": (result.get("usage") or {}).get("cost"),
                "fetches": [{"status": item.get("status"), "http": item.get("httpStatus"),
                             "chars": item.get("content_chars", 0), "error": (item.get("error") or "")[:120] or None}
                            for item in items]}})
            print(json.dumps(rows[-1]), flush=True)
        (out / "coverage.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    report = {"date": datetime.now(timezone.utc).isoformat(), "kind": "live_web_fetch_probe", "results": summaries}
    (out / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
