#!/usr/bin/env python3
"""V8.2: simulate Claude/Codex installs in a temp directory.

This is a release gate that exercises package selection and runtime-specific
manifest/MCP contracts without writing into ~/.claude or ~/.codex.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=180)
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", choices=["claude", "codex", "both"], default="both")
    parser.add_argument("--keep", action="store_true", help="Keep temp directory for inspection")
    args = parser.parse_args()

    runtimes = ["claude", "codex"] if args.runtime == "both" else [args.runtime]
    results = {}
    temp_root = Path(tempfile.mkdtemp(prefix="ultraprompt-install-sim-"))
    try:
        for runtime in runtimes:
            target = temp_root / runtime / "ultraprompt"
            code, out, err = run(
                [sys.executable, str(ROOT / "scripts" / "package-plugin.py"), "--copy-to", str(target)],
                ROOT,
            )
            checks = {"copy": {"ok": code == 0, "stdout": out.strip(), "stderr": err.strip()}}
            target_runtime = "claude" if runtime == "claude" else "codex"
            code, out, err = run(
                [sys.executable, str(target / "scripts" / "validate-plugin.py"),
                 "--target-runtime", target_runtime, "--strict-runtime-files"],
                target,
            )
            checks["validate_plugin"] = {"ok": code == 0, "stdout": out.strip(), "stderr": err.strip()}
            schema_runtime = "claude-code" if runtime == "claude" else "codex"
            code, out, err = run(
                [sys.executable, str(target / "scripts" / "audit-manifest-schemas.py"),
                 "--runtime", schema_runtime, "--strict-references"],
                target,
            )
            checks["manifest_schema"] = {"ok": code == 0, "stdout": out.strip(), "stderr": err.strip()}
            if runtime == "codex":
                checks["codex_mcp_present"] = {"ok": (target / ".codex.mcp.json").exists()}
            else:
                checks["claude_mcp_present"] = {"ok": (target / ".mcp.json").exists()}
            results[runtime] = {
                "ok": all(item.get("ok") for item in checks.values()),
                "target": str(target),
                "checks": checks,
            }
        output = {
            "ok": all(item["ok"] for item in results.values()),
            "temp_root": str(temp_root),
            "results": results,
        }
        print(json.dumps(output, indent=2))
        return 0 if output["ok"] else 1
    finally:
        if not args.keep:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
