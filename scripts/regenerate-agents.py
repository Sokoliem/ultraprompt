#!/usr/bin/env python3
"""Regenerate packaged agent .md files from source/agent-specs.json."""
from __future__ import annotations

import json
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "source" / "agent-specs.json"
AGENTS = ROOT / "agents"


def yaml_quote(value: str) -> str:
    """Emit a value as a strict-YAML double-quoted scalar.

    `description` lines routinely contain colons, em-dashes, single quotes, and
    backticks. Strict YAML parsers (e.g., Claude Code's `plugin validate`) reject
    unquoted scalars with `: ` in them. Double-quote and escape with backslashes.
    """
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def build_agent(spec: dict) -> str:
    front = [
        "---",
        f"name: {spec['name']}",
        f"description: {yaml_quote(spec['description'])}",
    ]
    if spec.get("max_turns"):
        front.append(f"maxTurns: {spec['max_turns']}")
    if spec.get("tools"):
        front.append(f"tools: {yaml_quote(spec['tools'])}")
    if spec.get("disallowed_tools"):
        front.append(f"disallowedTools: {yaml_quote(spec['disallowed_tools'])}")
    if spec.get("color"):
        front.append(f"color: {yaml_quote(spec['color'])}")
    front.append("---")
    return "\n".join(front) + "\n" + spec["body"].rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify generated agents match source specs")
    args = parser.parse_args()

    specs = json.loads(SPECS.read_text(encoding="utf-8"))
    AGENTS.mkdir(parents=True, exist_ok=True)
    seen = set()
    stale: list[str] = []
    for spec in specs:
        name = spec["name"]
        if name in seen:
            raise SystemExit(f"Duplicate agent: {name}")
        seen.add(name)
        target = AGENTS / f"{name}.md"
        content = build_agent(spec)
        if args.check:
            if not target.exists():
                stale.append(f"{target.relative_to(ROOT)} missing")
            elif target.read_text(encoding="utf-8") != content:
                stale.append(f"{target.relative_to(ROOT)} stale")
        else:
            target.write_text(content, encoding="utf-8")
    orphaned = sorted(p for p in AGENTS.glob("*.md") if p.stem not in seen)
    if orphaned:
        stale.extend(f"{p.relative_to(ROOT)} has no source spec" for p in orphaned)
    if args.check:
        if stale:
            print("Agent generation drift:")
            for item in stale:
                print(f"- {item}")
            raise SystemExit(1)
        print(f"Verified {len(specs)} agents match specs.")
    else:
        print(f"Regenerated {len(specs)} agents.")


if __name__ == "__main__":
    main()
