#!/usr/bin/env python3
"""Package the Ultraprompt V8 plugin into a release zip.

Excludes: __pycache__, .pyc, .DS_Store, *.swp, ledger files, and local test state.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXCLUDE_DIRS = {
    "__pycache__", ".git", ".pytest_cache", ".mypy_cache", "node_modules",
    ".test-tmp", "backups",
}
EXCLUDE_FILE_PATTERNS = (
    ".pyc", ".pyo", ".DS_Store", ".swp", ".swo", ".log", ".pid", ".lock",
)
EXCLUDE_FILES = {
    "ledger.jsonl",
    "ledger.lock",
    ".ultraprompt-install-manifest.json",
}


def included(path: Path) -> bool:
    parts = path.parts
    if any(p in EXCLUDE_DIRS or p.startswith(".test-") for p in parts):
        return False
    if path.name in EXCLUDE_FILES:
        return False
    if any(path.name.endswith(suffix) for suffix in EXCLUDE_FILE_PATTERNS):
        return False
    return True


def iter_included_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if not included(rel):
            continue
        files.append(path)
    return files


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def resolve_ref(ref: str) -> Path:
    rel = ref[2:] if ref.startswith("./") else ref
    return ROOT / rel


def verify_package(files: list[Path]) -> dict:
    included_rel = {p.relative_to(ROOT).as_posix() for p in files}
    errors: list[str] = []
    warnings: list[str] = []
    for manifest_rel in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        manifest_path = ROOT / manifest_rel
        if manifest_rel not in included_rel:
            errors.append(f"required manifest missing from package: {manifest_rel}")
            continue
        manifest = load_json(manifest_path)
        for field in ("mcpServers", "hooks", "outputStyles"):
            ref = manifest.get(field)
            if (
                manifest_rel == ".claude-plugin/plugin.json"
                and field == "hooks"
                and isinstance(ref, str)
                and ref.removeprefix("./") == "hooks/hooks.json"
            ):
                errors.append(
                    f"{manifest_rel} must not reference {ref}; Claude Code auto-loads hooks/hooks.json"
                )
            if isinstance(ref, str):
                ref_path = resolve_ref(ref)
                rel = ref_path.relative_to(ROOT).as_posix()
                if ref_path.is_dir():
                    prefix = rel.rstrip("/") + "/"
                    present = any(item.startswith(prefix) for item in included_rel)
                else:
                    present = rel in included_rel
                if not present:
                    errors.append(f"{manifest_rel} references file excluded or missing from package: {ref}")
    forbidden = sorted(
        rel for rel in included_rel
        if rel.startswith(".git/") or rel == ".ultraprompt-install-manifest.json" or "/backups/" in rel
    )
    if forbidden:
        errors.append(f"forbidden local state included: {forbidden[:10]}")
    return {"ok": not errors, "files": len(files), "errors": errors, "warnings": warnings}


def copy_to(target: Path, files: list[Path]) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for src in files:
        rel = src.relative_to(ROOT)
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def get_version() -> str:
    manifest = ROOT / ".claude-plugin" / "plugin.json"
    if not manifest.exists():
        return "unknown"
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("version", "unknown")
    except json.JSONDecodeError:
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None, help="Output zip path")
    parser.add_argument("--name", default="ultraprompt", help="Plugin name for filename")
    parser.add_argument("--verify-only", action="store_true", help="Verify inclusion policy without writing a zip")
    parser.add_argument("--copy-to", default=None, help="Copy the package file set to a target directory")
    args = parser.parse_args()

    version = get_version()
    out_path = Path(args.output) if args.output else ROOT.parent / f"{args.name}-claude-plugin-{version.replace('.', '_')}.zip"

    files = iter_included_files()
    verification = verify_package(files)
    if args.verify_only:
        print(json.dumps(verification, indent=2))
        return 0 if verification["ok"] else 1
    if not verification["ok"]:
        print(json.dumps(verification, indent=2), file=sys.stderr)
        return 1
    if args.copy_to:
        copy_to(Path(args.copy_to), files)
        print(f"Copied {len(files)} files to {args.copy_to}")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            rel = path.relative_to(ROOT)
            arcname = Path(args.name) / rel
            zf.write(path, arcname=arcname)

    size_kb = out_path.stat().st_size / 1024
    print(f"Packaged {len(files)} files into {out_path} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
