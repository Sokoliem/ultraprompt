#!/usr/bin/env python3
"""Audit Ultraprompt pathfinding and invocation telemetry.

This is intentionally different from catalog validation. Catalog validation proves
that skills, agents, panels, and graph metadata exist. This audit checks whether
the runtime is actually choosing those paths and whether telemetry can prove it.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PREFIXES = ("ultraprompt:", "ultra-prompt:")
RELEASE_CRITICAL_V8_2_SKILLS = ("goal", "frontend-visual-qa", "pathfinding-invocation-review")
RELEASE_CRITICAL_V8_3_SKILLS = RELEASE_CRITICAL_V8_2_SKILLS
RELEASE_CRITICAL_V8_4_SKILLS = RELEASE_CRITICAL_V8_3_SKILLS
PLUGIN_SKILL_RE = re.compile(r"(?:\$|/)ultra-?prompt:([a-z0-9][a-z0-9-]{0,63})", re.I)
MCP_TOOL_RE = re.compile(r"mcp__ultraprompt_meta__([a-zA-Z0-9_]+)")
MCP_DOTTED_TOOL_RE = re.compile(r"(?:mcp[.:_/ -]+)?ultraprompt[_-]meta[.:_/ -]+([a-zA-Z0-9_]+)", re.I)
HANDOFF_ARTIFACT_RE = re.compile(r"((?:~|/)[^\s\"'<>]*\.ultraprompt/agent-handoffs/[^\s\"'<>]+)")
TRUNCATION_PATTERNS = (
    ("persisted_output", re.compile(r"persisted-output|Output too large|Full output saved to", re.I)),
    ("truncated", re.compile(r"\[Truncated\. Full output:|returned only a partial|partial finding|partial report|reviewer truncated|auditor'?s response came back truncated|agent truncated", re.I)),
    ("empty", re.compile(r"Output empty", re.I)),
)
PROBLEM_HANDOFF_STATUSES = {"partial", "truncated", "persisted_output", "empty"}
HIGH_OUTPUT_AGENTS = {
    "reviewer",
    "feature-completeness-auditor",
    "repo-cartographer",
    "invocation-reliability-auditor",
    "design-critic",
    "gap-analysis-lead",
}


def repo_root() -> Path:
    try:
        import subprocess
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return Path(proc.stdout.strip()).resolve()
    except Exception:
        pass
    return ROOT.resolve()


def claude_project_slug(path: Path | None = None) -> str:
    root = str((path or repo_root()).resolve())
    return "-" + root.strip("/").replace("/", "-")


def scoped_claude_project(path: Path, scope: str) -> bool:
    if scope == "all":
        return True
    return claude_project_slug() in path.parts or claude_project_slug() in str(path)


def scoped_codex_session(path: Path, scope: str) -> bool:
    if scope == "all":
        return True
    root = repo_root()
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[:20]:
            try:
                event = json.loads(line)
            except Exception:
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            cwd = payload.get("cwd")
            if cwd and Path(str(cwd)).expanduser().resolve() == root:
                return True
    except Exception:
        return False
    return False


@lru_cache(maxsize=1)
def known_mcp_tool_names() -> set[str]:
    try:
        spec = importlib.util.spec_from_file_location("ultraprompt_meta_for_audit", ROOT / "mcp" / "ultraprompt_meta.py")
        if spec is None or spec.loader is None:
            return set()
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        tools = getattr(module, "TOOLS", {})
        return set(tools) if isinstance(tools, dict) else set()
    except Exception:
        return set()


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_ledger_module():
    spec = importlib.util.spec_from_file_location("ledger_v2", ROOT / "scripts" / "ledger-v2.py")
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_ref(value: object) -> tuple[str, bool, bool]:
    if not isinstance(value, str):
        return "?", False, False
    for prefix in PLUGIN_PREFIXES:
        if value.startswith(prefix):
            suffix = value.split(":", 1)[1]
            return f"ultraprompt:{suffix}", True, prefix == "ultra-prompt:"
    return value, False, False


def canonical_plugin_name(value: str) -> str:
    text = value.strip()
    for prefix in PLUGIN_PREFIXES:
        if text.startswith(prefix):
            return text.split(":", 1)[1]
    return text


def catalog_names() -> tuple[set[str], set[str]]:
    skill_index = load_json(ROOT / "dist" / "skill-index.json", {})
    skills = {
        str(skill.get("name"))
        for skill in skill_index.get("skills", [])
        if skill.get("name")
    }
    agents = {
        str(agent.get("name"))
        for agent in load_json(ROOT / "source" / "agent-specs.json", [])
        if agent.get("name")
    }
    return skills, agents


def read_runtime_events(days: int, scope: str = "all") -> list[dict[str, Any]]:
    ledger = load_ledger_module()
    if ledger is None:
        return []
    if scope == "current":
        return ledger.read_events(days=days, worktree=str(repo_root()))
    return ledger.read_events(days=days)


def read_project_dispatches(days: int, scope: str = "all") -> list[dict[str, Any]]:
    projects = Path.home() / ".claude" / "projects"
    if not projects.exists():
        return []
    cutoff = (datetime.now() - timedelta(days=days)).timestamp()
    dispatches: list[dict[str, Any]] = []
    for parent_jsonl in projects.rglob("*.jsonl"):
        if "subagents" in parent_jsonl.parts:
            continue
        if not scoped_claude_project(parent_jsonl, scope):
            continue
        try:
            for line in parent_jsonl.read_text(encoding="utf-8").splitlines():
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                ts_str = event.get("timestamp") or ""
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
                except Exception:
                    continue
                if ts < cutoff:
                    continue
                message = event.get("message") or {}
                content = message.get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_use" or block.get("name") not in {"Agent", "Task"}:
                        continue
                    tool_input = block.get("input") or {}
                    original = tool_input.get("subagent_type") or tool_input.get("agent") or "?"
                    agent, is_plugin, legacy = normalize_ref(original)
                    dispatches.append(
                        {
                            "ts": ts,
                            "agent": agent,
                            "original_agent": original,
                            "is_plugin_agent": is_plugin,
                            "legacy_prefix": legacy,
                            "tool": block.get("name"),
                            "description": (tool_input.get("description") or "")[:120],
                            "source": "claude_project_jsonl",
                        }
                    )
        except Exception:
            continue
    return dispatches


def event_text(event: dict[str, Any]) -> str:
    parts: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            for key in ("text", "content", "stdout", "stderr", "formatted_output", "message", "lastPrompt", "name"):
                if key in value:
                    visit(value.get(key))

    visit(event.get("message"))
    visit(event.get("payload"))
    visit(event.get("toolUseResult"))
    visit(event.get("attachment"))
    return "\n".join(parts)


def normalize_mcp_tool_name(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return ""
    text = value.strip()
    match = MCP_TOOL_RE.search(text)
    if match:
        return match.group(1)
    match = MCP_DOTTED_TOOL_RE.search(text)
    if match and match.group(1) in known_mcp_tool_names():
        return match.group(1)
    if text.startswith("ultraprompt_meta__"):
        candidate = text.split("__", 1)[1]
        return candidate if candidate in known_mcp_tool_names() else ""
    if text.startswith("ultraprompt_meta."):
        candidate = text.split(".", 1)[1]
        return candidate if candidate in known_mcp_tool_names() else ""
    return ""


def structured_mcp_tool_names(event: dict[str, Any]) -> set[str]:
    names: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, str):
            name = normalize_mcp_tool_name(value)
            if name:
                names.add(name)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)
            return
        if isinstance(value, dict):
            for key in ("name", "tool_name", "toolName", "recipient_name", "function", "server_tool"):
                raw = value.get(key)
                if isinstance(raw, dict):
                    visit(raw)
                else:
                    name = normalize_mcp_tool_name(raw)
                    if name:
                        names.add(name)
            function = value.get("function")
            if isinstance(function, dict):
                name = normalize_mcp_tool_name(function.get("name"))
                if name:
                    names.add(name)
            for key in ("message", "payload", "params", "arguments", "content", "tool_call", "function_call"):
                if key in value:
                    visit(value.get(key))

    visit(event)
    return names


def classify_handoff_status(text: str) -> tuple[str, str]:
    if not text.strip():
        return "complete", ""
    for status, pattern in TRUNCATION_PATTERNS:
        if pattern.search(text):
            return status, pattern.pattern
    return "complete", ""


def handoff_artifact_proof(text: str, artifact_path: object = None) -> dict[str, Any]:
    path_text = str(artifact_path or "").strip()
    if not path_text:
        match = HANDOFF_ARTIFACT_RE.search(text)
        if match:
            path_text = match.group(1).rstrip(".,);]")
    if not path_text:
        return {"artifact_path": "", "artifact_exists": False, "artifact_detected": False}
    path = Path(path_text).expanduser()
    return {
        "artifact_path": str(path),
        "artifact_exists": path.exists(),
        "artifact_detected": True,
    }


def read_claude_handoffs(days: int, scope: str = "all") -> list[dict[str, Any]]:
    projects = Path.home() / ".claude" / "projects"
    if not projects.exists():
        return []
    cutoff = (datetime.now() - timedelta(days=days)).timestamp()
    handoffs: list[dict[str, Any]] = []
    for parent_jsonl in projects.rglob("*.jsonl"):
        if not scoped_claude_project(parent_jsonl, scope):
            continue
        try:
            for line_no, line in enumerate(parent_jsonl.read_text(encoding="utf-8").splitlines(), 1):
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                ts_str = event.get("timestamp") or ""
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
                except Exception:
                    continue
                if ts < cutoff:
                    continue
                text = event_text(event)
                status, failure_kind = classify_handoff_status(text)
                tool_result = event.get("toolUseResult") if isinstance(event.get("toolUseResult"), dict) else {}
                agent = str(tool_result.get("agentType") or tool_result.get("agent") or "")
                is_agent_result = bool(tool_result.get("agentId") or agent)
                if is_agent_result and not text.strip():
                    status = "empty"
                    failure_kind = "empty_agent_handoff"
                if status in PROBLEM_HANDOFF_STATUSES or is_agent_result:
                    artifact = handoff_artifact_proof(text)
                    handoffs.append({
                        "ts": ts,
                        "source": "claude_project_jsonl",
                        "file": str(parent_jsonl),
                        "line": line_no,
                        "agent": agent,
                        "status": status,
                        "failure_kind": failure_kind,
                        **artifact,
                        "token_count": tool_result.get("totalTokens") or tool_result.get("total_tokens"),
                        "tool_count": tool_result.get("totalToolUseCount") or tool_result.get("tool_uses"),
                    })
        except Exception:
            continue
    return handoffs


def read_codex_activity(days: int, scope: str = "all") -> dict[str, Any]:
    sessions = Path(os.environ.get("ULTRAPROMPT_CODEX_SESSIONS_DIR", "")).expanduser() if os.environ.get("ULTRAPROMPT_CODEX_SESSIONS_DIR") else Path.home() / ".codex" / "sessions"
    cutoff = (datetime.now() - timedelta(days=days)).timestamp()
    activity = {
        "files": 0,
        "skill_mentions": Counter(),
        "mcp_tool_calls": Counter(),
        "agent_dispatches": [],
        "handoffs": [],
    }
    if not sessions.exists():
        return activity
    for path in sessions.rglob("*.jsonl"):
        try:
            if path.stat().st_mtime < cutoff:
                continue
        except OSError:
            continue
        if not scoped_codex_session(path, scope):
            continue
        activity["files"] += 1
        try:
            for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                ts_str = event.get("timestamp") or ""
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
                except Exception:
                    ts = path.stat().st_mtime
                if ts < cutoff:
                    continue
                text = event_text(event)
                for match in PLUGIN_SKILL_RE.finditer(text):
                    activity["skill_mentions"][f"ultraprompt:{match.group(1).lower()}"] += 1
                mcp_names = {match.group(1) for match in MCP_TOOL_RE.finditer(text)}
                mcp_names.update(structured_mcp_tool_names(event))
                for name in mcp_names:
                    activity["mcp_tool_calls"][name] += 1
                payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
                name = payload.get("name") or payload.get("tool_name")
                if name in {"spawn_agent", "wait_agent"}:
                    activity["agent_dispatches"].append({
                        "ts": ts,
                        "agent": str(((payload.get("arguments") or {}).get("agent_type") if isinstance(payload.get("arguments"), dict) else "") or name),
                        "original_agent": name,
                        "is_plugin_agent": "ultraprompt" in text.lower(),
                        "legacy_prefix": "ultra-prompt:" in text,
                        "tool": name,
                        "source": "codex_session_jsonl",
                    })
                status, failure_kind = classify_handoff_status(text)
                if status in PROBLEM_HANDOFF_STATUSES:
                    artifact = handoff_artifact_proof(text)
                    activity["handoffs"].append({
                        "ts": ts,
                        "source": "codex_session_jsonl",
                        "file": str(path),
                        "line": line_no,
                        "agent": "",
                        "status": status,
                        "failure_kind": failure_kind,
                        **artifact,
                    })
        except Exception:
            continue
    return activity


def read_pathfinder_events(days: int) -> list[dict[str, Any]]:
    path = Path.home() / ".ultraprompt" / "events" / "events.jsonl"
    if not path.exists():
        return []
    cutoff = datetime.now() - timedelta(days=days)
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue
        if event.get("type") != "pathfinder_decision":
            continue
        try:
            ts = datetime.fromisoformat(str(event.get("ts", "")).replace("Z", "+00:00"))
        except Exception:
            ts = datetime.fromtimestamp(0)
        if ts.replace(tzinfo=None) < cutoff.replace(tzinfo=None):
            continue
        events.append(event)
    return events


def read_cognitive_events(days: int, types: set[str]) -> list[dict[str, Any]]:
    path = Path.home() / ".ultraprompt" / "events" / "events.jsonl"
    if not path.exists():
        return []
    cutoff = datetime.now() - timedelta(days=days)
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue
        if event.get("type") not in types:
            continue
        try:
            ts = datetime.fromisoformat(str(event.get("ts", "")).replace("Z", "+00:00"))
        except Exception:
            ts = datetime.fromtimestamp(0)
        if ts.replace(tzinfo=None) < cutoff.replace(tzinfo=None):
            continue
        events.append(event)
    return events


def improvement_candidates(report: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    codex = report.get("codex_activity") or {}
    if codex.get("files", 0) and not (report.get("runtime_events") or {}).get("by_runtime", {}).get("codex"):
        candidates.append({
            "kind": "telemetry_ingestion",
            "priority": "high",
            "evidence_count": codex.get("files", 0),
            "recommendation": "record Codex MCP/session activity into the V8 ledger so route gates see both runtimes",
        })
    dispatch = report.get("agent_dispatches") or {}
    if dispatch.get("explore_share_pct", 0) > 35:
        candidates.append({
            "kind": "explore_fallback",
            "priority": "high",
            "evidence_count": dispatch.get("explore_total", 0),
            "recommendation": "tighten dispatch_advise/pathfinder prompts toward plugin specialists when confidence is above threshold",
        })
    handoffs = report.get("agent_handoffs") or {}
    problem_count = sum(handoffs.get("by_status", {}).get(status, 0) for status in PROBLEM_HANDOFF_STATUSES)
    if problem_count:
        candidates.append({
            "kind": "agent_handoff",
            "priority": "high",
            "evidence_count": problem_count,
            "recommendation": "use artifact-first handoff for high-output plugin agents and record compact envelope status",
        })
    pathfinder = report.get("pathfinder") or {}
    if pathfinder.get("decisions", 0) and pathfinder.get("bench_pathfinder_ratio_pct", 0) > 75:
        candidates.append({
            "kind": "pathfinder_live_signal",
            "priority": "medium",
            "evidence_count": pathfinder.get("bench_decisions", 0),
            "recommendation": "separate bench/golden events from live routing evidence and require live intent diversity for release gates",
        })
    if dispatch.get("legacy_prefix_total", 0) or (report.get("runtime_events") or {}).get("legacy_skill_invocations", 0):
        candidates.append({
            "kind": "legacy_prefix",
            "priority": "medium",
            "evidence_count": dispatch.get("legacy_prefix_total", 0) + (report.get("runtime_events") or {}).get("legacy_skill_invocations", 0),
            "recommendation": "normalize ultra-prompt prefixes while preserving original_prefix telemetry for drift diagnosis",
        })
    route_outcomes = report.get("route_outcomes") or {}
    corrected = route_outcomes.get("by_outcome", {}).get("corrected", 0) + route_outcomes.get("by_outcome", {}).get("failed", 0)
    if corrected:
        candidates.append({
            "kind": "route_update",
            "priority": "medium",
            "evidence_count": corrected,
            "recommendation": "review generated route_update learning candidates before applying route-policy overlays",
        })
    priority_order = {"high": 0, "medium": 1, "low": 2}
    candidates.sort(key=lambda item: (priority_order.get(item["priority"], 9), -int(item.get("evidence_count", 0))))
    return candidates


def agent_short_name(agent: Any) -> str:
    return str(agent or "").split(":", 1)[-1]


def handoff_contract_summary(handoff_rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_artifact = []
    missing_artifact_file = []
    artifact_present = 0
    required_total = 0
    failure_kinds = Counter()
    truncation_agents = Counter()
    for row in handoff_rows:
        agent = agent_short_name(row.get("agent"))
        status = str(row.get("status") or row.get("handoff_status") or "")
        failure_kind = str(row.get("failure_kind") or "")
        if failure_kind:
            failure_kinds[failure_kind] += 1
        if status in {"truncated", "persisted_output"}:
            truncation_agents[agent or "?"] += 1
        if agent in HIGH_OUTPUT_AGENTS:
            required_total += 1
            if not row.get("artifact_path"):
                missing_artifact.append(row)
            elif not row.get("artifact_exists"):
                missing_artifact_file.append(row)
            else:
                artifact_present += 1
    return {
        "schema": "handoff_contract.v2",
        "artifact_first_agents": sorted(HIGH_OUTPUT_AGENTS),
        "required_total": required_total,
        "artifact_present": artifact_present,
        "missing_artifact_path": len(missing_artifact),
        "missing_artifact_file": len(missing_artifact_file),
        "missing_artifact_examples": missing_artifact[:10],
        "missing_artifact_file_examples": missing_artifact_file[:10],
        "problem_handoffs": sum(1 for row in handoff_rows if str(row.get("status") or "") in PROBLEM_HANDOFF_STATUSES),
        "by_failure_kind": dict(failure_kinds.most_common(20)),
        "truncation_prone_agents": dict(truncation_agents.most_common(20)),
        "ok": not missing_artifact and not missing_artifact_file,
    }


def candidate_groups(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        kind = str(candidate.get("kind") or "unknown")
        bucket = groups.setdefault(kind, {
            "kind": kind,
            "count": 0,
            "evidence_count": 0,
            "priorities": Counter(),
            "recommendations": [],
        })
        bucket["count"] += 1
        bucket["evidence_count"] += int(candidate.get("evidence_count") or 0)
        bucket["priorities"][str(candidate.get("priority") or "unknown")] += 1
        recommendation = candidate.get("recommendation")
        if recommendation and recommendation not in bucket["recommendations"] and len(bucket["recommendations"]) < 3:
            bucket["recommendations"].append(recommendation)
    rendered = []
    for bucket in groups.values():
        rendered.append({
            **bucket,
            "priorities": dict(bucket["priorities"].most_common()),
        })
    rendered.sort(key=lambda item: (-int(item["evidence_count"]), item["kind"]))
    return {"total": len(candidates), "groups": rendered}


def panel_smoke_status(panel: str = "experience-quality-panel") -> dict[str, Any]:
    import subprocess
    import sys

    proof_proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "panel-runs.py"), "proof", "--panel", panel],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    live_error: dict[str, Any] | None = None
    try:
        proof = json.loads(proof_proc.stdout)
    except Exception:
        proof = {"ok": False, "stdout": proof_proc.stdout, "stderr": proof_proc.stderr}
    proof["exit"] = proof_proc.returncode
    if proof.get("ok") and proof.get("live_adoption"):
        return proof
    live_error = proof

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "panel-runs.py"), "smoke", "--panel", panel],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        data = json.loads(proc.stdout)
    except Exception:
        data = {"ok": False, "stdout": proc.stdout, "stderr": proc.stderr}
    data["exit"] = proc.returncode
    data.setdefault("proof_kind", "fixture")
    data.setdefault("live_adoption", False)
    data["live_proof"] = live_error
    return data


def golden_intents() -> set[str]:
    cases = load_json(ROOT / "tests" / "pathfinder" / "golden-cases.json", [])
    return {str(case.get("intent", "")) for case in cases if case.get("intent")}


def summarize(days: int, scope: str = "current") -> dict[str, Any]:
    skill_names, agent_names = catalog_names()
    runtime_events = read_runtime_events(days, scope)
    project_dispatches = read_project_dispatches(days, scope)
    codex_activity = read_codex_activity(days, scope)
    pathfinder_events = read_pathfinder_events(days)
    cognitive_events = read_cognitive_events(days, {"route_outcome", "agent_handoff"})
    bench_intents = golden_intents()

    skill_invocations: Counter[str] = Counter()
    legacy_skill_invocations: Counter[str] = Counter()
    mcp_calls: Counter[str] = Counter()
    by_runtime: Counter[str] = Counter()
    ledger_agent_dispatches: list[dict[str, Any]] = []

    for event in runtime_events:
        event_type = event.get("type")
        by_runtime[str(event.get("runtime") or "unknown")] += 1
        if event_type == "skill_invocation":
            skill, is_plugin, legacy = normalize_ref(event.get("skill"))
            if is_plugin or event.get("is_plugin_skill"):
                skill_invocations[skill] += 1
                if legacy or event.get("legacy_prefix"):
                    legacy_skill_invocations[skill] += 1
        elif event_type == "agent_dispatch":
            agent, is_plugin, legacy = normalize_ref(event.get("agent"))
            ledger_agent_dispatches.append({**event, "agent": agent, "is_plugin_agent": is_plugin or event.get("is_plugin_agent"), "legacy_prefix": legacy or event.get("legacy_prefix")})
        elif event_type == "mcp_tool_call":
            mcp_calls[str(event.get("tool", "?"))] += 1

    mcp_calls.update(codex_activity["mcp_tool_calls"])
    combined_dispatches = ledger_agent_dispatches + project_dispatches + codex_activity["agent_dispatches"]
    dispatch_counts = Counter(str(item.get("agent", "?")) for item in combined_dispatches)
    total_dispatches = len(combined_dispatches)
    plugin_dispatches = [item for item in combined_dispatches if item.get("is_plugin_agent")]
    explore_dispatches = [item for item in combined_dispatches if item.get("agent") == "Explore"]
    legacy_agent_dispatches = [item for item in combined_dispatches if item.get("legacy_prefix")]
    handoff_rows = read_claude_handoffs(days, scope) + codex_activity["handoffs"]
    for event in cognitive_events:
        if event.get("type") != "agent_handoff":
            continue
        data = event.get("data") or {}
        handoff_rows.append({
            "source": "cognitive_event_log",
            "agent": data.get("agent"),
            "status": data.get("handoff_status") or "unknown",
            "failure_kind": data.get("failure_kind") or "",
            **handoff_artifact_proof("", data.get("artifact_path")),
            "token_count": data.get("token_count"),
            "tool_count": data.get("tool_count"),
        })
    handoff_statuses = Counter(str(item.get("status") or "unknown") for item in handoff_rows)
    handoff_agents = Counter(str(item.get("agent") or "?") for item in handoff_rows)
    route_outcomes = Counter()
    for event in cognitive_events:
        if event.get("type") == "route_outcome":
            data = event.get("data") or {}
            route_outcomes[str(data.get("outcome") or "unknown")] += 1

    pathfinder_by_skill = Counter()
    pathfinder_by_source = Counter()
    distinct_real_intents: set[str] = set()
    panel_recommendations = 0
    bench = 0
    synthetic = 0
    real = 0
    for event in pathfinder_events:
        data = event.get("data") or {}
        intent = str(data.get("intent", ""))
        event_source = str(data.get("telemetry_source") or data.get("event_source") or data.get("source") or "").strip().lower()
        if event_source in {"bench", "golden", "test"} or intent in bench_intents:
            bench += 1
            source = "bench"
        elif event_source == "synthetic":
            synthetic += 1
            source = "synthetic"
        else:
            real += 1
            if intent:
                distinct_real_intents.add(intent)
            source = event_source or "runtime"
        pathfinder_by_source[source] += 1
        pathfinder_by_skill[str(data.get("skill", "?"))] += 1
        if data.get("panel") or data.get("panel_candidates"):
            panel_recommendations += 1

    plugin_share = (100.0 * len(plugin_dispatches) / total_dispatches) if total_dispatches else 0.0
    explore_share = (100.0 * len(explore_dispatches) / total_dispatches) if total_dispatches else 0.0
    pathfinder_total = len(pathfinder_events)
    real_ratio = (100.0 * real / pathfinder_total) if pathfinder_total else 0.0
    bench_ratio = (100.0 * bench / pathfinder_total) if pathfinder_total else 0.0
    fired_skills = {name.split(":", 1)[1] for name in skill_invocations if name.startswith("ultraprompt:")}
    fired_agents = {str(item.get("agent", "")).split(":", 1)[1] for item in plugin_dispatches if str(item.get("agent", "")).startswith("ultraprompt:")}
    release_critical_skills = {
        name: skill_invocations.get(f"ultraprompt:{name}", 0)
        for name in RELEASE_CRITICAL_V8_2_SKILLS
    }

    handoff_contract = handoff_contract_summary(handoff_rows)

    report = {
        "schema": "invocation_telemetry_audit.v3",
        "generated_at": int(time.time()),
        "window_days": days,
        "scope": scope,
        "repo_root": str(repo_root()),
        "runtime_events": {
            "total": len(runtime_events),
            "skill_invocations": sum(skill_invocations.values()),
            "live_skill_invocations_total": sum(skill_invocations.values()),
            "legacy_skill_invocations": sum(legacy_skill_invocations.values()),
            "mcp_tool_calls": sum(mcp_calls.values()),
            "by_runtime": dict(by_runtime.most_common()),
            "top_skills": dict(skill_invocations.most_common(20)),
            "top_mcp_tools": dict(mcp_calls.most_common(20)),
            "new_release_skill_invocations": release_critical_skills,
        },
        "codex_activity": {
            "files": codex_activity["files"],
            "skill_mentions": sum(codex_activity["skill_mentions"].values()),
            "top_skill_mentions": dict(codex_activity["skill_mentions"].most_common(20)),
            "mcp_tool_calls": sum(codex_activity["mcp_tool_calls"].values()),
            "top_mcp_tool_calls": dict(codex_activity["mcp_tool_calls"].most_common(20)),
            "agent_dispatches": len(codex_activity["agent_dispatches"]),
            "handoffs": len(codex_activity["handoffs"]),
        },
        "codex_mcp_tool_calls": {
            "total": sum(codex_activity["mcp_tool_calls"].values()),
            "by_tool": dict(codex_activity["mcp_tool_calls"].most_common(30)),
            "session_files": codex_activity["files"],
        },
        "agent_dispatches": {
            "total": total_dispatches,
            "plugin_total": len(plugin_dispatches),
            "plugin_share_pct": round(plugin_share, 1),
            "explore_total": len(explore_dispatches),
            "explore_share_pct": round(explore_share, 1),
            "legacy_prefix_total": len(legacy_agent_dispatches),
            "by_agent": dict(dispatch_counts.most_common(30)),
        },
        "agent_handoffs": {
            "total": len(handoff_rows),
            "problem_total": sum(handoff_statuses.get(status, 0) for status in PROBLEM_HANDOFF_STATUSES),
            "by_status": dict(handoff_statuses.most_common()),
            "by_agent": dict(handoff_agents.most_common(20)),
            "examples": handoff_rows[:10],
        },
        "handoff_contract": handoff_contract,
        "route_outcomes": {
            "total": sum(route_outcomes.values()),
            "by_outcome": dict(route_outcomes.most_common()),
        },
        "pathfinder": {
            "decisions": len(pathfinder_events),
            "real_decisions": real,
            "bench_decisions": bench,
            "synthetic_decisions": synthetic,
            "synthetic_or_bench_decisions": synthetic + bench,
            "real_pathfinder_ratio_pct": round(real_ratio, 1),
            "bench_pathfinder_ratio_pct": round(bench_ratio, 1),
            "distinct_real_intents": len(distinct_real_intents),
            "panel_recommendations": panel_recommendations,
            "by_source": dict(pathfinder_by_source.most_common()),
            "by_skill": dict(pathfinder_by_skill.most_common(30)),
        },
        "activation_gaps": {
            "skills_never_invoked": sorted(skill_names - fired_skills),
            "agents_never_dispatched": sorted(agent_names - fired_agents),
        },
    }
    report["routing_improvement_candidates"] = improvement_candidates(report)
    report["candidate_groups"] = candidate_groups(report["routing_improvement_candidates"])
    return report


def evaluate(report: dict[str, Any], args: argparse.Namespace) -> list[str]:
    failures: list[str] = []
    dispatch = report["agent_dispatches"]
    runtime = report["runtime_events"]
    pathfinder = report["pathfinder"]
    if dispatch["total"] >= args.min_dispatches:
        if dispatch["plugin_share_pct"] < args.min_plugin_agent_share:
            failures.append(
                f"plugin agent dispatch share {dispatch['plugin_share_pct']}% < {args.min_plugin_agent_share}%"
            )
        if dispatch["explore_share_pct"] > args.max_explore_share:
            failures.append(
                f"Explore dispatch share {dispatch['explore_share_pct']}% > {args.max_explore_share}%"
            )
    if runtime["skill_invocations"] < args.min_skill_invocations:
        failures.append(
            f"current plugin skill invocations {runtime['skill_invocations']} < {args.min_skill_invocations}"
        )
    if pathfinder["real_decisions"] < args.min_real_pathfinder_decisions:
        failures.append(
            f"real pathfinder decisions {pathfinder['real_decisions']} < {args.min_real_pathfinder_decisions}"
        )
    if pathfinder["real_pathfinder_ratio_pct"] < args.min_real_pathfinder_ratio:
        failures.append(
            f"real pathfinder ratio {pathfinder['real_pathfinder_ratio_pct']}% < {args.min_real_pathfinder_ratio}%"
        )
    if pathfinder.get("distinct_real_intents", 0) < args.min_distinct_release_intents:
        failures.append(
            f"distinct real pathfinder intents {pathfinder.get('distinct_real_intents', 0)} < {args.min_distinct_release_intents}"
        )
    if pathfinder["bench_pathfinder_ratio_pct"] > args.max_bench_pathfinder_ratio:
        failures.append(
            f"bench pathfinder ratio {pathfinder['bench_pathfinder_ratio_pct']}% > {args.max_bench_pathfinder_ratio}%"
        )
    handoffs = report.get("agent_handoffs") or {}
    if handoffs.get("problem_total", 0) > args.max_problem_handoffs:
        failures.append(
            f"problem agent handoffs {handoffs.get('problem_total', 0)} > {args.max_problem_handoffs}"
        )
    required_skills = list(args.required_live_skill or [])
    if args.release_critical_v8_2:
        required_skills.extend(RELEASE_CRITICAL_V8_2_SKILLS)
    if args.release_critical_v8_3:
        required_skills.extend(RELEASE_CRITICAL_V8_3_SKILLS)
    if getattr(args, "release_critical_v8_4", False):
        required_skills.extend(RELEASE_CRITICAL_V8_4_SKILLS)
    top_skills = runtime.get("top_skills", {})
    for skill in sorted(set(required_skills), key=canonical_plugin_name):
        name = canonical_plugin_name(skill)
        count = top_skills.get(f"ultraprompt:{name}", 0)
        if count < 1:
            failures.append(f"required live skill {name} has no current invocation")
    by_agent = dispatch.get("by_agent", {})
    for agent in sorted(set(args.required_live_agent or []), key=canonical_plugin_name):
        name = canonical_plugin_name(agent)
        count = by_agent.get(f"ultraprompt:{name}", 0)
        if count < 1:
            failures.append(f"required live agent {name} has no current dispatch")
    if args.require_panel_proof:
        panel_proof = report.get("panel_proof") or {}
        if not panel_proof.get("ok"):
            failures.append(f"panel proof for {args.require_panel_proof} missing or invalid")
        elif not args.allow_fixture_panel_proof and not panel_proof.get("live_adoption"):
            failures.append(
                f"live panel proof for {args.require_panel_proof} missing; fixture-only proof does not satisfy release gate"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--scope", choices=["current", "all"], default="current",
                        help="Telemetry scope. current filters local Claude/Codex/ledger evidence to this repo; all preserves broad installed-plugin health.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--enforce", action="store_true")
    parser.add_argument("--min-dispatches", type=int, default=20)
    parser.add_argument("--min-plugin-agent-share", type=float, default=25.0)
    parser.add_argument("--max-explore-share", type=float, default=50.0)
    parser.add_argument("--min-skill-invocations", type=int, default=1)
    parser.add_argument("--min-real-pathfinder-decisions", type=int, default=1)
    parser.add_argument("--min-real-pathfinder-ratio", type=float, default=0.0)
    parser.add_argument("--min-distinct-release-intents", type=int, default=0)
    parser.add_argument("--max-bench-pathfinder-ratio", type=float, default=100.0)
    parser.add_argument("--max-problem-handoffs", type=int, default=999999)
    parser.add_argument("--required-live-skill", action="append", default=[])
    parser.add_argument("--required-live-agent", action="append", default=[])
    parser.add_argument("--release-critical-v8-2", action="store_true",
                        help="Require live invocation for V8.2 release-critical skills")
    parser.add_argument("--release-critical-v8-3", action="store_true",
                        help="Require live invocation for V8.3 release-critical skills")
    parser.add_argument("--release-critical-v8-4", action="store_true",
                        help="Require live invocation for V8.4 release-critical skills")
    parser.add_argument("--require-panel-proof", default="",
                        help="Require schema-valid panel smoke proof for the named panel")
    parser.add_argument("--allow-fixture-panel-proof", action="store_true",
                        help="Allow fixture-only panel proof. Strict release gates leave this disabled.")
    args = parser.parse_args()

    report = summarize(args.days, args.scope)
    if args.require_panel_proof:
        report["panel_proof"] = panel_smoke_status(args.require_panel_proof)
    failures = evaluate(report, args)
    report["ok"] = not failures
    report["failures"] = failures
    report["thresholds"] = {
        "min_dispatches": args.min_dispatches,
        "min_plugin_agent_share": args.min_plugin_agent_share,
        "max_explore_share": args.max_explore_share,
        "min_skill_invocations": args.min_skill_invocations,
        "min_real_pathfinder_decisions": args.min_real_pathfinder_decisions,
        "min_real_pathfinder_ratio": args.min_real_pathfinder_ratio,
        "min_distinct_release_intents": args.min_distinct_release_intents,
        "max_bench_pathfinder_ratio": args.max_bench_pathfinder_ratio,
        "max_problem_handoffs": args.max_problem_handoffs,
        "required_live_skills": sorted(set(
            (args.required_live_skill or [])
            + (list(RELEASE_CRITICAL_V8_2_SKILLS) if args.release_critical_v8_2 else [])
            + (list(RELEASE_CRITICAL_V8_3_SKILLS) if args.release_critical_v8_3 else [])
            + (list(RELEASE_CRITICAL_V8_4_SKILLS) if args.release_critical_v8_4 else [])
        ), key=canonical_plugin_name),
        "required_live_agents": sorted(set(args.required_live_agent or []), key=canonical_plugin_name),
        "required_panel_proof": args.require_panel_proof,
        "allow_fixture_panel_proof": args.allow_fixture_panel_proof,
    }

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        dispatch = report["agent_dispatches"]
        runtime = report["runtime_events"]
        pathfinder = report["pathfinder"]
        print(f"Invocation telemetry audit (last {args.days} days)")
        print(f"- agent dispatches: {dispatch['total']} total, {dispatch['plugin_total']} plugin ({dispatch['plugin_share_pct']}%), {dispatch['explore_total']} Explore ({dispatch['explore_share_pct']}%)")
        print(f"- skill invocations: {runtime['skill_invocations']} current plugin, {runtime['legacy_skill_invocations']} legacy-prefix")
        print(f"- pathfinder: {pathfinder['decisions']} decisions, {pathfinder['real_decisions']} real ({pathfinder['real_pathfinder_ratio_pct']}%), {pathfinder['bench_decisions']} bench, {pathfinder['synthetic_decisions']} synthetic, {pathfinder.get('distinct_real_intents', 0)} distinct real intents")
        print(f"- handoffs: {report.get('agent_handoffs', {}).get('total', 0)} total, {report.get('agent_handoffs', {}).get('problem_total', 0)} problematic")
        if report.get("panel_proof"):
            proof = report["panel_proof"]
            print(f"- panel proof: {proof.get('panel')} {proof.get('status', 'unknown')}")
        if failures:
            print("Failures:")
            for failure in failures:
                print(f"- {failure}")
    return 1 if args.enforce and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
