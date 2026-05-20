#!/usr/bin/env python3
"""Generated routing policy and routing-decision helpers.

This module is dependency-free and intentionally sits under scripts/ so the MCP
server, CLI tools, release scorecard, and dashboard can all share the same
source-derived routing contract.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cognitive_common import ROOT, command_result, plugin_version, read_json, stable_hash

SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from ultraprompt_index import load_index, tokenize  # noqa: E402

OUT = ROOT / "dist" / "routing-policy.json"

RELEASE_CRITICAL_SKILLS = ("goal", "frontend-visual-qa", "pathfinding-invocation-review")
HIGH_OUTPUT_AGENTS = {
    "reviewer",
    "feature-completeness-auditor",
    "repo-cartographer",
    "invocation-reliability-auditor",
    "design-critic",
    "gap-analysis-lead",
}
PANEL_LANGUAGE = re.compile(r"\b(panel|multi[- ]perspective|fanout|cross[- ]functional|parallel specialists?)\b", re.I)
HIGH_STAKES_LANGUAGE = re.compile(
    r"\b(high[- ]stakes|release|ship|go/no-go|comprehensive|end[- ]to[- ]end|whole[- ]repo|security|privacy|incident|migration)\b",
    re.I,
)


def load_json(rel: str, default: Any) -> Any:
    return read_json(ROOT / rel, default)


def source_value(spec: dict[str, Any], key: str, default: Any = None) -> Any:
    if key in spec:
        return spec.get(key)
    cognitive = spec.get("cognitive") or {}
    if isinstance(cognitive, dict) and key in cognitive:
        return cognitive.get(key)
    return default


def source_skill_map() -> dict[str, dict[str, Any]]:
    return {str(spec.get("name")): spec for spec in load_json("source/skill-specs.json", []) if spec.get("name")}


def panel_map() -> dict[str, dict[str, Any]]:
    return {str(spec.get("name")): spec for spec in load_json("source/panel-specs.json", []) if spec.get("name")}


def agent_names() -> set[str]:
    return {str(spec.get("name")) for spec in load_json("source/agent-specs.json", []) if spec.get("name")}


def normalize_dispatch(dispatch: Any) -> dict[str, Any]:
    if not isinstance(dispatch, dict):
        return {}
    out = {k: v for k, v in dispatch.items() if v not in (None, "", [])}
    agent = out.get("agent")
    if agent and not str(agent).startswith("ultraprompt:"):
        out["agent_ref"] = f"ultraprompt:{agent}"
    return out


def safe_ref(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-") or "unknown"


def agent_handoff_policy(agent: str, trace_id: str | None = None) -> dict[str, Any]:
    agent_name = agent.split(":", 1)[-1]
    artifact_kind = "required" if agent_name in HIGH_OUTPUT_AGENTS else "optional"
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    artifact_trace = safe_ref(trace_id or "trace")
    artifact_path = str(Path.home() / ".ultraprompt" / "agent-handoffs" / month / f"{artifact_trace}-{safe_ref(agent_name)}.md")
    return {
        "mode": "artifact_first" if artifact_kind == "required" else "compact_chat",
        "artifact": artifact_kind,
        "artifact_path": artifact_path,
        "final_response_contract": "compact_envelope",
        "chat_handoff_budget": "summary_only_no_depth_cap",
        "required_fields": [
            "status",
            "artifact_path",
            "top_findings",
            "validation",
            "remaining_risk",
            "truncation_flag",
        ],
        "depth_cap": None,
    }


def dispatch_prompt(agent: str, *, focus: Any = None, phase: Any = None, artifact_path: str = "") -> str:
    focus_line = str(focus or "<from intent>")
    phase_line = f" phase={phase};" if phase else ""
    artifact_line = (
        f" Persist the full structured report to {artifact_path}. "
        "Return only a compact envelope with status, artifact_path, top_findings, validation, "
        "remaining_risk, and truncation_flag. Do not cap investigation depth."
        if artifact_path else ""
    )
    return (
        f"Dispatch ultraprompt:{agent} with focus={focus_line};{phase_line} "
        "apply ${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md."
        f"{artifact_line}"
    )


def handoff_contract_status(agent: str, handoff: dict[str, Any], prompt: str = "") -> dict[str, Any]:
    """Validate the artifact-first handoff contract for high-output agents."""
    agent_name = agent.split(":", 1)[-1]
    required = agent_name in HIGH_OUTPUT_AGENTS or handoff.get("artifact") == "required"
    missing: list[str] = []
    artifact_path = str(handoff.get("artifact_path") or "")
    if required:
        if handoff.get("mode") != "artifact_first":
            missing.append("mode=artifact_first")
        if handoff.get("artifact") != "required":
            missing.append("artifact=required")
        if not artifact_path:
            missing.append("artifact_path")
        elif prompt and artifact_path not in prompt:
            missing.append("artifact_path_in_prompt")
        required_fields = set(handoff.get("required_fields") or [])
        prompt_lower = prompt.lower()
        for field in sorted(required_fields):
            if prompt and str(field).lower() not in prompt_lower:
                missing.append(f"final_field:{field}")
    return {
        "schema": "handoff_contract_status.v1",
        "agent": agent_name,
        "required": required,
        "ok": not missing,
        "status": "satisfied" if not missing else "missing_contract",
        "missing": missing,
        "artifact_path": artifact_path or None,
    }


def normalize_confirmation(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = str(value or "")
    return {
        "required": text == "required_for_repo_mutation",
        "policy": text or "not_specified",
    }


def default_execution(index_skill: dict[str, Any], spec: dict[str, Any]) -> str:
    triggering = source_value(spec, "triggering", {}) or {}
    if triggering.get("default_execution"):
        return str(triggering["default_execution"])
    if source_value(spec, "inline_only_reason") or index_skill.get("inline_only_reason"):
        return "inline"
    if normalize_dispatch(source_value(spec, "dispatch_to") or index_skill.get("dispatch_to")).get("agent"):
        return "agent"
    return "inline"


def build_skill_policy(index_skill: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    triggering = source_value(spec, "triggering", {}) or {}
    name = str(index_skill.get("name") or spec.get("name"))
    dispatch = normalize_dispatch(source_value(spec, "dispatch_to") or index_skill.get("dispatch_to"))
    paired_panels = source_value(spec, "paired_panels") or index_skill.get("paired_panels") or []
    preferred_panel = source_value(spec, "preferred_panel") or index_skill.get("preferred_panel") or ""
    inline_reason = source_value(spec, "inline_only_reason") or index_skill.get("inline_only_reason") or ""
    mode = source_value(spec, "mode") or index_skill.get("mode") or "read_only"
    risk = source_value(spec, "risk") or index_skill.get("risk") or ("medium" if mode == "write_capable" else "low")
    execution = default_execution(index_skill, spec)
    release_critical = bool(triggering.get("release_critical", name in RELEASE_CRITICAL_SKILLS))
    auto_trigger = bool(triggering.get("auto_trigger", not index_skill.get("manual_only", False)))
    min_confidence = float(triggering.get("min_confidence", 0.78 if release_critical else (0.72 if mode == "write_capable" else 0.62)))
    dispatch_agent = str(dispatch.get("agent") or "")
    handoff = agent_handoff_policy(dispatch_agent) if dispatch_agent else {"mode": "inline", "artifact": "none"}
    return {
        "skill": name,
        "family": source_value(spec, "family") or index_skill.get("family"),
        "tier": index_skill.get("tier") or source_value(spec, "tier"),
        "auto_trigger": auto_trigger,
        "min_confidence": min_confidence,
        "default_execution": execution,
        "dispatch_to": dispatch,
        "handoff_policy": handoff,
        "panel_escalation": {
            "preferred_panel": preferred_panel or None,
            "paired_panels": paired_panels,
            "standard_budget_allowed": bool(triggering.get("panel_escalation", {}).get("standard_budget_allowed", False))
            if isinstance(triggering.get("panel_escalation"), dict)
            else False,
            "signals": ["explicit_panel_language", "high_stakes_scope", "low_confidence_gap"],
        },
        "inline_override": {
            "enabled": bool(inline_reason),
            "reason": inline_reason or None,
        },
        "release_critical": release_critical,
        "telemetry_required": bool(triggering.get("telemetry_required", release_critical or execution != "inline")),
        "mode": mode,
        "risk": risk,
        "confirmation": normalize_confirmation(source_value(spec, "confirmation") or index_skill.get("confirmation")),
        "expected_artifacts": sorted(set(source_value(spec, "outputs") or index_skill.get("outputs") or [])),
        "artifact_type": source_value(spec, "artifact_type") or index_skill.get("artifact_type"),
        "runtime_support": {
            "claude_command": f"/ultraprompt:{name}",
            "codex_command": f"$ultraprompt:{name}",
            "mcp_tools": ["route_intent", "pathfind_workflow", "dispatch_advise", "route_trigger_plan"],
        },
    }


def build_routing_policy(root: Path | None = None) -> dict[str, Any]:
    root = root or ROOT
    index = load_index(root)
    specs = source_skill_map()
    policies = [
        build_skill_policy(index_skill, specs.get(str(index_skill.get("name")), {}))
        for index_skill in index.get("skills", [])
        if index_skill.get("name")
    ]
    policies.sort(key=lambda item: item["skill"])
    dispatch_coverage = {
        "skills_with_dispatch": sorted(p["skill"] for p in policies if p.get("dispatch_to", {}).get("agent")),
        "inline_only_skills": sorted(p["skill"] for p in policies if p.get("inline_override", {}).get("enabled")),
        "release_critical_skills": sorted(p["skill"] for p in policies if p.get("release_critical")),
    }
    policy = {
        "schema": "routing_policy.v1",
        "plugin_version": plugin_version(),
        "generated_at": None,
        "summary": {
            "skills": len(policies),
            "dispatch_enabled": len(dispatch_coverage["skills_with_dispatch"]),
            "inline_only": len(dispatch_coverage["inline_only_skills"]),
            "release_critical": len(dispatch_coverage["release_critical_skills"]),
        },
        "dispatch_coverage": dispatch_coverage,
        "skills": policies,
    }
    policy["source_hash"] = stable_hash({k: policy[k] for k in ("plugin_version", "summary", "dispatch_coverage", "skills")})
    return policy


def routing_policy_findings(policy: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    known_skills = set(source_skill_map())
    known_agents = agent_names()
    known_panels = set(panel_map())
    seen_skills: set[str] = set()
    for item in policy.get("skills", []):
        skill = str(item.get("skill") or "")
        seen_skills.add(skill)
        if skill not in known_skills:
            findings.append({"severity": "high", "skill": skill, "issue": "policy skill missing from source specs"})
        dispatch_agent = str((item.get("dispatch_to") or {}).get("agent") or "")
        if dispatch_agent and dispatch_agent not in known_agents:
            findings.append({"severity": "high", "skill": skill, "issue": f"dispatch_to agent does not exist: {dispatch_agent}"})
        escalation = item.get("panel_escalation") or {}
        panel_names = set(escalation.get("paired_panels") or [])
        if escalation.get("preferred_panel"):
            panel_names.add(str(escalation["preferred_panel"]))
        for panel in sorted(panel_names):
            if panel not in known_panels:
                findings.append({"severity": "high", "skill": skill, "issue": f"panel reference does not exist: {panel}"})
        runtime_support = item.get("runtime_support") or {}
        for field in ("claude_command", "codex_command", "mcp_tools"):
            if not runtime_support.get(field):
                findings.append({"severity": "high", "skill": skill, "issue": f"missing runtime_support.{field}"})
        if item.get("default_execution") not in {"inline", "agent", "panel", "command", "skill-only"}:
            findings.append({"severity": "high", "skill": skill, "issue": f"invalid default_execution: {item.get('default_execution')}"})
    for missing in sorted(known_skills - seen_skills):
        findings.append({"severity": "high", "skill": missing, "issue": "source skill missing from routing policy"})
    return findings


def validate_routing_policy(policy: dict[str, Any]) -> None:
    findings = routing_policy_findings(policy)
    if findings:
        detail = "; ".join(f"{item.get('skill')}: {item.get('issue')}" for item in findings[:10])
        raise SystemExit(f"routing policy invalid: {detail}")


def routing_policy_text(policy: dict[str, Any]) -> str:
    return json.dumps(policy, indent=2, sort_keys=True) + "\n"


def write_routing_policy(root: Path | None = None, *, check: bool = False) -> Path:
    root = root or ROOT
    target = root / "dist" / "routing-policy.json"
    policy = build_routing_policy(root)
    validate_routing_policy(policy)
    rendered = routing_policy_text(policy)
    if check:
        if not target.exists():
            raise SystemExit("dist/routing-policy.json is missing; run scripts/build-routing-policy.py")
        if target.read_text(encoding="utf-8") != rendered:
            raise SystemExit("dist/routing-policy.json is stale; run scripts/build-routing-policy.py")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    return target


def load_routing_policy(root: Path | None = None) -> dict[str, Any]:
    root = root or ROOT
    path = root / "dist" / "routing-policy.json"
    if path.exists():
        return read_json(path, {})
    return build_routing_policy(root)


def policy_for_skill(policy: dict[str, Any], skill: str) -> dict[str, Any]:
    for item in policy.get("skills", []):
        if item.get("skill") == skill:
            return item
    return {}


def candidate_panel_names(skill_policy: dict[str, Any], graph: dict[str, Any]) -> list[str]:
    names: set[str] = set()
    escalation = skill_policy.get("panel_escalation") or {}
    if escalation.get("preferred_panel"):
        names.add(str(escalation["preferred_panel"]))
    for panel in escalation.get("paired_panels") or []:
        names.add(str(panel))
    skill = skill_policy.get("skill")
    for edge in graph.get("edges", []):
        if edge.get("source") == f"skill:{skill}" and edge.get("relation") == "may_use_panel":
            target = str(edge.get("target", ""))
            if target.startswith("panel:"):
                names.add(target.split(":", 1)[1])
    return sorted(names)


def panel_score(panel: dict[str, Any], intent: str, *, linked: bool, preferred: bool) -> float:
    text = " ".join(
        str(value)
        for value in (
            panel.get("name"),
            panel.get("title"),
            panel.get("use_when"),
            panel.get("do_not_use_when"),
            " ".join(panel.get("pathfinder_tags") or []),
        )
        if value
    )
    intent_tokens = set(tokenize(intent))
    score = 0.0
    if linked:
        score += 12.0
    if preferred:
        score += 8.0
    score += 3.0 * len(intent_tokens & set(tokenize(text)))
    if PANEL_LANGUAGE.search(intent):
        score += 16.0
    if HIGH_STAKES_LANGUAGE.search(intent):
        score += 8.0
    do_not = str(panel.get("do_not_use_when") or "")
    if do_not and len(intent_tokens & set(tokenize(do_not))) >= 3:
        score -= 6.0
    return round(score, 3)


def panel_candidates(
    *,
    policy: dict[str, Any],
    graph: dict[str, Any],
    skill_name: str,
    intent: str,
    budget: str,
    confidence_gap: float,
) -> list[dict[str, Any]]:
    panels = panel_map()
    skill_policy = policy_for_skill(policy, skill_name)
    linked_names = set(candidate_panel_names(skill_policy, graph))
    explicit_panel = bool(PANEL_LANGUAGE.search(intent))
    high_stakes = bool(HIGH_STAKES_LANGUAGE.search(intent))
    selection_allowed = budget == "deep" or explicit_panel or high_stakes or confidence_gap < 0.10
    candidates: list[dict[str, Any]] = []
    preferred = (skill_policy.get("panel_escalation") or {}).get("preferred_panel")
    for name, panel in panels.items():
        linked = name in linked_names
        score = panel_score(panel, intent, linked=linked, preferred=name == preferred)
        if not linked and score < 12:
            continue
        candidates.append({
            "panel": name,
            "score": score,
            "linked_to_skill": linked,
            "preferred_for_skill": name == preferred,
            "selected": False,
            "selection_signals": {
                "budget": budget,
                "explicit_panel_language": explicit_panel,
                "high_stakes_scope": high_stakes,
                "low_confidence_gap": confidence_gap < 0.10,
            },
            "estimated_cost": panel.get("estimated_cost"),
            "mode": panel.get("mode"),
            "risk": panel.get("risk"),
            "confirmation": panel.get("confirmation", {}),
            "output_artifact": panel.get("output_artifact"),
            "use_when": panel.get("use_when"),
            "do_not_use_when": panel.get("do_not_use_when"),
            "pathfinder_tags": panel.get("pathfinder_tags", []),
        })
    candidates.sort(key=lambda item: (-float(item["score"]), str(item["panel"])))
    if selection_allowed and candidates and float(candidates[0].get("score") or 0) > 0:
        candidates[0]["selected"] = True
        for candidate in candidates[1:]:
            candidate["reason_lost"] = "lower panel score for this intent and selected skill"
    elif candidates:
        for candidate in candidates:
            candidate["reason_lost"] = "panel escalation guardrails did not trigger for budget, risk, or confidence"
    return candidates


def route_confidence_gap(routes: list[dict[str, Any]]) -> float:
    if len(routes) < 2:
        return 1.0
    top = float(routes[0].get("adjusted_score", routes[0].get("score", 0)) or 0)
    second = float(routes[1].get("adjusted_score", routes[1].get("score", 0)) or 0)
    if top <= 0:
        return 0.0
    return round(max(0.0, (top - second) / top), 3)


def build_routing_envelope(path_result: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    recommended = path_result.get("recommended_path") or {}
    skill = str(recommended.get("skill") or "")
    skill_policy = policy_for_skill(policy, skill)
    dispatches = []
    for agent in recommended.get("agents", []):
        handoff = agent_handoff_policy(str(agent), str(path_result.get("trace_id") or ""))
        prompt = dispatch_prompt(
            str(agent),
            focus=(skill_policy.get("dispatch_to") or {}).get("focus"),
            phase=(skill_policy.get("dispatch_to") or {}).get("phase"),
            artifact_path=str(handoff.get("artifact_path") or ""),
        )
        contract = handoff_contract_status(str(agent), handoff, prompt)
        dispatches.append({
            "agent": agent,
            "subagent_type": f"ultraprompt:{agent}",
            "focus": (skill_policy.get("dispatch_to") or {}).get("focus"),
            "phase": (skill_policy.get("dispatch_to") or {}).get("phase"),
            "handoff_policy": handoff,
            "handoff_contract_status": contract,
            "artifact_path": handoff.get("artifact_path"),
            "prompt": prompt,
        })
    handoff_policy = dispatches[0].get("handoff_policy") if dispatches else {"mode": "inline", "artifact": "none"}
    contract_status = dispatches[0].get("handoff_contract_status") if dispatches else {
        "schema": "handoff_contract_status.v1",
        "required": False,
        "ok": True,
        "status": "not_required",
        "missing": [],
    }
    return {
        "schema": "routing_envelope.v1",
        "trace_id": path_result.get("trace_id"),
        "intent_excerpt": str(path_result.get("intent", ""))[:200],
        "selected_skill": skill or None,
        "confidence": recommended.get("confidence"),
        "confidence_gap": path_result.get("confidence_gap"),
        "ambiguity": "low_gap" if float(path_result.get("confidence_gap") or 0) < 0.10 else "clear",
        "execution_mode": recommended.get("type"),
        "dispatches": dispatches,
        "panel_candidates": path_result.get("panel_candidates", []),
        "selected_panel": recommended.get("panel"),
        "risk": recommended.get("risk"),
        "confirmation": skill_policy.get("confirmation") or recommended.get("risk", {}),
        "expected_artifact": skill_policy.get("artifact_type"),
        "validation_hint": "Run pathfinder/router/release gates after applying routing changes.",
        "alternatives": path_result.get("alternatives", []),
        "reasons_not_selected": [
            {"skill": alt.get("skill"), "reason": alt.get("reason_lost")}
            for alt in path_result.get("alternatives", [])
        ],
        "policy_influences": path_result.get("policy_influences", []),
        "memory_influences": path_result.get("memory_influences", []),
        "graph_hash": path_result.get("graph_hash"),
        "telemetry_policy": {
            "producer": "pathfinder",
            "telemetry_source": path_result.get("telemetry_source") or "runtime",
            "required": bool(skill_policy.get("telemetry_required")),
        },
        "handoff_policy": handoff_policy,
        "handoff_contract_status": contract_status,
        "reliability": {
            "handoff_mode": handoff_policy.get("mode"),
            "artifact_required": handoff_policy.get("artifact") == "required",
            "handoff_contract_ok": contract_status.get("ok"),
            "truncation_observed": None,
            "failure_kind": None,
        },
        "telemetry_evidence": {
            "policy_influences": path_result.get("policy_influences", []),
            "memory_influences": path_result.get("memory_influences", []),
            "graph_hash": path_result.get("graph_hash"),
        },
    }


def routing_decision_from_path(path_payload: dict[str, Any], *, runtime: str, constraints: dict[str, Any] | None = None) -> dict[str, Any]:
    path_result = path_payload.get("path", path_payload)
    recommended = path_result.get("recommended_path") or {}
    envelope = path_result.get("routing_envelope") or {}
    action = recommended.get("type") or "inline"
    if action == "agent-assisted skill":
        decision_type = "agent"
    elif action == "panel":
        decision_type = "panel"
    elif action == "command":
        decision_type = "command"
    else:
        decision_type = "inline" if action == "skill-only" else action
    return {
        "schema": "routing_decision.v1",
        "trace_id": path_result.get("trace_id"),
        "intent": path_result.get("intent"),
        "runtime": runtime,
        "top_skill": recommended.get("skill"),
        "confidence": recommended.get("confidence"),
        "decision_type": decision_type,
        "execution_mode": action,
        "dispatches": envelope.get("dispatches", []),
        "panel": recommended.get("panel"),
        "risk": recommended.get("risk"),
        "confirmation_required": bool((recommended.get("risk") or {}).get("confirmation_required")),
        "reason": "; ".join(recommended.get("rationale") or [])[:500],
        "trace": {
            "confidence_gap": path_result.get("confidence_gap"),
            "alternatives": path_result.get("alternatives", []),
            "constraints": constraints or {},
        },
        "telemetry_policy": envelope.get("telemetry_policy", {"producer": "route_trigger_plan", "telemetry_source": "runtime"}),
        "handoff_policy": envelope.get("handoff_policy"),
        "handoff_contract_status": envelope.get("handoff_contract_status"),
        "reliability": envelope.get("reliability"),
        "dry_run": True,
        "runtime_support": {
            "claude_command": recommended.get("command"),
            "codex_command": recommended.get("codex_command"),
            "mcp_tools": ["route_trigger_plan", "pathfind_workflow", "panel_plan"],
        },
    }


def run_pathfind_for_decision(intent: str, *, runtime: str = "codex", budget: str = "standard", repo: str = "", constraints: dict[str, Any] | None = None) -> dict[str, Any]:
    cmd = [sys.executable, str(ROOT / "scripts" / "pathfinder.py"), "pathfind", "--intent", intent, "--budget", budget, "--dry-run", "--no-telemetry"]
    if repo:
        cmd.extend(["--repo", repo])
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=60)
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        payload = command_result(False, error=proc.stdout or proc.stderr, exit=proc.returncode)
    if not payload.get("ok"):
        return payload
    return command_result(True, routing_decision=routing_decision_from_path(payload, runtime=runtime, constraints=constraints))
