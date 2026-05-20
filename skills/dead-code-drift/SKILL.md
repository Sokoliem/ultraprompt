---
name: "dead-code-drift"
description: "When user says 'find dead code / what's stale / unused exports / clean up the repo / find drift / what's deprecated / what's safe to delete / orphaned utilities / find duplicates' — produces a structured drift_findings list with safe-to-remove labels (yes/likely/needs_review/no) and migration plans. DEFAULT for cleanup audits. Different from refactor (applies changes) — dead-code-drift produces the report; user/refactor applies."
when_to_use: "When the user wants stale/dead/duplicate code identified with safe-to-remove labels."
argument-hint: "[optional: subdirectory or module to scope the audit]"
tier: "core"
aliases: ["cleanup-audit", "find-stale", "drift-hunt"]
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Dead Code & Drift Audit

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:dead-code-and-drift-hunter`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Panel escalation (V8)

Deep-budget or high-consequence versions of this lane can escalate to: `repo-completeness-panel`. Preferred: `repo-completeness-panel`. Use panel escalation for independent specialist breadth; keep the default path lighter for ordinary requests.

## Distinctive judgment

Dead-code-drift finds and labels stale code; refactor applies cleanup; reviewer evaluates code quality. Use this when planning cleanup before applying it.

## First signals to inspect

- User asks 'what can I delete'.
- User suspects the repo has accumulated cruft.
- User is preparing for major refactor and wants drift baseline.

## Failure modes specific to this lane

- Recommending deletion of dynamically loaded code.
- Missing generated files committed in error.
- Flagging plugin extension points as orphans.
- Producing recommendations without safe-to-remove confidence.

## Workflow

1. Dispatch dead-code-and-drift-hunter with optional scope from $ARGUMENTS.
2. Auditor produces drift_findings with safe-to-remove labels.
3. Synthesize: summary by safe-to-remove distribution.
4. Highlight quick wins (label=yes, low risk).
5. After synthesis, persist findings to the gap ledger via the `gap_ledger_write` MCP tool: ONE call per gap with required fields (repo, title, category, severity, confidence, evidence, recommended_fix). Auto-skip if --no-ledger argument supplied. Print the gap IDs assigned (e.g., GAP-celestial-0042) for user reference. Before writing, optionally call `gap_ledger_query` with the same repo to detect duplicates from prior sessions — if a similar gap exists, update its evidence rather than create new.
6. Flag needs_review items for human decision.

## Validation

Every drift finding must show evidence (grep results or file:line). Safe-to-remove label must have explicit justification. needs_review items must explain the uncertainty.

## Output contract

Drift findings by type | Safe-to-remove distribution | Quick wins (label=yes) | Needs-review items requiring human decision | Cleanup migration plans | Validation commands

## Subagent delegation

Default: dispatch dead-code-and-drift-hunter. Followup: /ultraprompt:refactor to apply cleanups.

## V4 aliases

This skill answers to V4 names: `cleanup-audit`, `find-stale`, `drift-hunt`. The router resolves them to `dead-code-drift` and notes the alias in its response.
