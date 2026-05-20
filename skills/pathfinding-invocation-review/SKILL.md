---
name: "pathfinding-invocation-review"
description: "When user says 'pathfinding review / invocation behavior / skill auto-fire / agent dispatch telemetry / routing effectiveness / why did Explore run / strengthen automated skill invocation / audit pathfinder telemetry' - dispatches invocation-reliability-auditor. DEFAULT for Ultraprompt runtime routing, pathfinder, skill activation, agent dispatch, Explore fallback, legacy-prefix, and telemetry effectiveness investigations."
when_to_use: "Use when the user asks whether Ultraprompt is actually being invoked effectively by Codex or Claude Code, asks to read telemetry, wants to reduce Explore fallback, wants routing/pathfinder behavior hardened, or needs release-gate evidence that catalog richness translates into runtime behavior."
argument-hint: "[telemetry window|runtime|focus]"
tier: "core"
aliases: ["invocation-review", "pathfinder-review", "routing-telemetry-review", "skill-activation-review"]
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Pathfinding + Invocation Review

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:invocation-reliability-auditor` (focus: `routing-telemetry`) for the analysis phase only. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Panel escalation (V8)

Deep-budget or high-consequence versions of this lane can escalate to: `cognitive-governance-panel`. Preferred: `cognitive-governance-panel`. Use panel escalation for independent specialist breadth; keep the default path lighter for ordinary requests.

## Distinctive judgment

Catalog coverage is not runtime effectiveness. A plugin can have many skills and agents while the actual sessions route to generic Explore, never auto-fire current skill names, or emit only synthetic pathfinder decisions. Review invocation telemetry as a product behavior: current vs legacy prefixes, skill activation, agent dispatch share, pathfinder real-vs-bench usage, and release gates that fail when runtime adoption regresses.

## First signals to inspect

- Live event ledgers: current `~/.claude/ultraprompt-data`, legacy `~/.claude/ultra-prompt-data`, and `~/.ultraprompt/events`.
- Agent dispatch sources: Claude project JSONL Task/Agent calls, ledger-v2 events, and dashboard feed.
- Prefix normalization: `ultraprompt:` vs `ultra-prompt:` and whether telemetry records both original and canonical names.
- Pathfinder decision sources: real user/API calls vs golden-case bench/synthetic runs.
- Activation gaps: current skills never invoked and plugin agents never dispatched over a meaningful window.
- Release gates: scorecard, doctor scripts, catalog consistency, and thresholds that should block silent routing decay.

## Failure modes specific to this lane

- Declaring routing healthy from catalog counts or generated graph alone.
- Counting legacy `ultra-prompt:*` telemetry as current without normalization labels.
- Treating pathfinder benchmark events as evidence of live user behavior.
- Ignoring generic Explore dominance when specialist agents should have been selected.
- Adding new skills without route boosts, golden cases, dispatch policies, and telemetry gates.
- Making the release scorecard pass by lowering thresholds instead of fixing invocation behavior.

## Workflow

1. Run or inspect invocation telemetry audit over the relevant window and separate current, legacy, and synthetic signals.
2. Compare skill activation, plugin-agent dispatch share, Explore share, pathfinder real decisions, and activation gaps against release thresholds.
3. Trace weak routes to source specs, boost rules, golden cases, capability graph edges, hooks, or runtime plugin/cache mismatch.
4. Apply narrow hardening: prefix normalization, route boosts, generated skill-name coverage, telemetry payload fields, or release-gate wiring.
5. Regenerate indexes/graphs after source edits and run pathfinder plus invocation telemetry validation.
6. Report remaining blockers as runtime behavior, not catalog-health issues.

## Validation

Run `python3 scripts/audit-invocation-telemetry.py --json` and, for release gating, `--enforce`. Pair it with `python3 scripts/run-pathfinder-tests.py --no-telemetry`, `python3 scripts/build-capability-graph.py --check`, and scorecard/correctness checks. A failing telemetry gate is a valid result when live usage is still below threshold.

## Output contract

Telemetry window | Skill invocation summary | Agent dispatch share + Explore share | Legacy-prefix normalization | Pathfinder real-vs-bench summary | Activation gaps | Changes applied or proposed | Release gate result | Remaining blockers

## Subagent delegation

Dispatch invocation-reliability-auditor for read-only analysis. Use build on the main thread for source/generator fixes after the audit identifies high-confidence changes.

## V4 aliases

This skill answers to V4 names: `invocation-review`, `pathfinder-review`, `routing-telemetry-review`, `skill-activation-review`. The router resolves them to `pathfinding-invocation-review` and notes the alias in its response.
