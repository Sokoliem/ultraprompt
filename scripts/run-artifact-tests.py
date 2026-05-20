#!/usr/bin/env python3
"""Focused regression tests for artifact contract validation."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_validator():
    path = ROOT / "scripts" / "artifact-validate.py"
    spec = importlib.util.spec_from_file_location("artifact_validate", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_fixture(name: str) -> dict:
    return json.loads((ROOT / "tests" / "artifacts" / name).read_text(encoding="utf-8"))


def base_gap() -> dict:
    return {
        "repo": "example",
        "category": "missing_test",
        "severity": "medium",
        "confidence": "likely",
        "title": "Missing regression coverage",
        "evidence": {"files": ["src/example.ts"], "commands": [], "symbols": []},
    }


def main() -> int:
    validator = load_validator()
    cases = []

    ok_gap = validator.validate("gap_ledger_entry", base_gap())
    cases.append(("valid_gap", ok_gap.get("ok") is True))
    status_gap = base_gap()
    status_gap["status"] = "validated"
    cases.append(("valid_gap_status", validator.validate("gap_ledger_entry", status_gap).get("ok") is True))

    for field, value in (
        ("severity", "major"),
        ("confidence", "certain"),
        ("category", "misc"),
    ):
        gap = base_gap()
        gap[field] = value
        result = validator.validate("gap_ledger_entry", gap)
        cases.append((f"invalid_gap_{field}", result.get("ok") is False))

    readiness = {
        "status": "ship-it",
        "status_reasoning": "invalid enum should fail",
        "blockers": [],
        "warnings": [],
        "missing_operational_controls": [],
        "required_validation": [],
        "recommended_release_sequence": [],
    }
    cases.append(("invalid_release_status", validator.validate("release_readiness_report", readiness).get("ok") is False))

    repo_completeness = {
        "repo": "example",
        "panel_run": {"run_id": "panel_1", "status": "completed"},
        "repo_review_report": {"executive_summary": "ok"},
        "gap_ledger_entries": [base_gap()],
        "dedupe_summary": {"merged": 0},
        "validation_summary": [{"command": "python3 scripts/run-artifact-tests.py", "ok": True}],
        "next_actions": ["ship"],
    }
    cases.append(("valid_repo_completeness_report", validator.validate("repo_completeness_report", repo_completeness).get("ok") is True))

    drift = {
        "contract_gaps": [{
            "contract": "api",
            "producer_side": "producer",
            "consumer_side": "consumer",
            "mismatch": "shape",
            "evidence": "test",
            "severity": "severe",
            "recommended_fix": "align schema",
        }]
    }
    cases.append(("invalid_contract_gap_severity", validator.validate("contract_drift_report", drift).get("ok") is False))

    memory = {
        "schema": "memory.v1",
        "id": "mem_1",
        "kind": "repo_fact",
        "scope": "repo",
        "status": "active",
        "privacy": "metadata",
        "text": "Repo uses Powershell commands.",
        "confidence": 0.8,
        "importance": 0.7,
        "evidence": [{"kind": "file", "ref": "README.md"}],
    }
    cases.append(("valid_memory_record", validator.validate("memory_record", memory).get("ok") is True))
    bad_memory = dict(memory)
    bad_memory["scope"] = "everywhere"
    cases.append(("invalid_memory_scope", validator.validate("memory_record", bad_memory).get("ok") is False))

    dream = {"schema": "dream_report.v1", "id": "dream_1", "job": "session-compaction", "created_at": "2026-05-11T00:00:00Z", "summary": "ok"}
    cases.append(("valid_dream_report", validator.validate("dream_report", dream).get("ok") is True))

    learning = {"schema": "learning_candidate.v1", "id": "learn_1", "kind": "route_update", "status": "pending", "title": "Route update", "risk": "low", "payload": {}}
    cases.append(("valid_learning_candidate", validator.validate("learning_candidate", learning).get("ok") is True))
    bad_learning = dict(learning)
    bad_learning["status"] = "secretly_applied"
    cases.append(("invalid_learning_status", validator.validate("learning_candidate", bad_learning).get("ok") is False))

    graph = {
        "schema": "capability_graph.v1",
        "plugin_version": "8.2.0",
        "nodes": [{"id": "skill:build", "kind": "skill"}],
        "edges": [{"source": "skill:build", "target": "agent:reviewer", "relation": "dispatches_to"}],
        "health": {"ok": True},
        "source_hash": "abc",
    }
    cases.append(("valid_capability_graph", validator.validate("capability_graph", graph).get("ok") is True))

    v82_fixture_types = {
        "design_review": "design_review.valid.json",
        "visual_qa_report": "visual_qa_report.valid.json",
        "design_system_review": "design_system_review.valid.json",
        "experience_quality_report": "experience_quality_report.valid.json",
        "invocation_telemetry_audit": "invocation_telemetry_audit.valid.json",
        "goal_contract": "goal_contract.valid.json",
        "routing_decision": "routing_decision.valid.json",
        "routing_envelope": "routing_envelope.valid.json",
        "route_outcome": "route_outcome.valid.json",
        "self_improvement_run": "self_improvement_run.valid.json",
        "self_improvement_patch": "self_improvement_patch.valid.json",
        "learner_eval_report": "learner_eval_report.valid.json",
        "rollback_manifest": "rollback_manifest.valid.json",
    }
    for artifact_type, fixture_name in v82_fixture_types.items():
        fixture = load_fixture(fixture_name)
        cases.append((f"valid_{artifact_type}", validator.validate(artifact_type, fixture).get("ok") is True))
        schema = validator.SCHEMAS[artifact_type]
        first_required = schema["required"][0]
        invalid = dict(fixture)
        invalid.pop(first_required, None)
        cases.append((f"invalid_{artifact_type}_missing_{first_required}", validator.validate(artifact_type, invalid).get("ok") is False))

    weak_visual = load_fixture("visual_qa_report.valid.json")
    weak_visual["screenshot_evidence"] = []
    weak_visual["remaining_visual_risks"] = []
    cases.append(("invalid_visual_qa_missing_evidence_and_risks", validator.validate("visual_qa_report", weak_visual).get("ok") is False))

    failures = [name for name, ok in cases if not ok]
    result = {"ok": not failures, "checked": [name for name, _ in cases], "failures": failures}
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
