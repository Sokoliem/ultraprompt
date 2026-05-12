#!/usr/bin/env python3
"""V8: Artifact contracts validator (PRD §28).

Validates structured artifacts (PRD, gap_ledger entries, repo_review_report,
release_readiness, contract_drift_report, opportunity_map, mvp_scope, etc.)
against required-section schemas. Catches the "fluffy artifact" failure mode.

Usage:
  artifact-validate.py validate <artifact_type> <yaml_or_json_file>
  artifact-validate.py schemas               # list known schemas
  artifact-validate.py schema <type>         # show schema for one type
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


# Artifact schemas: required sections per artifact type
SCHEMAS = {
    "prd_lite": {
        "required": [
            "problem", "users_and_jobs", "goals", "non_goals", "requirements",
            "success_criteria", "risks", "open_questions"
        ],
        "min_lengths": {"problem": 50, "non_goals": 1},
    },
    "prd_standard": {
        "required": [
            "problem", "users_and_jobs", "goals", "non_goals", "requirements",
            "scope", "technical_considerations", "risks", "metrics",
            "acceptance_criteria", "rollout_plan", "validation_plan", "open_questions"
        ],
        "min_lengths": {"problem": 100, "non_goals": 3, "acceptance_criteria": 1},
    },
    "prd_technical": {
        "required": [
            "problem", "users_and_jobs", "goals", "non_goals", "requirements",
            "scope", "technical_design", "risks", "metrics",
            "acceptance_criteria", "rollout_plan", "validation_plan", "open_questions"
        ],
        "required_in_technical_design": [
            "data_model", "api_surface", "integration_points",
            "failure_modes", "telemetry", "rollout_technical_plan"
        ],
    },
    "prd_ai_feature": {
        "required": [
            "problem", "users_and_jobs", "goals", "non_goals", "requirements",
            "scope", "technical_design", "ai_specific", "risks", "metrics",
            "acceptance_criteria", "rollout_plan", "validation_plan", "open_questions"
        ],
        "required_in_ai_specific": [
            "model_selection", "eval_methodology", "guardrails",
            "human_in_loop", "cost_model", "latency_targets",
            "prompt_versioning", "data_privacy_posture"
        ],
    },
    "gap_ledger_entry": {
        "required": ["repo", "category", "severity", "confidence", "title", "evidence"],
        "valid_severities": ["critical", "high", "medium", "low"],
        "valid_confidences": ["confirmed", "likely", "possible"],
        "valid_status": ["open", "accepted", "in_progress", "fixed", "validated", "false_positive", "deferred"],
        "valid_categories": [
            "incomplete_feature", "wiring_gap", "contract_mismatch", "missing_test",
            "release_blocker", "stale_code", "documentation_drift", "dead_code",
            "observability_gap", "configuration_gap"
        ],
    },
    "repo_completeness_report": {
        "required": [
            "repo", "panel_run", "repo_review_report", "gap_ledger_entries",
            "dedupe_summary", "validation_summary", "next_actions"
        ],
    },
    "repo_review_report": {
        "required": [
            "executive_summary", "repo_map_summary", "confirmed_gaps",
            "probable_gaps", "release_readiness", "top_risks",
            "quick_wins", "recommended_sequence", "validation_plan"
        ],
    },
    "release_readiness_report": {
        "required": [
            "status", "status_reasoning", "blockers", "warnings",
            "missing_operational_controls", "required_validation",
            "recommended_release_sequence"
        ],
        "valid_status": ["ready", "risky", "blocked"],
    },
    "contract_drift_report": {
        "required": ["contract_gaps"],
        "required_in_each_gap": [
            "contract", "producer_side", "consumer_side", "mismatch",
            "evidence", "severity", "recommended_fix"
        ],
    },
    "opportunity_map": {
        "required": [
            "market_axes", "occupied_zones", "underserved_zones",
            "recommended_focus", "validation_plan"
        ],
        "min_underserved_zones": 1,
    },
    "idea_triage": {
        "required": [
            "ideas_evaluated", "triage_criteria", "ranked_ideas",
            "must_kill", "must_pursue"
        ],
    },
    "concept_brief": {
        "required": [
            "problem", "target_users", "proposed_approach", "key_differentiator",
            "success_criteria_sketch", "top_risks", "validation_plan", "decision_required"
        ],
    },
    "mvp_scope": {
        "required": [
            "hypothesis", "must_have", "should_have", "won_t_have_this_mvp",
            "validation_plan", "success_criteria", "failure_criteria", "post_mvp_roadmap"
        ],
    },
    "problem_framing": {
        "required": [
            "original_problem", "reframings", "recommended_framing",
            "key_assumptions", "open_questions"
        ],
        "min_reframings": 3,
    },
    "memory_record": {
        "required": [
            "schema", "id", "kind", "scope", "status", "privacy",
            "text", "confidence", "importance", "evidence"
        ],
        "valid_schema": ["memory.v1"],
        "valid_kinds": [
            "episodic", "repo_fact", "repo_pattern", "procedure", "route_outcome",
            "user_preference", "project_preference", "gap_memory",
            "ecosystem_observation", "dream_hypothesis"
        ],
        "valid_scopes": ["user", "repo", "project", "plugin", "global"],
        "valid_memory_status": ["candidate", "active", "stale", "contradicted", "retired", "quarantined", "deleted"],
        "valid_privacy": ["metadata", "local_only", "contains_pii", "redacted"],
    },
    "dream_report": {
        "required": ["schema", "id", "job", "created_at", "summary"],
        "valid_schema": ["dream_report.v1"],
    },
    "learning_candidate": {
        "required": ["schema", "id", "kind", "status", "title", "risk", "payload"],
        "valid_schema": ["learning_candidate.v1"],
        "valid_learning_kinds": [
            "route_update", "benchmark_candidate", "memory_promotion",
            "catalog_proposal", "panel_proposal", "retrieval_hint"
        ],
        "valid_learning_status": ["pending", "approved", "rejected", "applied", "reverted", "expired", "needs_evidence"],
        "valid_risk": ["low", "medium", "high"],
    },
    "capability_graph": {
        "required": ["schema", "plugin_version", "nodes", "edges", "health", "source_hash"],
        "valid_schema": ["capability_graph.v1"],
    },
    "design_review": {
        "required": [
            "scope",
            "evidence_reviewed",
            "product_domain_fit",
            "visual_hierarchy_findings",
            "layout_density_findings",
            "interaction_state_findings",
            "copy_tone_findings",
            "design_system_alignment",
            "ranked_recommendations",
            "follow_up_validation_plan",
        ],
        "min_counts": {
            "evidence_reviewed": 1,
            "ranked_recommendations": 1,
            "follow_up_validation_plan": 1,
        },
    },
    "visual_qa_report": {
        "required": [
            "surface",
            "run_command",
            "viewports",
            "states_inspected",
            "screenshot_evidence",
            "visual_findings",
            "fixes_applied_or_proposed",
            "before_after_verification",
            "remaining_visual_risks",
            "validation",
        ],
        "min_counts": {
            "viewports": 1,
            "screenshot_evidence": 1,
            "remaining_visual_risks": 1,
        },
    },
    "design_system_review": {
        "required": [
            "design_system_map",
            "token_semantics_findings",
            "component_api_findings",
            "state_accessibility_coverage_findings",
            "drift_duplication_findings",
            "migration_sequence",
            "governance_checks",
            "validation_commands",
        ],
        "min_counts": {
            "design_system_map": 1,
            "governance_checks": 1,
            "validation_commands": 1,
        },
    },
    "experience_quality_report": {
        "required": [
            "surface_map",
            "evidence_inventory",
            "ranked_findings",
            "visual_quality_assessment",
            "interaction_accessibility_risks",
            "validation_plan",
            "implementation_sequence",
            "preserved_strengths",
        ],
        "min_counts": {
            "evidence_inventory": 1,
            "ranked_findings": 1,
            "validation_plan": 1,
        },
    },
    "invocation_telemetry_audit": {
        "required": [
            "schema",
            "generated_at",
            "window_days",
            "runtime_events",
            "agent_dispatches",
            "pathfinder",
            "activation_gaps",
            "thresholds",
            "ok",
        ],
        "valid_schema": ["invocation_telemetry_audit.v1", "invocation_telemetry_audit.v2"],
        "required_nested": {
            "runtime_events": ["skill_invocations", "legacy_skill_invocations"],
            "agent_dispatches": ["total", "plugin_total", "plugin_share_pct", "explore_total", "explore_share_pct"],
            "pathfinder": [
                "decisions",
                "real_decisions",
                "bench_decisions",
                "synthetic_decisions",
                "real_pathfinder_ratio_pct",
            ],
            "activation_gaps": ["skills_never_invoked", "agents_never_dispatched"],
        },
    },
    "goal_contract": {
        "required": [
            "condition",
            "acceptance_criteria",
            "proof_method",
            "bounds",
            "status",
            "runtime",
            "native_goal_available",
            "evidence_refs",
        ],
        "valid_status": ["active", "met", "blocked", "cleared"],
        "valid_runtime": ["codex", "claude-code"],
        "min_counts": {
            "acceptance_criteria": 1,
            "evidence_refs": 1,
        },
    },
}


def load_artifact(path: Path):
    """Load YAML or JSON artifact."""
    text = path.read_text()
    if path.suffix in (".yaml", ".yml"):
        if yaml is None:
            json_twin = path.with_suffix(".json")
            if json_twin.exists():
                return json.loads(json_twin.read_text(encoding="utf-8")), None
            return None, "PyYAML not installed; install with pip install pyyaml"
        return yaml.safe_load(text), None
    elif path.suffix == ".json":
        return json.loads(text), None
    else:
        # Try YAML first, then JSON
        if yaml:
            try:
                return yaml.safe_load(text), None
            except Exception:
                pass
        try:
            return json.loads(text), None
        except Exception as e:
            return None, f"could not parse as YAML or JSON: {e}"


def validate(artifact_type: str, data: dict) -> dict:
    """Validate an artifact against its schema."""
    if artifact_type not in SCHEMAS:
        return {"ok": False, "error": f"unknown artifact_type: {artifact_type}",
                "available": list(SCHEMAS.keys())}

    schema = SCHEMAS[artifact_type]
    findings = []

    # Drill into nested wrapper if present (e.g., {"prd": {...}} → {...})
    if len(data) == 1 and isinstance(next(iter(data.values())), dict):
        inner_key = next(iter(data.keys()))
        if inner_key in (artifact_type, artifact_type.replace("_", ""), "prd"):
            data = data[inner_key]

    # Required fields
    for field in schema.get("required", []):
        if field not in data:
            findings.append({"severity": "high", "issue": "missing_required_field", "field": field})
        elif data[field] is None or data[field] == "" or data[field] == []:
            findings.append({"severity": "high", "issue": "empty_required_field", "field": field})

    # Min lengths
    for field, min_len in schema.get("min_lengths", {}).items():
        val = data.get(field)
        if val:
            length = len(val) if isinstance(val, (list, str)) else 1
            if length < min_len:
                findings.append({"severity": "medium", "issue": "field_too_short",
                               "field": field, "length": length, "required": min_len})

    # Nested required (technical_design, ai_specific)
    for nested_key in ("required_in_technical_design", "required_in_ai_specific",
                       "required_in_each_gap"):
        if nested_key in schema:
            parent_field = nested_key.replace("required_in_", "")
            if parent_field == "each_gap":
                # Special: iterate contract_gaps
                gaps = data.get("contract_gaps", [])
                for i, gap in enumerate(gaps):
                    for f in schema[nested_key]:
                        if f not in gap:
                            findings.append({"severity": "high",
                                           "issue": "missing_field_in_array_item",
                                           "array": "contract_gaps", "index": i, "field": f})
            else:
                parent = data.get(parent_field, {})
                for f in schema[nested_key]:
                    if f not in parent:
                        findings.append({"severity": "high",
                                       "issue": f"missing_field_in_{parent_field}", "field": f})

    # Enum validation. Keep this explicit: plural schema keys do not map
    # mechanically to field names such as "severity" or "confidence".
    enum_fields = {
        "valid_severities": "severity",
        "valid_confidences": "confidence",
        "valid_categories": "category",
        "valid_status": "status",
        "valid_schema": "schema",
        "valid_kinds": "kind",
        "valid_scopes": "scope",
        "valid_memory_status": "status",
        "valid_privacy": "privacy",
        "valid_learning_kinds": "kind",
        "valid_learning_status": "status",
        "valid_risk": "risk",
        "valid_runtime": "runtime",
    }
    for schema_key, field in enum_fields.items():
        if schema_key not in schema:
            continue
        actual = data.get(field)
        if actual and actual not in schema[schema_key]:
            findings.append({"severity": "high", "issue": "invalid_enum_value",
                           "field": field, "value": actual, "allowed": schema[schema_key]})

    if artifact_type == "contract_drift_report":
        allowed_severity = SCHEMAS["gap_ledger_entry"]["valid_severities"]
        for i, gap in enumerate(data.get("contract_gaps", [])):
            actual = gap.get("severity")
            if actual and actual not in allowed_severity:
                findings.append({"severity": "high", "issue": "invalid_enum_value",
                               "array": "contract_gaps", "index": i, "field": "severity",
                               "value": actual, "allowed": allowed_severity})

    # Min counts
    if "min_underserved_zones" in schema:
        zones = data.get("underserved_zones", [])
        if len(zones) < schema["min_underserved_zones"]:
            findings.append({"severity": "medium", "issue": "too_few_underserved_zones",
                           "count": len(zones), "required": schema["min_underserved_zones"]})
    if "min_reframings" in schema:
        reframings = data.get("reframings", [])
        if len(reframings) < schema["min_reframings"]:
            findings.append({"severity": "medium", "issue": "too_few_reframings",
                           "count": len(reframings), "required": schema["min_reframings"]})
    for field, min_count in schema.get("min_counts", {}).items():
        value = data.get(field)
        if isinstance(value, (list, str, dict)):
            count = len(value)
        elif value:
            count = 1
        else:
            count = 0
        if count < min_count:
            findings.append({"severity": "high", "issue": "too_few_items",
                           "field": field, "count": count, "required": min_count})

    for parent_field, required_fields in schema.get("required_nested", {}).items():
        parent = data.get(parent_field)
        if not isinstance(parent, dict):
            findings.append({"severity": "high", "issue": "missing_nested_object",
                           "field": parent_field})
            continue
        for nested_field in required_fields:
            if nested_field not in parent:
                findings.append({"severity": "high",
                               "issue": "missing_nested_field",
                               "field": parent_field,
                               "nested_field": nested_field})

    return {
        "ok": len([f for f in findings if f["severity"] == "high"]) == 0,
        "artifact_type": artifact_type,
        "total_findings": len(findings),
        "high": [f for f in findings if f["severity"] == "high"],
        "medium": [f for f in findings if f["severity"] == "medium"],
    }


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s_v = sub.add_parser("validate")
    s_v.add_argument("artifact_type")
    s_v.add_argument("file")
    sub.add_parser("schemas")
    s_s = sub.add_parser("schema")
    s_s.add_argument("artifact_type")

    args = ap.parse_args()

    if args.cmd == "schemas":
        print(json.dumps({"known_artifact_types": list(SCHEMAS.keys())}, indent=2))
        return 0

    if args.cmd == "schema":
        if args.artifact_type not in SCHEMAS:
            print(json.dumps({"error": "unknown", "available": list(SCHEMAS.keys())}))
            return 1
        print(json.dumps({args.artifact_type: SCHEMAS[args.artifact_type]}, indent=2))
        return 0

    if args.cmd == "validate":
        data, err = load_artifact(Path(args.file))
        if err:
            print(json.dumps({"ok": False, "error": err}))
            return 1
        result = validate(args.artifact_type, data)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
