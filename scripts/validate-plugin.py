#!/usr/bin/env python3
"""Validate the Ultraprompt V8 Claude Code + Codex plugin package.

Checks structure, JSON, YAML frontmatter, naming, duplicate names, hook scripts,
commands, output styles, marketplace metadata, runtime neutrality, and tier
assignment. Dependency-free.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

SUPPORTED_SKILL_FIELDS = {
    "name", "description", "when_to_use", "argument-hint", "arguments",
    "disable-model-invocation", "user-invocable", "allowed-tools",
    "model", "effort", "context", "agent", "hooks", "paths", "shell",
    "tier", "aliases",
}
SUPPORTED_OUTPUT_STYLE_FIELDS = {"name", "description", "keep-coding-instructions"}
SUPPORTED_TIERS = {"core", "specialist", "ecosystem"}
REQUIRED_AGENT_FIELDS = {"name", "description"}
VALID_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("missing closing frontmatter delimiter")
    raw = text[4:end]
    body = text[end + 5:]
    data: dict[str, str] = {}
    current_key: str | None = None
    current_value: list[str] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        if re.match(r"^[A-Za-z0-9_-]+:\s*", line):
            if current_key is not None:
                data[current_key] = "\n".join(current_value).strip()
            key, value = line.split(":", 1)
            current_key = key.strip()
            current_value = [value.strip()]
        elif current_key is not None:
            current_value.append(line)
    if current_key is not None:
        data[current_key] = "\n".join(current_value).strip()
    return data, body


def check(condition: bool, message: str, bucket: list[str]) -> None:
    if not condition:
        bucket.append(message)


def load_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{path.relative_to(ROOT)}: not found")
        return None
    except json.JSONDecodeError as exc:
        errors.append(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
        return None


def claude_plugin_root_target(cmd: str) -> Path | None:
    marker = "${CLAUDE_PLUGIN_ROOT}"
    if marker not in cmd:
        return None
    tail = cmd.split(marker, 1)[1].lstrip("/\\")
    match = re.match(r'(?P<rel>[^"\']+?)(?:["\']|\s|$)', tail)
    if not match:
        return None
    rel = match.group("rel").replace("\\", "/").strip()
    return ROOT / rel


def clean(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        v = v[1:-1]
    return v.strip()


def split_list_field(value: str) -> set[str]:
    return {item.strip() for item in clean(value).split(",") if item.strip()}


def validate_skills(errors: list[str], warnings: list[str]) -> tuple[int, dict[str, int]]:
    skills_dir = ROOT / "skills"
    if not skills_dir.exists():
        warnings.append("skills/ directory not present")
        return 0, {}
    seen: set[str] = set()
    tier_counts = {"core": 0, "specialist": 0, "ecosystem": 0}
    count = 0
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        target = skill_dir / "SKILL.md"
        if not target.exists():
            errors.append(f"skills/{skill_dir.name}/SKILL.md: missing")
            continue
        try:
            data, body = parse_frontmatter(target)
        except Exception as exc:
            errors.append(f"skills/{skill_dir.name}/SKILL.md: {exc}")
            continue
        name = clean(data.get("name", ""))
        check(name == skill_dir.name, f"skills/{skill_dir.name}: name mismatch ({name!r})", errors)
        check(VALID_NAME.match(name) is not None, f"skills/{skill_dir.name}: invalid name {name!r}", errors)
        check(name not in seen, f"skills/{skill_dir.name}: duplicate name", errors)
        seen.add(name)
        for field in data.keys():
            if field not in SUPPORTED_SKILL_FIELDS:
                warnings.append(f"skills/{name}/SKILL.md: unsupported frontmatter field {field!r}")
        check(bool(clean(data.get("description", ""))), f"skills/{name}: empty description", errors)
        check(bool(clean(data.get("when_to_use", ""))), f"skills/{name}: empty when_to_use", errors)
        # V8: tier required
        tier = clean(data.get("tier", ""))
        if tier not in SUPPORTED_TIERS:
            errors.append(f"skills/{name}: tier must be one of {sorted(SUPPORTED_TIERS)}; got {tier!r}")
        else:
            tier_counts[tier] += 1
        # Runtime-neutrality: no model/effort overrides
        if "model" in data:
            errors.append(f"skills/{name}: model pin not allowed (Ultraprompt is runtime-neutral)")
        if "effort" in data:
            errors.append(f"skills/{name}: effort pin not allowed (Ultraprompt is runtime-neutral)")
        # Body must reference DISCIPLINE.md
        if "_shared/DISCIPLINE.md" not in body:
            warnings.append(f"skills/{name}: body does not reference DISCIPLINE.md")
        count += 1
    return count, tier_counts


def validate_agents(errors: list[str], warnings: list[str]) -> int:
    agents_dir = ROOT / "agents"
    if not agents_dir.exists():
        warnings.append("agents/ directory not present")
        return 0
    seen: set[str] = set()
    count = 0
    for agent_path in sorted(agents_dir.glob("*.md")):
        try:
            data, _ = parse_frontmatter(agent_path)
        except Exception as exc:
            errors.append(f"{agent_path.relative_to(ROOT)}: {exc}")
            continue
        name = clean(data.get("name", ""))
        check(VALID_NAME.match(name) is not None, f"{agent_path.relative_to(ROOT)}: invalid name {name!r}", errors)
        check(name not in seen, f"{agent_path.relative_to(ROOT)}: duplicate name", errors)
        seen.add(name)
        for field in REQUIRED_AGENT_FIELDS:
            check(field in data, f"{agent_path.relative_to(ROOT)}: missing required field {field}", errors)
        if "model" in data:
            errors.append(f"{agent_path.relative_to(ROOT)}: model pin not allowed")
        if "effort" in data:
            errors.append(f"{agent_path.relative_to(ROOT)}: effort pin not allowed")
        tools = split_list_field(data.get("tools", ""))
        disallowed_tools = split_list_field(data.get("disallowedTools", ""))
        overlap = sorted(tools & disallowed_tools)
        if overlap:
            errors.append(
                f"{agent_path.relative_to(ROOT)}: tools also appear in disallowedTools: "
                f"{', '.join(overlap)}"
            )
        count += 1
    return count


def validate_commands(errors: list[str], warnings: list[str]) -> int:
    cmds_dir = ROOT / "commands"
    if not cmds_dir.exists():
        return 0
    count = 0
    for cmd_path in sorted(cmds_dir.glob("*.md")):
        try:
            data, _ = parse_frontmatter(cmd_path)
        except Exception as exc:
            errors.append(f"{cmd_path.relative_to(ROOT)}: {exc}")
            continue
        check(bool(clean(data.get("description", ""))), f"{cmd_path.relative_to(ROOT)}: empty description", errors)
        count += 1
    return count


def validate_output_styles(errors: list[str], warnings: list[str]) -> int:
    styles_dir = ROOT / "output-styles"
    if not styles_dir.exists():
        return 0
    count = 0
    for style_path in sorted(styles_dir.glob("*.md")):
        try:
            data, _ = parse_frontmatter(style_path)
        except Exception as exc:
            errors.append(f"{style_path.relative_to(ROOT)}: {exc}")
            continue
        for field in data.keys():
            if field not in SUPPORTED_OUTPUT_STYLE_FIELDS:
                warnings.append(f"{style_path.relative_to(ROOT)}: unsupported field {field!r}")
        count += 1
    return count


def validate_hooks(errors: list[str], warnings: list[str]) -> int:
    hooks_path = ROOT / "hooks" / "hooks.json"
    if not hooks_path.exists():
        warnings.append("hooks/hooks.json not present")
        return 0
    data = load_json(hooks_path, errors)
    if not data:
        return 0
    count = 0
    for event_name, event_hooks in (data.get("hooks") or {}).items():
        for entry in event_hooks:
            for hook in entry.get("hooks", []):
                cmd = hook.get("command", "")
                target = claude_plugin_root_target(cmd)
                if target is not None and not target.exists():
                    errors.append(
                        f"hooks/hooks.json: {event_name} hook references missing script "
                        f"{target.relative_to(ROOT)}"
                    )
                count += 1
    return count


def runtime_manifest_paths(target_runtime: str) -> list[Path]:
    if target_runtime == "claude":
        return [ROOT / ".claude-plugin" / "plugin.json"]
    if target_runtime == "codex":
        return [ROOT / ".codex-plugin" / "plugin.json"]
    return [
        ROOT / ".claude-plugin" / "plugin.json",
        ROOT / ".codex-plugin" / "plugin.json",
    ]


def manifest_label(path: Path) -> str:
    if ".codex-plugin" in path.parts:
        return "codex"
    return "claude"


def validate_manifest(path: Path, errors: list[str], warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{path.relative_to(ROOT)}: missing")
        return {}
    data = load_json(path, errors) or {}
    for field in ("name", "version", "description"):
        if field not in data:
            errors.append(f"{path.relative_to(ROOT)}: missing {field}")
    return data


def validate_manifest_referenced_files(path: Path, manifest: dict[str, Any], errors: list[str]) -> None:
    mcp_ref = manifest.get("mcpServers")
    if isinstance(mcp_ref, str):
        rel = mcp_ref[2:] if mcp_ref.startswith("./") else mcp_ref
        target = ROOT / rel
        if not target.exists():
            errors.append(
                f"{path.relative_to(ROOT)}: references missing MCP config {mcp_ref}"
            )
    hooks_ref = manifest.get("hooks")
    if isinstance(hooks_ref, str):
        rel = hooks_ref[2:] if hooks_ref.startswith("./") else hooks_ref
        target = ROOT / rel
        if not target.exists():
            errors.append(
                f"{path.relative_to(ROOT)}: references missing hooks config {hooks_ref}"
            )
    styles_ref = manifest.get("outputStyles")
    if isinstance(styles_ref, str):
        rel = styles_ref[2:] if styles_ref.startswith("./") else styles_ref
        target = ROOT / rel
        if not target.exists():
            errors.append(
                f"{path.relative_to(ROOT)}: references missing output styles path {styles_ref}"
            )


def validate_marketplace(errors: list[str], warnings: list[str]) -> bool:
    path = ROOT / ".claude-plugin" / "marketplace.json"
    if not path.exists():
        warnings.append(".claude-plugin/marketplace.json: missing (optional)")
        return False
    data = load_json(path, errors) or {}
    return bool(data.get("plugins"))


def validate_mcp_file(path: Path, errors: list[str], warnings: list[str]) -> int:
    if not path.exists():
        warnings.append(f"{path.relative_to(ROOT)}: missing")
        return 0
    data = load_json(path, errors) or {}
    return len(data.get("mcpServers") or {})


def validate_mcp(target_runtime: str, errors: list[str], warnings: list[str]) -> int:
    paths = []
    if target_runtime in ("source", "claude"):
        paths.append(ROOT / ".mcp.json")
    if target_runtime in ("source", "codex"):
        paths.append(ROOT / ".codex.mcp.json")
    return sum(validate_mcp_file(path, errors, warnings) for path in paths)


def validate_index(errors: list[str], warnings: list[str]) -> bool:
    path = ROOT / "dist" / "skill-index.json"
    if not path.exists():
        warnings.append("dist/skill-index.json: missing (run scripts/build-skill-index.py)")
        return False
    data = load_json(path, errors)
    return bool(data)


def validate_generated_artifacts(errors: list[str], warnings: list[str]) -> None:
    checks = [
        ["build-skill-index.py", "--check"],
        ["build-catalog-metadata.py", "--check"],
        ["regenerate-skills.py", "--check"],
        ["regenerate-agents.py", "--check"],
        ["audit-catalog-consistency.py"],
    ]
    for check_args in checks:
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / check_args[0]), *check_args[1:]],
                              cwd=ROOT, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            detail = (proc.stdout or proc.stderr).strip().splitlines()
            suffix = f": {detail[0]}" if detail else ""
            errors.append(f"{' '.join(check_args)} failed{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target-runtime",
        default="source",
        choices=["source", "claude", "codex"],
        help="Validate source manifests or one installed runtime target.",
    )
    parser.add_argument(
        "--strict-runtime-files",
        action="store_true",
        help="Accepted for compatibility; manifest-referenced files are always strict in V8.2.",
    )
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    manifests: dict[str, dict[str, Any]] = {}
    for manifest_path in runtime_manifest_paths(args.target_runtime):
        manifest = validate_manifest(manifest_path, errors, warnings)
        if manifest:
            validate_manifest_referenced_files(manifest_path, manifest, errors)
        manifests[manifest_label(manifest_path)] = manifest

    display_manifest = manifests.get("claude") or manifests.get("codex") or {}
    skill_count, tier_counts = validate_skills(errors, warnings)
    agent_count = validate_agents(errors, warnings)
    cmd_count = validate_commands(errors, warnings)
    style_count = validate_output_styles(errors, warnings)
    hook_count = validate_hooks(errors, warnings)
    market = validate_marketplace(errors, warnings)
    mcp_count = validate_mcp(args.target_runtime, errors, warnings)
    has_index = validate_index(errors, warnings)
    validate_generated_artifacts(errors, warnings)

    print("Ultraprompt V8.2 plugin validation")
    print(f"- Target runtime: {args.target_runtime}")
    print(f"- Plugin: {display_manifest.get('name', '?')} v{display_manifest.get('version', '?')}")
    print(f"- Skills: {skill_count} (core: {tier_counts.get('core', 0)}, specialist: {tier_counts.get('specialist', 0)}, ecosystem: {tier_counts.get('ecosystem', 0)})")
    print(f"- Commands: {cmd_count}")
    print(f"- Agents: {agent_count}")
    print(f"- Output styles: {style_count}")
    print(f"- Registered hooks: {hook_count}")
    print(f"- Marketplace: {'yes' if market else 'no'}")
    print(f"- MCP servers: {mcp_count}")
    print(f"- Skill index: {'yes' if has_index else 'no'}")
    print(f"- Warnings: {len(warnings)}")
    print(f"- Errors: {len(errors)}")
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
