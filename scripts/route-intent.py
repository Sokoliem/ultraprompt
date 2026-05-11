#!/usr/bin/env python3
"""CLI fallback for /ultraprompt:route when the MCP server is unavailable.

Usage: python3 route-intent.py "review the auth diff before merging"
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ultraprompt_index import build_index, find_plugin_root, route_intent


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: route-intent.py <intent>", file=sys.stderr)
        return 2
    intent = " ".join(sys.argv[1:])
    root = find_plugin_root(ROOT)
    index = build_index(root)
    top = route_intent(index, intent, limit=3)
    if not top:
        print("| Skill | Confidence | Why | Invoke |")
        print("|-------|------------|-----|--------|")
        print(f"| /ultraprompt:repo-map | low | No clear match for intent; start with a structural map | /ultraprompt:repo-map |")
        return 0
    print("| Skill | Confidence | Why | Invoke |")
    print("|-------|------------|-----|--------|")
    for result in top:
        name = result["skill"]
        why = str(result.get("why", ""))[:120]
        invoke = result.get("command") or f"/ultraprompt:{name}"
        print(f"| /ultraprompt:{name} | {result['confidence']} | {why} | {invoke} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
