"""Keep upstream status codes when OpenRouter reports errors after HTTP 200."""

import json
from unittest.mock import Mock, patch

import pytest
import requests

from app.services.llm import engines, streaming


def _request(error, *, stream):
    body = {"error": error}
    response = requests.Response()
    response.status_code = 200
    response.close = Mock()
    if stream:
        response.iter_lines = Mock(return_value=iter([
            b'data: {"choices":[{"delta":{"content":"partial"}}]}',
            b"",
            ("data: " + json.dumps(body)).encode(),
            b"",
            b"data: [DONE]",
            b"",
        ]))
    else:
        response._content = json.dumps(body).encode()
    with patch.object(engines.requests, "post", return_value=response) as post:
        if stream:
            result = list(streaming.stream_model_query("openai", "question", "key"))[-1]["result"]
        else:
            result = engines.query_model("openai", "question", "key")
    post.assert_called_once()
    response.close.assert_called_once()
    return result


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("code", [400, 401, 402, 403, 408, 429, 500, 502, 503, 504, "429"])
def test_body_error_preserves_status_without_content_or_retry(stream, code, caplog):
    secret = "owner@example.test|private-provider-response"
    result = _request({
        "code": code,
        "message": secret,
        "metadata": {"raw": secret, "provider_code": secret},
    }, stream=stream)

    expected = "provider_timeout" if int(code) in (408, 504) else "provider_request_failed"
    assert result["error_code"] == expected
    assert result["text"] == ""
    assert result["sources"] == []
    assert f"_ProviderResponseError:{code}" in caplog.text
    assert secret not in caplog.text + json.dumps(result)


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("code", [None, True, 200, 999, "private-code", {"private": "code"}])
def test_untrusted_status_is_not_logged_or_mistaken_for_http_status(stream, code, caplog):
    result = _request({"code": code, "message": "private-message"}, stream=stream)

    assert result["error_code"] == "provider_request_failed"
    assert "category=_ProviderResponseError\n" in caplog.text
    assert "private" not in caplog.text + json.dumps(result)
