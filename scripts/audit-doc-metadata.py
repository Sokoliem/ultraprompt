#!/usr/bin/env python3
"""Check current-state docs and runtime descriptions for stale catalog metadata."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "dist" / "catalog-metadata.json"
_CLAUDE_MD = ROOT / "CLAUDE.md" if (ROOT / "CLAUDE.md").exists() else ROOT / "docs" / "CLAUDE.md"
FILES = [
    ROOT / "README.md",
    _CLAUDE_MD,
    ROOT / "commands" / "menu.md",
    ROOT / "commands" / "dashboard.md",
    ROOT / "mcp" / "ultraprompt_meta.py",
    # V9.0 R4: session-start-context.sh removed; banner now in session-bootstrap.py
    ROOT / "hooks" / "recipes" / "session-bootstrap.py",
]


def main() -> int:
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    counts = metadata["counts"]
    version = metadata["plugin_version"]
    required = [
        version,
        f"{counts['skills']} skills",
        f"{counts['agents']} agents",
        f"{counts['mcp_tools']} MCP tools",
        f"{counts['commands']} commands",
    ]
    stale_patterns = [
        r"\bV[5]\b\s+(?:plugin|command|menu|doctor|runtime|release|active)",
        r"\bV[6]\b\s+(?:plugin|command|menu|doctor|runtime|release|active)",
        r"\bV[7](?:\.\d+(?:\.\d+)?)?\b\s+(?:active|foundation|catalog|new|additions|core)",
        r"\b32 skills\b",
        r"\b9 agents\b",
        r"\b2[4] agents\b",
        r"\b17 MCP tools\b",
        r"\b26 MCP tools\b",
        r"\b2[3] commands\b",
        r"\b1[3] artifact schemas\b",
        r"\b22 commands\b",
    ]
    findings = []
    for path in FILES:
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(ROOT))
        if rel in ("README.md", "CLAUDE.md", "docs\\CLAUDE.md", "docs/CLAUDE.md"):
            for token in required:
                if token not in text:
                    findings.append({"file": rel, "issue": "missing_current_metadata", "token": token})
        for pattern in stale_patterns:
            for match in re.finditer(pattern, text):
                findings.append({"file": rel, "issue": "stale_metadata", "match": match.group(0)})
    result = {"ok": not findings, "version": version, "findings": findings}
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
