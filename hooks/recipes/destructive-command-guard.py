#!/usr/bin/env python3
"""V8: Risk-classifier destructive command guard (PRD §8.7).

Classifies commands into 4 risk classes:
- LOW: read-only, status, lint — allow
- MEDIUM: targeted removal, package install, migration dry-run — record + allow
- HIGH: rm -rf, git reset --hard, git clean -fdx, force push — block (unless override)
- CRITICAL: home/root destruction, secrets exfiltration, broad destructive chain — block always

Override: ULTRAPROMPT_DISABLE_HOOKS=1 disables ALL hooks (use sparingly).
Override: ULTRAPROMPT_ALLOW_HIGH_RISK=1 allows HIGH but not CRITICAL.

Fail-open on errors. Records all classifications to V8 ledger for evidence.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

if os.environ.get("ULTRAPROMPT_DISABLE_HOOKS") == "1":
    sys.exit(0)

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)

command = str(payload.get("tool_input", {}).get("command", "")) if isinstance(payload, dict) else ""
if not command:
    sys.exit(0)


# ============================================================
# Risk classifier
# ============================================================

CRITICAL_PATTERNS = [
    # Home/root/system destruction
    (r"\brm\s+-r?f?\s+/(?:\s|$)", "rm -rf at filesystem root"),
    (r"\brm\s+-r?f?\s+~", "rm -rf in home directory"),
    (r"\brm\s+-r?f?\s+\$HOME", "rm -rf with $HOME"),
    (r"\bsudo\s+rm\s+-r?f?\s+/", "sudo rm at root"),
    (r":\(\)\s*\{[^}]*:\s*\|\s*:", "fork bomb pattern"),
    (r":\|:&", "fork bomb shorthand"),
    # Secrets exfiltration patterns
    (r"curl[^|]*\|\s*bash", "remote-fetched script piped to shell"),
    (r"wget[^|]*\|\s*sh", "remote-fetched script piped to shell"),
    (r"(?:cat|tail)\s+(?:~/\.ssh/|~/.aws/credentials|/etc/shadow)", "credentials read"),
    # Destructive shell chains
    (r"&&\s*rm\s+-r?f?\s+/", "rm -rf at root in chain"),
    (r";\s*rm\s+-r?f?\s+/", "rm -rf at root in chain"),
]

HIGH_PATTERNS = [
    (r"\brm\s+-(?:rf|fr|r[a-z]*f|f[a-z]*r)\s+\S+", "rm -rf with target"),  # any rm -rf
    (r"\bfind\b[^|]*-delete", "find -delete"),
    (r"\bxargs\b[^|]*rm\s", "xargs rm"),
    (r"\bgit\s+clean\s+-[a-z]*[fdx]", "git clean -fdx variants"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard"),
    (r"\bgit\s+push\s+(?:--force(?!-with-lease)|-f\b)", "git push --force without --force-with-lease"),
    (r"\bdd\s+if=\S+\s+of=/dev/", "dd to device"),
    (r"\bmkfs(?:\.|\s)", "filesystem format"),
    (r"\bdrop\s+(?:database|schema)\b", "DROP DATABASE/SCHEMA"),
    (r"\btruncate\s+table\b", "TRUNCATE TABLE"),
]

MEDIUM_PATTERNS = [
    (r"\brm\s+\S+", "rm (without -rf)"),
    (r"\bgit\s+stash\s+drop\b", "git stash drop"),
    (r"\bgit\s+branch\s+-D\b", "git branch -D"),
    (r"\bgit\s+tag\s+-d\b", "git tag -d"),
    (r"\bgit\s+push\s+--force-with-lease\b", "git push --force-with-lease"),
    (r"\bnpm\s+(?:uninstall|remove)\b", "npm uninstall"),
    (r"\bpip\s+uninstall\b", "pip uninstall"),
    (r"\bdocker\s+(?:rm|rmi|system\s+prune)\b", "docker remove/prune"),
    (r"\bdelete\s+from\b", "DELETE FROM"),
    (r"\balter\s+table\b.*\bdrop\b", "ALTER TABLE DROP"),
]


def classify(cmd: str) -> tuple[str, str | None]:
    """Return (risk_class, matched_pattern_description)."""
    for pat, desc in CRITICAL_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            return "CRITICAL", desc
    for pat, desc in HIGH_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            return "HIGH", desc
    for pat, desc in MEDIUM_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            return "MEDIUM", desc
    return "LOW", None


risk_class, reason = classify(command)


# ============================================================
# Telemetry — log every classification to V8 ledger
# ============================================================

def _ledger_write(event_type: str, **kwargs) -> None:
    try:
        root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2])).resolve()
        spec = importlib.util.spec_from_file_location("led", root / "scripts" / "ledger-v2.py")
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.write_event(event_type, **kwargs)
    except Exception:
        pass


# Non-LOW classifications are operationally meaningful. LOW classifications
# are useful while debugging the guard itself, but too noisy for default
# dashboard telemetry because every shell command passes through this hook.
if risk_class != "LOW" or os.environ.get("ULTRAPROMPT_LOG_LOW_RISK_GUARD") == "1":
    _ledger_write(
        "destructive_guard_classification",
        risk_class=risk_class,
        matched_pattern=reason,
        command_excerpt=command[:120],
    )


# ============================================================
# Action by risk class
# ============================================================

if risk_class == "LOW":
    sys.exit(0)  # Allow silently

if risk_class == "MEDIUM":
    # Warn-only via stderr; allow execution
    print(
        f"[Ultraprompt destructive-guard] MEDIUM-risk command detected: {reason}. "
        f"Command runs but is logged.",
        file=sys.stderr,
    )
    sys.exit(0)

if risk_class == "HIGH":
    if os.environ.get("ULTRAPROMPT_ALLOW_HIGH_RISK") == "1":
        print(
            f"[Ultraprompt destructive-guard] HIGH-risk allowed by override: {reason}",
            file=sys.stderr,
        )
        sys.exit(0)
    print(
        f"[Ultraprompt destructive-guard] BLOCKED HIGH-risk command: {reason}.\n"
        f"Override: ULTRAPROMPT_ALLOW_HIGH_RISK=1 for this session (use carefully).\n"
        f"Full bypass: ULTRAPROMPT_DISABLE_HOOKS=1 (NOT recommended).",
        file=sys.stderr,
    )
    sys.exit(2)

# CRITICAL — block unconditionally
print(
    f"[Ultraprompt destructive-guard] BLOCKED CRITICAL-risk command: {reason}.\n"
    f"This pattern is blocked regardless of override flags due to data-loss / security risk.\n"
    f"If you genuinely need this, run the command outside the agent session.",
    file=sys.stderr,
)
sys.exit(2)
