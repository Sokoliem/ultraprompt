#!/usr/bin/env python3
"""V8: Gap-ledger persistent storage (PRD §10.5).

Stores structured gap findings from repo-completeness auditors at:
  ~/.ultraprompt/gaps/<repo>/gap-ledger.jsonl

Schema (one JSON object per line):
  {
    "v": 1,
    "ts": <unix timestamp>,
    "id": "GAP-<repo>-<seq>",
    "repo": "<repo name>",
    "worktree": "<worktree path>",
    "session_id": "<originating session>",
    "category": "incomplete_feature|wiring_gap|contract_mismatch|missing_test|"
                "release_blocker|stale_code|documentation_drift|dead_code|"
                "observability_gap|configuration_gap",
    "severity": "critical|high|medium|low",
    "confidence": "confirmed|likely|possible",
    "title": "<short summary>",
    "affected_area": "<file or feature>",
    "evidence": {"files": [...], "commands": [...], "symbols": [...]},
    "expected_behavior": "...",
    "actual_behavior": "...",
    "user_or_system_impact": "...",
    "recommended_fix": "...",
    "validation_plan": "...",
    "suggested_owner_agent": "ultraprompt:<agent>",
    "suggested_skill": "<skill name>",
    "status": "open|accepted|fixed|false_positive|deferred",
    "auditor": "<agent name that produced it>",
  }

Usage:
  gap-ledger.py write <gap.json>          # write one gap
  gap-ledger.py write-batch <gaps.json>   # write N gaps from a list
  gap-ledger.py list [--repo X] [--status open] [--severity critical]
  gap-ledger.py update <gap_id> <field=value>...
  gap-ledger.py path                      # show ledger path
  gap-ledger.py stats                     # summary
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALID_STATUSES = {"open", "accepted", "in_progress", "fixed", "validated", "false_positive", "deferred"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


def fingerprint_for_gap(gap: dict) -> str:
    material = {
        "repo": normalize_text(gap.get("repo", "unknown")),
        "category": normalize_text(gap.get("category", "")),
        "affected_area": normalize_text(gap.get("affected_area", "")),
        "title": normalize_text(gap.get("title", "")),
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return "gap_" + digest[:16]


def validate_gap(gap: dict) -> dict:
    """Validate a gap entry against the shared artifact contract before write."""
    validator_path = ROOT / "scripts" / "artifact-validate.py"
    spec = importlib.util.spec_from_file_location("artifact_validate", validator_path)
    if spec is None or spec.loader is None:
        return {"ok": False, "error": f"could not load validator: {validator_path}"}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate("gap_ledger_entry", gap)


def ledger_dir(repo_name: str | None = None) -> Path:
    base = Path.home() / ".ultraprompt" / "gaps"
    if repo_name:
        base = base / repo_name
    base.mkdir(parents=True, exist_ok=True)
    return base


def ledger_path(repo_name: str | None) -> Path:
    return ledger_dir(repo_name) / "gap-ledger.jsonl"


def next_id(repo_name: str) -> str:
    """Generate next sequential gap ID for the repo."""
    p = ledger_path(repo_name)
    seq = 0
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                if e.get("repo") == repo_name:
                    parts = e.get("id", "").rsplit("-", 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        seq = max(seq, int(parts[1]))
            except Exception:
                continue
    return f"GAP-{repo_name}-{seq + 1:04d}"


def write_gap(gap: dict) -> dict:
    """Write a single gap entry. Returns the written record with ID assigned."""
    validation = validate_gap(gap)
    if not validation.get("ok"):
        raise ValueError(json.dumps(validation, default=str))
    repo = gap.get("repo", "unknown")
    status = gap.get("status", "open")
    if status not in VALID_STATUSES:
        raise ValueError(json.dumps({"ok": False, "error": "invalid_status", "allowed": sorted(VALID_STATUSES)}))
    fingerprint = gap.get("fingerprint") or fingerprint_for_gap(gap)
    prior = list_gaps(repo=repo, fingerprint=fingerprint, history=False, limit=1)
    previous = prior[0] if prior else {}
    ts_iso = now_iso()
    owner_agent = gap.get("owner_agent") or gap.get("suggested_owner_agent")
    fix_skill = gap.get("fix_skill") or gap.get("suggested_skill")
    status_history = list(previous.get("status_history", []))
    previous_status = previous.get("status")
    if previous_status != status:
        status_history.append({
            "from": previous_status,
            "to": status,
            "at": ts_iso,
            "reason": gap.get("status_reason") or gap.get("reason") or "gap write",
        })
    record = {
        "v": 1,
        "ts": int(time.time()),
        "id": gap.get("id") or previous.get("id") or next_id(repo),
        "fingerprint": fingerprint,
        "status": status,
        "first_seen_at": previous.get("first_seen_at") or ts_iso,
        "last_seen_at": ts_iso,
        "owner_agent": owner_agent,
        "fix_skill": fix_skill,
        "status_history": status_history,
        "panel_run_ids": sorted(set((previous.get("panel_run_ids") or []) + (gap.get("panel_run_ids") or []))),
        **{k: v for k, v in gap.items() if k not in (
            "v", "ts", "id", "status", "fingerprint", "first_seen_at", "last_seen_at",
            "owner_agent", "fix_skill", "status_history", "panel_run_ids", "next_action",
        )},
    }
    record["next_action"] = gap.get("next_action") or gap.get("recommended_fix") or gap.get("validation_plan")
    p = ledger_path(repo)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
    return record


def list_gaps(repo: str | None = None, status: str | None = None,
              severity: str | None = None, limit: int = 100,
              *, fingerprint: str | None = None, history: bool = False) -> list[dict]:
    results = []
    p = ledger_path(repo) if repo else None
    paths = [p] if p and p.exists() else list(ledger_dir().rglob("gap-ledger.jsonl"))
    for path in paths:
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if fingerprint and e.get("fingerprint") != fingerprint:
                    continue
                if status and e.get("status") != status:
                    continue
                if severity and e.get("severity") != severity:
                    continue
                results.append(e)
        except Exception:
            continue
    results.sort(key=lambda e: (e.get("ts", 0), e.get("last_seen_at", "")))
    if history:
        return results[-limit:]
    by_fingerprint: dict[str, dict] = {}
    for entry in results:
        key = entry.get("fingerprint") or entry.get("id")
        if key:
            by_fingerprint[key] = entry
    return sorted(by_fingerprint.values(), key=lambda e: e.get("ts", 0), reverse=True)[:limit]


def update_gap(gap_id: str, updates: dict) -> dict | None:
    """Update a gap by appending a new record with same ID and updated fields.
    Latest record per ID wins on read."""
    matches = [e for e in list_gaps(limit=10000, history=True) if e.get("id") == gap_id]
    if not matches:
        return None
    latest = matches[-1]
    repo = latest.get("repo", "unknown")
    if "status" in updates and updates["status"] not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
    status_history = list(latest.get("status_history", []))
    if "status" in updates and updates["status"] != latest.get("status"):
        status_history.append({
            "from": latest.get("status"),
            "to": updates["status"],
            "at": now_iso(),
            "reason": updates.get("reason") or "manual update",
        })
    new_record = {
        **latest,
        **updates,
        "ts": int(time.time()),
        "last_seen_at": now_iso(),
        "status_history": status_history,
    }
    with open(ledger_path(repo), "a", encoding="utf-8") as f:
        f.write(json.dumps(new_record, default=str) + "\n")
    return new_record


def stats() -> dict:
    """Summary across all repos."""
    all_gaps = list_gaps(limit=10000, history=True)
    # Latest record per ID wins
    by_id = {}
    for e in all_gaps:
        by_id[e.get("id")] = e

    summary = {
        "total_gap_ids": len(by_id),
        "by_status": {},
        "by_severity": {},
        "by_category": {},
        "by_repo": {},
        "by_auditor": {},
    }
    for e in by_id.values():
        for key in ["status", "severity", "category", "repo", "auditor"]:
            v = e.get(key, "unknown")
            d = summary[f"by_{key}"]
            d[v] = d.get(v, 0) + 1
    return summary


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub_write = sub.add_parser("write")
    sub_write.add_argument("file", help="JSON file with gap object")

    sub_batch = sub.add_parser("write-batch")
    sub_batch.add_argument("file", help="JSON file with list of gap objects")

    sub_list = sub.add_parser("list")
    sub_list.add_argument("--repo")
    sub_list.add_argument("--status")
    sub_list.add_argument("--severity")
    sub_list.add_argument("--fingerprint")
    sub_list.add_argument("--history", action="store_true", help="return append-only history instead of latest-by-fingerprint")
    sub_list.add_argument("--limit", type=int, default=50)

    sub_update = sub.add_parser("update")
    sub_update.add_argument("gap_id")
    sub_update.add_argument("kv", nargs="+", help="field=value pairs")

    sub.add_parser("path")
    sub.add_parser("stats")

    args = ap.parse_args()

    if args.cmd == "path":
        print(ledger_dir())
        return 0

    if args.cmd == "stats":
        print(json.dumps(stats(), indent=2))
        return 0

    if args.cmd == "write":
        gap = json.load(open(args.file))
        try:
            r = write_gap(gap)
        except ValueError as exc:
            print(json.dumps({"ok": False, "error": "invalid_gap", "details": json.loads(str(exc))}, indent=2))
            return 1
        print(json.dumps({"ok": True, "id": r["id"], "wrote_to": str(ledger_path(r.get("repo")))}, indent=2))
        return 0

    if args.cmd == "write-batch":
        gaps = json.load(open(args.file))
        ids = []
        for g in gaps:
            try:
                r = write_gap(g)
            except ValueError as exc:
                print(json.dumps({"ok": False, "error": "invalid_gap", "details": json.loads(str(exc))}, indent=2))
                return 1
            ids.append(r["id"])
        print(json.dumps({"ok": True, "count": len(ids), "ids": ids}, indent=2))
        return 0

    if args.cmd == "list":
        results = list_gaps(
            args.repo,
            args.status,
            args.severity,
            args.limit,
            fingerprint=args.fingerprint,
            history=args.history,
        )
        print(json.dumps({
            "count": len(results),
            "mode": "history" if args.history else "latest_by_fingerprint",
            "gaps": results,
        }, indent=2, default=str))
        return 0

    if args.cmd == "update":
        updates = {}
        for kv in args.kv:
            if "=" in kv:
                k, v = kv.split("=", 1)
                updates[k] = v
        r = update_gap(args.gap_id, updates)
        print(json.dumps({"ok": r is not None, "updated": r}, indent=2, default=str))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
