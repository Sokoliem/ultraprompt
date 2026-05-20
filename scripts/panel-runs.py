#!/usr/bin/env python3
"""V8.2 panel run lifecycle ledger.

Stores resumable panel run state at:
  ~/.ultraprompt/panels/<repo>/<panel-name>-runs.jsonl

Latest record per run_id is the current state; append-only history is retained.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VALID_STATUSES = {"planned", "running", "completed", "cancelled", "failed"}
PANEL_SMOKE_FIXTURES = {
    "experience-quality-panel": {
        "artifact_type": "experience_quality_report",
        "fixture": ROOT / "tests" / "artifacts" / "experience_quality_report.valid.json",
    }
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def git_value(args: list[str], cwd: Path) -> str | None:
    try:
        proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            return proc.stdout.strip() or None
    except Exception:
        return None
    return None


def default_repo(worktree: Path) -> tuple[str, str | None, str | None, int]:
    repo_root = git_value(["rev-parse", "--show-toplevel"], worktree)
    repo_name = Path(repo_root).name if repo_root else worktree.resolve().name
    git_head = git_value(["rev-parse", "HEAD"], Path(repo_root) if repo_root else worktree)
    dirty = 0
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=Path(repo_root) if repo_root else worktree,
            capture_output=True,
            text=True,
            timeout=5,
        )
        dirty = len([line for line in proc.stdout.splitlines() if line.strip()])
    except Exception:
        pass
    return repo_name, repo_root, git_head, dirty


def run_id(panel_name: str, repo: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"panel-{repo}-{panel_name}-{stamp}-{int(time.time() * 1000) % 10000:04d}"


def panel_dir(repo: str | None = None) -> Path:
    base = Path.home() / ".ultraprompt" / "panels"
    if repo:
        base = base / repo
    base.mkdir(parents=True, exist_ok=True)
    return base


def ledger_path(repo: str, panel_name: str) -> Path:
    return panel_dir(repo) / f"{panel_name}-runs.jsonl"


def read_records(repo: str | None = None, panel_name: str | None = None) -> list[dict[str, Any]]:
    if repo and panel_name:
        paths = [ledger_path(repo, panel_name)]
    elif repo:
        paths = list(panel_dir(repo).glob("*-runs.jsonl"))
    else:
        paths = list(panel_dir().glob("*/*-runs.jsonl"))
    out: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                out.append(item)
    out.sort(key=lambda item: item.get("updated_at") or item.get("started_at") or "")
    return out


def latest_runs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        rid = record.get("run_id")
        if rid:
            by_id[rid] = record
    return sorted(by_id.values(), key=lambda item: item.get("updated_at") or item.get("started_at") or "", reverse=True)


def append_record(record: dict[str, Any]) -> dict[str, Any]:
    path = ledger_path(record["repo"], record["panel_name"])
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")
    return record


def start_run(panel_name: str, scope: str, repo: str | None, worktree: Path) -> dict[str, Any]:
    repo_name, repo_root, git_head, dirty_count = default_repo(worktree)
    repo = repo or repo_name
    ts = now_iso()
    record = {
        "schema": "panel_run.v1",
        "run_id": run_id(panel_name, repo),
        "repo": repo,
        "repo_root": repo_root,
        "git_head": git_head,
        "worktree_dirty_count": dirty_count,
        "requested_scope": scope,
        "panel_name": panel_name,
        "started_at": ts,
        "updated_at": ts,
        "completed_at": None,
        "status": "running",
        "phase_statuses": {},
        "agents": [],
        "artifact_paths": [],
        "validation_summary": [],
    }
    return append_record(record)


def update_run(run_id_value: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    records = read_records()
    latest = next((item for item in latest_runs(records) if item.get("run_id") == run_id_value), None)
    if not latest:
        return None
    status = updates.get("status", latest.get("status"))
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
    record = dict(latest)
    record.update({k: v for k, v in updates.items() if v not in (None, "")})
    record["status"] = status
    record["updated_at"] = now_iso()
    if status in {"completed", "cancelled", "failed"} and not record.get("completed_at"):
        record["completed_at"] = record["updated_at"]
    return append_record(record)


def list_runs(repo: str | None, panel_name: str | None, status: str | None, limit: int, history: bool) -> list[dict[str, Any]]:
    records = read_records(repo=repo, panel_name=panel_name)
    runs = records if history else latest_runs(records)
    if status:
        runs = [item for item in runs if item.get("status") == status]
    return runs[:limit]


def stats() -> dict[str, Any]:
    runs = latest_runs(read_records())
    by_status: dict[str, int] = {}
    by_panel: dict[str, int] = {}
    for run in runs:
        by_status[run.get("status", "unknown")] = by_status.get(run.get("status", "unknown"), 0) + 1
        by_panel[run.get("panel_name", "unknown")] = by_panel.get(run.get("panel_name", "unknown"), 0) + 1
    return {"total_runs": len(runs), "by_status": by_status, "by_panel": by_panel}


def load_artifact_validator():
    path = ROOT / "scripts" / "artifact-validate.py"
    spec = importlib.util.spec_from_file_location("artifact_validate", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def smoke(panel_name: str, fixture: str | None = None) -> dict[str, Any]:
    config = PANEL_SMOKE_FIXTURES.get(panel_name)
    if not config:
        return {
            "ok": False,
            "panel": panel_name,
            "error": "no_smoke_fixture_configured",
            "available": sorted(PANEL_SMOKE_FIXTURES),
        }
    fixture_path = Path(fixture).expanduser() if fixture else config["fixture"]
    if not fixture_path.is_absolute():
        fixture_path = ROOT / fixture_path
    validator = load_artifact_validator()
    data, err = validator.load_artifact(fixture_path)
    if err:
        return {
            "ok": False,
            "panel": panel_name,
            "fixture_or_run_id": str(fixture_path),
            "artifact_type": config["artifact_type"],
            "validator": "artifact-validate.py",
            "status": "failed",
            "findings": [{"severity": "high", "issue": err}],
            "recorded_at": now_iso(),
        }
    result = validator.validate(str(config["artifact_type"]), data)
    return {
        "ok": bool(result.get("ok")),
        "panel": panel_name,
        "proof_kind": "fixture",
        "live_adoption": False,
        "fixture_or_run_id": str(fixture_path.relative_to(ROOT) if fixture_path.is_relative_to(ROOT) else fixture_path),
        "artifact_type": config["artifact_type"],
        "validator": "artifact-validate.py",
        "status": "passed" if result.get("ok") else "failed",
        "findings": result.get("high", []) + result.get("medium", []),
        "recorded_at": now_iso(),
    }


def resolve_artifact_path(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


def proof(panel_name: str) -> dict[str, Any]:
    config = PANEL_SMOKE_FIXTURES.get(panel_name)
    if not config:
        return {
            "ok": False,
            "panel": panel_name,
            "proof_kind": "live",
            "live_adoption": False,
            "error": "no_smoke_fixture_configured",
            "available": sorted(PANEL_SMOKE_FIXTURES),
        }
    runs = [
        run for run in latest_runs(read_records())
        if run.get("panel_name") == panel_name and run.get("status") == "completed"
    ]
    validator = load_artifact_validator()
    findings: list[dict[str, Any]] = []
    for run in runs:
        for artifact in run.get("artifact_paths") or []:
            artifact_path = resolve_artifact_path(str(artifact))
            if not artifact_path.exists():
                findings.append({
                    "severity": "high",
                    "issue": "panel artifact path does not exist",
                    "artifact_path": str(artifact_path),
                    "run_id": run.get("run_id"),
                })
                continue
            data, err = validator.load_artifact(artifact_path)
            if err:
                findings.append({
                    "severity": "high",
                    "issue": err,
                    "artifact_path": str(artifact_path),
                    "run_id": run.get("run_id"),
                })
                continue
            result = validator.validate(str(config["artifact_type"]), data)
            if result.get("ok"):
                return {
                    "ok": True,
                    "panel": panel_name,
                    "proof_kind": "live",
                    "live_adoption": True,
                    "fixture_or_run_id": run.get("run_id"),
                    "run_id": run.get("run_id"),
                    "repo": run.get("repo"),
                    "artifact_path": str(artifact_path.relative_to(ROOT) if artifact_path.is_relative_to(ROOT) else artifact_path),
                    "artifact_type": config["artifact_type"],
                    "validator": "artifact-validate.py",
                    "status": "passed",
                    "findings": result.get("high", []) + result.get("medium", []),
                    "recorded_at": now_iso(),
                    "completed_at": run.get("completed_at"),
                    "validation_summary": run.get("validation_summary") or [],
                }
            findings.extend(result.get("high", []) + result.get("medium", []))
    return {
        "ok": False,
        "panel": panel_name,
        "proof_kind": "live",
        "live_adoption": False,
        "status": "missing_live_proof",
        "findings": findings[:10],
        "completed_runs": len(runs),
        "recorded_at": now_iso(),
    }


def parse_json_arg(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    s_start = sub.add_parser("start")
    s_start.add_argument("--panel", required=True)
    s_start.add_argument("--scope", default="")
    s_start.add_argument("--repo")
    s_start.add_argument("--worktree", default=".")

    s_update = sub.add_parser("update")
    s_update.add_argument("run_id")
    s_update.add_argument("--status", choices=sorted(VALID_STATUSES))
    s_update.add_argument("--phase")
    s_update.add_argument("--phase-status")
    s_update.add_argument("--agent")
    s_update.add_argument("--artifact-path")
    s_update.add_argument("--validation", help="JSON validation summary item")

    s_list = sub.add_parser("list")
    s_list.add_argument("--repo")
    s_list.add_argument("--panel")
    s_list.add_argument("--status")
    s_list.add_argument("--history", action="store_true")
    s_list.add_argument("--limit", type=int, default=20)

    sub.add_parser("stats")
    s_smoke = sub.add_parser("smoke")
    s_smoke.add_argument("--panel", required=True)
    s_smoke.add_argument("--fixture")
    s_proof = sub.add_parser("proof")
    s_proof.add_argument("--panel", required=True)

    args = parser.parse_args()
    if args.cmd == "start":
        record = start_run(args.panel, args.scope, args.repo, Path(args.worktree).resolve())
        print(json.dumps({"ok": True, "run": record}, indent=2, default=str))
        return 0
    if args.cmd == "update":
        updates: dict[str, Any] = {}
        if args.status:
            updates["status"] = args.status
        latest = next((item for item in latest_runs(read_records()) if item.get("run_id") == args.run_id), {})
        if args.phase:
            phases = dict(latest.get("phase_statuses") or {})
            phases[args.phase] = args.phase_status or args.status or "running"
            updates["phase_statuses"] = phases
        if args.agent:
            updates["agents"] = sorted(set((latest.get("agents") or []) + [args.agent]))
        if args.artifact_path:
            updates["artifact_paths"] = sorted(set((latest.get("artifact_paths") or []) + [args.artifact_path]))
        if args.validation:
            validations = list(latest.get("validation_summary") or [])
            validations.append(parse_json_arg(args.validation, {"raw": args.validation}))
            updates["validation_summary"] = validations
        record = update_run(args.run_id, updates)
        print(json.dumps({"ok": record is not None, "run": record}, indent=2, default=str))
        return 0 if record else 1
    if args.cmd == "list":
        runs = list_runs(args.repo, args.panel, args.status, args.limit, args.history)
        print(json.dumps({"ok": True, "count": len(runs), "mode": "history" if args.history else "latest", "runs": runs}, indent=2, default=str))
        return 0
    if args.cmd == "stats":
        print(json.dumps({"ok": True, **stats()}, indent=2))
        return 0
    if args.cmd == "smoke":
        result = smoke(args.panel, args.fixture)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("ok") else 1
    if args.cmd == "proof":
        result = proof(args.panel)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("ok") else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
