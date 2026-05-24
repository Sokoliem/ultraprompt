---
name: "state-machine-review"
description: "**DEFAULT for state-machine design and review — dispatches reviewer with state-machine focus.**"
when_to_use: "Manual-only. Invoke for state-machine, FSM, reducer, or protocol-lifecycle review. Different cognitive model from architecture review (which handles boundaries) and concurrency (which handles timing). For lock/race/async issues, see `_shared/playbooks/concurrency-patterns.md`."
argument-hint: "[state machine|reducer|protocol]"
tier: "specialist"
disable-model-invocation: true
output_style: "concise-review"
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# State Machine Review

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:reviewer` (focus: `code`). See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Explicit state machines are easier to reason about than implicit ones (booleans + flags). The transition table tells you what's possible; the invariants tell you what should be impossible. Impossible states should be unrepresentable (type system) or unreachable (validation). Most state-machine bugs are 'this transition shouldn't have been allowed from this state'.

## First signals to inspect

- Is the state machine explicit (FSM library, state pattern, reducer) or implicit (mix of booleans)?
- States: enumerated? Documented?
- Transitions: when does each fire? Which states are allowed pre-conditions?
- Invariants: what must always be true regardless of state?
- Persistence: how is state stored? Migration path when state set changes?
- Concurrent transitions: can two transitions race?

## Failure modes specific to this lane

- Implicit state machine: combinations of booleans creating impossible states (`isLoading && isError && !hasData`)
- Transition allowed from a state where it shouldn't be (no guard)
- State set extended without updating persistence migration
- Race between two transitions on the same entity
- State reached but no transition out (stuck state)
- Invariant assumed but not enforced

## Workflow

1. Identify the state machine. If implicit, make it explicit (enumerate states from code).
2. Build the transition table: state × event → new state | rejected.
3. Identify invariants and confirm they're enforced (type, validation, or assertion).
4. Look for impossible states and unreachable states.
5. Look for stuck states (no transition out).
6. Identify concurrent transition risks; require atomic transitions where needed.
7. Apply fixes: tighten guards, make impossible states unrepresentable, add invariant checks.
8. Add tests covering transition table edges and invariants.

## Validation

Property-based tests on the transition table where feasible. Tests for each transition's pre-condition and post-condition. Tests for stuck-state detection. For persistence: test migration of stored state across version changes.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `concise-review` style.

```yaml
schema:
  - field: State Machine
    type: section
    required: true
    evidence_rule: "none"
  - field: Transition Table
    type: section
    required: true
    evidence_rule: "none"
  - field: Invariants
    type: section
    required: true
    evidence_rule: "stated as boolean; explain what falsifies it"
  - field: Impossible States Found
    type: section
    required: true
    evidence_rule: "none"
  - field: Stuck States Found
    type: section
    required: true
    evidence_rule: "none"
  - field: Concurrent Transition Risks
    type: section
    required: true
    evidence_rule: "named risk + likelihood + impact"
  - field: Fixes Applied
    type: section
    required: true
    evidence_rule: "none"
  - field: Tests Added
    type: section
    required: true
    evidence_rule: "test name + run command + result"
```

State Machine | Transition Table | Invariants | Impossible States Found | Stuck States Found | Concurrent Transition Risks | Fixes Applied | Tests Added

## Subagent delegation

Dispatch `reviewer` with focus=architecture for boundary questions. See `_shared/playbooks/concurrency-patterns.md` for concurrent transition concerns.
