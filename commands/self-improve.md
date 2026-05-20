---
description: Run or inspect V8.5 evidence-backed self-improvement. Supports dry-run, canary, autopilot, list/latest, and rollback.
argument-hint: "[run|latest|list|rollback <run_id>] [--mode dry-run|canary|autopilot] [--scope all|routing|telemetry|dashboard|tests]"
---

# Ultraprompt Self Improve

Run the V8.5 self-improvement autopilot. It mines telemetry, materializes hypotheses, writes run/patch/rollback artifacts, validates gates, and only mutates local repo files through the gated runner.

## Usage

- `/ultraprompt:self-improve run --mode dry-run --scope routing`
- `/ultraprompt:self-improve run --mode canary --scope all`
- `/ultraprompt:self-improve run --mode autopilot --scope routing`
- `/ultraprompt:self-improve latest`
- `/ultraprompt:self-improve list`
- `/ultraprompt:self-improve rollback <run_id>`

Codex does not route plugin command markdown through its native `/` slash parser. In Codex, use `$ultraprompt:self-improve ...`, plain language, or the MCP tools directly.

## Dispatch

Prefer MCP tools: `self_improve_run`, `self_improve_runs`, and `self_improve_rollback`.
Use `scripts/self-improve.py` from the plugin root when MCP tools are unavailable.

## Safety

Scheduled or unattended runs should start with `dry-run` or `canary`. The dream job defaults to canary; set `ULTRAPROMPT_SELF_IMPROVE_DREAM_MODE=autopilot` only after canary evidence is healthy. Full `autopilot` may mutate local repo files after gates pass, but it never commits, pushes, installs, publishes, or mutates remotes.
