#!/usr/bin/env python3
"""Deterministic pathfinder golden tests."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from cognitive_common import ROOT, command_result, print_json


def run_case(intent: str, *, budget: str = "standard", no_telemetry: bool = False) -> dict:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "pathfinder.py"),
        "pathfind",
        "--intent",
        intent,
        "--budget",
        budget,
        "--dry-run",
    ]
    if no_telemetry:
        cmd.append("--no-telemetry")
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = {"ok": False, "error": proc.stdout or proc.stderr}
    return {"exit": proc.returncode, "data": data}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-telemetry", action="store_true", help="do not write pathfinder_decision events")
    args = parser.parse_args()
    cases = json.loads((ROOT / "tests" / "pathfinder" / "golden-cases.json").read_text(encoding="utf-8"))
    skill_index = json.loads((ROOT / "dist" / "skill-index.json").read_text(encoding="utf-8"))
    existing = {(case.get("intent"), case.get("expected_skill")) for case in cases}
    for skill in skill_index.get("skills", []):
        name = skill.get("name")
        if not name:
            continue
        case = {
            "intent": f"$ultraprompt:{name} run this lane",
            "expected_skill": name,
            "generated": True,
        }
        key = (case["intent"], name)
        if key not in existing:
            cases.append(case)
            existing.add(key)
    results = []
    top1 = 0
    top3 = 0
    for case in cases:
        result = run_case(case["intent"], budget=case.get("budget", "standard"), no_telemetry=args.no_telemetry)
        path = result["data"].get("path", {}) if result["data"].get("ok") else {}
        got = path.get("recommended_path", {}).get("skill")
        alternatives = [a.get("skill") for a in path.get("alternatives", [])]
        ok1 = got == case["expected_skill"]
        ok3 = ok1 or case["expected_skill"] in alternatives
        expected_path_type = case.get("expected_path_type")
        expected_panel = case.get("expected_panel")
        path_type_ok = not expected_path_type or path.get("recommended_path", {}).get("type") == expected_path_type
        panel_ok = not expected_panel or path.get("recommended_path", {}).get("panel") == expected_panel
        top1 += 1 if ok1 else 0
        top3 += 1 if ok3 else 0
        results.append({
            **case,
            "got": got,
            "path_type": path.get("recommended_path", {}).get("type"),
            "panel": path.get("recommended_path", {}).get("panel"),
            "alternatives": alternatives,
            "top1": ok1,
            "top3": ok3,
            "path_type_ok": path_type_ok,
            "panel_ok": panel_ok,
            "exit": result["exit"],
        })
    ok = top1 / len(cases) >= 0.95 and top3 == len(cases) and all(item["path_type_ok"] and item["panel_ok"] for item in results)
    generated_total = sum(1 for case in cases if case.get("generated"))
    payload = command_result(
        ok,
        total=len(cases),
        generated_cases=generated_total,
        hand_authored_cases=len(cases) - generated_total,
        top1=top1,
        top3=top3,
        results=results,
    )
    if args.json:
        print_json(payload)
    else:
        print(f"Pathfinder bench: {len(cases)} cases ({len(cases) - generated_total} hand-authored, {generated_total} generated skill-name coverage)")
        print(f"- top-1: {top1}/{len(cases)} ({top1 / len(cases) * 100:.1f}%; target >=95%)")
        print(f"- top-3: {top3}/{len(cases)} ({top3 / len(cases) * 100:.1f}%; target 100%)")
        for item in results:
            if not item["top1"] or not item["path_type_ok"] or not item["panel_ok"]:
                print(
                    f"  MISS {item['intent']!r} expected={item['expected_skill']} got={item['got']} "
                    f"path_type={item['path_type']} panel={item['panel']} alternatives={item['alternatives']}"
                )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
