---
name: "refactor"
description: "When user says 'refactor X / clean up Y / improve the structure of / extract this / consolidate / simplify / restructure this code / improve readability without changing behavior' — apply behavior-preserving improvements with tests as the safety net. DEFAULT for refactoring tasks. Different from /build (writes new code) and /migrate (intentional behavior change)."
when_to_use: "Use for behavior-preserving cleanup. Use `--types` for type-strengthening focus. Do not use for new features (use build). Do not use for bug fixes (use debug). If behavior change is required to fix a bug, use debug and call out the behavior change."
argument-hint: "[path|module|function|--types]"
tier: "core"
aliases: ["refactor-hardening", "types-strengthen"]
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Refactor

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Inline execution policy (V8)

Prefer main-thread execution for the core workflow because the main thread must preserve local behavior and coordinate edits directly; dispatch only bounded discovery, architecture critique, or test strategy sidecars. Use subagents only for bounded discovery, critique, or test-strategy sidecars when that does not block the immediate implementation path.

## Distinctive judgment

Behavior preservation is the core invariant. Tests that pass before must pass after, with the same assertions. If a test would have failed before but the refactor would make it pass, that's a behavior change disguised as a refactor. Strengthen types only when the strengthened type accurately reflects current behavior.

## First signals to inspect

- Test suite covering the refactor target (the safety net)
- Public API surface (don't break it without explicit deprecation)
- Hot paths or perf-sensitive code (refactor can introduce regression)
- Type definitions: are they accurate or aspirational?
- Generated code or codegen consumers

## Failure modes specific to this lane

- Behavior change disguised as 'cleanup' (changes default values, error messages, side effects)
- Type strengthening that breaks downstream callers (Optional removed when callers pass undefined)
- DRY violation: extracting a helper that loses important context
- Renaming a public export without an alias or deprecation
- Refactoring untested code without first adding characterization tests

## Workflow

1. Identify the refactor target and its observable behavior contract.
2. Confirm test coverage of the target. If thin, add characterization tests first.
3. Plan the refactor as a sequence of small steps, each leaving the suite green.
4. Apply changes. Run tests after each meaningful step.
5. If `--types`: strengthen types only where the new type matches actual behavior. Don't tighten types ahead of behavior.
6. Re-review the diff. Confirm no behavior change beyond the stated intent.
7. Validate.

## Validation

Full test suite (or scoped suite if monorepo). Type-check. If perf-sensitive, run benchmark before and after. Diff observable outputs (snapshot tests, golden files) and confirm equivalence.

## Output contract

Refactor Target | Behavior Invariants Preserved | Steps Taken | Tests Status | Type-Check Status | Diff Summary | What Changed Observably (should be 'nothing')

## Subagent delegation

Use `reviewer` with focus=architecture for structural refactors. Use `test-strategist` if the target lacks coverage.

## V4 aliases

This skill answers to V4 names: `refactor-hardening`, `types-strengthen`. The router resolves them to `refactor` and notes the alias in its response.
