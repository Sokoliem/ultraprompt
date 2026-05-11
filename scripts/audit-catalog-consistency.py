#!/usr/bin/env python3
"""Release-blocking catalog consistency and V8 cognitive checks."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str]) -> dict:
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / args[0]), *args[1:]],
                          cwd=ROOT, capture_output=True, text=True, timeout=90)
    return {
        "cmd": " ".join(args),
        "ok": proc.returncode == 0,
        "exit": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def names_from_specs(rel: str) -> set[str]:
    return {item["name"] for item in json.loads((ROOT / rel).read_text(encoding="utf-8"))}


def file_stems(pattern: str) -> set[str]:
    return {p.parent.name if p.name == "SKILL.md" else p.stem for p in ROOT.glob(pattern)}


def audit() -> dict:
    checks = []
    checks.append(run(["build-skill-index.py", "--check"]))
    checks.append(run(["build-catalog-metadata.py", "--check"]))
    checks.append(run(["build-capability-graph.py", "--check"]))
    checks.append(run(["regenerate-skills.py", "--check"]))
    checks.append(run(["regenerate-agents.py", "--check"]))
    checks.append(run(["audit-hook-coverage.py"]))
    checks.append(run(["run-config-tests.py"]))
    checks.append(run(["run-artifact-tests.py"]))
    checks.append(run(["run-pathfinder-tests.py"]))
    checks.append(run(["run-cognitive-tests.py"]))
    checks.append(run(["dream-runner.py", "validate-catalog"]))
    checks.append(run(["audit-doc-metadata.py"]))

    skill_specs = names_from_specs("source/skill-specs.json")
    skill_files = file_stems("skills/*/SKILL.md")
    agent_specs = names_from_specs("source/agent-specs.json")
    agent_files = file_stems("agents/*.md")
    source_checks = [
        {
            "name": "skills_have_source_specs",
            "ok": skill_specs == skill_files,
            "missing_specs": sorted(skill_files - skill_specs),
            "orphan_specs": sorted(skill_specs - skill_files),
        },
        {
            "name": "agents_have_source_specs",
            "ok": agent_specs == agent_files,
            "missing_specs": sorted(agent_files - agent_specs),
            "orphan_specs": sorted(agent_specs - agent_files),
        },
    ]
    ok = all(check["ok"] for check in checks) and all(check["ok"] for check in source_checks)
    return {"ok": ok, "checks": checks, "source_checks": source_checks}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="print JSON only")
    args = parser.parse_args()
    result = audit()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Ultraprompt catalog consistency audit")
        for check in result["checks"]:
            status = "OK" if check["ok"] else "FAIL"
            print(f"- {status}: {check['cmd']}")
            if not check["ok"]:
                if check["stdout"]:
                    print(f"  stdout: {check['stdout']}")
                if check["stderr"]:
                    print(f"  stderr: {check['stderr']}")
        for check in result["source_checks"]:
            status = "OK" if check["ok"] else "FAIL"
            print(f"- {status}: {check['name']}")
            if check.get("missing_specs"):
                print(f"  missing_specs: {check['missing_specs']}")
            if check.get("orphan_specs"):
                print(f"  orphan_specs: {check['orphan_specs']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
