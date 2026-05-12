#!/usr/bin/env python3
"""Windows-safe SessionStart hook.

Keeps the hook payload single-sourced from the existing shell recipe while
avoiding a bash dependency on Windows installs.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def main() -> int:
    if os.environ.get("ULTRAPROMPT_DISABLE_HOOKS") == "1":
        return 0
    try:
        text = Path(__file__).with_suffix(".sh").read_text(encoding="utf-8")
        match = re.search(r"cat <<'JSON'\n(?P<payload>.*)\nJSON\s*$", text, re.S)
        if match:
            print(match.group("payload"))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
