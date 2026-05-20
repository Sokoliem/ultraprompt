#!/usr/bin/env python3
"""Evidence-backed self-improvement autopilot for Ultraprompt V8.5.

The runner turns telemetry into executable learning jobs. It is intentionally
local-first: run records, patch manifests, rollback manifests, and canary
overlays live under ~/.ultraprompt/self-improvement and ~/.ultraprompt/learning.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from cognitive_common import (
    ROOT,
    command_result,
    data_dir,
    print_json,
    read_json,
    sortable_id,
    stable_hash,
    utc_now,
    write_json,
)

MODES = {"autopilot", "canary", "dry-run"}
SCOPES = {"all", "routing", "telemetry", "dashboard", "tests"}
SELF_IMPROVEMENT_KINDS = {
    "route_update",
    "prompt_update",
    "agent_contract_update",
    "eval_case_update",
    "dashboard_ui_update",
    "telemetry_parser_update",
    "source_patch",
}


def base_dir() -> Path:
    return data_dir("self-improvement")


def runs_dir() -> Path:
    return base_dir() / "runs"


def patches_dir() -> Path:
    return base_dir() / "patches"


def rollbacks_dir() -> Path:
    return base_dir() / "rollbacks"


def overlays_dir() -> Path:
    return data_dir("learning") / "overlays"


def route_policy_path() -> Path:
    return data_dir("learning") / "route-policy.json"


def run_path(run_id: str) -> Path:
    return runs_dir() / f"{run_id}.json"


def patch_path(run_id: str) -> Path:
    return patches_dir() / f"{run_id}.json"


def rollback_path(run_id: str) -> Path:
    return rollbacks_dir() / f"{run_id}.json"


def run_script(args: list[str], *, timeout: int = 120, repo: Path | None = None) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / args[0]), *args[1:]],
        cwd=repo or ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    try:
        parsed = json.loads(proc.stdout)
    except Exception:
        parsed = None
    return {
        "cmd": " ".join(args),
        "ok": proc.returncode == 0,
        "exit": proc.returncode,
        "stdout": proc.stdout[-8000:],
        "stderr": proc.stderr[-8000:],
        "json": parsed,
    }


def load_evidence(scope: str, days: int) -> dict[str, Any]:
    audit = run_script(["audit-invocation-telemetry.py", "--json", "--days", str(days)], timeout=90)
    replay = run_script(["replay-routing-events.py", "--json", "--days", "7", "--limit", "100"], timeout=120)
    learning = run_script(["learning-queue.py", "list", "--grouped", "--limit", "200"], timeout=30)
    scorecard_path = ROOT / "dist" / "release-scorecard.json"
    scorecard = read_json(scorecard_path, {})
    return {
        "schema": "self_improvement_evidence.v1",
        "scope": scope,
        "days": days,
        "audit": audit.get("json") or {},
        "audit_exit": audit.get("exit"),
        "replay": replay.get("json") or {},
        "replay_exit": replay.get("exit"),
        "learning": learning.get("json") or {},
        "learning_exit": learning.get("exit"),
        "scorecard": scorecard.get("release_scorecard", scorecard),
        "scorecard_path": str(scorecard_path),
        "collected_at": utc_now(),
    }


def route_payload_for_group(kind: str) -> dict[str, Any]:
    if kind == "explore_fallback":
        return {
            "intent_pattern": "map",
            "skill": "repo-map",
            "agent": "ultraprompt:scout",
            "weight_delta": 0.25,
            "failure_kind": "explore_fallback",
            "reason": "Telemetry shows generic Explore remains overused for repo discovery intents.",
        }
    if kind == "legacy_prefix":
        return {
            "intent_pattern": "ultra-prompt",
            "skill": "pathfinding-invocation-review",
            "weight_delta": 0.2,
            "failure_kind": "stale_legacy_prefix",
            "reason": "Telemetry still sees legacy prefix drift that should route to invocation review.",
        }
    if kind == "pathfinder_live_signal":
        return {
            "intent_pattern": "routing thresholds",
            "skill": "pathfinding-invocation-review",
            "agent": "ultraprompt:invocation-reliability-auditor",
            "weight_delta": 0.2,
            "failure_kind": "low_confidence_gap",
            "reason": "Live pathfinder evidence is thin compared with bench/golden events.",
        }
    return {
        "intent_pattern": kind.replace("_", " "),
        "skill": "pathfinding-invocation-review",
        "weight_delta": 0.1,
        "failure_kind": kind,
        "reason": f"Telemetry candidate group: {kind}.",
    }


def hypothesis_from_group(group: dict[str, Any]) -> dict[str, Any]:
    kind = str(group.get("kind") or group.get("group") or "unknown")
    evidence_count = int(group.get("evidence_count") or 0)
    if kind in {"explore_fallback", "legacy_prefix", "pathfinder_live_signal"}:
        candidate_kind = "route_update"
        payload = route_payload_for_group(kind)
    elif kind == "agent_handoff":
        candidate_kind = "agent_contract_update"
        payload = {
            "failure_kind": "missing_artifact_contract",
            "handoff_status": "partial",
            "reason": "High-output agent handoffs lack artifact paths or compact envelopes in telemetry.",
        }
    else:
        candidate_kind = "eval_case_update"
        payload = {"failure_kind": kind, "reason": f"Telemetry group {kind} needs eval coverage."}
    return {
        "id": sortable_id("hyp"),
        "kind": candidate_kind,
        "title": f"Auto-improve {kind}",
        "priority": "high" if evidence_count >= 50 else "medium",
        "evidence_count": evidence_count,
        "evidence_group": kind,
        "payload": payload,
        "risk": "low" if candidate_kind in {"route_update", "eval_case_update"} else "medium",
        "mutation_scope": "learning_overlay" if candidate_kind == "route_update" else "repo_code_allowed",
    }


def derive_hypotheses(evidence: dict[str, Any], scope: str) -> list[dict[str, Any]]:
    audit = evidence.get("audit") or {}
    groups = ((audit.get("candidate_groups") or {}).get("groups") or [])
    if not groups:
        groups = audit.get("routing_improvement_candidates") or []
    hypotheses = [hypothesis_from_group(group) for group in groups]
    runtime_events = audit.get("runtime_events") or {}
    if int((runtime_events.get("by_runtime") or {}).get("unknown") or 0) > 0:
        hypotheses.append({
            "id": sortable_id("hyp"),
            "kind": "telemetry_parser_update",
            "title": "Reduce unknown runtime telemetry bucket",
            "priority": "high",
            "evidence_count": int((runtime_events.get("by_runtime") or {}).get("unknown") or 0),
            "evidence_group": "unknown_runtime",
            "payload": {
                "failure_kind": "unknown_runtime_attribution",
                "reason": "Runtime events still contain unknown attribution and should drive parser/backfill work.",
            },
            "risk": "medium",
            "mutation_scope": "repo_code_allowed",
        })
    activation = audit.get("activation_gaps") or {}
    never_fired = list(activation.get("skills_never_invoked") or []) + list(activation.get("agents_never_dispatched") or [])
    if never_fired:
        hypotheses.append({
            "id": sortable_id("hyp"),
            "kind": "eval_case_update",
            "title": "Add specialist coverage eval cases",
            "priority": "medium",
            "evidence_count": len(never_fired),
            "evidence_group": "specialist_coverage_gap",
            "payload": {
                "failure_kind": "never_fired_coverage",
                "skills_or_agents": never_fired[:25],
                "reason": "Telemetry shows skills or agents with no live activation evidence.",
            },
            "risk": "low",
            "mutation_scope": "repo_code_allowed",
        })
    allowed_by_scope = {
        "all": SELF_IMPROVEMENT_KINDS,
        "routing": {"route_update", "eval_case_update", "agent_contract_update"},
        "telemetry": {"telemetry_parser_update", "eval_case_update"},
        "dashboard": {"dashboard_ui_update", "eval_case_update"},
        "tests": {"eval_case_update", "source_patch"},
    }
    allowed = allowed_by_scope.get(scope, SELF_IMPROVEMENT_KINDS)
    return [hyp for hyp in hypotheses if hyp["kind"] in allowed]


def materialize_learning_candidate(hypothesis: dict[str, Any], run_id: str) -> dict[str, Any]:
    payload = {
        **(hypothesis.get("payload") or {}),
        "self_improvement_run_id": run_id,
        "materialized_from_audit": True,
    }
    result = run_script([
        "learning-queue.py",
        "add",
        "--kind",
        hypothesis["kind"],
        "--title",
        hypothesis["title"],
        "--payload-json",
        json.dumps(payload),
        "--evidence-json",
        json.dumps([{"kind": "telemetry_group", "ref": hypothesis.get("evidence_group"), "count": hypothesis.get("evidence_count")}]),
        "--risk",
        hypothesis.get("risk", "medium"),
        "--auto-apply",
        "--evidence-threshold",
        str(max(1, min(25, int(hypothesis.get("evidence_count") or 1)))),
        "--mutation-scope",
        hypothesis.get("mutation_scope", "repo_code_allowed"),
    ], timeout=30)
    return result.get("json") or result


def build_patch_manifest(run_id: str, hypotheses: list[dict[str, Any]], candidate_results: list[dict[str, Any]]) -> dict[str, Any]:
    operations = []
    if not hypotheses:
        operations.append({
            "operation": "no_op",
            "reason": "No telemetry-backed hypotheses met the evidence threshold for this scope.",
        })
    for index, hyp in enumerate(hypotheses):
        candidate = candidate_results[index] if index < len(candidate_results) else {}
        operations.append({
            "operation": "learning_candidate" if candidate else "hypothesis_preview",
            "hypothesis_id": hyp.get("id"),
            "candidate_id": ((candidate.get("candidate") or {}).get("id") if isinstance(candidate, dict) else None),
            "kind": hyp.get("kind"),
            "title": hyp.get("title"),
            "payload": hyp.get("payload"),
        })
    return {
        "schema": "self_improvement_patch.v1",
        "id": f"{run_id}-patch",
        "run_id": run_id,
        "created_at": utc_now(),
        "mutation_scope": "any_repo_code_gated",
        "operations": operations,
        "patch_hash": stable_hash(operations),
    }


def apply_route_overlay(run_id: str, hypotheses: list[dict[str, Any]], *, promote: bool) -> dict[str, Any]:
    route_hypotheses = [h for h in hypotheses if h.get("kind") == "route_update"]
    before = read_json(route_policy_path(), {"schema": "route_policy.v1", "routes": []})
    routes = list(before.get("routes") or [])
    overlay_routes = []
    for hyp in route_hypotheses:
        payload = hyp.get("payload") or {}
        route = {
            "id": f"{run_id}-{hyp['id']}",
            "intent_pattern": payload.get("intent_pattern") or "",
            "skill": payload.get("skill") or "",
            "agent": payload.get("agent") or "",
            "panel": payload.get("panel") or "",
            "failure_group": hyp.get("evidence_group"),
            "weight_delta": float(payload.get("weight_delta", 0.1)),
            "reason": payload.get("reason") or hyp.get("title"),
            "self_improvement_run_id": run_id,
            "applied_at": utc_now(),
        }
        if route["intent_pattern"] and route["skill"]:
            overlay_routes.append(route)
    overlay_path = overlays_dir() / run_id / "route-policy.json"
    overlay = {"schema": "route_policy_overlay.v1", "run_id": run_id, "routes": overlay_routes, "created_at": utc_now()}
    write_json(overlay_path, overlay)
    if promote and overlay_routes:
        existing_ids = {route.get("id") for route in overlay_routes}
        routes = [route for route in routes if route.get("id") not in existing_ids]
        routes.extend(overlay_routes)
        after = {**before, "schema": before.get("schema") or "route_policy.v1", "routes": routes, "updated_at": utc_now()}
        write_json(route_policy_path(), after)
    else:
        after = before
    return {
        "kind": "route_policy",
        "overlay_path": str(overlay_path),
        "promoted": promote and bool(overlay_routes),
        "path": str(route_policy_path()),
        "before": before,
        "after": after,
        "route_count": len(overlay_routes),
    }


def apply_source_changes(run_id: str, repo: Path, source_changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rollback_entries = []
    for change in source_changes:
        rel = str(change.get("path") or "").strip()
        if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValueError(f"unsafe source patch path: {rel}")
        path = repo / rel
        before_exists = path.exists()
        before_text = path.read_text(encoding="utf-8") if before_exists else None
        after_text = str(change.get("content", ""))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(after_text, encoding="utf-8")
        rollback_entries.append({
            "kind": "source_file",
            "path": str(path),
            "relative_path": rel,
            "before_exists": before_exists,
            "before_text": before_text,
            "after_hash": stable_hash(after_text),
            "run_id": run_id,
        })
    return rollback_entries


def rollback_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    restored = []
    for entry in manifest.get("entries") or []:
        if entry.get("kind") == "route_policy":
            write_json(Path(entry["path"]), entry.get("before") or {"schema": "route_policy.v1", "routes": []})
            restored.append(entry["path"])
        elif entry.get("kind") == "source_file":
            path = Path(entry["path"])
            if entry.get("before_exists"):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(entry.get("before_text") or "", encoding="utf-8")
            else:
                path.unlink(missing_ok=True)
            restored.append(str(path))
    return {"restored": restored, "count": len(restored)}


def validation_commands(scope: str) -> list[list[str]]:
    fast = os.environ.get("ULTRAPROMPT_SELF_IMPROVE_FAST") == "1"
    commands = [["generated-artifacts.py", "check", "--json"]]
    if fast:
        commands.append(["run-router-bench.py"])
        return commands
    commands.extend([
        ["run-router-bench.py"],
        ["run-pathfinder-tests.py", "--no-telemetry"],
        ["replay-routing-events.py", "--json", "--days", "7", "--limit", "50"],
        ["audit-invocation-telemetry.py", "--json", "--days", "14"],
    ])
    if scope in {"all", "routing", "telemetry", "dashboard"}:
        commands.append(["release-scorecard.py", "--check", "--target", "source", "--json"])
    return commands


def run_gates(scope: str) -> dict[str, Any]:
    results = []
    ok = True
    for command in validation_commands(scope):
        result = run_script(command, timeout=240)
        results.append({k: result[k] for k in ("cmd", "ok", "exit", "stdout", "stderr")})
        ok = ok and result["ok"]
    return {"ok": ok, "results": results}


def learner_eval_report(hypotheses: list[dict[str, Any]], patch: dict[str, Any], rollback: dict[str, Any], gates: dict[str, Any] | None) -> dict[str, Any]:
    no_op = any(op.get("operation") == "no_op" for op in (patch.get("operations") or []))
    evidence_supported = no_op or (bool(hypotheses) and all(int(h.get("evidence_count") or 0) >= 1 for h in hypotheses))
    minimal = len(patch.get("operations") or []) <= 8
    rollback_complete = bool(rollback.get("entries") is not None)
    validation_matches = not gates or isinstance(gates.get("ok"), bool)
    verdict = "pass" if evidence_supported and minimal and rollback_complete and validation_matches else "fail"
    return {
        "schema": "learner_eval_report.v1",
        "verdict": verdict,
        "evidence_supported": evidence_supported,
        "minimal_patch": minimal,
        "rollback_complete": rollback_complete,
        "validation_claim_matches": validation_matches,
        "risks": [
            "Autopilot changes are local and uncommitted.",
            "Source patches require rollback manifest integrity.",
        ],
        "created_at": utc_now(),
    }


def persist_run(run: dict[str, Any], patch: dict[str, Any], rollback: dict[str, Any]) -> dict[str, Any]:
    for directory in (runs_dir(), patches_dir(), rollbacks_dir()):
        directory.mkdir(parents=True, exist_ok=True)
    write_json(patch_path(run["id"]), patch)
    write_json(rollback_path(run["id"]), rollback)
    run["patch_path"] = str(patch_path(run["id"]))
    run["rollback_path"] = str(rollback_path(run["id"]))
    write_json(run_path(run["id"]), run)
    return run


def run_autopilot(args: argparse.Namespace) -> dict[str, Any]:
    run_id = sortable_id("improve")
    repo = Path(args.repo or ROOT).resolve()
    evidence = load_evidence(args.scope, args.days)
    hypotheses = derive_hypotheses(evidence, args.scope)[: args.max_hypotheses]
    candidate_results: list[dict[str, Any]] = []
    rollback_entries: list[dict[str, Any]] = []
    gate_results: dict[str, Any] = {}
    status = "dry_run" if hypotheses else "no_op"
    if args.mode != "dry-run" and hypotheses:
        for hypothesis in hypotheses:
            candidate_results.append(materialize_learning_candidate(hypothesis, run_id))
        route_rollback = apply_route_overlay(run_id, hypotheses, promote=args.mode == "autopilot")
        rollback_entries.append(route_rollback)
        source_changes: list[dict[str, Any]] = []
        for hypothesis in hypotheses:
            source_changes.extend(hypothesis.get("source_changes") or [])
        if source_changes:
            rollback_entries.extend(apply_source_changes(run_id, repo, source_changes))
        gate_results = run_gates(args.scope)
        status = "applied" if args.mode == "autopilot" and gate_results.get("ok") else "canary"
        if not gate_results.get("ok"):
            rollback_from_manifest({"entries": rollback_entries})
            status = "needs_evidence"
    patch = build_patch_manifest(run_id, hypotheses, candidate_results)
    rollback = {
        "schema": "rollback_manifest.v1",
        "id": f"{run_id}-rollback",
        "run_id": run_id,
        "created_at": utc_now(),
        "entries": rollback_entries,
    }
    learner_eval = learner_eval_report(hypotheses, patch, rollback, gate_results)
    if learner_eval["verdict"] != "pass" and status == "applied":
        rollback_from_manifest(rollback)
        status = "needs_evidence"
    run = {
        "schema": "self_improvement_run.v1",
        "id": run_id,
        "mode": args.mode,
        "scope": args.scope,
        "status": status,
        "repo": str(repo),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "evidence": evidence,
        "hypotheses": hypotheses,
        "candidates": candidate_results,
        "gate_results": gate_results or {},
        "learner_eval": learner_eval,
        "patch_hash": patch.get("patch_hash"),
        "touched_files": [entry.get("path") for entry in rollback_entries if entry.get("kind") == "source_file"],
        "post_apply_monitor": {
            "status": "pending_live_evidence" if status == "applied" else "not_started",
            "recommended_command": "python3 scripts/audit-invocation-telemetry.py --json --days 14",
        },
    }
    persist_run(run, patch, rollback)
    return command_result(True, run=run, patch=patch, rollback=rollback)


def list_runs(limit: int) -> dict[str, Any]:
    rows = []
    for path in sorted(runs_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        rows.append(read_json(path, {"path": str(path)}))
    return command_result(True, count=len(rows), runs=rows, path=str(runs_dir()))


def latest_run() -> dict[str, Any]:
    runs = list_runs(1)
    latest = (runs.get("runs") or [None])[0]
    return command_result(bool(latest), run=latest, path=str(runs_dir()))


def rollback_run(run_id: str) -> dict[str, Any]:
    path = rollback_path(run_id)
    if not path.exists():
        return command_result(False, error="unknown_self_improvement_run", run_id=run_id, path=str(path))
    manifest = read_json(path, {})
    result = rollback_from_manifest(manifest)
    run = read_json(run_path(run_id), {})
    if run:
        run = {**run, "status": "rolled_back", "rolled_back_at": utc_now(), "rollback_result": result}
        write_json(run_path(run_id), run)
    return command_result(True, run_id=run_id, rollback=result, run=run)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--mode", choices=sorted(MODES), default="dry-run")
    run.add_argument("--scope", choices=sorted(SCOPES), default="all")
    run.add_argument("--repo", default=str(ROOT))
    run.add_argument("--days", type=int, default=14)
    run.add_argument("--max-hypotheses", type=int, default=6)
    rb = sub.add_parser("rollback")
    rb.add_argument("run_id")
    ls = sub.add_parser("list")
    ls.add_argument("--limit", type=int, default=20)
    sub.add_parser("latest")

    args = parser.parse_args()
    try:
        if args.cmd == "run":
            print_json(run_autopilot(args))
        elif args.cmd == "rollback":
            result = rollback_run(args.run_id)
            print_json(result)
            return 0 if result.get("ok") else 1
        elif args.cmd == "list":
            print_json(list_runs(args.limit))
        elif args.cmd == "latest":
            result = latest_run()
            print_json(result)
            return 0 if result.get("ok") else 1
    except Exception as exc:
        print_json(command_result(False, error=str(exc)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
