#!/usr/bin/env python3
"""SubagentStart hook — single source of the subagent scaffold payload.

Both the POSIX recipe (`subagent-scaffold.sh`, which delegates to this file)
and the Windows registration (`hooks.windows.json`, which calls this file
directly) emit this one payload, so the two platforms cannot diverge. A parity
test in `scripts/run-release-integrity-tests.py` asserts the `.sh` and `.py`
produce byte-identical stdout.
"""
from __future__ import annotations

import json
import os
import sys

# Canonical scaffold injected into every subagent's context at SubagentStart.
ADDITIONAL_CONTEXT = (
    "Return concise, evidence-tagged findings. Prefer Observed > Inferred > "
    "Assumed claims. Stay read-only unless the parent task explicitly grants "
    "edits. Do not claim validation you did not run. When uncertain, name the "
    "highest-leverage next inspection target instead of padding the answer. "
    "Apply discipline per ${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md."
)


def payload() -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": ADDITIONAL_CONTEXT,
        }
    }


def main() -> int:
    # Fail open when hooks are disabled.
    if os.environ.get("ULTRAPROMPT_DISABLE_HOOKS") == "1":
        return 0
    print(json.dumps(payload(), indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Fail open: a scaffold hook must never block a subagent from starting.
        sys.exit(0)
