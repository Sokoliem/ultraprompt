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
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PREFIXES = ("ultraprompt:", "ultra-prompt:")
RELEASE_CRITICAL_V8_2_SKILLS = ("goal", "frontend-visual-qa", "pathfinding-invocation-review")


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


def read_runtime_events(days: int) -> list[dict[str, Any]]:
    ledger = load_ledger_module()
    if ledger is None:
        return []
    return ledger.read_events(days=days)


def read_project_dispatches(days: int) -> list[dict[str, Any]]:
    projects = Path.home() / ".claude" / "projects"
    if not projects.exists():
        return []
    cutoff = (datetime.now() - timedelta(days=days)).timestamp()
    dispatches: list[dict[str, Any]] = []
    for parent_jsonl in projects.rglob("*.jsonl"):
        if "subagents" in parent_jsonl.parts:
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


def golden_intents() -> set[str]:
    cases = load_json(ROOT / "tests" / "pathfinder" / "golden-cases.json", [])
    return {str(case.get("intent", "")) for case in cases if case.get("intent")}


def summarize(days: int) -> dict[str, Any]:
    skill_names, agent_names = catalog_names()
    runtime_events = read_runtime_events(days)
    project_dispatches = read_project_dispatches(days)
    pathfinder_events = read_pathfinder_events(days)
    bench_intents = golden_intents()

    skill_invocations: Counter[str] = Counter()
    legacy_skill_invocations: Counter[str] = Counter()
    mcp_calls: Counter[str] = Counter()
    ledger_agent_dispatches: list[dict[str, Any]] = []

    for event in runtime_events:
        event_type = event.get("type")
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

    combined_dispatches = ledger_agent_dispatches + project_dispatches
    dispatch_counts = Counter(str(item.get("agent", "?")) for item in combined_dispatches)
    total_dispatches = len(combined_dispatches)
    plugin_dispatches = [item for item in combined_dispatches if item.get("is_plugin_agent")]
    explore_dispatches = [item for item in combined_dispatches if item.get("agent") == "Explore"]
    legacy_agent_dispatches = [item for item in combined_dispatches if item.get("legacy_prefix")]

    pathfinder_by_skill = Counter()
    pathfinder_by_source = Counter()
    bench = 0
    synthetic = 0
    real = 0
    for event in pathfinder_events:
        data = event.get("data") or {}
        intent = str(data.get("intent", ""))
        event_source = str(data.get("source") or "").strip().lower()
        if event_source in {"bench", "golden", "test"} or intent in bench_intents:
            bench += 1
            source = "bench"
        elif event_source == "synthetic":
            synthetic += 1
            source = "synthetic"
        else:
            real += 1
            source = event_source or "runtime"
        pathfinder_by_source[source] += 1
        pathfinder_by_skill[str(data.get("skill", "?"))] += 1

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

    return {
        "schema": "invocation_telemetry_audit.v2",
        "generated_at": int(time.time()),
        "window_days": days,
        "runtime_events": {
            "total": len(runtime_events),
            "skill_invocations": sum(skill_invocations.values()),
            "live_skill_invocations_total": sum(skill_invocations.values()),
            "legacy_skill_invocations": sum(legacy_skill_invocations.values()),
            "mcp_tool_calls": sum(mcp_calls.values()),
            "top_skills": dict(skill_invocations.most_common(20)),
            "top_mcp_tools": dict(mcp_calls.most_common(20)),
            "new_release_skill_invocations": release_critical_skills,
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
        "pathfinder": {
            "decisions": len(pathfinder_events),
            "real_decisions": real,
            "bench_decisions": bench,
            "synthetic_decisions": synthetic,
            "synthetic_or_bench_decisions": synthetic + bench,
            "real_pathfinder_ratio_pct": round(real_ratio, 1),
            "bench_pathfinder_ratio_pct": round(bench_ratio, 1),
            "by_source": dict(pathfinder_by_source.most_common()),
            "by_skill": dict(pathfinder_by_skill.most_common(30)),
        },
        "activation_gaps": {
            "skills_never_invoked": sorted(skill_names - fired_skills),
            "agents_never_dispatched": sorted(agent_names - fired_agents),
        },
    }


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
    if pathfinder["bench_pathfinder_ratio_pct"] > args.max_bench_pathfinder_ratio:
        failures.append(
            f"bench pathfinder ratio {pathfinder['bench_pathfinder_ratio_pct']}% > {args.max_bench_pathfinder_ratio}%"
        )
    required_skills = list(args.required_live_skill or [])
    if args.release_critical_v8_2:
        required_skills.extend(RELEASE_CRITICAL_V8_2_SKILLS)
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
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--enforce", action="store_true")
    parser.add_argument("--min-dispatches", type=int, default=20)
    parser.add_argument("--min-plugin-agent-share", type=float, default=25.0)
    parser.add_argument("--max-explore-share", type=float, default=50.0)
    parser.add_argument("--min-skill-invocations", type=int, default=1)
    parser.add_argument("--min-real-pathfinder-decisions", type=int, default=1)
    parser.add_argument("--min-real-pathfinder-ratio", type=float, default=0.0)
    parser.add_argument("--max-bench-pathfinder-ratio", type=float, default=100.0)
    parser.add_argument("--required-live-skill", action="append", default=[])
    parser.add_argument("--required-live-agent", action="append", default=[])
    parser.add_argument("--release-critical-v8-2", action="store_true",
                        help="Require live invocation for V8.2 release-critical skills")
    args = parser.parse_args()

    report = summarize(args.days)
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
        "max_bench_pathfinder_ratio": args.max_bench_pathfinder_ratio,
        "required_live_skills": sorted(set((args.required_live_skill or []) + (list(RELEASE_CRITICAL_V8_2_SKILLS) if args.release_critical_v8_2 else [])), key=canonical_plugin_name),
        "required_live_agents": sorted(set(args.required_live_agent or []), key=canonical_plugin_name),
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
        print(f"- pathfinder: {pathfinder['decisions']} decisions, {pathfinder['real_decisions']} real ({pathfinder['real_pathfinder_ratio_pct']}%), {pathfinder['bench_decisions']} bench, {pathfinder['synthetic_decisions']} synthetic")
        if failures:
            print("Failures:")
            for failure in failures:
                print(f"- {failure}")
    return 1 if args.enforce and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
