---
name: "feature-completeness"
description: "**DEFAULT for AUDITOR-ONLY single-feature completeness check (when you already know which feature and do not want orchestration): structured completeness audit for one feature with confirmed/likely/missing controls and file:line evidence; no cross-feature orchestration.** Different from /gap-analysis (orchestrates this auditor + wiring-gap-inspector — use that for cross-cutting feature gaps), /repo-review (whole repo), /test-gap-analysis (missing tests only). Triggers: 'is <feature> complete, audit <feature> for completeness, does <feature> handle <case>'."
when_to_use: "When the user names ONE feature, workflow, or user journey and wants end-to-end completeness verified. Triggers on 'is X complete', 'audit feature Y', 'does workflow Z work end-to-end', 'find missing pieces of W'."
argument-hint: "<feature name or workflow description>"
tier: "core"
aliases: ["feature-audit", "is-this-complete", "e2e-audit"]
output_style: "concise-review"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Feature Completeness Audit

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:feature-completeness-auditor` (focus derived from `$ARGUMENTS`). See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

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

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `concise-review` style.

```yaml
schema:
  - field: Feature surface map
    type: section
    required: true
    evidence_rule: "none"
  - field: Confirmed gaps
    type: section
    required: true
    evidence_rule: "none"
  - field: Likely gaps
    type: section
    required: true
    evidence_rule: "none"
  - field: Missing tests for the feature
    type: section
    required: true
    evidence_rule: "test name + run command + result"
  - field: Likely user impact
    type: section
    required: true
    evidence_rule: "none"
  - field: Recommended next steps ordered by dependency
    type: section
    required: true
    evidence_rule: "package + version + source"
  - field: Validation commands
    type: section
    required: true
    evidence_rule: "exact commands run + exit codes + stdout/stderr excerpts"
```

Feature surface map | Confirmed gaps (with file:line evidence) | Likely gaps (with verification) | Missing tests for the feature | Likely user impact | Recommended next steps ordered by dependency | Validation commands

## Subagent delegation

Default: dispatch feature-completeness-auditor with focus from $ARGUMENTS. For 3+ gaps found, recommend dispatching gap-analysis-lead next. For test-coverage gaps specifically, recommend dispatching test-strategist.

## V4 aliases

This skill answers to V4 names: `feature-audit`, `is-this-complete`, `e2e-audit`. The router resolves them to `feature-completeness` and notes the alias in its response.
