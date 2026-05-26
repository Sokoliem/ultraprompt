#!/usr/bin/env python3
"""Run hook fixture tests against Ultraprompt V8 hook recipes.

Each hook recipe receives JSON via stdin and emits JSON-or-text to stdout
with a specific exit code. This runner feeds fixtures from tests/hooks/<hook>/
to the corresponding recipe and verifies the expected response.

Fixture format (JSON):
{
  "input": <stdin payload as JSON>,
  "env": {"VAR": "value"},
  "expected_exit": <int>,
  "expected_decision": "allow|block|ask|null",
  "stdout_contains": "<substring or null>"
}
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = ROOT / "hooks" / "recipes"
TESTS_DIR = ROOT / "tests" / "hooks"

HOOK_TO_SCRIPT = {
    "destructive-command-guard": HOOKS_DIR / "destructive-command-guard.py",
    "protected-file-guard": HOOKS_DIR / "protected-file-guard.py",
    "stop-validation-check": HOOKS_DIR / "stop-validation-check.py",
    "subagent-scaffold": HOOKS_DIR / "subagent-scaffold.py",
    "user-prompt-route-suggest": HOOKS_DIR / "user-prompt-route-suggest.py",
    "post-tool-use-ledger": HOOKS_DIR / "post-tool-use-ledger.py",
    "vibe-detect": HOOKS_DIR / "vibe-detect.py",
}


def run_one(hook_name: str, fixture_path: Path) -> tuple[bool, str]:
    script = HOOK_TO_SCRIPT.get(hook_name)
    if script is None or not script.exists():
        return False, f"hook script not found: {hook_name}"
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"invalid fixture JSON: {exc}"
    stdin_payload = json.dumps(fixture.get("input") or {})
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(ROOT)
    env.update(fixture.get("env") or {})
    expected_exit = fixture.get("expected_exit", 0)
    expected_decision = fixture.get("expected_decision")
    stdout_contains = fixture.get("stdout_contains")

    interpreter = [sys.executable] if str(script).endswith(".py") else ["bash"]
    proc = subprocess.run(
        interpreter + [str(script)],
        input=stdin_payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    fails: list[str] = []
    if proc.returncode != expected_exit:
        fails.append(f"exit {proc.returncode} != expected {expected_exit}")
    if expected_decision is not None:
        try:
            response = json.loads(proc.stdout) if proc.stdout.strip() else {}
            actual_decision = (response.get("hookSpecificOutput") or {}).get("permissionDecision")
            if actual_decision != expected_decision:
                fails.append(f"decision {actual_decision!r} != expected {expected_decision!r}")
        except json.JSONDecodeError:
            fails.append("response not valid JSON")
    if stdout_contains and stdout_contains not in proc.stdout:
        fails.append(f"stdout missing {stdout_contains!r}")
    if fails:
        return False, "; ".join(fails) + f" | stderr: {proc.stderr.strip()[:200]}"
    return True, "ok"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hook", help="run only the named hook")
    args = parser.parse_args()

    if not TESTS_DIR.exists():
        print("ERROR: tests/hooks/ not found", file=sys.stderr)
        return 1

    total = passed = failed = 0
    failures: list[tuple[str, str, str]] = []
    for hook_dir in sorted(TESTS_DIR.iterdir()):
        if not hook_dir.is_dir():
            continue
        if args.hook and hook_dir.name != args.hook:
            continue
        for fixture in sorted(hook_dir.glob("*.json")):
            total += 1
            ok, msg = run_one(hook_dir.name, fixture)
            if ok:
                passed += 1
            else:
                failed += 1
                failures.append((hook_dir.name, fixture.name, msg))
    print(f"Ultraprompt V8 hook tests: {total} fixtures")
    print(f"- passed: {passed}")
    print(f"- failed: {failed}")
    for hook, fixture, msg in failures:
        print(f"  FAIL  {hook}/{fixture}: {msg}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
