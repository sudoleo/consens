"""Offline re-analysis of the existing pooled benchmark; no network or app startup.

Run from any directory with the repository's Python interpreter.
Writes only aggregate findings and per-question answer labels beside this script.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RUN = ROOT / "data/benchmark/runs/pooled_v1"
PROVIDERS = ("openai", "mistral", "anthropic", "gemini", "deepseek", "grok")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paired_test(questions, baseline):
    wins = sum(q["correct"]["consensus"] and not q["correct"][baseline] for q in questions)
    losses = sum(q["correct"][baseline] and not q["correct"]["consensus"] for q in questions)
    n = wins + losses
    # Exact two-sided McNemar test: conditional Binomial(n, 1/2).
    p = min(1.0, 2 * sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / 2**n) if n else 1.0
    return {"consensus_only_correct": wins, "baseline_only_correct": losses, "discordant_pairs": n, "exact_two_sided_p": p}


def main():
    records = [json.loads(line) for line in (RUN / "calls.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    manifest = read_json(RUN / "manifest.json")
    stored = read_json(RUN / "results.json")
    cells = {}
    for r in records:
        system = r["provider"] if r["role"] == "model" else r["role"]
        key = (r["question_id"], system)
        assert key not in cells, f"Duplicate cell: {key}"
        assert r["benchmark_mode"] is True
        assert bool(r["correct"]) == bool(r.get("extracted_letter") and r["extracted_letter"] == r["ground_truth"] and not r.get("error"))
        cells[key] = r

    questions = []
    systems = (*PROVIDERS, "consensus", "synth_alone")
    for qid in sorted({key[0] for key in cells}):
        rows = {system: cells[(qid, system)] for system in systems}
        assert len({r["ground_truth"] for r in rows.values()}) == 1
        votes = {system: r["extracted_letter"] for system, r in rows.items()}
        correctness = {system: bool(r["correct"]) for system, r in rows.items()}
        q = {"question_id": qid, "category": rows["openai"]["category"], "ground_truth": rows["openai"]["ground_truth"], "answers": votes, "correct": correctness}
        q["unanimous"] = len({votes[p] for p in PROVIDERS}) == 1 and bool(votes[PROVIDERS[0]])
        q["all_models_wrong"] = not any(correctness[p] for p in PROVIDERS)
        q["correct_candidate_missed"] = not correctness["consensus"] and not q["all_models_wrong"]
        questions.append(q)

    counts = {system: sum(q["correct"][system] for q in questions) for system in systems}
    for system, count in counts.items():
        stored_key = "model:" + system if system in PROVIDERS else system
        assert count == stored["systems"][stored_key]["correct"]
    n = len(questions)
    assert n == stored["n_questions"] == 314
    unanimous_wrong = [q["question_id"] for q in questions if q["unanimous"] and q["all_models_wrong"]]
    missed = [q["question_id"] for q in questions if q["correct_candidate_missed"]]

    # Load only the pure scoring module, avoiding Firebase and all runtime setup.
    spec = importlib.util.spec_from_file_location("research_scoring", ROOT / "app/services/llm/consensus_scoring.py")
    scoring = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scoring)
    synthetic = {"models_compared": list(PROVIDERS), "differences": [], "claims": [{"anchor": "Illustrative assertion, not a real user response.", "agree": list(PROVIDERS), "dissent": []}]}
    scoring_example = scoring.compute_agreement_score(synthetic)

    relevant = ["app/services/llm/consensus_scoring.py", "app/services/llm/coverage_judge.py", "app/services/llm/consensus_engine.py", "app/services/llm/resolve_engine.py", "app/services/topic_runner.py", "app/services/claim_ledger.py", "benchmark/runner.py", "templates/benchmark.html"]
    findings = {
        "scope": "Offline analysis of stored June 2026 artifacts, not a fresh model benchmark or current production quality estimate.",
        "run": manifest["run_id"], "created": manifest["created"], "label_mode": manifest["label_mode"],
        "pooled_from": manifest["pooled_from"], "records": len(records), "questions": n,
        "duplicate_cells": 0, "error_cells": sum(bool(r.get("error")) for r in records),
        "timestamp_range": [min(r["ts"] for r in records), max(r["ts"] for r in records)],
        "correct_counts": counts,
        "accuracy_percent": {s: round(100 * c / n, 4) for s, c in counts.items()},
        "disagreement_questions": sum(not q["unanimous"] for q in questions),
        "unanimous_questions": sum(q["unanimous"] for q in questions),
        "unanimous_wrong_question_ids": unanimous_wrong,
        "unanimous_wrong_percent": 100 * len(unanimous_wrong) / sum(q["unanimous"] for q in questions),
        "all_six_wrong_question_ids": [q["question_id"] for q in questions if q["all_models_wrong"]],
        "oracle_any_candidate_correct": sum(not q["all_models_wrong"] for q in questions),
        "correct_candidate_missed_question_ids": missed,
        "consensus_correct_when_all_candidates_wrong": sum(q["all_models_wrong"] and q["correct"]["consensus"] for q in questions),
        "paired_comparisons": {s: paired_test(questions, s) for s in ["synth_alone", "anthropic"]},
        "identical_consensus_and_alone_texts": sum(cells[(q["question_id"], "consensus")]["parsed_text"] == cells[(q["question_id"], "synth_alone")]["parsed_text"] for q in questions),
        "synthetic_agreement_example": {"input": synthetic, "output": scoring_example, "interpretation": "A deterministic agreement-only example; this does not measure live false-confidence frequency."},
        "cost_caveat": "Consensus est_cost_usd uses candidate output caps as estimated input tokens in benchmark.runner._consensus_estimate. Do not treat as billed usage or compare cost ratios with measured baseline usage.",
        "source_sha256": {str(p.relative_to(ROOT)).replace(chr(92), "/"): digest(p) for p in [RUN / "calls.jsonl", RUN / "results.json", RUN / "manifest.json", *[ROOT / x for x in relevant]]},
    }
    (OUT / "benchmark-findings.json").write_text(json.dumps(findings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "benchmark-question-results.json").write_text(json.dumps(questions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"questions": n, "records": len(records), "correct_counts": counts, "unanimous_wrong": len(unanimous_wrong), "missed_correct_candidates": len(missed), "paired_comparisons": findings["paired_comparisons"], "synthetic_agreement_score": scoring_example["score"]}, indent=2))


if __name__ == "__main__":
    main()
