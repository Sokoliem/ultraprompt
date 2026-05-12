---
name: "build"
description: "When user says 'build this / implement X / write the code for / create the feature / make a new component / scaffold this / let's write Y / add a function that does Z' — apply minimum diff implementation with explicit tests + validation. DEFAULT for code-writing tasks. Different from /refactor (changes existing without behavior change) and /migrate (changes with explicit migration plan)."
when_to_use: "Use when the user has specified a feature or user story and wants implementation. Do not use for open-ended module improvement (use refactor or technical-debt-triage). Do not use for bug fixes (use debug)."
argument-hint: "[feature|issue|user story|acceptance criteria]"
tier: "core"
aliases: ["feature-build"]
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Build

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Inline execution policy (V8)

Prefer main-thread execution for the core workflow because the main thread owns the requested code change, edits, integration, and validation; dispatch only bounded sidecars that do not own the critical implementation path. Use subagents only for bounded discovery, critique, or test-strategy sidecars when that does not block the immediate implementation path.

## Distinctive judgment

Smallest coherent feature slice that satisfies the request. Avoid scope creep. Inspect adjacent UX/API patterns and match them. Public API impact, data flow, state management, and error handling are part of the deliverable, not afterthoughts.

## First signals to inspect

- Acceptance criteria from `$ARGUMENTS`, linked issue, or product doc
- Existing analogous features (search for similar route/component/handler)
- Public API surface affected (exports, schemas, CLI flags, events, config)
- Test patterns in adjacent code; testing framework conventions
- Documentation surfaces (README, examples, docstrings, generated docs)

## Failure modes specific to this lane

- Inventing a new pattern when an existing one would do
- Skipping tests because 'it's a small feature'
- Updating code without updating docs/examples that referenced the old behavior
- Adding a public API surface without considering deprecation/compatibility
- Implementing more than the requirement (gold-plating)

## Workflow

1. Infer requirements from `$ARGUMENTS`, issue body, docs, and adjacent code.
2. Identify integration points, public API impact, data flow, error handling.
3. Sketch the smallest coherent slice. Confirm scope before implementing if ambiguous.
4. Implement, matching neighboring conventions.
5. Add tests for intended behavior, boundaries, and regression risk.
6. Update docs, examples, configs where user-facing behavior changed.
7. Validate. Summarize remaining assumptions.

## Validation

Test the new behavior. Test the boundary cases (empty, max, error). Run type-check and lint. Run adjacent test suites that exercise the same code paths. Update generated docs if the project has them.

## Output contract

Feature Understanding | Design Decision (if non-obvious) | Files Changed | Tests Added | Docs Updated | Validation | Remaining Assumptions

## Subagent delegation

Use `scout` to locate extension points in unfamiliar code. Use `reviewer` with focus=architecture for design-sensitive changes. Use `test-strategist` before finalizing if test design isn't obvious.

## V4 aliases

This skill answers to V4 names: `feature-build`. The router resolves them to `build` and notes the alias in its response.
