#!/usr/bin/env python3
"""Audit Ultraprompt V8 skill tier assignments.

Verifies:
- Every skill has a tier
- Tier is one of {core, specialist, ecosystem}
- Tier counts match the V8 spec (28 core, 15 specialist, 5 ecosystem)
- Specialist and ecosystem skills have disable-model-invocation: true
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COUNTS = {"core": 28, "specialist": 15, "ecosystem": 5}  # V8 release profile


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    raw = text[4:end]
    data: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip() or not re.match(r"^[A-Za-z0-9_-]+:\s*", line):
            continue
        key, value = line.split(":", 1)
        v = value.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
            v = v[1:-1]
        data[key.strip()] = v.strip()
    return data


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    counts = {"core": 0, "specialist": 0, "ecosystem": 0}
    skills_dir = ROOT / "skills"
    if not skills_dir.exists():
        print("ERROR: skills/ not found", file=sys.stderr)
        return 1

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            errors.append(f"{skill_dir.name}: SKILL.md missing")
            continue
        data = parse_frontmatter(skill_md)
        tier = data.get("tier", "")
        if tier not in counts:
            errors.append(f"{skill_dir.name}: invalid tier {tier!r}")
            continue
        counts[tier] += 1
        if tier in ("specialist", "ecosystem"):
            disable = data.get("disable-model-invocation", "false").lower()
            if disable not in ("true", "1"):
                errors.append(f"{skill_dir.name}: tier={tier} requires disable-model-invocation: true")

    print("Ultraprompt V8 skill-tier audit")
    print(f"- core: {counts['core']} (expected {EXPECTED_COUNTS['core']})")
    print(f"- specialist: {counts['specialist']} (expected {EXPECTED_COUNTS['specialist']})")
    print(f"- ecosystem: {counts['ecosystem']} (expected {EXPECTED_COUNTS['ecosystem']})")
    for tier, expected in EXPECTED_COUNTS.items():
        if counts[tier] != expected:
            warnings.append(f"tier {tier}: count {counts[tier]} != expected {expected}")
    print(f"- Warnings: {len(warnings)}")
    print(f"- Errors: {len(errors)}")
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
