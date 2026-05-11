#!/usr/bin/env python3
"""V8 SessionStart hook: bootstrap banner + checkpoint snapshot."""
from __future__ import annotations
import importlib.util, json, os, sys, time
from pathlib import Path

PR = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))


def _imp(n, p):
    try:
        spec = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m); return m
    except Exception:
        return None


def main():
    if os.environ.get("ULTRAPROMPT_DISABLE_HOOKS") == "1": return 0
    try: sys.stdin.read()
    except Exception: pass
    cfg = _imp("cfg", PR / "scripts" / "config-loader.py")
    ws = _imp("ws", PR / "scripts" / "worktree-state.py")
    led = _imp("ledger_v2", PR / "scripts" / "ledger-v2.py")
    if not (cfg and ws): return 0
    config = cfg.load_config()
    if not cfg.get(config, "hooks.session_bootstrap_enabled", True): return 0
    if not cfg.get(config, "ledger.enabled", True): led = None
    repo_root = ws.find_repo_root()
    if repo_root is None: return 0
    cwd = Path.cwd().resolve()
    state = ws.worktree_state(cwd)
    repo_n = ws.repo_name(repo_root)
    sid = os.environ.get("CLAUDE_SESSION_ID") or f"unknown-{int(time.time())}"
    if led:
        led.write_event("session_start", repo=repo_n, worktree=str(cwd),
            branch=state.get("branch"), head=state.get("head"),
            dirty=state.get("dirty_count", 0), untracked=state.get("untracked_count", 0),
            stash=state.get("stash_count", 0), unpushed=state.get("unpushed_count", 0),
            in_progress=state.get("in_progress"), session_id=sid, runtime="claude-code")
    win = cfg.get(config, "session.active_window_minutes", 15)
    others = []
    try:
        sessions = ws.find_active_sessions(cwd, win)
        others = [s for s in sessions if s.get("session_id") != sid]
    except Exception: pass
    dirty = state.get("dirty_count", 0) + state.get("untracked_count", 0)
    unpushed = state.get("unpushed_count", 0)
    ip = state.get("in_progress")
    dt = cfg.get(config, "worktree.dirty_warn_count", 50)
    upt = cfg.get(config, "worktree.unpushed_warn_count", 5)
    warns = []
    if ip: warns.append(f"in-progress {ip} — complete or abort before continuing")
    if dirty >= dt: warns.append(f"{dirty} dirty files (threshold {dt})")
    if unpushed >= upt: warns.append(f"{unpushed} unpushed commits (threshold {upt})")
    if others: warns.append(f"{len(others)} concurrent session(s) active")
    if not warns: return 0
    branch = state.get("branch") or "(detached)"
    lines = [f"ultraprompt session bootstrap",
             f"  repo: {repo_n} · worktree: {cwd.name} · branch: {branch}"]
    for w in warns: lines.append(f"  ⚠️  {w}")
    lines.append(f"  run /ultraprompt:status for full picture")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                              "additionalContext": "\n".join(lines)}}))
    return 0


if __name__ == "__main__":
    try: sys.exit(main())
    except Exception: sys.exit(0)
