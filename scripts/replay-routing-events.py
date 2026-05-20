#!/usr/bin/env python3
"""Replay recent route events against the current routing catalog."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cognitive_common import ROOT, command_result, data_dir, print_json, read_jsonl


def event_log_path() -> Path:
    custom = os.environ.get("ULTRAPROMPT_EVENT_LOG")
    if custom:
        return Path(custom).expanduser()
    custom_dir = os.environ.get("ULTRAPROMPT_EVENT_DIR")
    if custom_dir:
        return Path(custom_dir).expanduser() / "events.jsonl"
    return data_dir("events") / "events.jsonl"


def parse_ts(value: object) -> datetime | None:
    text = str(value or "").replace("Z", "+00:00")
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def recent_route_events(days: int, limit: int) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = read_jsonl(event_log_path())
    events: list[dict[str, Any]] = []
    for row in rows:
        if row.get("type") not in {"pathfinder_decision", "route_outcome"}:
            continue
        ts = parse_ts(row.get("ts"))
        if ts and ts < cutoff:
            continue
        events.append(row)
    return events[-limit:]


def expected_from_event(event: dict[str, Any]) -> tuple[str, str, str]:
    data = event.get("data") or {}
    intent = str(data.get("intent") or "")
    skill = str(data.get("corrected_skill") or data.get("selected_skill") or data.get("skill") or "")
    panel = str(data.get("corrected_panel") or data.get("selected_panel") or data.get("panel") or "")
    return intent, skill, panel


def pathfind(intent: str, budget: str) -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "pathfinder.py"),
            "pathfind",
            "--intent",
            intent,
            "--budget",
            budget,
            "--dry-run",
            "--no-telemetry",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return command_result(False, error=proc.stdout or proc.stderr, exit=proc.returncode)


def replay(days: int, limit: int, budget: str) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    skipped = 0
    for event in recent_route_events(days, limit):
        intent, expected_skill, expected_panel = expected_from_event(event)
        if not intent or not expected_skill:
            skipped += 1
            continue
        result = pathfind(intent, budget)
        path = result.get("path") or {}
        recommended = path.get("recommended_path") or {}
        actual_skill = str(recommended.get("skill") or "")
        actual_panel = str(recommended.get("panel") or "")
        alternatives = [str(item.get("skill") or "") for item in path.get("alternatives") or []]
        skill_stable = actual_skill == expected_skill or expected_skill in alternatives
        panel_stable = not expected_panel or actual_panel == expected_panel
        cases.append({
            "event_id": event.get("id"),
            "event_type": event.get("type"),
            "intent_excerpt": intent[:160],
            "expected_skill": expected_skill,
            "actual_skill": actual_skill,
            "expected_panel": expected_panel,
            "actual_panel": actual_panel,
            "skill_stable": skill_stable,
            "panel_stable": panel_stable,
            "ok": skill_stable and panel_stable,
        })
    drifted = [case for case in cases if not case["ok"]]
    return command_result(
        not drifted,
        schema="routing_replay.v1",
        event_log=str(event_log_path()),
        window_days=days,
        budget=budget,
        replayed=len(cases),
        skipped=skipped,
        stable=len(cases) - len(drifted),
        drifted=len(drifted),
        cases=cases,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--budget", choices=["low", "standard", "deep"], default="standard")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--enforce", action="store_true")
    parser.add_argument("--min-replayed", type=int, default=0,
                        help="Minimum replayable route cases required. Enforce mode defaults to at least 1.")
    args = parser.parse_args()

    result = replay(args.days, args.limit, args.budget)
    min_replayed = max(args.min_replayed, 1 if args.enforce else 0)
    failures: list[str] = []
    if result["replayed"] < min_replayed:
        failures.append(f"routing replay cases {result['replayed']} < {min_replayed}")
    if failures:
        result["ok"] = False
        result["failures"] = failures
    if args.json:
        print_json(result)
    else:
        print(f"Routing replay: {result['stable']}/{result['replayed']} stable, {result['drifted']} drifted, {result['skipped']} skipped")
        for case in result["cases"]:
            if not case["ok"]:
                print(f"- {case['intent_excerpt']} expected={case['expected_skill']} got={case['actual_skill']}")
    return 1 if args.enforce and not result["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
