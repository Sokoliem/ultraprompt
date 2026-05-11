#!/usr/bin/env python3
"""V8 Doctor: dispatch outcomes — reads subagent JSONLs directly.

Independent observability path. Survives telemetry hook bugs (the earlier shipped
'tool_name=Task' vs 'tool_name=Agent' issue showed why we need this).

Reports for the last 7 days:
- Total subagent dispatches
- Plugin specialist dispatches (ultraprompt:* agents) vs Explore vs other
- Per-agent dispatch counts
- Recent activity timeline
- Never-fired specialists (activation gaps)
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter


def find_dispatches(window_start_ts: float):
    """Read all parent session JSONLs and extract Task/Agent tool_use entries."""
    projects = Path.home() / ".claude/projects"
    if not projects.exists():
        return []

    dispatches = []
    for parent_jsonl in projects.rglob("*.jsonl"):
        # Skip subagent JSONLs (in subagents/ subdir)
        if "subagents" in parent_jsonl.parts:
            continue
        try:
            for line in parent_jsonl.read_text(encoding="utf-8").splitlines():
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                ts_str = e.get("timestamp", "")
                if not ts_str:
                    continue
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
                except Exception:
                    continue
                if ts < window_start_ts:
                    continue
                msg = e.get("message", {})
                if not isinstance(msg.get("content"), list):
                    continue
                for b in msg["content"]:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task"):
                        inp = b.get("input", {}) or {}
                        dispatches.append({
                            "ts": ts,
                            "tool": b.get("name"),
                            "subagent_type": inp.get("subagent_type", "?"),
                            "description": (inp.get("description") or "")[:80],
                        })
        except Exception:
            continue
    return dispatches


def main():
    days = 7
    if len(sys.argv) > 1:
        try: days = int(sys.argv[1])
        except: pass

    window_start = (datetime.now() - timedelta(days=days)).timestamp()
    dispatches = find_dispatches(window_start)

    print(f"=== Dispatch outcomes (last {days} days) ===")
    print(f"Total subagent dispatches: {len(dispatches)}")
    print()

    # Plugin vs Explore vs Other
    plugin = [d for d in dispatches if d["subagent_type"].startswith("ultraprompt:")]
    explore = [d for d in dispatches if d["subagent_type"] == "Explore"]
    other = [d for d in dispatches if d not in plugin and d not in explore]

    print(f"  Plugin specialists (ultraprompt:*): {len(plugin)}")
    print(f"  Built-in Explore:                    {len(explore)}")
    print(f"  Other:                               {len(other)}")
    if dispatches:
        plugin_pct = 100 * len(plugin) / len(dispatches)
        print(f"  Plugin share:                        {plugin_pct:.0f}%")

    # Per-agent
    print()
    print("=== Per-agent dispatch counts ===")
    by_agent = Counter(d["subagent_type"] for d in dispatches)
    for agent, n in by_agent.most_common():
        marker = "✓ plugin" if agent.startswith("ultraprompt:") else "  built-in" if agent == "Explore" else "  other"
        print(f"  {n:5d}  {agent:<35} {marker}")

    # Never-fired specialists
    KNOWN_SPECIALISTS = [
        "ultraprompt:reviewer", "ultraprompt:auditor", "ultraprompt:security-auditor",
        "ultraprompt:debugger", "ultraprompt:scout", "ultraprompt:test-strategist",
        "ultraprompt:writer", "ultraprompt:adversarial", "ultraprompt:router",
    ]
    fired = set(by_agent.keys())
    never_fired = [s for s in KNOWN_SPECIALISTS if s not in fired]
    if never_fired:
        print()
        print("=== Never-fired specialists (activation gaps) ===")
        for s in never_fired:
            print(f"  ⚠  {s}")
        print()
        print(f"Recommendation: review trigger phrasing in {Path.home() / '.claude/plugins/marketplaces/local-marketplace/ultraprompt/agents'}")

    # Recent timeline (last 10)
    if dispatches:
        print()
        print("=== Recent dispatches (last 10) ===")
        for d in sorted(dispatches, key=lambda x: -x["ts"])[:10]:
            ts_str = datetime.fromtimestamp(d["ts"]).strftime("%m-%d %H:%M")
            marker = "✓" if d["subagent_type"].startswith("ultraprompt:") else " "
            print(f"  {marker} {ts_str}  {d['subagent_type']:<35} {d['description']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
