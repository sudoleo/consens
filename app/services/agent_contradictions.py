"""Agent tool for the shared, source-backed contradiction judge.

The tool only plans and enqueues: each comparison's check becomes a durable
job in `source_check_jobs` (the queue Consensus uses), bound to the exact
comparison/answer snapshot. The turn finalizes with the job references; the
browser follows each job until it settles. Paid judge attempts stay on the
owner's token account: the job reserves its bound at admission and settles
its measured tokens with each result.
"""

from app.services.agent_tools import ReadOnlyTool
from app.services.source_verification import Limits


# A queued or running job is a valid end of the turn: its reference is bound
# and the worker settles it. Terminal snapshots come from skipped plans,
# admission failures and jobs that already finished (idempotent re-submits).
PENDING = {"queued", "running"}
TERMINAL = {"complete", "partial", "skipped", "failed"}


def source_check_is_bound(check, comparison, digest):
    value = check.get("source_verification") or {}
    status = value.get("status")
    return (value.get("answer_version") == digest
            and value.get("run_id") == comparison["id"]
            and value.get("basis_hash") == comparison.get("basis_hash")
            and value.get("check_type") == "contradiction_evidence"
            and (status in TERMINAL or (status in PENDING and bool(value.get("job_id")))))


class ContradictionChecks:
    def __init__(self, comparison, arguments, limits=None):
        self.comparison = comparison
        self.limits = limits or Limits.configured()
        self.tool = ReadOnlyTool("check_contradictions",
            "Queue a check of the factual contradictions found by judge_answer against existing original sources. "
            "Runs after the answer; never rewrites it.",
            arguments, self.check)

    def complete(self):
        owner = self.comparison
        return bool(owner.review) and all(source_check_is_bound(check, comparison, owner.snapshot()["answer_hash"])
            for comparison, check in zip(owner.comparisons, owner.review["checks"])) and len(owner.review["checks"]) == len(owner.comparisons)

    def metering(self):
        """The Agent account the background job charges, as Agent steps do."""
        from app.services import agent_budget_config, agent_quota
        loop = self.comparison.loop
        config = agent_budget_config.get_config(loop.store.db)
        return {"account": "agent", "quota_day": agent_quota.period_key(config),
                "limit": agent_budget_config.limit_for(config, agent_quota.account_tier(loop.uid))}

    def submit(self, comparison, check):
        from app.services.source_check_jobs import submit_advisory
        owner, loop = self.comparison, self.comparison.loop
        sources = [*loop.completion.sources]
        for event in loop.completion.activity:
            sources.extend(event.get("sources") or [])
        # The job's run is the comparison; its parent is the chat, so deleting
        # the chat also stops and deletes its pending checks.
        return submit_advisory(question=comparison["question"], consensus=owner.text, sources=sources,
            keys={"OpenRouter": loop.api_key}, differences_data=check["differences_data"],
            model_answers={a["provider_label"]: a["text"] for a in comparison["answers"]},
            model_sources={a["provider_label"]: a["sources"] for a in comparison["answers"]},
            limits=self.limits, binding={"basis_hash": comparison.get("basis_hash")}, metering=self.metering(),
            context={"uid": loop.uid, "run_key": comparison["id"], "own_keys": False, "origin": "interactive",
                     "references": [f"users/{loop.uid}/chats/{loop.chat_id}"]})

    def check(self, args, *, cancellation):
        from app.services.agent_comparison import review_is_bound
        from app.services.source_check_jobs import unavailable_snapshot
        owner, loop = self.comparison, self.comparison.loop
        loop._check(cancellation)
        if not owner.review or not review_is_bound(owner.snapshot(), owner.text, check_sources=False):
            raise ValueError("First stream the synthesis and call judge_answer for this exact answer and comparison basis.")
        for comparison, check in zip(owner.comparisons, owner.review["checks"]):
            if source_check_is_bound(check, comparison, owner.snapshot()["answer_hash"]):
                continue
            binding = {"run_id": comparison["id"], "basis_hash": comparison.get("basis_hash")}
            if not isinstance(check.get("differences_data"), dict):
                check["source_verification"] = {**unavailable_snapshot(owner.text, "differences_failed",
                    check_type="contradiction_evidence"), **binding}
            else:
                loop._check(cancellation)
                check["source_verification"] = {**self.submit(comparison, check), **binding}
            owner.checkpoint()
        owner.versions[-1]["checks"] = owner.review["checks"]
        owner.finalized = self.complete()
        owner.checkpoint()
        return {"finalized": owner.finalized, "checks": [
            {"comparison_id": c["comparison_id"], "status": c["source_verification"]["status"],
             "reason_code": c["source_verification"].get("reason_code")}
            for c in owner.review["checks"]],
            "note": "Queued checks finish after this run. Their verdicts are not available to you."}
