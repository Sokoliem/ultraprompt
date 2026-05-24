#!/usr/bin/env python3
"""V8 SessionStart hook: bootstrap banner + V8 plugin banner + checkpoint snapshot.

V8.8 (S4): collapses the previous two-script SessionStart pipeline
(session-bootstrap.py + session-start-context.{sh,py}) into one Python
entry. Targets ≤8s p95 by avoiding a second subprocess invocation.
"""
from __future__ import annotations
import importlib.util, json, os, sys, time
from pathlib import Path

PR = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))


def _catalog_counts() -> dict[str, int]:
    """Read dist/catalog-metadata.json for dynamic counts; falls back to defaults."""
    defaults = {"skills": 49, "agents": 30, "mcp_tools": 42, "commands": 31,
                "panels": 12, "artifact_schemas": 17, "output_styles": 2}
    try:
        data = json.loads((PR / "dist" / "catalog-metadata.json").read_text(encoding="utf-8"))
        return {
            "skills": int(data.get("skills_total", data.get("skills", defaults["skills"]))),
            "agents": int(data.get("agents_total", data.get("agents", defaults["agents"]))),
            "mcp_tools": int(data.get("mcp_tools_total", data.get("mcp_tools", defaults["mcp_tools"]))),
            "commands": int(data.get("commands_total", data.get("commands", defaults["commands"]))),
            "panels": int(data.get("panels_total", data.get("panels", defaults["panels"]))),
            "artifact_schemas": int(data.get("artifact_schemas_total", data.get("artifact_schemas", defaults["artifact_schemas"]))),
            "output_styles": int(data.get("output_styles_total", data.get("output_styles", defaults["output_styles"]))),
        }
    except Exception:
        return defaults


def _v8_banner() -> str:
    c = _catalog_counts()
    return (
        f"Ultraprompt V8.9.0 active. Catalog: "
        f"{c['skills']} skills, {c['agents']} agents, {c['mcp_tools']} MCP tools, "
        f"{c['commands']} commands, {c['panels']} panels, {c['artifact_schemas']} artifact schemas, "
        f"{c['output_styles']} output styles.\n\n"
        "**V8.9 adds (on top of V8.7):**\n"
        "- 6 new skills: incident-response, adr-author, runbook-author, cost-audit, git-workflow, onboarding-doc.\n"
        "- 4 new agents: incident-commander, prompt-engineer, release-manager, data-analyst.\n"
        "- 2 new commands: /ultraprompt:dispatch (manual agent dispatch), /ultraprompt:rollback (restore wip-save / checkpoint).\n"
        "- V8.8 hardening: description lint with CI gate, read-only enforcement via disallowedTools on 14 agents, protected-file-guard extended (service-account/p12/pfx/aws-creds), catalog templating eliminates count drift, bash safety denylist (chmod, package installs) in destructive-command-guard.\n\n"
        "**FIRST RULE:** when uncertain how to handle a request, follow the V8.7 picker directive if one is injected (call `ultraprompt:choose` Skill).\n\n"
        "**Dispatch defaults:** see `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md`.\n\n"
        "**Safety:** write evidence for validation claims, use `/ultraprompt:wip-save` before risky work, "
        "apply `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md`. "
        "(Disable hooks via `ULTRAPROMPT_DISABLE_HOOKS=1`.)"
    )


def _imp(n, p):
    try:
        spec = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m); return m
    except Exception:
        return None


def _personal_lanes(cfg, config) -> str | None:
    """Read the user's personal dispatch-bias file and return it as additionalContext,
    truncated to max_chars. Returns None when disabled or absent."""
    try:
        if cfg and not cfg.get(config, "hooks.personal_lanes_enabled", True):
            return None
        raw_path = (cfg.get(config, "personal_lanes.file", "~/.claude/ultraprompt-user.md")
                    if cfg else "~/.claude/ultraprompt-user.md") or "~/.claude/ultraprompt-user.md"
        path = Path(os.path.expanduser(str(raw_path)))
        if not path.exists() or not path.is_file():
            return None
        max_chars = int((cfg.get(config, "personal_lanes.max_chars", 4000) if cfg else 4000) or 4000)
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            return None
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "\n... (truncated; raise personal_lanes.max_chars to include more)"
        return (
            "ultraprompt personal lanes (`~/.claude/ultraprompt-user.md`) — apply these dispatch biases "
            "as the first arbitration signal:\n\n" + text
        )
    except Exception:
        return None


def main():
    if os.environ.get("ULTRAPROMPT_DISABLE_HOOKS") == "1": return 0
    try: sys.stdin.read()
    except Exception: pass
    cfg = _imp("cfg", PR / "scripts" / "config-loader.py")
    ws = _imp("ws", PR / "scripts" / "worktree-state.py")
    led = _imp("ledger_v2", PR / "scripts" / "ledger-v2.py")
    if not (cfg and ws): return 0
    config = cfg.load_config()
    if not cfg.get(config, "hooks.session_bootstrap_enabled", True): return 0

    personal = _personal_lanes(cfg, config)
    if not cfg.get(config, "ledger.enabled", True): led = None
    repo_root = ws.find_repo_root()
    if repo_root is None: return 0
    cwd = Path.cwd().resolve()
    state = ws.worktree_state(cwd)
    repo_n = ws.repo_name(repo_root)
    sid = os.environ.get("CLAUDE_SESSION_ID") or f"unknown-{int(time.time())}"
    if led:
        led.write_event("session_start", repo=repo_n, worktree=str(cwd),
            branch=state.get("branch"), head=state.get("head"),
            dirty=state.get("dirty_count", 0), untracked=state.get("untracked_count", 0),
            stash=state.get("stash_count", 0), unpushed=state.get("unpushed_count", 0),
            in_progress=state.get("in_progress"), session_id=sid, runtime="claude-code")
    win = cfg.get(config, "session.active_window_minutes", 15)
    others = []
    try:
        sessions = ws.find_active_sessions(cwd, win)
        others = [s for s in sessions if s.get("session_id") != sid]
    except Exception: pass
    dirty = state.get("dirty_count", 0) + state.get("untracked_count", 0)
    unpushed = state.get("unpushed_count", 0)
    ip = state.get("in_progress")
    dt = cfg.get(config, "worktree.dirty_warn_count", 50)
    upt = cfg.get(config, "worktree.unpushed_warn_count", 5)
    warns = []
    if ip: warns.append(f"in-progress {ip} — complete or abort before continuing")
    if dirty >= dt: warns.append(f"{dirty} dirty files (threshold {dt})")
    if unpushed >= upt: warns.append(f"{unpushed} unpushed commits (threshold {upt})")
    if others: warns.append(f"{len(others)} concurrent session(s) active")
    branch = state.get("branch") or "(detached)"
    lines: list[str] = []
    # V8.8 (S4): always emit the V8 banner so SessionStart needs only this one hook.
    lines.append(_v8_banner())
    if warns:
        lines.append("")
        lines.append("ultraprompt session bootstrap")
        lines.append(f"  repo: {repo_n} · worktree: {cwd.name} · branch: {branch}")
        for w in warns: lines.append(f"  ⚠️  {w}")
        lines.append(f"  run /ultraprompt:status for full picture")
    if personal:
        lines.append("")
        lines.append(personal)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                              "additionalContext": "\n".join(lines)}}))
    return 0


if __name__ == "__main__":
    try: sys.exit(main())
    except Exception: sys.exit(0)
