"""Wall-clock progress is not prompt configuration drift."""
import json

import pytest

from app.services.llm import consensus_engine
from benchmark.runner import BenchmarkRunner


def context(date="Friday, 2026-10-02", time="12:34:56", zone="Europe/Berlin", offset="+02:00"):
    return (f"Current date: {date}. Reference time at request start: {time}. "
            f"Reference timezone: {zone} (UTC{offset}). Rest of the clock instructions.")


def test_resume_across_seconds_days_and_dst_keeps_manifest(tmp_path, monkeypatch):
    runner = BenchmarkRunner()
    monkeypatch.setattr(consensus_engine, "get_date_context", lambda *a: context())
    runner.write_or_validate_manifest(tmp_path)
    original = (tmp_path / "manifest.json").read_bytes()
    monkeypatch.setattr(consensus_engine, "get_date_context", lambda *a: context("Sunday, 2026-10-25", "02:00:01", offset="+01:00"))
    runner.write_or_validate_manifest(tmp_path)
    assert (tmp_path / "manifest.json").read_bytes() == original


@pytest.mark.parametrize("change", ["timezone", "instructions", "model"])
def test_actual_configuration_drift_still_rejects_resume(tmp_path, monkeypatch, change):
    runner = BenchmarkRunner()
    monkeypatch.setattr(consensus_engine, "get_date_context", lambda *a: context())
    runner.write_or_validate_manifest(tmp_path)
    if change == "timezone":
        monkeypatch.setattr(consensus_engine, "get_date_context", lambda *a: context(zone="UTC"))
    elif change == "instructions":
        monkeypatch.setattr(consensus_engine, "get_date_context", lambda *a: context() + "different policy")
    else:
        runner.output_tokens += 1
    with pytest.raises(RuntimeError, match="drifted"):
        runner.write_or_validate_manifest(tmp_path)


def test_timestamped_legacy_manifest_resumes_without_rewriting_it(tmp_path, monkeypatch):
    runner = BenchmarkRunner()
    monkeypatch.setattr(consensus_engine, "get_date_context", lambda *a: context())
    manifest = runner.build_manifest("legacy")
    template = manifest["consensus_prompt_template"]
    # Keep the exact pre-fix file representation, including its old clock.
    manifest["consensus_prompt_template"] = context() + "\n\n" + template.split("\n\n", 1)[1]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    before = path.read_bytes()
    monkeypatch.setattr(consensus_engine, "get_date_context", lambda *a: context(time="13:00:00"))
    runner.write_or_validate_manifest(tmp_path)
    assert path.read_bytes() == before
