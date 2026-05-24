---
name: "migrate"
description: "**DEFAULT for INTENTIONAL BREAKING CHANGE with explicit migration plan (data, API, or framework): phased migration with pre/action/validate/rollback per step and consumer notification plan.** Different from /refactor (NO behavior change), /build (no migration of existing state/API), /database-review (reviews DB changes but does not own the sequence). Triggers: 'migrate <X> to <Y>, breaking change rollout, deprecate <thing>, upgrade <framework>'."
when_to_use: "Use for migrations that span multiple steps and require rollback planning. Use `--deps` for dependency upgrade migrations specifically. Do not use for one-shot config changes (just edit them). Do not use for API contract changes (use api-contract for the design; use migrate for the rollout)."
argument-hint: "[migration scope|--deps]"
tier: "core"
aliases: ["migration-plan", "deps-upgrade"]
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Migrate

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

Migrations must be reversible at each step until the point of no return, which should be explicit. Forward-compatible (new code can read old data) before backward-incompatible (new code only reads new data). For deps: identify breaking changes, then sequence by risk: leaf deps first, framework deps last.

## First signals to inspect

- Current state: schema, config, API version, dependency lockfile
- Target state: what does 'done' look like?
- Concurrent traffic: is the system live? Multiple replicas?
- Backwards-compat window: how long do old + new coexist?
- Rollback signals: what would tell us to roll back? How fast can we?
- For deps: changelog of upgrade target; breaking changes section

## Failure modes specific to this lane

- Migration that requires downtime when the system can't tolerate it
- Forward-incompatible step deployed before all replicas are upgraded (mixed-version traffic breaks)
- Schema migration that locks tables for hours on production data size
- Dep upgrade that pulls in transitive breakage not visible from the direct upgrade
- No rollback plan past a certain step (and not flagging that step as point of no return)
- Migration plan written for the test environment data scale, not production

## Workflow

1. Define current state, target state, and 'done' criteria.
2. Identify constraints: downtime tolerance, replica count, data scale, rollback SLO.
3. Sequence steps: each step is forward-compatible until the explicit point of no return.
4. For each step: pre-conditions, action, validation, rollback procedure.
5. Identify and flag the point-of-no-return step (e.g., dropping the old column).
6. For deps: dry-run the upgrade in CI; check transitive breakage; sequence leaf-first.
7. Document the plan as a checklist with expected duration per step.

## Validation

Dry-run on a copy of production-scale data where possible. For schema migrations, time the migration on production-scale dataset. For deps, run the full test matrix. After each step, validate observable behavior matches expectations.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Current State
    type: section
    required: true
    evidence_rule: "none"
  - field: Target State
    type: section
    required: true
    evidence_rule: "none"
  - field: Constraints
    type: section
    required: true
    evidence_rule: "none"
  - field: Sequenced Steps
    type: section
    required: true
    evidence_rule: "none"
  - field: Point of No Return
    type: section
    required: true
    evidence_rule: "none"
  - field: Estimated Duration
    type: section
    required: true
    evidence_rule: "none"
  - field: Validation Plan
    type: section
    required: true
    evidence_rule: "exact commands run + exit codes + stdout/stderr excerpts"
  - field: Rollback Plan
    type: section
    required: true
    evidence_rule: "none"
```

Current State | Target State | Constraints | Sequenced Steps (each with pre/action/validate/rollback) | Point of No Return | Estimated Duration | Validation Plan | Rollback Plan

## Subagent delegation

Use `auditor` with focus=db for schema migrations. Use `auditor` with focus=infra for cross-environment rollout. Use `panel-run migration-assess` for cross-surface migrations.

## V4 aliases

This skill answers to V4 names: `migration-plan`, `deps-upgrade`. The router resolves them to `migrate` and notes the alias in its response.
