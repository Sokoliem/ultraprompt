#!/usr/bin/env python3
"""Ultraprompt V8 duplication audit.

Fails the build if skills regress to V4-style inlined boilerplate.

Specifically:
1. No skill body should contain inlined DISCIPLINE.md content (only reference it).
2. No paragraph (a contiguous block of text) ≥ 5 lines should appear verbatim in 2+ skill bodies.
3. No 8-gram (sequence of 8 normalized words) should appear in more than 4 skill bodies.
4. The fraction of total cross-skill shared lines should be ≤ 10%.

This is the anti-boilerplate enforcement gate.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
DISCIPLINE_PATH = ROOT / "_shared" / "DISCIPLINE.md"

# Normalized 8-gram threshold: how many skills can share an 8-gram before it counts as boilerplate
NGRAM_SKILL_LIMIT = 4
NGRAM_N = 8

# Paragraph reuse threshold: lines per paragraph
PARA_MIN_LINES = 5

# Cross-skill shared-line budget
SHARED_LINE_BUDGET = 0.10

# Allowlisted lines: structural references intentionally identical across skills.
# These are NOT boilerplate; they are pointers to shared content by design.
ALLOWLIST_LINES = {
    "apply discipline per `${claude_plugin_root}/_shared/discipline.md` (covers `$arguments` handling, evidence, validation, and safety).",
    # V8.6: per-skill output-contract reference. Two variants (evidence-led, concise-review)
    # are pointers to the shared OUTPUT-CONTRACT.md doc + the matching output-style file.
    "schema below + `${claude_plugin_root}/_shared/output-contract.md` + `evidence-led` style.",
    "schema below + `${claude_plugin_root}/_shared/output-contract.md` + `concise-review` style.",
    # Standard section headings — structural, identical across all skills by design.
    "## failure modes specific to this lane",
    "## first signals to inspect",
    "## distinctive judgment",
    "## subagent delegation",
    "## output contract",
    "## validation",
    "## workflow",
    "## dispatch policy (v8)",
    "## v4 aliases",
}
# Allowlisted line *prefixes*: short, schema-structural YAML rows that are stable across skills
# because the schema dialect itself is stable (V8.6 OUTPUT-CONTRACT.md defines it). Also
# whitelists the V8.6 evidence-rule vocabulary — these are *shared rules*, not duplicated prose.
ALLOWLIST_PREFIXES = (
    "    type: ",
    "    required: ",
    "evidence_rule: ",
)


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    return text[end + 5:]


def normalize(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().lower())


def tokenize(text: str) -> list[str]:
    text = strip_frontmatter(text)
    text = re.sub(r"`[^`]*`", " ", text)  # strip inline code
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return text.split()


def ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def paragraphs(text: str) -> list[list[str]]:
    body = strip_frontmatter(text)
    paras: list[list[str]] = []
    current: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                paras.append(current)
                current = []
        else:
            if stripped.startswith("#") or stripped.startswith("- ") or re.match(r"^\d+\.\s", stripped):
                # Skip headings, bullets, numbered list items - they're structural
                if current:
                    paras.append(current)
                    current = []
                continue
            current.append(normalize(stripped))
    if current:
        paras.append(current)
    return paras


def main() -> int:
    if not SKILLS_DIR.exists():
        print("ERROR: skills/ not found", file=sys.stderr)
        return 1

    errors: list[str] = []
    warnings: list[str] = []

    # Load discipline content for inline check
    discipline_text = DISCIPLINE_PATH.read_text(encoding="utf-8") if DISCIPLINE_PATH.exists() else ""
    discipline_paragraphs: set[str] = set()
    for para in paragraphs(discipline_text):
        if len(para) >= 3:
            discipline_paragraphs.add("\n".join(para))

    # Load skills
    skills: dict[str, str] = {}
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        sm = skill_dir / "SKILL.md"
        if not sm.exists():
            continue
        skills[skill_dir.name] = sm.read_text(encoding="utf-8")

    print(f"Ultraprompt V8 duplication audit ({len(skills)} skills)")

    # 1. Inlined DISCIPLINE check
    inlined_count = 0
    for name, text in skills.items():
        for dp in discipline_paragraphs:
            if dp in "\n".join(normalize(line) for line in strip_frontmatter(text).splitlines()):
                errors.append(f"{name}: inlines DISCIPLINE.md content (paragraph match)")
                inlined_count += 1
                break

    # 2. Paragraph reuse check
    para_owners: dict[str, list[str]] = {}
    for name, text in skills.items():
        for para in paragraphs(text):
            if len(para) >= PARA_MIN_LINES:
                key = "\n".join(para)
                para_owners.setdefault(key, []).append(name)
    for para, owners in para_owners.items():
        if len(set(owners)) >= 2:
            errors.append(f"paragraph reused across {len(set(owners))} skills: {sorted(set(owners))}")

    # 3. 8-gram reuse check
    ngram_owners: dict[str, set[str]] = {}
    for name, text in skills.items():
        tokens = tokenize(text)
        for ng in set(ngrams(tokens, NGRAM_N)):
            ngram_owners.setdefault(ng, set()).add(name)
    overshared_ngrams = [(ng, owners) for ng, owners in ngram_owners.items() if len(owners) > NGRAM_SKILL_LIMIT]
    overshared_ngrams.sort(key=lambda x: -len(x[1]))
    if overshared_ngrams:
        for ng, owners in overshared_ngrams[:5]:
            warnings.append(f"8-gram in {len(owners)} skills (limit {NGRAM_SKILL_LIMIT}): {ng!r}")
        if len(overshared_ngrams) > 5:
            warnings.append(f"... and {len(overshared_ngrams) - 5} more overshared 8-grams")

    # 4. Cross-skill shared-line budget
    line_counts: Counter[str] = Counter()
    line_skill_owners: dict[str, set[str]] = {}
    total_lines = 0
    for name, text in skills.items():
        body = strip_frontmatter(text)
        for line in body.splitlines():
            n = normalize(line)
            if not n or len(n) < 30:
                continue
            if n in ALLOWLIST_LINES:
                continue
            if any(n.startswith(p) for p in ALLOWLIST_PREFIXES):
                continue
            line_counts[n] += 1
            line_skill_owners.setdefault(n, set()).add(name)
            total_lines += 1
    shared_lines = sum(c for line, c in line_counts.items() if len(line_skill_owners.get(line, set())) >= 2)
    shared_fraction = shared_lines / total_lines if total_lines else 0.0
    print(f"- Total significant lines: {total_lines}")
    print(f"- Cross-skill shared lines: {shared_lines} ({shared_fraction:.1%}, budget {SHARED_LINE_BUDGET:.0%})")
    if shared_fraction > SHARED_LINE_BUDGET:
        errors.append(f"shared-line fraction {shared_fraction:.1%} exceeds budget {SHARED_LINE_BUDGET:.0%}")

    print(f"- Inlined-discipline violations: {inlined_count}")
    print(f"- Reused paragraphs (5+ lines, in 2+ skills): {sum(1 for owners in para_owners.values() if len(set(owners)) >= 2)}")
    print(f"- Overshared 8-grams (>{NGRAM_SKILL_LIMIT} skills): {len(overshared_ngrams)}")
    print(f"- Warnings: {len(warnings)}")
    print(f"- Errors: {len(errors)}")
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
