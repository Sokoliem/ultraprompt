---
name: "mvp-scope"
description: "When user says 'scope the MVP / minimum viable scope / what's the MVP / cut this to MVP / MVP definition / smallest shippable version / phase 1 scope / what to include in MVP' — produces structured MVP scope with must/should/won't-have per phase, scope cuts with reasoning, validation plan for what we keep, and what we'd add post-MVP. DEFAULT for MVP scoping decisions. Different from prd-to-plan (sequences the whole PRD) and prd-lite (drafts the PRD itself)."
when_to_use: "When the user is scoping the minimum viable version of a product or feature. Triggers on MVP discussions, scope cuts, phase-1 definitions, and 'what's the smallest we can ship that proves the hypothesis'."
argument-hint: "<product or feature to scope>"
tier: "core"
aliases: ["minimum-viable-scope", "phase-1-scope", "mvp-definition"]
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# MVP Scope

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:principal-pm`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

MVP-scope decides what's in the smallest shippable version; prd-to-plan sequences the whole PRD into phases; concept-brief drafts the concept; prd-lite drafts the PRD. Use MVP-scope when scope-cutting decisions are the primary need.

## First signals to inspect

- User says 'MVP' or 'minimum viable' or 'smallest shippable'.
- User has a larger feature/PRD and needs to cut scope.
- User wants to validate a hypothesis before building the full version.

## Failure modes specific to this lane

- Including too much in 'must-have' (MVP becomes the full product).
- Skipping the hypothesis the MVP is supposed to validate.
- Missing post-MVP roadmap (what would be added after).
- Generic 'launch fast' framing without specific scope cuts.
- Failing to name what's explicitly cut and why.

## Workflow

1. Dispatch principal-pm for MVP scope.
2. Output names the hypothesis the MVP validates ('users will X if we ship Y').
3. Must-have: minimum to validate hypothesis (typically 3-7 items).
4. Should-have: improves validation but not required.
5. Won't-have-this-MVP: explicit cuts with reasoning.
6. Validation plan: how we know the MVP succeeded.
7. Post-MVP roadmap: what we'd add in phase 2/3 if validation succeeds.
8. End with explicit cut-list and ship-criteria.

## Validation

Hypothesis-driven (MVP validates a specific hypothesis). Must-have list capped (typically ≤7 items). Cuts have explicit reasoning. Validation criteria measurable. Post-MVP roadmap present.

## Output contract

Hypothesis MVP validates | Must-have (3-7 items, with reason) | Should-have | Won't-have-this-MVP with cut reasons | Validation plan | Success criteria | Failure criteria (when to abandon hypothesis) | Post-MVP roadmap sketch

## Subagent delegation

Default: dispatch principal-pm. Followup: evaluator for validation plan design; prd-to-plan to break the chosen MVP into engineering work.

## V4 aliases

This skill answers to V4 names: `minimum-viable-scope`, `phase-1-scope`, `mvp-definition`. The router resolves them to `mvp-scope` and notes the alias in its response.
