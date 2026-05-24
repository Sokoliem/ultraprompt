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

EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", "node_modules", ".remember", ".venv"}
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
    parser.add_argument("--output", default=None, help="Output archive path")
    parser.add_argument("--name", default="ultraprompt", help="Plugin name for filename")
    parser.add_argument(
        "--format",
        choices=("zip", "plugin", "both"),
        default="both",
        help=(
            "zip: wraps content in <name>/ for Claude Code marketplace installs. "
            "plugin: .plugin file with content at the archive root for Claude Desktop "
            "Cowork drag-drop install. both: emit both."
        ),
    )
    args = parser.parse_args()

    version = get_version()
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if not included(rel):
            continue
        files.append(path)

    outputs: list[Path] = []

    if args.format in ("zip", "both"):
        zip_out = (
            Path(args.output)
            if args.output and args.format == "zip"
            else ROOT.parent / f"{args.name}-claude-plugin-{version.replace('.', '_')}.zip"
        )
        zip_out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_out, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in files:
                rel = path.relative_to(ROOT)
                arcname = Path(args.name) / rel
                zf.write(path, arcname=arcname)
        outputs.append(zip_out)

    if args.format in ("plugin", "both"):
        # Cowork (Claude Desktop) expects `.plugin` extension and the plugin contents
        # at the archive root (so `.claude-plugin/plugin.json` is at depth 0). Per
        # `cowork-plugin-management` skill: `zip -r /tmp/<name>.plugin .` from inside
        # the plugin dir. We mirror that layout from Python so the archive drag-drops
        # cleanly into cowork.
        plugin_out = (
            Path(args.output)
            if args.output and args.format == "plugin"
            else ROOT.parent / f"{args.name}.plugin"
        )
        plugin_out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(plugin_out, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in files:
                rel = path.relative_to(ROOT)
                zf.write(path, arcname=str(rel))
        outputs.append(plugin_out)

    for out in outputs:
        size_kb = out.stat().st_size / 1024
        print(f"Packaged {len(files)} files into {out} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
