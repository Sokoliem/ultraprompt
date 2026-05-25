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
# Risk classifier — patterns loaded from _shared/safety-policy.json (V9.0 R2)
# ============================================================

def _load_safety_policy() -> tuple[list, list, list, int]:
    """Load patterns from _shared/safety-policy.json. Fail-open with empty pattern
    lists if the file is missing or unparseable — a broken safety file should
    never brick sessions. The load is logged to the ledger for ops visibility.
    """
    root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))
    path = os.environ.get("ULTRAPROMPT_SAFETY_POLICY_PATH") or str(root / "_shared" / "safety-policy.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        critical = [(re.compile(p["pattern"], re.IGNORECASE), p["description"]) for p in data.get("critical_patterns", [])]
        high = [(re.compile(p["pattern"], re.IGNORECASE), p["description"]) for p in data.get("high_patterns", [])]
        medium = [(re.compile(p["pattern"], re.IGNORECASE), p["description"]) for p in data.get("medium_patterns", [])]
        return critical, high, medium, int(data.get("version", 0))
    except Exception as exc:
        # Fail-open: empty pattern lists mean every command classifies as LOW.
        # Loud about it: ledger event + stderr warning so a broken policy file
        # does not silently disable safety (v9.0 F-001 hardening).
        try:
            spec = importlib.util.spec_from_file_location("led_err", root / "scripts" / "ledger-v2.py")
            if spec and spec.loader:
                m = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(m)
                m.write_event("safety-policy-load-error", path=path, error=str(exc)[:200])
        except Exception:
            pass
        print(
            f"[Ultraprompt destructive-guard] WARNING: safety-policy.json unreadable at {path} ({exc}). "
            "Destructive-command classification DEGRADED — every command will pass through as LOW. "
            "Fix the file and restart the session, or set ULTRAPROMPT_SAFETY_POLICY_PATH to a working copy.",
            file=sys.stderr,
        )
        return [], [], [], 0


_CRIT_COMPILED, _HIGH_COMPILED, _MED_COMPILED, _POLICY_VERSION = _load_safety_policy()


def classify(cmd: str) -> tuple[str, str | None]:
    """Return (risk_class, matched_pattern_description). Patterns pre-compiled at module load."""
    for pat, desc in _CRIT_COMPILED:
        if pat.search(cmd):
            return "CRITICAL", desc
    for pat, desc in _HIGH_COMPILED:
        if pat.search(cmd):
            return "HIGH", desc
    for pat, desc in _MED_COMPILED:
        if pat.search(cmd):
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


# Always log the classification
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
