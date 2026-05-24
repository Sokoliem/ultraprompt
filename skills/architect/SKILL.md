---
name: "architect"
description: "**DEFAULT for ARCHITECTURAL QUESTIONS — boundaries, contracts, and system design with tradeoffs: architectural question framing + current vs intended shape + gaps + cost-assessment with recommendation.** Different from /build (implements the architecture), /review (PR-scope), /repo-review (whole-repo audit without design recommendation). Triggers: 'should we use X or Y, how should we structure this, design tradeoffs, system boundaries'."
when_to_use: "Use for module/package boundary questions, coupling concerns, dependency-direction analysis, or abstraction-quality review. Do not use for diff review (use review). Do not use for state-transition lifecycle work (use state-machine-review specialist). For monorepo-specific structure, see `_shared/playbooks/monorepo-architecture-checklist.md`."
argument-hint: "[module|package|subsystem|architectural question]"
tier: "core"
aliases: ["architecture-review", "monorepo-architecture"]
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Architect

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:reviewer` (focus: `architecture`). See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Module boundaries, coupling, dependency direction, abstraction quality, long-term design risk. The question is not 'is this clean?' but 'will this hold up under expected change?' Identify cycles, leaky abstractions, and dependency inversions that violate the intended layering. Defer judgment when the team's design intent isn't documented.

## First signals to inspect

- Top-level package/module structure and intended layering (read CLAUDE.md, ADRs, design docs)
- Import graph: who depends on whom; are there cycles?
- Public API surfaces between modules (clean? minimal? leaky?)
- Cross-cutting concerns: how are logging, auth, tracing handled across boundaries
- Abstractions: do they hide complexity or just shuffle it?
- Pain points in recent changes (commits/PRs that touched many files often indicate boundary problems)

## Failure modes specific to this lane

- Critiquing as 'should be cleaner' without showing the concrete cost of the current shape
- Recommending a refactor without knowing the team's design intent
- Conflating coupling with dependency (some coupling is essential)
- Missing the difference between accidental and essential complexity
- Producing recommendations the team can't act on (rewrite the world)

## Workflow

1. Identify the architectural question or focus area from `$ARGUMENTS`.
2. Map the current shape: packages, modules, dependency graph, public surfaces.
3. Read existing design docs/ADRs to understand intended structure.
4. Identify gaps between intended and actual: cycles, layer violations, leaky abstractions.
5. Assess the cost: which changes have been hard recently? Which boundaries are friction points?
6. Produce findings ordered by impact and reversibility.
7. Recommend incremental improvements; flag where a larger redesign would be warranted.
8. Stay read-only; do not refactor as part of this skill.

## Validation

No code changes; this skill is read-only. Validate findings by referring to recent commits/PRs that confirm or contradict the assessment.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Architectural Question
    type: section
    required: true
    evidence_rule: "none"
  - field: Current Shape
    type: section
    required: true
    evidence_rule: "none"
  - field: Intended Shape
    type: section
    required: true
    evidence_rule: "none"
  - field: Gaps + Evidence
    type: section
    required: true
    evidence_rule: "file:line citation, command output, or doc reference required"
  - field: Cost Assessment
    type: section
    required: true
    evidence_rule: "none"
  - field: Recommendations
    type: section
    required: true
    evidence_rule: "concrete action; no vague advice"
  - field: What Would Confirm/Refute
    type: section
    required: true
    evidence_rule: "none"
```

Architectural Question | Current Shape | Intended Shape (from docs/ADRs) | Gaps + Evidence | Cost Assessment | Recommendations (incremental) | Recommendations (larger redesign, flagged) | What Would Confirm/Refute

## Subagent delegation

Use `reviewer` with focus=architecture for a second perspective. Use `scout` for unfamiliar territory. For deep ADR documentation work, see `_shared/playbooks/adr-template.md`.

## V4 aliases

This skill answers to V4 names: `architecture-review`, `monorepo-architecture`. The router resolves them to `architect` and notes the alias in its response.
