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

KINDS = {"route_update", "benchmark_candidate", "memory_promotion", "catalog_proposal", "panel_proposal", "retrieval_hint"}
STATUSES = {"pending", "approved", "rejected", "applied", "reverted", "expired", "needs_evidence"}
LOW_RISK = {"route_update", "benchmark_candidate", "memory_promotion", "retrieval_hint"}


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
    }
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
        [sys.executable, "scripts/run-pathfinder-tests.py"],
        [sys.executable, "scripts/run-router-bench.py"],
    ]
    results = []
    ok = True
    root = Path(__file__).resolve().parents[1]
    for cmd in commands:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=120)
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
    if candidate.get("status") != "approved" and not args.force:
        raise ValueError("candidate_must_be_approved")
    if candidate.get("risk") == "high" and not args.force:
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
        raise ValueError(f"unknown candidate: {args.candidate_id}")
    rollback = candidate.get("rollback") or {}
    if rollback.get("kind") == "route_policy":
        write_json(policy_path(), rollback.get("before") or {"schema": "route_policy.v1", "routes": []})
    candidate = {**candidate, "status": "reverted", "reverted_at": utc_now()}
    persist("revert", candidate)
    emit_cognitive_event("learning_candidate_reverted", {"candidate_id": candidate["id"], "kind": candidate["kind"]})
    return command_result(True, candidate=candidate)


def list_candidates(args: argparse.Namespace) -> dict[str, Any]:
    rows = list(latest_candidates().values())
    if args.status:
        rows = [c for c in rows if c.get("status") == args.status]
    if args.kind:
        rows = [c for c in rows if c.get("kind") == args.kind]
    rows.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
    return command_result(True, count=len(rows[: args.limit]), candidates=rows[: args.limit], path=str(queue_path()))


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

    list_p = sub.add_parser("list")
    list_p.add_argument("--status", choices=sorted(STATUSES), default="")
    list_p.add_argument("--kind", choices=sorted(KINDS), default="")
    list_p.add_argument("--limit", type=int, default=100)

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
