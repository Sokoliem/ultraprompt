---
name: "test-gap-analysis"
description: "When user says 'find test gaps / where's the missing coverage / risk-weighted test plan / what should we test / find untested paths / regression coverage review / what edge cases am I missing' — finds critical behavior with weak/missing validation. Risk-weights findings (critical for auth/payment/data-deletion lanes; medium for UI rendering; low for admin). DEFAULT for test-gap detection. Different from test-harden (designs new tests) — test-gap-analysis specifically finds the gaps."
when_to_use: "When the user wants risk-weighted analysis of where existing tests are missing, weak, or only happy-path. Triggers on test-coverage prep, pre-release confidence checks, post-feature hardening passes, audit asks like 'where are we under-tested', or stress tests against the test suite itself."
argument-hint: "[optional: specific feature, lane, or risk area]"
tier: "core"
aliases: ["test-coverage-audit", "find-test-gaps", "untested-paths"]
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Test Gap Analysis

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:test-gap-analyst`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Panel escalation (V8)

Deep-budget or high-consequence versions of this lane can escalate to: `feature-gap-panel`. Preferred: `feature-gap-panel`. Use panel escalation for independent specialist breadth; keep the default path lighter for ordinary requests.

## Distinctive judgment

Test-gap-analysis finds risky behavior with weak coverage; test-harden designs the missing tests; review evaluates existing tests; debugger investigates failing tests. Use this when you want a prioritized list of what to test next.

## First signals to inspect

- User asks 'where are we under-tested'.
- User is preparing for release and wants confidence check.
- User just shipped a feature and wants to harden coverage.

## Failure modes specific to this lane

- Producing generic '100% coverage' recommendations.
- Flagging admin pages as critical when auth flows are uncovered.
- Missing error paths and edge cases.
- Listing existing tests without identifying gaps.

## Workflow

1. Dispatch test-gap-analyst with the focus area from $ARGUMENTS.
2. Auditor produces risk-weighted test_gaps entries.
3. Synthesize: top 5 critical, top 5 high, summary of medium/low.
4. For each critical/high gap, recommend specific test type (unit/integration/e2e/contract).
5. After synthesis, persist findings to the gap ledger via the `gap_ledger_write` MCP tool: ONE call per gap with required fields (repo, title, category, severity, confidence, evidence, recommended_fix). Auto-skip if --no-ledger argument supplied. Print the gap IDs assigned (e.g., GAP-celestial-0042) for user reference. Before writing, optionally call `gap_ledger_query` with the same repo to detect duplicates from prior sessions — if a similar gap exists, update its evidence rather than create new.
6. End with 'next dispatch' suggestion: test-harden to design the tests.

## Validation

Every gap must cite specific file:line for both the behavior and the absence-of-test evidence. Risk weighting must use the lane-based heuristic, not be uniform across findings.

## Output contract

Risk-weighted test gaps | Critical lanes uncovered | Existing test summary | Missing test types per gap | Suggested test cases | Validation commands

## Subagent delegation

Default: dispatch test-gap-analyst. Followup: test-harden to design and write the missing tests.

## V4 aliases

This skill answers to V4 names: `test-coverage-audit`, `find-test-gaps`, `untested-paths`. The router resolves them to `test-gap-analysis` and notes the alias in its response.
