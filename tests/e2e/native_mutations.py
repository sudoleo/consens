"""Isolated negative controls for the native audit contracts.

Run as a script with the safe demo emulator environment. Each mutation exists
only in its pytest child process; source files and running applications are never
changed. The harness requires an assertion failure, not import/setup failure.
"""
import __future__
import importlib
import inspect
import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap
import threading


CASES = {
    "WP-01": ("app.services.watch_service", "create_watch", [
        ("if not bypass_active_limit and active_count >= cfg.get_watch_active_limit(tier):", "if False:")],
        "test_phase2_transactions.py::test_two_workers_cannot_exceed_owner_watch_limit"),
    "WP-02": ("app.services.share_snapshots", "report_share", [
        ("count = old_count + 1 if isinstance(old_count, int) and old_count >= 0 else 1", "count = 1")],
        "test_phase2_transactions.py::test_parallel_reports_never_lose_increments_or_change_indexing"),
    "WP-07": ("app.services.usage_repository", "FirestoreUsageRepository.book_operation", [
        ("if operation in booked:", "if False:")],
        "test_usage_transactions.py::test_native_identical_key_and_booking_are_exactly_once"),
    "WP-07-atomicity": ("app.services.usage_repository", "FirestoreUsageRepository._transaction", [
        ("return run(transaction)", "return _audit_unprotected_operation(self, uid, operation)")],
        "test_usage_transactions.py::test_native_last_allowance_release_and_utc_period"),
    "WP-07-atomicity-charge": ("app.services.usage_repository", "FirestoreUsageRepository._transaction", [
        ("return run(transaction)", "return _audit_unprotected_operation(self, uid, operation)")],
        "test_usage_transactions.py::test_native_distinct_bookings_preserve_both_charges"),
    "WP-08": ("app.services.chat_store", "ChatStore.complete_turn", [
        ('if (chat_snapshot.to_dict() or {}).get("status") != CHAT_STATUS_ACTIVE:', 'if False:')],
        "test_chat_lifecycle_transactions.py::test_native_deleting_tombstone_fences_writes_before_physical_purge"),
    "WP-08-terminal": ("app.services.chat_store", "ChatStore.complete_turn", [
        ("if status != TURN_STATUS_PENDING:", "if False:")],
        "test_chat_lifecycle_transactions.py::test_native_terminal_failure_rejects_completion_and_remains_failed"),
    "WP-09": ("app.services.account_deletion", "FirestoreAccountDeletion.cleanup_uid", [
        ('("answer_receipts", lambda: self._delete_query("answer_receipts", "owner_uid", uid))', '("answer_receipts", lambda: None)')],
        "test_account_deletion_transactions.py::test_native_account_repeats_success_after_lost_checkpoint"),
    "WP-10": ("app.services.memory_edit", "_lossless_profile", [
        ('if isinstance(notes, str) and len(notes) > max(0, int(memory_limit)):', 'if False:')],
        "test_memory_edit_transactions.py::test_native_undo_is_lossless_owner_bound_idempotent_and_revision_checked"),
    "WP-14": ("app.services.source_check_repository", "SourceCheckRepository.finish_package", [
        ("or job.get('lease_token') != claimed['lease_token']", "or False")],
        "test_source_check_transactions.py::test_native_source_claim_takeover_and_exactly_once_package"),
    "WP-19": ("app.services.seo_weekly_review", "WeeklyReviewRepository.finish_lease", [
        ('if (data or {}).get("lease_run_id") != run_id:', 'if False:')],
        "test_scheduler_transactions.py::test_native_seo_claim_and_finish_require_current_owner"),
    "WP-33": ("app.api.routers.admin", "_persist_and_activate_models", [
        ('if cfg.model_config_revision_of(current) != new_revision:', 'if False:')],
        "test_model_configuration_transactions.py::test_native_failed_model_activation_preserves_other_writer"),
    "WP-35": ("app.services.agent_actions", "AgentActions.confirm", [
        ('if data.get("status") in {"succeeded", "executing", "unknown"}:', 'if False:'),
        ('if data.get("status") != "pending" or data["approval_until"] <= now().isoformat():', 'if data["approval_until"] <= now().isoformat():')],
        "test_google_action_transactions.py::test_native_google_confirmation_one_attempt_and_unknown_never_retries"),
    "WP-36": ("app.services.agent_files", "AgentFiles.save", [
        ('if usage.get("count", 0) >= MAX_FILES or usage.get("bytes", 0) + len(raw) > MAX_STORAGE_BYTES:', 'if False:')],
        "test_file_storage_transactions.py::test_native_cloud_upload_quota_foreign_download_and_delete_retry"),
    "WP-37": ("app.services.notification_outbox", "finish", [
        ('or str(data.get("lease_owner") or "") != str(lease_owner)', 'or False')],
        "test_watch_delivery_transactions.py::test_native_outbox_claim_takeover_rejects_stale_ack_and_terminal_replay"),
    "WP-37-probe": ("app.services.watch_probe", "record_probe", [
        ('if any(data.get(field) != expected_claim.get(field) for field in fields):', 'if False:')],
        "test_watch_delivery_transactions.py::test_native_probe_budget_is_atomic_and_old_configuration_cannot_schedule"),
}


def _install_unprotected_native_reads():
    """The deliberate mutant still uses actual SDK calls and every quota guard.

    Both unprotected workers first read the same ledger before either writes.
    This synchronization exists only in the mutant, never inside a production
    SDK transaction callback. It makes the lost-update schedule deterministic.
    """
    from google.cloud.firestore_v1.document import DocumentReference
    original_get = DocumentReference.get
    both_ledgers_read = threading.Barrier(2)

    class ImmediateWrites:
        def set(self, ref, data, **kwargs):
            return ref.set(data, **kwargs)

        def update(self, ref, data, **kwargs):
            return ref.update(data, **kwargs)

    def unprotected_get(self, *args, **kwargs):
        if isinstance(kwargs.get("transaction"), ImmediateWrites):
            kwargs.pop("transaction")
            snapshot = original_get(self, *args, **kwargs)
            if self.id.startswith("agent_tokens_") and threading.current_thread().name.startswith("ThreadPoolExecutor"):
                both_ledgers_read.wait(timeout=15)
            return snapshot
        return original_get(self, *args, **kwargs)

    DocumentReference.get = unprotected_get
    return lambda repository, uid, operation: operation(ImmediateWrites())


def pytest_sessionstart(session):
    name = os.environ.get("AUDIT_NATIVE_MUTATION")
    if not name:
        return
    module_name, path, replacements, _ = CASES[name]
    target = importlib.import_module(module_name)
    for part in path.split(".")[:-1]:
        target = getattr(target, part)
    attribute = path.split(".")[-1]
    original = getattr(target, attribute)
    source = textwrap.dedent(inspect.getsource(original))
    for old, new in replacements:
        assert old in source, f"Mutation target drift: {name} {old}"
        source = source.replace(old, new, 1)
    namespace = dict(original.__globals__)
    if name.startswith("WP-07-atomicity"):
        namespace["_audit_unprotected_operation"] = _install_unprotected_native_reads()
    exec(compile(source, f"<negative-control-{name}>", "exec", flags=__future__.annotations.compiler_flag), namespace)
    setattr(target, attribute, namespace[attribute])


def main():
    root = Path(__file__).resolve().parents[2]
    folder = root / "test-results" / "native-mutations"
    folder.mkdir(parents=True, exist_ok=True)
    for name in sys.argv[1:] or CASES:
        environment = {**os.environ, "AUDIT_NATIVE_MUTATION": name,
            "PYTHONPATH": os.pathsep.join([str(root / "tests/e2e"), str(root / "tests"), str(root)])}
        case = "tests/e2e/" + CASES[name][3]
        result = subprocess.run([sys.executable, "-m", "pytest", "-p", "native_mutations", case, "-q", "--tb=short"],
            cwd=root, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", timeout=180)
        (folder / (name + ".txt")).write_text(result.stdout, encoding="utf-8")
        killed = result.returncode == 1 and re.search(r"[1-9][0-9]* failed", result.stdout) and (
            re.search(r"\nE\s+assert\b", result.stdout) or "AssertionError" in result.stdout or "DID NOT RAISE" in result.stdout)
        print(f"{name}: {'rejected by contract assertion' if killed else 'NEGATIVE CONTROL FAILED'}", flush=True)
        if not killed:
            print(result.stdout)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
