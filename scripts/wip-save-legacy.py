#!/usr/bin/env python3
"""Legacy wip-save: safe atomic snapshot via stash+branch+pop pattern."""
from __future__ import annotations
import argparse, importlib.util, json, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _imp(n, p):
    try:
        spec = importlib.util.spec_from_file_location(n, p)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
    except Exception:
        return None


def _git(args, cwd, timeout=10):
    try:
        p = subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return -1, "", str(e)


def _ledger_write(t, **kw):
    m = _imp("ledger_v2", ROOT / "scripts" / "ledger-v2.py")
    if m: m.write_event(t, **kw)


def wip_save(worktree, include_untracked=True, push_to_backup=False,
             backup_remote="wip-backup", trigger="manual", message=None, dry_run=False):
    ws = _imp("ws", ROOT / "scripts" / "worktree-state.py")
    if ws is None:
        return {"ok": False, "err": "worktree-state module unavailable"}
    state = ws.worktree_state(worktree)
    repo_root = ws.find_repo_root(worktree)
    if not state.get("exists"):
        return {"ok": False, "err": "worktree does not exist"}
    if state.get("in_progress"):
        return {"ok": False, "err": f"in-progress {state['in_progress']} — refusing"}
    dirty = state.get("dirty_count", 0) + (state.get("untracked_count", 0) if include_untracked else 0)
    if dirty == 0:
        return {"ok": True, "skipped": True, "reason": "nothing to save"}
    if repo_root is None:
        return {"ok": False, "err": "not in a git repository"}
    repo_n = ws.repo_name(repo_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    branch = f"wip/{repo_n}/{worktree.name}/{timestamp}"
    msg = message or f"WIP autosave {timestamp} ({trigger}, {dirty} files)"
    if dry_run:
        return {"ok": True, "dry_run": True, "would_create_branch": branch, "would_save_files": dirty}

    # Stash with message
    stash_args = ["stash", "push", "--include-untracked" if include_untracked else "--keep-index", "-m", msg]
    rc, _, err = _git(stash_args, worktree)
    if rc != 0:
        return {"ok": False, "err": f"git stash failed: {err.strip()}"}

    try:
        rc2, sha, err2 = _git(["rev-parse", "stash@{0}"], worktree)
        if rc2 != 0:
            _git(["stash", "pop"], worktree)
            return {"ok": False, "err": f"rev-parse stash failed: {err2.strip()}"}
        sha = sha.strip()
        rc3, _, err3 = _git(["branch", branch, sha], worktree)
        if rc3 != 0:
            _git(["stash", "pop"], worktree)
            return {"ok": False, "err": f"branch creation failed: {err3.strip()}"}
        rc4, _, err4 = _git(["stash", "pop"], worktree)
        if rc4 != 0:
            return {"ok": False, "err": f"stash pop failed (branch was created): {err4.strip()}",
                    "branch_created": branch}
        push_result = None
        if push_to_backup:
            rc5, _, err5 = _git(["push", backup_remote, branch], worktree, timeout=60)
            push_result = {"ok": rc5 == 0, "err": err5.strip() if rc5 != 0 else None}
        result = {"ok": True, "branch_created": branch, "files_saved": dirty,
                  "head_at_save": state.get("head"), "trigger": trigger, "push_result": push_result}
        _ledger_write("wip_save", repo=repo_n, worktree=str(worktree),
                      branch_name=branch, file_count=dirty, trigger=trigger, ok=True)
        return result
    except Exception as e:
        _git(["stash", "pop"], worktree)
        return {"ok": False, "err": f"unexpected: {e}"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--worktree", default=None)
    p.add_argument("--include-untracked", action="store_true", default=True)
    p.add_argument("--no-untracked", dest="include_untracked", action="store_false")
    p.add_argument("--push", action="store_true")
    p.add_argument("--backup-remote", default="wip-backup")
    p.add_argument("--trigger", default="manual")
    p.add_argument("--message", default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    wt = Path(args.worktree).resolve() if args.worktree else Path.cwd()
    r = wip_save(wt, args.include_untracked, args.push, args.backup_remote,
                 args.trigger, args.message, args.dry_run)
    print(json.dumps(r, indent=2, default=str))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
