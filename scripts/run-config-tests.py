#!/usr/bin/env python3
"""Focused tests for Ultraprompt layered config loading."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "scripts" / "config-loader.py"
    spec = importlib.util.spec_from_file_location("config_loader", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = load_module()
    previous = dict(os.environ)
    try:
        for key in list(os.environ):
            if key.startswith("ULTRAPROMPT"):
                os.environ.pop(key, None)
        os.environ.update({
            "ULTRAPROMPT__AUTO_WIP_SAVE__ENABLED": "false",
            "ULTRAPROMPT__NOTIFICATION__QUIET_HOURS_START": "22",
            "ULTRAPROMPT__WORKTREE__DIRTY_WARN_COUNT": "10",
        })
        config = module.load_config()
    finally:
        os.environ.clear()
        os.environ.update(previous)

    assertions = [
        ("auto_wip_save.enabled", config.get("auto_wip_save", {}).get("enabled") is False),
        ("notification.quiet_hours_start", config.get("notification", {}).get("quiet_hours_start") == 22),
        ("worktree.dirty_warn_count", config.get("worktree", {}).get("dirty_warn_count") == 10),
    ]
    failures = [name for name, ok in assertions if not ok]
    result = {"ok": not failures, "checked": [name for name, _ in assertions], "failures": failures}
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
