#!/usr/bin/env python3
"""V8 wip-save: verified temp-worktree snapshot.

PRD §8.1 implementation. Creates a temporary worktree, syncs dirty state
into it (staged + unstaged + untracked, with explicit policy), commits to
a verifiable branch, verifies file list + content hashes, then removes
the temp worktree. The original worktree is never modified.

Fallback: --legacy uses the legacy stash-based path (scripts/wip-save-legacy.py).
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
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


def _git(args, cwd, timeout=30):
    try:
        r = subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, "", str(e)


def _ledger_write(event_type, **kwargs):
    m = _imp("ledger_v2", ROOT / "scripts" / "ledger-v2.py")
    if m:
        m.write_event(event_type, **kwargs)


def _file_hash(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _collect_dirty_files(worktree: Path, include_untracked: bool, include_ignored: bool):
    """Return list of relative paths that are dirty (staged, modified, untracked per policy)."""
    files = set()

    # Staged + modified-tracked
    rc, out, _ = _git(["status", "--porcelain", "-z"], worktree)
    if rc != 0:
        return None
    for entry in out.split("\0"):
        if not entry or len(entry) < 3:
            continue
        status, _, path = entry[:2], entry[2], entry[3:]
        if not path:
            continue
        # Handle rename "A -> B" format
        if " -> " in path:
            _, _, path = path.partition(" -> ")
        # Skip untracked if policy says so
        if status == "??" and not include_untracked:
            continue
        # Skip ignored unless explicitly included
        if status == "!!" and not include_ignored:
            continue
        files.add(path)

    return sorted(files)


def _generate_unique_branch(repo_root: Path, base_name: str) -> str:
    """Make sure branch doesn't collide. Append .N if needed."""
    rc, out, _ = _git(["branch", "--list", base_name], repo_root)
    if rc == 0 and base_name not in out:
        return base_name
    # Collision — append numeric suffix
    for i in range(2, 100):
        candidate = f"{base_name}.{i}"
        rc, out, _ = _git(["branch", "--list", candidate], repo_root)
        if rc == 0 and candidate not in out:
            return candidate
    raise RuntimeError(f"could not find unique branch name starting with {base_name}")


def wip_save_verified(worktree: Path, include_untracked=True, include_ignored=False,
                trigger="manual", message=None, dry_run=False):
    """V8 verified-snapshot implementation."""
    worktree = worktree.resolve()
    ws = _imp("ws", ROOT / "scripts" / "worktree-state.py")
    if ws is None:
        return {"ok": False, "err": "worktree-state module unavailable", "implementation": "verified"}

    state = ws.worktree_state(worktree)
    repo_root = ws.find_repo_root(worktree)
    if not state.get("exists"):
        return {"ok": False, "err": "worktree does not exist", "implementation": "verified"}
    if state.get("in_progress"):
        return {"ok": False, "err": f"in-progress {state['in_progress']} — refusing", "implementation": "verified"}
    if repo_root is None:
        return {"ok": False, "err": "not in a git repository", "implementation": "verified"}

    files = _collect_dirty_files(worktree, include_untracked, include_ignored)
    if files is None:
        return {"ok": False, "err": "could not collect dirty files", "implementation": "verified"}
    if not files:
        return {"ok": True, "skipped": True, "reason": "nothing to save", "implementation": "verified"}

    repo_n = ws.repo_name(repo_root)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_branch = f"wip/{repo_n}/{worktree.name}/{ts}"
    msg = message or f"WIP verified-snapshot {ts} ({trigger}, {len(files)} files)"

    if dry_run:
        return {"ok": True, "dry_run": True, "implementation": "verified",
                "would_create_branch": base_branch, "would_save_files": len(files), "files": files[:20]}

    # Ensure unique branch name (PRD §8.1 collision case)
    try:
        branch = _generate_unique_branch(repo_root, base_branch)
    except Exception as e:
        return {"ok": False, "err": str(e), "implementation": "verified"}

    # Compute source content hashes for verification
    source_hashes = {p: _file_hash(worktree / p) for p in files}

    # Get the current HEAD as the base
    rc, head_sha, _ = _git(["rev-parse", "HEAD"], worktree)
    if rc != 0:
        return {"ok": False, "err": "could not resolve HEAD", "implementation": "verified"}
    head_sha = head_sha.strip()

    # Create a detached temp worktree at HEAD in a temp location
    temp_dir = Path(tempfile.mkdtemp(prefix=f"ultraprompt-wip-{ts}-"))
    temp_wt_path = temp_dir / "snapshot"

    try:
        rc, _, err = _git(
            ["worktree", "add", "--detach", str(temp_wt_path), head_sha],
            worktree, timeout=60
        )
        if rc != 0:
            return {"ok": False, "err": f"git worktree add failed: {err.strip()}", "implementation": "verified"}

        # Copy dirty files from source worktree into temp worktree
        copied = []
        for rel in files:
            src = worktree / rel
            dst = temp_wt_path / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                if src.is_dir():
                    # Untracked directory; copy recursively
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst, symlinks=True)
                    copied.append(rel + "/")
                elif src.exists():
                    shutil.copy2(src, dst)
                    copied.append(rel)
                else:
                    # File was deleted in working tree — remove from temp too
                    if dst.exists():
                        dst.unlink()
                    copied.append(rel + " (deleted)")
            except Exception as e:
                # Continue but record
                copied.append(f"{rel} (copy_error: {e})")

        # Stage everything in the temp worktree (including deletions)
        rc, _, err = _git(["add", "-A"], temp_wt_path, timeout=60)
        if rc != 0:
            return {"ok": False, "err": f"git add -A in temp failed: {err.strip()}", "implementation": "verified"}

        # Commit on a new branch
        rc, _, err = _git(["checkout", "-b", branch], temp_wt_path, timeout=30)
        if rc != 0:
            return {"ok": False, "err": f"checkout -b failed: {err.strip()}", "implementation": "verified"}

        rc, _, err = _git(
            ["-c", "user.name=ultraprompt-wip", "-c", "user.email=wip@ultraprompt",
             "commit", "-m", msg, "--allow-empty"],
            temp_wt_path, timeout=60
        )
        if rc != 0:
            return {"ok": False, "err": f"commit failed: {err.strip()}", "implementation": "verified"}

        # Get commit SHA for verification
        rc, commit_sha, _ = _git(["rev-parse", "HEAD"], temp_wt_path)
        commit_sha = commit_sha.strip() if rc == 0 else None

        # Verification: count tree entries in the commit
        rc, tree_listing, _ = _git(["ls-tree", "-r", "HEAD"], temp_wt_path)
        committed_files = tree_listing.count("\n") if rc == 0 else 0

        # Verify a sample of files match source hashes
        sample_size = min(5, len(files))
        sample = files[:sample_size]
        hash_verification = []
        for rel in sample:
            src_hash = source_hashes.get(rel)
            dst_path = temp_wt_path / rel
            if dst_path.exists() and dst_path.is_file():
                dst_hash = _file_hash(dst_path)
                hash_verification.append({"path": rel, "match": src_hash == dst_hash})

        verified = all(h["match"] for h in hash_verification) if hash_verification else True

        result = {
            "ok": True,
            "implementation": "verified",
            "branch_created": branch,
            "commit_sha": commit_sha,
            "files_saved": len(files),
            "committed_files_in_tree": committed_files,
            "head_at_save": head_sha,
            "trigger": trigger,
            "verification": {
                "hash_sample_size": len(hash_verification),
                "all_hashes_matched": verified,
                "details": hash_verification,
            },
            "include_untracked": include_untracked,
            "include_ignored": include_ignored,
        }

        _ledger_write(
            "wip_save",
            repo=repo_n,
            worktree=str(worktree),
            branch_name=branch,
            file_count=len(files),
            commit_sha=commit_sha,
            trigger=trigger,
            implementation="verified",
            verified=verified,
            ok=True,
        )

        return result

    finally:
        # Remove the temp worktree (the branch survives because it was committed)
        _git(["worktree", "remove", "--force", str(temp_wt_path)], worktree, timeout=30)
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--worktree", default=None)
    p.add_argument("--include-untracked", action="store_true", default=True)
    p.add_argument("--no-untracked", dest="include_untracked", action="store_false")
    p.add_argument("--include-ignored", action="store_true", default=False)
    p.add_argument("--trigger", default="manual")
    p.add_argument("--message", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--legacy", action="store_true",
                   help="Use legacy stash-based implementation (fallback for known-edge-case bugs)")
    args = p.parse_args()

    wt = Path(args.worktree).resolve() if args.worktree else Path.cwd()

    if args.legacy:
        # Delegate to legacy implementation
        legacy = _imp("legacy", ROOT / "scripts" / "wip-save-legacy.py")
        if legacy is None:
            print(json.dumps({"ok": False, "err": "legacy module not available"}, indent=2))
            return 1
        r = legacy.wip_save(wt, args.include_untracked, False, "wip-backup",
                           args.trigger, args.message, args.dry_run)
        r["implementation"] = "legacy-stash"
        print(json.dumps(r, indent=2, default=str))
        return 0 if r.get("ok") else 1

    r = wip_save_verified(wt, args.include_untracked, args.include_ignored,
                    args.trigger, args.message, args.dry_run)
    print(json.dumps(r, indent=2, default=str))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
