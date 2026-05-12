#!/usr/bin/env python3
"""V8: Mission Control state model (PRD §9.2).

Reads from existing state stores and produces a unified mission_state view:
- repo capsule (scripts/repo-capsule.py)
- worktree state (scripts/worktree-state.py)
- session lookup (scripts/session-lookup.py)
- evidence ledger v2 (scripts/ledger-v2.py)
- validation status
- WIP snapshots
- gap ledger (scripts/gap-ledger.py)

Output schema: PRD §10.1 mission_state (mission-state.yaml or .json).

Subcommands:
  mission-state.py snapshot         # produce current snapshot
  mission-state.py path             # show state file path
  mission-state.py history [--n 5]  # show recent snapshots
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _imp(name, path):
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    except Exception:
        return None


def _safe_call(callable_name, *args, **kwargs):
    """Call a function safely, return None on failure."""
    try:
        return callable_name(*args, **kwargs)
    except Exception:
        return None


def _detect_runtime() -> dict:
    """Detect Claude Code vs Codex by environment variables."""
    runtime = "unknown"
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_SESSION"):
        runtime = "claude"
    elif os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_VERSION"):
        runtime = "codex"

    # Plugin manifest
    claude_manifest = ROOT / ".claude-plugin" / "plugin.json"
    codex_manifest = ROOT / ".codex-plugin" / "plugin.json"
    version = "unknown"
    try:
        if claude_manifest.exists():
            d = json.load(open(claude_manifest))
            version = d.get("version", "unknown")
    except Exception:
        pass

    return {
        "name": runtime,
        "plugin_version": version,
        "claude_manifest_present": claude_manifest.exists(),
        "codex_manifest_present": codex_manifest.exists(),
        "hooks_available": (ROOT / "hooks").exists(),
        "mcp_available": (ROOT / "mcp").exists(),
    }


def _get_repo_state(worktree: Path) -> dict:
    """Get repo + worktree state."""
    ws = _imp("ws", ROOT / "scripts" / "worktree-state.py")
    if ws is None:
        return {"error": "worktree-state module unavailable"}
    state = _safe_call(ws.worktree_state, worktree) or {}
    repo_root = _safe_call(ws.find_repo_root, worktree)
    repo_name = _safe_call(ws.repo_name, repo_root) if repo_root else None
    return {
        "repo": {
            "root": str(repo_root) if repo_root else None,
            "name": repo_name,
            "git_head": state.get("head"),
            "branch": state.get("branch"),
            "in_progress_op": state.get("in_progress"),
        },
        "worktree": {
            "path": str(worktree),
            "exists": state.get("exists", False),
            "dirty_count": state.get("dirty_count", 0),
            "untracked_count": state.get("untracked_count", 0),
            "staged_count": state.get("staged_count", 0),
            "stash_count": state.get("stash_count", 0),
            "unpushed_count": state.get("unpushed_count", 0),
        },
    }


def _get_sessions(worktree: Path) -> dict:
    """Get active sessions via worktree-state.find_active_sessions."""
    ws = _imp("ws", ROOT / "scripts" / "worktree-state.py")
    if ws is None:
        return {"active_count": 0, "active": [], "error": "worktree-state unavailable"}
    try:
        sessions = _safe_call(ws.find_active_sessions, worktree, 15) or []
        return {"active_count": len(sessions), "active": sessions[:10]}
    except Exception as e:
        return {"active_count": 0, "active": [], "error": str(e)}


def _get_evidence_summary() -> dict:
    """Summary from ledger v2."""
    led = _imp("led", ROOT / "scripts" / "ledger-v2.py")
    if led is None:
        return {"error": "ledger-v2 unavailable"}
    try:
        recent = _safe_call(led.read_events, days=1) or []
        events_24h = len(recent)
        # Categorize
        by_type = {}
        for e in recent:
            t = e.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "events_24h": events_24h,
            "by_type_24h": dict(sorted(by_type.items(), key=lambda x: -x[1])[:10]),
            "ledger_path_exists": (Path.home() / ".claude" / "ultraprompt-data").exists(),
        }
    except Exception as e:
        return {"error": str(e)}


def _get_wip_snapshots(repo_name: str | None) -> dict:
    """Recent WIP snapshots — query git for wip/<repo>/* branches."""
    if not repo_name:
        return {"recent_count": 0, "branches": []}
    cwd = ROOT
    try:
        r = subprocess.run(
            ["git", "branch", "--list", f"wip/{repo_name}/*"],
            cwd=cwd, capture_output=True, text=True, timeout=5
        )
        branches = [b.strip() for b in r.stdout.splitlines() if b.strip()]
        return {
            "recent_count": len(branches),
            "branches": branches[-5:],  # most recent 5
            "implementation": "verified",
        }
    except Exception:
        return {"recent_count": 0, "branches": []}


def _get_gap_ledger_summary() -> dict:
    """Summary from gap-ledger."""
    gl = _imp("gl", ROOT / "scripts" / "gap-ledger.py")
    if gl is None:
        return {"error": "gap-ledger unavailable"}
    try:
        stats = _safe_call(gl.stats) or {}
        return {
            "total_gap_ids": stats.get("total_gap_ids", 0),
            "open": stats.get("by_status", {}).get("open", 0),
            "critical": stats.get("by_severity", {}).get("critical", 0),
            "high": stats.get("by_severity", {}).get("high", 0),
            "by_repo": stats.get("by_repo", {}),
        }
    except Exception as e:
        return {"error": str(e)}


def _get_panel_runs(repo_name: str | None) -> dict:
    """Recent panel lifecycle state."""
    try:
        cmd = [sys.executable, str(ROOT / "scripts" / "panel-runs.py"), "list", "--limit", "10"]
        if repo_name:
            cmd.extend(["--repo", repo_name])
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=10)
        data = json.loads(proc.stdout)
        stats_proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "panel-runs.py"), "stats"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        stats = json.loads(stats_proc.stdout)
        return {
            "recent": data.get("runs", []),
            "recent_count": data.get("count", 0),
            "stats": stats,
        }
    except Exception as e:
        return {"recent": [], "recent_count": 0, "error": str(e)}


def _read_cached_release_scorecard() -> dict | None:
    """Read the generated scorecard for dashboard-fast mission snapshots."""
    scorecard_path = ROOT / "dist" / "release-scorecard.json"
    if not scorecard_path.exists():
        return None
    try:
        data = json.load(open(scorecard_path))
        scorecard = data.get("release_scorecard", data)
        return {
            "ok": scorecard.get("conclusion") != "blocked",
            "conclusion": scorecard.get("conclusion"),
            "blockers": scorecard.get("blockers", []),
            "warnings": scorecard.get("warnings", []),
            "runtime_targets": scorecard.get("runtime_targets", {}),
            "source": "dist/release-scorecard.json",
            "cached": True,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "source": "dist/release-scorecard.json", "cached": True}


def _get_runtime_readiness(fast: bool = False) -> dict:
    """Release scorecard target snapshot without writing dist artifacts."""
    if fast:
        cached = _read_cached_release_scorecard()
        if cached is not None:
            return cached

    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "release-scorecard.py"), "--check", "--json", "--target", "source"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        data = json.loads(proc.stdout)
        scorecard = data.get("release_scorecard", data)
        return {
            "ok": proc.returncode == 0 and scorecard.get("conclusion") != "blocked",
            "conclusion": scorecard.get("conclusion"),
            "blockers": scorecard.get("blockers", []),
            "warnings": scorecard.get("warnings", []),
            "runtime_targets": scorecard.get("runtime_targets", {}),
            "source": "release-scorecard.py --check --json --target source",
            "cached": False,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "cached": False}


def _get_panels() -> dict:
    """Read panel catalog from source/panel-specs.json."""
    panels_path = ROOT / "source" / "panel-specs.json"
    if not panels_path.exists():
        return {"available": [], "specs_path": "source/panel-specs.json", "error": "panel-specs.json not found"}
    try:
        panels = json.load(open(panels_path))
        return {
            "available": [p["name"] for p in panels],
            "specs_path": "source/panel-specs.json",
            "count": len(panels),
            "summary": [
                {"name": p["name"], "agents": sum(len(ph["agents"]) for ph in p["phases"]),
                 "cost": p.get("estimated_cost"), "time_min": p.get("estimated_time_minutes"),
                 "mode": p.get("mode"), "risk": p.get("risk"),
                 "confirmation_required": (p.get("confirmation") or {}).get("required", False),
                 "pathfinder_tags": p.get("pathfinder_tags", [])}
                for p in panels
            ],
        }
    except Exception as e:
        return {"available": [], "error": str(e)}


def snapshot(worktree: Path | None = None, fast: bool = False) -> dict:
    """Produce a current Mission Control state snapshot."""
    worktree = (worktree or Path.cwd()).resolve()
    runtime_info = _detect_runtime()
    repo_state = _get_repo_state(worktree)
    repo_name = repo_state.get("repo", {}).get("name")

    state = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime": runtime_info,
        "repo": repo_state.get("repo", {}),
        "worktree": repo_state.get("worktree", {}),
        "sessions": _get_sessions(worktree),
        "evidence": _get_evidence_summary(),
        "recovery": {
            "wip_snapshots": _get_wip_snapshots(repo_name),
        },
        "gaps": _get_gap_ledger_summary(),
        "panel_runs": _get_panel_runs(repo_name),
        "runtime_readiness": _get_runtime_readiness(fast=fast),
        "panels": _get_panels(),
    }
    return state


def write_snapshot(state: dict) -> Path:
    """Persist snapshot to ~/.ultraprompt/state/mission-state.json."""
    state_dir = Path.home() / ".ultraprompt" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    p = state_dir / "mission-state.json"
    json.dump(state, open(p, "w"), indent=2, default=str)

    # Also append to history
    history = state_dir / "mission-state-history.jsonl"
    with open(history, "a") as f:
        f.write(json.dumps(state, default=str) + "\n")
    return p


def history(n: int = 5) -> list[dict]:
    """Recent mission state snapshots."""
    history = Path.home() / ".ultraprompt" / "state" / "mission-state-history.jsonl"
    if not history.exists():
        return []
    lines = history.read_text().splitlines()
    out = []
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s_snap = sub.add_parser("snapshot")
    s_snap.add_argument("--worktree", default=None)
    s_snap.add_argument("--write", action="store_true", help="Persist to ~/.ultraprompt/state/")
    s_snap.add_argument("--fast", action="store_true", help="Use generated release-scorecard cache for dashboard latency.")
    sub.add_parser("path")
    s_hist = sub.add_parser("history")
    s_hist.add_argument("--n", type=int, default=5)

    args = ap.parse_args()

    if args.cmd == "path":
        print(Path.home() / ".ultraprompt" / "state" / "mission-state.json")
        return 0

    if args.cmd == "history":
        h = history(args.n)
        print(json.dumps({"count": len(h), "snapshots": h}, indent=2, default=str))
        return 0

    if args.cmd == "snapshot":
        wt = Path(args.worktree).resolve() if args.worktree else Path.cwd()
        state = snapshot(wt, fast=args.fast)
        if args.write:
            p = write_snapshot(state)
            state["_persisted_to"] = str(p)
        print(json.dumps(state, indent=2, default=str))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
