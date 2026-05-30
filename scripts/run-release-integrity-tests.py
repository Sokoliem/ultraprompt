#!/usr/bin/env python3
"""Release-integrity tests (V9.2).

Two guards that protect the release pipeline itself:

  1. Version single-source — every version site (VERSION file, CHANGELOG top
     entry, the Codex manifest, and the rendered Claude manifests) must agree.
     This is the regression test for the V9.1 drift where the rendered
     plugin.json silently reverted to an old version because the .tmpl
     hard-coded it and the renderer never tokenized the version.

  2. SubagentStart hook parity — the POSIX recipe (subagent-scaffold.sh) and the
     direct entry (subagent-scaffold.py) must emit byte-identical stdout, so a
     future edit can't break one platform silently.

Run: python3 scripts/run-release-integrity-tests.py
Exit 0 if all pass, 1 otherwise.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader, f"cannot load {rel}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_version_single_source() -> list[str]:
    """VERSION file must be in sync with every other version site."""
    rm = _load("render_manifest", "scripts/render-manifest-template.py")
    version = rm.read_version()
    problems = rm.check_versions(version)
    return [f"version drift: {p}" for p in problems]


def test_hook_parity() -> list[str]:
    """subagent-scaffold.sh and .py must emit identical stdout.

    The .py is the canonical payload on every platform (Windows registers it
    directly via hooks.windows.json). The .sh is the POSIX delegator. On Windows
    the .sh path never runs in production and git-bash lacks `python3`, so the
    byte-for-byte comparison is scoped to POSIX; the .py is always validated.
    """
    py = ROOT / "hooks" / "recipes" / "subagent-scaffold.py"
    sh = ROOT / "hooks" / "recipes" / "subagent-scaffold.sh"
    fails: list[str] = []

    py_out = subprocess.run([sys.executable, str(py)], capture_output=True, text=True, timeout=10)
    if py_out.returncode != 0:
        fails.append(f"subagent-scaffold.py exited {py_out.returncode}")

    if sys.platform == "win32":
        return fails  # .sh delegation is POSIX-only; .py already validated above

    # POSIX: the .sh must run cleanly and match the canonical .py byte-for-byte.
    try:
        sh_out = subprocess.run(["bash", sh.name], cwd=str(sh.parent), capture_output=True, text=True, timeout=10)
    except FileNotFoundError:
        return fails  # no bash at all; nothing to compare
    if sh_out.returncode != 0:
        fails.append(f"subagent-scaffold.sh exited {sh_out.returncode}: {sh_out.stderr.strip()[:200]}")
    elif sh_out.stdout != py_out.stdout:
        fails.append("subagent-scaffold.sh and .py emit different stdout (single-source violated)")
    return fails


def main() -> int:
    tests = [
        ("version_single_source", test_version_single_source),
        ("hook_parity", test_hook_parity),
    ]
    total = passed = 0
    all_fails: list[str] = []
    for name, fn in tests:
        total += 1
        fails = fn()
        if fails:
            all_fails.extend(f"{name}: {f}" for f in fails)
        else:
            passed += 1

    print(f"Ultraprompt release-integrity tests: {total} checks")
    print(f"- passed: {passed}")
    print(f"- failed: {total - passed}")
    for f in all_fails:
        print(f"  FAIL  {f}")
    return 1 if all_fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
