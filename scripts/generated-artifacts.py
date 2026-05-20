#!/usr/bin/env python3
"""Check source-derived generated artifacts and print the exact fix plan."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

GENERATED_CHECKS = [
    {
        "id": "skill_index",
        "check": ["build-skill-index.py", "--check"],
        "fix": ["build-skill-index.py"],
        "artifacts": ["dist/skill-index.json"],
    },
    {
        "id": "routing_policy",
        "check": ["build-routing-policy.py", "--check"],
        "fix": ["build-routing-policy.py"],
        "artifacts": ["dist/routing-policy.json"],
    },
    {
        "id": "catalog_metadata",
        "check": ["build-catalog-metadata.py", "--check"],
        "fix": ["build-catalog-metadata.py"],
        "artifacts": ["dist/catalog-metadata.json"],
    },
    {
        "id": "capability_graph",
        "check": ["build-capability-graph.py", "--check"],
        "fix": ["build-capability-graph.py"],
        "artifacts": ["dist/capability-graph.json"],
    },
    {
        "id": "skills",
        "check": ["regenerate-skills.py", "--check"],
        "fix": ["regenerate-skills.py"],
        "artifacts": ["skills/*/SKILL.md"],
    },
    {
        "id": "agents",
        "check": ["regenerate-agents.py", "--check"],
        "fix": ["regenerate-agents.py"],
        "artifacts": ["agents/*.md"],
    },
]


def run_check(argv: list[str], *, timeout: int = 120) -> dict[str, Any]:
    cmd = [sys.executable, str(ROOT / "scripts" / argv[0]), *argv[1:]]
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return {
            "command": " ".join(argv),
            "exit_code": proc.returncode,
            "ok": proc.returncode == 0,
            "duration_ms": int((time.time() - started) * 1000),
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode(errors="ignore")
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode(errors="ignore")
        return {
            "command": " ".join(argv),
            "exit_code": -124,
            "ok": False,
            "duration_ms": int((time.time() - started) * 1000),
            "stdout": (stdout or "").strip(),
            "stderr": "\n".join(part for part in ((stderr or "").strip(), f"timeout after {timeout}s") if part),
        }


def classify_artifact_check(check_id: str, result: dict[str, Any]) -> dict[str, Any]:
    text = f"{result.get('stdout', '')}\n{result.get('stderr', '')}".lower()
    drift = (
        not result.get("ok")
        and (
            "stale" in text
            or "drift" in text
            or "missing" in text
            or "run scripts/" in text
            or "run regenerate" in text
        )
    )
    timeout = result.get("exit_code") == -124 or "timeout after" in text
    return {
        "id": check_id,
        "ok": bool(result.get("ok")),
        "drift": bool(drift),
        "timeout": bool(timeout),
        "failure_kind": "generated_artifact_drift" if drift else ("harness_timeout" if timeout else ("implementation_blocker" if not result.get("ok") else "")),
    }


def build_report() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    fix_plan: list[dict[str, Any]] = []
    for spec in GENERATED_CHECKS:
        result = run_check(spec["check"])
        classification = classify_artifact_check(spec["id"], result)
        row = {
            **classification,
            "artifacts": spec["artifacts"],
            "check_command": "python3 scripts/" + " ".join(spec["check"]),
            "fix_command": "python3 scripts/" + " ".join(spec["fix"]),
            "result": result,
        }
        checks.append(row)
        if not row["ok"]:
            fix_plan.append({
                "id": spec["id"],
                "command": row["fix_command"],
                "artifacts": spec["artifacts"],
                "failure_kind": row["failure_kind"],
            })
    return {
        "schema": "generated_artifacts.v1",
        "generated_at": int(time.time()),
        "ok": all(row["ok"] for row in checks),
        "checks": checks,
        "fix_plan": fix_plan,
    }


def print_human(report: dict[str, Any]) -> None:
    print("Generated artifact preflight")
    for row in report["checks"]:
        state = "ok" if row["ok"] else row["failure_kind"]
        print(f"- {row['id']}: {state}")
        if not row["ok"]:
            print(f"  fix: {row['fix_command']}")
    if report["ok"]:
        print("All generated artifacts are current.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("check", "fix-plan"):
        p = sub.add_parser(name)
        p.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_report()
    if args.cmd == "fix-plan":
        report = {**report, "checks": [], "ok": not report["fix_plan"]}
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_human(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
