---
name: "build"
description: "**DEFAULT for WRITING NEW CODE — minimum-diff implementation with explicit tests + claim-check before declaring success: feature-scoped implementation with files-changed, tests-added, validation-runs, and a claim-check result; dispatches to the ultraprompt:builder agent for multi-file scope and stays inline for single-function tweaks.** Different from /refactor (behavior-preserving cleanup — no new feature), /migrate (intentional breaking change with migration plan), anthropic-skills:frontend-studio (UI design artifact, not code), anthropic-skills:plan-mode (plans, not implementations). Triggers: 'build this, implement <feature>, write the code for <X>, scaffold this, add a function that <Y>, create the feature, make a new component'."
when_to_use: "Use when the user has specified a feature or user story and wants implementation. Do not use for open-ended module improvement (use refactor or technical-debt-triage). Do not use for bug fixes (use debug)."
argument-hint: "[feature|issue|user story|acceptance criteria]"
tier: "core"
aliases: ["feature-build"]
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Build

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:builder`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

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
2. Identify integration points, public API impact, data flow, and error handling.
3. Decide dispatch: if scope is multi-file or introduces a new public surface, dispatch `ultraprompt:builder` per `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md`. Stay inline for single-function tweaks.
4. Sketch the smallest coherent slice. Confirm scope before implementing if ambiguous.
5. Implement, matching neighboring conventions. No drive-by refactors.
6. Add or update tests for intended behavior, boundaries, and regression risk in the same change.
7. Update docs, examples, and configs where user-facing behavior changed.
8. Validate: focused tests first, then type-check/lint, then adjacent suites.
9. **Required:** call `claim_check` (MCP `claim_check` or `/ultraprompt:claim-check`) against the draft report. Surface any failed/unresolved claims.
10. Summarize remaining assumptions and produce the ship verdict.

## Validation

Test the new behavior. Test the boundary cases (empty, max, error). Run type-check and lint. Run adjacent test suites that exercise the same code paths. Update generated docs if the project has them. **Required gate:** call `claim_check` before declaring success and reflect the result in the report. Failing `claim_check` blocks the ship verdict.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Feature Understanding
    type: section
    required: true
    evidence_rule: "none"
  - field: Design Decision
    type: section
    required: true
    evidence_rule: "rationale + alternative considered"
  - field: Files Changed
    type: section
    required: true
    evidence_rule: "per-file path + change_type + lines_added + lines_removed + reason"
  - field: Tests Added
    type: section
    required: true
    evidence_rule: "co-located test path + behavior tested + run command + result"
  - field: Docs Updated
    type: section
    required: true
    evidence_rule: "none"
  - field: Validation
    type: section
    required: true
    evidence_rule: "exact command + exit code + stdout/stderr excerpt (redacted)"
  - field: Remaining Assumptions
    type: section
    required: true
    evidence_rule: "claim + confidence + blocks_what"
  - field: Claim-check result
    type: section
    required: true
    evidence_rule: "claim_check called, passed/failed/unresolved lists"
```

Feature Understanding | Design Decision (if non-obvious) | Files Changed | Tests Added | Docs Updated | Validation | Claim-check result (required: passed/failed/unresolved) | Remaining Assumptions | Ship verdict (ready | ready-with-followups | needs-rework)

## Subagent delegation

Default: dispatch `ultraprompt:builder` when scope is multi-file or introduces a new public surface; stay inline for single-function tweaks (override condition per `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md`). Use `scout` to locate extension points in unfamiliar code. Use `reviewer` with focus=architecture for design-sensitive changes. Use `test-strategist` before finalizing if test design isn't obvious.

## V4 aliases

This skill answers to V4 names: `feature-build`. The router resolves them to `build` and notes the alias in its response.
