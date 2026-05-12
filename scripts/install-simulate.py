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


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def catalog_counts(root: Path) -> dict[str, int | None]:
    return {
        "skill_count": sum(1 for p in (root / "skills").iterdir() if p.is_dir()) if (root / "skills").exists() else None,
        "agent_count": sum(1 for p in (root / "agents").glob("*.md")) if (root / "agents").exists() else None,
        "command_count": sum(1 for p in (root / "commands").glob("*.md")) if (root / "commands").exists() else None,
    }


def manifest_for(root: Path, runtime: str) -> Path:
    return root / (".codex-plugin" if runtime == "codex" else ".claude-plugin") / "plugin.json"


def source_expected() -> dict:
    source_manifest = load_json(ROOT / ".claude-plugin" / "plugin.json")
    return {"version": source_manifest.get("version"), **catalog_counts(ROOT)}


def parity_status(target: Path, runtime: str, expected: dict) -> dict:
    manifest = manifest_for(target, runtime)
    data = load_json(manifest)
    counts = catalog_counts(target)
    findings = []
    version = data.get("version")
    if version != expected.get("version"):
        findings.append(f"version {version} != source {expected.get('version')}")
    for field in ("skill_count", "agent_count", "command_count"):
        if counts.get(field) != expected.get(field):
            findings.append(f"{field} {counts.get(field)} != source {expected.get(field)}")
    return {
        "ok": not findings,
        "runtime": runtime,
        "path": str(target),
        "version": version,
        **counts,
        "expected": expected,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", choices=["claude", "codex", "both"], default="both")
    parser.add_argument("--keep", action="store_true", help="Keep temp directory for inspection")
    args = parser.parse_args()

    runtimes = ["claude", "codex"] if args.runtime == "both" else [args.runtime]
    results = {}
    expected = source_expected()
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
            parity = parity_status(target, runtime, expected)
            checks["runtime_parity"] = {"ok": parity["ok"], "findings": parity["findings"]}
            results[runtime] = {
                "ok": all(item.get("ok") for item in checks.values()),
                "target": str(target),
                "runtime_target_status": parity,
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
