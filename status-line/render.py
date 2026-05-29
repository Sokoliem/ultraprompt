#!/usr/bin/env python3
"""Ultraprompt status-line renderer.

Reads JSON from stdin (Claude Code session metadata) and emits a one-line status
string to stdout. Stays terse: version + tier counts. Version is read from
dist/catalog-metadata.json — never hard-coded.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _plugin_version(plugin_root: Path) -> str:
    meta_path = plugin_root / "dist" / "catalog-metadata.json"
    try:
        return str(json.loads(meta_path.read_text(encoding="utf-8")).get("plugin_version") or "?")
    except Exception:
        return "?"


def main() -> int:
    try:
        _ = json.load(sys.stdin)
    except Exception:
        pass

    plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[1])).resolve()
    version = _plugin_version(plugin_root)
    index_path = plugin_root / "dist" / "skill-index.json"
    if not index_path.exists():
        print(f"ultraprompt v{version} · catalog missing", file=sys.stdout)
        print(f"status-line: skill-index.json not found at {index_path}", file=sys.stderr)
        return 0
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        counts = index.get("counts", {})
        skills = counts.get("skills", 0)
        tiers = {"core": 0, "specialist": 0, "ecosystem": 0}
        for s in index.get("skills", []):
            tier = s.get("tier", "")
            if tier in tiers:
                tiers[tier] += 1
        print(f"ultraprompt v{version} · {skills} skills ({tiers['core']}c/{tiers['specialist']}s/{tiers['ecosystem']}e) · /ultraprompt:menu")
    except Exception as e:
        print(f"ultraprompt v{version} · catalog read error")
        print(f"status-line: {type(e).__name__}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
