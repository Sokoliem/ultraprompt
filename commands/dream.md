---
description: Run or inspect safe V8 dream jobs that compact sessions, reflect on repos, learn routes, inspect catalog health, prune memory candidates, and launch gated self-improvement.
argument-hint: "[run [job]|status|review|validate-catalog] [--repo path] [--dry-run]"
---

# Ultraprompt Dream

Run local scheduled-reflection jobs. Dream jobs are repo-read-only except `self-improvement-autopilot`, which runs in canary mode by default and may mutate local repo files only if `ULTRAPROMPT_SELF_IMPROVE_DREAM_MODE=autopilot` is set and the gated self-improvement runner passes.

## Usage

- `/ultraprompt:dream status`
- `/ultraprompt:dream run` (defaults to `session-compaction`)
- `/ultraprompt:dream run session-compaction`
- `/ultraprompt:dream run repo-reflection --repo .`
- `/ultraprompt:dream run self-improvement-autopilot --repo .`
- `/ultraprompt:dream review`

Codex does not route plugin command markdown through its native `/` slash parser. In Codex, use `$ultraprompt:dream ...`, plain `ultraprompt:dream ...`, or the MCP tools directly.

## Dispatch

Prefer MCP tools: `dream_run`, `dream_status`, and `dream_review`.
Use `scripts/dream-runner.py validate-catalog` for release-gate diagnostics.
