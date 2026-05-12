---
name: "prd-standard"
description: "When user says 'full PRD for X / product requirements doc / write the PRD / comprehensive product spec / standard PRD' — produces a full structured product doc with problem, users, goals, non-goals, must/should/won't-have, scope, technical considerations, risks, metrics, acceptance criteria, rollout plan, validation plan, open questions. DEFAULT for any product change crossing teams or with meaningful complexity. Use prd-lite for early-stage; prd-technical for heavily technical features."
when_to_use: "When the user wants a complete PRD for a meaningful product change — cross-team scope, non-trivial complexity, or pre-engineering-kickoff documentation."
argument-hint: "<feature or product change name>"
tier: "core"
aliases: ["prd", "full-prd", "product-spec"]
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# PRD Standard

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:principal-pm`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Panel escalation (V8)

Deep-budget or high-consequence versions of this lane can escalate to: `prd-panel`. Preferred: `prd-panel`. Use panel escalation for independent specialist breadth; keep the default path lighter for ordinary requests.

## Distinctive judgment

PRD-standard is the default PRD; prd-lite for fast/lightweight; prd-technical for engineering-heavy; prd-ai-feature for ML/agent; prd-to-plan converts to implementation plan.

## First signals to inspect

- User explicitly asks for 'a PRD' or 'product requirements doc'.
- Cross-team work, meaningful complexity, or pre-engineering kickoff.
- Feature has user-facing impact and warrants formal documentation.

## Failure modes specific to this lane

- Producing marketing prose instead of structured artifact.
- Skipping non-goals (the most common failure).
- Metrics without baselines.
- Acceptance criteria without given/when/then format.

## Workflow

1. Dispatch principal-pm with focus from $ARGUMENTS.
2. Agent produces the full PRD per its output contract.
3. Verify all required sections present: problem, users_and_jobs, goals, non_goals, requirements, scope, technical_considerations, risks, metrics, acceptance_criteria, rollout_plan, validation_plan, open_questions.
4. If technical depth warrants, recommend chaining to technical-product-architect.
5. If compliance/regulatory exposure, recommend chaining to risk-and-controls-reviewer.
6. End with prioritized open_questions.

## Validation

Every problem claim cites evidence. Non-goals explicit (3-5). All metrics have baseline + target + measurement method. Acceptance criteria in given/when/then. Rollout plan with phase gate criteria. Risks ranked by severity × likelihood with mitigations.

## Output contract

Problem statement with evidence | Users + jobs-to-be-done | Goals + non-goals (3-5) | Requirements (must/should/won't-have) | Scope (in/out) | Technical considerations | Risks (severity × likelihood + mitigations) | Metrics (leading/lagging/guardrails with baselines+targets) | Acceptance criteria (given/when/then) | Rollout plan with phase gates | Validation plan | Open questions ranked by blocking-priority

## Subagent delegation

Default: dispatch principal-pm. Follow-up: technical-product-architect for technical design; risk-and-controls-reviewer for compliance/privacy; evaluator for measurement design.

## V4 aliases

This skill answers to V4 names: `prd`, `full-prd`, `product-spec`. The router resolves them to `prd-standard` and notes the alias in its response.
