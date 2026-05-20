#!/usr/bin/env python3
"""V8 worktree state primitive. Repo-agnostic, fail-open."""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path
from typing import Any


def _git(args, cwd=None, timeout=5):
    try:
        p = subprocess.run(["git"] + args, cwd=str(cwd) if cwd else None,
                           capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return -1, "", str(e)


def find_repo_root(start=None):
    rc, out, _ = _git(["rev-parse", "--show-toplevel"], cwd=start or Path.cwd())
    if rc != 0 or not out.strip():
        return None
    return Path(out.strip())


def repo_name(repo_root):
    rc, out, _ = _git(["config", "--get", "remote.origin.url"], cwd=repo_root)
    if rc == 0 and out.strip():
        n = out.strip().rstrip("/").rsplit("/", 1)[-1]
        if n.endswith(".git"):
            n = n[:-4]
        if n:
            return n
    return repo_root.name


def list_worktrees(repo_root):
    rc, out, _ = _git(["worktree", "list", "--porcelain"], cwd=repo_root)
    if rc != 0:
        return []
    wts, cur = [], {}
    for line in out.splitlines():
        line = line.rstrip()
        if not line:
            if cur:
                wts.append(cur); cur = {}
            continue
        if line.startswith("worktree "):
            cur = {"path": line[9:], "detached": False, "locked": False, "prunable": False}
        elif line.startswith("HEAD "):
            cur["head"] = line[5:]
        elif line.startswith("branch "):
            cur["branch"] = line[7:].replace("refs/heads/", "")
        elif line == "detached":
            cur["detached"] = True
        elif line.startswith("locked"):
            cur["locked"] = True
        elif line.startswith("prunable"):
            cur["prunable"] = True
    if cur:
        wts.append(cur)
    return wts


def in_progress_state(wt):
    git_dir = wt / ".git"
    if git_dir.is_file():
        try:
            c = git_dir.read_text(encoding="utf-8").strip()
            if c.startswith("gitdir:"):
                git_dir = Path(c[7:].strip())
        except Exception:
            pass
    elif not git_dir.exists():
        rc, out, _ = _git(["rev-parse", "--git-dir"], cwd=wt)
        if rc == 0 and out.strip():
            git_dir = Path(out.strip())
            if not git_dir.is_absolute():
                git_dir = wt / git_dir
    markers = {"MERGE_HEAD": "merge", "REBASE_HEAD": "rebase", "rebase-merge": "rebase",
               "rebase-apply": "rebase", "CHERRY_PICK_HEAD": "cherry-pick",
               "BISECT_LOG": "bisect", "REVERT_HEAD": "revert"}
    for m, n in markers.items():
        if (git_dir / m).exists():
            return n
    return None


def worktree_state(wt):
    s = {"path": str(wt), "exists": wt.exists()}
    if not s["exists"]:
        s["err"] = "worktree path does not exist"
        return s
    rc, out, _ = _git(["rev-parse", "HEAD"], cwd=wt)
    s["head"] = out.strip() if rc == 0 else None
    rc, out, _ = _git(["branch", "--show-current"], cwd=wt)
    s["branch"] = out.strip() if rc == 0 else None
    s["detached"] = s["branch"] == ""
    rc, out, _ = _git(["status", "--porcelain=v1", "-uall"], cwd=wt)
    if rc == 0:
        lines = [l for l in out.splitlines() if l.strip()]
        s["dirty_count"] = sum(1 for l in lines if not l.startswith("??"))
        s["untracked_count"] = sum(1 for l in lines if l.startswith("??"))
    else:
        s["dirty_count"] = s["untracked_count"] = 0
    rc, out, _ = _git(["stash", "list"], cwd=wt)
    s["stash_count"] = len([l for l in out.splitlines() if l.strip()]) if rc == 0 else 0
    s["unpushed_count"] = 0; s["upstream"] = None
    rc, out, _ = _git(["rev-parse", "--abbrev-ref", "@{upstream}"], cwd=wt)
    if rc == 0 and out.strip():
        s["upstream"] = out.strip()
        rc2, out2, _ = _git(["rev-list", "--count", "@{upstream}..HEAD"], cwd=wt)
        if rc2 == 0:
            try: s["unpushed_count"] = int(out2.strip())
            except ValueError: s["unpushed_count"] = 0
    rc, out, _ = _git(["log", "-1", "--format=%ct"], cwd=wt)
    s["last_commit_ts"] = int(out.strip()) if rc == 0 and out.strip() else None
    s["in_progress"] = in_progress_state(wt)
    s["activity_ts"] = s["last_commit_ts"]
    try:
        head_file = wt / ".git"
        if head_file.exists():
            mt = int(head_file.stat().st_mtime)
            if s["activity_ts"] is None or mt > s["activity_ts"]:
                s["activity_ts"] = mt
    except OSError:
        pass
    return s


def repo_summary(repo_root=None):
    if repo_root is None:
        repo_root = find_repo_root()
    if repo_root is None:
        return {"err": "not in a git repository"}
    wts = list_worktrees(repo_root)
    out = []
    for wt in wts:
        st = worktree_state(Path(wt["path"])); st["meta"] = wt
        out.append(st)
    return {"repo": repo_name(repo_root), "repo_root": str(repo_root),
            "worktrees": out, "scanned_at": int(time.time())}


def find_active_sessions(wt, window_min=15):
    home = Path.home()
    cutoff = time.time() - window_min * 60
    sessions = []
    encoded = str(wt).replace("/", "-")
    if encoded.startswith("-"):
        encoded = encoded[1:]
    for cand in [home / ".claude" / "projects" / f"-{encoded}",
                 home / ".claude" / "projects" / encoded]:
        if not cand.exists():
            continue
        for j in cand.glob("*.jsonl"):
            try:
                m = j.stat().st_mtime
            except OSError:
                continue
            if m < cutoff:
                continue
            sessions.append({"runtime": "claude-code", "session_id": j.stem,
                             "last_activity_ts": int(m), "transcript_path": str(j)})
    return sessions


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("repo"); s.add_argument("--path", default=None)
    s = sub.add_parser("worktree"); s.add_argument("path")
    s = sub.add_parser("active-sessions")
    s.add_argument("path"); s.add_argument("--window-minutes", type=int, default=15)
    s = sub.add_parser("repo-name"); s.add_argument("--path", default=None)
    args = p.parse_args()
    if args.cmd == "repo":
        root = Path(args.path).resolve() if args.path else None
        print(json.dumps(repo_summary(root), indent=2, default=str))
    elif args.cmd == "worktree":
        print(json.dumps(worktree_state(Path(args.path).resolve()), indent=2, default=str))
    elif args.cmd == "active-sessions":
        print(json.dumps(find_active_sessions(Path(args.path).resolve(), args.window_minutes), indent=2))
    elif args.cmd == "repo-name":
        root = Path(args.path).resolve() if args.path else find_repo_root()
        if root is None:
            print("(not in a git repo)", file=sys.stderr); return 1
        print(repo_name(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
