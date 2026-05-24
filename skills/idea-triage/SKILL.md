---
name: "idea-triage"
description: "**DEFAULT for deciding what to build from a known set of options: runs structured triage of existing ideas with weighted criteria (customer impact, strategic fit, effort, evidence strength, risk).** Different from /innovation-lead (idea generation), /concept-brief (single concept polish), /opportunity-map (landscape framing, not triage)."
when_to_use: "When the user has a list of ideas/features/options and needs ranked recommendations. Triggers on backlog prioritization, post-brainstorm triage, options narrowing, must-kill decisions."
argument-hint: "[idea list path or topic]"
tier: "core"
aliases: ["prioritize-ideas", "backlog-triage", "feature-prioritization"]
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Idea Triage

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:innovation-lead`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Idea-triage ranks existing ideas; opportunity-map explores the space; problem-framing reframes one known problem; concept-brief drafts one chosen idea; mvp-scope scopes a chosen direction.

## First signals to inspect

- User has 5+ ideas/features and wants ranked recommendations.
- User asks 'which should I build first' or 'prioritize these'.
- User is closing on a roadmap and needs cuts.

## Failure modes specific to this lane

- Recommending 'pursue' for everything.
- Equal-weighting criteria.
- Skipping the must-kill recommendations.
- Producing rank order without per-criterion breakdown.
- Inventing customer impact data not in source.

## Workflow

1. Read the idea list from $ARGUMENTS or context.
2. Dispatch innovation-lead for triage with weighted criteria.
3. If customer signal data available, chain customer-advocate to validate impact claims.
4. Output ranked ideas with per-criterion scores, recommendation, validation step (where applicable).
5. Explicitly call out must-kill and must-pursue items.

## Validation

Triage criteria weighted (not uniform). Every idea has per-criterion breakdown. Must-kill recommendations have specific reason. Pursue recommendations capped at ~30% of total or have explicit justification for higher rates.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Triage criteria with weights
    type: section
    required: true
    evidence_rule: "none"
  - field: Ranked ideas with scores
    type: section
    required: true
    evidence_rule: "none"
  - field: Per-criterion breakdown per idea
    type: section
    required: true
    evidence_rule: "none"
  - field: Recommendations
    type: section
    required: true
    evidence_rule: "concrete action; no vague advice"
  - field: Must-kill list with reasons
    type: section
    required: true
    evidence_rule: "none"
  - field: Must-pursue list with reasons
    type: section
    required: true
    evidence_rule: "none"
  - field: Validation steps for 'validate-first' items
    type: section
    required: true
    evidence_rule: "exact commands run + exit codes + stdout/stderr excerpts"
```

Triage criteria with weights | Ranked ideas with scores | Per-criterion breakdown per idea | Recommendations (pursue/validate/defer/reject) | Must-kill list with reasons | Must-pursue list with reasons | Validation steps for 'validate-first' items

## Subagent delegation

Default: dispatch innovation-lead. Chain customer-advocate if customer signals available. Followup: prd-lite or concept-brief for top-ranked items.

## V4 aliases

This skill answers to V4 names: `prioritize-ideas`, `backlog-triage`, `feature-prioritization`. The router resolves them to `idea-triage` and notes the alias in its response.
