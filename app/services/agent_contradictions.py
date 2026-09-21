"""Agent tool for the shared, source-backed contradiction judge.

Plans and outcomes belong to the exact comparison/answer snapshot. Paid judge
attempts use Agent receipts and quota; retrieval keeps the shared document rules.
"""
from dataclasses import replace
import json

from app.services.agent_tools import ReadOnlyTool
from app.services.llm.agent_client import metered_model
from app.services.llm.provider_runtime import current_analysis_budget
from app.services.source_verification import (
    Limits, SourceCheckError, _parse_judge_output, execute_source_package,
    judge_sources, merge_source_verification, plan_source_verification,
)


PROMPT = """Check contradictions is ON for this message. After judge_answer,
call check_contradictions to examine factual disagreements using existing original
sources. This separate tool does not change the synthesis or model agreement.
The source check finishes the run with the exact fixed answer. It never allows
a revision or a second review round, including when finalize=false is supplied.
No eligible disagreements means a skipped source check, not a verified answer.
Do not claim missing, failed or inconclusive evidence proves either position.
"""


def source_check_is_bound(check, comparison, digest):
    value = check.get("source_verification") or {}
    return (value.get("answer_version") == digest
            and value.get("run_id") == comparison["id"]
            and value.get("basis_hash") == comparison.get("basis_hash")
            and value.get("check_type") == "contradiction_evidence"
            and value.get("status") in {"complete", "partial", "skipped", "failed"})


class ContradictionChecks:
    def __init__(self, comparison, arguments, limits=None):
        self.comparison = comparison
        self.limits = limits or Limits.configured()
        self.tool = ReadOnlyTool("check_contradictions",
            "Check factual contradictions found by judge_answer against existing original sources. Never rewrites the answer.",
            arguments, self.check)

    def complete(self):
        owner = self.comparison
        return bool(owner.review) and all(source_check_is_bound(check, comparison, owner.snapshot()["answer_hash"])
            for comparison, check in zip(owner.comparisons, owner.review["checks"])) and len(owner.review["checks"]) == len(owner.comparisons)

    def transport(self, payload, keys, limits):
        from app.services.contradiction_verification import SYSTEM
        model = metered_model(limits.model, max_tokens=limits.output_tokens)
        config = {"response_format": {"type": "json_object"}}
        if model.model == "openai/gpt-5-mini":
            config["reasoning"] = {"effort": "minimal"}
        value = self.comparison.call(replace(model, request_config=config), [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            title="Contradiction source judge", kind="judge", budget=current_analysis_budget())
        if len(value.text) > limits.output_chars:
            raise SourceCheckError("output_limit")
        usage = value.usage or {}
        return _parse_judge_output(value.text), {**usage,
            "prompt_tokens": usage.get("input_tokens", 0), "completion_tokens": usage.get("output_tokens", 0)}

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
            if not isinstance(check.get("differences_data"), dict):
                check["source_verification"] = {**unavailable_snapshot(owner.text, "differences_failed",
                    check_type="contradiction_evidence"), "run_id": comparison["id"], "basis_hash": comparison.get("basis_hash")}
                owner.checkpoint()
                continue
            sources = [*loop.completion.sources]
            for event in loop.completion.activity:
                sources.extend(event.get("sources") or [])
            plan = plan_source_verification(question=comparison["question"], consensus=owner.text,
                sources=sources, differences_data=check["differences_data"],
                model_answers={a["provider_label"]: a["text"] for a in comparison["answers"]},
                model_sources={a["provider_label"]: a["sources"] for a in comparison["answers"]},
                run_id=comparison["id"], limits=self.limits)
            snapshot = plan["snapshot"]
            snapshot["basis_hash"] = comparison.get("basis_hash")
            check["source_verification"] = snapshot
            owner.checkpoint()
            for package in plan["packages"]:
                loop._check(cancellation)
                partial = execute_source_package(package=package, question=comparison["question"],
                    answer_version=plan["answer_version"], keys={"OpenRouter": loop.api_key}, limits=self.limits,
                    judge=lambda payload, keys, limits: judge_sources(payload, keys, limits, transport=self.transport))
                loop._check(cancellation)
                snapshot = merge_source_verification(snapshot, partial)
                check["source_verification"] = snapshot
                owner.checkpoint()
        owner.versions[-1]["checks"] = owner.review["checks"]
        owner.finalized = self.complete()
        owner.checkpoint()
        # Full originals are persisted for the UI, not copied back into context.
        return {"finalized": owner.finalized, "checks": [
            {"comparison_id": c["comparison_id"], "status": c["source_verification"]["status"],
             "reason_code": c["source_verification"].get("reason_code"),
             "findings": [{k: f.get(k) for k in ("contradiction_id", "checked", "verdict", "supported_position_id", "reason", "reason_code")}
                          for f in c["source_verification"].get("findings", [])]}
            for c in owner.review["checks"]]}
