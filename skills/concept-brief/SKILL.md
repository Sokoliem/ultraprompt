---
name: "concept-brief"
description: "When user says 'concept brief for X / one-pager for this concept / quick concept doc / concept summary / explain this idea in a page / concept-stage spec / pre-PRD concept' — produces a structured concept brief (problem, target users, proposed approach, key differentiator, success criteria, top risks, validation plan, decision required). DEFAULT for concept-stage thinking. Lighter than prd-lite; richer than a freeform notes."
when_to_use: "When the user has chosen one concept and wants a structured one-page brief that captures the concept clearly enough for stakeholder review or pre-PRD validation."
argument-hint: "<concept name or topic>"
tier: "core"
aliases: ["concept-doc", "concept-one-pager"]
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Concept Brief

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:principal-pm`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Panel escalation (V8)

Deep-budget or high-consequence versions of this lane can escalate to: `idea-panel`, `prd-panel`. Preferred: `idea-panel`. Use panel escalation for independent specialist breadth; keep the default path lighter for ordinary requests.

## Distinctive judgment

Concept-brief is concept-stage (one chosen idea, not yet PRD); prd-lite is fast PRD; opportunity-map explores broadly; idea-triage ranks; problem-framing reframes. Use concept-brief before prd-lite when stakeholder approval of the concept is needed first.

## First signals to inspect

- User has chosen a concept but isn't ready for full PRD.
- User needs to socialize the concept with stakeholders before deeper specification.
- Pre-PRD stage with decision-required framing.

## Failure modes specific to this lane

- Skipping the differentiator (concept brief without clear 'why this approach' is incomplete).
- Missing the decision-required statement (concept briefs need an explicit ask).
- Producing a full PRD when the user wanted a one-pager.
- Marketing prose instead of structured artifact.

## Workflow

1. Dispatch principal-pm for concept brief.
2. Brief includes: problem, target users + jobs, proposed approach summary, key differentiator, success criteria sketch, top 3-5 risks, validation plan, decision required from stakeholders.
3. Length target: ~1 page worth of YAML.
4. End with decision_required (specific ask: 'approve concept' / 'validate first' / 'kill').

## Validation

Differentiator explicit (what makes this approach different). Top risks named (3-5). Validation plan present. Decision-required statement explicit.

## Output contract

Problem statement | Target users + jobs | Proposed approach summary | Key differentiator | Success criteria sketch | Top risks (3-5) | Validation plan | Decision required from stakeholders

## Subagent delegation

Default: dispatch principal-pm. Followup if concept approved: prd-standard for full PRD.

## V4 aliases

This skill answers to V4 names: `concept-doc`, `concept-one-pager`. The router resolves them to `concept-brief` and notes the alias in its response.
