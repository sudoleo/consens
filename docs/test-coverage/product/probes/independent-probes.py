"""Opt-in observations on synthetic data; NOT product regression tests.

UNIT_TEST_MODE=1 python docs/test-coverage/product/probes/independent-probes.py
No lifespan, live credentials, database, provider, mail or network access.
The real product functions remain unchanged. A zero exit code means the probe
ran, not that the observed product behavior is correct.
"""
from contextlib import ExitStack
from copy import deepcopy
from datetime import timedelta
import json
import os
from pathlib import Path
import runpy
import socket
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))


def network_forbidden(*args, **kwargs):
    raise AssertionError("Audit probe attempted network access")


def header_probe():
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from app.api.routers import api_v1
    import main

    def rejected():
        api_v1.enforce_uid_rate_limit("audit-synthetic-owner", "create", 1)

    # Process-local synthetic entry point through the actual main middleware and
    # exception registration; no auth/DB/worker path is represented by this route.
    route = "/__audit__/uid-rate-limit"
    main.app.add_api_route(route, rejected, methods=["GET"])
    control = FastAPI()
    control.add_api_route(route, rejected, methods=["GET"])
    with patch.object(api_v1.api_uid_limiter, "check", side_effect=api_v1.ApiUidRateLimitExceeded):
        try:
            rejected()
        except HTTPException as exc:
            raised = {"status": exc.status_code, "headers": exc.headers}
        app_client, control_client = TestClient(main.app), TestClient(control)
        try:
            response = app_client.get(route)
            stock = control_client.get(route)
        finally:
            app_client.close()
            control_client.close()
    return {"id": "P-01", "raised": raised,
            "main": {"status": response.status_code, "retry_after": response.headers.get("retry-after"), "body": response.json()},
            "stock_fastapi_control": {"status": stock.status_code, "retry_after": stock.headers.get("retry-after")}}


def memory_probe():
    from app.services import memory_edit, user_memory
    support = runpy.run_path(str(ROOT / "tests/test_memory_edit.py"))

    def roundtrip(limit):
        db = support["Database"]()
        repository = memory_edit.FirestoreMemoryEditRepository(db)
        uid, now = "audit-synthetic-owner", support["NOW"]
        before = {**user_memory.empty_profile(), "role": "Role A", "notes": "x" * 12050, "revision": 4}
        repository._profile_ref(uid).set(before)
        request_id, fingerprint = "audit-pro-edit-0001", "a" * 64
        repository.reserve(uid, client_request_id=request_id, fingerprint=fingerprint,
                           tier="pro", config=support["config"](), now=now)
        result = repository.apply_patch(uid, client_request_id=request_id, fingerprint=fingerprint,
            patch={"operation": "replace", "target": "Role A", "replacement": "Role B"},
            memory_limit=50000, now=now + timedelta(seconds=1))
        undone = repository.undo(uid, result["revision_id"], memory_limit=limit,
                                 now=now + timedelta(seconds=2))
        after = repository._profile_ref(uid).get().to_dict()
        return {"limit": limit, "before_notes_chars": len(before["notes"]),
                "after_notes_chars": len(after["notes"]), "notes_equal": after["notes"] == before["notes"],
                "role": after["role"], "revision": after["revision"], "status": undone["status"]}

    # The real persistence guard executes against the empty synthetic database;
    # unlike the regular repository fixture, it is not patched away.
    return {"id": "P-02", "unchanged_limit_control": roundtrip(50000), "reduced_limit": roundtrip(12000)}


def rollback_probe():
    from app.api.routers import admin

    def attempt(interleave):
        state = {"document": {"writer": "initial"}, "writes": []}

        def write(value):
            state["document"] = deepcopy(value)
            state["writes"].append(deepcopy(value))

        def activate(*, strict):
            if strict is not True:
                raise AssertionError("Activation must use the reviewed strict path")
            if interleave:
                # Models a second process committing after A's write. It does
                # not claim to execute threads, a Firestore transaction or B's
                # runtime activation. The process-local lock cannot fence B.
                write({"writer": "B"})
            raise RuntimeError("synthetic activation failure")

        doc = SimpleNamespace(get=lambda: SimpleNamespace(exists=True, to_dict=lambda: deepcopy(state["document"])),
                              set=write)
        with patch.object(admin, "load_models_from_db", side_effect=activate):
            try:
                admin._persist_and_activate_models(doc, {"writer": "A"})
            except RuntimeError:
                pass
        return state

    return {"id": "P-03", "single_writer_control": attempt(False), "interleaved_external_write": attempt(True)}


def topic_auth_probe():
    from fastapi import HTTPException
    from app.api.routers import admin, topics
    from app.core import security
    request = SimpleNamespace(headers={"Authorization": "Bearer audit-synthetic-token"}, cookies={})

    def one(module, *, revoked, role_outage):
        flags = []

        def verify(_token, **kwargs):
            flags.append(bool(kwargs.get("check_revoked", False)))
            if revoked and kwargs.get("check_revoked"):
                raise ValueError("synthetic revoked token")
            return {"uid": "audit-synthetic-admin", "email_verified": True}

        role = {"side_effect": security.TierStatusUnavailable("synthetic outage")} if role_outage else {"return_value": True}
        with patch.object(security.auth, "verify_id_token", side_effect=verify), \
             patch.object(security, "_is_account_tombstoned", return_value=False), \
             patch.object(module, "is_user_admin", **role):
            try:
                module._require_admin(request, {})
                outcome = "accepted"
            except HTTPException as exc:
                outcome = f"HTTP {exc.status_code}"
            except security.TierStatusUnavailable:
                outcome = "unmapped TierStatusUnavailable"
        return {"sdk_check_revoked": flags, "outcome": outcome}

    return {"id": "P-04", "revoked_token": {m.__name__.rsplit(".", 1)[-1]: one(m, revoked=True, role_outage=False) for m in (admin, topics)},
            "role_outage": {m.__name__.rsplit(".", 1)[-1]: one(m, revoked=False, role_outage=True) for m in (admin, topics)}}


def benchmark_probe():
    from benchmark import transport, runner

    def attempt(status):
        raw = {"error": {"code": 429, "message": "synthetic provider rejection"}}
        response = SimpleNamespace(status_code=status, json=lambda: raw, close=lambda: None)
        outcome = transport.execute({"provider": "openai", "api_model": "audit/model", "payload": {}},
                                    "audit-not-a-key", http_post=lambda *args, **kwargs: response)
        record = runner.BenchmarkRunner._make_cell_record(
            SimpleNamespace(label_mode="audit", system_prompt="synthetic"),
            run_id="audit", qrecord={"question_id": 1, "category": "audit", "answer": "A", "options": ["one", "two"]},
            role="model", provider="openai", internal_model="audit", api_model="audit/model",
            user_prompt="synthetic", payload={}, outcome=outcome, est_cost=0)
        indexed = next(iter(runner.index_existing([record]).values()))
        return {"http_status": status, "error": outcome["error"], "error_code": outcome["error_code"],
                "usage": outcome["usage"], "abstain": record["abstain"],
                "resume_indexes_as_success": indexed["success"] is not None, "indexed_errors": len(indexed["errors"])}

    return {"id": "P-05", "http_429_control": attempt(429), "http_200_error_body": attempt(200)}


def main():
    if os.environ.get("UNIT_TEST_MODE") != "1":
        raise RuntimeError("Explicit UNIT_TEST_MODE=1 required")
    if os.environ.get("MOCK_AUTH") == "1" or os.environ.get("RUN_E2E") == "1":
        raise RuntimeError("Do not combine the probe with E2E/auth bypass flags")
    with ExitStack() as stack:
        stack.enter_context(patch.object(socket, "create_connection", network_forbidden))
        stack.enter_context(patch.object(socket.socket, "connect", network_forbidden))
        observations = [header_probe(), memory_probe(), rollback_probe(), topic_auth_probe(), benchmark_probe()]
    print(json.dumps({"schema_version": 1, "product_sources_changed": False,
                      "network_allowed": False, "observations": observations}, indent=2))


if __name__ == "__main__":
    main()
