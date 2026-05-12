#!/usr/bin/env python3
"""V8 schema audit: validates Claude/Codex manifests and MCP shape.

Runtime-aware: pass --runtime claude-code (default) or --runtime codex.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rel_target(root: Path, ref: str) -> Path:
    rel = ref[2:] if ref.startswith("./") else ref
    return root / rel


def check_plugin_json(path, errors, warnings, *, strict_references=True):
    if not path.exists():
        errors.append(f"{path}: missing"); return
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        errors.append(f"{path}: invalid JSON ({e})"); return
    for f in ["name", "version", "description"]:
        if f not in data:
            errors.append(f"{path}: missing required field '{f}'")
    plugin_root = path.parent.parent
    if (plugin_root / ".mcp.json").exists() and "mcpServers" not in data:
        errors.append(f"{path}: .mcp.json exists but plugin.json missing 'mcpServers' field. "
                      'Add: "mcpServers": "./.mcp.json"')
    if strict_references:
        for field in ("mcpServers", "hooks", "outputStyles"):
            ref = data.get(field)
            if (
                field == "hooks"
                and isinstance(ref, str)
                and ref.removeprefix("./") == "hooks/hooks.json"
                and ".claude-plugin" in path.parts
            ):
                errors.append(
                    f"{path}: hooks references {ref}; Claude Code auto-loads hooks/hooks.json, "
                    "so this duplicate manifest reference prevents plugin load"
                )
            if isinstance(ref, str) and not rel_target(plugin_root, ref).exists():
                errors.append(f"{path}: {field} references missing path {ref}")


def check_mcp_json(path, runtime, errors, warnings):
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        errors.append(f"{path}: invalid JSON ({e})"); return
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        errors.append(f"{path}: top-level 'mcpServers' must be an object"); return
    for sname, scfg in servers.items():
        if not isinstance(scfg, dict):
            errors.append(f"{path}:{sname}: server config must be an object"); continue
        if "command" not in scfg:
            errors.append(f"{path}:{sname}: missing 'command'")
        allowed = {"claude-code": {"command", "args", "env"},
                   "codex": {"command", "args", "env", "cwd"}}
        unknown = set(scfg.keys()) - allowed[runtime]
        for u in unknown:
            if u == "cwd" and runtime == "claude-code":
                errors.append(f"{path}:{sname}: 'cwd' field not supported by Claude Code. "
                              "Remove it. (Codex variant should be in .codex.mcp.json)")
            else:
                warnings.append(f"{path}:{sname}: field '{u}' may not be supported by {runtime}")
        if runtime == "claude-code":
            for a in scfg.get("args", []):
                if isinstance(a, str) and a.startswith("./"):
                    warnings.append(f"{path}:{sname}: relative arg '{a}' won't resolve in Claude Code "
                                    "without ${CLAUDE_PLUGIN_ROOT} prefix")


def main():
    import os
    # V8: auto-detect runtime from script location
    script_path = str(Path(__file__).resolve()).lower()
    auto_runtime = "codex" if (".codex" in script_path or "/codex/" in script_path or "\\codex\\" in script_path) else "claude-code"
    p = argparse.ArgumentParser()
    p.add_argument("--runtime", default=auto_runtime, choices=["claude-code", "codex"],
                   help=f"Override runtime (auto-detected from path: {auto_runtime})")
    p.add_argument("--strict-references", action="store_true",
                   help="Accepted for compatibility; declared manifest references are strict in V8.2.")
    args = p.parse_args()
    errors, warnings = [], []
    print(f"Ultraprompt V8 manifest + MCP schema audit (runtime: {args.runtime})")
    print("=" * 50)
    check_plugin_json(ROOT / ".claude-plugin" / "plugin.json", errors, warnings)
    if (ROOT / ".codex-plugin" / "plugin.json").exists():
        check_plugin_json(ROOT / ".codex-plugin" / "plugin.json", errors, warnings)
    check_mcp_json(ROOT / ".mcp.json", args.runtime, errors, warnings)
    # If a .codex.mcp.json sibling exists (in the source tree), audit it as Codex too
    if (ROOT / ".codex.mcp.json").exists():
        check_mcp_json(ROOT / ".codex.mcp.json", "codex", errors, warnings)
    for w in warnings: print(f"  WARN: {w}", file=sys.stderr)
    for e in errors: print(f"  ERR : {e}", file=sys.stderr)
    if errors:
        print(f"\nFAIL: {len(errors)} error(s), {len(warnings)} warning(s)", file=sys.stderr)
        return 1
    print(f"OK: 0 errors, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
