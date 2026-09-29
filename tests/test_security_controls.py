from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import chat as chat_router
from app.api.routers import pages as pages_router
from app.core.rate_limit import limiter


def make_client(router):
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(router)
    return TestClient(app)


def test_check_keys_requires_verified_login():
    client = make_client(pages_router.router)

    response = client.post("/check_keys", json={"openrouter_key": "sk-test-value"})

    assert response.status_code == 401


def test_check_keys_requires_at_least_one_key_after_auth():
    client = make_client(pages_router.router)

    with patch.object(pages_router, "verify_user_token", return_value="uid-1"):
        response = client.post(
            "/check_keys",
            headers={"Authorization": "Bearer token"},
            json={},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Enter an OpenRouter API key to test."


def test_user_api_key_requests_require_login():
    client = make_client(chat_router.router)

    response = client.post(
        "/ask_openai",
        json={
            "question": "hello",
            "useOwnKeys": True,
            "openrouter_key": "sk-user-key",
            "model": "gpt-5.4-mini",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == chat_router.OWN_KEYS_LOGIN_REQUIRED


def test_validation_errors_stay_422_and_never_echo_the_submitted_value():
    """Der globale Handler in main.py muss ValueError-Validatoren ueberleben.

    Fast jeder Validator in diesem Projekt meldet ungueltige Eingaben als
    ValueError. Pydantic v2 haengt dieses ROHE Exception-Objekt in errors()
    unter "ctx" -- der Handler serialisierte das direkt und lief in einen
    TypeError, sodass die Antwort ein 500er statt eines 422ers wurde. Die
    Unit-Tests der einzelnen Router sehen das nicht: sie bauen eigene
    FastAPI-Apps ohne diesen Handler.
    """
    import main

    client = TestClient(main.app)
    response = client.post(
        "/chats/" + "a" * 32 + "/turns",
        json={
            "question": "Test",
            "mode": "x" * 41,  # ValueError aus normalize_mode
            "deep_search": False,
            "selected_models": ["OpenAI"],
            "consensus_model": "OpenAI",
        },
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "Validation failed"
    assert payload["details"], "der Grund der Ablehnung muss erkennbar bleiben"
    for entry in payload["details"]:
        assert set(entry) == {"loc", "type", "msg"}
        assert all(isinstance(part, str) for part in entry["loc"])
    # Weder das rohe Exception-Objekt noch der eingesendete Wert gehen zurueck.
    body = response.text
    assert "ctx" not in body
    assert "x" * 41 not in body


def _client_with_registered_http_handler():
    """Frische App, aber mit genau dem Handler-Objekt, das main.app registriert."""
    import main
    from fastapi import HTTPException

    handler = main.app.exception_handlers[HTTPException]
    app = FastAPI()
    app.add_exception_handler(HTTPException, handler)

    @app.get("/busy")
    def busy():
        raise HTTPException(status_code=429, detail="busy", headers={"Retry-After": "15"})

    @app.get("/unavailable")
    def unavailable():
        raise HTTPException(status_code=503, detail="later", headers={"Retry-After": "5"})

    @app.get("/auth")
    def auth():
        raise HTTPException(status_code=401, detail="login", headers={"WWW-Authenticate": "Bearer"})

    @app.get("/plain")
    def plain():
        raise HTTPException(status_code=404, detail="missing")

    return TestClient(app)


def test_registered_http_exception_handler_preserves_headers():
    """R04: Retry-After/WWW-Authenticate duerfen im JSON-Fehlerformat nicht verloren gehen."""
    client = _client_with_registered_http_handler()

    busy = client.get("/busy")
    assert busy.status_code == 429
    assert busy.headers["retry-after"] == "15"
    assert busy.json() == {"error": "busy"}

    unavailable = client.get("/unavailable")
    assert unavailable.status_code == 503
    assert unavailable.headers["retry-after"] == "5"

    auth = client.get("/auth")
    assert auth.status_code == 401
    assert auth.headers["www-authenticate"] == "Bearer"

    plain = client.get("/plain")
    assert plain.status_code == 404
    assert plain.json() == {"error": "missing"}
    assert "retry-after" not in plain.headers
