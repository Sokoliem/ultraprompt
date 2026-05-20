#!/usr/bin/env python3
"""Audit registered hook coverage against the explicit hook coverage matrix."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS_PATH = ROOT / "hooks" / "hooks.json"
COVERAGE_PATH = ROOT / "tests" / "hooks" / "coverage.json"
VALID_COVERAGE = {"fixture", "integration", "manual", "none"}


def registered_hooks() -> dict[str, str]:
    data = json.loads(HOOKS_PATH.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for event, groups in (data.get("hooks") or {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                command = hook.get("command", "")
                match = re.search(r"hooks/recipes/([^\"'\s]+)", command.replace("\\", "/"))
                if match:
                    out[match.group(1)] = event
    return out


def audit() -> dict:
    registered = registered_hooks()
    coverage_doc = json.loads(COVERAGE_PATH.read_text(encoding="utf-8")) if COVERAGE_PATH.exists() else {}
    entries = coverage_doc.get("entries", {})
    missing = []
    mismatched_event = []
    invalid = []
    uncovered = []
    for script, event in sorted(registered.items()):
        entry = entries.get(script)
        if not entry:
            missing.append(script)
            continue
        if entry.get("event") != event:
            mismatched_event.append({"script": script, "expected": event, "actual": entry.get("event")})
        level = entry.get("coverage")
        if level not in VALID_COVERAGE:
            invalid.append({"script": script, "coverage": level})
        if level in ("none", "manual"):
            uncovered.append(script)
    orphaned = sorted(set(entries) - set(registered))
    return {
        "ok": not missing and not mismatched_event and not invalid,
        "registered": len(registered),
        "covered": len(registered) - len(missing),
        "fixture": sum(1 for script in registered if entries.get(script, {}).get("coverage") == "fixture"),
        "integration": sum(1 for script in registered if entries.get(script, {}).get("coverage") == "integration"),
        "manual_or_none": uncovered,
        "missing": missing,
        "mismatched_event": mismatched_event,
        "invalid": invalid,
        "orphaned_coverage_entries": orphaned,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="print JSON only")
    args = parser.parse_args()
    result = audit()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Ultraprompt hook coverage audit")
        print(f"- Registered hooks: {result['registered']}")
        print(f"- Coverage entries: {result['covered']}/{result['registered']}")
        print(f"- Fixture-covered: {result['fixture']}")
        print(f"- Integration-covered: {result['integration']}")
        print(f"- Manual/none: {len(result['manual_or_none'])}")
        if result["missing"]:
            print(f"- Missing: {', '.join(result['missing'])}")
        if result["mismatched_event"]:
            print(f"- Event mismatches: {result['mismatched_event']}")
        if result["invalid"]:
            print(f"- Invalid coverage values: {result['invalid']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
