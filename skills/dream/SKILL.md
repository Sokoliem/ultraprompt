---
name: "dream"
description: "When user says 'ultraprompt:dream / $ultraprompt:dream / dream run / dream status / dream review / run a dream job' - provides the Codex-compatible entrypoint for safe V8 dream jobs. DEFAULT for Codex users trying to run the Claude `/ultraprompt:dream` command."
when_to_use: "Use when the user invokes the dream command by name, asks to run or inspect safe dream jobs, or reports that `/ultraprompt:dream` is not recognized in Codex. This is the Codex skill bridge for the Claude Code slash command; Codex native slash parsing does not route plugin command markdown."
argument-hint: "[run [job]|status|review|validate-catalog] [--repo path] [--dry-run]"
tier: "core"
aliases: ["dream-run", "dream-status", "dream-review", "ultraprompt-dream"]
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Dream

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

Dream is an operations bridge, not a planning or writing lane. It should run or inspect local dream jobs through MCP tools or the bundled runner, report exact artifacts created, and avoid treating dream output as verified truth. If the user used a slash form in Codex, explain that Codex rejected the slash command before plugin routing and continue via this skill/MCP path.

## First signals to inspect

- User types `ultraprompt:dream run`, `$ultraprompt:dream run`, or asks why `/ultraprompt:dream` is unrecognized.
- User asks for dream status, dream review, route-learning dreams, repo-reflection dreams, or session-compaction.
- The task is operational: run a safe local job, inspect reports, or validate the dream catalog.

## Failure modes specific to this lane

- Claiming Codex supports plugin slash commands when the slash parser rejected the command.
- Stopping at 'job is required' for a bare `run` instead of using the safe default `session-compaction`.
- Presenting dream reports or memory candidates as durable facts before review.
- Mutating repository files from a dream job outside the gated self-improvement runner.
- Ignoring the concrete report path or failure payload from the runner.

## Workflow

1. Parse `$ARGUMENTS` into one operation: status, run, review, or validate-catalog.
2. For `run` with no job, default to `session-compaction` and state that default.
3. Prefer MCP tools: `dream_status`, `dream_run`, and `dream_review`. Use the bundled `scripts/dream-runner.py` from the plugin root if MCP tools are unavailable.
4. For `validate-catalog`, run `python3 scripts/dream-runner.py validate-catalog` from the plugin root.
5. Return exact result fields: ok/error, job, report id, report path, candidate ids if present, and whether repo mutation occurred.
6. If the user attempted `/ultraprompt:dream` in Codex, make the runtime boundary explicit: use `$ultraprompt:dream ...`, natural language, or the MCP dream tools in Codex; slash command markdown is for Claude Code.

## Validation

A successful run reports `ok: true` and either recent dream status, a report path under `~/.ultraprompt/dreams/reports`, recent report ids, a clean catalog validation result, or a self-improvement run id with patch and rollback manifests. Bare `run` must resolve to `session-compaction`. Dream jobs remain repo-read-only except `self-improvement-autopilot`, which defaults to canary mode and may mutate local repo files only when configured for autopilot through the gated self-improvement runner.

## Output contract

Runtime note when slash command was attempted | Operation executed | Job/default used | Result status | Report path/id or recent reports | Candidate memory/learning ids if present | Repo mutation statement | Next review action if output created candidates

## Subagent delegation

Do not dispatch by default. This is a narrow operations bridge; use dream-synthesizer only when the user asks to analyze multiple dream reports after they exist.

## V4 aliases

This skill answers to V4 names: `dream-run`, `dream-status`, `dream-review`, `ultraprompt-dream`. The router resolves them to `dream` and notes the alias in its response.
