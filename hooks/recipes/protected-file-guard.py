#!/usr/bin/env python3
"""Block edits to secret-like or protected files. Fail-open on errors.

The whole flow runs inside main() under a top-level try/except → exit 0 so an
unexpected payload shape (e.g. a non-dict tool_input) degrades to allow rather
than surfacing a traceback on the user's tool call (v9.3 hardening). The
intentional `return 2` block path for a matched secret file is preserved.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

PROTECTED = re.compile(
    r"(^|/)("
    r"\.env($|\.)"
    r"|.*\.pem$"
    r"|.*\.key$"
    r"|id_rsa$"
    r"|id_ed25519$"
    r"|secrets?\.(json|ya?ml|toml)$"
    # V8.8: additional credential families
    r"|service[-_]?account.*\.json$"
    r"|.*\.p12$"
    r"|.*\.pfx$"
    r"|aws[-_]?credentials\.json$"
    r"|accessKeys\.csv$"
    r")",
    re.IGNORECASE,
)


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


def main() -> int:
    if os.environ.get("ULTRAPROMPT_DISABLE_HOOKS") == "1":
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

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

    for path in paths:
        if PROTECTED.search(path):
            reason = (
                f"Blocked by Ultraprompt: {path!r} looks like a secrets or protected file. "
                "Edit it manually, or set ULTRAPROMPT_DISABLE_HOOKS=1 if intentional."
            )
            record_block(reason)
            print(reason, file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Defense-in-depth: never let an unexpected exception block a tool call.
        sys.exit(0)
