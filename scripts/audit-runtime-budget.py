#!/usr/bin/env python3
"""Audit Ultraprompt V8 for runtime profile pins (model, effort, long-context, extra-usage).

Ultraprompt is runtime-neutral: the active session controls the runtime profile. This audit
fails the build if any frontmatter or text file pins runtime behavior.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Frontmatter fields that pin runtime behavior. These are forbidden everywhere.
FORBIDDEN_FRONTMATTER = ("model:", "effort:", "context:")

# Text patterns that suggest runtime pinning advice. Looked for in body text.
SUSPICIOUS_TEXT = [
    re.compile(r"\bmodel:\s*opus\b", re.IGNORECASE),
    re.compile(r"\bmodel:\s*sonnet\b", re.IGNORECASE),
    re.compile(r"\beffort:\s*high\b", re.IGNORECASE),
    re.compile(r"\beffort:\s*ultra\b", re.IGNORECASE),
    re.compile(r"\blong-context:\s*true\b", re.IGNORECASE),
    re.compile(r"\bextra-usage:\s*true\b", re.IGNORECASE),
]

# Files we audit
AUDIT_GLOBS = [
    "skills/**/*.md",
    "agents/*.md",
    "commands/*.md",
    "output-styles/*.md",
    "_shared/**/*.md",
]

# Allowlisted paths: source specs may discuss model selection conceptually
ALLOWLIST_DIRS = {
    ROOT / "source",
    ROOT / "tests",
}


def audit_file(path: Path, errors: list[str], warnings: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(ROOT)
    # Frontmatter check
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            frontmatter = text[4:end]
            for forbidden in FORBIDDEN_FRONTMATTER:
                for line in frontmatter.splitlines():
                    if line.strip().startswith(forbidden):
                        errors.append(f"{rel}: forbidden frontmatter field {forbidden.rstrip(':')!r}")
            body = text[end + 5:]
        else:
            body = text
    else:
        body = text
    # Body text check - warn only (these are sometimes legitimate documentation)
    for pat in SUSPICIOUS_TEXT:
        m = pat.search(body)
        if m:
            warnings.append(f"{rel}: suspicious runtime hint: {m.group(0)!r}")


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    files_checked = 0
    for glob in AUDIT_GLOBS:
        for path in ROOT.glob(glob):
            if not path.is_file():
                continue
            if any(str(path).startswith(str(d)) for d in ALLOWLIST_DIRS):
                continue
            audit_file(path, errors, warnings)
            files_checked += 1
    print("Ultraprompt V8 runtime-budget audit")
    print(f"- Files checked: {files_checked}")
    print(f"- Warnings: {len(warnings)}")
    print(f"- Errors: {len(errors)}")
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
