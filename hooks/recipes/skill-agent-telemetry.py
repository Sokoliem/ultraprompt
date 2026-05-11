#!/usr/bin/env python3
"""V8 PreToolUse telemetry hook.

Observes when Claude calls Skill or Task tools. Filters for ultraprompt:*
identifiers. Writes skill_invocation or agent_dispatch events to the V8 ledger.

Passive observer — never blocks, never produces output, fail-open.
Respects ULTRAPROMPT_DISABLE_HOOKS=1.
"""
from __future__ import annotations
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

PR = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))


def _imp(name: str, path: Path):
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def main() -> int:
    if os.environ.get("ULTRAPROMPT_DISABLE_HOOKS") == "1":
        return 0

    # Read hook input from stdin (best-effort)
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {}) or {}

    # Only observe Skill and Task tool calls
    if tool_name not in ("Skill", "Task", "Agent"):
        return 0

    cfg = _imp("cfg", PR / "scripts" / "config-loader.py")
    led = _imp("led", PR / "scripts" / "ledger-v2.py")
    ws = _imp("ws", PR / "scripts" / "worktree-state.py")
    if not led:
        return 0
    if cfg:
        config = cfg.load_config()
        if not cfg.get(config, "ledger.enabled", True):
            return 0

    # Determine repo / worktree context
    repo_n = None
    worktree = None
    try:
        cwd = Path.cwd().resolve()
        worktree = str(cwd)
        if ws:
            repo_root = ws.find_repo_root(cwd)
            if repo_root:
                repo_n = ws.repo_name(repo_root)
    except Exception:
        pass

    sid = os.environ.get("CLAUDE_SESSION_ID") or f"unknown-{int(time.time())}"

    if tool_name == "Skill":
        # Skill tool input has a 'skill' field
        skill = tool_input.get("skill") or tool_input.get("name") or "?"
        is_plugin = isinstance(skill, str) and skill.startswith("ultraprompt:")
        led.write_event(
            "skill_invocation",
            skill=skill,
            is_plugin_skill=is_plugin,
            repo=repo_n,
            worktree=worktree,
            session_id=sid,
            runtime="claude-code",
        )
    elif tool_name in ("Task", "Agent"):
        # Task tool input has 'subagent_type', 'description', 'prompt'
        agent = tool_input.get("subagent_type") or tool_input.get("agent") or "?"
        is_plugin = isinstance(agent, str) and agent.startswith("ultraprompt:")
        led.write_event(
            "agent_dispatch",
            agent=agent,
            is_plugin_agent=is_plugin,
            repo=repo_n,
            worktree=worktree,
            session_id=sid,
            runtime="claude-code",
        )

    # No output — passive observer
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
