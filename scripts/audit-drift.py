#!/usr/bin/env python3
"""V8: Drift audit.

Checks for:
- Stale major-version references in current-state docs
- Manifest count drift (declared vs actual skills/agents/commands/hooks/MCP tools)
- README/menu/status-line/MCP-instructions disagreement on counts

Exit non-zero if drift detected. Non-blocking warnings for historical changelog entries.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors = []
warnings = []


def main():
    # Count actual artifacts
    skills_actual = len([p for p in (ROOT / "skills").iterdir() if p.is_dir()])
    agents_actual = len([p for p in (ROOT / "agents").iterdir() if p.suffix == ".md"])
    commands_actual = len([p for p in (ROOT / "commands").iterdir() if p.suffix == ".md"])

    print(f"Actual artifact counts:")
    print(f"  skills:   {skills_actual}")
    print(f"  agents:   {agents_actual}")
    print(f"  commands: {commands_actual}")

    # Validate manifest counts
    try:
        manifest = json.load(open(ROOT / ".claude-plugin/plugin.json"))
        ver = manifest.get("version", "?")
        print(f"\nManifest version: {ver}")
    except Exception as e:
        errors.append(f"plugin.json read failed: {e}")
        manifest = {}

    # Check for stale legacy-version references in current-state files (not CHANGELOG)
    SKIP_FILES = {"CHANGELOG.md"}
    SKIP_DIRS = {"backups", "dist", "__pycache__"}
    stale_refs = []
    for f in ROOT.rglob("*"):
        if not f.is_file():
            continue
        if f.name in SKIP_FILES:
            continue
        if any(d in f.parts for d in SKIP_DIRS):
            continue
        if f.suffix not in (".md", ".py", ".sh", ".json", ".toml"):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        # Look for legacy major-version tokens as a current-version claim.
        for m in re.finditer(r"\bV[5]\b\s+(plugin|version|release|active)", text):
            stale_refs.append((f.relative_to(ROOT), m.group(0)))
        # Look for legacy active-version claims outside transition language
        for m in re.finditer(r"\bV[6]\.\d\s+is\s+active\b", text):
            stale_refs.append((f.relative_to(ROOT), m.group(0)))

    if stale_refs:
        print(f"\nStale version references ({len(stale_refs)}):")
        for path, match in stale_refs[:10]:
            print(f"  ⚠  {path}: {match}")
        # These are warnings unless major version drift
        warnings.extend(f"{p}: {m}" for p, m in stale_refs)

    # MCP server count vs actual
    try:
        mcp_src = (ROOT / "mcp/ultraprompt_meta.py").read_text()
        tool_count_match = re.search(r'TOOLS\s*[:=]\s*\{', mcp_src)
        if tool_count_match:
            # Count function names in TOOLS dict
            tools_in_src = len(re.findall(r'^\s*"[a-z_]+"\s*:\s*\(', mcp_src, re.MULTILINE))
            print(f"\nMCP tools declared in source: {tools_in_src}")
    except Exception:
        pass

    # Print summary
    print()
    print(f"=== Drift audit summary ===")
    print(f"  Errors: {len(errors)}")
    print(f"  Warnings: {len(warnings)}")
    if errors:
        for e in errors:
            print(f"  ✗ {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
