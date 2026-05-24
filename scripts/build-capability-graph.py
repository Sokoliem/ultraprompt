#!/usr/bin/env python3
"""Build/check the V8 capability graph."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from cognitive_common import ROOT, command_result, plugin_version, print_json, read_json, stable_hash

OUT = ROOT / "dist" / "capability-graph.json"


def load_json(rel: str, default: Any) -> Any:
    path = ROOT / rel
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mcp_tools() -> list[dict[str, Any]]:
    candidates = [ROOT / "mcp" / "ultraprompt_meta.py", ROOT / "mcp" / "ultraprompt_meta.py"]
    path = next((p for p in candidates if p.exists()), candidates[0])
    module = load_module("ultraprompt_meta_graph", path)
    out: list[dict[str, Any]] = []
    for name, entry in sorted(module.TOOLS.items()):
        desc, schema = entry[0], entry[1]
        annotations = entry[3] if len(entry) > 3 else None
        item: dict[str, Any] = {"name": name, "description": desc, "input_schema": schema}
        if annotations:
            item["annotations"] = annotations
            if annotations.get("readOnlyHint"):
                item["readonly"] = True
        out.append(item)
    return out


def artifact_schemas() -> list[str]:
    module = load_module("artifact_validate_graph", ROOT / "scripts" / "artifact-validate.py")
    return sorted(module.SCHEMAS.keys())


def command_names() -> list[str]:
    return sorted(p.stem for p in (ROOT / "commands").glob("*.md"))


def hook_names() -> list[str]:
    hooks = load_json("hooks/hooks.json", {})
    out: list[str] = []
    for groups in (hooks.get("hooks") or {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                out.append(str(hook.get("command", "")).split("/")[-1] or "hook")
    return sorted(out)


def add_node(nodes: list[dict[str, Any]], node_id: str, kind: str, label: str, **attrs: Any) -> None:
    nodes.append({"id": node_id, "kind": kind, "label": label, **{k: v for k, v in attrs.items() if v not in (None, "", [])}})


def add_edge(edges: list[dict[str, Any]], source: str, target: str, relation: str, **attrs: Any) -> None:
    edges.append({"source": source, "target": target, "relation": relation, **{k: v for k, v in attrs.items() if v not in (None, "", [])}})


def build_graph() -> dict[str, Any]:
    skill_specs = load_json("source/skill-specs.json", [])
    agent_specs = load_json("source/agent-specs.json", [])
    panel_specs = load_json("source/panel-specs.json", [])
    dream_jobs = load_json("source/dream-jobs.json", {}).get("jobs", [])
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for skill in skill_specs:
        add_node(
            nodes,
            f"skill:{skill['name']}",
            "skill",
            skill["name"],
            tier=skill.get("tier"),
            family=skill.get("family"),
            mode=skill.get("mode"),
            risk=skill.get("risk"),
            confirmation=skill.get("confirmation"),
        )
        dispatch = skill.get("dispatch_to") or {}
        if dispatch.get("agent"):
            add_edge(edges, f"skill:{skill['name']}", f"agent:{dispatch['agent']}", "dispatches_to", phase=dispatch.get("phase"), focus=dispatch.get("focus"))
        for panel in skill.get("paired_panels") or skill.get("cognitive", {}).get("paired_panels") or []:
            add_edge(edges, f"skill:{skill['name']}", f"panel:{panel}", "may_use_panel")
        if skill.get("output_contract"):
            add_edge(edges, f"skill:{skill['name']}", "artifact:structured_output", "emits")

    for agent in agent_specs:
        add_node(nodes, f"agent:{agent['name']}", "agent", agent["name"], color=agent.get("color"), risk=agent.get("risk"))

    for panel in panel_specs:
        confirmation = panel.get("confirmation") or {}
        add_node(
            nodes,
            f"panel:{panel['name']}",
            "panel",
            panel["name"],
            artifact=panel.get("output_artifact"),
            estimated_cost=panel.get("estimated_cost"),
            mode=panel.get("mode"),
            risk=panel.get("risk"),
            confirmation_required=confirmation.get("required", False),
            pathfinder_tags=panel.get("pathfinder_tags", []),
        )
        for phase in panel.get("phases", []):
            phase_id = f"panel_phase:{panel['name']}:{phase['phase']}"
            contract = panel.get("phase_contracts", {}).get(phase["phase"], {})
            add_node(
                nodes,
                phase_id,
                "panel_phase",
                f"{panel['name']}:{phase['phase']}",
                parallel=phase.get("parallel"),
                contract_input=contract.get("input"),
                contract_output=contract.get("output"),
                quality_gate=contract.get("quality_gate"),
            )
            add_edge(edges, f"panel:{panel['name']}", phase_id, "has_phase")
            for agent in phase.get("agents", []):
                add_edge(edges, phase_id, f"agent:{agent}", "dispatches_to", parallel=phase.get("parallel"))
        if panel.get("output_artifact"):
            add_edge(edges, f"panel:{panel['name']}", f"artifact:{panel['output_artifact']}", "emits")
        for artifact in panel.get("artifacts", []):
            add_edge(edges, f"panel:{panel['name']}", f"artifact:{artifact}", "emits")
        for artifact in panel.get("handoff_artifacts", []):
            add_edge(edges, f"panel:{panel['name']}", f"artifact:{artifact}", "hands_off")
        for validator in panel.get("validators", []):
            add_edge(edges, f"panel:{panel['name']}", f"validator:{validator}", "validated_by")
        for ledger in panel.get("ledger_writes", []):
            add_edge(edges, f"panel:{panel['name']}", f"ledger:{ledger}", "writes")
        policy_ledgers = {
            "memory_policy": "memory-db",
            "learning_policy": "learning-queue",
            "dream_policy": "dream-reports",
        }
        for policy_name, ledger in policy_ledgers.items():
            policy = panel.get(policy_name) or {}
            if any(value is True for key, value in policy.items() if key != "promote"):
                add_edge(edges, f"panel:{panel['name']}", f"ledger:{ledger}", "governed_by", policy=policy_name)

    for command in command_names():
        add_node(nodes, f"command:{command}", "command", command)
        command_tools = {
            "memory": "memory_query",
            "dream": "dream_run",
            "dream-review": "dream_review",
            "learn-review": "learning_candidates",
            "pathfind": "pathfind_workflow",
            "graph": "capability_graph",
            "mission-control": "dashboard_launch",
        }
        if command in command_tools:
            add_edge(edges, f"command:{command}", f"mcp:{command_tools[command]}", "invokes")

    for tool in mcp_tools():
        add_node(nodes, f"mcp:{tool['name']}", "mcp_tool", tool["name"], description=tool.get("description"))
        for script_name in {
            "memory": "memory-store.py",
            "dream": "dream-runner.py",
            "pathfind": "pathfinder.py",
            "capability_graph": "build-capability-graph.py",
            "learning": "learning-queue.py",
            "route_feedback": "learning-queue.py",
        }.items():
            prefix, script = script_name
            if tool["name"].startswith(prefix):
                add_edge(edges, f"mcp:{tool['name']}", f"validator:{script}", "backs_onto")

    for schema in artifact_schemas():
        add_node(nodes, f"artifact:{schema}", "artifact_schema", schema)
        add_edge(edges, f"artifact:{schema}", "validator:artifact-validate.py", "validated_by")

    validators = [
        "validate-plugin.py",
        "artifact-validate.py",
        "catalog-audit.py",
        "audit-catalog-consistency.py",
        "build-capability-graph.py",
        "dream-runner.py",
        "learning-queue.py",
        "memory-store.py",
        "pathfinder.py",
        "run-hook-tests.py",
        "run-pathfinder-tests.py",
        "run-cognitive-tests.py",
        "run-router-bench.py",
    ]
    for validator in validators:
        add_node(nodes, f"validator:{validator}", "validator", validator)

    for hook in hook_names():
        add_node(nodes, f"hook:{hook}", "hook", hook)

    for ledger in ["cognitive-events", "memory-db", "learning-queue", "dream-reports", "ledger-v2", "gap-ledger"]:
        add_node(nodes, f"ledger:{ledger}", "ledger", ledger)

    for job in dream_jobs:
        add_node(nodes, f"dream:{job['name']}", "dream_job", job["name"], cadence=job.get("cadence"), budget=job.get("budget"))
        for output in job.get("outputs", []):
            add_edge(edges, f"dream:{job['name']}", f"artifact:{output}", "emits")
        add_edge(edges, f"dream:{job['name']}", "ledger:dream-reports", "writes")

    artifact_targets = sorted({
        str(edge["target"]).split(":", 1)[1]
        for edge in edges
        if edge.get("relation") in {"emits", "hands_off"} and str(edge.get("target", "")).startswith("artifact:")
    })
    existing_node_ids = {n["id"] for n in nodes}
    for artifact in artifact_targets:
        node_id = f"artifact:{artifact}"
        if node_id not in existing_node_ids:
            add_node(nodes, node_id, "artifact", artifact)
            existing_node_ids.add(node_id)

    deduped_edges = []
    seen_edges = set()
    for edge in edges:
        key = json.dumps(edge, sort_keys=True)
        if key not in seen_edges:
            deduped_edges.append(edge)
            seen_edges.add(key)
    edges = deduped_edges

    node_ids = {n["id"] for n in nodes}
    health = {"ok": True, "findings": []}
    for edge in edges:
        if edge["source"] not in node_ids:
            health["findings"].append({"severity": "high", "issue": "missing_source", "edge": edge})
        if edge["target"] not in node_ids and not edge["target"].startswith("artifact:structured_output"):
            health["findings"].append({"severity": "high", "issue": "missing_target", "edge": edge})
    health["ok"] = not any(f["severity"] == "high" for f in health["findings"])

    graph = {
        "schema": "capability_graph.v1",
        "plugin_version": plugin_version(),
        "generated_at": None,
        "nodes": sorted(nodes, key=lambda n: n["id"]),
        "edges": sorted(edges, key=lambda e: (e["source"], e["target"], e["relation"])),
        "health": health,
    }
    graph["source_hash"] = stable_hash({k: graph[k] for k in ("plugin_version", "nodes", "edges", "health")})
    return graph


def graph_text(graph: dict[str, Any]) -> str:
    return json.dumps(graph, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    graph = build_graph()
    if args.json:
        print_json(command_result(graph["health"]["ok"], graph=graph))
        return 0 if graph["health"]["ok"] else 1
    text = graph_text(graph)
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("dist/capability-graph.json is stale; run scripts/build-capability-graph.py")
            return 1
        print("dist/capability-graph.json is current.")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0 if graph["health"]["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
