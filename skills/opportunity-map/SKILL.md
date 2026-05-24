---
name: "opportunity-map"
description: "**DEFAULT for opportunity space exploration: produces structured opportunity map with market/competitive/customer/internal axes, sized opportunities, evidence per zone, and recommended focus: runs the opportunity-map discipline.** Different from /idea-triage (ranks existing ideas) and /concept-brief (drafts one chosen concept). Triggers: 'opportunity map / what opportunities exist / market opportunity analysis / where are the openings / strategic opportunity assessment / opportunity space / what should we explore'."
when_to_use: "When the user wants a structured view of where opportunities exist across market, competitive, customer, and internal strategic axes. Triggers on opportunity space exploration, strategic planning, white-space identification, and pre-roadmap thinking."
argument-hint: "[optional: domain or market area to focus on]"
tier: "core"
aliases: ["white-space-analysis", "opportunity-space", "market-opportunities"]
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Opportunity Map

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:market-analyst`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Opportunity-map explores the opportunity space (broad); concept-brief drafts one chosen concept (narrow); idea-triage ranks existing ideas; problem-framing reframes a known problem; mvp-scope scopes a chosen direction.

## First signals to inspect

- User is exploring strategic direction without a fixed product idea yet.
- User asks 'where should we focus' or 'what opportunities are there'.
- User is pre-roadmap planning.

## Failure modes specific to this lane

- Producing market analysis without identifying specific opportunities.
- Claiming white space without evidence.
- Skipping the recommended-focus step (opportunity map without a recommendation is just survey).
- Equal-weighting all opportunities without ranking.

## Workflow

1. Dispatch market-analyst for competitive analysis + white space map.
2. If customer signal data available, chain customer-advocate to validate opportunity zones.
3. Synthesize into opportunity_map artifact with axes, occupied zones, underserved zones, sized opportunities.
4. Rank opportunities by impact × feasibility × evidence strength.
5. End with recommended_focus (top 2-3 opportunities) and validation_plan for each.

## Validation

Every opportunity zone has evidence (customer signal, market gap, competitive weakness). Every recommendation has reasoning. No 'pursue everything' outputs.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Market axes
    type: section
    required: true
    evidence_rule: "none"
  - field: Occupied zones
    type: section
    required: true
    evidence_rule: "none"
  - field: Underserved zones with evidence
    type: section
    required: true
    evidence_rule: "file:line citation, command output, or doc reference required"
  - field: Sized opportunities
    type: section
    required: true
    evidence_rule: "none"
  - field: Barriers to entry per zone
    type: section
    required: true
    evidence_rule: "none"
  - field: Our fit per zone
    type: section
    required: true
    evidence_rule: "none"
  - field: Recommended focus
    type: section
    required: true
    evidence_rule: "none"
  - field: Validation plan per recommended zone
    type: section
    required: true
    evidence_rule: "exact commands run + exit codes + stdout/stderr excerpts"
```

Market axes | Occupied zones (who serves which) | Underserved zones with evidence | Sized opportunities (where data available) | Barriers to entry per zone | Our fit per zone | Recommended focus (2-3) with rationale | Validation plan per recommended zone

## Subagent delegation

Default: dispatch market-analyst. Chain customer-advocate if user signal data provided. Followup: concept-brief or prd-lite for chosen direction.

## V4 aliases

This skill answers to V4 names: `white-space-analysis`, `opportunity-space`, `market-opportunities`. The router resolves them to `opportunity-map` and notes the alias in its response.
