---
name: "prd-technical"
description: "When user says 'technical PRD for X / engineering spec / technical product doc / infrastructure PRD / platform feature spec / heavy-tech feature requirements' — produces a PRD oriented around technical design with deeper technical_considerations, data model implications, API surface, integrations, failure modes, telemetry. DEFAULT for infrastructure work, platform features, developer tools, or any product where technical shape is the primary risk. Combines principal-pm and technical-product-architect outputs."
when_to_use: "When the product change is technical-heavy — infrastructure, platform, dev tools, APIs, data pipelines. Less time on customer journey; more time on system shape."
argument-hint: "<technical feature or platform name>"
tier: "core"
aliases: ["tech-prd", "engineering-spec", "infra-prd"]
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Technical PRD

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:principal-pm`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Panel escalation (V8)

Deep-budget or high-consequence versions of this lane can escalate to: `prd-panel`. Preferred: `prd-panel`. Use panel escalation for independent specialist breadth; keep the default path lighter for ordinary requests.

## Distinctive judgment

PRD-technical is for engineering-heavy features; prd-standard is general product; prd-ai-feature is for ML/agent; prd-lite is early-stage. Use prd-technical when the technical risk dwarfs the product risk.

## First signals to inspect

- User is building infrastructure, platform, or developer tools.
- Technical shape (data model, APIs, integrations) is the primary risk.
- User says 'engineering' or 'technical' or 'infrastructure' in the request.

## Failure modes specific to this lane

- Skipping the user-facing problem statement.
- Producing technical design without product requirements traceability.
- Missing failure modes and telemetry.
- No rollout strategy.

## Workflow

1. Dispatch principal-pm first for problem + users + goals + non-goals.
2. Then dispatch technical-product-architect for data model + API + integrations + failure modes + telemetry + rollout.
3. Combine into single PRD-technical artifact with explicit traceability between sections.
4. Recommend chaining to risk-and-controls-reviewer for any change touching auth, payment, PII, or third-party services.
5. End with prioritized open_technical_questions + open_product_questions.

## Validation

Product requirements traceable to technical decisions. Every technical change has a product driver OR is flagged as technical-only. At least 5 failure modes. Telemetry for product validation included. Rollback strategy explicit.

## Output contract

Problem statement + evidence | Users + jobs-to-be-done | Goals + non-goals | Must/should/won't-have requirements | Scope (in/out) | Technical design: data model (entities, fields, indexes, migrations) | Technical design: API surface (endpoints, request/response shapes, deprecations) | Technical design: integration points (upstream, downstream, third-party) | Technical design: sequence flows + failure modes (≥5) | Technical design: feature flags + telemetry events + metrics | Performance considerations + security_and_privacy + rollout_technical_plan | Risks (severity × likelihood) | Acceptance criteria (given/when/then) | Rollout plan with phase gates | Validation plan | Open product questions + open technical questions

## Subagent delegation

Default: chain principal-pm → technical-product-architect. Follow-up: risk-and-controls-reviewer + security-auditor for sensitive surfaces.

## V4 aliases

This skill answers to V4 names: `tech-prd`, `engineering-spec`, `infra-prd`. The router resolves them to `prd-technical` and notes the alias in its response.
