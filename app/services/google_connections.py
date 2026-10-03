"""Owner-bound Google OAuth, encrypted credentials and bounded API transport.

No token, provider error body, authorization code or refresh request is exposed
to agent tools. OAuth consent and tool selection are separate user decisions.
"""
from __future__ import annotations
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
import secrets
from urllib.parse import urlencode, urlparse

from cryptography.fernet import Fernet, MultiFernet, InvalidToken
import httpx
import jwt

from app.services import persistence_guard
from app.services.chat_store import ChatStore

SCOPES = {
    "calendar_read": ["https://www.googleapis.com/auth/calendar.readonly"],
    "calendar_write": ["https://www.googleapis.com/auth/calendar.events"],
    "gmail_read": ["https://www.googleapis.com/auth/gmail.readonly"],
    "gmail_send": ["https://www.googleapis.com/auth/gmail.send"],
}
IDENTITY_SCOPES = ["openid", "email"]
TOKEN_URL = "https://oauth2.googleapis.com/token"
# Sending email and creating/changing events. Google is a source of evidence
# in Consens; writing back is a separate operator decision (off by default).
WRITE_CAPABILITIES = {"calendar_write", "gmail_send"}


class GoogleError(ValueError):
    def __init__(self, message, status=422, *, uncertain=False):
        super().__init__(message)
        self.status, self.uncertain = status, uncertain


def now():
    return datetime.now(timezone.utc)


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def configuration():
    values = {key: os.getenv("GOOGLE_" + key, "") for key in ("CLIENT_ID", "CLIENT_SECRET", "REDIRECT_URI", "TOKEN_KEYS")}
    if os.getenv("GOOGLE_INTEGRATIONS_ENABLED") != "1" or not all(values.values()):
        raise GoogleError("Google connections are not configured on this installation.", 503)
    uri = urlparse(values["REDIRECT_URI"])
    # Plain http only for a local checkout (Google allows loopback redirects);
    # a hosted deploy always needs https, like the private file store.
    hosted = bool(os.getenv("RENDER_SERVICE_NAME")) or os.getenv("ENVIRONMENT") == "production"
    local = uri.hostname in {"localhost", "127.0.0.1"} and (os.getenv("UNIT_TEST_MODE") == "1" or not hosted)
    if (uri.scheme != "https" and not local) or uri.path != "/agent/google/callback" or uri.query or uri.fragment or uri.username:
        raise GoogleError("Google redirect configuration is invalid.", 503)
    return values


def available():
    try:
        configuration()
        return True
    except GoogleError:
        return False


def writes_enabled():
    """Read access works without this; tools that prepare emails or events,
    their confirmation and the write scopes all need GOOGLE_WRITES_ENABLED=1."""
    return os.getenv("GOOGLE_WRITES_ENABLED") == "1"


def drive_picker():
    """Public browser configuration for Google's own file picker, or None.

    Drive needs no stored grant and no server secret: the browser asks Google
    for a short-lived drive.file token, the user picks files in Google's
    picker, and the picked files become ordinary chat attachments. All three
    values are public by design (the API key is restricted to the Picker API
    and this site's origin in the Cloud console).
    """
    if os.getenv("GOOGLE_INTEGRATIONS_ENABLED") != "1":
        return None
    client_id, api_key, app_id = (os.getenv(key, "").strip() for key in ("GOOGLE_CLIENT_ID", "GOOGLE_PICKER_API_KEY", "GOOGLE_PROJECT_NUMBER"))
    if not (client_id and re.fullmatch(r"[A-Za-z0-9_-]{20,100}", api_key) and re.fullmatch(r"\d{6,20}", app_id)):
        return None
    return {"client_id": client_id, "api_key": api_key, "app_id": app_id}


class Wire:
    """Allowlisted callers provide fixed Google hosts; no automatic retries."""
    def request(self, method, url, **kwargs):
        if urlparse(url).hostname not in {"oauth2.googleapis.com", "www.googleapis.com", "gmail.googleapis.com"}:
            raise GoogleError("Invalid Google API destination.")
        try:
            with httpx.Client(timeout=15, follow_redirects=False) as client:
                with client.stream(method, url, **kwargs) as response:
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 8_000_000:
                            raise GoogleError("Google response is too large. Narrow the request.", uncertain=method != "GET")
                    data = json.loads(raw) if raw else {}
                    if not isinstance(data, dict):
                        raise GoogleError("Unexpected Google response.", uncertain=method != "GET")
                    if response.status_code >= 400:
                        invalid = url == TOKEN_URL and data.get("error") == "invalid_grant"
                        raise GoogleError("Google authorization expired or was revoked. Reconnect the account." if invalid or response.status_code == 401
                            else "Google rejected the request. Check permissions or retry later.", 401 if invalid else response.status_code,
                            uncertain=method != "GET" and response.status_code >= 500)
                    if response.status_code >= 300 or not isinstance(data, dict):
                        raise GoogleError("Unexpected Google response.", uncertain=method != "GET")
                    return data
        except (httpx.HTTPError, ValueError) as exc:
            if isinstance(exc, GoogleError):
                raise
            raise GoogleError("Google did not return a reliable result. Check the action status before retrying.", 503, uncertain=method != "GET") from None


def public_connection(data):
    public = {key: data[key] for key in ("id", "email", "status", "capabilities", "updated_at", "revision") if key in data}
    # A grant can still hold write scopes from an earlier consent; without
    # writes they must not look usable anywhere.
    if "capabilities" in public and not writes_enabled():
        public["capabilities"] = [c for c in public["capabilities"] if c not in WRITE_CAPABILITIES]
    return public


def restricted_model(model):
    """Routing boundary for every model call in a chat with Google data,
    including comparison and review models.

    Each request requires zero data retention and excludes every endpoint that
    may collect or train on prompts. OpenRouter fails such a call closed when
    no endpoint qualifies; that model then fails like any other unavailable
    model, the run continues with the others. Operators can narrow this
    further with GOOGLE_ALLOWED_MODEL_IDS and GOOGLE_ALLOWED_PROVIDERS.
    """
    from dataclasses import replace
    allowed = set(filter(None, (s.strip() for s in os.getenv("GOOGLE_ALLOWED_MODEL_IDS", "").split(","))))
    providers = list(filter(None, (s.strip() for s in os.getenv("GOOGLE_ALLOWED_PROVIDERS", "").split(","))))
    if allowed and model.model not in allowed:
        raise GoogleError("This model is not approved for Google data on this installation. Choose another model for this chat.", 403)
    provider = {**(model.request_config.get("provider") or {}), "zdr": True, "data_collection": "deny"}
    if providers:
        provider.update(only=providers, allow_fallbacks=False)
    return replace(model, request_config={**model.request_config, "provider": provider})


class GoogleConnections:
    def __init__(self, db, wire=None):
        self.db, self.chats, self.wire = db, ChatStore(db), wire or Wire()

    def ref(self, uid, connection_id):
        if not re.fullmatch(r"[a-f0-9]{32}", connection_id):
            raise GoogleError("Invalid connection ID.")
        return self.db.collection("users").document(uid).collection("google_connections").document(connection_id)

    def control(self, uid):
        return self.db.collection("users").document(uid).collection("chat_state").document("google_control")

    def cipher(self):
        try:
            return MultiFernet([Fernet(key.strip().encode()) for key in configuration()["TOKEN_KEYS"].split(",")])
        except (ValueError, TypeError):
            raise GoogleError("Google credential encryption is not configured correctly.", 503) from None

    def seal(self, uid, identifier, value):
        return self.cipher().encrypt(json.dumps({"uid": uid, "id": identifier, "value": value}).encode()).decode()

    def unseal(self, uid, identifier, value):
        try:
            decoded = json.loads(self.cipher().decrypt(value.encode()))
            if decoded["uid"] != uid or decoded["id"] != identifier:
                raise InvalidToken()
            return decoded["value"]
        except (InvalidToken, ValueError, KeyError):
            raise GoogleError("Google credentials cannot be read. Reconnect this account.", 401) from None

    def guard(self, uid, tx=None):
        persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=tx)

    def list(self, uid):
        self.guard(uid)
        return [public_connection(s.to_dict()) for s in self.db.collection("users").document(uid).collection("google_connections").limit(10).stream()]

    def get(self, uid, connection_id, capability=None, tx=None):
        self.guard(uid, tx)
        data = self.ref(uid, connection_id).get(transaction=tx).to_dict()
        if not data or data.get("status") != "connected":
            raise GoogleError("This Google account is disconnected or needs authorization.", 401)
        if capability and capability not in data.get("capabilities", []):
            raise GoogleError("Authorize the required Google permission first.", 403)
        return data

    def consume_quota(self, uid):
        ref = self.db.collection("users").document(uid).collection("chat_state").document("google_quota")
        today = now().date().isoformat()
        def operation(tx):
            self.guard(uid, tx)
            data = ref.get(transaction=tx).to_dict() or {}
            count = data.get("count", 0) if data.get("day") == today else 0
            if count >= 500:
                raise GoogleError("Daily Google request limit reached. Try again tomorrow.", 429)
            tx.set(ref, {"day": today, "count": count + 1})
        self.chats._transaction(operation)

    def start(self, uid, capabilities, *, connection_id=None):
        config = configuration()
        self.guard(uid)
        if not capabilities or any(c not in SCOPES for c in capabilities):
            raise GoogleError("Unknown Google permission request.")
        if not writes_enabled() and WRITE_CAPABILITIES & set(capabilities):
            raise GoogleError("Consens only reads Google data on this installation.", 403)
        existing = None
        if connection_id:
            existing = self.ref(uid, connection_id).get().to_dict()
            if not existing:
                raise GoogleError("Connection not found.", 404)
        if len(self.list(uid)) >= 5 and not existing:
            raise GoogleError("At most five Google accounts can be connected.")
        self.consume_quota(uid)
        state, verifier, browser, nonce = [secrets.token_urlsafe(32) for _ in range(4)]
        state_id = sha(state)
        scopes = sorted(set(IDENTITY_SCOPES + [s for c in capabilities for s in SCOPES[c]]))
        data = {"id": state_id, "expires_at": (now() + timedelta(minutes=10)).isoformat(), "browser_hash": sha(browser),
            "secret": self.seal(uid, state_id, {"verifier": verifier, "nonce": nonce}), "scopes": scopes,
            "connection_id": connection_id, "revision": (existing or {}).get("revision")}
        ref = self.db.collection("users").document(uid).collection("google_oauth_states").document(state_id)
        def save(tx):
            self.guard(uid, tx)
            control = self.control(uid).get(transaction=tx).to_dict() or {}
            data["epoch"] = control.get("epoch", 0)
            tx.set(ref, data)
        self.chats._transaction(save)
        query = {"client_id": config["CLIENT_ID"], "redirect_uri": config["REDIRECT_URI"], "response_type": "code", "scope": " ".join(scopes),
            "state": state, "access_type": "offline", "include_granted_scopes": "true", "prompt": "consent select_account", "nonce": nonce,
            "code_challenge": base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("="), "code_challenge_method": "S256"}
        if existing:
            query["login_hint"] = existing["email"]
        return {"url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(query), "state": state}, browser

    def identity(self, token, nonce):
        try:
            header = jwt.get_unverified_header(token)
            keys = self.wire.request("GET", "https://www.googleapis.com/oauth2/v3/certs")["keys"]
            key = next(k for k in keys if k["kid"] == header.get("kid"))
            data = jwt.decode(token, jwt.PyJWK(key).key, algorithms=["RS256"], audience=configuration()["CLIENT_ID"],
                issuer=["accounts.google.com", "https://accounts.google.com"], options={"require": ["exp", "iss", "aud", "sub", "nonce"]})
            if (data["nonce"] != nonce or not data.get("email_verified") or not data.get("email")
                or data.get("azp", configuration()["CLIENT_ID"]) != configuration()["CLIENT_ID"]):
                raise ValueError()
            return data
        except (ValueError, KeyError, StopIteration, jwt.PyJWTError):
            raise GoogleError("Google identity verification failed.", 401) from None

    def finish(self, uid, state, code, browser):
        config = configuration()
        state_id = sha(state)
        ref = self.db.collection("users").document(uid).collection("google_oauth_states").document(state_id)
        def claim(tx):
            self.guard(uid, tx)
            data = ref.get(transaction=tx).to_dict() or {}
            if data.get("expires_at", "") <= now().isoformat() or not secrets.compare_digest(data.get("browser_hash", ""), sha(browser)) or data.get("used"):
                raise GoogleError("Google authorization session expired or does not belong to this browser.", 401)
            tx.update(ref, {"used": True})
            return data
        state_data = self.chats._transaction(claim)
        secret = self.unseal(uid, state_id, state_data["secret"])
        token = self.wire.request("POST", TOKEN_URL, data={"code": code, "client_id": config["CLIENT_ID"], "client_secret": config["CLIENT_SECRET"],
            "redirect_uri": config["REDIRECT_URI"], "grant_type": "authorization_code", "code_verifier": secret["verifier"]})
        identity = self.identity(token.get("id_token", ""), secret["nonce"])
        connection_id = sha(identity["sub"])[:32]
        if state_data["connection_id"] and state_data["connection_id"] != connection_id:
            raise GoogleError("The selected Google account differs from the account being reconnected.", 409)
        target = self.ref(uid, connection_id)
        granted = token.get("scope", "").split()
        if not token.get("access_token") or not granted:
            raise GoogleError("Google did not return the requested authorization.", 401)
        def save(tx):
            self.guard(uid, tx)
            control = self.control(uid).get(transaction=tx).to_dict() or {}
            existing = target.get(transaction=tx).to_dict() or {}
            if control.get("epoch", 0) != state_data["epoch"]:
                raise GoogleError("Google access changed during authorization. Start again.", 409)
            identifiers = list(dict.fromkeys([*control.get("connections", []), connection_id]))
            if len(identifiers) > 5:
                raise GoogleError("At most five Google accounts can be connected.")
            if state_data["connection_id"] and existing.get("revision") != state_data["revision"]:
                raise GoogleError("The connection changed during authorization. Start again.", 409)
            old = self.unseal(uid, connection_id, existing["credentials"]) if existing.get("credentials") else {}
            refresh = token.get("refresh_token") or old.get("refresh_token")
            if not refresh:
                raise GoogleError("Offline access was not granted. Reconnect with consent.", 401)
            credentials = {"access_token": token["access_token"], "refresh_token": refresh,
                "expires_at": (now() + timedelta(seconds=min(int(token.get("expires_in", 3600)), 86400))).isoformat()}
            data = {"id": connection_id, "email": identity["email"], "status": "connected", "scopes": granted,
                "capabilities": [cap for cap, required in SCOPES.items() if set(required) <= set(granted)],
                "revision": secrets.token_hex(16), "credentials": self.seal(uid, connection_id, credentials), "updated_at": now().isoformat()}
            tx.set(target, data)
            tx.set(self.control(uid), {**control, "connections": identifiers})
            tx.delete(ref)
            return public_connection(data)
        return self.chats._transaction(save)

    def access_token(self, uid, connection_id, capability):
        ref = self.ref(uid, connection_id)
        data = self.get(uid, connection_id, capability)
        credentials = self.unseal(uid, connection_id, data["credentials"])
        if credentials["expires_at"] > (now() + timedelta(seconds=60)).isoformat():
            return credentials["access_token"], data["revision"]
        lease = secrets.token_hex(16)
        def claim(tx):
            current = self.get(uid, connection_id, capability, tx)
            if current["revision"] != data["revision"] or current.get("refresh_until", "") > now().isoformat():
                raise GoogleError("Google authorization is being refreshed. Retry shortly.", 409)
            tx.update(ref, {"refresh_lease": lease, "refresh_until": (now() + timedelta(seconds=30)).isoformat()})
        self.chats._transaction(claim)
        try:
            config = configuration()
            fresh = self.wire.request("POST", TOKEN_URL, data={"grant_type": "refresh_token", "refresh_token": credentials["refresh_token"],
                "client_id": config["CLIENT_ID"], "client_secret": config["CLIENT_SECRET"]})
            if not fresh.get("access_token"):
                raise GoogleError("Google did not return an access token.", 401)
            credentials.update(access_token=fresh["access_token"], refresh_token=fresh.get("refresh_token") or credentials["refresh_token"],
                expires_at=(now() + timedelta(seconds=min(int(fresh.get("expires_in", 3600)), 86400))).isoformat())
            def save(tx):
                current = self.get(uid, connection_id, capability, tx)
                if current["revision"] != data["revision"] or current.get("refresh_lease") != lease:
                    raise GoogleError("The connection changed while refreshing.", 409)
                scopes = fresh.get("scope", " ".join(current["scopes"])).split()
                caps = [cap for cap, required in SCOPES.items() if set(required) <= set(scopes)]
                tx.update(ref, {"credentials": self.seal(uid, connection_id, credentials), "refresh_until": "", "refresh_lease": "",
                    "scopes": scopes, "capabilities": caps})
                return caps
            caps = self.chats._transaction(save)
            if capability not in caps:
                raise GoogleError("Google permission was revoked. Authorize it again.", 403)
            return credentials["access_token"], data["revision"]
        except GoogleError as exc:
            def release(tx):
                self.guard(uid, tx)
                current = ref.get(transaction=tx).to_dict() or {}
                if current.get("revision") == data["revision"] and current.get("refresh_lease") == lease:
                    patch = {"refresh_until": "", "refresh_lease": ""}
                    if exc.status == 401:
                        patch.update(status="reauthorize", credentials="")
                    tx.update(ref, patch)
            self.chats._transaction(release)
            raise

    def api(self, uid, connection_id, capability, method, path, *, cancellation=None, revision=None, **kwargs):
        if cancellation:
            cancellation.raise_if_cancelled()
        self.consume_quota(uid)
        token, current_revision = self.access_token(uid, connection_id, capability)
        if revision and current_revision != revision:
            raise GoogleError("The Google connection changed. Prepare and confirm the action again.", 409)
        if not path.startswith(("/calendar/v3/", "/gmail/v1/")) or ".." in path or "?" in path or "#" in path:
            raise GoogleError("Invalid Google API path.")
        headers = {**kwargs.pop("headers", {}), "Authorization": "Bearer " + token}
        if cancellation:
            cancellation.raise_if_cancelled()
        # A reconnect/revocation after token retrieval must not silently authorize a new operation.
        if self.get(uid, connection_id, capability)["revision"] != current_revision:
            raise GoogleError("The Google connection changed.", 409)
        try:
            origin = "https://gmail.googleapis.com" if path.startswith("/gmail/") else "https://www.googleapis.com"
            result = self.wire.request(method, origin + path, headers=headers, **kwargs)
        except GoogleError as exc:
            if exc.status == 401:
                def invalidate(tx):
                    self.guard(uid, tx)
                    ref = self.ref(uid, connection_id)
                    current = ref.get(transaction=tx).to_dict() or {}
                    if current.get("revision") == current_revision:
                        # Keep the sealed refresh token: an API 401 does not prove the
                        # grant is dead, and disconnect must still be able to revoke it.
                        tx.update(ref, {"status": "reauthorize"})
                self.chats._transaction(invalidate)
            raise
        if cancellation:
            cancellation.raise_if_cancelled()
        return result

    def disconnect(self, uid, connection_id):
        ref = self.ref(uid, connection_id)
        def disable(tx):
            self.guard(uid, tx)
            control = self.control(uid).get(transaction=tx).to_dict() or {}
            data = ref.get(transaction=tx).to_dict()
            if not data:
                raise GoogleError("Connection not found.", 404)
            tx.delete(ref)
            tx.set(self.control(uid), {"epoch": control.get("epoch", 0) + 1,
                "connections": [c for c in control.get("connections", []) if c != connection_id]})
            return data
        data = self.chats._transaction(disable)
        revoked = False
        if data.get("credentials"):
            try:
                token = self.unseal(uid, connection_id, data["credentials"])
                self.wire.request("POST", "https://oauth2.googleapis.com/revoke", data={"token": token["refresh_token"]})
                revoked = True
            except GoogleError:
                pass
        return {"status": "disconnected", "provider_revoked": revoked,
            "notice": "Local access removed. You can also revoke Consens in your Google Account security settings."}

    def revoke_all(self, uid):
        """Best-effort provider revocation for account deletion.

        Runs while the account tombstone blocks writes, so it only reads the
        sealed grants and asks Google to revoke them; deleting the documents
        is left to the deletion job. Returns the number of revoked grants.
        """
        if not available():
            return 0
        revoked = 0
        for snapshot in self.db.collection("users").document(uid).collection("google_connections").stream():
            data = snapshot.to_dict() or {}
            if not data.get("credentials"):
                continue
            try:
                token = self.unseal(uid, snapshot.id, data["credentials"])
                self.wire.request("POST", "https://oauth2.googleapis.com/revoke", data={"token": token["refresh_token"]})
                revoked += 1
            except (GoogleError, KeyError):
                pass
        return revoked


def cleanup_google_data(db=None):
    # Without Google configured nothing is written here, and the collection
    # group indexes may not be deployed: do not fail the hourly task.
    if db is None and not available():
        return 0
    from google.cloud.firestore_v1.base_query import FieldFilter
    if db is None:
        from app.core.security import db_firestore
        db = db_firestore
    count = 0
    for collection, length in (("google_oauth_states", 4), ("actions", 6), ("google_evidence", 6), ("google_write_intents", 4)):
        for snapshot in db.collection_group(collection).where(filter=FieldFilter("expires_at", "<=", now().isoformat())).limit(200).stream():
            pieces = snapshot.reference.path.split("/")
            if len(pieces) == length and pieces[0] == "users" and (length == 4 or pieces[2] == "chats"):
                snapshot.reference.delete()
                count += 1
    return count
