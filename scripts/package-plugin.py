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

EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", "node_modules"}
EXCLUDE_FILE_PATTERNS = (".pyc", ".pyo", ".DS_Store", ".swp", ".swo")
EXCLUDE_FILES = {"ledger.jsonl", "ledger.lock"}


def included(path: Path) -> bool:
    parts = path.parts
    if any(p in EXCLUDE_DIRS or p.startswith(".test-") for p in parts):
        return False
    if path.name in EXCLUDE_FILES:
        return False
    if any(path.name.endswith(suffix) for suffix in EXCLUDE_FILE_PATTERNS):
        return False
    return True


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
    args = parser.parse_args()

    version = get_version()
    out_path = Path(args.output) if args.output else ROOT.parent / f"{args.name}-claude-plugin-{version.replace('.', '_')}.zip"

    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if not included(rel):
            continue
        files.append(path)

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
