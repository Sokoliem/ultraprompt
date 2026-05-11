---
name: "api-contract"
description: "When user says 'API contract review / OpenAPI review / API design review / RESTful contract / GraphQL schema review / API versioning' — dispatches reviewer/integration-contract-reviewer with API contract focus. DEFAULT for API contract design and review."
when_to_use: "Use for any change that affects a public surface: API endpoints, schemas, CLI flags, config formats, events, package exports, wire formats. Use when planning a deprecation. Do not use for purely internal refactors with no external surface (use refactor)."
argument-hint: "[surface|change description|consumer]"
tier: "core"
aliases: ["api-contract", "api-deprecation"]
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# API Contract

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:reviewer` (focus: `contract`). See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Compatibility is asymmetric: producers can extend (add fields, add methods, add optional flags) more freely than they can change or remove. Identify what consumers depend on — including undocumented behavior — before declaring something safe to change. Deprecation is a process, not an event: announce, warn, sunset.

## First signals to inspect

- Public surface inventory: exports, endpoints, CLI flags, config keys, event names, message formats
- Versioning scheme: SemVer? CalVer? Internal stability tiers?
- Existing deprecation policy and mechanisms (warnings, deprecation headers, version skew tolerance)
- Consumer signals: who consumes this surface, how, with what expectations
- Tests that pin the contract (contract tests, golden files, snapshot tests)
- Release notes/changelog conventions for breaking changes

## Failure modes specific to this lane

- Treating undocumented behavior as 'not part of the contract' when consumers rely on it (Hyrum's Law)
- Removing a deprecated surface before users have migrated
- Adding a 'compatible' field that breaks consumers using strict schema validation
- Changing default values silently (breaks consumers who didn't set the value explicitly)
- Not bumping major version when behavior changes
- Inventing a deprecation timeline without consulting affected consumers

## Workflow

1. Identify the public surface affected by the proposed change.
2. Classify the change: additive (new field/method/flag), modifying (changes existing behavior), removing.
3. Identify consumers and how they use the surface (search for callers; check changelog feedback; ask about telemetry).
4. For modifying/removing: design the deprecation path. Announce → warn → sunset.
5. Update or add contract tests that pin the new behavior.
6. Document the change in changelog/release notes following project conventions.
7. If it's a breaking change, confirm version bump and migration guide.

## Validation

Contract tests pass on both old and new behavior during deprecation window. Schema validation tools (json-schema, OpenAPI lint, GraphQL diff) confirm compatibility classification. Consumer integration tests where available.

## Output contract

Surface Affected | Change Classification (additive/modifying/removing) | Consumer Impact Analysis | Deprecation Path (if not additive) | Contract Tests Added/Updated | Changelog/Release Note Entry | Version Bump Recommendation | Migration Guidance for Consumers

## Subagent delegation

Use `reviewer` with focus=contract for a compatibility second opinion. Use `_shared/playbooks/contract-test-patterns.md` for contract test design.

## V4 aliases

This skill answers to V4 names: `api-contract`, `api-deprecation`. The router resolves them to `api-contract` and notes the alias in its response.
