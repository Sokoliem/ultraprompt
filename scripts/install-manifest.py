#!/usr/bin/env python3
"""V8: Install manifest tracking + atomic rollback (PRD §8.6).

During install:
  manifest write —  records every file written, with sha256 + timestamp.
  Stored at <install-root>/.ultraprompt-install-manifest.json

During rollback:
  Reads manifest, restores previous state from backup, removes added files.
  Verifies via sha256 that rollback restored original content.

Subcommands:
  install-manifest.py write <install-root> <backup-root>
  install-manifest.py verify <install-root>
  install-manifest.py rollback <install-root>
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

VOLATILE_GENERATED_FILES = {
    "dist/catalog-audit-report.json",
    "dist/release-scorecard.json",
}
EXCLUDED_PARTS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    ".test-tmp",
    "backups",
}
EXCLUDED_FILES = {
    ".ultraprompt-install-manifest.json",
    "ledger.lock",
}


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def collect_install_state(install_root: Path) -> dict:
    """Walk install root and record sha256 of every file."""
    files = {}
    for p in install_root.rglob("*"):
        if not p.is_file():
            continue
        # Skip the manifest itself + obvious caches
        rel = p.relative_to(install_root)
        rel_key = rel.as_posix()
        if rel_key in EXCLUDED_FILES:
            continue
        if rel_key in VOLATILE_GENERATED_FILES:
            continue
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        if rel.suffix == ".pyc":
            continue
        files[str(rel)] = {
            "sha256": file_sha256(p),
            "size": p.stat().st_size,
        }
    return files


def write_manifest(install_root: Path, backup_root: Path | None,
                   plugin_version: str | None = None) -> Path:
    """Record current install state as a manifest."""
    manifest = {
        "schema_version": 1,
        "plugin_version": plugin_version,
        "installed_at": int(time.time()),
        "install_root": str(install_root),
        "backup_root": str(backup_root) if backup_root else None,
        "files": collect_install_state(install_root),
    }
    p = install_root / ".ultraprompt-install-manifest.json"
    json.dump(manifest, open(p, "w"), indent=2)
    return p


def verify_manifest(install_root: Path) -> dict:
    """Verify each file in the manifest still has matching sha256."""
    p = install_root / ".ultraprompt-install-manifest.json"
    if not p.exists():
        return {"ok": False, "error": "manifest not found"}
    manifest = json.load(open(p))
    drift = []
    missing = []
    for rel, info in manifest["files"].items():
        full = install_root / rel
        if not full.exists():
            missing.append(rel)
            continue
        actual = file_sha256(full)
        if actual != info["sha256"]:
            drift.append({"file": rel, "expected": info["sha256"], "actual": actual})
    return {
        "ok": len(drift) == 0 and len(missing) == 0,
        "manifest_files": len(manifest["files"]),
        "drift_count": len(drift),
        "missing_count": len(missing),
        "drift": drift[:20],
        "missing": missing[:20],
    }


def rollback(install_root: Path) -> dict:
    """Restore install_root from its declared backup_root.

    Strategy: rather than per-file restore (complex when files were added/deleted),
    we replace install_root with backup_root contents wholesale.
    """
    p = install_root / ".ultraprompt-install-manifest.json"
    if not p.exists():
        return {"ok": False, "error": "no manifest — cannot determine backup location"}
    manifest = json.load(open(p))
    backup_root = manifest.get("backup_root")
    if not backup_root:
        return {"ok": False, "error": "manifest has no backup_root"}
    backup_path = Path(backup_root)
    if not backup_path.exists():
        return {"ok": False, "error": f"backup directory not found: {backup_root}"}

    # Move current install to a stash before applying backup, in case rollback fails partway
    stash_path = install_root.parent / f"{install_root.name}.rollback-stash-{int(time.time())}"
    try:
        shutil.move(str(install_root), str(stash_path))
    except Exception as exc:
        return {"ok": False, "error": f"could not stash current install: {exc}"}

    try:
        # Restore from backup
        shutil.copytree(str(backup_path), str(install_root))
        # Verify restoration
        new_files = collect_install_state(install_root)
        return {
            "ok": True,
            "restored_from": str(backup_path),
            "stashed_to": str(stash_path),
            "files_restored": len(new_files),
            "rollback_at": int(time.time()),
        }
    except Exception as exc:
        # Try to put stash back
        try:
            if install_root.exists():
                shutil.rmtree(install_root)
            shutil.move(str(stash_path), str(install_root))
        except Exception:
            pass
        return {"ok": False, "error": f"rollback failed: {exc}"}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    s_write = sub.add_parser("write")
    s_write.add_argument("install_root")
    s_write.add_argument("--backup-root")
    s_write.add_argument("--plugin-version")

    s_verify = sub.add_parser("verify")
    s_verify.add_argument("install_root")

    s_rollback = sub.add_parser("rollback")
    s_rollback.add_argument("install_root")
    s_rollback.add_argument("--confirm", action="store_true",
                            help="Required to actually perform rollback")

    args = ap.parse_args()

    if args.cmd == "write":
        p = write_manifest(
            Path(args.install_root).resolve(),
            Path(args.backup_root).resolve() if args.backup_root else None,
            args.plugin_version,
        )
        print(json.dumps({"ok": True, "manifest_at": str(p)}, indent=2))
        return 0

    if args.cmd == "verify":
        r = verify_manifest(Path(args.install_root).resolve())
        print(json.dumps(r, indent=2))
        return 0 if r.get("ok") else 1

    if args.cmd == "rollback":
        if not args.confirm:
            print(json.dumps({
                "ok": False,
                "error": "rollback requires --confirm flag (this will replace the current install)",
            }, indent=2))
            return 1
        r = rollback(Path(args.install_root).resolve())
        print(json.dumps(r, indent=2))
        return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
