#!/usr/bin/env python3
"""V8 Doctor: skill activation scorecard.

Per-skill auto-discovery rate over the window. Reads ledger v2.
Surfaces never-fired skills with description-sharpening recommendation.
"""
from __future__ import annotations
import json
import sys
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def read_ledger_events(days: int) -> list[dict]:
    spec = importlib.util.spec_from_file_location("ledger_v2", PLUGIN_ROOT / "scripts" / "ledger-v2.py")
    if spec is None or spec.loader is None:
        return []
    ledger = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ledger)
    return ledger.read_events(days=days)


def main():
    days = 7
    if len(sys.argv) > 1:
        try: days = int(sys.argv[1])
        except: pass

    window_start = (datetime.now() - timedelta(days=days)).timestamp()
    events = read_ledger_events(days)
    if not events:
        print("ledger has no events in Claude Code or Codex runtime paths")
        return 1

    skill_invocations = Counter()
    mcp_calls = Counter()
    route_decisions = Counter()
    claim_checks = []

    for e in events:
        if e.get("ts", 0) < window_start: continue
        t = e.get("type")
        if t == "skill_invocation" and e.get("is_plugin_skill"):
            skill_invocations[e.get("skill", "?")] += 1
        elif t == "mcp_tool_call":
            mcp_calls[e.get("tool", "?")] += 1
            if e.get("tool") == "claim_check":
                claim_checks.append(e)
        elif t == "route_decision":
            route_decisions[e.get("top_skill", "?")] += 1

    print(f"=== Skill activation scorecard (last {days} days) ===")
    print()

    print("Plugin skills auto-fired (skill_invocation events):")
    if skill_invocations:
        for s, n in skill_invocations.most_common():
            print(f"  {n:5d}  {s}")
    else:
        print("  (none recorded — telemetry hook may need fixing)")

    # Skills never fired (from skill index)
    skill_index = PLUGIN_ROOT / "dist/skill-index.json"
    if skill_index.exists():
        try:
            idx = json.load(open(skill_index))
            all_skills = set()
            if isinstance(idx, dict) and "skills" in idx:
                for s in idx["skills"]:
                    all_skills.add(s.get("name", "?"))
            elif isinstance(idx, list):
                for s in idx:
                    all_skills.add(s.get("name", "?"))
            fired = set(s.split(":")[-1] for s in skill_invocations.keys())
            never_fired = sorted(all_skills - fired - {"?"})
            if never_fired:
                print()
                print(f"Skills never auto-fired ({len(never_fired)}/{len(all_skills)}):")
                for s in never_fired[:20]:
                    print(f"  ⚠  {s}")
                if len(never_fired) > 20:
                    print(f"  ... and {len(never_fired) - 20} more")
        except Exception as e:
            pass

    print()
    print("MCP tool calls:")
    if mcp_calls:
        for t, n in mcp_calls.most_common():
            marker = "★" if t in ("dispatch_advise", "claim_check", "route_intent") else " "
            print(f"  {marker} {n:5d}  {t}")
    else:
        print("  (none)")

    if route_decisions:
        print()
        print("Route decisions (route_intent suggestions):")
        for s, n in route_decisions.most_common():
            print(f"  {n:5d}  → {s}")

    if claim_checks:
        print()
        print(f"Claim checks: {len(claim_checks)} (✓ evidence discipline working)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
