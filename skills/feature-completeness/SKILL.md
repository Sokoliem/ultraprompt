---
name: "feature-completeness"
description: "When user says 'is feature X complete / audit this feature end-to-end / does this workflow actually work / find missing pieces of feature W / is the UI wired to the backend / does feature Y persist correctly' — runs end-to-end completeness audit on ONE named feature. Dispatches feature-completeness-auditor with the feature scope. Produces structured incomplete_features findings with file-level evidence, missing parts list, confidence labels, validation plan. DEFAULT for single-feature audits — wins over repo-review (whole repo) and over manual investigation because the auditor knows the layer-by-layer gap patterns."
when_to_use: "When the user names ONE feature, workflow, or user journey and wants end-to-end completeness verified. Triggers on 'is X complete', 'audit feature Y', 'does workflow Z work end-to-end', 'find missing pieces of W'."
argument-hint: "<feature name or workflow description>"
tier: "core"
aliases: ["feature-audit", "is-this-complete", "e2e-audit"]
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Feature Completeness Audit

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:feature-completeness-auditor` (focus derived from `$ARGUMENTS`). See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Panel escalation (V8)

Deep-budget or high-consequence versions of this lane can escalate to: `feature-gap-panel`. Preferred: `feature-gap-panel`. Use panel escalation for independent specialist breadth; keep the default path lighter for ordinary requests.

## Distinctive judgment

Feature-completeness is single-feature scope (UI → API → backend → DB). Repo-review is whole-repo scope. Gap-analysis is synthesis across multiple sources. Architect is design review, not implementation completeness.

## First signals to inspect

- User names a specific feature/workflow.
- User says 'does it actually work' or 'is it wired'.
- User suspects partial implementation but doesn't know where the gap is.

## Failure modes specific to this lane

- Auditing the whole repo when one feature was named.
- Claiming the feature is complete without verifying all layers.
- Missing the database layer or the auth layer.
- Not producing structured incomplete_features entries.

## Workflow

1. Verify the user named a specific feature; if not, ask before dispatching.
2. Dispatch feature-completeness-auditor with the feature name as focus.
3. If repo-cartographer output is available in context, pass it; otherwise the auditor builds a mini-map for the feature.
4. After synthesis, persist findings to the gap ledger via the `gap_ledger_write` MCP tool: ONE call per gap with required fields (repo, title, category, severity, confidence, evidence, recommended_fix). Auto-skip if --no-ledger argument supplied. Print the gap IDs assigned (e.g., GAP-celestial-0042) for user reference. Before writing, optionally call `gap_ledger_query` with the same repo to detect duplicates from prior sessions — if a similar gap exists, update its evidence rather than create new.
5. On completion, synthesize findings; if 3+ gaps found, recommend dispatching gap-analysis-lead for prioritization.

## Validation

Auditor must trace at least: UI entry, API client call, backend route, handler, service, data persistence, response render. Every layer's presence/absence/wiring must have file:line evidence. confidence labels mandatory.

## Output contract

Feature surface map | Confirmed gaps (with file:line evidence) | Likely gaps (with verification) | Missing tests for the feature | Likely user impact | Recommended next steps ordered by dependency | Validation commands

## Subagent delegation

Default: dispatch feature-completeness-auditor with focus from $ARGUMENTS. For 3+ gaps found, recommend dispatching gap-analysis-lead next. For test-coverage gaps specifically, recommend dispatching test-strategist.

## V4 aliases

This skill answers to V4 names: `feature-audit`, `is-this-complete`, `e2e-audit`. The router resolves them to `feature-completeness` and notes the alias in its response.
