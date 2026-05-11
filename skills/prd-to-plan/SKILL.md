---
name: "prd-to-plan"
description: "When user says 'convert this PRD to engineering plan / break down PRD for implementation / make a project plan from this PRD / split this PRD into milestones / what work is needed to ship this PRD / phase plan for PRD X' — converts a PRD into a phased implementation plan with milestones, dependencies, parallelizable work, sequencing, owner suggestions, validation gates per phase. DEFAULT for PRD → engineering handoff. Different from prd-technical (which produces the technical design): prd-to-plan takes a finished PRD and produces the build sequence."
when_to_use: "When a PRD is approved and needs to be broken into engineering work with sequencing and dependencies. Not for drafting the PRD itself; that's prd-standard/technical/etc."
argument-hint: "<path to PRD or PRD topic>"
tier: "core"
aliases: ["prd-breakdown", "implementation-plan", "engineering-plan"]
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# PRD to Implementation Plan

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:principal-pm`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

PRD-to-plan converts approved PRD to implementation plan; prd-standard creates the PRD; prd-technical adds technical design. Use in sequence: prd-standard → (optional prd-technical) → prd-to-plan.

## First signals to inspect

- User has an approved PRD and wants to start engineering.
- User asks for milestones, phases, or build sequence.
- User wants to identify parallel vs sequential work.

## Failure modes specific to this lane

- Producing implementation plan without reading the source PRD.
- Missing dependencies (work that must happen before other work).
- No validation gates between phases.
- Generic 'sprint 1 / sprint 2' breakdown without dependency analysis.

## Workflow

1. Read the source PRD (file path from $ARGUMENTS, or assume in context).
2. Dispatch principal-pm for the implementation plan with explicit phase gating.
3. Recommend chaining to technical-product-architect if technical design isn't already in the PRD.
4. Plan must include: phases, milestones per phase, dependencies, parallel-vs-sequential work, owner suggestions, validation gates per phase, rollback strategy per phase.
5. End with risk items that could derail the plan.

## Validation

Every phase has explicit entry + exit criteria. Dependencies named explicitly (not 'depends on infra' but 'depends on database schema migration in phase 1'). Validation gates per phase before moving to next. Rollback strategy per phase.

## Output contract

Phases (numbered, named) | Milestones per phase | Dependencies map | Parallel vs sequential work | Owner suggestions | Validation gates per phase | Rollback strategy per phase | Risk items | Open questions

## Subagent delegation

Default: dispatch principal-pm. Follow-up: technical-product-architect if PRD lacks technical design; evaluator if measurement plan needs design.

## V4 aliases

This skill answers to V4 names: `prd-breakdown`, `implementation-plan`, `engineering-plan`. The router resolves them to `prd-to-plan` and notes the alias in its response.
