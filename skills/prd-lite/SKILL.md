---
name: "prd-lite"
description: "**DEFAULT for early-stage thinking that doesn't yet warrant a full PRD — produces a 1-2 page structured product doc with problem, users, goals, scope, success criteria.** Different from /prd-standard (full PRD with users + scope + risks), /prd-technical (infra-heavy PRD), /concept-brief (single concept, not yet a product)."
when_to_use: "When the user wants a fast, structured product brief — typically for early ideas, feature triage, or single-engineer-team scope. Not appropriate for cross-team or regulated changes."
argument-hint: "<feature or problem name>"
tier: "core"
aliases: ["one-pager", "opportunity-brief", "quick-prd"]
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# PRD Lite

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:principal-pm`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

PRD-lite is for early thinking; prd-standard for cross-team work; prd-technical for engineering-heavy implementations; prd-ai-feature for ML/agent features; prd-to-plan converts PRD to implementation plan.

## First signals to inspect

- User has an idea but no formal product process yet.
- Single-team scope, no compliance/regulatory exposure.
- User says 'quick' or 'lightweight' or 'one-pager'.

## Failure modes specific to this lane

- Using PRD-lite for cross-team or regulated work (use prd-standard or prd-technical instead).
- Producing freeform prose without the structured sections.
- Skipping non-goals to keep the doc short.

## Workflow

1. Dispatch principal-pm with focus from $ARGUMENTS.
2. Agent produces structured PRD-lite (problem, users, goals, non-goals, must-haves, scope, success criteria, risks, open questions).
3. Length target: 1-2 pages worth of YAML.
4. If user has compliance concerns or cross-team scope, recommend escalating to prd-standard.
5. End with 3-5 open questions ordered by blocking-priority.

## Validation

Every problem statement cites evidence. Non-goals explicit. Success criteria with baseline + target. Acceptance criteria in given/when/then. Skip the deeper PRD sections (technical_considerations, rollout_plan) — those go to prd-standard.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Problem statement
    type: section
    required: true
    evidence_rule: "none"
  - field: Users + jobs-to-be-done
    type: section
    required: true
    evidence_rule: "none"
  - field: Goals + non-goals
    type: section
    required: true
    evidence_rule: "none"
  - field: Must-have requirements
    type: section
    required: true
    evidence_rule: "none"
  - field: Scope boundaries
    type: section
    required: true
    evidence_rule: "none"
  - field: Success criteria
    type: section
    required: true
    evidence_rule: "none"
  - field: Top risks
    type: section
    required: true
    evidence_rule: "named risk + likelihood + impact"
  - field: Open questions
    type: section
    required: true
    evidence_rule: "none"
```

Problem statement (with evidence) | Users + jobs-to-be-done | Goals + non-goals | Must-have requirements | Scope boundaries | Success criteria (baseline+target) | Top risks | Open questions

## Subagent delegation

Default: dispatch principal-pm. For deeper analysis: recommend prd-standard or prd-technical.

## V4 aliases

This skill answers to V4 names: `one-pager`, `opportunity-brief`, `quick-prd`. The router resolves them to `prd-lite` and notes the alias in its response.
