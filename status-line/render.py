#!/usr/bin/env python3
"""Ultraprompt V5 status-line renderer.

Reads JSON from stdin (Claude Code session metadata) and emits a one-line status
string to stdout. Stays terse: tier counts + last validation if any.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    try:
        _ = json.load(sys.stdin)
    except Exception:
        pass

    plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[1])).resolve()
    index_path = plugin_root / "dist" / "skill-index.json"
    if not index_path.exists():
        print("ultraprompt v5")
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
        print(f"ultraprompt v5 · {skills} skills ({tiers['core']}c/{tiers['specialist']}s/{tiers['ecosystem']}e) · /ultraprompt:menu")
    except Exception:
        print("ultraprompt v5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
