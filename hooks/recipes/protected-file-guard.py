#!/usr/bin/env python3
"""Block edits to secret-like or protected files. Fail-open on errors."""
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

tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
paths: list[str] = []
for key in ("file_path", "path"):
    value = tool_input.get(key)
    if isinstance(value, str):
        paths.append(value)

edits = tool_input.get("edits", [])
if isinstance(edits, list):
    for e in edits:
        if isinstance(e, dict) and isinstance(e.get("file_path"), str):
            paths.append(e["file_path"])

PROTECTED = re.compile(r"(^|/)(\.env($|\.)|.*\.pem$|.*\.key$|id_rsa$|id_ed25519$|secrets?\.(json|ya?ml|toml)$)")


def record_block(reason: str) -> None:
    try:
        root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2])).resolve()
        scripts = root / "scripts" / "evidence-ledger.py"
        spec = importlib.util.spec_from_file_location("ultra_evidence_ledger", scripts)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.append_event("hook-block", {"reason": reason})
    except Exception:
        pass


for path in paths:
    if PROTECTED.search(path):
        reason = (
            f"Blocked by Ultraprompt: {path!r} looks like a secrets or protected file. "
            "Edit it manually, or set ULTRAPROMPT_DISABLE_HOOKS=1 if intentional."
        )
        record_block(reason)
        print(reason, file=sys.stderr)
        sys.exit(2)

sys.exit(0)
