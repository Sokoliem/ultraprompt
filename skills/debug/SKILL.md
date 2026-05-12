---
name: "debug"
description: "When user says 'this is failing / why is X broken / reproduce the error / debug this / what's causing the bug / failing test / runtime error / unexpected output / why does this crash' — runs the debugger discipline of failure-signature capture, smallest reproduction, bisection, confirmed root cause hypothesis with confidence label. DEFAULT for active debugging. Different from /test-gap-analysis (finds missing tests) and /review (PR-scope review)."
when_to_use: "Use for concrete failures with a reproducible symptom or trace. Use `--flaky` for non-deterministic failures (handles flake-specific reasoning). Use `ci-repair` when failure is pipeline-shape (matrix, env, cache). Do not use for broad refactors or speculative cleanup."
argument-hint: "[failure|error|test name|symptom|--flaky]"
tier: "core"
aliases: ["debug-fix", "flake-hunter"]
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Debug

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:debugger`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Panel escalation (V8)

Deep-budget or high-consequence versions of this lane can escalate to: `incident-response-panel`. Preferred: `incident-response-panel`. Use panel escalation for independent specialist breadth; keep the default path lighter for ordinary requests.

## Distinctive judgment

Symptom-to-root-cause traversal. The failing assertion is the symptom, not the cause. Trace through call sites, data flow, recent changes, invariants, and shared state. For non-deterministic failures, the variable is usually time, randomness, order dependence, network, or shared state — not 'bad luck'. Retry-masking is not repair.

## First signals to inspect

- Exact error message, stack trace, test name, and reproduction command
- git log on touched files since last known-good (last passing CI, last release)
- Recently merged changes near the failure path (git log --oneline --decorate -n 30)
- For flakes: timing assumptions, shared state, parallelism config, network mocks, fixture order
- Adjacent passing tests that exercise nearby behavior

## Failure modes specific to this lane

- Fixing the assertion rather than the cause (changing expected values or adding tolerance)
- Adding retry/sleep/timeout instead of finding the race
- Catching an exception that should propagate
- Fixing one path while leaving the same bug elsewhere (search for the pattern)
- Quarantining a flake without filing a follow-up to investigate the root cause

## Workflow

1. Reproduce or localize the failure. Capture exact command and output.
2. For `--flaky`: characterize the non-determinism (frequency, conditions). Identify the variable.
3. Trace from symptom backward: failing assertion → state at failure → input/conditions → root cause.
4. Identify the narrowest correct fix. Reject 'works around it' fixes.
5. Search for the same bug elsewhere by pattern.
6. Apply fix. Add or update a regression test that would have caught it.
7. Validate the focused failure first, then adjacent suites.
8. Re-review the final diff for unintended behavior changes.

## Validation

Run the originally-failing test/command first. Then run the broader suite that contains it. For flakes, run the failing test ≥10× to confirm stabilization (or document why that's not feasible).

## Output contract

Symptom | Reproduction | Root cause (with evidence) | Same-bug-elsewhere check | Fix Summary (files, why localized) | Regression Test Added | Validation Run (commands + results, including stabilization runs for flakes) | Remaining Risks

## Subagent delegation

For unfamiliar code paths, dispatch `scout` first. For competing root-cause hypotheses, invoke `panel-run debug-triangulate`. For test design after the fix, dispatch `test-strategist`.

## V4 aliases

This skill answers to V4 names: `debug-fix`, `flake-hunter`. The router resolves them to `debug` and notes the alias in its response.
