#!/usr/bin/env python3
"""V9.0 PostToolUse hook: append every tool call to the evidence ledger.

Replaces the V8.8 workaround where validate-descriptions.py manually seeded
validation_command events. With this hook registered, every Bash/Edit/Write/etc
call automatically lands in the ledger so claim_check has real signal.

Fails open on any error. Respects:
- ULTRAPROMPT_DISABLE_HOOKS=1                  (disables all hooks)
- ULTRAPROMPT_DISABLE_POST_TOOL_LEDGER=1       (disables only this hook)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

PR = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))


def main() -> int:
    if os.environ.get("ULTRAPROMPT_DISABLE_HOOKS") == "1":
        return 0
    if os.environ.get("ULTRAPROMPT_DISABLE_POST_TOOL_LEDGER") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    try:
        spec = importlib.util.spec_from_file_location("ev", PR / "scripts" / "evidence-ledger.py")
        if spec and spec.loader:
            ev = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(ev)
            ev.append_event("PostToolUse", payload)
    except Exception:
        # Fail open: never block tool result delivery.
        pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
