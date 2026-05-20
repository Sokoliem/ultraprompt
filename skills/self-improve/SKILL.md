---
name: "self-improve"
description: "When user says 'self improvement / run autopilot / improve the plugin from telemetry / apply learning automatically / rollback self improvement' - runs the V8.5 evidence-backed self-improvement autopilot. DEFAULT for direct requests to mine telemetry, generate repo patches, validate gates, apply safely, or roll back a previous self-improvement run."
when_to_use: "Use when the user explicitly asks to run, inspect, schedule, or roll back Ultraprompt self-improvement. This is the Codex skill bridge for Claude Code `/ultraprompt:self-improve`; Codex native slash parsing does not route plugin command markdown, so use this skill, natural language, MCP tools, or the bundled CLI."
argument-hint: "[run|latest|list|rollback <run_id>] [--mode dry-run|canary|autopilot] [--scope all|routing|telemetry|dashboard|tests]"
tier: "core"
aliases: ["self-improvement", "self-improve-run", "autopilot", "learning-autopilot"]
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Self Improve

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

Self-improvement is model-owned mutation with evidence gates, not a suggestion queue. Prefer dry-run for inspection, canary for scheduled or low-trust runs, and autopilot when the user explicitly wants gated local mutation. Never commit, push, install, or mutate remotes from this lane. Every applied change must have a run record, patch hash, gate matrix, learner eval, rollback manifest, and post-apply monitor status.

## First signals to inspect

- User asks to run self-improvement, autopilot, automated learning, or telemetry-backed patching.
- User asks whether learning can apply itself without human approval.
- User asks to list latest runs, inspect evidence, view rollback state, or revert a self-improvement run.
- User asks to schedule self-improvement separately from dream reporting.

## Failure modes specific to this lane

- Treating self-improvement as review-gated suggestions when the user asked for gated auto-apply.
- Running full autopilot on a schedule before canary/dry-run evidence is healthy.
- Applying changes without gate results, learner eval, patch hash, and rollback manifest.
- Committing, pushing, installing, or mutating remote state from self-improvement.
- Claiming a patch applied or rolled back without showing the run id and manifest path.

## Workflow

1. Parse `$ARGUMENTS` into run, latest, list, or rollback. Default bare run to `--mode dry-run --scope routing`.
2. Prefer MCP tools: `self_improve_run`, `self_improve_runs`, and `self_improve_rollback`. Use `python3 scripts/self-improve.py` from the plugin root if MCP tools are unavailable.
3. For scheduled work, prefer `dry-run` or `canary` unless the user explicitly requests `autopilot` and accepts local repo mutation.
4. For rollback, require the run id and call `self_improve_rollback` or `python3 scripts/self-improve.py rollback <run_id>`.
5. Return exact result fields: ok/error, run id, mode, scope, status, patch path, rollback path, gate status, learner eval verdict, touched files, and next monitor command.
6. If the user attempted `/ultraprompt:self-improve` in Codex, make the runtime boundary explicit: use `$ultraprompt:self-improve ...`, natural language, or the MCP self-improve tools in Codex; slash command markdown is for Claude Code.

## Validation

A successful run returns `ok: true`, a `self_improvement_run.v1` record, patch and rollback artifact paths, and either dry-run evidence, canary gate results, applied gate results, or rolled-back status. Autopilot success requires gate results with `ok: true`; failed gates must leave source restored and status `needs_evidence`.

## Output contract

Runtime note when slash command was attempted | Operation executed | Mode/scope/defaults used | Result status | Run id | Patch path | Rollback path | Gate summary | Learner eval verdict | Touched files | Post-apply monitor or next action

## Subagent delegation

Do not dispatch by default. This is a control-plane operation; use specialist review only after a run exists and the user asks to audit its evidence or patch.

## V4 aliases

This skill answers to V4 names: `self-improvement`, `self-improve-run`, `autopilot`, `learning-autopilot`. The router resolves them to `self-improve` and notes the alias in its response.
