---
name: "debug"
description: "**DEFAULT for ACTIVE FAILURE DIAGNOSIS — symptom → reproduction → falsifiable root cause: captured failure signature, smallest reproduction, bisection trail, root-cause hypothesis with confidence label, and same-bug-elsewhere search.** Different from /test-gap-analysis (finds missing tests, not broken behavior), /review (PR scope), /ci-repair (pipeline-shape failures: matrix, env, cache). Triggers: 'this is failing, why is X broken, reproduce the error, debug this, failing test, runtime error'."
when_to_use: "Use for concrete failures with a reproducible symptom or trace. Use `--flaky` for non-deterministic failures (handles flake-specific reasoning). Use `ci-repair` when failure is pipeline-shape (matrix, env, cache). Do not use for broad refactors or speculative cleanup."
argument-hint: "[failure|error|test name|symptom|--flaky]"
tier: "core"
aliases: ["debug-fix", "flake-hunter"]
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Debug

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:debugger`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

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

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Symptom
    type: section
    required: true
    evidence_rule: "none"
  - field: Reproduction
    type: section
    required: true
    evidence_rule: "exact command + observed output"
  - field: Root cause
    type: section
    required: true
    evidence_rule: "file:line + minimal reproduction + falsifiable hypothesis"
  - field: Same-bug-elsewhere check
    type: section
    required: true
    evidence_rule: "none"
  - field: Fix Summary
    type: section
    required: true
    evidence_rule: "files modified + scope justification"
  - field: Regression Test Added
    type: section
    required: true
    evidence_rule: "test name + command + before/after result"
  - field: Validation Run
    type: section
    required: true
    evidence_rule: "exact commands run + exit codes + stdout/stderr excerpts"
  - field: Remaining Risks
    type: section
    required: true
    evidence_rule: "named risk + likelihood + impact"
```

Symptom | Reproduction | Root cause (with evidence) | Same-bug-elsewhere check | Fix Summary (files, why localized) | Regression Test Added | Validation Run (commands + results, including stabilization runs for flakes) | Remaining Risks

## Subagent delegation

For unfamiliar code paths, dispatch `scout` first. For competing root-cause hypotheses, invoke `panel-run debug-triangulate`. For test design after the fix, dispatch `test-strategist`.

## V4 aliases

This skill answers to V4 names: `debug-fix`, `flake-hunter`. The router resolves them to `debug` and notes the alias in its response.
