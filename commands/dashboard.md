---
description: Launch the Ultraprompt live dashboard — catalog browser + streaming telemetry. Auto-opens browser at localhost:5174 (or next free port). Idempotent — re-running just opens the existing instance.
argument-hint: "[--stop | --status]"
---

# Ultraprompt Dashboard

Launch the dashboard, surface the entire plugin ecosystem (31 agents, 55 skills, 46 MCP tools, 32 commands, 13 panels, 31 artifact schemas) with live invocation telemetry streaming from the evidence ledger.

## Usage

- `/ultraprompt:dashboard` — start dashboard, open browser
- `/ultraprompt:dashboard --status` — check if running
- `/ultraprompt:dashboard --stop` — stop the dashboard process

## What you'll see

Three-pane localhost UI at `http://localhost:5174/`:

- **Left pane**: catalog tree (skills, agents, panels, MCP tools, commands, artifact schemas) — searchable with ⌘K, filterable by tier
- **Center pane**: entity detail — description, trigger phrases, distinctive judgment, failure modes, workflow, output contract, lane boundaries, anti-patterns, recent invocations
- **Right pane**: live activity feed — filterable/exportable invocation telemetry with low-value guard noise hidden by default

## Dispatch

This command invokes the `dashboard_launch` MCP tool. It will:

1. Check `~/.ultraprompt/state/dashboard.pid` — if running, just open the browser to it
2. Otherwise spawn `scripts/dashboard.py` via `subprocess.Popen(start_new_session=True)`
3. Pick a free port starting at 5174 (scans up to 5199)
4. Wait for server health
5. Open browser (suppressible with `--no-open` if scripted)

## Prerequisites

`aiohttp` Python package. If missing, the command will print:

```
ERROR: aiohttp not installed. Install with:
  pip3 install --user aiohttp
```

## Behavior in argument

If `$ARGUMENTS` contains `--stop`, invoke `dashboard_stop` MCP tool. If `--status`, invoke `dashboard_status`. Otherwise `dashboard_launch`.
