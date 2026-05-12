#!/usr/bin/env python3
"""Explainable V8 skill/agent/panel pathfinder."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from cognitive_common import ROOT, command_result, print_json, read_json, sortable_id, stable_hash

SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from ultraprompt_index import load_index, route_intent  # noqa: E402


def load_graph() -> dict[str, Any]:
    path = ROOT / "dist" / "capability-graph.json"
    if not path.exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "build-capability-graph.py")], cwd=ROOT, check=False, capture_output=True, text=True)
    return read_json(path, {"nodes": [], "edges": [], "health": {"ok": False}})


def load_policy() -> dict[str, Any]:
    candidates = [
        Path.home() / ".ultraprompt" / "learning" / "route-policy.json",
        Path.home() / ".ultraprompt" / "learning" / "route-policy.json",
    ]
    for path in candidates:
        if path.exists():
            return read_json(path, {"routes": []})
    return {"routes": []}


def memory_query(intent: str, repo: str, limit: int = 8) -> list[dict[str, Any]]:
    script = ROOT / "scripts" / "memory-store.py"
    args = [sys.executable, str(script), "query", "--text", intent[:120], "--limit", str(limit), "--include-inactive"]
    if repo:
        args.extend(["--repo", repo])
    try:
        proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=10)
        data = json.loads(proc.stdout)
        memories = data.get("memories", [])
        return [m for m in memories if m.get("status") in {"active", "candidate"}]
    except Exception:
        return []


def skill_by_name(index: dict[str, Any], name: str) -> dict[str, Any]:
    for skill in index.get("skills", []):
        if skill.get("name") == name:
            return skill
    return {}


def panel_for_skill(graph: dict[str, Any], skill: str) -> str | None:
    for edge in graph.get("edges", []):
        if edge.get("source") == f"skill:{skill}" and edge.get("relation") == "may_use_panel":
            return str(edge.get("target", "")).split(":", 1)[-1]
    return None


def agents_for_skill(graph: dict[str, Any], skill: str) -> list[str]:
    agents = []
    for edge in graph.get("edges", []):
        if edge.get("source") == f"skill:{skill}" and edge.get("relation") == "dispatches_to":
            target = str(edge.get("target", ""))
            if target.startswith("agent:"):
                agents.append(target.split(":", 1)[1])
    return sorted(set(agents))


def risk_for_skill(skill: dict[str, Any], intent: str) -> dict[str, Any]:
    mode = skill.get("mode") or ("write_capable" if skill.get("editing") else "read_only")
    risk = skill.get("risk") or ("medium" if mode == "write_capable" else "low")
    mutation_words = {"delete", "drop", "reset", "rewrite", "migrate", "install", "publish", "push", "apply", "change", "build", "fix"}
    mutation_intent = any(word in intent.lower() for word in mutation_words)
    confirmation_required = mode == "write_capable" and mutation_intent
    return {
        "mode": mode,
        "risk": risk,
        "mutation_intent": mutation_intent,
        "confirmation_required": confirmation_required,
        "rule": "read-only preferred for audit/review; mutation paths are marked for confirmation",
    }


def numeric_confidence(route: dict[str, Any]) -> float:
    for key in ("adjusted_score", "score"):
        value = route.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value))
        except (TypeError, ValueError):
            pass
    label = str(route.get("confidence", "")).lower()
    return {"high": 0.9, "medium": 0.6, "low": 0.35}.get(label, 0.0)


def apply_policy(routes: list[dict[str, Any]], intent: str, policy: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    influences = []
    adjusted = []
    for route in routes:
        route = dict(route)
        score = numeric_confidence(route)
        text = intent.lower()
        if route.get("skill") == "release-readiness" and any(phrase in text for phrase in ("release ready", "ship/no-ship", "ship ready", "ready to ship")):
            score += 100
            influences.append({"type": "pathfinder_rule", "skill": "release-readiness", "delta": 100, "reason": "release readiness intent"})
        if route.get("skill") == "repo-map" and "memory" in text and "repo" in text:
            score += 100
            influences.append({"type": "pathfinder_rule", "skill": "repo-map", "delta": 100, "reason": "repo-scoped memory lookup intent"})
        for overlay in policy.get("routes", []):
            pattern = str(overlay.get("intent_pattern", "")).lower()
            skill = overlay.get("skill")
            if pattern and pattern in intent.lower() and skill == route.get("skill"):
                delta = float(overlay.get("weight_delta", 0.1))
                score += delta
                influences.append({"type": "route_policy", "id": overlay.get("id"), "skill": skill, "delta": delta})
        route["adjusted_score"] = score
        adjusted.append(route)
    adjusted.sort(key=lambda r: r.get("adjusted_score", 0), reverse=True)
    return adjusted, influences


def expected_artifacts(skill: dict[str, Any]) -> list[str]:
    out = []
    contract = skill.get("output_contract")
    if contract:
        out.append("structured_output")
    for value in skill.get("outputs") or []:
        out.append(str(value))
    return sorted(set(out))


def pathfind(
    intent: str,
    *,
    repo: str = "",
    budget: str = "standard",
    dry_run: bool = True,
    no_telemetry: bool = False,
) -> dict[str, Any]:
    index = load_index(ROOT)
    graph = load_graph()
    policy = load_policy()
    raw_routes = route_intent(index, intent, limit=5)
    routes, policy_influences = apply_policy(raw_routes, intent, policy)
    memories = memory_query(intent, repo, limit=8)

    top = routes[0] if routes else {}
    skill = skill_by_name(index, str(top.get("skill", "")))
    agents = agents_for_skill(graph, skill.get("name", ""))
    preferred_panel = panel_for_skill(graph, skill.get("name", ""))
    path_type = "skill-only"
    if budget == "deep" and preferred_panel:
        path_type = "panel"
    elif agents:
        path_type = "agent-assisted skill"
    if skill.get("name") and skill.get("name") in {"dashboard", "doctor", "menu", "route"}:
        path_type = "command"

    risk = risk_for_skill(skill, intent)
    confidence = numeric_confidence(top)
    confidence = max(0.0, min(1.0, confidence + min(0.1, len(memories) * 0.01)))
    alternatives = []
    for alt in routes[1:4]:
        alternatives.append(
            {
                "skill": alt.get("skill"),
                "confidence": alt.get("confidence"),
                "adjusted_score": alt.get("adjusted_score"),
                "reason_lost": "lower route score after policy and memory context",
            }
        )

    trace_id = sortable_id("path")
    result = {
        "schema": "pathfinder_result.v1",
        "trace_id": trace_id,
        "intent": intent,
        "repo": repo,
        "dry_run": dry_run,
        "telemetry_enabled": not no_telemetry,
        "budget": budget,
        "recommended_path": {
            "type": path_type,
            "skill": skill.get("name"),
            "command": f"/ultraprompt:{skill.get('name')}" if skill.get("name") else None,
            "codex_command": f"$ultraprompt:{skill.get('name')}" if skill.get("name") else None,
            "agents": agents,
            "panel": preferred_panel if path_type == "panel" else None,
            "confidence": round(confidence, 3),
            "raw_score": top.get("score"),
            "adjusted_score": top.get("adjusted_score"),
            "rationale": [
                "router selected highest-scoring matching skill",
                "capability graph supplied agent/panel edges",
                "risk rules annotated mutation and read-only behavior",
            ],
            "expected_artifacts": expected_artifacts(skill),
            "risk": risk,
            "cost": {"budget": budget, "estimated": "high" if path_type == "panel" else ("medium" if agents else "low")},
        },
        "alternatives": alternatives,
        "memory_influences": [{"id": m.get("id"), "kind": m.get("kind"), "scope": m.get("scope"), "status": m.get("status")} for m in memories],
        "policy_influences": policy_influences,
        "graph_hash": graph.get("source_hash") or stable_hash(graph),
        "graph_health": graph.get("health", {}),
    }
    if not no_telemetry:
        emit_event(result)
    return command_result(True, path=result)


def emit_event(result: dict[str, Any]) -> None:
    script = ROOT / "scripts" / "cognitive-event-log.py"
    try:
        payload = {
            "source": "pathfinder",
            "trace_id": result["trace_id"],
            "intent": result["intent"][:200],
            "skill": result["recommended_path"].get("skill"),
            "path_type": result["recommended_path"].get("type"),
            "confidence": result["recommended_path"].get("confidence"),
            "raw_score": result["recommended_path"].get("raw_score"),
            "adjusted_score": result["recommended_path"].get("adjusted_score"),
            "agents": result["recommended_path"].get("agents", []),
            "panel": result["recommended_path"].get("panel"),
            "budget": result.get("budget"),
            "alternatives": [
                {
                    "skill": alt.get("skill"),
                    "adjusted_score": alt.get("adjusted_score"),
                    "confidence": alt.get("confidence"),
                }
                for alt in result.get("alternatives", [])
            ],
            "followed": None,
            "outcome": "recommended",
        }
        subprocess.run(
            [sys.executable, str(script), "write", "pathfinder_decision", "--json", json.dumps(payload), "--trace-id", result["trace_id"]],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pathfind")
    p.add_argument("--intent", required=True)
    p.add_argument("--repo", default="")
    p.add_argument("--budget", choices=["low", "standard", "deep"], default="standard")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-telemetry", action="store_true", help="do not write pathfinder_decision events")
    b = sub.add_parser("bench")
    b.add_argument("--json", action="store_true")
    b.add_argument("--no-telemetry", action="store_true", help="run golden tests without telemetry writes")
    e = sub.add_parser("explain")
    e.add_argument("intent")
    e.add_argument("--repo", default="")
    e.add_argument("--budget", choices=["low", "standard", "deep"], default="standard")
    e.add_argument("--no-telemetry", action="store_true", help="do not write pathfinder_decision events")

    args = parser.parse_args()
    if args.cmd in {"pathfind", "explain"}:
        intent = args.intent if args.cmd == "explain" else args.intent
        print_json(pathfind(intent, repo=args.repo, budget=args.budget, dry_run=True, no_telemetry=args.no_telemetry))
        return 0
    if args.cmd == "bench":
        bench_args = [sys.executable, str(ROOT / "scripts" / "run-pathfinder-tests.py"), "--json"]
        if args.no_telemetry:
            bench_args.append("--no-telemetry")
        proc = subprocess.run(bench_args, cwd=ROOT, capture_output=True, text=True, timeout=120)
        print(proc.stdout.strip())
        return proc.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
