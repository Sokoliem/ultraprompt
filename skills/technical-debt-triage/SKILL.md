---
name: "technical-debt-triage"
description: "**DEFAULT for tech debt prioritization — produces ranked tech debt list with impact + effort + recommended sequencing.**"
when_to_use: "Manual-only. Invoke for maintenance-backlog work: debt inventory, modernization sequencing, 30/60/90-day plans, contributor friction, build/test speed audit. Consolidates V4's tech-debt-triage, codebase-health, developer-experience-audit, build-test-optimizer."
argument-hint: "[scope|focus: debt|dx|build-speed|health]"
tier: "specialist"
aliases: ["codebase-health", "developer-experience-audit", "build-test-optimizer"]
disable-model-invocation: true
output_style: "concise-review"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Technical Debt Triage

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

Maintenance backlog is shaped like an inventory + sequencing problem. The inventory is what's broken or rotting; the sequencing is what to fix first given finite engineering time. Risk × leverage × cost. DX friction and build speed are debt with compounding interest: every day of delay costs more time per contributor.

## First signals to inspect

- Recent pain points: PRs that took unusually long, recent incidents, contributor complaints
- Build/test/lint times locally and in CI
- Test flakiness rate
- Onboarding time for new contributors
- Areas with high churn + high bug rate (correlation often = debt)
- Versions: language, framework, deps — how stale?
- Tooling: linter, formatter, type checker — config drift, ignored rules

## Failure modes specific to this lane

- Listing every imperfection without prioritizing (overwhelming, no action taken)
- Optimizing for what's easy to fix rather than what hurts most
- Recommending modernization for its own sake (latest framework version)
- Ignoring DX/build-speed because it's not 'real' code
- 30/60/90 plan with no measurement (can't tell if it worked)

## Workflow

1. Identify scope and focus (debt / DX / build-speed / health).
2. Inventory: enumerate the items. Concrete, file-level when possible.
3. Score each: risk (likelihood × impact), leverage (how much friction it removes), cost (engineering time).
4. Sequence into 30/60/90 buckets. Highest risk × leverage / cost first.
5. For build/test speed: profile the current pipeline. Identify the dominant cost.
6. For DX: enumerate friction points concretely (this command takes 3 min, that error is unclear).
7. Produce the plan with measurable targets per bucket.
8. Stay read-only; this skill produces a plan, not the fixes.

## Validation

No code changes. Validate by referring to recent incidents and contributor pain that confirm the items in the inventory.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `concise-review` style.

```yaml
schema:
  - field: Scope + Focus
    type: section
    required: true
    evidence_rule: "none"
  - field: Inventory
    type: section
    required: true
    evidence_rule: "none"
  - field: Risk × Leverage / Cost Scoring
    type: section
    required: true
    evidence_rule: "named risk + likelihood + impact"
  - field: 30/60/90 Sequenced Plan
    type: section
    required: true
    evidence_rule: "none"
  - field: Measurement Targets per Bucket
    type: section
    required: true
    evidence_rule: "none"
  - field: Specific Build/DX Bottlenecks
    type: section
    required: true
    evidence_rule: "none"
```

Scope + Focus | Inventory (file-level when possible) | Risk × Leverage / Cost Scoring | 30/60/90 Sequenced Plan | Measurement Targets per Bucket | Specific Build/DX Bottlenecks (if applicable)

## Subagent delegation

Dispatch `auditor` with focus=infra for build pipeline depth. See `_shared/playbooks/codebase-health-signals.md`, `_shared/playbooks/developer-experience-friction-list.md`, `_shared/playbooks/build-test-optimizer-patterns.md`.

## V4 aliases

This skill answers to V4 names: `codebase-health`, `developer-experience-audit`, `build-test-optimizer`. The router resolves them to `technical-debt-triage` and notes the alias in its response.
