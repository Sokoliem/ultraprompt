---
name: "contract-test-generate"
description: "**DEFAULT for contract-test generation — dispatches test-strategist + test-harden with contract focus.**"
when_to_use: "Manual-only. Invoke when a boundary needs contract-test coverage to prevent silent breakage. For API contract design or deprecation, use core `api-contract`."
argument-hint: "[boundary|consumer|surface]"
tier: "specialist"
disable-model-invocation: true
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Contract Test Generate

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

Contract tests pin the surface from the consumer's perspective. They differ from unit tests (which test the producer's internal logic) and integration tests (which test the live integration). A contract test should fail when the producer changes the surface in a way that breaks consumers — even if the producer's own tests still pass.

## First signals to inspect

- Boundary type: REST API, GraphQL, gRPC, message queue, CLI, file format, package export
- Consumer list: who depends on this surface?
- Existing contract tests or schema files (OpenAPI, GraphQL SDL, JSON Schema, Protobuf)
- Consumer expectations not captured in schema (ordering, default values, error formats)

## Failure modes specific to this lane

- Contract test that's actually an integration test (calls live producer; not a contract pin)
- Schema-only contract that misses behavioral expectations (ordering, error format)
- Contract test owned by producer (goalpost-moving when producer changes the surface)
- Contract for one consumer applied as universal (other consumers have different needs)

## Workflow

1. Identify the boundary and its consumers.
2. Capture consumer expectations as concrete cases (request → expected response shape).
3. Generate tests using a contract-test framework (Pact, Spring Cloud Contract, custom).
4. Run tests against the producer to confirm current behavior matches.
5. Wire into producer's CI so producer-side changes that break consumers fail.
6. Document the contract for future consumer onboarding.

## Validation

Run the new contract tests against current producer (should pass). Modify producer in a known-breaking way (in a branch); confirm contract test fails. Revert.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Boundary
    type: section
    required: true
    evidence_rule: "none"
  - field: Consumers Captured
    type: section
    required: true
    evidence_rule: "none"
  - field: Contract Cases
    type: section
    required: true
    evidence_rule: "consumer + version + breaking-change classification"
  - field: Framework + Test Files
    type: section
    required: true
    evidence_rule: "test name + run command + result"
  - field: CI Wiring
    type: section
    required: true
    evidence_rule: "none"
  - field: Documentation
    type: section
    required: true
    evidence_rule: "none"
```

Boundary | Consumers Captured | Contract Cases (request → expected response/behavior) | Framework + Test Files | CI Wiring | Documentation

## Subagent delegation

Dispatch `reviewer` with focus=contract for second perspective. See `_shared/playbooks/contract-test-patterns.md`.
