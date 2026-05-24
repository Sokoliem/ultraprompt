---
description: Alias for /ultraprompt:dashboard. Opens the V8 Mission Control dashboard (catalog browser + live telemetry + memory + dreams + pathfinder + learning + graph + governance health).
argument-hint: "[--status|--stop|--port N]"
---

# Ultraprompt Mission Control (alias)

This command is preserved for backward compatibility. The Mission Control dashboard is now opened by `/ultraprompt:dashboard`.

Run `/ultraprompt:dashboard` (or `/ultraprompt:dashboard --status` / `--stop`) — it surfaces the same Mission Control panes (catalog, live invocation telemetry, memory, dreams, pathfinder, learning, graph, governance health) plus the cognitive endpoints at `/api/cognitive/health`.

## Dispatch

When invoked directly, dispatch to the same MCP tools `/ultraprompt:dashboard` uses:

- No args: `dashboard_launch`
- `--status`: `dashboard_status`
- `--stop`: `dashboard_stop`
