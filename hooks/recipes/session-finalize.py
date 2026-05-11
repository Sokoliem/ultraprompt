#!/usr/bin/env python3
"""V8 SessionEnd hook: final report + ledger session_end event."""
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
    if not (cfg and ws and led): return 0
    config = cfg.load_config()
    if not cfg.get(config, "hooks.session_finalize_enabled", True): return 0
    if not cfg.get(config, "ledger.enabled", True): return 0
    if ws.find_repo_root() is None: return 0
    cwd = Path.cwd().resolve()
    state = ws.worktree_state(cwd)
    repo_n = ws.repo_name(ws.find_repo_root())
    sid = os.environ.get("CLAUDE_SESSION_ID") or f"unknown-{int(time.time())}"
    start = None
    try:
        starts = led.read_events(days=2, event_types=["session_start"], worktree=str(cwd))
        for e in reversed(starts):
            if e.get("session_id") == sid: start = e; break
    except Exception: pass
    dur = 0; changed = 0
    if start:
        dur = max(0, int(time.time()) - start.get("ts", int(time.time())))
        sd = start.get("dirty", 0) + start.get("untracked", 0)
        ed = state.get("dirty_count", 0) + state.get("untracked_count", 0)
        changed = max(0, ed - sd)
    saves = claims = 0
    if start:
        try:
            since = start.get("ts", 0)
            saves = sum(1 for e in led.read_events(days=1, event_types=["wip_save"], worktree=str(cwd))
                       if e.get("ts", 0) >= since)
            claims = sum(1 for e in led.read_events(days=1, event_types=["claim_flagged"], worktree=str(cwd))
                        if e.get("ts", 0) >= since)
        except Exception: pass
    led.write_event("session_end", repo=repo_n, worktree=str(cwd), session_id=sid,
        runtime="claude-code", duration_sec=dur, files_changed=changed,
        wip_saves_made=saves, claims_flagged=claims,
        ended_dirty=state.get("dirty_count", 0) + state.get("untracked_count", 0),
        ended_unpushed=state.get("unpushed_count", 0), head_at_end=state.get("head"))
    end_dirty = state.get("dirty_count", 0) + state.get("untracked_count", 0)
    lines = ["ultraprompt session finalize"]
    if dur: lines.append(f"  duration: {dur//60}m{dur%60}s · files changed: {changed}")
    if saves: lines.append(f"  WIP saves made: {saves}")
    if claims: lines.append(f"  ⚠️  claims flagged: {claims}")
    if end_dirty:
        lines.append(f"  ⚠️  ended dirty: {end_dirty} files uncommitted")
        lines.append(f"  next session: /ultraprompt:resume to pick up")
    if len(lines) > 1:
        print(json.dumps({"systemMessage": "\n".join(lines)}))
    return 0


if __name__ == "__main__":
    try: sys.exit(main())
    except Exception: sys.exit(0)
