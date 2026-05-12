#!/usr/bin/env python3
"""V8 cross-worktree status dashboard."""
from __future__ import annotations
import argparse, importlib.util, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _imp(n, p):
    try:
        spec = importlib.util.spec_from_file_location(n, p)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
    except Exception:
        return None


_ws = _imp("ws", ROOT / "scripts" / "worktree-state.py")
_cfg = _imp("cfg", ROOT / "scripts" / "config-loader.py")


def reltime(ts):
    if ts is None:
        return "unknown"
    d = time.time() - ts
    if d < 60: return f"{int(d)}s ago"
    if d < 3600: return f"{int(d/60)}m ago"
    if d < 86400: return f"{int(d/3600)}h ago"
    return f"{int(d/86400)}d ago"


def urgency(state, config):
    reasons = []
    dirty_t = _cfg.get(config, "worktree.dirty_warn_count", 50)
    idle_s = _cfg.get(config, "worktree.idle_warn_hours", 24) * 3600
    stale_s = _cfg.get(config, "worktree.stale_warn_days", 14) * 86400
    unpushed_t = _cfg.get(config, "worktree.unpushed_warn_count", 5)
    if state.get("err"): return "error", [state["err"]]
    if state.get("in_progress"): return "critical", [f"in-progress {state['in_progress']}"]
    dirty = state.get("dirty_count", 0) + state.get("untracked_count", 0)
    unpushed = state.get("unpushed_count", 0)
    activity_ts = state.get("activity_ts") or 0
    age = time.time() - activity_ts if activity_ts else 0
    if dirty >= dirty_t: reasons.append(f"{dirty} dirty files")
    if unpushed >= unpushed_t: reasons.append(f"{unpushed} unpushed commits")
    if dirty > 0 and age > idle_s: reasons.append(f"dirty + idle {reltime(activity_ts)}")
    if state.get("detached") and age > stale_s: reasons.append(f"detached HEAD, {reltime(activity_ts)}")
    if reasons and (dirty >= dirty_t or unpushed >= unpushed_t): return "needs-triage", reasons
    if reasons: return "watch", reasons
    return "clean", []


def render_table(summary, config, sessions_per_wt):
    lines = [f"ULTRA-PROMPT STATUS — {summary.get('repo','?')} · scanned {reltime(summary.get('scanned_at'))}", ""]
    buckets = {"critical": [], "needs-triage": [], "in-flight": [], "watch": [], "clean": [], "error": []}
    for wt in summary.get("worktrees", []):
        sessions = sessions_per_wt.get(wt.get("path", ""), [])
        level, reasons = urgency(wt, config)
        if sessions and level in ("clean", "watch"): level = "in-flight"
        wt["_urgency"] = level; wt["_reasons"] = reasons; wt["_sessions"] = sessions
        buckets.setdefault(level, []).append(wt)
    icons = {"critical": "🛑", "needs-triage": "🔴", "in-flight": "🟡",
             "watch": "🟠", "clean": "🟢", "error": "⚠️ "}
    headers = {"critical": "CRITICAL — IN-PROGRESS OPERATION", "needs-triage": "NEEDS TRIAGE",
               "in-flight": "IN FLIGHT", "watch": "WATCH", "clean": "CLEAN", "error": "ERROR"}
    for b in ["critical", "needs-triage", "in-flight", "watch", "clean", "error"]:
        if not buckets[b]: continue
        lines.append(f"{icons[b]} {headers[b]}")
        for wt in buckets[b]:
            short = wt.get("path", "?").replace(str(Path.home()), "~")
            branch = wt.get("branch") or ("(detached)" if wt.get("detached") else "?")
            dirty = wt.get("dirty_count", 0) + wt.get("untracked_count", 0)
            sm = f" · 🟢 {len(wt['_sessions'])} session(s) active" if wt['_sessions'] else ""
            lines.append(f"  {short}")
            lines.append(f"    branch: {branch} · dirty: {dirty} · unpushed: {wt.get('unpushed_count',0)} · stash: {wt.get('stash_count',0)} · {reltime(wt.get('activity_ts'))}{sm}")
            for r in wt.get("_reasons", []):
                lines.append(f"    └─ {r}")
        lines.append("")
    triage = [w for w in summary.get("worktrees", []) if w.get("_urgency") in ("critical", "needs-triage")]
    if triage:
        lines.append("RECOMMENDED ACTIONS")
        for wt in triage:
            short = wt.get("path", "?").replace(str(Path.home()), "~")
            if wt.get("in_progress"):
                lines.append(f"  {short}: complete or abort the {wt['in_progress']} (do not wip-save)")
            else:
                lines.append(f"  {short}: cd in, then /ultraprompt:wip-save then /ultraprompt:cleanup")
        lines.append("")
    if not any(buckets[b] for b in ("critical", "needs-triage", "in-flight", "watch", "error")):
        lines.append("All worktrees clean. No action needed.")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=None); p.add_argument("--all-repos", action="store_true")
    p.add_argument("--format", default="table", choices=["table", "json", "markdown"])
    p.add_argument("--active-window-minutes", type=int, default=None)
    args = p.parse_args()
    config = _cfg.load_config()
    win = args.active_window_minutes or _cfg.get(config, "session.active_window_minutes", 15)
    summaries = []
    if args.all_repos:
        watched = _cfg.get(config, "watched_repos.paths", []) or []
        seen = set()
        for base in watched:
            bp = Path(base).expanduser()
            if not bp.exists(): continue
            for cand in [bp] + (list(bp.iterdir()) if bp.is_dir() else []):
                if not cand.is_dir(): continue
                root = _ws.find_repo_root(cand)
                if root and root not in seen:
                    seen.add(root); summaries.append(_ws.repo_summary(root))
    else:
        root = Path(args.repo).resolve() if args.repo else _ws.find_repo_root()
        if root is None:
            print("Not in a git repo. Pass --repo or run from a repo.", file=sys.stderr); return 1
        summaries.append(_ws.repo_summary(root))
    spw = {}
    for s in summaries:
        for wt in s.get("worktrees", []):
            spw[wt["path"]] = _ws.find_active_sessions(Path(wt["path"]), win)
    if args.format == "json":
        print(json.dumps({"summaries": summaries, "active_sessions": spw}, indent=2, default=str))
    else:
        for s in summaries:
            print(render_table(s, config, spw)); print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
