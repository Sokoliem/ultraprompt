#!/usr/bin/env python3
"""Regenerate Ultraprompt skill bodies from canonical specs.

Run: python3 scripts/regenerate-skills.py [--check]

Each SKILL.md contains only skill-specific specialty content. Shared discipline
lives in `_shared/DISCIPLINE.md` and is referenced once. No inlined boilerplate.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "source" / "skill-specs.json"
SKILLS_DIR = ROOT / "skills"


def yaml_quote(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def yaml_value(value: Any) -> str:
    if isinstance(value, list):
        if not value:
            return "[]"
        return "[" + ", ".join(yaml_quote(v) for v in value) + "]"
    return yaml_quote(value)


def numbered_list(items: list[str]) -> str:
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items, start=1))


def bulleted_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def build_skill(spec: dict[str, Any]) -> str:
    name = spec["name"]
    tier = spec["tier"]
    aliases = spec.get("aliases", [])

    front: dict[str, Any] = {
        "name": name,
        "description": spec["description"],
        "when_to_use": spec["when_to_use"],
        "argument-hint": spec["argument_hint"],
        "tier": tier,
    }
    if aliases:
        front["aliases"] = aliases
    if tier in ("specialist", "ecosystem"):
        front["disable-model-invocation"] = True
    if spec.get("editing"):
        front["allowed-tools"] = "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
    else:
        front["allowed-tools"] = "Read, Grep, Glob, Bash, Agent"

    lines = ["---"]
    for key, value in front.items():
        lines.append(f"{key}: {yaml_value(value)}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {spec['title']}")
    lines.append("")
    lines.append(
        "Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety)."
    )
    lines.append("")

    # V8: DISPATCH POLICY — for skills with a corresponding specialist agent.
    dispatch = spec.get("dispatch_to")
    if dispatch:
        agent = dispatch["agent"]
        focus = dispatch.get("focus")
        focus_from = dispatch.get("focus_from")
        phase = dispatch.get("phase", "full")  # 'full' (whole skill) or 'analysis' (analysis phase only)

        lines.append("## Dispatch policy (V8)")
        lines.append("")
        focus_str = ""
        if focus_from == "argument":
            focus_str = " (focus derived from `$ARGUMENTS`)"
        elif focus:
            focus_str = f" (focus: `{focus}`)"
        phase_str = "" if phase == "full" else " for the analysis phase only"
        lines.append(
            f"**Dispatch target:** `ultraprompt:{agent}`{focus_str}{phase_str}. "
            f"See `${{CLAUDE_PLUGIN_ROOT}}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, "
            f"Task call template, and inline-override conditions."
        )
        lines.append("")


    lines.append("## Distinctive judgment")
    lines.append("")
    lines.append(spec["distinctive_judgment"])
    lines.append("")

    lines.append("## First signals to inspect")
    lines.append("")
    lines.append(bulleted_list(spec["first_signals"]))
    lines.append("")

    lines.append("## Failure modes specific to this lane")
    lines.append("")
    lines.append(bulleted_list(spec["failure_modes"]))
    lines.append("")

    lines.append("## Workflow")
    lines.append("")
    lines.append(numbered_list(spec["workflow_steps"]))
    lines.append("")

    lines.append("## Validation")
    lines.append("")
    lines.append(spec["validation_strategy"])
    lines.append("")

    lines.append("## Output contract")
    lines.append("")
    lines.append(spec["output_contract"])
    lines.append("")

    lines.append("## Subagent delegation")
    lines.append("")
    lines.append(spec["subagent_delegation"])
    lines.append("")

    if aliases:
        lines.append("## V4 aliases")
        lines.append("")
        alias_str = ", ".join(f"`{a}`" for a in aliases)
        lines.append(
            f"This skill answers to V4 names: {alias_str}. The router resolves them to `{name}` and notes the alias in its response."
        )
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Verify regenerated content matches on-disk content")
    args = parser.parse_args()

    if not SPECS.exists():
        print(f"ERROR: {SPECS} not found", file=sys.stderr)
        return 1

    specs = json.loads(SPECS.read_text(encoding="utf-8"))
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    seen: set[str] = set()
    drift = 0

    for spec in specs:
        name = spec["name"]
        if name in seen:
            print(f"ERROR: duplicate skill name {name!r}", file=sys.stderr)
            return 1
        seen.add(name)
        skill_dir = SKILLS_DIR / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        target = skill_dir / "SKILL.md"
        new_content = build_skill(spec)

        if args.check:
            if not target.exists():
                print(f"DRIFT: {target.relative_to(ROOT)} missing", file=sys.stderr)
                drift += 1
                continue
            current = target.read_text(encoding="utf-8")
            if current != new_content:
                print(f"DRIFT: {target.relative_to(ROOT)} differs from spec", file=sys.stderr)
                drift += 1
        else:
            target.write_text(new_content, encoding="utf-8")

    if args.check:
        if drift:
            print(f"\n{drift} skill(s) drift from specs. Run regenerate-skills.py to fix.", file=sys.stderr)
            return 1
        print(f"Verified {len(specs)} skills match specs.")
        return 0

    print(f"Regenerated {len(specs)} skills from {SPECS.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
