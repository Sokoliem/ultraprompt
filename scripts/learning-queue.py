#!/usr/bin/env python3
"""Governed V8 learning candidate queue."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from cognitive_common import (
    append_jsonl,
    command_result,
    data_dir,
    print_json,
    read_json,
    read_jsonl,
    sortable_id,
    utc_now,
    write_json,
)

KINDS = {
    "route_update",
    "benchmark_candidate",
    "memory_promotion",
    "catalog_proposal",
    "panel_proposal",
    "retrieval_hint",
    "prompt_update",
    "agent_contract_update",
    "eval_case_update",
    "dashboard_ui_update",
    "telemetry_parser_update",
    "source_patch",
}
STATUSES = {"pending", "approved", "rejected", "applied", "reverted", "expired", "needs_evidence"}
LOW_RISK = {"route_update", "benchmark_candidate", "memory_promotion", "retrieval_hint", "eval_case_update"}
ROUTE_FAILURE_KINDS = {
    "wrong_skill",
    "wrong_agent",
    "explore_fallback",
    "low_confidence_gap",
    "truncation_prone_agent",
    "stale_legacy_prefix",
    "missing_artifact_contract",
    "handoff_partial",
    "handoff_empty",
}


def queue_path() -> Path:
    return data_dir("learning") / "candidates.jsonl"


def policy_path() -> Path:
    return data_dir("learning") / "route-policy.json"


def event(action: str, candidate: dict[str, Any]) -> dict[str, Any]:
    return {"ts": utc_now(), "action": action, "candidate": candidate}


def latest_candidates() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(queue_path()):
        cand = row.get("candidate") if isinstance(row.get("candidate"), dict) else row
        if cand.get("id"):
            out[cand["id"]] = cand
    return out


def persist(action: str, candidate: dict[str, Any]) -> dict[str, Any]:
    candidate = {**candidate, "updated_at": utc_now()}
    append_jsonl(queue_path(), event(action, candidate))
    return candidate


def route_update_failure_group(payload: dict[str, Any]) -> str:
    failure_kind = str(payload.get("failure_kind") or "").lower().replace(" ", "_").replace("-", "_")
    handoff_status = str(payload.get("handoff_status") or "").lower()
    agent = str(payload.get("agent") or "")
    if agent == "Explore":
        return "explore_fallback"
    if handoff_status in {"truncated", "persisted_output"} or "trunc" in failure_kind:
        return "truncation_prone_agent"
    if handoff_status in {"partial", "empty"}:
        return f"handoff_{handoff_status}"
    if "artifact" in failure_kind and "missing" in failure_kind:
        return "missing_artifact_contract"
    if "agent" in failure_kind:
        return "wrong_agent"
    if "skill" in failure_kind or "route" in failure_kind:
        return "wrong_skill"
    if "confidence" in failure_kind:
        return "low_confidence_gap"
    if "legacy" in failure_kind or "prefix" in failure_kind:
        return "stale_legacy_prefix"
    return failure_kind if failure_kind in ROUTE_FAILURE_KINDS else "wrong_skill"


def route_update_policy_preview(payload: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    return {
        "operation": "append_or_replace_route_overlay",
        "policy_path": str(policy_path()),
        "route": {
            "id": candidate_id,
            "intent_pattern": payload.get("intent_pattern") or payload.get("intent") or "",
            "skill": payload.get("skill") or payload.get("preferred_skill") or "",
            "agent": payload.get("agent") or "",
            "panel": payload.get("panel") or "",
            "weight_delta": float(payload.get("weight_delta", 0.1)),
            "reason": payload.get("reason") or "",
            "failure_group": route_update_failure_group(payload),
        },
        "durable_mutation_requires": "learning_apply",
    }


def route_update_replay_impact(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": "preview_only",
        "intent_pattern": payload.get("intent_pattern") or payload.get("intent") or "",
        "expected_effect": "increase selected route weight for the matched intent pattern",
        "validation_commands": [
            "python3 scripts/run-pathfinder-tests.py",
            "python3 scripts/run-router-bench.py",
            "python3 scripts/replay-routing-events.py --json --days 7 --limit 50",
        ],
    }


def evidence_summary(kind: str, payload: dict[str, Any], evidence: list[Any]) -> dict[str, Any]:
    return {
        "evidence_count": len(evidence),
        "failure_kind": payload.get("failure_kind") or "",
        "handoff_status": payload.get("handoff_status") or "",
        "artifact_path": payload.get("artifact_path") or "",
        "group": route_update_failure_group(payload) if kind == "route_update" else kind,
    }


def enrich_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    payload = candidate.get("payload") or {}
    evidence = candidate.get("evidence") if isinstance(candidate.get("evidence"), list) else []
    enriched = {
        **candidate,
        "evidence_summary": evidence_summary(str(candidate.get("kind")), payload, evidence),
    }
    if candidate.get("kind") == "route_update":
        enriched["replay_impact"] = route_update_replay_impact(payload)
        enriched["policy_preview"] = route_update_policy_preview(payload, candidate["id"])
    return enriched


def add_candidate(args: argparse.Namespace) -> dict[str, Any]:
    if args.kind not in KINDS:
        raise ValueError(f"invalid learning kind: {args.kind}")
    payload = json.loads(args.payload_json or "{}")
    risk = "low" if args.kind in LOW_RISK else "high"
    candidate = {
        "schema": "learning_candidate.v1",
        "id": sortable_id("learn"),
        "kind": args.kind,
        "status": "pending",
        "title": args.title,
        "risk": args.risk or risk,
        "payload": payload,
        "evidence": json.loads(args.evidence_json or "[]"),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "validation": None,
        "rollback": None,
        "notes": args.notes,
        "auto_apply": bool(args.auto_apply),
        "evidence_threshold": args.evidence_threshold,
        "mutation_scope": args.mutation_scope,
        "gate_results": json.loads(args.gate_results_json or "{}"),
        "patch_path": args.patch_path,
        "rollback_path": args.rollback_path,
        "learner_eval": json.loads(args.learner_eval_json or "{}"),
        "post_apply_monitor": json.loads(args.post_apply_monitor_json or "{}"),
    }
    candidate = enrich_candidate(candidate)
    persist("add", candidate)
    emit_cognitive_event("learning_candidate_created", {"candidate_id": candidate["id"], "kind": candidate["kind"], "risk": candidate["risk"]})
    return command_result(True, candidate=candidate)


def set_status(args: argparse.Namespace, status: str) -> dict[str, Any]:
    candidates = latest_candidates()
    candidate = candidates.get(args.candidate_id)
    if not candidate:
        raise ValueError(f"unknown candidate: {args.candidate_id}")
    candidate = {**candidate, "status": status}
    if args.reason:
        candidate.setdefault("history", []).append({"ts": utc_now(), "status": status, "reason": args.reason})
    persist(status, candidate)
    return command_result(True, candidate=candidate)


def run_validation() -> dict[str, Any]:
    commands = [
        [sys.executable, "scripts/build-capability-graph.py", "--check"],
        [sys.executable, "scripts/run-pathfinder-tests.py", "--no-telemetry"],
        [sys.executable, "scripts/run-router-bench.py"],
    ]
    results = []
    ok = True
    root = Path(__file__).resolve().parents[1]
    for cmd in commands:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=180)
        item = {
            "cmd": " ".join(cmd[1:]),
            "ok": proc.returncode == 0,
            "exit": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }
        results.append(item)
        ok = ok and item["ok"]
    return {"ok": ok, "results": results}


def apply_route_update(candidate: dict[str, Any]) -> dict[str, Any]:
    policy = read_json(policy_path(), {"schema": "route_policy.v1", "routes": [], "updated_at": None})
    before = json.loads(json.dumps(policy))
    payload = candidate.get("payload") or {}
    route = {
        "id": candidate["id"],
        "intent_pattern": payload.get("intent_pattern") or payload.get("intent") or "",
        "skill": payload.get("skill") or payload.get("preferred_skill") or "",
        "agent": payload.get("agent") or "",
        "panel": payload.get("panel") or "",
        "failure_group": route_update_failure_group(payload),
        "weight_delta": float(payload.get("weight_delta", 0.1)),
        "reason": payload.get("reason") or candidate.get("title"),
        "expires_at": payload.get("expires_at"),
        "applied_at": utc_now(),
    }
    if not route["intent_pattern"] or not route["skill"]:
        raise ValueError("route_update requires intent_pattern and skill")
    policy["routes"] = [r for r in policy.get("routes", []) if r.get("id") != candidate["id"]]
    policy["routes"].append(route)
    policy["updated_at"] = utc_now()
    write_json(policy_path(), policy)
    return {"kind": "route_policy", "path": str(policy_path()), "before": before, "after": policy}


def apply_candidate(args: argparse.Namespace) -> dict[str, Any]:
    candidates = latest_candidates()
    candidate = candidates.get(args.candidate_id)
    if not candidate:
        raise ValueError(f"unknown candidate: {args.candidate_id}")
    auto_apply = bool(candidate.get("auto_apply"))
    if candidate.get("status") != "approved" and not args.force and not auto_apply:
        raise ValueError("candidate_must_be_approved")
    if candidate.get("risk") == "high" and not args.force and not auto_apply:
        raise ValueError("high_risk_candidate_requires_explicit_force")
    validation = run_validation()
    if not validation["ok"]:
        candidate = {**candidate, "status": "needs_evidence", "validation": validation}
        persist("needs_evidence", candidate)
        return command_result(False, error="validation_failed", candidate=candidate)
    rollback = {"kind": "none", "details": "no source mutation"}
    if candidate["kind"] == "route_update":
        rollback = apply_route_update(candidate)
    candidate = {**candidate, "status": "applied", "validation": validation, "rollback": rollback, "applied_at": utc_now()}
    persist("apply", candidate)
    emit_cognitive_event("learning_candidate_applied", {"candidate_id": candidate["id"], "kind": candidate["kind"]})
    return command_result(True, candidate=candidate)


def revert_candidate(args: argparse.Namespace) -> dict[str, Any]:
    candidates = latest_candidates()
    candidate = candidates.get(args.candidate_id)
    if not candidate:
        rollback = data_dir("self-improvement") / "rollbacks" / f"{args.candidate_id}.json"
        if rollback.exists():
            proc = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("self-improve.py")), "rollback", args.candidate_id],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                timeout=60,
            )
            try:
                return json.loads(proc.stdout)
            except Exception:
                return command_result(proc.returncode == 0, stdout=proc.stdout, stderr=proc.stderr)
        raise ValueError(f"unknown candidate: {args.candidate_id}")
    rollback = candidate.get("rollback") or {}
    if rollback.get("kind") == "route_policy":
        write_json(policy_path(), rollback.get("before") or {"schema": "route_policy.v1", "routes": []})
    candidate = {**candidate, "status": "reverted", "reverted_at": utc_now()}
    persist("revert", candidate)
    emit_cognitive_event("learning_candidate_reverted", {"candidate_id": candidate["id"], "kind": candidate["kind"]})
    return command_result(True, candidate=candidate)


def list_candidates(args: argparse.Namespace) -> dict[str, Any]:
    rows = [enrich_candidate(row) for row in latest_candidates().values()]
    if args.status:
        rows = [c for c in rows if c.get("status") == args.status]
    if args.kind:
        rows = [c for c in rows if c.get("kind") == args.kind]
    rows.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
    limited = rows[: args.limit]
    result = command_result(True, count=len(limited), candidates=limited, path=str(queue_path()))
    if getattr(args, "grouped", False):
        groups: dict[str, dict[str, Any]] = {}
        for candidate in limited:
            summary = candidate.get("evidence_summary") or {}
            group = str(summary.get("group") or candidate.get("kind") or "unknown")
            bucket = groups.setdefault(group, {
                "group": group,
                "count": 0,
                "candidate_ids": [],
                "evidence_count": 0,
                "examples": [],
            })
            bucket["count"] += 1
            bucket["candidate_ids"].append(candidate.get("id"))
            bucket["evidence_count"] += int(summary.get("evidence_count") or 0)
            if len(bucket["examples"]) < 3:
                bucket["examples"].append({
                    "id": candidate.get("id"),
                    "title": candidate.get("title"),
                    "policy_preview": candidate.get("policy_preview"),
                    "replay_impact": candidate.get("replay_impact"),
                })
        result["candidate_groups"] = sorted(groups.values(), key=lambda item: (-item["count"], item["group"]))
    return result


def stats() -> dict[str, Any]:
    rows = latest_candidates().values()
    by_status: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    for row in rows:
        by_status[row.get("status", "unknown")] = by_status.get(row.get("status", "unknown"), 0) + 1
        by_kind[row.get("kind", "unknown")] = by_kind.get(row.get("kind", "unknown"), 0) + 1
    return command_result(True, path=str(queue_path()), policy_path=str(policy_path()), total=sum(by_status.values()), by_status=by_status, by_kind=by_kind)


def emit_cognitive_event(event_type: str, payload: dict[str, Any]) -> None:
    script = Path(__file__).with_name("cognitive-event-log.py")
    try:
        subprocess.run(
            [sys.executable, str(script), "write", event_type, "--json", json.dumps(payload), "--privacy", "metadata"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add")
    add.add_argument("--kind", required=True, choices=sorted(KINDS))
    add.add_argument("--title", required=True)
    add.add_argument("--payload-json", default="{}")
    add.add_argument("--evidence-json", default="[]")
    add.add_argument("--risk", choices=["low", "medium", "high"], default="")
    add.add_argument("--notes", default="")
    add.add_argument("--auto-apply", action="store_true")
    add.add_argument("--evidence-threshold", type=int, default=1)
    add.add_argument("--mutation-scope", default="learning_overlay")
    add.add_argument("--gate-results-json", default="{}")
    add.add_argument("--patch-path", default="")
    add.add_argument("--rollback-path", default="")
    add.add_argument("--learner-eval-json", default="{}")
    add.add_argument("--post-apply-monitor-json", default="{}")

    list_p = sub.add_parser("list")
    list_p.add_argument("--status", choices=sorted(STATUSES), default="")
    list_p.add_argument("--kind", choices=sorted(KINDS), default="")
    list_p.add_argument("--limit", type=int, default=100)
    list_p.add_argument("--grouped", action="store_true")

    for name in ("approve", "reject", "expire", "needs-evidence"):
        p = sub.add_parser(name)
        p.add_argument("candidate_id")
        p.add_argument("--reason", default="")

    ap = sub.add_parser("apply")
    ap.add_argument("candidate_id")
    ap.add_argument("--force", action="store_true")

    rv = sub.add_parser("revert")
    rv.add_argument("candidate_id")

    sub.add_parser("stats")
    sub.add_parser("policy")

    args = parser.parse_args()
    try:
        if args.cmd == "add":
            print_json(add_candidate(args))
        elif args.cmd == "list":
            print_json(list_candidates(args))
        elif args.cmd == "approve":
            print_json(set_status(args, "approved"))
        elif args.cmd == "reject":
            print_json(set_status(args, "rejected"))
        elif args.cmd == "expire":
            print_json(set_status(args, "expired"))
        elif args.cmd == "needs-evidence":
            print_json(set_status(args, "needs_evidence"))
        elif args.cmd == "apply":
            print_json(apply_candidate(args))
        elif args.cmd == "revert":
            print_json(revert_candidate(args))
        elif args.cmd == "stats":
            print_json(stats())
        elif args.cmd == "policy":
            print_json(command_result(True, policy=read_json(policy_path(), {"schema": "route_policy.v1", "routes": []}), path=str(policy_path())))
    except Exception as exc:
        print_json(command_result(False, error=str(exc)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
