#!/usr/bin/env python3
"""V8 Doctor: evidence discipline scorecard.

Reads ledger v2 and surfaces:
- claim_check pass/fail ratio (the discipline working signal)
- dispatch_advise recommendation distribution
- dispatch_advise → actual dispatch follow-through (when measurable)
- route_intent suggestion distribution
"""
from __future__ import annotations
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

    claim_checks = []
    dispatch_advises = []
    route_intents = []

    for e in events:
        if e.get("ts", 0) < window_start: continue
        if e.get("type") != "mcp_tool_call": continue
        tool = e.get("tool")
        if tool == "claim_check": claim_checks.append(e)
        elif tool == "dispatch_advise": dispatch_advises.append(e)
        elif tool == "route_intent": route_intents.append(e)

    print(f"=== Evidence discipline scorecard (last {days} days) ===")
    print()

    # Claim check
    print(f"claim_check: {len(claim_checks)} calls")
    if claim_checks:
        with_outcome = [c for c in claim_checks if "passed" in c]
        no_outcome = [c for c in claim_checks if "passed" not in c]
        if with_outcome:
            passed = sum(1 for c in with_outcome if c.get("passed"))
            failed = len(with_outcome) - passed
            print(f"  passed: {passed}")
            print(f"  failed: {failed}")
            if failed > 0:
                print(f"  ✓ Discipline catching real issues — {failed}/{len(with_outcome)} failed validation")
            else:
                print(f"  ⚠  All {len(with_outcome)} claim_checks passed — either work is clean or checks are too lax")
        if no_outcome:
            print(f"  legacy events without outcome data: {len(no_outcome)}")
        # Total checks (sum of check_count)
        total_checks = sum(c.get("check_count", 0) for c in claim_checks)
        if total_checks:
            print(f"  total individual claims validated: {total_checks}")

    # Dispatch advise
    print()
    print(f"dispatch_advise: {len(dispatch_advises)} calls")
    if dispatch_advises:
        recs = Counter(c.get("recommend") for c in dispatch_advises if c.get("recommend"))
        for rec, n in recs.most_common():
            print(f"  recommend={rec}: {n}")
        agents = Counter(c.get("agent") for c in dispatch_advises if c.get("agent"))
        if agents:
            print("  Agents recommended:")
            for a, n in agents.most_common():
                print(f"    {n:5d}  {a}")
        # Legacy events without outcome data
        no_outcome_da = sum(1 for c in dispatch_advises if "recommend" not in c)
        if no_outcome_da:
            print(f"  legacy events without outcome data: {no_outcome_da}")
    else:
        print("  ⚠  No dispatch_advise calls — Claude isn't reaching for it")

    # Route intent
    print()
    print(f"route_intent: {len(route_intents)} calls")
    if route_intents:
        skills = Counter(c.get("top_skill") for c in route_intents if c.get("top_skill"))
        if skills:
            print("  Top skills routed to:")
            for s, n in skills.most_common(5):
                print(f"    {n:5d}  {s}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
