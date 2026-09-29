"""R27: one budget covers every paid benchmark call, including audits and
failed attempts. Offline: transport and consensus are injected fakes."""

import json
import random
import tempfile
import unittest
from pathlib import Path

from benchmark.runner import AUDIT_JOURNAL, BenchmarkRunner, index_existing, load_existing_records, spent_from_index

QUESTIONS = [
    {"question_id": 1, "question": "Q1?", "options": ["o0", "o1", "o2", "o3"],
     "answer": "B", "answer_index": 1, "category": "math"},
    {"question_id": 2, "question": "Q2?", "options": ["p0", "p1", "p2", "p3"],
     "answer": "C", "answer_index": 2, "category": "law"},
]


class CountingTransport:
    def __init__(self, *, usage=True, fail=()):
        self.calls = []
        self.usage = usage
        self.fail = set(fail)

    def __call__(self, request_data, api_key, **kwargs):
        self.calls.append(request_data["provider"])
        if request_data["provider"] in self.fail:
            return {"text": "", "sources": [], "usage": {"prompt": 0, "completion": 0, "total": 0},
                    "raw": None, "status": 500, "latency_ms": 1.0, "error": "boom",
                    "error_code": "provider_http_error"}
        usage = {"prompt": 5000, "completion": 2000, "total": 7000} if self.usage else None
        return {"text": "Reason.\nFINAL_ANSWER: B", "sources": [], "usage": usage,
                "raw": {}, "status": 200, "latency_ms": 1.0, "error": None, "error_code": None}


class CountingConsensus:
    def __init__(self):
        self.calls = 0

    def __call__(self, question, answers, model_sources=None):
        self.calls += 1
        return "Synthesis.\nFINAL_ANSWER: B"


def pilot(runner, run_dir, transport, consensus, budget=None):
    return runner.run_pilot(QUESTIONS, run_dir=run_dir, api_keys={}, transport_execute=transport,
                            consensus_fn=consensus, budget=budget, permutation_subset=2,
                            rng=random.Random(7))


class BenchmarkBudgetTests(unittest.TestCase):
    def test_tight_budget_stops_before_the_first_uncovered_audit_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            runner = BenchmarkRunner()
            main_transport, main_consensus = CountingTransport(), CountingConsensus()
            main = runner.run(QUESTIONS, run_dir=run_dir, api_keys={},
                              transport_execute=main_transport, consensus_fn=main_consensus)
            self.assertFalse(main.stopped)
            # Budget covers the finished main run but not one more audit call.
            budget = main.spent_usd + 1e-9
            transport, consensus = CountingTransport(), CountingConsensus()
            result, audits, summary = pilot(runner, run_dir, transport, consensus, budget)
            self.assertTrue(result.stopped)
            self.assertIn("audit", result.stop_reason)
            self.assertIsNone(audits)
            self.assertIsNone(summary)
            self.assertEqual(transport.calls, [])
            self.assertEqual(consensus.calls, 0)
            self.assertLessEqual(result.spent_usd, budget)

    def test_resume_of_a_finished_pilot_does_not_pay_for_audits_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            runner = BenchmarkRunner()
            first_transport, first_consensus = CountingTransport(), CountingConsensus()
            first, audits, _ = pilot(runner, run_dir, first_transport, first_consensus)
            self.assertFalse(first.stopped)
            journal = load_existing_records(run_dir / AUDIT_JOURNAL)
            self.assertEqual(len(journal), 2 * 6 + 2 * 3 + 2)  # permutation + order + anonymized

            again_transport, again_consensus = CountingTransport(), CountingConsensus()
            second, audits_again, _ = pilot(runner, run_dir, again_transport, again_consensus,
                                            budget=first.spent_usd)
            self.assertFalse(second.stopped)
            self.assertEqual(again_transport.calls, [])
            self.assertEqual(again_consensus.calls, 0)
            self.assertEqual(len(load_existing_records(run_dir / AUDIT_JOURNAL)), len(journal))
            self.assertEqual(audits_again["option_permutation"]["checks"], audits["option_permutation"]["checks"])
            self.assertAlmostEqual(second.spent_usd, first.spent_usd, places=8)

    def test_failed_paid_attempts_count_toward_the_resumed_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            runner = BenchmarkRunner()
            runner.run(QUESTIONS[:1], run_dir=run_dir, api_keys={},
                       transport_execute=CountingTransport(usage=False, fail={"mistral"}),
                       consensus_fn=CountingConsensus())
            records = load_existing_records(run_dir / "calls.jsonl")
            failed = [r for r in records if r["error"]]
            self.assertEqual(len(failed), 1)
            # Unknown usage is charged its upper-bound estimate, never zero.
            self.assertGreater(failed[0]["est_cost_usd"], 0)
            self.assertEqual(failed[0]["cost_basis"], "estimate")
            runner.run(QUESTIONS[:1], run_dir=run_dir, api_keys={},
                       transport_execute=CountingTransport(), consensus_fn=CountingConsensus(),
                       retry_failed=True)
            index = index_existing(load_existing_records(run_dir / "calls.jsonl"))
            total = sum(float(r["est_cost_usd"]) for r in load_existing_records(run_dir / "calls.jsonl"))
            self.assertAlmostEqual(spent_from_index(index), total, places=8)

    def test_audit_costs_without_usage_are_estimated_conservatively(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            runner = BenchmarkRunner()
            result, audits, _ = pilot(runner, run_dir, CountingTransport(usage=False), CountingConsensus())
            self.assertFalse(result.stopped)
            journal = load_existing_records(run_dir / AUDIT_JOURNAL)
            self.assertTrue(all(entry["est_cost_usd"] > 0 for entry in journal))
            self.assertTrue(all(entry["cost_basis"] == "estimate" for entry in journal))
            self.assertGreater(result.estimated_cost_cells, 0)
            saved = json.loads((run_dir / "audits.json").read_text(encoding="utf-8"))
            self.assertAlmostEqual(saved["cost"]["total_spent_usd"], result.spent_usd, places=6)
            self.assertEqual(saved["cost"]["estimated_cost_calls"], result.estimated_cost_cells)


if __name__ == "__main__":
    unittest.main()
