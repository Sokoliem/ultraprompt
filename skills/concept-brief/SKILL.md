---
name: "concept-brief"
description: "**DEFAULT for concept-stage thinking — produces a structured concept brief (problem, target users, proposed approach, key differentiator, success criteria, top risks, validation plan, decision required).** Different from /prd-lite (early-stage PRD), /idea-triage (multi-idea ranking), /problem-framing (problem definition only)."
when_to_use: "When the user has chosen one concept and wants a structured one-page brief that captures the concept clearly enough for stakeholder review or pre-PRD validation."
argument-hint: "<concept name or topic>"
tier: "core"
aliases: ["concept-doc", "concept-one-pager"]
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Concept Brief

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:principal-pm`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

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

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Problem statement
    type: section
    required: true
    evidence_rule: "none"
  - field: Target users + jobs
    type: section
    required: true
    evidence_rule: "none"
  - field: Proposed approach summary
    type: section
    required: true
    evidence_rule: "none"
  - field: Key differentiator
    type: section
    required: true
    evidence_rule: "none"
  - field: Success criteria sketch
    type: section
    required: true
    evidence_rule: "none"
  - field: Top risks
    type: section
    required: true
    evidence_rule: "named risk + likelihood + impact"
  - field: Validation plan
    type: section
    required: true
    evidence_rule: "exact commands run + exit codes + stdout/stderr excerpts"
  - field: Decision required from stakeholders
    type: section
    required: true
    evidence_rule: "rationale + alternative considered"
```

Problem statement | Target users + jobs | Proposed approach summary | Key differentiator | Success criteria sketch | Top risks (3-5) | Validation plan | Decision required from stakeholders

## Subagent delegation

Default: dispatch principal-pm. Followup if concept approved: prd-standard for full PRD.

## V4 aliases

This skill answers to V4 names: `concept-doc`, `concept-one-pager`. The router resolves them to `concept-brief` and notes the alias in its response.
