---
name: "test-harden"
description: "When user says 'write tests for X / harden test coverage / add tests / improve test suite / implement test plan / write missing tests' — apply test code per a test plan (uses test-strategist output if provided). DEFAULT for actually writing test code. Different from /test-gap-analysis (finds gaps) and /test-strategist (designs plan)."
when_to_use: "Use when confidence is low, coverage is shallow, regressions are likely, or a change needs durable behavioral tests. Do not use when the failure is concrete (use debug); do not use when the change is a feature delivery (use build)."
argument-hint: "[path|module|behavior|changed feature]"
tier: "core"
aliases: ["test-harden"]
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Test Harden

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:test-strategist`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Coverage percentage is a weak signal. Test value comes from: (1) catching regressions in observable behavior, (2) exercising boundaries (empty, max, error, concurrent), (3) pinning contracts that other code relies on. A 95%-covered module with shallow tests is weaker than an 80%-covered module with sharp tests.

## First signals to inspect

- Existing test suite shape: unit, integration, e2e ratios; framework conventions
- Behavior contracts that are public but untested
- Recent bugs in the area (git log of fixes; test should have caught it)
- Boundaries: what happens at 0, 1, max, with concurrent calls, with errors
- Mocks and fixtures: are they accurate or rotting?

## Failure modes specific to this lane

- Adding tests that mirror the implementation (change-detector tests)
- Mocking the thing under test
- Testing implementation details rather than observable behavior
- Adding 'happy path' tests where boundaries are the actual risk
- Increasing coverage % without increasing confidence

## Workflow

1. Identify behavior contracts that lack tests (or have shallow tests).
2. For each, write the test that would have caught the bug (real or hypothetical).
3. Cover boundaries: empty, max, error, concurrent, malformed input.
4. Pin contracts that other code relies on (snapshot APIs, golden files).
5. Remove or replace change-detector tests that don't add confidence.
6. Validate: run the new tests; mutation-test the area if tooling is available.

## Validation

Run the new tests. Run the broader suite to confirm nothing else broke. If mutation testing is available (Stryker, mutmut, cargo-mutants), confirm the new tests kill mutants in the changed code.

## Output contract

Coverage Target | Behavior Contracts Tested | Boundary Cases Added | Removed Change-Detector Tests | Mutation-Test Result (if run) | Remaining Gaps

## Subagent delegation

Use `test-strategist` to design test plans for unfamiliar areas.

## V4 aliases

This skill answers to V4 names: `test-harden`. The router resolves them to `test-harden` and notes the alias in its response.
