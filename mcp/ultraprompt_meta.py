#!/usr/bin/env python3
"""Ultraprompt Meta MCP server (V8).

Dependency-free stdio MCP server. Core tools include:
- claim_check (scan draft text for unbacked validation claims)
- query_ledger (return events matching filter)
- validation_status (aggregate check)
- evidence_diff (events since timestamp)
- team_plan (return orchestration plan for panel-run patterns)
- repo_capsule, repo_capsule_diff (cached capsule + drift)

Legacy tools retained: list_skills, route_intent, explain_skill, list_agents,
validate_plugin. compose_workflow is kept but marked deprecated.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[1])).resolve()
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from ultraprompt_index import (  # noqa: E402
    compose_workflow,
    explain_skill,
    load_index,
    route_intent,
    validate_plugin,
)
from routing_policy import (  # noqa: E402
    load_routing_policy,
    policy_for_skill,
    run_pathfind_for_decision,
)
from cognitive_common import sortable_id  # noqa: E402


def plugin_version() -> str:
    for rel in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        try:
            data = json.loads((PLUGIN_ROOT / rel).read_text(encoding="utf-8"))
            version = data.get("version")
            if version:
                return str(version)
        except Exception:
            continue
    return "unknown"


# -------------------- MCP instructions block (for Claude Code context injection) --------------------

MCP_INSTRUCTIONS = """## ultraprompt-meta (V8)

V8: dispatch-first architecture with trust-consolidated release gates and live dashboard telemetry.

**FIRST CALL when uncertain: `dispatch_advise`** â€” pass intent + estimated_files_to_read + is_interactive. Returns dispatch-vs-inline recommendation with specific agent and Task brief. Cost: one MCP call. Benefit: prevents wrong-tool dispatches before they happen.

**Routing:**
- `dispatch_advise` â€” dispatch vs inline decision 
- `route_intent` â€” top-3 skill matches when lane is unclear

**Evidence:**
- `claim_check` â€” call on draft BEFORE asserting "tests pass" / "build succeeds"
- `repo_capsule` â€” cached read-only contract for unfamiliar repos

**Multi-session safety:**
- `worktree_state` â€” state of all worktrees in current repo
- `session_lookup` â€” detect concurrent sessions
- `wip_save_advise` â€” recommend wip-save based on threshold + cooldown

**Panel:**
- `team_plan` â€” preview panel-run plan BEFORE paying NÃ—baseline cost

### V8 dispatch defaults

Skills with specialist agents dispatch via Task by default. Follow each skill body's DISPATCH POLICY. Inline override only when trivial (â‰¤5 reads), user asked for fast-path, OR context is already loaded.

### Specialist-first routing

- When a matching `ultraprompt:*` specialist exists and confidence is above threshold, prefer it over built-in Explore.
- "map X / explore Y / read Z / show me W" â†’ `ultraprompt:scout`, not Explore.
- "audit X for Y" â†’ `ultraprompt:auditor` with focus, not Explore.
- "draft release notes / write ADR" â†’ `ultraprompt:writer`, not Explore.
- "red-team / critique / find weakness" â†’ `ultraprompt:adversarial`, not Explore.
- High-output specialists should use artifact-first handoff: full report on disk, compact envelope in chat."""


def _ledger_write_call(tool_name: str, args: dict, dur_ms: int, ok: bool, extra: dict = None) -> None:
    """Append mcp_tool_call event to ledger v2. Fail-open.

    V8: `extra` dict merged into the event for outcome telemetry â€” e.g.,
    claim_check passes 'passed' + 'fail_count', dispatch_advise passes 'recommend' + 'agent'.
    """
    try:
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location("_ledger", Path(__file__).resolve().parents[1] / "scripts" / "ledger-v2.py")
        ledger = _ilu.module_from_spec(spec)
        spec.loader.exec_module(ledger)
        args_summary = {k: (v if not isinstance(v, str) or len(v) <= 200 else v[:200] + "...") for k, v in args.items()}
        kwargs = {
            "trace_id": str(args.get("trace_id") or sortable_id("mcp")),
            "tool": tool_name,
            "args": args_summary,
            "dur_ms": dur_ms,
            "ok": ok,
            "source": "mcp/ultraprompt_meta.py",
            "repo": PLUGIN_ROOT.name,
            "worktree": str(PLUGIN_ROOT),
        }
        if extra:
            kwargs.update(extra)
        ledger.write_event("mcp_tool_call", **kwargs)
    except Exception:
        pass


def _extract_outcome_fields(tool_name: str, result: dict) -> dict:
    """Extract outcome fields from a tool result for richer telemetry.

    Each tool exposes specific outcome signals worth logging:
    - claim_check: passed (bool), check_count, fail_count
    - dispatch_advise: recommend ('inline'|'dispatch'), agent (suggested), top_skill
    - route_intent: top_skill, confidence
    """
    extra = {}
    try:
        content = result.get("content", [])
        if not content or not isinstance(content, list):
            return extra
        text = content[0].get("text", "") if isinstance(content[0], dict) else ""
        if not text or not (text.startswith("{") or text.startswith("[")):
            return extra
        import json as _j
        parsed = _j.loads(text)
        if not isinstance(parsed, dict):
            return extra
        if tool_name == "claim_check":
            if "passed" in parsed:
                extra["passed"] = bool(parsed.get("passed"))
            checks = parsed.get("checks") if isinstance(parsed.get("checks"), list) else None
            if checks:
                extra["check_count"] = len(checks)
                extra["fail_count"] = sum(
                    1 for c in checks if isinstance(c, dict) and c.get("passed") is False
                )
        elif tool_name == "dispatch_advise":
            for k in ("recommend", "agent", "top_skill", "is_interactive"):
                if k in parsed:
                    extra[k] = parsed[k]
        elif tool_name == "route_intent":
            routes = parsed.get("routes")
            if isinstance(routes, list) and routes:
                top = routes[0] or {}
                if isinstance(top, dict):
                    extra["top_skill"] = top.get("skill")
                    extra["confidence"] = top.get("confidence")
    except Exception:
        pass
    return extra


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_LEDGER_MOD = _load_module("ultra_evidence_ledger", SCRIPTS_DIR / "evidence-ledger.py")
_CAPSULE_MOD = _load_module("ultra_repo_capsule", SCRIPTS_DIR / "repo-capsule.py")


def text_result(data: Any, *, is_error: bool = False) -> dict[str, Any]:
    text = data if isinstance(data, str) else json.dumps(data, indent=2, sort_keys=True)
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


# -------------------- list / route / explain --------------------

def tool_list_skills(args: dict[str, Any]) -> dict[str, Any]:
    index = load_index(PLUGIN_ROOT)
    query = str(args.get("query", "")).strip().lower()
    tier = str(args.get("tier", "")).strip().lower()
    include_manual = bool(args.get("include_manual", True))
    limit = int(args.get("limit", 80))
    skills = []
    for skill in index.get("skills", []):
        if not include_manual and skill.get("manual_only"):
            continue
        if tier and str(skill.get("tier", "")).lower() != tier:
            continue
        haystack = " ".join(str(skill.get(k, "")) for k in ("name", "description", "when_to_use", "tier")).lower()
        if query and query not in haystack:
            continue
        skills.append({k: skill.get(k) for k in ("name", "command", "codex_command", "description", "tier", "manual_only", "paths", "path")})
    return text_result({"count": len(skills[:limit]), "skills": skills[:limit]})


def tool_route_intent(args: dict[str, Any]) -> dict[str, Any]:
    intent = str(args.get("intent", "")).strip()
    if not intent:
        return text_result({"error": "intent is required"}, is_error=True)
    limit = int(args.get("limit", 3))
    routes = route_intent(load_index(PLUGIN_ROOT), intent, limit=limit)
    # V8: log route_decision event for routing accuracy analysis
    try:
        import importlib.util as _ilu_rd
        _spec = _ilu_rd.spec_from_file_location("_led_rd", Path(__file__).resolve().parents[1] / "scripts" / "ledger-v2.py")
        _led = _ilu_rd.module_from_spec(_spec)
        _spec.loader.exec_module(_led)
        intent_excerpt = str(args.get("intent", ""))[:200]
        top = routes[0] if isinstance(routes, list) and routes else {}
        _led.write_event("route_decision",
                         intent_excerpt=intent_excerpt,
                         top_skill=top.get("skill"),
                         confidence=top.get("confidence"))
    except Exception:
        pass
    return text_result({"intent": intent, "routes": routes})



def tool_explain_skill(args: dict[str, Any]) -> dict[str, Any]:
    name = str(args.get("skill", "")).strip()
    if not name:
        return text_result({"error": "skill is required"}, is_error=True)
    skill = explain_skill(load_index(PLUGIN_ROOT), name)
    if not skill:
        return text_result({"error": f"unknown skill: {name}"}, is_error=True)
    return text_result(skill)


def tool_list_agents(args: dict[str, Any]) -> dict[str, Any]:
    index = load_index(PLUGIN_ROOT)
    query = str(args.get("query", "")).strip().lower()
    agents = []
    for agent in index.get("agents", []):
        haystack = " ".join(str(agent.get(k, "")) for k in ("name", "description", "tools", "disallowed_tools")).lower()
        if query and query not in haystack:
            continue
        agents.append(agent)
    return text_result({"count": len(agents), "agents": agents})


def tool_validate_plugin(args: dict[str, Any]) -> dict[str, Any]:
    return text_result(validate_plugin(PLUGIN_ROOT))


def tool_compose_workflow(args: dict[str, Any]) -> dict[str, Any]:
    skills_arg = args.get("skills", [])
    if isinstance(skills_arg, str):
        skills = [s.strip() for s in skills_arg.split(",") if s.strip()]
    elif isinstance(skills_arg, list):
        skills = [str(item).strip() for item in skills_arg if str(item).strip()]
    else:
        skills = []
    if not skills:
        return text_result({"error": "skills must be a non-empty array or comma-separated string"}, is_error=True)
    return text_result(compose_workflow(load_index(PLUGIN_ROOT), skills))


# -------------------- evidence ledger tools (legacy core) --------------------

def tool_query_ledger(args: dict[str, Any]) -> dict[str, Any]:
    if _LEDGER_MOD is None:
        return text_result({"error": "evidence ledger module unavailable"}, is_error=True)
    event_filter = str(args.get("event", "")).strip()
    tool_filter = str(args.get("tool", "")).strip()
    validation_only = bool(args.get("validation_only", False))
    since = str(args.get("since", "")).strip()
    limit = int(args.get("limit", 50))
    try:
        events = _LEDGER_MOD.read_events()
    except Exception as exc:
        return text_result({"error": f"failed to read ledger: {exc}"}, is_error=True)
    out = []
    for ev in events:
        if event_filter and ev.get("event") != event_filter:
            continue
        if tool_filter and ev.get("tool") != tool_filter:
            continue
        if validation_only and not ev.get("validation_command"):
            continue
        if since and str(ev.get("ts", "")) < since:
            continue
        out.append(ev)
    return text_result({"count": len(out[-limit:]), "events": out[-limit:]})


def tool_validation_status(args: dict[str, Any]) -> dict[str, Any]:
    if _LEDGER_MOD is None:
        return text_result({"error": "evidence ledger module unavailable"}, is_error=True)
    try:
        validation_seen = bool(_LEDGER_MOD.has_validation_record())
        edits_seen = bool(_LEDGER_MOD.has_edit_record())
    except Exception as exc:
        return text_result({"error": f"failed to query ledger: {exc}"}, is_error=True)
    return text_result({
        "validation_seen": validation_seen,
        "edits_seen": edits_seen,
        "ledger_path": str(_LEDGER_MOD.ledger_path()),
        "summary": (
            "validation recorded" if validation_seen
            else ("edits recorded without validation" if edits_seen else "no validation or edits recorded")
        ),
    })


def tool_evidence_diff(args: dict[str, Any]) -> dict[str, Any]:
    if _LEDGER_MOD is None:
        return text_result({"error": "evidence ledger module unavailable"}, is_error=True)
    since = str(args.get("since", "")).strip()
    if not since:
        return text_result({"error": "since (ISO timestamp) is required"}, is_error=True)
    try:
        events = _LEDGER_MOD.read_events()
    except Exception as exc:
        return text_result({"error": f"failed to read ledger: {exc}"}, is_error=True)
    out = [ev for ev in events if str(ev.get("ts", "")) > since]
    return text_result({"since": since, "count": len(out), "events": out})


def tool_claim_check(args: dict[str, Any]) -> dict[str, Any]:
    """Scan draft text for unbacked validation claims; return warnings."""
    text = str(args.get("text", ""))
    if not text:
        return text_result({"error": "text is required"}, is_error=True)
    if _LEDGER_MOD is None:
        return text_result({"error": "evidence ledger module unavailable"}, is_error=True)
    try:
        validation_seen = bool(_LEDGER_MOD.has_validation_record())
    except Exception:
        validation_seen = False
    import re as _re
    claim_patterns = [
        (r"\b(all\s+)?(tests?|specs?|checks?|builds?|lints?|typechecks?)\s+(passed|pass|are\s+green|succeeded|are\s+passing|completed\s+successfully)\b",
         "validation-passed"),
        (r"\b(passed|green|succeeded|clean|successful)\b[^\n]{0,80}\b(validation|tests?|lint|typecheck|build|checks?)\b",
         "validation-passed-rev"),
        (r"\bI\s+ran\b[^\n]{0,80}\b(pytest|npm|pnpm|yarn|bun|go test|cargo|mvn|gradle|make|tsc|eslint|ruff|mypy|pyright)\b",
         "ran-validation"),
        (r"\b(no\s+regressions?|no\s+failures?|nothing\s+broke|everything\s+works)\b",
         "no-regression-claim"),
    ]
    warnings: list[dict[str, Any]] = []
    for pattern, label in claim_patterns:
        for match in _re.finditer(pattern, text, flags=_re.I):
            warnings.append({
                "kind": label,
                "snippet": text[max(0, match.start() - 20): match.end() + 20].strip(),
                "backed_by_ledger": validation_seen,
            })
    actionable = [w for w in warnings if not w["backed_by_ledger"]]
    return text_result({
        "warnings": warnings,
        "unbacked_count": len(actionable),
        "validation_seen": validation_seen,
        "verdict": (
            "OK" if not actionable
            else "UNBACKED-CLAIMS"
        ),
        "guidance": (
            "Validation claims are present but no validation command has been recorded in the ledger this session. "
            "Either run a real validation command and re-check, or remove the claim, or qualify it (e.g., 'I have not run the test suite')."
        ) if actionable else "No unbacked claims detected.",
    })


# -------------------- team_plan (legacy core) --------------------

TEAM_PATTERNS = {
    "review-fanout": {
        "description": "Parallel multi-perspective review of a diff or branch.",
        "agents": [
            {"role": "reviewer", "focus": "security"},
            {"role": "reviewer", "focus": "performance"},
            {"role": "reviewer", "focus": "architecture"},
            {"role": "reviewer", "focus": "tests"},
        ],
        "synthesis": "Merge findings, deduplicate, classify by severity (Blocker/Major/Minor), surface conflicts.",
    },
    "debug-triangulate": {
        "description": "Competing-hypothesis debug. Each debugger investigates a different root-cause hypothesis.",
        "agents": [
            {"role": "debugger", "focus": "hypothesis-A"},
            {"role": "debugger", "focus": "hypothesis-B"},
            {"role": "debugger", "focus": "hypothesis-C"},
        ],
        "synthesis": "Compare evidence per hypothesis, declare strongest fit, name remaining unknowns.",
    },
    "migration-assess": {
        "description": "Assess migration impact across compatibility, data, and rollout surfaces in parallel.",
        "agents": [
            {"role": "reviewer", "focus": "api-compat"},
            {"role": "auditor", "focus": "db"},
            {"role": "auditor", "focus": "infra"},
        ],
        "synthesis": "Combine into a sequenced rollout plan with explicit rollback path and risk register.",
    },
    "release-panel": {
        "description": "Pre-release evaluation: readiness + notes + supply-chain risk in parallel.",
        "agents": [
            {"role": "reviewer", "focus": "release-readiness"},
            {"role": "writer", "focus": "release-notes"},
            {"role": "auditor", "focus": "supply-chain"},
        ],
        "synthesis": "Produce go/no-go with notes draft and outstanding risks.",
    },
}


def tool_team_plan(args: dict[str, Any]) -> dict[str, Any]:
    pattern = str(args.get("pattern", "")).strip()
    problem = str(args.get("problem", "")).strip()
    custom_agents = args.get("agents")

    if pattern and pattern not in TEAM_PATTERNS and not custom_agents:
        return text_result({
            "error": f"unknown pattern: {pattern}",
            "available_patterns": sorted(TEAM_PATTERNS.keys()),
        }, is_error=True)

    if pattern and pattern in TEAM_PATTERNS:
        spec = TEAM_PATTERNS[pattern]
        agents = spec["agents"]
        synthesis = spec["synthesis"]
        description = spec["description"]
    else:
        if not isinstance(custom_agents, list) or not custom_agents:
            return text_result({"error": "either pattern or agents (list) is required"}, is_error=True)
        agents = []
        for a in custom_agents:
            if isinstance(a, dict):
                agents.append({"role": str(a.get("role", "")), "focus": str(a.get("focus", ""))})
            else:
                agents.append({"role": str(a), "focus": ""})
        synthesis = str(args.get("synthesis", "Merge findings, surface disagreements, produce concise summary."))
        description = "Custom team plan."

    plan = {
        "pattern": pattern or "custom",
        "description": description,
        "problem": problem or "(none provided)",
        "parallel_agents": [
            {
                "agent": a["role"],
                "focus": a["focus"],
                "task": (
                    f"As the {a['role']} agent with focus={a['focus']!r}, address: {problem or 'the parent skill problem'}. "
                    "Apply discipline per ${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md. "
                    "Return concise evidence-tagged findings."
                ),
            }
            for a in agents
        ],
        "synthesis": synthesis,
        "execution_note": (
            "Spawn each parallel_agent via the Agent tool with its task as the prompt. "
            "After all return, perform the synthesis step on the main thread. "
            "Treat each result as evidence to merge, not authority to copy."
        ),
    }
    return text_result(plan)


# -------------------- repo_capsule (cached) and repo_capsule_diff (legacy core) --------------------

def tool_repo_capsule(args: dict[str, Any]) -> dict[str, Any]:
    if _CAPSULE_MOD is None:
        return text_result({"error": "repo capsule module unavailable"}, is_error=True)
    path = str(args.get("path", ".")).strip() or "."
    force = bool(args.get("force_refresh", False))
    try:
        capsule, cache_hit = _CAPSULE_MOD.capsule_with_cache(path, force_refresh=force)
    except Exception as exc:
        return text_result({"error": f"capsule failed: {exc}"}, is_error=True)
    return text_result({"cache_hit": cache_hit, "capsule": capsule})


def tool_repo_capsule_diff(args: dict[str, Any]) -> dict[str, Any]:
    if _CAPSULE_MOD is None:
        return text_result({"error": "repo capsule module unavailable"}, is_error=True)
    path = str(args.get("path", ".")).strip() or "."
    since_commit = str(args.get("since_commit", "")).strip()
    if not since_commit:
        return text_result({"error": "since_commit is required"}, is_error=True)
    try:
        diff = _CAPSULE_MOD.capsule_diff(path, since_commit)
    except Exception as exc:
        return text_result({"error": f"capsule diff failed: {exc}"}, is_error=True)
    return text_result(diff)




# -------------------- multi-session/worktree tools --------------------

import importlib.util as _ilu
_PR = Path(__file__).resolve().parents[1]


def _import_v6(name: str, relpath: str):
    try:
        spec = _ilu.spec_from_file_location(name, _PR / relpath)
        m = _ilu.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    except Exception:
        return None


def tool_worktree_state(args: dict[str, Any]) -> dict[str, Any]:
    """Return state of all worktrees in the current repo (or specified path)."""
    ws = _import_v6("ws", "scripts/worktree-state.py")
    if ws is None:
        return text_result({"error": "worktree-state module unavailable"}, is_error=True)
    path = args.get("path")
    repo_root = Path(path).resolve() if path else None
    summary = ws.repo_summary(repo_root)
    return text_result(summary)


def tool_session_lookup(args: dict[str, Any]) -> dict[str, Any]:
    """Find Claude Code / Codex sessions active in a worktree path."""
    ws = _import_v6("ws", "scripts/worktree-state.py")
    if ws is None:
        return text_result({"error": "worktree-state module unavailable"}, is_error=True)
    path = Path(args.get("path", ".")).resolve()
    window = int(args.get("window_minutes", 15))
    return text_result({"path": str(path), "window_minutes": window,
                        "sessions": ws.find_active_sessions(path, window)})


def tool_ledger_query(args: dict[str, Any]) -> dict[str, Any]:
    """Query ledger v2 with filters. Returns events list."""
    led = _import_v6("led", "scripts/ledger-v2.py")
    if led is None:
        return text_result({"error": "ledger-v2 module unavailable"}, is_error=True)
    days = int(args.get("days", 7))
    types = args.get("types")
    repo = args.get("repo")
    worktree = args.get("worktree")
    events = led.read_events(days=days, event_types=types, repo=repo, worktree=worktree)
    limit = int(args.get("limit", 200))
    return text_result({"count": len(events), "events": events[-limit:]})


def tool_wip_save_advise(args: dict[str, Any]) -> dict[str, Any]:
    """Recommend whether to wip-save based on current state + cooldown."""
    ws = _import_v6("ws", "scripts/worktree-state.py")
    cfg = _import_v6("cfg", "scripts/config-loader.py")
    led = _import_v6("led", "scripts/ledger-v2.py")
    if not (ws and cfg):
        return text_result({"error": "modules unavailable"}, is_error=True)
    path = Path(args.get("path", ".")).resolve()
    state = ws.worktree_state(path)
    config = cfg.load_config()
    threshold = cfg.get(config, "auto_wip_save.delta_threshold", 10)
    cooldown = cfg.get(config, "auto_wip_save.cooldown_minutes", 15)
    dirty = state.get("dirty_count", 0) + state.get("untracked_count", 0)
    advise = {"path": str(path), "dirty": dirty, "threshold": threshold,
              "cooldown_minutes": cooldown, "in_progress": state.get("in_progress")}
    if state.get("in_progress"):
        advise["recommend"] = "no"
        advise["reason"] = f"in-progress {state['in_progress']} â€” refusing"
    elif dirty == 0:
        advise["recommend"] = "no"
        advise["reason"] = "nothing to save"
    elif dirty < threshold:
        advise["recommend"] = "no"
        advise["reason"] = f"below threshold ({dirty} < {threshold})"
    else:
        in_cooldown = False
        if led:
            try:
                import time as _time
                recent = led.read_events(days=1, event_types=["wip_save"], worktree=str(path))
                if recent and _time.time() - max(e.get("ts", 0) for e in recent) < cooldown * 60:
                    in_cooldown = True
            except Exception:
                pass
        if in_cooldown:
            advise["recommend"] = "no"; advise["reason"] = "within cooldown window"
        else:
            advise["recommend"] = "yes"; advise["reason"] = f"{dirty} dirty files exceed threshold"
    return text_result(advise)




def tool_dispatch_advise(args):
    """V8.5: Recommend dispatch vs inline from generated source policy."""
    intent = str(args.get("intent", "")).strip()
    if not intent:
        return text_result({"error": "intent is required"}, is_error=True)

    estimated = int(args.get("estimated_files_to_read", 10))
    is_interactive = bool(args.get("is_interactive", False))

    index = load_index(PLUGIN_ROOT)
    policy = load_routing_policy(PLUGIN_ROOT)
    skill_routes = route_intent(index, intent, limit=3)
    top_skill = skill_routes[0].get("skill") if skill_routes else None
    skill_policy = policy_for_skill(policy, str(top_skill or ""))
    dispatch = skill_policy.get("dispatch_to") or {}
    inline_override = skill_policy.get("inline_override") or {}
    default_execution = skill_policy.get("default_execution")

    advise = {
        "schema": "dispatch_advise.v2",
        "intent_excerpt": intent[:200],
        "top_skill": top_skill,
        "top_routes": skill_routes,
        "estimated_files": estimated,
        "is_interactive": is_interactive,
        "routing_policy_hash": policy.get("source_hash"),
    }

    if estimated <= 5 and not skill_routes:
        advise["recommend"] = "inline"
        advise["agent"] = None
        advise["reason"] = "trivial scope, no matching skill - answer inline"
    elif inline_override.get("enabled") or (estimated <= 5 and default_execution == "inline"):
        advise["recommend"] = "inline"
        advise["agent"] = None
        advise["reason"] = inline_override.get("reason") or f"{top_skill} policy prefers inline execution for this scope"
    elif dispatch.get("agent"):
        agent = str(dispatch["agent"])
        focus = dispatch.get("focus") or dispatch.get("focus_from")
        advise["recommend"] = "dispatch"
        advise["agent"] = "ultraprompt:" + agent
        if focus:
            advise["focus"] = focus
        advise["phase"] = dispatch.get("phase")
        advise["reason"] = top_skill + " has source-derived dispatch_to metadata; dispatch uses a specialist with artifact-first handoff when needed"
    else:
        advise["recommend"] = "inline" if estimated <= 5 else "dispatch"
        advise["agent"] = None
        if advise["recommend"] == "inline":
            advise["reason"] = "no clear specialist agent match"
        else:
            advise["reason"] = "high scope but no specialist - consider /ultraprompt:panel-run for cross-cutting work"
    advise["policy"] = {
        "default_execution": default_execution,
        "release_critical": skill_policy.get("release_critical"),
        "telemetry_required": skill_policy.get("telemetry_required"),
        "panel_escalation": skill_policy.get("panel_escalation"),
        "risk": skill_policy.get("risk"),
        "confirmation": skill_policy.get("confirmation"),
    }
    envelope_payload = _run_json_script(
        "pathfinder.py",
        ["pathfind", "--intent", intent, "--budget", "standard", "--dry-run", "--no-telemetry"],
        timeout=30,
    )
    envelope = ((envelope_payload.get("path") or {}).get("routing_envelope") if envelope_payload.get("ok") else None)
    if envelope:
        advise["routing_envelope"] = envelope
        dispatches = envelope.get("dispatches") or []
        if dispatches:
            first = dispatches[0]
            advise["brief"] = first.get("prompt")
            advise["handoff_policy"] = first.get("handoff_policy")
            advise["artifact_path"] = first.get("artifact_path")

    return text_result(advise)




def tool_release_scorecard(args):
    """V8.6.0: Generate plugin release scorecard without returning stale timeout data."""
    import subprocess
    target = str(args.get("target") or "source")
    if target not in {"source", "all"}:
        target = "source"
    timeout_seconds = int(args.get("timeout_seconds") or 180)
    cmd = [
        sys.executable,
        str(PLUGIN_ROOT / "scripts/release-scorecard.py"),
        "--check",
        "--target",
        target,
        "--json",
    ]
    if args.get("no_gate_cache"):
        cmd.append("--no-gate-cache")
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
        try:
            report = json.loads(out.stdout)
        except json.JSONDecodeError:
            return text_result({
                "ok": False,
                "schema": "release_scorecard_tool.v2",
                "error": "scorecard stdout was not valid JSON",
                "command": cmd,
                "exit": out.returncode,
                "stdout": out.stdout[-4000:],
                "stderr": out.stderr[-4000:],
                "stale_report_used": False,
            }, is_error=True)
        report.setdefault("tool", {})
        report["tool"].update({
            "schema": "release_scorecard_tool.v2",
            "command": cmd,
            "exit": out.returncode,
            "target": target,
            "timeout_seconds": timeout_seconds,
            "stale_report_used": False,
        })
        return text_result(report, is_error=out.returncode != 0)
    except subprocess.TimeoutExpired as exc:
        return text_result({
            "ok": False,
            "schema": "release_scorecard_tool.v2",
            "error": "release scorecard timed out before completion",
            "command": cmd,
            "target": target,
            "timeout_seconds": timeout_seconds,
            "stdout": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            "suggested_cli": " ".join(cmd),
            "stale_report_used": False,
        }, is_error=True)
    except Exception as exc:
        return text_result({"ok": False, "schema": "release_scorecard_tool.v2", "error": str(exc), "stale_report_used": False}, is_error=True)



def tool_panel_plan(args):
    """V8.2.0: Return dispatch plan for a named panel.

    Args:
        panel_name: name of the panel (e.g. 'repo-completeness-panel')
        scope: optional scope arg (feature name, area, etc.)
    """
    panel_name = args.get("panel_name", "").strip()
    scope = args.get("scope", "")

    panels_path = PLUGIN_ROOT / "source" / "panel-specs.json"
    try:
        panels = json.loads(panels_path.read_text())
    except Exception as exc:
        return text_result({"error": f"could not load panel-specs.json: {exc}"}, is_error=True)

    if not panel_name:
        return text_result({
            "available_panels": [
                {
                    "name": p["name"],
                    "title": p["title"],
                    "use_when": p.get("use_when"),
                    "mode": p.get("mode"),
                    "risk": p.get("risk"),
                    "confirmation_required": (p.get("confirmation") or {}).get("required", False),
                    "pathfinder_tags": p.get("pathfinder_tags", []),
                    "estimated_cost": p.get("estimated_cost"),
                    "agents_total": sum(len(ph["agents"]) for ph in p["phases"]),
                }
                for p in panels
            ],
            "guidance": "Pass panel_name to get a full dispatch plan.",
        })

    panel = next((p for p in panels if p["name"] == panel_name), None)
    if not panel:
        return text_result({
            "error": f"panel '{panel_name}' not found",
            "available": [p["name"] for p in panels],
        }, is_error=True)

    # Build dispatch plan
    plan = {
        "panel_name": panel["name"],
        "title": panel["title"],
        "description": panel["description"],
        "scope": scope or "(no scope provided)",
        "estimated_cost": panel.get("estimated_cost"),
        "estimated_time_minutes": panel.get("estimated_time_minutes"),
        "mode": panel.get("mode"),
        "risk": panel.get("risk"),
        "confirmation": panel.get("confirmation", {}),
        "do_not_use_when": panel.get("do_not_use_when"),
        "inputs": panel.get("inputs", []),
        "success_criteria": panel.get("success_criteria", []),
        "handoff_artifacts": panel.get("handoff_artifacts", []),
        "pathfinder_tags": panel.get("pathfinder_tags", []),
        "policies": {
            "memory": panel.get("memory_policy", {}),
            "learning": panel.get("learning_policy", {}),
            "dream": panel.get("dream_policy", {}),
        },
        "validators": panel.get("validators", []),
        "ledger_writes": panel.get("ledger_writes", []),
        "resume_behavior": panel.get("resume_behavior"),
        "cancel_behavior": panel.get("cancel_behavior"),
        "writes_gap_ledger": panel.get("writes_gap_ledger", False),
        "output_artifact": panel.get("output_artifact"),
        "phases": [],
        "synthesis_strategy": (
            "Run phases sequentially. Within phases marked parallel=true, dispatch all agents "
            "simultaneously (single message with multiple Task calls). Pass each agent the "
            "output of prior phases as context. Synthesize via the synthesize-phase agent."
        ),
    }
    for phase in panel["phases"]:
        contract = panel.get("phase_contracts", {}).get(phase["phase"], {})
        phase_plan = {
            "phase": phase["phase"],
            "purpose": phase.get("purpose"),
            "parallel": phase.get("parallel", False),
            "contract": contract,
            "dispatches": [
                {
                    "subagent_type": f"ultraprompt:{agent}",
                    "task_brief": (
                        f"focus: {scope or 'as-described'}\n"
                        f"phase: {phase['phase']}\n"
                        f"panel: {panel['name']}\n\n"
                        f"phase_contract: {json.dumps(contract, sort_keys=True)}\n\n"
                        f"Apply discipline at ${{CLAUDE_PLUGIN_ROOT}}/_shared/DISCIPLINE.md. "
                        f"Produce structured output per your output contract."
                    ),
                }
                for agent in phase["agents"]
            ],
        }
        plan["phases"].append(phase_plan)

    return text_result(plan)



def tool_mission_state(args):
    """V8.2.0: Mission Control unified state snapshot.

    Reads from repo capsule, worktree state, sessions, evidence ledger v2,
    WIP snapshots, gap ledger. Returns the V8 mission_state schema.

    Args:
        path: optional worktree path (default: cwd)
        write: if true, persists snapshot to ~/.ultraprompt/state/mission-state.json
    """
    import subprocess
    path = args.get("path", ".")
    write = args.get("write", False)
    try:
        cmd = [sys.executable, str(PLUGIN_ROOT / "scripts" / "mission-state.py"),
               "snapshot", "--worktree", path]
        if write:
            cmd.append("--write")
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return text_result(json.loads(out.stdout))
    except Exception as exc:
        return text_result({"error": str(exc)}, is_error=True)


def tool_gap_ledger_query(args):
    """V8.2.0: Query gap ledger.

    Args:
        repo: filter by repo name
        status: filter by status (open|accepted|fixed|false_positive|deferred)
        severity: filter by severity (critical|high|medium|low)
        limit: max results (default 50)
    """
    import subprocess
    cmd_args = [sys.executable, str(PLUGIN_ROOT / "scripts" / "gap-ledger.py"), "list"]
    if args.get("repo"): cmd_args += ["--repo", args["repo"]]
    if args.get("status"): cmd_args += ["--status", args["status"]]
    if args.get("severity"): cmd_args += ["--severity", args["severity"]]
    if args.get("fingerprint"): cmd_args += ["--fingerprint", args["fingerprint"]]
    if args.get("history"): cmd_args += ["--history"]
    if args.get("limit"): cmd_args += ["--limit", str(args["limit"])]
    try:
        out = subprocess.run(cmd_args, capture_output=True, text=True, timeout=15)
        return text_result(json.loads(out.stdout))
    except Exception as exc:
        return text_result({"error": str(exc)}, is_error=True)


def tool_gap_ledger_write(args):
    """V8.2.0: Write gap entry to persistent ledger.

    Required fields: repo, category, severity, confidence, title, evidence
    Optional: affected_area, expected_behavior, actual_behavior, recommended_fix,
             validation_plan, suggested_owner_agent, suggested_skill, auditor.
    """
    import subprocess
    import tempfile
    required = ["repo", "title", "category", "severity", "confidence", "evidence"]
    missing = [field for field in required if not args.get(field)]
    if missing:
        return text_result({"error": "missing required fields", "missing": missing}, is_error=True)
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(args, f)
            tmp_path = f.name
        out = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "gap-ledger.py"), "write", tmp_path],
            capture_output=True, text=True, timeout=10
        )
        Path(tmp_path).unlink(missing_ok=True)
        return text_result(json.loads(out.stdout))
    except Exception as exc:
        return text_result({"error": str(exc)}, is_error=True)


def tool_gap_ledger_stats(args):
    """V8.2.0: Gap ledger summary stats."""
    import subprocess
    try:
        out = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "gap-ledger.py"), "stats"],
            capture_output=True, text=True, timeout=10
        )
        return text_result(json.loads(out.stdout))
    except Exception as exc:
        return text_result({"error": str(exc)}, is_error=True)



def tool_artifact_validate(args):
    """V8: Validate a structured artifact against its schema.

    Args:
        artifact_type: e.g. 'prd_lite', 'gap_ledger_entry', 'release_readiness_report'
        artifact: the artifact data (dict)
    """
    import subprocess
    import tempfile

    artifact_type = args.get("artifact_type", "").strip()
    artifact_data = args.get("artifact", {})

    if not artifact_type:
        # No type: return schema list
        try:
            out = subprocess.run(
                [sys.executable, str(PLUGIN_ROOT / "scripts/artifact-validate.py"), "schemas"],
                capture_output=True, text=True, timeout=10,
            )
            return text_result(json.loads(out.stdout))
        except Exception as exc:
            return text_result({"error": str(exc)}, is_error=True)

    if not artifact_data:
        # Type but no artifact: return schema for that type
        try:
            out = subprocess.run(
                [sys.executable, str(PLUGIN_ROOT / "scripts/artifact-validate.py"), "schema", artifact_type],
                capture_output=True, text=True, timeout=10,
            )
            return text_result(json.loads(out.stdout))
        except Exception as exc:
            return text_result({"error": str(exc)}, is_error=True)

    # Validate the artifact
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(artifact_data, f)
            tmp_path = f.name
        out = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts/artifact-validate.py"),
             "validate", artifact_type, tmp_path],
            capture_output=True, text=True, timeout=15,
        )
        Path(tmp_path).unlink(missing_ok=True)
        return text_result(json.loads(out.stdout))
    except Exception as exc:
        return text_result({"error": str(exc)}, is_error=True)


def tool_catalog_audit(args):
    """V8: Run catalog robustness audit across all agents + skills + panels.

    Returns structured findings by severity (critical/high/medium/low) for:
    short descriptions, missing trigger phrasing, missing lane boundaries,
    missing output contracts, duplicate descriptions, dispatch_to references
    to missing agents, panel references to missing agents, etc.
    """
    import subprocess
    try:
        subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts/catalog-audit.py")],
            capture_output=True, text=True, timeout=30,
        )
        # Read the JSON report
        report_path = PLUGIN_ROOT / "dist/catalog-audit-report.json"
        state_dir = Path.home() / ".ultraprompt" / "state"
        candidates = [report_path, *state_dir.glob("catalog-audit-report*.json")]
        existing = [p for p in candidates if p.exists()]
        if existing:
            report_path = max(existing, key=lambda p: p.stat().st_mtime)
        report = json.loads(report_path.read_text())
        return text_result(report)
    except Exception as exc:
        return text_result({"error": str(exc)}, is_error=True)


def _dashboard_state_files():
    state_dir = Path.home() / ".ultraprompt" / "state"
    return state_dir / "dashboard.pid", state_dir / "dashboard.port"


def _pid_running(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            exit_code = wintypes.DWORD()
            if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == 259
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _terminate_pid(pid: int) -> None:
    if sys.platform == "win32":
        import subprocess
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=5)
        return
    import signal
    os.kill(pid, signal.SIGTERM)


def _dashboard_running():
    """Returns (running, pid, port)."""
    pid_file, port_file = _dashboard_state_files()
    if not pid_file.exists() or not port_file.exists():
        return False, None, None
    try:
        pid = int(pid_file.read_text().strip())
        port = int(port_file.read_text().strip())
        if _pid_running(pid):
            return True, pid, port
        pid_file.unlink(missing_ok=True)
        port_file.unlink(missing_ok=True)
        return False, None, None
    except ValueError:
        pid_file.unlink(missing_ok=True)
        port_file.unlink(missing_ok=True)
        return False, None, None


def tool_dashboard_launch(args):
    """V8: Launch the Ultraprompt live dashboard.

    Args:
        no_open: optional bool, skip auto-opening browser
        port: optional int, override port (default scans 5174-5199)
    """
    import subprocess
    import time

    running, pid, port = _dashboard_running()
    if running:
        return text_result({
            "already_running": True,
            "pid": pid,
            "port": port,
            "url": f"http://localhost:{port}/",
            "note": "dashboard already running; open this URL in browser",
        })

    cmd = [sys.executable, str(PLUGIN_ROOT / "scripts/dashboard.py")]
    if args.get("no_open"):
        cmd.append("--no-open")
    if args.get("port"):
        cmd.extend(["--port", str(args["port"])])

    try:
        log_dir = Path.home() / ".ultraprompt" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "dashboard.log"

        proc = subprocess.Popen(
            cmd,
            stdout=open(log_path, "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=str(PLUGIN_ROOT),
        )

        # Wait up to 3s for pid/port files to materialize
        for _ in range(30):
            time.sleep(0.1)
            running, pid, port = _dashboard_running()
            if running:
                break

        if not running:
            return text_result({
                "error": "dashboard failed to start; check log",
                "log_path": str(log_path),
                "command": " ".join(cmd),
            }, is_error=True)

        return text_result({
            "ok": True,
            "pid": pid,
            "port": port,
            "url": f"http://localhost:{port}/",
            "log_path": str(log_path),
            "note": "dashboard launched; browser opening to this URL",
        })
    except Exception as exc:
        return text_result({"error": str(exc)}, is_error=True)


def tool_dashboard_status(args):
    """V8: Check if the Ultraprompt dashboard is running."""
    running, pid, port = _dashboard_running()
    return text_result({
        "running": running,
        "pid": pid,
        "port": port,
        "url": f"http://localhost:{port}/" if port else None,
        "log_path": str(Path.home() / ".ultraprompt" / "logs" / "dashboard.log"),
    })


def tool_dashboard_stop(args):
    """V8: Stop the Ultraprompt dashboard."""
    import signal
    running, pid, port = _dashboard_running()
    if not running:
        return text_result({"ok": True, "note": "dashboard was not running"})
    try:
        _terminate_pid(pid)
        pid_file, port_file = _dashboard_state_files()
        pid_file.unlink(missing_ok=True)
        port_file.unlink(missing_ok=True)
        return text_result({"ok": True, "stopped_pid": pid})
    except Exception as exc:
        return text_result({"error": str(exc)}, is_error=True)


# -------------------- V8 cognitive tools --------------------

def _run_json_script(script_name: str, argv: list[str], *, timeout: int = 60) -> dict[str, Any]:
    import subprocess
    cmd = [sys.executable, str(PLUGIN_ROOT / "scripts" / script_name), *argv]
    proc = subprocess.run(cmd, cwd=str(PLUGIN_ROOT), capture_output=True, text=True, timeout=timeout)
    try:
        data = json.loads(proc.stdout)
    except Exception:
        data = {
            "ok": proc.returncode == 0,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    if isinstance(data, dict):
        data.setdefault("plugin_version", plugin_version())
        data.setdefault("script", script_name)
        data.setdefault("exit", proc.returncode)
    return data


def tool_memory_query(args: dict[str, Any]) -> dict[str, Any]:
    argv = ["query", "--limit", str(args.get("limit", 50))]
    for key in ("text", "kind", "scope", "entity", "repo", "status"):
        value = str(args.get(key, "")).strip()
        if value:
            argv.extend([f"--{key.replace('_', '-')}", value])
    if args.get("include_inactive"):
        argv.append("--include-inactive")
    if args.get("redacted"):
        argv.append("--redacted")
    return text_result(_run_json_script("memory-store.py", argv))


def tool_memory_write_candidate(args: dict[str, Any]) -> dict[str, Any]:
    argv = [
        "write-candidate",
        "--kind", str(args.get("kind", "")),
        "--scope", str(args.get("scope", "")),
        "--text", str(args.get("text", "")),
        "--privacy", str(args.get("privacy", "metadata")),
        "--confidence", str(args.get("confidence", 0.6)),
        "--importance", str(args.get("importance", 0.5)),
    ]
    for key in ("repo", "project", "entity", "source", "reason"):
        value = str(args.get(key, "")).strip()
        if value:
            argv.extend([f"--{key.replace('_', '-')}", value])
    for evidence in args.get("evidence", []) or []:
        if isinstance(evidence, dict):
            argv.extend(["--evidence", f"{evidence.get('kind')}:{evidence.get('ref')}"])
        else:
            argv.extend(["--evidence", str(evidence)])
    return text_result(_run_json_script("memory-store.py", argv))


def tool_memory_promote(args: dict[str, Any]) -> dict[str, Any]:
    memory_id = str(args.get("memory_id", "")).strip()
    if not memory_id:
        return text_result({"ok": False, "error": "memory_id is required"}, is_error=True)
    argv = ["promote", memory_id]
    for evidence in args.get("evidence", []) or []:
        if isinstance(evidence, dict):
            argv.extend(["--evidence", f"{evidence.get('kind')}:{evidence.get('ref')}"])
        else:
            argv.extend(["--evidence", str(evidence)])
    if args.get("reason"):
        argv.extend(["--reason", str(args["reason"])])
    data = _run_json_script("memory-store.py", argv)
    data["risk"] = "medium"
    data["confirmation_required"] = True
    return text_result(data, is_error=not data.get("ok", False))


def tool_memory_forget(args: dict[str, Any]) -> dict[str, Any]:
    memory_id = str(args.get("memory_id", "")).strip()
    if not memory_id:
        return text_result({"ok": False, "error": "memory_id is required"}, is_error=True)
    argv = ["forget", memory_id]
    if args.get("reason"):
        argv.extend(["--reason", str(args["reason"])])
    data = _run_json_script("memory-store.py", argv)
    data["risk"] = "medium"
    data["confirmation_required"] = True
    return text_result(data, is_error=not data.get("ok", False))


def tool_memory_stats(args: dict[str, Any]) -> dict[str, Any]:
    return text_result(_run_json_script("memory-store.py", ["stats"]))


def tool_dream_run(args: dict[str, Any]) -> dict[str, Any]:
    job = str(args.get("job", "")).strip()
    defaulted_job = False
    if not job:
        job = "session-compaction"
        defaulted_job = True
    argv = ["run", job]
    if args.get("repo"):
        argv.extend(["--repo", str(args["repo"])])
    if args.get("dry_run", False):
        argv.append("--dry-run")
    data = _run_json_script("dream-runner.py", argv, timeout=120)
    data["risk"] = "low"
    data["confirmation_required"] = False
    data["defaulted_job"] = defaulted_job
    return text_result(data, is_error=not data.get("ok", False))


def tool_dream_status(args: dict[str, Any]) -> dict[str, Any]:
    return text_result(_run_json_script("dream-runner.py", ["status"]))


def tool_dream_review(args: dict[str, Any]) -> dict[str, Any]:
    return text_result(_run_json_script("dream-runner.py", ["review", "--limit", str(args.get("limit", 10))]))


def tool_pathfind_workflow(args: dict[str, Any]) -> dict[str, Any]:
    intent = str(args.get("intent", "")).strip()
    if not intent:
        return text_result({"ok": False, "error": "intent is required"}, is_error=True)
    argv = ["pathfind", "--intent", intent, "--budget", str(args.get("budget", "standard"))]
    if args.get("repo"):
        argv.extend(["--repo", str(args["repo"])])
    if args.get("dry_run", True):
        argv.append("--dry-run")
    if args.get("no_telemetry", False):
        argv.append("--no-telemetry")
    return text_result(_run_json_script("pathfinder.py", argv, timeout=60))


def tool_route_trigger_plan(args: dict[str, Any]) -> dict[str, Any]:
    """V8.5: Return a dry-run main-thread action plan for an intent."""
    intent = str(args.get("intent", "")).strip()
    if not intent:
        return text_result({"ok": False, "error": "intent is required"}, is_error=True)
    runtime = str(args.get("runtime", "codex"))
    budget = str(args.get("budget", "standard"))
    repo = str(args.get("repo", ""))
    constraints = args.get("constraints") if isinstance(args.get("constraints"), dict) else {}
    data = run_pathfind_for_decision(intent, runtime=runtime, budget=budget, repo=repo, constraints=constraints)
    if data.get("ok") and not args.get("no_telemetry", False):
        decision = data.get("routing_decision") or {}
        _run_json_script(
            "cognitive-event-log.py",
            [
                "write",
                "route_trigger_plan_emitted",
                "--json",
                json.dumps({
                    "producer": "route_trigger_plan",
                    "telemetry_source": "runtime",
                    "trace_id": decision.get("trace_id"),
                    "intent": intent[:200],
                    "skill": decision.get("top_skill"),
                    "decision_type": decision.get("decision_type"),
                    "execution_mode": decision.get("execution_mode"),
                    "panel": decision.get("panel"),
                    "handoff_policy": decision.get("handoff_policy"),
                    "handoff_contract_status": decision.get("handoff_contract_status"),
                    "reliability": decision.get("reliability"),
                    "dry_run": True,
                }),
                "--trace-id",
                str(decision.get("trace_id") or ""),
            ],
        )
    return text_result(data, is_error=not data.get("ok", False))


def tool_capability_graph(args: dict[str, Any]) -> dict[str, Any]:
    argv = ["--json"]
    data = _run_json_script("build-capability-graph.py", argv, timeout=60)
    if not args.get("include_graph", False) and isinstance(data.get("graph"), dict):
        graph = data["graph"]
        data["summary"] = {
            "node_count": len(graph.get("nodes", [])),
            "edge_count": len(graph.get("edges", [])),
            "health": graph.get("health", {}),
            "source_hash": graph.get("source_hash"),
        }
        data.pop("graph", None)
    return text_result(data, is_error=not data.get("ok", False))


def tool_learning_candidates(args: dict[str, Any]) -> dict[str, Any]:
    argv = ["list", "--limit", str(args.get("limit", 100))]
    if args.get("status"):
        argv.extend(["--status", str(args["status"])])
    if args.get("kind"):
        argv.extend(["--kind", str(args["kind"])])
    if args.get("grouped"):
        argv.append("--grouped")
    return text_result(_run_json_script("learning-queue.py", argv))


def tool_learning_apply(args: dict[str, Any]) -> dict[str, Any]:
    candidate_id = str(args.get("candidate_id", "")).strip()
    if not candidate_id:
        return text_result({"ok": False, "error": "candidate_id is required"}, is_error=True)
    action = str(args.get("action", "apply"))
    if action not in {"approve", "reject", "apply", "revert"}:
        return text_result({"ok": False, "error": "action must be approve|reject|apply|revert"}, is_error=True)
    argv = [action, candidate_id]
    if action == "apply" and args.get("force"):
        argv.append("--force")
    data = _run_json_script("learning-queue.py", argv, timeout=180)
    data["risk"] = "medium"
    data["confirmation_required"] = action in {"apply", "revert"}
    return text_result(data, is_error=not data.get("ok", False))


def tool_self_improve_run(args: dict[str, Any]) -> dict[str, Any]:
    argv = [
        "run",
        "--mode",
        str(args.get("mode", "dry-run")),
        "--scope",
        str(args.get("scope", "all")),
    ]
    if args.get("repo"):
        argv.extend(["--repo", str(args["repo"])])
    data = _run_json_script("self-improve.py", argv, timeout=420)
    data["risk"] = "high" if args.get("mode") == "autopilot" else "medium"
    data["confirmation_required"] = False
    return text_result(data, is_error=not data.get("ok", False))


def tool_self_improve_runs(args: dict[str, Any]) -> dict[str, Any]:
    data = _run_json_script("self-improve.py", ["list", "--limit", str(args.get("limit", 20))], timeout=30)
    return text_result(data, is_error=not data.get("ok", False))


def tool_self_improve_rollback(args: dict[str, Any]) -> dict[str, Any]:
    run_id = str(args.get("run_id", "")).strip()
    if not run_id:
        return text_result({"ok": False, "error": "run_id is required"}, is_error=True)
    data = _run_json_script("self-improve.py", ["rollback", run_id], timeout=60)
    data["risk"] = "medium"
    data["confirmation_required"] = False
    return text_result(data, is_error=not data.get("ok", False))


def tool_route_feedback(args: dict[str, Any]) -> dict[str, Any]:
    intent = str(args.get("intent", "")).strip()
    outcome = str(args.get("outcome", "")).strip()
    skill = str(args.get("skill", "")).strip()
    corrected_skill = str(args.get("corrected_skill", "")).strip()
    selected_panel = str(args.get("selected_panel", "")).strip()
    corrected_panel = str(args.get("corrected_panel", "")).strip()
    agent = str(args.get("agent", "")).strip()
    corrected_agent = str(args.get("corrected_agent", "")).strip()
    handoff_status = str(args.get("handoff_status", "")).strip()
    failure_kind = str(args.get("failure_kind", "")).strip()
    artifact_path = str(args.get("artifact_path", "")).strip()
    tool_count = args.get("tool_count")
    token_count = args.get("token_count")
    trace_id = str(args.get("trace_id", "")).strip() or sortable_id("route")
    payload = {
        "schema": "route_outcome.v1",
        "trace_id": trace_id,
        "intent": intent,
        "outcome": outcome,
        "selected_skill": skill,
        "skill": skill,
        "corrected_skill": corrected_skill,
        "selected_panel": selected_panel,
        "corrected_panel": corrected_panel,
        "agent": agent,
        "corrected_agent": corrected_agent,
        "handoff_status": handoff_status,
        "failure_kind": failure_kind,
        "artifact_path": artifact_path,
        "tool_count": tool_count,
        "token_count": token_count,
        "reason": str(args.get("reason", "")),
        "evidence_refs": args.get("evidence_refs", []),
    }
    event_args = ["write", "route_outcome", "--json", json.dumps(payload), "--privacy", "metadata"]
    if trace_id:
        event_args.extend(["--trace-id", trace_id])
    event = _run_json_script("cognitive-event-log.py", event_args)
    learning = None
    handoff_failed = handoff_status in {"partial", "truncated", "persisted_output", "empty"}
    if (outcome in {"corrected", "failed"} or handoff_failed or agent == "Explore") and (corrected_skill or skill or corrected_panel):
        learning = _run_json_script(
            "learning-queue.py",
            [
                "add", "--kind", "route_update",
                "--title", "Route feedback candidate",
                "--payload-json", json.dumps({
                    "intent_pattern": intent[:80],
                    "skill": corrected_skill or skill,
                    "panel": corrected_panel or selected_panel,
                    "agent": corrected_agent or agent,
                    "handoff_status": handoff_status,
                    "failure_kind": failure_kind,
                    "artifact_path": artifact_path,
                    "tool_count": tool_count,
                    "token_count": token_count,
                    "weight_delta": 0.1,
                    "reason": str(args.get("reason", "")),
                }),
                "--evidence-json",
                json.dumps(args.get("evidence_refs", [])),
            ],
        )
    if handoff_status:
        _run_json_script(
            "cognitive-event-log.py",
            [
                "write", "agent_handoff",
                "--json", json.dumps({
                    "trace_id": trace_id,
                    "intent": intent[:200],
                    "skill": skill,
                    "agent": agent,
                    "handoff_status": handoff_status,
                    "failure_kind": failure_kind,
                    "artifact_path": artifact_path,
                    "tool_count": tool_count,
                    "token_count": token_count,
                }),
                "--trace-id", trace_id,
            ],
        )
    return text_result({"ok": event.get("ok", False), "event": event, "learning_candidate": learning, "schema_version": "route_feedback.v1", "plugin_version": plugin_version()})
# -------------------- tool registry --------------------

TOOLS: dict[str, tuple[str, dict[str, Any], Callable[[dict[str, Any]], dict[str, Any]]]] = {
    "list_skills": (
        "List Ultraprompt skills from the generated index. Read-only. Filter by tier (core|specialist|ecosystem) or query.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional substring filter"},
                "tier": {"type": "string", "enum": ["core", "specialist", "ecosystem", ""], "default": ""},
                "include_manual": {"type": "boolean", "default": True},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 80},
            },
        },
        tool_list_skills,
    ),
    "route_intent": (
        "Route a free-form task intent to the best 1-3 Ultraprompt skills.",
        {
            "type": "object",
            "required": ["intent"],
            "properties": {
                "intent": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3},
            },
        },
        tool_route_intent,
    ),
    "explain_skill": (
        "Return indexed metadata for one Ultraprompt skill. Resolves V4 aliases.",
        {"type": "object", "required": ["skill"], "properties": {"skill": {"type": "string"}}},
        tool_explain_skill,
    ),
    "list_agents": (
        "List Ultraprompt plugin subagents from the generated index. Read-only.",
        {"type": "object", "properties": {"query": {"type": "string"}}},
        tool_list_agents,
    ),
    "validate_plugin": (
        "Run the bundled Ultraprompt validator and return stdout. Read-only.",
        {"type": "object", "properties": {}},
        tool_validate_plugin,
    ),
    "compose_workflow": (
        "[DEPRECATED; use team_plan] Compose a small sequential workflow from named skills.",
        {
            "type": "object",
            "required": ["skills"],
            "properties": {
                "skills": {"type": "array", "items": {"type": "string"}},
            },
        },
        tool_compose_workflow,
    ),
    "claim_check": (
        "Scan draft answer text for unbacked validation claims. Returns warnings if claims like 'tests passed' have no supporting validation event in the evidence ledger.",
        {
            "type": "object",
            "required": ["text"],
            "properties": {"text": {"type": "string", "description": "Draft answer text to scan"}},
        },
        tool_claim_check,
    ),
    "query_ledger": (
        "Return evidence ledger events matching the given filter. Read-only.",
        {
            "type": "object",
            "properties": {
                "event": {"type": "string", "description": "Event name filter (e.g. PostToolUse, SubagentStart)"},
                "tool": {"type": "string", "description": "Tool name filter (Bash, Edit, Write, MultiEdit)"},
                "validation_only": {"type": "boolean", "default": False},
                "since": {"type": "string", "description": "ISO timestamp"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
            },
        },
        tool_query_ledger,
    ),
    "validation_status": (
        "Return aggregate session status: validation_seen, edits_seen, summary.",
        {"type": "object", "properties": {}},
        tool_validation_status,
    ),
    "evidence_diff": (
        "Return events recorded since a timestamp.",
        {
            "type": "object",
            "required": ["since"],
            "properties": {"since": {"type": "string"}},
        },
        tool_evidence_diff,
    ),
    "team_plan": (
        "V8.2.0: aliased to panel_plan (preferred). Return a parallel-agent orchestration plan for a panel-run pattern. Patterns: review-fanout, debug-t...",
        {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "enum": ["review-fanout", "debug-triangulate", "migration-assess", "release-panel", ""],
                },
                "problem": {"type": "string"},
                "agents": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string"},
                            "focus": {"type": "string"},
                        },
                    },
                },
                "synthesis": {"type": "string"},
            },
        },
        tool_team_plan,
    ),
    "repo_capsule": (
        "Return a compact repository contract capsule. Cached by repo_root + git HEAD; pass force_refresh=true to bypass cache.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": "."},
                "force_refresh": {"type": "boolean", "default": False},
            },
        },
        tool_repo_capsule,
    ),
    "repo_capsule_diff": (
        "Return contract drift between current capsule and a prior commit's capsule. Reveals package-manager changes, validation-command changes, new sensitive paths, etc.",
        {
            "type": "object",
            "required": ["since_commit"],
            "properties": {
                "path": {"type": "string", "default": "."},
                "since_commit": {"type": "string"},
            },
        },
        tool_repo_capsule_diff,
    ),
    "worktree_state": (
        "V8: Return state of all worktrees in the current repo. Includes branch, dirty/untracked counts, stash count, unpushed count, in-progress operations, last activity timestamp.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Repo path (default: cwd)"},
            },
        },
        tool_worktree_state,
    ),
    "session_lookup": (
        "V8: Find Claude Code / Codex sessions currently active in a worktree path.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Worktree path"},
                "window_minutes": {"type": "integer", "minimum": 1, "maximum": 240, "default": 15},
            },
        },
        tool_session_lookup,
    ),
    "ledger_query": (
        "V8: Query the always-on evidence ledger v2 with filters (days, event types, repo, worktree).",
        {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "minimum": 1, "maximum": 365, "default": 7},
                "types": {"type": "array", "items": {"type": "string"}},
                "repo": {"type": "string"},
                "worktree": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 200},
            },
        },
        tool_ledger_query,
    ),
    "release_scorecard": (
        "V8.6.0: Generate a release-readiness scorecard for the plugin with classified gates, runtime targets, telemetry adoption state, routing policy, self-improvement regression classification, and conclusion. Returns live --check JSON and reports timeout explicitly without falling back to stale dist output.",
        {
            "type": "object",
            "properties": {
                "target": {"type": "string", "enum": ["source", "all"], "default": "source"},
                "timeout_seconds": {"type": "integer", "minimum": 30, "maximum": 900, "default": 180},
                "no_gate_cache": {"type": "boolean", "default": False},
            },
        },
        tool_release_scorecard,
    ),
    "panel_plan": (
        "V8.2.0: Return dispatch plan for a named expert panel from source/panel-specs.json. Without panel_name returns the catalog. With panel_name returns phased dispatch plan including mode, risk, confirmation, inputs, success criteria, cognitive policies, phase contracts, parallel/sequential strategy, agent task briefs, and synthesis approach. Pass scope as the panel's focus argument (feature name, area, version, etc.).",
        {
            "type": "object",
            "properties": {
                "panel_name": {"type": "string", "description": "Panel name (e.g. 'repo-completeness-panel'). Omit to list catalog."},
                "scope": {"type": "string", "description": "Optional scope/focus argument passed to all dispatched agents."},
            },
        },
        tool_panel_plan,
    ),
    "mission_state": (
        "V8.2.0: Mission Control unified state snapshot. Reads repo capsule, worktree state, sessions, ledger, WIP snapshots, gap ledger. Returns single view of repo + worktree + sessions + evidence + recovery + gaps + panels.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Worktree path (default: cwd)"},
                "write": {"type": "boolean", "description": "Persist snapshot to ~/.ultraprompt/state/mission-state.json"},
            },
        },
        tool_mission_state,
    ),
    "gap_ledger_query": (
        "V8.2.0: Query persistent gap ledger at ~/.ultraprompt/gaps/<repo>/gap-ledger.jsonl. Defaults to latest-by-fingerprint; pass history=true for append-only lifecycle records.",
        {
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "status": {"type": "string", "description": "open|accepted|in_progress|fixed|validated|false_positive|deferred"},
                "severity": {"type": "string", "description": "critical|high|medium|low"},
                "fingerprint": {"type": "string"},
                "history": {"type": "boolean", "default": False},
                "limit": {"type": "integer"},
            },
        },
        tool_gap_ledger_query,
    ),
    "gap_ledger_write": (
        "V8.2.0: Persist a schema-valid gap finding to the gap ledger. Writes fingerprinted lifecycle records for repo-completeness audit skills and panel syntheses.",
        {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Required: repo name"},
                "title": {"type": "string", "description": "Required: short summary"},
                "category": {"type": "string", "description": "incomplete_feature|wiring_gap|contract_mismatch|missing_test|release_blocker|stale_code|documentation_drift|dead_code|observability_gap|configuration_gap"},
                "severity": {"type": "string"},
                "confidence": {"type": "string"},
                "affected_area": {"type": "string"},
                "evidence": {"type": "object"},
                "expected_behavior": {"type": "string"},
                "actual_behavior": {"type": "string"},
                "recommended_fix": {"type": "string"},
                "validation_plan": {"type": "string"},
                "suggested_owner_agent": {"type": "string"},
                "suggested_skill": {"type": "string"},
                "owner_agent": {"type": "string"},
                "fix_skill": {"type": "string"},
                "panel_run_ids": {"type": "array", "items": {"type": "string"}},
                "auditor": {"type": "string"},
            },
            "required": ["repo", "title", "category", "severity", "confidence", "evidence"],
        },
        tool_gap_ledger_write,
    ),
    "gap_ledger_stats": (
        "V8.2: Gap ledger summary stats â€” totals by status/severity/category/repo/auditor.",
        {"type": "object", "properties": {}},
        tool_gap_ledger_stats,
    ),
    "artifact_validate": (
        "V8.5: Validate structured artifact against schema. Catches the 'fluffy artifact' failure mode. Known artifact types include PRDs, gap/review/release reports, route telemetry artifacts, learning candidates, and self_improvement_run/self_improvement_patch/learner_eval_report/rollback_manifest. Without artifact_type: returns schema list. With type but no artifact: returns schema. With both: validates and returns findings.",
        {
            "type": "object",
            "properties": {
                "artifact_type": {"type": "string"},
                "artifact": {"type": "object"},
            },
        },
        tool_artifact_validate,
    ),
    "catalog_audit": (
        "V8: Run catalog robustness audit (PRD Â§27.4). Scans all agents and skills for: short descriptions, missing trigger phrasing (USE WHEN), missing lane boundaries, missing output contracts, anti-patterns, duplicate descriptions, dispatch_to references resolving, panel references resolving. Returns findings by severity (critical/high/medium/low). Used in CI and pre-release governance.",
        {"type": "object", "properties": {}},
        tool_catalog_audit,
    ),
    "dashboard_launch": (
        "V8.5: Launch the Ultraprompt live dashboard (localhost browser UI). Three-pane layout: catalog tree (31 agents, 55 skills, 13 panels, 46 MCP tools, 32 commands, 31 artifact schemas) on the left; entity detail in the center; live invocation feed on the right via Server-Sent Events. Auto-opens browser. Idempotent; if already running, returns the existing URL. Optional args: no_open (skip browser launch), port (override default).",
        {
            "type": "object",
            "properties": {
                "no_open": {"type": "boolean"},
                "port": {"type": "integer"},
            },
        },
        tool_dashboard_launch,
    ),
    "dashboard_status": (
        "V8: Check if the Ultraprompt dashboard is running. Returns pid, port, URL, log path.",
        {"type": "object", "properties": {}},
        tool_dashboard_status,
    ),
    "dashboard_stop": (
        "V8: Stop the Ultraprompt dashboard process. Sends SIGTERM and cleans up pid/port files.",
        {"type": "object", "properties": {}},
        tool_dashboard_stop,
    ),
    "memory_query": (
        "V8: Query typed local memory by text, kind, scope, entity, repo, status, confidence, and importance.",
        {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "kind": {"type": "string"},
                "scope": {"type": "string"},
                "entity": {"type": "string"},
                "repo": {"type": "string"},
                "status": {"type": "string"},
                "include_inactive": {"type": "boolean", "default": False},
                "redacted": {"type": "boolean", "default": False},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
            },
        },
        tool_memory_query,
    ),
    "memory_write_candidate": (
        "V8: Write a candidate memory after schema, scope, privacy, and secret checks.",
        {
            "type": "object",
            "required": ["kind", "scope", "text"],
            "properties": {
                "kind": {"type": "string"},
                "scope": {"type": "string"},
                "text": {"type": "string"},
                "privacy": {"type": "string", "default": "metadata"},
                "repo": {"type": "string"},
                "project": {"type": "string"},
                "entity": {"type": "string"},
                "source": {"type": "string"},
                "confidence": {"type": "number", "default": 0.6},
                "importance": {"type": "number", "default": 0.5},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "reason": {"type": "string"},
            },
        },
        tool_memory_write_candidate,
    ),
    "memory_promote": (
        "V8: Promote a candidate memory to active memory. Mutating; returns risk and confirmation metadata.",
        {
            "type": "object",
            "required": ["memory_id"],
            "properties": {
                "memory_id": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "reason": {"type": "string"},
            },
        },
        tool_memory_promote,
    ),
    "memory_forget": (
        "V8: Forget/delete a memory record locally. Mutating; returns risk and confirmation metadata.",
        {"type": "object", "required": ["memory_id"], "properties": {"memory_id": {"type": "string"}, "reason": {"type": "string"}}},
        tool_memory_forget,
    ),
    "memory_stats": (
        "V8: Return memory store counts by kind, scope, and status.",
        {"type": "object", "properties": {}},
        tool_memory_stats,
    ),
    "dream_run": (
        "V8.5: Run a dream job manually. Jobs are read-only except self-improvement-autopilot, which may mutate local repo files only through the gated self-improvement runner. If job is omitted, defaults to session-compaction.",
        {
            "type": "object",
            "properties": {
                "job": {"type": "string", "default": "session-compaction"},
                "repo": {"type": "string"},
                "dry_run": {"type": "boolean", "default": False},
            },
        },
        tool_dream_run,
    ),
    "dream_status": (
        "V8: Return dream report, lock, and scheduler status.",
        {"type": "object", "properties": {}},
        tool_dream_status,
    ),
    "dream_review": (
        "V8: Return recent dream reports for governance review.",
        {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10}}},
        tool_dream_review,
    ),
    "pathfind_workflow": (
        "V8: Recommend and explain the skill/agent/command/panel path for an intent, including memory influences, alternatives, graph hash, risk, and cost.",
        {
            "type": "object",
            "required": ["intent"],
            "properties": {
                "intent": {"type": "string"},
                "repo": {"type": "string"},
                "budget": {"type": "string", "enum": ["low", "standard", "deep"], "default": "standard"},
                "dry_run": {"type": "boolean", "default": True},
                "no_telemetry": {"type": "boolean", "default": False},
            },
        },
        tool_pathfind_workflow,
    ),
    "route_trigger_plan": (
        "V8.5: Dry-run Invocation Director contract. Returns the exact main-thread action plan for an intent without executing agents, panels, or mutating work.",
        {
            "type": "object",
            "required": ["intent"],
            "properties": {
                "intent": {"type": "string"},
                "runtime": {"type": "string", "enum": ["codex", "claude-code", "generic"], "default": "codex"},
                "repo": {"type": "string"},
                "budget": {"type": "string", "enum": ["low", "standard", "deep"], "default": "standard"},
                "constraints": {"type": "object"},
                "dry_run": {"type": "boolean", "default": True},
                "no_telemetry": {"type": "boolean", "default": False},
            },
        },
        tool_route_trigger_plan,
    ),
    "capability_graph": (
        "V8: Return capability graph health, source hash, node counts, and optionally full graph JSON.",
        {"type": "object", "properties": {"include_graph": {"type": "boolean", "default": False}}},
        tool_capability_graph,
    ),
    "learning_candidates": (
        "V8.5: List evidence-backed learning candidates by status or kind, optionally grouped by route failure evidence and self-improvement provenance.",
        {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "kind": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
                "grouped": {"type": "boolean", "default": False},
            },
        },
        tool_learning_candidates,
    ),
    "learning_apply": (
        "V8.5: Approve, reject, apply, or revert a learning candidate. Auto-apply candidates may apply without human approval when evidence thresholds and gates pass; manual apply still validates graph, pathfinder, and router gates first.",
        {
            "type": "object",
            "required": ["candidate_id"],
            "properties": {
                "candidate_id": {"type": "string"},
                "action": {"type": "string", "enum": ["approve", "reject", "apply", "revert"], "default": "apply"},
                "force": {"type": "boolean", "default": False},
            },
        },
        tool_learning_apply,
    ),
    "self_improve_run": (
        "V8.5: Run the evidence-backed self-improvement autopilot. Autopilot may mutate local repo files only through gated apply and rollback manifests.",
        {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["autopilot", "canary", "dry-run"], "default": "dry-run"},
                "scope": {"type": "string", "enum": ["all", "routing", "telemetry", "dashboard", "tests"], "default": "all"},
                "repo": {"type": "string"},
            },
        },
        tool_self_improve_run,
    ),
    "self_improve_runs": (
        "V8.5: List recent self-improvement autopilot runs and their gate/rollback status.",
        {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}}},
        tool_self_improve_runs,
    ),
    "self_improve_rollback": (
        "V8.5: Roll back a self-improvement run from its rollback manifest.",
        {"type": "object", "required": ["run_id"], "properties": {"run_id": {"type": "string"}}},
        tool_self_improve_rollback,
    ),
    "route_feedback": (
        "V8.5: Record accepted/corrected/failed route outcomes and create evidence-backed route-learning candidates when appropriate.",
        {
            "type": "object",
            "required": ["intent", "outcome"],
            "properties": {
                "intent": {"type": "string"},
                "outcome": {"type": "string", "enum": ["accepted", "corrected", "failed", "abandoned", "unknown"]},
                "skill": {"type": "string"},
                "corrected_skill": {"type": "string"},
                "selected_panel": {"type": "string"},
                "corrected_panel": {"type": "string"},
                "agent": {"type": "string"},
                "corrected_agent": {"type": "string"},
                "handoff_status": {"type": "string", "enum": ["", "complete", "partial", "truncated", "persisted_output", "empty"]},
                "failure_kind": {"type": "string"},
                "artifact_path": {"type": "string"},
                "tool_count": {"type": "integer"},
                "token_count": {"type": "integer"},
                "trace_id": {"type": "string"},
                "evidence_refs": {"type": "array", "items": {"type": "string"}},
                "reason": {"type": "string"},
            },
        },
        tool_route_feedback,
    ),
    "dispatch_advise": (
        "V8: Recommend dispatch (specialist agent) vs inline (main thread) for a user intent. Pass intent + estimated_files_to_read + is_interactive. Returns recommendation, suggested agent, and Task brief.",
        {
            "type": "object",
            "properties": {
                "intent": {"type": "string"},
                "estimated_files_to_read": {"type": "integer", "minimum": 1, "default": 10},
                "is_interactive": {"type": "boolean", "default": False},
            },
            "required": ["intent"],
        },
        tool_dispatch_advise,
    ),
    "wip_save_advise": (
        "V8: Recommend whether to wip-save the current worktree based on dirty count, threshold, cooldown, and in-progress state.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Worktree path (default: cwd)"},
            },
        },
        tool_wip_save_advise,
    ),
}


def handle(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ultraprompt-meta", "version": plugin_version()},
                "instructions": MCP_INSTRUCTIONS,
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        tools = [
            {"name": name, "description": description, "inputSchema": schema}
            for name, (description, schema, _h) in sorted(TOOLS.items())
        ]
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools}}
    if method == "tools/call":
        import time as _time
        params = request.get("params", {}) or {}
        name = params.get("name")
        args = params.get("arguments", {}) or {}
        if name not in TOOLS:
            return {"jsonrpc": "2.0", "id": request_id, "result": text_result({"error": f"unknown tool: {name}"}, is_error=True)}
        _start = _time.time()
        ok = True
        try:
            result = TOOLS[name][2](args)
        except Exception as exc:
            ok = False
            result = text_result({"error": f"{type(exc).__name__}: {exc}"}, is_error=True)
        # V8 telemetry: record mcp_tool_call event with outcome fields (fail-open)
        try:
            extra = _extract_outcome_fields(name, result) if ok else {}
            _ledger_write_call(name, args, int((_time.time() - _start) * 1000), ok, extra=extra)
        except Exception:
            pass
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def serve() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle(request)
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
        if response is not None:
            print(json.dumps(response, separators=(",", ":")), flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}), indent=2))
        return 0
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
